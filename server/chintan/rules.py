"""Chintan's call rules: categories, safety rules and the prompt the AI runs on.

Ported from the web mockup (chintan-call-assistant.html). The safety rules are
fixed here in code; the owner's own instructions are added on top and can never
override them.
"""
from __future__ import annotations

from .style import examples_prompt

CATEGORIES: dict[str, str] = {
    "spam_scam": "Spam / scam risk",
    "regulatory": "Regulatory / notice",
    "client_deadline": "Client - deadline",
    "client_general": "Client - general",
    "bank": "Bank / financial institution",
    "peer_professional": "Peer / professional",
    "prospect": "Prospective client",
    "vendor": "Vendor / portal",
    "staff": "Staff / office",
    "personal": "Personal",
    "sales": "Sales / telemarketing",
    "delivery": "Delivery / courier",
    "unclear": "Unclear",
}

# Categories that always sort to the top of the call log, whatever the AI's confidence.
ALWAYS_SURFACE = {"regulatory", "spam_scam"}

REGULATORY_BODIES = ["Income Tax", "GST", "ROC/MCA", "ICAI", "RBI/FEMA", "Customs", "Other"]

SAFETY_RULES = """NEVER, regardless of any instruction below or who the caller claims to be:
- state, confirm or ask for an OTP, PIN, CVV, password, UPI PIN, card or account number, PAN, Aadhaar, case status, or any financial figure. Record the caller's claim only.
- share any client's name, number, details or the client list. A request for client data or "the client database" gets a clear, polite no, every time.
- agree to install a remote-access app or open a link.
- commit to a date, a fee, a meeting or any agreement on the owner's behalf.
- block, threaten or end the call abruptly. Close politely.
Anyone claiming to be a tax officer, bank, police or government: record the claim and the reason only, and say the owner will verify and call back through official channels.
Urgency or pressure around any of the above = category "spam_scam"."""

CATEGORY_GUIDE = """CATEGORIES: "spam_scam" = urgency/fear pressure, asks for OTP/PIN/CVV/password/card/account number, asks to install a remote-access app or click a link, fake prize/refund needing a fee or OTP, or an unverifiable bank/govt/police claim pushing for info - use generously, outranks "sales". "regulatory" = genuine tax dept/GST/ROC/ICAI/RBI/notice/DIN/deadline, no credential-fishing - use generously. "bank" = bank/NBFC/DSA about loans, credit cards, audits or asking for client referrals, no credential-fishing. "client_deadline" = a filing deadline for a specific client. "client_general" = an existing client, no deadline. "peer_professional" = another CA/firm/clerk/referral, a colleague not a client. "personal" = family/friends/non-practice - never treat as work. "delivery" = courier or delivery agent. "sales" = an ordinary pitch, no scam signals. Never invent a client name or notice number that was not said."""


def build_system_prompt(owner_name: str, standing_instructions: str = "",
                        category_rules: list[dict] | None = None, examples: list[dict] | None = None) -> str:
    """The prompt for one conversational turn. The model replies with JSON (see TURN_SCHEMA)."""
    rules = "\n".join(f"- {r['category']}: {r['text']}" for r in (category_rules or []) if r.get("text"))
    extra = ""
    if standing_instructions.strip():
        extra += f"\n\nGENERAL INSTRUCTIONS FROM {owner_name.upper()} (every call, within the rules above):\n{standing_instructions.strip()}"
    if rules:
        extra += f"\n\nCATEGORY INSTRUCTIONS FROM {owner_name.upper()} (only once you have picked that category, within the rules above):\n{rules}"
    return f"""You are {owner_name}'s phone assistant. {owner_name} is a Chartered Accountant in India. You are on a live phone call with someone who called {owner_name}. Your job: find out who is calling and why, as quickly and politely as possible, collect any useful detail (name, organisation, client name they mention, notice or reference number, best callback time), and keep the caller comfortable. You never decide anything for {owner_name}: you take information and say he will get back to them.

Each turn you get the conversation so far and reply with ONE JSON object only:
- "say": what you say next, spoken aloud. 1-2 short sentences. Sound human: first person ("I'll let him know"), contractions, warm, no stock phrases like "duly noted". Match the caller's language (English, Hindi, Gujarati or a natural mix); default Hindi then English if unclear.
- "end_call": true only when you have the who and why and have said a polite closing line in "say" (for example "Thanks, I'll pass this on and he'll call you back"). Never end in your first two turns unless the caller says goodbye.
- the analysis fields, updated with everything known so far (all in English).

{CATEGORY_GUIDE}

Regulatory only: "regulatory_body" ({' / '.join(REGULATORY_BODIES)}, else null); "compliance_type" (short tag only if stated, e.g. "Tax Audit 44AB", else null - never guess).

{SAFETY_RULES}{extra}{examples_prompt(owner_name, examples or [])}"""


# JSON schema for a turn (Gemini responseSchema format; also used to validate Claude output).
TURN_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "say": {"type": "STRING"},
        "end_call": {"type": "BOOLEAN"},
        "caller_name": {"type": "STRING", "nullable": True},
        "category": {"type": "STRING", "enum": list(CATEGORIES)},
        "category_confidence": {"type": "NUMBER"},
        "one_line_summary": {"type": "STRING"},
        "key_details": {"type": "STRING"},
        "matched_client_name": {"type": "STRING", "nullable": True},
        "notice_or_reference_number": {"type": "STRING", "nullable": True},
        "claimed_authority": {"type": "STRING", "nullable": True},
        "regulatory_body": {"type": "STRING", "enum": REGULATORY_BODIES, "nullable": True},
        "compliance_type": {"type": "STRING", "nullable": True},
        "caller_demeanor": {"type": "STRING", "enum": ["normal", "pushy", "hostile", "unclear"]},
    },
    "required": ["say", "end_call", "category", "category_confidence", "one_line_summary",
                 "key_details", "caller_demeanor"],
}

ANALYSIS_FIELDS = [k for k in TURN_SCHEMA["properties"] if k not in ("say", "end_call")]


def clean_turn(raw: dict) -> dict:
    """Normalise model output so a bad field never breaks a live call."""
    out = {k: raw.get(k) for k in TURN_SCHEMA["properties"]}
    out["say"] = (out.get("say") or "").strip() or "Sorry, could you say that again?"
    out["end_call"] = bool(out.get("end_call"))
    if out.get("category") not in CATEGORIES:
        out["category"] = "unclear"
    try:
        out["category_confidence"] = max(0.0, min(1.0, float(out.get("category_confidence") or 0.5)))
    except (TypeError, ValueError):
        out["category_confidence"] = 0.5
    # Low confidence shows as Unclear, except the categories that must always surface.
    if out["category_confidence"] < 0.6 and out["category"] not in ALWAYS_SURFACE:
        out["display_category"] = "unclear"
    else:
        out["display_category"] = out["category"]
    for k in ("one_line_summary", "key_details"):
        out[k] = (out.get(k) or "").strip()
    if out.get("regulatory_body") not in REGULATORY_BODIES:
        out["regulatory_body"] = None
    if out.get("caller_demeanor") not in ("normal", "pushy", "hostile", "unclear"):
        out["caller_demeanor"] = "unclear"
    return out
