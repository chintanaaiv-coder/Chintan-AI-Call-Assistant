"""Speech-to-text and text-to-speech through ElevenLabs (the voice clone you made
in the mockup). Both work on 8 kHz 16-bit phone audio."""
from __future__ import annotations

import httpx

from .audio import to_wav
from .config import Config


class Speech:
    def __init__(self, cfg: Config, http: httpx.AsyncClient | None = None):
        self.cfg = cfg
        self.http = http or httpx.AsyncClient(timeout=30)

    @property
    def ready(self) -> bool:
        return bool(self.cfg.elevenlabs_api_key and self.cfg.elevenlabs_voice_id)

    async def transcribe(self, pcm: bytes) -> str:
        r = await self.http.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": self.cfg.elevenlabs_api_key},
            data={"model_id": self.cfg.stt_model},
            files={"file": ("utterance.wav", to_wav(pcm), "audio/wav")},
        )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()

    async def speak(self, text: str) -> bytes:
        """Returns raw 8 kHz 16-bit mono PCM in the owner's cloned voice."""
        r = await self.http.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}",
            params={"output_format": "pcm_8000"},
            headers={"xi-api-key": self.cfg.elevenlabs_api_key},
            json={"text": text, "model_id": self.cfg.tts_model},
        )
        r.raise_for_status()
        return r.content
