#!/usr/bin/env python3
# run/run_capability_platform.py
# Phase 6 — Integration Demonstration
# Marine Intelligence System | Runtime Capability Platform
#
# Demonstrates the full runtime flow:
#
#   Capability Request
#         ↓
#   Capability Registry (discover + validate attachment)
#         ↓
#   Replay Authority (consume, never decide)
#         ↓
#   Runtime Execution
#         ↓
#   Execution Evidence (emitted to provenance layer)
#         ↓
#   Observability (timeline + metrics + health)
#         ↓
#   Dashboard JSON
#         ↓
#   Caller
#
# Usage:  python run/run_capability_platform.py
# Exit:   0 on PASS, 1 on FAIL

import io, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.runtime.capability_runtime import (
    invoke_capability,
    get_active_capabilities,
    get_dashboard_json,
    get_capability_availability,
    get_latency_metrics,
    get_replay_statistics,
    get_provenance_status,
)
from src.runtime.runtime_capability_registry import (
    list_capabilities,
    get_capability_health,
    get_registry_summary,
    validate_attachment,
)
from src.runtime.runtime_observability import (
    get_runtime_health,
    get_execution_history,
    get_capability_metrics,
    get_runtime_summary,
    get_runtime_heartbeat,
)


def _sep(title: str = "") -> None:
    line = "=" * 68
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(f"\n{line}")


def _sub(title: str) -> None:
    print(f"\n  ── {title} {'─' * (60 - len(title))}")


def _json(obj: dict, indent: int = 4) -> str:
    return json.dumps(obj, indent=indent, default=str)


PASS_COUNT = 0
FAIL_COUNT = 0


def _check(label: str, condition: bool) -> None:
    global PASS_COUNT, FAIL_COUNT
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"      {status}  {label}")
    if condition:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1


# ── Phase 1: Registry Discovery ───────────────────────────────────────────────

def demo_registry() -> None:
    _sep("PHASE 1 — Capability Registry")

    caps = list_capabilities()
    print(f"\n  Registered capabilities: {len(caps)}")
    for cap in caps:
        print(f"\n  ┌── {cap['capability_id']} ──────────────────────────────────────")
        print(f"  │  owner    : {cap['owner']}")
        print(f"  │  version  : {cap['version']}")
        print(f"  │  class    : {cap['capability_class']}")
        print(f"  │  inputs   : {cap['inputs']}")
        print(f"  │  ceiling  : {cap['authority_ceiling']}")
        print(f"  │  neg_auth : {cap['negative_authority'][0]}")
        print(f"  │  desc_id  : {cap['descriptor_id'][:32]}...")
        print(f"  └──────────────────────────────────────────────────────────────")

    _sub("Attachment Validation")
    valid_payload = {
        "node_id": "qnode_01", "energy_delta": 0.0001,
        "iterations": 120, "confidence": 0.92, "variance": 0.002
    }
    result = validate_attachment("signal", valid_payload)
    print(f"\n  Attachment check (signal + valid payload):  valid={result['valid']}")
    _check("signal attachment valid", result["valid"])

    incomplete = {"node_id": "qnode_01"}
    result2 = validate_attachment("signal", incomplete)
    print(f"\n  Attachment check (signal + incomplete payload): valid={result2['valid']}, missing={result2['missing']}")
    _check("incomplete attachment correctly rejected", not result2["valid"])


# ── Phase 2: Observability APIs ───────────────────────────────────────────────

def demo_observability_apis() -> None:
    _sep("PHASE 2 — Observability APIs (pre-invocation state)")
    heartbeat = get_runtime_heartbeat()
    print(f"\n  Heartbeat: {_json(heartbeat)}")
    _check("runtime is ALIVE", heartbeat["heartbeat"] == "ALIVE")


# ── Phase 3: Full Invocation Flow ─────────────────────────────────────────────

def demo_invocation_flow() -> None:
    _sep("PHASE 3 — Full Invocation Flow")

    # Signal
    _sub("signal capability")
    signal_payload = {
        "node_id": "qnode_01", "energy_delta": 0.0001,
        "iterations": 120, "confidence": 0.92, "variance": 0.002
    }
    result = invoke_capability("signal", signal_payload)
    print(f"\n  status          : {result['status']}")
    print(f"  invocation_id   : {result['invocation_id'][:32]}...")
    print(f"  deterministic_hash: {result['deterministic_hash'][:32]}...")
    print(f"  replay_authority: {result['replay_authority']['decision']}")
    print(f"  provenance_ref  : {result['provenance_ref'][:32]}...")
    if result.get("output"):
        t = result["output"].get("transition", {})
        print(f"  transition      : {t.get('next')}  cause={t.get('cause')[:50]}...")
    _check("signal invocation SUCCESS", result["status"] == "SUCCESS")
    _check("signal invocation_id is deterministic (SHA-256 length)", len(result.get("invocation_id","")) == 64)
    _check("replay authority consulted", result.get("replay_authority", {}).get("decision") == "PERMIT")

    # Distributed QApp
    _sub("distributed_qapp capability")
    dist_payload = {
        "qapp_id":          "hull-corrosion-qapp-01",
        "node_origin":      "Node_A",
        "sequence_id":      1,
        "contract_version": "qapp-v1.0",
        "data": {
            "node_id": "qnode_01", "energy_delta": 0.0001,
            "iterations": 120, "confidence": 0.92, "variance": 0.002
        }
    }
    result2 = invoke_capability("distributed_qapp", dist_payload)
    print(f"\n  status        : {result2['status']}")
    if result2.get("output"):
        print(f"  consistent    : {result2['output'].get('consistent')}")
        print(f"  consensus_hash: {result2['output'].get('consensus_hash','')[:32]}...")
    _check("distributed_qapp invocation SUCCESS", result2["status"] == "SUCCESS")

    # Invalid attachment
    _sub("attachment violation")
    bad_payload = {"node_id": "qnode_bad"}
    result3 = invoke_capability("signal", bad_payload)
    print(f"\n  status  : {result3['status']}")
    print(f"  missing : {result3.get('attachment_check', {}).get('missing')}")
    _check("attachment violation caught before execution", result3["status"] == "VALIDATION_ERROR")

    # Unknown capability
    _sub("unknown capability")
    result4 = invoke_capability("unknown_capability", {})
    print(f"\n  status : {result4['status']}")
    _check("unknown capability returns CAPABILITY_NOT_FOUND", result4["status"] == "CAPABILITY_NOT_FOUND")


