"""One screened call, whether it arrives by phone or from the text simulator.

The session holds the conversation, asks the AI for each reply, relays the
owner's messages word for word, and handles Join / End from the app.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import WebSocket

from .ai import Brain
from .deadlines import deadline_info
from .store import Store

SpeakFn = Callable[[str], Awaitable[None]]


class Hub:
    """Live updates to every open copy of the app."""

    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def broadcast(self, event: dict) -> None:
        dead = []
        msg = json.dumps(event)
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


class CallSession:
    live: dict[str, "CallSession"] = {}

    def __init__(self, store: Store, brain: Brain, hub: Hub, caller_number: str | None, source: str,
                 speak: SpeakFn | None = None, recordings_dir: Path | None = None):
        self.store, self.brain, self.hub = store, brain, hub
        self.caller_number = caller_number
        self.source = source
        self.id = store.create_call(caller_number, source)
        self.turns: list[dict] = []
        self.analysis: dict = {}
        self.join_requested = False
        self.ended = asyncio.Event()
        self._speak = speak or (lambda text: asyncio.sleep(0))
        self._lock = asyncio.Lock()
        self.recorder = None  # set by the phone transport
        self.recordings_dir = recordings_dir
        CallSession.live[self.id] = self

    # --- helpers ---
    async def _add(self, speaker: str, text: str) -> None:
        turn = self.store.add_turn(self.id, speaker, text)
        self.turns.append(turn)
        await self.hub.broadcast({"type": "turn", **turn})

    async def say(self, text: str, speaker: str = "assistant") -> None:
        async with self._lock:
            await self._add(speaker, text)
            await self._speak(text)

    async def _publish(self) -> None:
        await self.hub.broadcast({"type": "call_updated", "call": self.store.get_call(self.id, with_turns=False)})

    # --- the conversation ---
    async def start(self, greeting: str) -> None:
        await self._publish()
        await self.say(greeting)

    async def on_caller_text(self, text: str) -> dict | None:
        text = text.strip()
        if not text or self.ended.is_set():
            return None
        await self._add("caller", text)
        result = await self.brain.next_turn(self.turns, self.caller_number, self.store.settings())
        if self.ended.is_set():  # owner joined or ended while the AI was thinking
            return result
        self.analysis = {k: v for k, v in result.items() if k not in ("say", "end_call")}
        self.store.update_call(self.id, analysis=self.analysis)
        await self._publish()
        await self.say(result["say"])
        if result["end_call"]:
            await self.finish("message_taken")
        return result

    # --- owner controls from the app ---
    async def owner_message(self, text: str) -> None:
        """Said to the caller exactly as typed: the AI never adds to it."""
        if text.strip() and not self.ended.is_set():
            await self.say(text.strip(), speaker="owner_message")

    async def join(self) -> None:
        if self.ended.is_set():
            return
        self.join_requested = True
        await self.say("Please hold, I'm connecting you to him now.")
        await self.finish("joined")

    async def end_by_owner(self) -> None:
        if self.ended.is_set():
            return
        await self.say("Thanks for calling. I've noted everything and he'll get back to you.")
        await self.finish("message_taken")

    # --- wrap up ---
    async def finish(self, outcome: str) -> None:
        if self.ended.is_set():
            return
        self.ended.set()
        analysis = dict(self.analysis)
        analysis.update(deadline_info(analysis.get("compliance_type")))
        fields = {"status": "ended", "ended_at": time.time(), "outcome": outcome, "analysis": analysis}
        if self.recorder is not None and not self.recorder.empty() and self.recordings_dir:
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
            path = self.recordings_dir / f"{self.id}.wav"
            path.write_bytes(self.recorder.wav())
            fields["recording"] = str(path)
        self.store.update_call(self.id, **fields)
        CallSession.live.pop(self.id, None)
        await self._publish()
        await self.hub.broadcast({"type": "call_ended", "call_id": self.id, "outcome": outcome})
