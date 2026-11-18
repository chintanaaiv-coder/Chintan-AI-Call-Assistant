"""Speech: understanding the caller (speech-to-text) and speaking (text-to-speech).

SPEECH_PROVIDER=gemini (default): everything runs on the same Gemini key as the
AI brain. A natural Indian assistant voice, not your own voice.
SPEECH_PROVIDER=elevenlabs: speaks in your cloned voice (needs a paid ElevenLabs plan).

Phone audio is 8 kHz, 16-bit mono.
"""
from __future__ import annotations

import array
import base64
import re

import httpx

from .audio import RATE, to_wav
from .config import Config

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"


def resample(pcm: bytes, src_rate: int, dst_rate: int = RATE) -> bytes:
    """Change sample rate of 16-bit mono PCM. Whole-number ratios (24k -> 8k)
    average each group of samples, which also filters out the highs."""
    if src_rate == dst_rate or not pcm:
        return pcm
    src = array.array("h", pcm[: len(pcm) // 2 * 2])
    if src_rate % dst_rate == 0:
        k = src_rate // dst_rate
        out = array.array("h", (sum(src[i:i + k]) // k for i in range(0, len(src) - k + 1, k)))
        return out.tobytes()
    n = int(len(src) * dst_rate / src_rate)
    step = src_rate / dst_rate
    out = array.array("h")
    for i in range(n):
        pos = i * step
        j = int(pos)
        frac = pos - j
        a = src[j]
        b = src[j + 1] if j + 1 < len(src) else a
        out.append(int(a + (b - a) * frac))
    return out.tobytes()


def _rate_from_mime(mime: str, default: int = 24000) -> int:
    m = re.search(r"rate=(\d+)", mime or "")
    return int(m.group(1)) if m else default


class Speech:
    def __init__(self, cfg: Config, http: httpx.AsyncClient | None = None):
        self.cfg = cfg
        self.http = http or httpx.AsyncClient(timeout=30)

    @property
    def provider(self) -> str:
        return self.cfg.speech_provider

    # --- understanding the caller ---
    async def transcribe(self, pcm: bytes) -> str:
        if self.provider == "elevenlabs":
            return await self._eleven_transcribe(pcm)
        return await self._gemini_transcribe(pcm)

    async def _gemini_transcribe(self, pcm: bytes) -> str:
        r = await self.http.post(
            f"{GEMINI}/{self.cfg.gemini_model}:generateContent",
            headers={"x-goog-api-key": self.cfg.gemini_api_key},
            json={
                "contents": [{"role": "user", "parts": [
                    {"text": "Transcribe exactly what the caller says in this phone audio. It may be English, "
                             "Hindi, Gujarati or a mix: write Hindi and Gujarati in Roman letters. Reply with "
                             "only the words spoken. If there is no clear speech, reply with nothing."},
                    {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(to_wav(pcm)).decode()}},
                ]}],
                "generationConfig": {"temperature": 0},
            },
        )
        r.raise_for_status()
        parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()

    async def _eleven_transcribe(self, pcm: bytes) -> str:
        r = await self.http.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": self.cfg.elevenlabs_api_key},
            data={"model_id": self.cfg.stt_model},
            files={"file": ("utterance.wav", to_wav(pcm), "audio/wav")},
        )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()

    # --- speaking ---
    async def speak(self, text: str) -> bytes:
        """Returns raw 8 kHz 16-bit mono PCM."""
        if self.provider == "elevenlabs":
            return await self._eleven_speak(text)
        return await self._gemini_speak(text)

    async def _gemini_speak(self, text: str) -> bytes:
        r = await self.http.post(
            f"{GEMINI}/{self.cfg.gemini_tts_model}:generateContent",
            headers={"x-goog-api-key": self.cfg.gemini_api_key},
            json={
                "contents": [{"parts": [{"text": f"{self.cfg.voice_style}: {text}"}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.cfg.gemini_voice}}},
                },
            },
        )
        r.raise_for_status()
        part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(part["data"])
        return resample(pcm, _rate_from_mime(part.get("mimeType", "")))

    async def _eleven_speak(self, text: str) -> bytes:
        r = await self.http.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}",
            params={"output_format": "pcm_8000"},
            headers={"xi-api-key": self.cfg.elevenlabs_api_key},
            json={"text": text, "model_id": self.cfg.tts_model},
        )
        r.raise_for_status()
        return r.content
