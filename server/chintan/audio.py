"""Audio helpers for 8 kHz, 16-bit mono phone audio (no extra libraries needed)."""
from __future__ import annotations

import array
import io
import math
import wave

RATE = 8000
BYTES_PER_MS = RATE * 2 // 1000  # 16 bytes per millisecond


def rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    samples = array.array("h", pcm[: len(pcm) // 2 * 2])
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def to_wav(pcm: bytes, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class Utterances:
    """Simple voice-activity detection: collects caller audio and returns one
    utterance when the caller has spoken and then gone quiet."""

    def __init__(self, threshold: float = 500.0, end_silence_ms: int = 700,
                 min_speech_ms: int = 300, max_ms: int = 15000):
        self.threshold = threshold
        self.end_silence = end_silence_ms * BYTES_PER_MS
        self.min_speech = min_speech_ms * BYTES_PER_MS
        self.max_len = max_ms * BYTES_PER_MS
        self.reset()

    def reset(self) -> None:
        self.buf = bytearray()
        self.speech_bytes = 0
        self.silence_run = 0

    def feed(self, pcm: bytes) -> bytes | None:
        loud = rms(pcm) >= self.threshold
        if not self.buf and not loud:
            return None  # still waiting for speech to start
        self.buf += pcm
        if loud:
            self.speech_bytes += len(pcm)
            self.silence_run = 0
        else:
            self.silence_run += len(pcm)
        done = (self.silence_run >= self.end_silence and self.speech_bytes >= self.min_speech) \
            or len(self.buf) >= self.max_len
        if self.silence_run >= self.end_silence and self.speech_bytes < self.min_speech:
            self.reset()  # a click or a cough, not speech
            return None
        if done:
            out = bytes(self.buf)
            self.reset()
            return out
        return None


class Recorder:
    """Two-track recording: caller on the left channel, assistant on the right,
    kept in time with each other. Saved as one stereo WAV."""

    def __init__(self):
        self.caller = bytearray()
        self.assistant = bytearray()

    def add_caller(self, pcm: bytes) -> None:
        self.caller += pcm

    def add_assistant(self, pcm: bytes) -> None:
        # Assistant audio starts "now" on the timeline (where the caller track is).
        if len(self.assistant) < len(self.caller):
            self.assistant += bytes(len(self.caller) - len(self.assistant))
        self.assistant += pcm

    def wav(self) -> bytes:
        n = max(len(self.caller), len(self.assistant))
        left = array.array("h", bytes(self.caller) + bytes(n - len(self.caller)))
        right = array.array("h", bytes(self.assistant) + bytes(n - len(self.assistant)))
        stereo = array.array("h", bytes(n * 2))
        stereo[0::2] = left
        stereo[1::2] = right
        return to_wav(stereo.tobytes(), channels=2)

    def empty(self) -> bool:
        return not self.caller and not self.assistant
