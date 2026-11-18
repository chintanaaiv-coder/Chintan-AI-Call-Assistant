"""The AI brain: one call to an LLM per conversational turn.

Providers: Gemini (default, the key you already use in the mockup), Claude, or a
rule-based "mock" for tests and offline demos.
"""
from __future__ import annotations

import json
import re

import httpx

from .config import Config
from .rules import TURN_SCHEMA, build_system_prompt, clean_turn


def _transcript_text(turns: list[dict]) -> str:
    names = {"assistant": "YOU (assistant)", "caller": "CALLER", "owner_message": "YOU (relaying owner)"}
    return "\n".join(f"{names.get(t['speaker'], t['speaker'])}: {t['text']}" for t in turns)


def _user_prompt(turns: list[dict], caller_number: str | None) -> str:
    return (f"Caller's number: {caller_number or 'unknown'}\n\nConversation so far:\n"
            f"{_transcript_text(turns)}\n\nReply with the JSON for your next turn.")


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


class Brain:
    def __init__(self, cfg: Config, http: httpx.AsyncClient | None = None):
        self.cfg = cfg
        self.http = http or httpx.AsyncClient(timeout=20)

    async def next_turn(self, turns: list[dict], caller_number: str | None, settings: dict) -> dict:
        system = build_system_prompt(self.cfg.owner_name, settings.get("standing_instructions", ""),
                                     settings.get("category_rules", []))
        user = _user_prompt(turns, caller_number)
        provider = self.cfg.llm_provider
        try:
            if provider == "gemini":
                raw = await self._gemini(system, user)
            elif provider == "claude":
                raw = await self._claude(system, user)
            else:
                raw = mock_turn(turns)
        except Exception as e:  # never leave a caller in silence because of an AI error
            raw = {"say": "Sorry, I didn't catch that. Could you tell me your name and why you're calling?",
                   "end_call": False, "category": "unclear", "category_confidence": 0.0,
                   "one_line_summary": "", "key_details": f"(AI error: {type(e).__name__})",
                   "caller_demeanor": "unclear"}
        return clean_turn(raw)

    async def _gemini(self, system: str, user: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.cfg.gemini_model}:generateContent"
        r = await self.http.post(url, headers={"x-goog-api-key": self.cfg.gemini_api_key}, json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": TURN_SCHEMA,
                                 "temperature": 0.4},
        })
        r.raise_for_status()
        return _parse_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])

    async def _claude(self, system: str, user: str) -> dict:
        fields = ", ".join(TURN_SCHEMA["properties"])
        r = await self.http.post("https://api.anthropic.com/v1/messages", headers={
            "x-api-key": self.cfg.anthropic_api_key, "anthropic-version": "2023-06-01"}, json={
            "model": self.cfg.claude_model, "max_tokens": 600, "temperature": 0.4,
            "system": system + f"\n\nOutput only a JSON object with these keys: {fields}.",
            "messages": [{"role": "user", "content": user}],
        })
        r.raise_for_status()
        return _parse_json("".join(b.get("text", "") for b in r.json()["content"]))


# --- Offline stand-in, used by tests and the demo when no AI key is set ---------
_SCAM = ("otp", "pin", "cvv", "password", "anydesk", "teamviewer", "blocked today", "kyc", "prize", "lottery")
_LOAN = ("loan", "credit card", "dsa", "client list", "client database", "referral", "your clients")
_REG = ("notice", "gst", "income tax", "scrutiny", "roc", "icai", "assessment", "din")


def mock_turn(turns: list[dict]) -> dict:
    said = " ".join(t["text"].lower() for t in turns if t["speaker"] == "caller")
    caller_turns = sum(1 for t in turns if t["speaker"] == "caller")
    if any(w in said for w in _SCAM):
        cat, conf = "spam_scam", 0.9
        say = "I can't share or confirm any codes or account details on a call. I'll let him know you called."
    elif any(w in said for w in ("client database", "client list", "your clients", "referral")):
        cat, conf = "bank", 0.85
        say = "Sorry, client information is confidential and can't be shared. I'll pass on that you called."
    elif any(w in said for w in _REG):
        cat, conf = "regulatory", 0.85
        say = "Thank you. Could you share the notice or reference number so he can verify and respond?"
    elif any(w in said for w in _LOAN):
        cat, conf = "bank", 0.8
        say = "Thanks, I'll let him know about the offer. He'll get back to you if he's interested."
    elif "deliver" in said or "courier" in said or "parcel" in said:
        cat, conf = "delivery", 0.85
        say = "Thanks, I'll let him know. Is there anything you need from him for the delivery?"
    else:
        cat, conf = "unclear", 0.4
        say = "Thanks. Could you tell me your name and what it's regarding?"
    end = caller_turns >= 2
    if end:
        say = "Thanks, I've noted that and he'll get back to you. Have a good day."
    last = next((t["text"] for t in reversed(turns) if t["speaker"] == "caller"), "")
    return {"say": say, "end_call": end, "category": cat, "category_confidence": conf,
            "one_line_summary": last[:120], "key_details": last[:300], "caller_demeanor": "normal",
            "compliance_type": "Tax Audit 44AB" if "44ab" in said or "tax audit" in said else None}