# ── Phase 4: Determinism Proof ────────────────────────────────────────────────

def demo_determinism() -> None:
    _sep("PHASE 4 — Determinism Proof (5× same input)")

    payload = {
        "node_id": "qnode_01", "energy_delta": 0.0001,
        "iterations": 120, "confidence": 0.92, "variance": 0.002
    }
    hashes = []
    inv_ids = []
    for i in range(1, 6):
        r = invoke_capability("signal", payload)
        hashes.append(r.get("deterministic_hash", ""))
        inv_ids.append(r.get("invocation_id", ""))
        print(f"  Run {i}: hash={r.get('deterministic_hash','')[:32]}...  invocation_id={r.get('invocation_id','')[:32]}...")

    all_hashes_same = len(set(hashes)) == 1
    all_ids_same    = len(set(inv_ids)) == 1
    print()
    _check("all 5 deterministic_hashes identical", all_hashes_same)
    _check("all 5 invocation_ids identical (same input = same ID)", all_ids_same)


# ── Phase 5: Observability Post-Invocation ────────────────────────────────────

def demo_observability_post() -> None:
    _sep("PHASE 5 — Observability (post-invocation)")

    _sub("runtime_health")
    health = get_runtime_health()
    print(f"\n  overall_health      : {health['overall_health']}")
    print(f"  total_invocations   : {health['total_invocations']}")
    print(f"  capability_health   : {health['capability_health']}")
    _check("runtime health is operational (HEALTHY or DEGRADED)", health["overall_health"] in ("HEALTHY", "DEGRADED"))

    _sub("capability_metrics")
    metrics = get_capability_metrics()
    for cid, m in metrics.items():
        print(f"\n  {cid}:")
        print(f"    total={m['total_invocations']}  success={m['success_count']}  "
              f"avg_ms={m['avg_latency_ms']}  health={m['health']}")
    _check("signal metrics recorded", "signal" in metrics)

    _sub("execution_history (last 5)")
    hist = get_execution_history(limit=5)
    print(f"\n  total_records : {hist['total_records']}")
    for rec in hist["timeline"]:
        print(f"  seq={rec['seq']}  cap={rec['capability_id']}  "
              f"status={rec['status']}  ms={rec['duration_ms']}")
    _check("execution history non-empty", hist["total_records"] > 0)

    _sub("provenance status")
    prov = get_provenance_status()
    print(f"\n  {_json(prov)}")
    _check("evidence records emitted", prov["records_buffered"] > 0)


# ── Phase 6: Dashboard JSON ───────────────────────────────────────────────────

def demo_dashboard() -> None:
    _sep("PHASE 6 — Dashboard JSON Output")

    dashboard = get_dashboard_json()

    _sub("active_capabilities")
    for cap in dashboard["active_capabilities"]:
        print(f"  {cap['capability_id']:<22}  v{cap['version']}  "
              f"class={cap['capability_class']}  health={cap.get('health','?')}")

    _sub("capability_availability")
    for cid, av in dashboard["capability_availability"].items():
        print(f"  {cid:<22}  {av['availability']:<12}  owner={av['owner']}")

    _sub("latency_metrics")
    for cid, lm in dashboard["latency_metrics"].items():
        print(f"  {cid:<22}  avg={lm['avg_latency_ms']:.2f}ms  "
              f"min={lm['min_latency_ms']:.2f}ms  max={lm['max_latency_ms']:.2f}ms")

    _sub("replay_statistics")
    print(f"\n  {_json(dashboard['replay_statistics'])}")

    _sub("provenance_status")
    print(f"\n  {_json(dashboard['provenance_status'])}")

    _sub("runtime_heartbeat")
    hb = dashboard["runtime_heartbeat"]
    print(f"\n  heartbeat={hb['heartbeat']}  health={hb['overall_health']}  "
          f"total_invocations={hb['total_invocations']}  session_seq={hb['session_seq']}")

    _check("dashboard JSON produced", bool(dashboard))
    _check("active_capabilities present", len(dashboard["active_capabilities"]) == 4)
    _check("runtime_health in dashboard", "overall_health" in dashboard["runtime_health"])
    _check("latency_metrics in dashboard", bool(dashboard["latency_metrics"]))


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("\n" + "=" * 68)
    print("  Marine Intelligence System — Runtime Capability Platform")
    print("  Phase IV Production Transition Demonstration")
    print("=" * 68)

    demo_registry()
    demo_observability_apis()
    demo_invocation_flow()
    demo_determinism()
    demo_observability_post()
    demo_dashboard()

    _sep("RESULT")
    total = PASS_COUNT + FAIL_COUNT
    print(f"\n  Checks passed : {PASS_COUNT} / {total}")
    print(f"  Checks failed : {FAIL_COUNT} / {total}")
    print()
    if FAIL_COUNT == 0:
        print("  [PASS] Runtime Capability Platform — ALL CHECKS PASSED ✅")
    else:
        print("  [FAIL] Runtime Capability Platform — FAILURES DETECTED ❌")
    print()
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    run()
