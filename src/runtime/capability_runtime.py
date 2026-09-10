# src/runtime/capability_runtime.py
# Runtime Capability Platform — Invocation Surface
# UPDATED:
#   - Real CanonicalReplayAuthority wired by default (not stub)
#   - PersistentHistory wired for EvidenceLedger (not in-memory-only stub)
#   - Per-capability SequenceRegistry (not global seq counter)
#   - Typed attachment validation
#   - Dependency graph check before every invocation
#   - Authority matrix check before every invocation
#
# PUBLIC API:
#   invoke_capability(capability_id, payload) -> dict
#   get_active_capabilities() -> list[dict]
#   get_runtime_health() -> dict
#   get_dashboard_json() -> dict
#   attach_replay_authority(authority) -> None
#   attach_evidence_ledger(ledger) -> None

import hashlib
import json
import sys
import os
import time
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.runtime.runtime_capability_registry import (
    discover_capability, list_capabilities, get_registry_summary,
    validate_attachment, validate_dependency_graph, record_invocation_result,
    RegistryError, CapabilityNotFound,
)
from src.runtime.runtime_observability import (
    record_invocation, get_runtime_health, get_execution_history,
    get_capability_metrics, get_runtime_summary, get_runtime_heartbeat,
    InvocationRecord, make_invocation_id, make_payload_hash, make_output_hash,
)
from src.runtime.sequence_registry import SequenceRegistry
from src.runtime.persistent_history import PersistentHistory
from src.governance.replay_legitimacy import CanonicalReplayAuthority
from src.governance.authority_matrix import check as authority_check, check_execution


# ── Per-capability sequence registry ──────────────────────────────────────────
_SEQ_REGISTRY = SequenceRegistry()


def _next_seq(capability_id: str) -> int:
    return _SEQ_REGISTRY.next(capability_id)


# ── Replay Authority (real implementation, not stub) ──────────────────────────
_replay_authority: Any = CanonicalReplayAuthority(allow_re_execution=True)
# allow_re_execution=True for development; set False in production via attach_replay_authority()


def attach_replay_authority(authority: Any) -> None:
    """
    Attach a CanonicalReplayAuthority instance.
    Use CanonicalReplayAuthority(allow_re_execution=False) for production.
    """
    global _replay_authority
    _replay_authority = authority


# ── Evidence Ledger (persistent, not in-memory-only stub) ─────────────────────
_evidence_ledger: Any = PersistentHistory()


def attach_evidence_ledger(ledger: Any) -> None:
    """Attach an alternative evidence ledger (must implement append(record))."""
    global _evidence_ledger
    _evidence_ledger = ledger


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ── Core Invocation ───────────────────────────────────────────────────────────

