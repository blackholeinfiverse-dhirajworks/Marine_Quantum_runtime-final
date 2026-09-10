#!/usr/bin/env python3
# run/run_governance.py
# Governance Layer Entry Point
# Proves: Authority Matrix, Decision Ledger, Semantic Registry,
#         Doctrine Registry, Replay Legitimacy, Dependency Graph,
#         Typed Attachment, Conflict Detection, Version Negotiation.
#
# Usage:  python run/run_governance.py
# Exit:   0 on PASS, 1 on FAIL

import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.governance.authority_matrix   import check, matrix_snapshot, audit_log
from src.governance.decision_ledger    import record_decision, summary as ledger_summary
from src.governance.semantic_registry  import get, list_all, check_invariant
from src.governance.doctrine_registry  import evaluate_all, list_doctrines
from src.governance.replay_legitimacy  import CanonicalReplayAuthority
from src.runtime.runtime_capability_registry import (
    validate_attachment, validate_dependency_graph,
    validate_dependency_graph_all, negotiate_version,
    detect_conflicts, hot_attach, hot_detach,
    CapabilityDescriptor,
)
from src.contracts.typed_attachment import validate_typed
from src.monitoring.metrics_export  import (
    export_to_dict, format_as_prometheus, format_as_otel_spans
)
from src.monitoring.otel_adapter    import export, export_health_gauges

W = 64
PASS_COUNT = 0
FAIL_COUNT = 0


def _sep(title: str = "") -> None:
    line = "=" * W
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(f"\n{line}")


def _sub(title: str) -> None:
    print(f"\n  ── {title}")


def _check(label: str, condition: bool) -> None:
    global PASS_COUNT, FAIL_COUNT
    tag = "✅ PASS" if condition else "❌ FAIL"
    print(f"      {tag}  {label}")
    if condition:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1


VALID_PAYLOAD = {
    "node_id": "qnode_01", "energy_delta": 0.0001,
    "iterations": 120, "confidence": 0.92, "variance": 0.002,
}
VALID_EVENT = {
    "engine_event_version": "2.0",
    "node_ref": "qnode_01",
    "transition": {"prev": "ACTIVE", "next": "CONVERGED",
                   "cause": "all criteria met", "seq": 1, "ts": "2026-01-01T02:00:00Z"},
    "uncertainty_envelope": {"confidence": 0.92, "sigma": 0.04472136},
}


def test_authority_matrix() -> None:
    _sep("PHASE 1 — Authority Matrix (Executable)")

    _sub("Permitted actions")
    r1 = check("signal", "classify_state")
    print(f"  signal + classify_state: permitted={r1.permitted}  reason={r1.reason}")
    _check("signal can classify_state", r1.permitted)

    r2 = check("signal", "invoke_other_capability")
    print(f"  signal + invoke_other_capability: permitted={r2.permitted}")
    _check("signal CANNOT invoke_other_capability (negative authority)", not r2.permitted)
    _check("signal blocked_by_neg=True", r2.blocked_by_neg)

    _sub("Ceiling enforcement")
    r3 = check("signal", "set_execution_policy")
    print(f"  signal + set_execution_policy: permitted={r3.permitted}  ceiling=STATE_CLASSIFICATION")
    _check("signal CANNOT set_execution_policy (ceiling too low)", not r3.permitted)

    _sub("Unknown action")
    r4 = check("signal", "fly_to_moon")
    _check("Unknown action returns DENY", not r4.permitted)

    _sub("Matrix snapshot")
    snap = matrix_snapshot()
    print(f"  Capabilities in matrix: {list(snap['capabilities'].keys())}")
    _check("All 4 capabilities in matrix", len(snap["capabilities"]) == 4)

    _sub("Audit log")
    log = audit_log()
    print(f"  Audit log entries: {len(log)}")
    _check("Authority checks recorded in audit log", len(log) > 0)


