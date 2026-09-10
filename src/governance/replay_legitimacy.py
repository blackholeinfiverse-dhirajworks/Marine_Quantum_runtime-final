# src/governance/replay_legitimacy.py
# Canonical Replay Authority — real implementation.
# The runtime CONSUMES this. It does not OWN the decision.
#
# Replaces _CanonicalReplayAuthorityStub in capability_runtime.py.
# Attach via: capability_runtime.attach_replay_authority(CanonicalReplayAuthority())
#
# Policy:
#   PERMIT         — first-time execution of this invocation_id
#   DENY           — previously executed; use replay() to verify
#   REPLAY_VERIFIED — replay output matches recorded truth hash
#   REPLAY_DIVERGED — replay output does not match recorded truth hash

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass
class ReplayVerdict:
    verdict:        str
    invocation_id:  str
    truth_hash:     Optional[str]
    replay_hash:    Optional[str]
    match:          Optional[bool]
    reason:         str

    def to_dict(self) -> dict:
        return {
            "verdict":       self.verdict,
            "invocation_id": self.invocation_id,
            "truth_hash":    self.truth_hash,
            "replay_hash":   self.replay_hash,
            "match":         self.match,
            "reason":        self.reason,
        }


class CanonicalReplayAuthority:
    """
    Real implementation of the Replay Authority.

    The runtime calls check() before every execution.
    This class owns the decision. The runtime only consumes it.

    Attach via: capability_runtime.attach_replay_authority(CanonicalReplayAuthority())
    """

    def __init__(self, allow_re_execution: bool = False) -> None:
        self._seen:             Dict[str, str]  = {}   # invocation_id → truth_hash
        self._decisions:        List[dict]      = []
        self._permits:          int             = 0
        self._denials:          int             = 0
        self._allow_re_execution = allow_re_execution  # test mode only

    def _make_invocation_id(self, capability_id: str, payload: dict) -> str:
        payload_hash  = _sha256(_canonical(payload))
        return _sha256(f"invoke:{capability_id}:ph={payload_hash}")

    def check(self, capability_id: str, payload: dict) -> dict:
        """Called by the runtime before every execution."""
        invocation_id = self._make_invocation_id(capability_id, payload)

        if invocation_id in self._seen and not self._allow_re_execution:
            self._denials += 1
            decision = {
                "authority":      "CanonicalReplayAuthority",
                "decision":       "DENY",
                "reason":         f"Invocation '{invocation_id[:16]}...' already executed. Use replay() to verify.",
                "capability_id":  capability_id,
                "invocation_id":  invocation_id,
            }
        else:
            self._permits += 1
            decision = {
                "authority":      "CanonicalReplayAuthority",
                "decision":       "PERMIT",
                "reason":         "First execution of this invocation_id" if invocation_id not in self._seen
                                  else "Re-execution permitted (allow_re_execution=True)",
                "capability_id":  capability_id,
                "invocation_id":  invocation_id,
            }

        self._decisions.append(decision)
        return decision

    def record_truth(self, invocation_id: str, output_hash: str) -> None:
        """Record the canonical output hash after a successful execution."""
        self._seen[invocation_id] = output_hash

    def replay(self, invocation_id: str, replay_output: dict) -> ReplayVerdict:
        """Verify a replay attempt against the recorded truth hash."""
        if invocation_id not in self._seen:
            return ReplayVerdict(
                verdict="DENY", invocation_id=invocation_id,
                truth_hash=None, replay_hash=None, match=None,
                reason="No truth record for this invocation_id",
            )
        truth_hash  = self._seen[invocation_id]
        replay_hash = _sha256(_canonical(replay_output))
        match       = truth_hash == replay_hash
        return ReplayVerdict(
            verdict="REPLAY_VERIFIED" if match else "REPLAY_DIVERGED",
            invocation_id=invocation_id,
            truth_hash=truth_hash,
            replay_hash=replay_hash,
            match=match,
            reason="Output matches truth" if match else "Output diverges from recorded truth",
        )

    def statistics(self) -> dict:
        return {
            "permits_issued":    self._permits,
            "denials_issued":    self._denials,
            "total_decisions":   self._permits + self._denials,
            "known_invocations": len(self._seen),
            "authority":         "CanonicalReplayAuthority",
            "status":            "LIVE",
        }

    def all_decisions(self) -> List[dict]:
        return list(self._decisions)
