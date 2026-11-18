"""Real phone calls through Exotel's Voicebot applet (bidirectional audio stream).

Call flow you set up in Exotel (see docs/SETUP.md):
  Incoming call on your Exotel number -> Voicebot applet (this websocket)
  -> Passthru applet (GET /exotel/after-stream) -> on 200: Connect to your mobile,
                                                 -> otherwise: Hangup.

Audio both ways: base64 16-bit linear PCM, 8 kHz, mono.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from .audio import Recorder, Utterances
from .session import CallSession

log = logging.getLogger("chintan.phone")
CHUNK = 3200  # 200 ms of audio per message (a multiple of 320 bytes, as Exotel asks)

# Exotel call_sid -> should the Passthru applet connect the caller to the owner?
connect_after_stream: dict[str, bool] = {}


class ExotelCall:
    def __init__(self, ws: WebSocket, app_state):
        self.ws = ws
        self.s = app_state
        self.stream_sid = ""
        self.call_sid = ""
        self.session: CallSession | None = None
        self.vad = Utterances()
        self.recorder = Recorder()
        self.pending_marks: dict[str, asyncio.Event] = {}
        self.busy = False  # the assistant is talking or thinking: caller audio is recorded, not transcribed

    async def send_audio(self, pcm: bytes) -> None:
        self.recorder.add_assistant(pcm)
        for i in range(0, len(pcm), CHUNK):
            chunk = pcm[i:i + CHUNK]
            if len(chunk) % 320:
                chunk += bytes(320 - len(chunk) % 320)
            await self.ws.send_text(json.dumps({"event": "media", "stream_sid": self.stream_sid,
                                                "media": {"payload": base64.b64encode(chunk).decode()}}))
        name = uuid.uuid4().hex[:8]
        done = asyncio.Event()
        self.pending_marks[name] = done
        await self.ws.send_text(json.dumps({"event": "mark", "stream_sid": self.stream_sid, "mark": {"name": name}}))
        # Wait until Exotel has played it, so the caller isn't talked over (cap in case no mark comes back).
        seconds = len(pcm) / 16000
        try:
            await asyncio.wait_for(done.wait(), timeout=seconds + 3)
        except asyncio.TimeoutError:
            pass
        self.pending_marks.pop(name, None)

    async def speak(self, text: str) -> None:
        try:
            pcm = await self.s.speech.speak(text)
        except Exception as e:
            log.warning("TTS failed: %s", e)
            return
        await self.send_audio(pcm)

    async def handle_utterance(self, pcm: bytes) -> None:
        self.busy = True
        try:
            text = await self.s.speech.transcribe(pcm)
            if text and self.session:
                await self.session.on_caller_text(text)
        except Exception as e:
            log.warning("turn failed: %s", e)
        finally:
            self.busy = False
            self.vad.reset()

    async def run(self) -> None:
        await self.ws.accept()
        tasks: set[asyncio.Task] = set()
        try:
            while True:
                msg = json.loads(await self.ws.receive_text())
                ev = msg.get("event")
                if ev == "start":
                    await self.on_start(msg.get("start", {}))
                    tasks.add(asyncio.create_task(self.watch_end()))
                elif ev == "media" and self.session:
                    pcm = base64.b64decode(msg.get("media", {}).get("payload", ""))
                    self.recorder.add_caller(pcm)
                    if not self.busy and not self.session.ended.is_set():
                        utt = self.vad.feed(pcm)
                        if utt:
                            tasks.add(asyncio.create_task(self.handle_utterance(utt)))
                elif ev == "mark":
                    e = self.pending_marks.get(msg.get("mark", {}).get("name", ""))
                    if e:
                        e.set()
                elif ev == "stop":
                    break
        except (WebSocketDisconnect, RuntimeError):
            pass  # caller hung up, or we closed the stream ourselves
        finally:
            for t in tasks:
                t.cancel()
            if self.session and not self.session.ended.is_set():
                await self.session.finish("caller_hung_up")

    async def on_start(self, start: dict) -> None:
        self.stream_sid = start.get("stream_sid", "")
        self.call_sid = start.get("call_sid", "")
        caller = start.get("from")
        st = self.s.store.settings()
        self.session = CallSession(self.s.store, self.s.brain, self.s.hub, caller, "phone",
                                   speak=self.speak, recordings_dir=self.s.cfg.data_dir / "recordings")
        self.session.recorder = self.recorder
        connect_after_stream[self.call_sid] = False

        if st["snoozed"]:
            # Snoozed: put the caller straight through to the owner.
            connect_after_stream[self.call_sid] = True
            await self.session.finish("snoozed")
            return
        if self.s.store.is_muted(caller):
            await self.session.start("Sorry, he isn't available. Goodbye.")
            await self.session.finish("muted")
            return
        self.busy = True
        await self.session.start(self.s.cfg.greeting_text())
        self.busy = False

    async def watch_end(self) -> None:
        """When the session ends (AI wrapped up, owner joined or ended), close the stream so
        Exotel moves on to the Passthru applet."""
        await self.session.ended.wait()
        if self.session.join_requested:
            connect_after_stream[self.call_sid] = True
        await asyncio.sleep(0.5)
        try:
            await self.ws.close()
        except Exception:
            pass
