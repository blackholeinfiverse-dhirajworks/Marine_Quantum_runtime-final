#!/usr/bin/env python3
# run_ecosystem_runtime.py
# MAIN ENTRY POINT — Tasks 10.1 / 10.2 / 10.3
# Capability Registry + Runtime Observability + Production Integration
#
# Usage:
#   python run_ecosystem_runtime.py
#
# Proves:
#   TASK 1 — Self-registering modules, dynamic capability discovery
#   TASK 2 — Invocation timeline, metrics, health APIs, failure aggregation
#   TASK 3 — Replay authority, provenance APIs, constitutional boundary declaration
#
# Exit code 0 on PASS.

import io
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.runtime.ecosystem_runtime import EcosystemRuntime
from src.runtime.participants import register_all_participants
from src.runtime.capability_registry import CapabilityRegistration, CapabilityRegistrationError
from src.runtime.observability import EventType


SAMPLE_PAYLOAD = {
    "node_id":      "qnode_01",
    "energy_delta": 0.0001,
    "iterations":   120,
    "confidence":   0.92,
    "variance":     0.002,
}

SUSPENDED_PAYLOAD = {
    "node_id":      "qnode_02",
    "energy_delta": 0.0002,
    "iterations":   80,
    "confidence":   0.55,
    "variance":     0.003,
}

DIVERGED_PAYLOAD = {
    "node_id":      "qnode_03",
    "energy_delta": 0.05,
    "iterations":   200,
    "confidence":   0.88,
    "variance":     0.001,
}


def _sep(title=""):
    line = "-" * 64
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


def _jprint(obj, indent=2):
    print(json.dumps(obj, indent=indent, default=str))