def test_decision_ledger() -> None:
    _sep("PHASE 2 — Decision Ledger")

    r1 = record_decision("signal", "classify_state", "PERMIT",
                         "CanonicalReplayAuthority", "First execution")
    r2 = record_decision("signal", "invoke_capability", "DENY",
                         "AuthorityMatrix", "Blocked by negative authority")
    r3 = record_decision("quantum_pipeline", "invoke_qapp", "PERMIT",
                         "CanonicalReplayAuthority", "Within ceiling")

    summ = ledger_summary()
    print(f"  Total decisions  : {summ['total_decisions']}")
    print(f"  Permits          : {summ['permits']}")
    print(f"  Denials          : {summ['denials']}")
    print(f"  Ledger hash      : {summ['ledger_hash'][:24]}...")

    _check("3 decisions recorded", summ["total_decisions"] == 3)
    _check("2 permits", summ["permits"] == 2)
    _check("1 denial", summ["denials"] == 1)
    _check("Ledger hash is 64-char SHA-256", len(summ["ledger_hash"]) == 64)
    _check("Decision IDs are deterministic SHA-256", len(r1.decision_id) == 64)


def test_semantic_registry() -> None:
    _sep("PHASE 3 — Semantic Registry")

    all_descriptors = list_all()
    print(f"  Registered semantic descriptors: {[d['capability_id'] for d in all_descriptors]}")
    _check("signal semantic descriptor registered", get("signal") is not None)
    _check("quantum_pipeline semantic descriptor registered",
           get("quantum_pipeline") is not None)

    _sub("Invariant check — valid event")
    result = check_invariant("signal", VALID_EVENT)
    print(f"  Valid event invariants: {result}")
    _check("Valid event passes invariant check", result["valid"])

    _sub("Invariant check — bad confidence")
    bad_event = {**VALID_EVENT,
                 "uncertainty_envelope": {"confidence": 1.5, "sigma": 0.04}}
    result2 = check_invariant("signal", bad_event)
    print(f"  Bad confidence invariants: {result2}")
    _check("Out-of-range confidence fails invariant", not result2["valid"])

    _sub("Known limitations declared")
    sig = get("signal")
    print(f"  signal known_limitations: {len(sig.known_limitations)} declared")
    _check("signal has >= 3 known limitations", len(sig.known_limitations) >= 3)


def test_doctrine_registry() -> None:
    _sep("PHASE 4 — Doctrine Registry")

    doctrines = list_doctrines()
    print(f"  Registered doctrines: {[d['name'] for d in doctrines]}")
    _check("At least 7 doctrines registered", len(doctrines) >= 7)

    _sub("All doctrines pass with correct context")
    ctx_ok = {
        "timestamp_posture":         "DETERMINISTIC",
        "silent_failure":            False,
        "negative_authority":        ["Must not do X"],
        "id_generation":             "SHA256",
        "log_type":                  "append_only",
        "stub_declared":             True,
        "attachment_typed":          True,
        "dependency_graph_enforced": True,
    }
    result = evaluate_all(ctx_ok)
    print(f"  All passed: {result['all_passed']}  violations: {result['violations']}")
    _check("Correct context passes all doctrines", result["all_passed"])

    _sub("Doctrine violations caught")
    ctx_bad = {**ctx_ok, "timestamp_posture": "WALL_CLOCK", "silent_failure": True}
    result2 = evaluate_all(ctx_bad)
    print(f"  Violations detected: {[v['doctrine'] for v in result2['violations']]}")
    _check("WALL_CLOCK timestamp detected as violation", not result2["all_passed"])
    _check("At least 2 violations caught", len(result2["violations"]) >= 2)


