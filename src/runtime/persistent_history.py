# src/runtime/persistent_history.py
# Persistent Runtime History — append-only JSONL file.
# Makes observability claims testable across process restarts.
# Degrades gracefully on write failure — runtime never crashes due to log failure.

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional

_ANCHOR           = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runtime_history.jsonl"
)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _ts(seq: int) -> str:
    return (_ANCHOR + timedelta(seconds=seq * 60)).strftime("%Y-%m-%dT%H:%M:%SZ")


class PersistentHistory:
    """
    Append-only JSON Lines log of all runtime invocations.
    One JSON object per line. Never overwritten, never deleted.
    Survives process restarts. Cross-session queryable.
    """

    def __init__(self, path: str = _DEFAULT_LOG_PATH) -> None:
        self._path = os.path.abspath(path)
        self._seq  = self._load_max_seq()

    def _load_max_seq(self) -> int:
        if not os.path.exists(self._path):
            return 0
        max_seq = 0
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        max_seq = max(max_seq, rec.get("seq", 0))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return max_seq

    def append(self, record: dict) -> dict:
        """Append a record. Returns the stored entry with seq, ts, entry_hash."""
        self._seq += 1
        entry = {
            **record,
            "seq":        self._seq,
            "ts":         _ts(self._seq),
            "entry_hash": _sha256(
                json.dumps({**record, "seq": self._seq}, sort_keys=True, separators=(",", ":"))
            ),
        }
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        except OSError as exc:
            # Log failure must never crash the runtime
            entry["_write_error"] = str(exc)
        return entry

    def read_all(self) -> List[dict]:
        records = []
        if not os.path.exists(self._path):
            return records
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return records

    def read_last(self, n: int) -> List[dict]:
        return self.read_all()[-n:]

    def count(self) -> int:
        return len(self.read_all())

    def log_path(self) -> str:
        return self._path

    def summary(self) -> dict:
        records = self.read_all()
        if not records:
            return {"total_records": 0, "log_path": self._path, "status": "EMPTY"}
        status_counts: dict = {}
        for r in records:
            s = r.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "total_records": len(records),
            "status_counts": status_counts,
            "first_seq":     records[0].get("seq"),
            "last_seq":      records[-1].get("seq"),
            "log_path":      self._path,
            "status":        "OK",
        }

    def clear(self) -> None:
        """Wipe the log file. For testing only."""
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
            self._seq = 0
        except OSError:
            pass


# ── Module-level singleton ─────────────────────────────────────────────────────
_HISTORY = PersistentHistory()


def append(record: dict) -> dict:
    return _HISTORY.append(record)


def read_all() -> List[dict]:
    return _HISTORY.read_all()


def read_last(n: int) -> List[dict]:
    return _HISTORY.read_last(n)


def count() -> int:
    return _HISTORY.count()


def summary() -> dict:
    return _HISTORY.summary()


def log_path() -> str:
    return _HISTORY.log_path()
