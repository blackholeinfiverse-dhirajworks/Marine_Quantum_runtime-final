# src/governance/decision_ledger.py
# Decision Ledger — append-only record of all governance decisions.
# No decision logic lives here. Decisions are only recorded here.
# Immutable after write. SHA-256 chained. No external dependencies.

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional

_ANCHOR = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _ts(seq: int) -> str:
    return (_ANCHOR + timedelta(seconds=seq * 60)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DecisionRecord:
    decision_id:    str
    seq:            int
    capability_id:  str
    action:         str
    decision:       str     # PERMIT | DENY
    authority:      str
    reason:         str
    ts:             str

    def to_dict(self) -> dict:
        return {
            "decision_id":   self.decision_id,
            "seq":           self.seq,
            "capability_id": self.capability_id,
            "action":        self.action,
            "decision":      self.decision,
            "authority":     self.authority,
            "reason":        self.reason,
            "ts":            self.ts,
        }


class DecisionLedger:
    """
    Append-only, SHA-256-chained record of all governance decisions.
    No decision logic. Only recording.
    """

    def __init__(self) -> None:
        self._records:     List[DecisionRecord] = []
        self._seq:         int  = 0
        self._ledger_hash: str  = "0" * 64

    def record(
        self,
        capability_id: str,
        action:        str,
        decision:      str,
        authority:     str,
        reason:        str,
    ) -> DecisionRecord:
        if decision not in ("PERMIT", "DENY"):
            raise ValueError(f"Decision must be PERMIT or DENY, got '{decision}'")
        self._seq += 1
        raw = f"{self._ledger_hash}:{capability_id}:{action}:{decision}:{authority}:{self._seq}"
        decision_id = _sha256(raw)
        rec = DecisionRecord(
            decision_id=decision_id, seq=self._seq,
            capability_id=capability_id, action=action,
            decision=decision, authority=authority,
            reason=reason, ts=_ts(self._seq),
        )
        self._records.append(rec)
        self._ledger_hash = _sha256(f"{self._ledger_hash}:{decision_id}")
        return rec

    def get_records(self, capability_id: Optional[str] = None) -> List[dict]:
        recs = self._records if not capability_id else [
            r for r in self._records if r.capability_id == capability_id
        ]
        return [r.to_dict() for r in recs]

    def ledger_hash(self) -> str:
        return self._ledger_hash

    def summary(self) -> dict:
        permits = sum(1 for r in self._records if r.decision == "PERMIT")
        denials = sum(1 for r in self._records if r.decision == "DENY")
        return {
            "total_decisions": len(self._records),
            "permits":         permits,
            "denials":         denials,
            "ledger_hash":     self._ledger_hash,
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
_LEDGER = DecisionLedger()


def record_decision(
    capability_id: str,
    action:        str,
    decision:      str,
    authority:     str,
    reason:        str,
) -> DecisionRecord:
    return _LEDGER.record(capability_id, action, decision, authority, reason)


def get_records(capability_id: Optional[str] = None) -> List[dict]:
    return _LEDGER.get_records(capability_id)


def ledger_hash() -> str:
    return _LEDGER.ledger_hash()


def summary() -> dict:
    return _LEDGER.summary()
