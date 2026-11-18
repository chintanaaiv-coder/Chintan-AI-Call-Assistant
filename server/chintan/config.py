"""Settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Config:
    owner_name: str = field(default_factory=lambda: _env("OWNER_NAME", "Chintan"))
    owner_phone: str = field(default_factory=lambda: _env("OWNER_PHONE"))
    app_token: str = field(default_factory=lambda: _env("APP_TOKEN"))
    exotel_secret: str = field(default_factory=lambda: _env("EXOTEL_STREAM_SECRET"))
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "./data")))

    # AI providers. LLM_PROVIDER: gemini | claude | mock
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "gemini"))
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-3.5-flash"))
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-haiku-5-5"))

    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    elevenlabs_voice_id: str = field(default_factory=lambda: _env("ELEVENLABS_VOICE_ID"))
    tts_model: str = field(default_factory=lambda: _env("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"))
    stt_model: str = field(default_factory=lambda: _env("ELEVENLABS_STT_MODEL", "scribe_v1"))

    greeting: str = field(default_factory=lambda: _env(
        "GREETING",
        "Namaste, this is {owner}'s assistant. He can't take the call right now. "
        "This call may be recorded. Who's calling, and what's it about?"))

    def greeting_text(self) -> str:
        return self.greeting.replace("{owner}", self.owner_name)

    def check(self) -> list[str]:
        """Human-readable problems with the settings (shown at /health)."""
        problems = []
        if not self.app_token:
            problems.append("APP_TOKEN is not set: the app cannot log in.")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            problems.append("GEMINI_API_KEY is not set.")
        if self.llm_provider == "claude" and not self.anthropic_api_key:
            problems.append("ANTHROPIC_API_KEY is not set.")
        if not (self.elevenlabs_api_key and self.elevenlabs_voice_id):
            problems.append("ElevenLabs key or voice ID missing: real phone calls need them (the text simulator works without).")
        if not self.exotel_secret:
            problems.append("EXOTEL_STREAM_SECRET is not set: real phone calls are switched off.")
        return problems
