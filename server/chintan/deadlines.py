"""Statutory deadline calendar, ported from the mockup.

Dates are computed in code, never left to the AI to recall. The AI only extracts
`compliance_type` from what the caller said; this works out what is next.
"""
from __future__ import annotations

from datetime import date

CALENDAR = [
    {"keywords": ["44ab", "tax audit"], "label": "Tax Audit (Sec 44AB)", "type": "annual", "dates": [(9, 30)]},
    {"keywords": ["audit itr", "itr audit case", "audit case itr"], "label": "ITR - audit cases", "type": "annual", "dates": [(10, 31)]},
    {"keywords": ["itr", "income tax return"], "label": "ITR - non-audit cases", "type": "annual", "dates": [(7, 31)]},
    {"keywords": ["advance tax"], "label": "Advance Tax installment", "type": "quarterly", "dates": [(6, 15), (9, 15), (12, 15), (3, 15)]},
    {"keywords": ["gstr-3b", "gstr 3b", "3b"], "label": "GSTR-3B", "type": "monthly", "day": 20},
    {"keywords": ["gstr-1", "gstr 1"], "label": "GSTR-1", "type": "monthly", "day": 11},
    {"keywords": ["gstr-9", "gstr 9", "annual return"], "label": "GSTR-9 Annual Return", "type": "annual", "dates": [(12, 31)]},
    {"keywords": ["tds return", "24q", "26q"], "label": "TDS Return", "type": "quarterly", "dates": [(7, 31), (10, 31), (1, 31), (5, 31)]},
    {"keywords": ["aoc-4", "aoc4", "mgt-7", "mgt7", "roc filing", "company annual filing"], "label": "ROC Annual Filing", "type": "annual", "dates": [(10, 29)], "approximate": True},
]


def _next_occurrence(entry: dict, today: date) -> date | None:
    candidates: list[date] = []
    if entry["type"] == "monthly":
        for offset in (0, 1):
            m = today.month + offset
            y = today.year + (m - 1) // 12
            m = (m - 1) % 12 + 1
            candidates.append(date(y, m, entry["day"]))
    else:
        for m, d in entry["dates"]:
            candidates += [date(today.year, m, d), date(today.year + 1, m, d)]
    future = sorted(c for c in candidates if c >= today)
    return future[0] if future else None


def deadline_info(compliance_type: str | None, today: date | None = None) -> dict:
    empty = {"days_to_deadline": None, "deadline_flag": None, "deadline_label": None, "deadline_date": None}
    if not compliance_type:
        return empty
    text = compliance_type.lower()
    entry = next((e for e in CALENDAR if any(k in text for k in e["keywords"])), None)
    if not entry:
        return empty
    today = today or date.today()
    nxt = _next_occurrence(entry, today)
    label = entry["label"] + (" (approximate, varies by AGM date)" if entry.get("approximate") else "")
    if not nxt:
        return {**empty, "deadline_label": label}
    days = (nxt - today).days
    flag = "urgent" if days <= 3 else "approaching" if days <= 15 else "normal"
    return {"days_to_deadline": days, "deadline_flag": flag, "deadline_label": label,
            "deadline_date": nxt.isoformat()}
