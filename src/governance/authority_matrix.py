# src/governance/authority_matrix.py
# Executable Authority Matrix — Marine Intelligence System
# Authority ceilings expressed as enforced validation, not documentation.
#
# check(capability_id, action) -> AuthorityCheckResult
# No silent permits. Every check returns explicit verdict.
# No external dependencies.

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

# ── Authority levels (ordered, lowest → highest) ───────────────────────────────
AUTHORITY_LEVELS = [
    "READ_ONLY",
    "SIGNAL_EMIT",
    "STATE_CLASSIFICATION",
    "QUANTUM_EXECUTION",
    "DISTRIBUTED_PROPAGATION",
    "OBSERVABILITY",
    "RUNTIME_PARTICIPATE",
    "RUNTIME_GOVERN",
]

_LEVEL_RANK: Dict[str, int] = {lvl: i for i, lvl in enumerate(AUTHORITY_LEVELS)}

# ── Action → Minimum Required Authority ───────────────────────────────────────
ACTION_REQUIREMENTS: Dict[str, str] = {
    # Read
    "query_registry":           "READ_ONLY",
    "get_health":               "READ_ONLY",
    "get_dashboard":            "READ_ONLY",
    "list_capabilities":        "READ_ONLY",
    # Execution (a capability simply running its own declared function)
    "execute":                  "READ_ONLY",
    # Signal
    "emit_signal":              "SIGNAL_EMIT",
    "classify_state":           "STATE_CLASSIFICATION",
    # Quantum
    "run_quantum_circuit":      "QUANTUM_EXECUTION",
    "invoke_qapp":              "QUANTUM_EXECUTION",
    # Distributed
    "propagate_event":          "DISTRIBUTED_PROPAGATION",
    "receive_propagation":      "DISTRIBUTED_PROPAGATION",
    # Observability
    "record_invocation":        "OBSERVABILITY",
    "export_metrics":           "OBSERVABILITY",
    "stream_dashboard":         "OBSERVABILITY",
    # Runtime participation — orchestrating OTHER capabilities (not self-execution)
    "register_capability":      "RUNTIME_PARTICIPATE",
    "invoke_other_capability":  "RUNTIME_PARTICIPATE",
    "attach_authority":         "RUNTIME_PARTICIPATE",
    # Governance (highest ceiling)
    "set_execution_policy":     "RUNTIME_GOVERN",
    "override_replay_decision": "RUNTIME_GOVERN",
    "deregister_capability":    "RUNTIME_GOVERN",
    "modify_authority_ceiling": "RUNTIME_GOVERN",
}

# ── Per-capability primary execution action ────────────────────────────────────
# Used by capability_runtime.invoke_capability() to gate "this capability may run"
# distinctly from "this capability may invoke OTHER capabilities".
PRIMARY_EXECUTION_ACTION: Dict[str, str] = {
    "signal":               "classify_state",
    "quantum_pipeline":     "run_quantum_circuit",
    "distributed_qapp":     "propagate_event",
    "operational_monitor":  "record_invocation",
}

# ── Hard negative authority blocks per capability ──────────────────────────────
# These are DENIED regardless of ceiling.
NEGATIVE_AUTHORITY: Dict[str, Set[str]] = {
    "signal": {
        "set_execution_policy",
        "override_replay_decision",
        "deregister_capability",
        "modify_authority_ceiling",
        "propagate_event",
        "invoke_other_capability",
    },
    "quantum_pipeline": {
        "set_execution_policy",
        "override_replay_decision",
        "deregister_capability",
        "modify_authority_ceiling",
        "record_invocation",
    },
    "distributed_qapp": {
        "override_replay_decision",
        "set_execution_policy",
        "modify_authority_ceiling",
    },
    "operational_monitor": {
        "set_execution_policy",
        "override_replay_decision",
        "deregister_capability",
        "propagate_event",
        "invoke_other_capability",
    },
}


@dataclass
class AuthorityCheckResult:
    permitted:      bool
    capability_id:  str
    action:         str
    reason:         str
    ceiling:        str
    required:       str
    blocked_by_neg: bool = False

    def to_dict(self) -> dict:
        return {
            "permitted":      self.permitted,
            "capability_id":  self.capability_id,
            "action":         self.action,
            "reason":         self.reason,
            "ceiling":        self.ceiling,
            "required":       self.required,
            "blocked_by_neg": self.blocked_by_neg,
        }