def invoke_capability(capability_id: str, payload: dict) -> dict:
    """
    Invoke a registered capability through the full capability platform stack.

    Pipeline:
        Capability Discovery
              ↓
        Dependency Graph Validation  ← NEW: ensures dependencies are registered
              ↓
        Authority Matrix Check       ← NEW: enforce ceiling before execution
              ↓
        Typed Attachment Validation  ← UPDATED: checks types + bounds
              ↓
        Replay Authority Check       ← REAL: CanonicalReplayAuthority
              ↓
        Runtime Execution
              ↓
        Evidence Emission            ← PERSISTENT: survives restarts
              ↓
        Observability Recording
              ↓
        Return to Caller
    """
    t0  = time.perf_counter()
    seq = _next_seq(capability_id)

    # 1. Discover capability
    try:
        descriptor = discover_capability(capability_id)
    except CapabilityNotFound as exc:
        return {"status": "CAPABILITY_NOT_FOUND", "capability_id": capability_id,
                "errors": [str(exc)]}

    # 2. Dependency graph validation (NEW)
    dep_check = validate_dependency_graph(capability_id)
    if not dep_check["valid"]:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = (f"DependencyError: capability '{capability_id}' has unregistered dependencies: "
               f"{dep_check['missing_dependencies']}")
        _emit_record(capability_id, seq, payload, None, "DEPENDENCY_ERROR", err, elapsed_ms)
        return {
            "status":           "DEPENDENCY_ERROR",
            "capability_id":    capability_id,
            "invocation_id":    make_invocation_id(capability_id, seq, payload),
            "errors":           [err],
            "dependency_check": dep_check,
        }

    # 3. Authority matrix check (NEW) — checks this capability's right to EXECUTE
    #    itself, not its right to invoke OTHER capabilities (different action).
    auth_result = check_execution(capability_id)
    if not auth_result.permitted:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = f"AuthorityViolation: {auth_result.reason}"
        _emit_record(capability_id, seq, payload, None, "AUTHORITY_DENIED", err, elapsed_ms)
        return {
            "status":        "AUTHORITY_DENIED",
            "capability_id": capability_id,
            "invocation_id": make_invocation_id(capability_id, seq, payload),
            "errors":        [err],
            "authority":     auth_result.to_dict(),
        }

    # 4. Typed attachment validation (UPDATED)
    attachment = validate_attachment(capability_id, payload)
    if not attachment["valid"]:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        missing    = attachment.get("missing", [])
        type_errs  = attachment.get("type_errors", [])
        all_errors = [f"Missing: {missing}"] if missing else []
        all_errors += type_errs
        err = f"AttachmentViolation: {'; '.join(all_errors)}"
        _emit_record(capability_id, seq, payload, None, "VALIDATION_ERROR", err, elapsed_ms)
        return {
            "status":           "VALIDATION_ERROR",
            "capability_id":    capability_id,
            "invocation_id":    make_invocation_id(capability_id, seq, payload),
            "errors":           all_errors,
            "attachment_check": attachment,
        }

    # 5. Replay authority check (REAL implementation)
    replay_decision = _replay_authority.check(capability_id, payload)
    if replay_decision.get("decision") != "PERMIT":
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = f"ReplayAuthority DENY: {replay_decision.get('reason', 'no reason')}"
        _emit_record(capability_id, seq, payload, None, "REPLAY_DENIED", err, elapsed_ms)
        return {
            "status":           "REPLAY_DENIED",
            "capability_id":    capability_id,
            "invocation_id":    make_invocation_id(capability_id, seq, payload),
            "replay_authority": replay_decision,
            "errors":           [err],
        }

    # 6. Execute
    try:
        import invoke_runtime as _ir
        inner_result = _ir.invoke_runtime(capability_id, payload)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = f"ExecutionError: {exc}"
        _emit_record(capability_id, seq, payload, None, "FAILED", err, elapsed_ms)
        record_invocation_result(capability_id, success=False, error=err)
        return {
            "status":        "FAILED",
            "capability_id": capability_id,
            "invocation_id": make_invocation_id(capability_id, seq, payload),
            "errors":        [err],
        }

    elapsed_ms = (time.perf_counter() - t0) * 1000
    succeeded  = inner_result.get("status") == "SUCCESS"
    errors     = inner_result.get("errors", [])
    output     = inner_result.get("result") or inner_result.get("output")

    # 7. Record truth hash in replay authority
    invocation_id = make_invocation_id(capability_id, seq, payload)
    if succeeded and output is not None:
        output_hash = make_output_hash(output)
        if hasattr(_replay_authority, "record_truth"):
            _replay_authority.record_truth(invocation_id, output_hash)

    # 8. Emit persistent evidence
    evidence_record = {
        "invocation_id":      invocation_id,
        "capability_id":      capability_id,
        "capability_version": descriptor.version,
        "owner":              descriptor.owner,
        "seq":                seq,
        "status":             "SUCCESS" if succeeded else "FAILED",
        "deterministic_hash": _sha256(_canonical(output)) if output else "",
        "payload_hash":       make_payload_hash(payload),
        "output_hash":        make_output_hash(output) if output else "",
        "duration_ms":        round(elapsed_ms, 3),
        "errors":             errors,
    }
    _evidence_ledger.append(evidence_record)

    # 9. Observability
    status_str = "SUCCESS" if succeeded else "FAILED"
    _emit_record(capability_id, seq, payload, output, status_str,
                 errors[0] if errors else None, elapsed_ms)
    record_invocation_result(capability_id, success=succeeded,
                             error=errors[0] if errors else None)

    return {
        "status":             status_str,
        "capability_id":      capability_id,
        "invocation_id":      invocation_id,
        "deterministic_hash": _sha256(_canonical(output)) if output else "",
        "duration_ms":        round(elapsed_ms, 3),
        "output":             output,
        "errors":             errors,
        "replay_authority":   replay_decision,
        "provenance_ref":     invocation_id,
        "metrics":            inner_result.get("metrics", {}),
        "dependency_check":   dep_check,
        "authority_check":    auth_result.to_dict(),
    }


