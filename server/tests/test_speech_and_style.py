import array
import asyncio
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from chintan.config import Config
from chintan.main import create_app
from chintan.rules import build_system_prompt
from chintan.speech import Speech, resample
from chintan.style import clean_example, pick_examples, redact

TOKEN = "t"
H = {"Authorization": f"Bearer {TOKEN}"}


# --- redaction: the owner's style, never a client's details -------------------------

@pytest.mark.parametrize("raw,leak", [
    ("His PAN is ABCPK1234D", "ABCPK1234D"),
    ("Aadhaar 1234 5678 9012", "9012"),
    ("call me on +91 98765 43210", "43210"),
    ("account 50100234567890", "50100234567890"),
    ("fees Rs. 25,000 this year", "25,000"),
    ("turnover 3.5 crore", "3.5"),
    ("mail ca.office@gmail.com", "gmail"),
    ("GSTIN 27ABCPK1234D1Z5", "27ABCPK"),
])
def test_redact_removes_identifiers(raw, leak):
    assert leak not in redact(raw)


def test_redact_keeps_the_way_he_talks():
    text = "Haan ji, bilkul. Aap notice email kar dijiye, main dekh ke call karta hoon."
    assert redact(text) == text


def test_examples_are_trimmed_and_picked_by_topic():
    assert len(clean_example("a" * 5000)) == 1500
    ex = [
        {"title": "Loan RM", "text": "Bank loan offer, not interested", "created_at": 1},
        {"title": "GST officer", "text": "GST notice DIN please email", "created_at": 2},
        {"title": "Family", "text": "beta khana kha liya", "created_at": 3},
    ]
    assert pick_examples(ex, "Calling from GST department about your notice", k=1)[0]["title"] == "GST officer"


def test_examples_go_after_the_safety_rules():
    p = build_system_prompt("Chintan", examples=[{"title": "x", "text": "Haan ji bilkul", "created_at": 1}])
    assert p.index("NEVER") < p.index("HOW CHINTAN TALKS") < p.index("Haan ji bilkul")
    assert "STYLE ONLY" in p


# --- API -------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Config(app_token=TOKEN, llm_provider="mock", data_dir=tmp_path))) as c:
        yield c


def test_examples_api(client):
    r = client.post("/api/examples", json={"title": "", "text": "Haan ji, PAN ABCPK1234D wala client. "
                                                               "Aap documents WhatsApp kar dijiye, main dekh leta hoon."}, headers=H)
    assert r.status_code == 200 and "ABCPK1234D" not in r.json()["text"]
    assert client.post("/api/examples", json={"text": "too short"}, headers=H).status_code == 400
    ex = client.get("/api/examples", headers=H).json()["examples"]
    assert len(ex) == 1
    client.delete(f"/api/examples/{ex[0]['id']}", headers=H)
    assert client.get("/api/examples", headers=H).json()["examples"] == []


# --- Gemini speech, against a fake Gemini ------------------------------------------------

def test_resample_24k_to_8k():
    pcm = array.array("h", [3000] * 2400).tobytes()  # 0.1 s at 24 kHz
    out = resample(pcm, 24000)
    assert len(out) == 800 * 2 and array.array("h", out)[10] == 3000


def test_gemini_speak_and_transcribe():
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append((request.url.path, body))
        if "tts" in request.url.path:
            pcm = array.array("h", [100] * 2400).tobytes()
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {
                "mimeType": "audio/l16; rate=24000; channels=1", "data": base64.b64encode(pcm).decode()}}]}}]})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": " Haan ji, GST notice ke baare mein "}]}}]})

    cfg = Config(gemini_api_key="k")
    sp = Speech(cfg, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    audio = asyncio.run(sp.speak("Thanks, I'll let him know."))
    text = asyncio.run(sp.transcribe(b"\x00\x00" * 8000))
    assert len(audio) == 800 * 2
    assert text == "Haan ji, GST notice ke baare mein"
    tts_path, tts_body = seen[0]
    assert tts_path.endswith("gemini-3.1-flash-tts-preview:generateContent")
    assert tts_body["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert tts_body["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Charon"
    stt_body = seen[1][1]
    assert stt_body["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "audio/wav"