def test_replay_legitimacy() -> None:
    _sep("PHASE 5 — Replay Legitimacy (Real Implementation)")

    auth = CanonicalReplayAuthority(allow_re_execution=False)

    _sub("First execution — PERMIT")
    d1 = auth.check("signal", VALID_PAYLOAD)
    print(f"  Decision: {d1['decision']}  invocation_id: {d1['invocation_id'][:24]}...")
    _check("First execution PERMIT", d1["decision"] == "PERMIT")

    _sub("Repeat execution — DENY (after truth recorded)")
    import hashlib, json
    output_hash = hashlib.sha256(
        json.dumps(VALID_EVENT, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    auth.record_truth(d1["invocation_id"], output_hash)
    d2 = auth.check("signal", VALID_PAYLOAD)
    print(f"  Decision: {d2['decision']}  reason: {d2['reason'][:60]}...")
    _check("Repeat execution DENY after truth recorded", d2["decision"] == "DENY")

    _sub("Record truth and replay")
    verdict = auth.replay(d1["invocation_id"], VALID_EVENT)
    print(f"  Replay verdict: {verdict.verdict}  match={verdict.match}")
    _check("Identical replay returns REPLAY_VERIFIED", verdict.verdict == "REPLAY_VERIFIED")

    _sub("Tampered replay — REPLAY_DIVERGED")
    tampered = {**VALID_EVENT,
                "transition": {**VALID_EVENT["transition"], "next": "DIVERGED"}}
    verdict2 = auth.replay(d1["invocation_id"], tampered)
    print(f"  Tampered verdict: {verdict2.verdict}")
    _check("Tampered output returns REPLAY_DIVERGED", verdict2.verdict == "REPLAY_DIVERGED")

    stats = auth.statistics()
    print(f"  Stats: permits={stats['permits_issued']}  denials={stats['denials_issued']}")
    _check("Statistics tracked (1 permit, >=1 denial)",
           stats["permits_issued"] == 1 and stats["denials_issued"] >= 1)


def test_dependency_graph() -> None:
    _sep("PHASE 6 — Dependency Graph Validation")

    _sub("signal — no dependencies")
    r1 = validate_dependency_graph("signal")
    print(f"  signal deps: {r1}")
    _check("signal has no dependencies — valid", r1["valid"])

    _sub("distributed_qapp — depends on signal (registered)")
    r2 = validate_dependency_graph("distributed_qapp")
    print(f"  distributed_qapp deps: valid={r2['valid']}  resolved={r2['resolved']}")
    _check("distributed_qapp dependencies resolved", r2["valid"])

    _sub("All capabilities — graph validation")
    all_r = validate_dependency_graph_all()
    print(f"  All valid: {all_r['all_valid']}")
    _check("All built-in dependencies satisfied", all_r["all_valid"])


def test_typed_attachment() -> None:
    _sep("PHASE 7 — Typed Attachment Validation")

    _sub("Valid signal payload")
    r1 = validate_typed("signal", VALID_PAYLOAD)
    print(f"  Valid: {r1['valid']}  errors: {r1['errors']}")
    _check("Valid payload passes typed validation", r1["valid"])

    _sub("Wrong type — confidence as string")
    bad1 = {**VALID_PAYLOAD, "confidence": "high"}
    r2 = validate_typed("signal", bad1)
    print(f"  String confidence: valid={r2['valid']}  errors={r2['errors']}")
    _check("String confidence caught by typed validation", not r2["valid"])

    _sub("Out of bounds — confidence=1.5")
    bad2 = {**VALID_PAYLOAD, "confidence": 1.5}
    r3 = validate_typed("signal", bad2)
    print(f"  confidence=1.5: valid={r3['valid']}  errors={r3['errors']}")
    _check("confidence=1.5 caught by typed validation", not r3["valid"])

    _sub("Negative energy_delta")
    bad3 = {**VALID_PAYLOAD, "energy_delta": -0.001}
    r4 = validate_typed("signal", bad3)
    print(f"  energy_delta<0: valid={r4['valid']}  errors={r4['errors']}")
    _check("Negative energy_delta caught by typed validation", not r4["valid"])

    _sub("Missing required field")
    bad4 = {k: v for k, v in VALID_PAYLOAD.items() if k != "variance"}
    r5 = validate_typed("signal", bad4)
    print(f"  Missing variance: valid={r5['valid']}  missing={r5['missing']}")
    _check("Missing field caught", not r5["valid"] and "variance" in r5["missing"])


def test_version_negotiation() -> None:
    _sep("PHASE 8 — Capability Version Negotiation")

    r1 = negotiate_version("signal", "4.0.0")
    print(f"  signal 4.0.0 vs 4.0.0: compatible={r1['compatible']}")
    _check("Same major version compatible", r1["compatible"])

    r2 = negotiate_version("signal", "3.0.0")
    print(f"  signal 4.0.0 vs 3.0.0: compatible={r2['compatible']}  reason={r2['reason']}")
    _check("Different major version incompatible", not r2["compatible"])

    r3 = negotiate_version("signal", "4.9.9")
    print(f"  signal 4.0.0 vs 4.9.9: compatible={r3['compatible']}")
    _check("Same major, different minor = compatible", r3["compatible"])


def test_conflict_detection() -> None:
    _sep("PHASE 9 — Conflict Detection")

    result = detect_conflicts()
    print(f"  Status: {result['status']}  conflicts: {result['conflict_count']}")
    for c in result["conflicts"]:
        print(f"    {c['conflict']}")
    _check("Conflict detection runs without error", "status" in result)


def test_hot_attach_detach() -> None:
    _sep("PHASE 10 — Hot Attach / Detach")

    test_cap = CapabilityDescriptor(
        capability_id     = "test_hot_cap",
        owner             = "Test",
        version           = "1.0.0",
        capability_class  = "SIGNAL",
        inputs            = ["x"],
        outputs           = ["y"],
        dependencies      = [],
        authority_ceiling = "SIGNAL_EMIT",
        negative_authority = ["Must not govern"],
    )

    _sub("Hot attach")
    r1 = hot_attach(test_cap)
    print(f"  Attach status: {r1['status']}")
    _check("Hot attach returns ATTACHED", r1["status"] == "ATTACHED")

    _sub("Idempotent re-attach")
    r2 = hot_attach(test_cap)
    print(f"  Re-attach status: {r2['status']}")
    _check("Same descriptor re-attach returns IDEMPOTENT", r2["status"] == "IDEMPOTENT")

    _sub("Hot detach")
    r3 = hot_detach("test_hot_cap")
    print(f"  Detach status: {r3['status']}")
    _check("Hot detach returns DETACHED", r3["status"] == "DETACHED")


def test_metrics_export() -> None:
    _sep("PHASE 11 — Metrics Export + OTel Adapter")

    _sub("Prometheus format")
    mock_metrics = {
        "capability_metrics": {
            "signal": {"total_invocations": 5, "success_count": 5,
                       "failure_count": 0, "avg_latency_ms": 1.2, "max_latency_ms": 2.1},
        }
    }
    prom = format_as_prometheus(mock_metrics)
    print(f"  Prometheus output lines: {len(prom.splitlines())}")
    _check("Prometheus output generated", "marine_runtime_signal_invocations_total 5" in prom)

    _sub("OTel span export")
    mock_records = [{
        "invocation_id": "a" * 64, "capability_id": "signal",
        "status": "SUCCESS", "seq": 1, "duration_ms": 1.2,
        "payload_hash": "b" * 64, "output_hash": "c" * 64,
    }]
    spans = format_as_otel_spans(mock_records)
    print(f"  OTel spans generated: {len(spans)}")
    _check("OTel span name correct", spans[0]["name"] == "invoke.signal")
    _check("OTel status OK", spans[0]["status"] == "STATUS_CODE_OK")

    _sub("Full OTel export")
    full = export(mock_records, mock_metrics["capability_metrics"])
    print(f"  format={full['format']}  spans={len(full['spans'])}  metrics={len(full['metrics'])}")
    _check("OTel export format correct", full["format"] == "otel_compatible_v1")
    _check("OTel export has spans and metrics",
           len(full["spans"]) > 0 and len(full["metrics"]) > 0)


def run() -> None:
    print("\n" + "=" * W)
    print("  Marine Intelligence System — Governance Layer")
    print("  All Missing Components — Executable Proof")
    print("=" * W)

    test_authority_matrix()
    test_decision_ledger()
    test_semantic_registry()
    test_doctrine_registry()
    test_replay_legitimacy()
    test_dependency_graph()
    test_typed_attachment()
    test_version_negotiation()
    test_conflict_detection()
    test_hot_attach_detach()
    test_metrics_export()

    _sep("RESULT")
    total = PASS_COUNT + FAIL_COUNT
    print(f"\n  Checks passed : {PASS_COUNT} / {total}")
    print(f"  Checks failed : {FAIL_COUNT} / {total}")
    print()
    if FAIL_COUNT == 0:
        print("  [PASS] Governance Layer — ALL CHECKS PASSED ✅")
    else:
        print("  [FAIL] Governance Layer — FAILURES DETECTED ❌")
    print()
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    run()