def _emit_record(
    capability_id: str, seq: int, payload: dict,
    output: Any, status: str, error: Optional[str], duration_ms: float,
) -> None:
    record = InvocationRecord(
        invocation_id = make_invocation_id(capability_id, seq, payload),
        capability_id = capability_id,
        status        = status,
        seq           = seq,
        duration_ms   = round(duration_ms, 3),
        error         = error,
        payload_hash  = make_payload_hash(payload),
        output_hash   = make_output_hash(output) if output else "",
    )
    record_invocation(record)


# ── Dashboard APIs ────────────────────────────────────────────────────────────

def get_active_capabilities() -> List[dict]:
    caps    = list_capabilities()
    metrics = get_capability_metrics()
    for cap in caps:
        cid = cap["capability_id"]
        cap["health"] = metrics.get(cid, {}).get("health", "IDLE")
    return caps


def get_latency_metrics() -> dict:
    raw = get_capability_metrics()
    return {
        cid: {
            "avg_latency_ms": m.get("avg_latency_ms", 0.0),
            "min_latency_ms": m.get("min_latency_ms", 0.0),
            "max_latency_ms": m.get("max_latency_ms", 0.0),
        }
        for cid, m in raw.items()
    }


def get_capability_availability() -> dict:
    caps    = list_capabilities()
    metrics = get_capability_metrics()
    result  = {}
    for cap in caps:
        cid    = cap["capability_id"]
        health = metrics.get(cid, {}).get("health", "IDLE")
        result[cid] = {
            "availability": "AVAILABLE" if health in ("HEALTHY", "IDLE") else health,
            "version":      cap["version"],
            "owner":        cap["owner"],
        }
    return result


def get_replay_statistics() -> dict:
    if hasattr(_replay_authority, "statistics"):
        stats = _replay_authority.statistics()
        return {**stats, "stub": False}
    return {
        "replay_authority": "CanonicalReplayAuthority",
        "authority_status": "STUB — attach via attach_replay_authority()",
        "permits_issued":   "N/A",
        "denials_issued":   "N/A",
        "stub":             True,
    }


def get_provenance_status() -> dict:
    if hasattr(_evidence_ledger, "summary"):
        summ = _evidence_ledger.summary()
        return {**summ, "stub": False, "persistent": True}
    if hasattr(_evidence_ledger, "count"):
        return {
            "records_buffered": _evidence_ledger.count(),
            "persistent":       False,
            "stub":             True,
        }
    return {"stub": True, "persistent": False}


def get_dependency_graph_status() -> dict:
    from src.runtime.runtime_capability_registry import validate_dependency_graph_all
    return validate_dependency_graph_all()


def get_conflict_status() -> dict:
    from src.runtime.runtime_capability_registry import detect_conflicts
    return detect_conflicts()


def get_dashboard_json() -> dict:
    return {
        "active_capabilities":     get_active_capabilities(),
        "runtime_health":          get_runtime_health(),
        "execution_timeline":      get_execution_history(limit=20),
        "latency_metrics":         get_latency_metrics(),
        "capability_availability": get_capability_availability(),
        "replay_statistics":       get_replay_statistics(),
        "provenance_status":       get_provenance_status(),
        "registry_summary":        get_registry_summary(),
        "runtime_heartbeat":       get_runtime_heartbeat(),
        "dependency_graph":        get_dependency_graph_status(),
        "conflict_detection":      get_conflict_status(),
    }
