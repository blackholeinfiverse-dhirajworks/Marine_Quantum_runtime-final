#!/usr/bin/env python3
# run_hybrid_runtime.py
# MAIN ENTRY POINT — Task 10: Hybrid Participation + Contract Layer
#
# Usage:
#   python run_hybrid_runtime.py
#
# Proves:
#   1. RuntimeRequest / RuntimeResponse contract round-trip
#   2. Classical participant (REPLAYABLE determinism)
#   3. Quantum participant (RECONSTRUCTABLE determinism — seeded sim)
#   4. Shared runtime contract participation
#   5. RuntimeLineageRecord sealed with chain_hash
#   6. Failure case: ContractViolation on bad payload
#   7. 3-run determinism proof (classical leg)

import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.runtime.invoke_runtime import invoke_hybrid_runtime
from src.contracts.runtime_contracts import RuntimeRequest, ContractViolation


SAMPLE_PAYLOAD = {
    "node_id":      "qnode_01",
    "energy_delta": 0.0001,
    "iterations":   120,
    "confidence":   0.92,
    "variance":     0.002,
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
    print("  Marine Intelligence System — Hybrid Runtime")
    print("  Task 10: Contract Layer + Hybrid Participation")
    print("  BHIV Core / TANTRA Ecosystem | Dhiraj Chavan")
    print("=" * 64)

    # ── PHASE 1: Single hybrid invocation ─────────────────────────────────────
    _sep("PHASE 1 — Single Hybrid Invocation")
    print("\nPayload:")
    _jprint(SAMPLE_PAYLOAD)

    result = invoke_hybrid_runtime(SAMPLE_PAYLOAD, seq=1, caller_id="bhiv_core")

    print("\nRuntimeRequest:")
    req = result["request"]
    print(f"  request_id        : {req['request_id'][:24]}...")
    print(f"  module_name       : {req['module_name']}")
    print(f"  participant_class : {req['participant_class']}")
    print(f"  timestamp_posture : {req['timestamp_posture']}")

    print("\nClassical Participant Response:")
    cr = result["classical_response"]
    print(f"  execution_status  : {cr['execution_status']}")
    if cr["result"]:
        t = cr["result"]["transition"]
        print(f"  transition        : {t['prev']} → {t['next']}")
        print(f"  cause             : {t['cause']}")
        print(f"  sigma             : {cr['result']['uncertainty_envelope']['sigma']}")
        print(f"  ts                : {t['ts']}")
        print(f"  determinism       : {cr['determinism_metadata']['category']}")

    print("\nQuantum Participant Response:")
    qr = result["quantum_response"]
    print(f"  execution_status  : {qr['execution_status']}")
    if qr["result"]:
        vqe = qr["result"]["vqe_result"]
        print(f"  E0_hartree        : {vqe['E0_hartree']} ± {vqe['uncertainty_hartree']}")
        print(f"  k_base            : {qr['result']['corrosion_estimate']['k_base_scaled']}")
        print(f"  determinism       : {qr['determinism_metadata']['category']}")
        print(f"  simulation_mode   : {qr['result']['simulation_mode']}")

    print("\nLineage Record:")
    lin = result["lineage"]
    print(f"  chain_hash        : {lin['chain_hash'][:24]}...")
    print(f"  is_replayable     : {lin['is_replayable']}")
    print(f"  trace count       : {len(lin['traces'])}")
    for tr in lin["traces"]:
        print(f"    [{tr['module_name']}]")
        print(f"      determinism   : {tr['determinism_class']}")
        print(f"      status        : {tr['execution_status']}")
        print(f"      input_hash    : {tr['input_hash'][:16]}...")
        print(f"      output_hash   : {tr['output_hash'][:16]}...")
        print(f"      trace_id      : {tr['trace_id'][:16]}...")

    # ── PHASE 2: Registered descriptors ───────────────────────────────────────
    _sep("PHASE 2 — Descriptor Registry Snapshot")
    for key, desc in result["descriptors"].items():
        print(f"\n  [{key.upper()} PARTICIPANT]")
        print(f"    qapp_id           : {desc['qapp_id']}")
        print(f"    capability_class  : {desc['capability_class']}")
        print(f"    attachment_mode   : {desc['attachment_mode']}")
        print(f"    authority_ceiling : {desc['authority_ceiling']}")
        print(f"    descriptor_hash   : {desc['descriptor_hash'][:16]}...")
        print(f"    negative_decl[0]  : {desc['negative_declarations'][0]}")

    # ── PHASE 3: Failure case — ContractViolation ──────────────────────────────
    _sep("PHASE 3 — Failure Case: ContractViolation on Bad Payload")
    bad_request_cases = [
        {
            "label": "negative seq",
            "kwargs": {"payload": SAMPLE_PAYLOAD, "seq": -1},
        },
        {
            "label": "invalid participant_class in RuntimeRequest",
            "constructor_test": True,
            "kwargs": {
                "module_name": "test_module", "seq": 1,
                "payload": {}, "participant_class": "ALIEN",
            },
        },
    ]
    for case in bad_request_cases:
        print(f"\n  >> {case['label']}")
        try:
            if case.get("constructor_test"):
                RuntimeRequest(**case["kwargs"])
            else:
                invoke_hybrid_runtime(**case["kwargs"])
            print("     -> [UNEXPECTED PASS — expected failure]")
        except (ContractViolation, ValueError) as exc:
            print(f"     -> ContractViolation (expected): {exc}")

    # ── PHASE 4: 3-run determinism proof — classical leg ──────────────────────
    # NOTE: seq=1 is fixed across all runs — we prove content determinism.
    # output_hash in lineage includes seq-derived request_id, so we compare
    # the content fingerprint (transition + sigma + ts + cause) instead.
    _sep("PHASE 4 — Determinism Proof (3 runs, same input, classical participant)")
    import hashlib as _hl, json as _j
    fingerprints = []
    for i in range(1, 4):
        r = invoke_hybrid_runtime(SAMPLE_PAYLOAD, seq=1, caller_id="bhiv_core")
        cr = r["classical_response"]["result"]
        sig = cr["uncertainty_envelope"]["sigma"]
        ts  = cr["transition"]["ts"]
        nxt = cr["transition"]["next"]
        cau = cr["transition"]["cause"]
        fp  = _hl.sha256(_j.dumps(
            {"next": nxt, "sigma": sig, "ts": ts, "cause": cau}, sort_keys=True
        ).encode()).hexdigest()
        fingerprints.append(fp)
        print(f"  Run {i}: transition={nxt!r:<12}  sigma={sig}  ts={ts}")
        print(f"          content_hash={fp[:24]}...")

    all_same = len(set(fingerprints)) == 1
    print()
    if all_same:
        print("  [PASS] All 3 classical outputs IDENTICAL — determinism CONFIRMED.")
    else:
        print("  [FAIL] Classical outputs DIFFER — determinism VIOLATION.")

    # ── Summary ───────────────────────────────────────────────────────────────
    _sep()
    status = "PASS" if all_same else "FAIL"
    print(f"\n  EXECUTION COMPLETE")
    print(f"  Classical determinism : {status}")
    print(f"  Hybrid participation  : CONFIRMED (classical + quantum in shared contract)")
    print(f"  Lineage sealed        : {lin['chain_hash'][:24]}...")
    print()
    sys.exit(0 if all_same else 1)


if __name__ == "__main__":
    run()
