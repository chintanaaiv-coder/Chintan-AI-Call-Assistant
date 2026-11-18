"""SQLite storage for calls, transcript turns, settings and muted numbers."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  id TEXT PRIMARY KEY,
  started_at REAL NOT NULL,
  ended_at REAL,
  caller_number TEXT,
  source TEXT NOT NULL,            -- phone | simulator
  status TEXT NOT NULL,            -- live | ended
  outcome TEXT,                    -- message_taken | joined | caller_hung_up | muted | snoozed | error
  analysis TEXT NOT NULL DEFAULT '{}',
  recording TEXT
);
CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  call_id TEXT NOT NULL,
  ts REAL NOT NULL,
  speaker TEXT NOT NULL,           -- assistant | caller | owner_message
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS turns_call ON turns(call_id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS muted (number TEXT PRIMARY KEY, added_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS examples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "snoozed_until": 0,            # unix time; 0 = not snoozed
    "standing_instructions": "",
    "category_rules": [],          # [{"category": "...", "text": "..."}]
    "quick_replies": [
        "Please email the notice to my office.",
        "He'll call you back after 6 pm.",
        "Please send the documents on WhatsApp.",
        "Leave the parcel with the watchman.",
    ],
}


def normalise_number(n: str | None) -> str:
    digits = "".join(ch for ch in (n or "") if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    # --- calls ---
    def create_call(self, caller_number: str | None, source: str) -> str:
        call_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self._exec("INSERT INTO calls(id, started_at, caller_number, source, status) VALUES (?,?,?,?, 'live')",
                   (call_id, time.time(), caller_number, source))
        return call_id

    def update_call(self, call_id: str, **fields) -> None:
        if "analysis" in fields:
            fields["analysis"] = json.dumps(fields["analysis"])
        cols = ", ".join(f"{k}=?" for k in fields)
        self._exec(f"UPDATE calls SET {cols} WHERE id=?", (*fields.values(), call_id))

    def add_turn(self, call_id: str, speaker: str, text: str) -> dict:
        ts = time.time()
        self._exec("INSERT INTO turns(call_id, ts, speaker, text) VALUES (?,?,?,?)", (call_id, ts, speaker, text))
        return {"call_id": call_id, "ts": ts, "speaker": speaker, "text": text}

    def _call_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["analysis"] = json.loads(d.get("analysis") or "{}")
        d["has_recording"] = bool(d.pop("recording", None))
        return d

    def get_call(self, call_id: str, with_turns: bool = True) -> dict | None:
        row = self._exec("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not row:
            return None
        d = self._call_dict(row)
        if with_turns:
            d["turns"] = [dict(r) for r in self._exec(
                "SELECT ts, speaker, text FROM turns WHERE call_id=? ORDER BY id", (call_id,)).fetchall()]
        return d

    def recording_path(self, call_id: str) -> str | None:
        row = self._exec("SELECT recording FROM calls WHERE id=?", (call_id,)).fetchone()
        return row["recording"] if row else None

    def list_calls(self, limit: int = 100) -> list[dict]:
        rows = self._exec("SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._call_dict(r) for r in rows]

    def delete_call(self, call_id: str) -> str | None:
        rec = self.recording_path(call_id)
        self._exec("DELETE FROM turns WHERE call_id=?", (call_id,))
        self._exec("DELETE FROM calls WHERE id=?", (call_id,))
        return rec

    # --- settings ---
    def settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        for r in self._exec("SELECT key, value FROM settings").fetchall():
            s[r["key"]] = json.loads(r["value"])
        s["snoozed"] = s["snoozed_until"] > time.time()
        return s

    def set_settings(self, **values) -> dict:
        for k, v in values.items():
            if k in DEFAULT_SETTINGS:
                self._exec("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (k, json.dumps(v)))
        return self.settings()

    # --- muted callers ---
    def mute(self, number: str) -> None:
        self._exec("INSERT OR IGNORE INTO muted(number, added_at) VALUES (?, ?)", (normalise_number(number), time.time()))

    def unmute(self, number: str) -> None:
        self._exec("DELETE FROM muted WHERE number=?", (normalise_number(number),))

    def is_muted(self, number: str | None) -> bool:
        n = normalise_number(number)
        return bool(n) and self._exec("SELECT 1 FROM muted WHERE number=?", (n,)).fetchone() is not None

    def muted_numbers(self) -> list[str]:
        return [r["number"] for r in self._exec("SELECT number FROM muted ORDER BY added_at DESC").fetchall()]

    # --- "how I talk" examples ---
    def add_example(self, title: str, text: str) -> dict:
        now = time.time()
        cur = self._exec("INSERT INTO examples(title, text, created_at) VALUES (?,?,?)", (title, text, now))
        return {"id": cur.lastrowid, "title": title, "text": text, "created_at": now}

    def examples(self) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT * FROM examples ORDER BY created_at DESC").fetchall()]

    def delete_example(self, example_id: int) -> None:
        self._exec("DELETE FROM examples WHERE id=?", (example_id,))
