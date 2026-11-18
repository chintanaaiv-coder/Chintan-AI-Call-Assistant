"""Chintan AI Call Assistant - server.

Run locally:  uvicorn chintan.main:app --reload   (from the server/ folder)
"""
from __future__ import annotations

import hmac
import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from .ai import Brain
from .config import Config
from .phone import ExotelCall, connect_after_stream
from .rules import CATEGORIES
from .session import CallSession, Hub
from .speech import Speech
from .store import Store

logging.basicConfig(level=logging.INFO)


class Text(BaseModel):
    text: str


class SettingsIn(BaseModel):
    standing_instructions: str | None = None
    category_rules: list[dict] | None = None
    quick_replies: list[str] | None = None


class Snooze(BaseModel):
    minutes: int  # 0 = resume now


class Number(BaseModel):
    number: str


class SimStart(BaseModel):
    caller_number: str | None = None


class State:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        http = httpx.AsyncClient(timeout=30)
        self.store = Store(cfg.data_dir / "chintan.db")
        self.brain = Brain(cfg, http)
        self.speech = Speech(cfg, http)
        self.hub = Hub()


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or Config()
    app = FastAPI(title="Chintan AI Call Assistant")
    s = State(cfg)
    app.state.s = s

    def _token_ok(token: str | None) -> bool:
        return bool(cfg.app_token) and bool(token) and hmac.compare_digest(token, cfg.app_token)

    def auth(authorization: str = Header(default=""), token: str | None = Query(default=None)):
        given = authorization.removeprefix("Bearer ").strip() or token
        if not _token_ok(given):
            raise HTTPException(401, "Wrong or missing app token")

    def live(call_id: str) -> CallSession:
        sess = CallSession.live.get(call_id)
        if not sess:
            raise HTTPException(409, "That call has already ended")
        return sess

    # --- health ---
    @app.get("/health")
    def health():
        return {"ok": True, "owner": cfg.owner_name, "llm": cfg.llm_provider, "problems": cfg.check()}

    # --- calls ---
    @app.get("/api/calls", dependencies=[Depends(auth)])
    def list_calls(limit: int = 100):
        return {"calls": s.store.list_calls(limit), "categories": CATEGORIES}

    @app.get("/api/calls/{call_id}", dependencies=[Depends(auth)])
    def get_call(call_id: str):
        call = s.store.get_call(call_id)
        if not call:
            raise HTTPException(404, "No such call")
        call["live"] = call_id in CallSession.live
        return call

    @app.get("/api/calls/{call_id}/recording", dependencies=[Depends(auth)])
    def recording(call_id: str):
        path = s.store.recording_path(call_id)
        if not path or not Path(path).exists():
            raise HTTPException(404, "No recording for this call")
        return FileResponse(path, media_type="audio/wav", filename=f"chintan-{call_id}.wav")

    @app.delete("/api/calls/{call_id}", dependencies=[Depends(auth)])
    def delete_call(call_id: str):
        rec = s.store.delete_call(call_id)
        if rec and Path(rec).exists():
            Path(rec).unlink()
        return {"deleted": call_id}


    @app.post("/api/calls/{call_id}/say", dependencies=[Depends(auth)])
    async def say(call_id: str, body: Text):
        await live(call_id).owner_message(body.text)
        return {"ok": True}

    @app.post("/api/calls/{call_id}/join", dependencies=[Depends(auth)])
    async def join(call_id: str):
        await live(call_id).join()
        return {"ok": True}

    @app.post("/api/calls/{call_id}/end", dependencies=[Depends(auth)])
    async def end(call_id: str):
        await live(call_id).end_by_owner()
        return {"ok": True}

    # --- settings, snooze, muted callers ---
    @app.get("/api/settings", dependencies=[Depends(auth)])
    def get_settings():
        return {**s.store.settings(), "muted": s.store.muted_numbers(), "owner_name": cfg.owner_name,
                "categories": CATEGORIES}


    @app.put("/api/settings", dependencies=[Depends(auth)])
    def put_settings(body: SettingsIn):
        return s.store.set_settings(**body.model_dump(exclude_none=True))


    @app.post("/api/snooze", dependencies=[Depends(auth)])
    async def snooze(body: Snooze):
        until = time.time() + body.minutes * 60 if body.minutes > 0 else 0
        st = s.store.set_settings(snoozed_until=until)
        await s.hub.broadcast({"type": "settings", "snoozed_until": until})
        return st


    @app.post("/api/muted", dependencies=[Depends(auth)])
    def mute(body: Number):
        s.store.mute(body.number)
        return {"muted": s.store.muted_numbers()}

    @app.delete("/api/muted/{number}", dependencies=[Depends(auth)])
    def unmute(number: str):
        s.store.unmute(number)
        return {"muted": s.store.muted_numbers()}

    # --- text simulator: test the AI by typing what a caller says ---

    @app.post("/api/simulate", dependencies=[Depends(auth)])
    async def sim_start(body: SimStart):
        sess = CallSession(s.store, s.brain, s.hub, body.caller_number, "simulator")
        await sess.start(cfg.greeting_text())
        return {"call_id": sess.id, "greeting": cfg.greeting_text()}

    @app.post("/api/simulate/{call_id}", dependencies=[Depends(auth)])
    async def sim_turn(call_id: str, body: Text):
        result = await live(call_id).on_caller_text(body.text)
        return {"reply": result and result["say"], "ended": call_id not in CallSession.live,
                "call": s.store.get_call(call_id)}

    # --- live updates to the app ---
    @app.websocket("/ws")
    async def app_socket(ws: WebSocket, token: str = Query(default="")):
        if not _token_ok(token):
            await ws.close(code=4401)
            return
        await ws.accept()
        s.hub.clients.add(ws)
        try:
            while True:
                msg = await ws.receive_json()
                sess = CallSession.live.get(msg.get("call_id", ""))
                if not sess:
                    continue
                if msg.get("type") == "say":
                    await sess.owner_message(msg.get("text", ""))
                elif msg.get("type") == "join":
                    await sess.join()
                elif msg.get("type") == "end":
                    await sess.end_by_owner()
        except (WebSocketDisconnect, RuntimeError, ValueError):
            pass
        finally:
            s.hub.clients.discard(ws)

    # --- Exotel ---
    @app.websocket("/exotel/stream/{secret}")
    async def exotel_stream(ws: WebSocket, secret: str):
        if not cfg.exotel_secret or not hmac.compare_digest(secret, cfg.exotel_secret):
            await ws.close(code=4401)
            return
        await ExotelCall(ws, s).run()

    @app.get("/exotel/after-stream/{secret}")
    def after_stream(secret: str, request: Request):
        """Passthru applet: 200 = connect the caller to the owner's mobile, 302 = hang up."""
        if not cfg.exotel_secret or not hmac.compare_digest(secret, cfg.exotel_secret):
            raise HTTPException(401)
        call_sid = request.query_params.get("CallSid", "")
        if connect_after_stream.pop(call_sid, False):
            return PlainTextResponse("connect", status_code=200)
        return PlainTextResponse("hangup", status_code=302, headers={"Location": "/"})

    return app


app = create_app() if os.environ.get("CHINTAN_NO_AUTOAPP") != "1" else None