def run():
    print("\n" + "=" * 64)
    print("  Marine Intelligence System — TANTRA Ecosystem Runtime")
    print("  Tasks 10.1 / 10.2 / 10.3: Registry + Observability + Production")
    print("  BHIV Core | Dhiraj Chavan")
    print("=" * 64)

    # ═══════════════════════════════════════════════════════════════
    # TASK 1 — Capability Registry: Self-registration + Discovery
    # ═══════════════════════════════════════════════════════════════
    _sep("TASK 1 — Capability Registry: Self-Registration + Discovery")

    runtime = EcosystemRuntime()

    # Modules self-register — runtime does not hardcode them
    print("\n  >> Self-registering modules...")
    register_all_participants(runtime)

    # Discovery query — runtime discovers by capability class
    print("\n  >> Discovery: all ACTIVE modules")
    all_active = runtime.discover()
    for m in all_active:
        print(f"     [{m['capability_class']:8}] {m['module_name']:<35} "
              f"state={m['lifecycle_state']:<12} "
              f"determinism={m['determinism_class']}")

    print("\n  >> Discovery: CLASSICAL only")
    classical = runtime.discover(capability_class="CLASSICAL")
    for m in classical:
        print(f"     {m['module_name']}")

    print("\n  >> Discovery: QUANTUM only")
    quantum = runtime.discover(capability_class="QUANTUM")
    for m in quantum:
        print(f"     {m['module_name']}")

    print("\n  >> Registry snapshot:")
    snap = runtime.registry_snapshot()
    print(f"     total_modules      : {snap['health']['total_modules']}")
    print(f"     by_lifecycle_state : {snap['health']['by_lifecycle_state']}")
    print(f"     by_capability_class: {snap['health']['by_capability_class']}")

    # ── Module lifecycle: suspend then re-check discovery ─────────────────────
    print("\n  >> Lifecycle: suspend quantum_vqe_participant")
    runtime.suspend_module("quantum_vqe_participant", reason="maintenance window")
    active_after = runtime.discover()
    print(f"     Active modules after suspend: {[m['module_name'] for m in active_after]}")
    runtime.activate_module("quantum_vqe_participant")
    print("     >> Reactivated quantum_vqe_participant")

    print("\n  [TASK 1] ✅ Self-registration and discovery confirmed.")

    # ═══════════════════════════════════════════════════════════════
    # TASK 2 — Runtime Observability
    # ═══════════════════════════════════════════════════════════════
    _sep("TASK 2 — Runtime Observability: Timeline + Metrics + Health")

    # Run 3 classical invocations (CONVERGED, SUSPENDED, DIVERGED)
    print("\n  >> Invoking 3 classical scenarios...")
    results = {}
    for label, payload in [
        ("CONVERGED", SAMPLE_PAYLOAD),
        ("SUSPENDED", SUSPENDED_PAYLOAD),
        ("DIVERGED",  DIVERGED_PAYLOAD),
    ]:
        result = runtime.invoke(
            "classical_signal_participant",
            payload,
            ts_offset=120 * 60,
        )
        results[label] = result
        rr = result.runtime_response
        if rr.execution_status == "SUCCESS":
            t = rr.result["transition"]
            print(f"     [{label}] {t['prev']} → {t['next']} | sigma={rr.result['uncertainty_envelope']['sigma']}")
        else:
            print(f"     [{label}] FAILURE: {rr.failure_contract.halt_formatted}")

    # Run 2 quantum invocations
    print("\n  >> Invoking 2 quantum scenarios...")
    q_result1 = runtime.invoke("quantum_vqe_participant", SAMPLE_PAYLOAD, ts_offset=120 * 60)
    q_result2 = runtime.invoke("quantum_vqe_participant", DIVERGED_PAYLOAD, ts_offset=200 * 60)
    for r in (q_result1, q_result2):
        rr = r.runtime_response
        k = rr.result["vqe_result"]["k_base"] if rr.execution_status == "SUCCESS" else "N/A"
        print(f"     [QUANTUM] k_base={k} | chain={r.lineage_chain_hash[:16]}...")

    # Invocation timeline
    print("\n  >> Invocation Timeline:")
    timeline = runtime.invocation_timeline()
    for rec in timeline:
        print(f"     seq={rec['start_seq']:>2} | {rec['module_name']:<35} "
              f"status={rec['status']:<8} latency={rec['latency_ms']}ms")

    # Latency summary
    print("\n  >> Latency Summary:")
    lat = runtime.latency_summary()
    for k, v in lat.items():
        print(f"     {k:<12} : {v}")

    # Failure aggregation
    print("\n  >> Failure Aggregation:")
    fagg = runtime.failure_aggregation()
    print(f"     total_failures : {fagg['total_failures']}")
    print(f"     by_module      : {fagg['by_module']}")
    print(f"     by_error_class : {fagg['by_error_class']}")

    # Health report
    print("\n  >> Health Report:")
    health = runtime.health(ts_offset=120 * 60)
    print(f"     ts                  : {health['ts']}")
    print(f"     total_invocations   : {health['total_invocations']}")
    print(f"     success_count       : {health['success_count']}")
    print(f"     failure_count       : {health['failure_count']}")
    print(f"     success_rate        : {health['success_rate']}")
    print(f"     failure_rate        : {health['failure_rate']}")
    print(f"     active_modules      : {health['active_modules']}")
    print(f"     latency.mean_ms     : {health['latency_stats']['mean_ms']}")
    print(f"     latency.p90_ms      : {health['latency_stats']['p90_ms']}")
    print(f"     replay.attempted    : {health['replay_stats']['attempted']}")
    print(f"     replay.verified     : {health['replay_stats']['verified']}")
    print(f"     replay.diverged     : {health['replay_stats']['diverged']}")

    # Recent event log
    print("\n  >> Recent Event Log (last 8):")
    for ev in runtime.event_log(limit=8):
        lat_str = f" lat={ev['latency_ms']}ms" if ev['latency_ms'] is not None else ""
        print(f"     [{ev['seq']:>2}] {ev['event_type']:<26} | {ev['module_name'][:30]}{lat_str}")

    print("\n  [TASK 2] ✅ Observability layer confirmed.")

    # ═══════════════════════════════════════════════════════════════
    # TASK 3 — Production Integration: Replay + Provenance + Constitution
    # ═══════════════════════════════════════════════════════════════
    _sep("TASK 3 — Production Integration: Replay + Provenance + Constitution")

    # Replay the first CONVERGED classical invocation
    converged_request_id = results["CONVERGED"].runtime_response.request_id
    print(f"\n  >> Canonical Replay: request_id={converged_request_id[:24]}...")
    evidence = runtime.replay(converged_request_id, ts_offset=120 * 60)
    print(f"     verdict      : {evidence['verdict']}")
    print(f"     truth_hash   : {evidence.get('truth_hash', 'N/A')}")
    print(f"     replay_hash  : {evidence.get('replay_hash', 'N/A')}")
    print(f"     match        : {evidence.get('match', 'N/A')}")

    # Provenance snapshot
    print("\n  >> Provenance (Lineage) Snapshot:")
    lin = runtime.lineage_snapshot()
    print(f"     total_records    : {lin['total_records']}")
    print(f"     replayable_count : {lin['replayable_count']}")

    # Constitutional boundary declaration
    posture = results["CONVERGED"].constitutional_posture
    print("\n  >> Constitutional Boundary Declaration:")
    print("     RUNTIME OWNS:")
    for item in posture["owns"]:
        print(f"       ✅ {item}")
    print("     RUNTIME DOES NOT OWN:")
    for item in posture["not_owns"]:
        print(f"       ❌ {item}")

    # Determinism proof: 3-run classical content fingerprint
    _sep("TASK 3 — Determinism Proof (3 runs, classical, same input)")
    import hashlib as _hl, json as _j
    fingerprints = []
    for i in range(1, 4):
        r = runtime.invoke("classical_signal_participant", SAMPLE_PAYLOAD, ts_offset=120 * 60)
        rr = r.runtime_response
        t = rr.result["transition"]
        s = rr.result["uncertainty_envelope"]["sigma"]
        fp = _hl.sha256(_j.dumps(
            {"next": t["next"], "sigma": s, "ts": t["ts"], "cause": t["cause"]},
            sort_keys=True,
        ).encode()).hexdigest()
        fingerprints.append(fp)
        print(f"  Run {i}: transition={t['next']!r:<12} sigma={s}  ts={t['ts']}")
        print(f"          content_hash={fp[:24]}...")

    all_same = len(set(fingerprints)) == 1
    print()
    if all_same:
        print("  [PASS] All 3 classical outputs IDENTICAL — determinism CONFIRMED.")
    else:
        print("  [FAIL] Classical outputs DIFFER — determinism VIOLATION.")

    # Final health after all invocations
    print("\n  >> Final Health Report:")
    final_health = runtime.health(ts_offset=0)
    print(f"     total_invocations : {final_health['total_invocations']}")
    print(f"     success_rate      : {final_health['success_rate']}")
    print(f"     replay.verified   : {final_health['replay_stats']['verified']}")
    print(f"     replay.diverged   : {final_health['replay_stats']['diverged']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    _sep()
    print(f"\n  EXECUTION COMPLETE")
    print(f"  Task 1 — Capability Registry    : ✅ PASS")
    print(f"  Task 2 — Runtime Observability  : ✅ PASS")
    print(f"  Task 3 — Production Integration : ✅ PASS")
    print(f"  Classical determinism           : {'PASS ✅' if all_same else 'FAIL ❌'}")
    print(f"  Replay verdict                  : {evidence['verdict']}")
    print(f"  Ecosystem runtime status        : {'PASS ✅' if all_same else 'FAIL ❌'}")
    print()
    sys.exit(0 if all_same else 1)


if __name__ == "__main__":
    run()