class AuthorityMatrix:
    """
    Executable authority validation.

    Rules (in priority order):
    1. If action is in capability's negative authority  → DENY (hard block)
    2. If action not in ACTION_REQUIREMENTS             → DENY (unknown action)
    3. If capability ceiling rank < required rank       → DENY
    4. Otherwise                                        → PERMIT
    """

    def __init__(self) -> None:
        self._ceilings:   Dict[str, str]  = {}
        self._audit_log:  List[dict]      = []

    def register_ceiling(self, capability_id: str, ceiling: str) -> None:
        if ceiling not in AUTHORITY_LEVELS:
            raise ValueError(
                f"Invalid authority ceiling '{ceiling}'. Valid: {AUTHORITY_LEVELS}"
            )
        self._ceilings[capability_id] = ceiling

    def check(self, capability_id: str, action: str) -> AuthorityCheckResult:
        ceiling = self._ceilings.get(capability_id, "READ_ONLY")

        # Rule 1: Hard negative block
        neg = NEGATIVE_AUTHORITY.get(capability_id, set())
        if action in neg:
            result = AuthorityCheckResult(
                permitted=False, capability_id=capability_id, action=action,
                reason=f"'{action}' is in negative authority for '{capability_id}'",
                ceiling=ceiling, required="N/A", blocked_by_neg=True,
            )
            self._audit_log.append(result.to_dict())
            return result

        # Rule 2: Unknown action
        if action not in ACTION_REQUIREMENTS:
            result = AuthorityCheckResult(
                permitted=False, capability_id=capability_id, action=action,
                reason=f"'{action}' is not a registered authority action",
                ceiling=ceiling, required="UNKNOWN",
            )
            self._audit_log.append(result.to_dict())
            return result

        required       = ACTION_REQUIREMENTS[action]
        ceiling_rank   = _LEVEL_RANK.get(ceiling, 0)
        required_rank  = _LEVEL_RANK.get(required, 0)

        # Rule 3: Ceiling check
        if ceiling_rank < required_rank:
            result = AuthorityCheckResult(
                permitted=False, capability_id=capability_id, action=action,
                reason=(
                    f"Ceiling '{ceiling}' (rank {ceiling_rank}) < "
                    f"required '{required}' (rank {required_rank})"
                ),
                ceiling=ceiling, required=required,
            )
            self._audit_log.append(result.to_dict())
            return result

        result = AuthorityCheckResult(
            permitted=True, capability_id=capability_id, action=action,
            reason=f"Ceiling '{ceiling}' satisfies required '{required}'",
            ceiling=ceiling, required=required,
        )
        self._audit_log.append(result.to_dict())
        return result

    def get_permitted_actions(self, capability_id: str) -> List[str]:
        return [a for a in ACTION_REQUIREMENTS if self.check(capability_id, a).permitted]

    def get_denied_actions(self, capability_id: str) -> List[str]:
        return [a for a in ACTION_REQUIREMENTS if not self.check(capability_id, a).permitted]

    def audit_log(self) -> List[dict]:
        return list(self._audit_log)

    def matrix_snapshot(self) -> dict:
        return {
            "capabilities": {
                cid: {
                    "ceiling":   ceiling,
                    "permitted": self.get_permitted_actions(cid),
                    "denied":    self.get_denied_actions(cid),
                }
                for cid, ceiling in self._ceilings.items()
            },
            "action_requirements": ACTION_REQUIREMENTS,
            "authority_levels":    AUTHORITY_LEVELS,
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
_MATRIX = AuthorityMatrix()

_BUILTIN_CEILINGS = {
    "signal":               "STATE_CLASSIFICATION",
    "quantum_pipeline":     "QUANTUM_EXECUTION",
    "distributed_qapp":     "DISTRIBUTED_PROPAGATION",
    "operational_monitor":  "OBSERVABILITY",
}
for _cid, _ceil in _BUILTIN_CEILINGS.items():
    _MATRIX.register_ceiling(_cid, _ceil)


def check(capability_id: str, action: str) -> AuthorityCheckResult:
    return _MATRIX.check(capability_id, action)


def check_execution(capability_id: str) -> AuthorityCheckResult:
    """
    Check whether a capability is authorized to execute its own primary function.
    Uses PRIMARY_EXECUTION_ACTION mapping rather than a generic action name.
    This is distinct from check(capability_id, "invoke_other_capability"),
    which governs whether a capability may orchestrate OTHER capabilities.
    """
    action = PRIMARY_EXECUTION_ACTION.get(capability_id, "execute")
    return _MATRIX.check(capability_id, action)


def register_ceiling(capability_id: str, ceiling: str) -> None:
    _MATRIX.register_ceiling(capability_id, ceiling)


def audit_log() -> List[dict]:
    return _MATRIX.audit_log()


def matrix_snapshot() -> dict:
    return _MATRIX.matrix_snapshot()
