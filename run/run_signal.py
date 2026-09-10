#!/usr/bin/env python3
# run/run_signal.py
# Signal Generator entry point — Tasks 1–4 proof.
#
# Usage:  python run/run_signal.py
#
# Phases:
#   4 — Single signal execution
#   5 — 4 failure / edge-case inputs
#   6 — 5-run determinism proof

import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.invoke_runtime import invoke_runtime
from src.signal.validator import ValidationError

SAMPLE_INPUT = {
    "node_id": "qnode_01", "energy_delta": 0.0001,
    "iterations": 120,     "confidence": 0.92, "variance": 0.002,
}

FAILURE_INPUTS = [
    {"label": "Low confidence → SUSPENDED",
     "payload": {"node_id": "qnode_02", "energy_delta": 0.0003, "iterations": 80, "confidence": 0.55, "variance": 0.003}},
    {"label": "High energy_delta → DIVERGED",
     "payload": {"node_id": "qnode_03", "energy_delta": 0.05, "iterations": 200, "confidence": 0.88, "variance": 0.001}},
    {"label": "Missing field → ValidationError",
     "payload": {"node_id": "qnode_04", "iterations": 50, "confidence": 0.90, "variance": 0.002}},
    {"label": "confidence out of range → ValidationError",
     "payload": {"node_id": "qnode_05", "energy_delta": 0.0002, "iterations": 60, "confidence": 1.5, "variance": 0.001}},
]


def _sep(title=""):
    line = "-" * 60
    print(f"\n{line}\n  {title}\n{line}" if title else line)


def run():
    print("\n" + "=" * 60)
    print("  Marine Quantum Runtime — Signal Generator")
    print("  BHIV Core Interface | Tasks 1–4")
    print("=" * 60)

    _sep("PHASE 4 — Single Execution")
    print("\nInput:")
    print(json.dumps(SAMPLE_INPUT, indent=2))
    result = invoke_runtime("signal", SAMPLE_INPUT)
    print("\nOutput:")
    print(json.dumps(result["result"], indent=2))
    assert result["status"] == "SUCCESS", f"Phase 4 FAIL: {result['error']}"

    _sep("PHASE 5 — Failure Cases")
    for case in FAILURE_INPUTS:
        print(f"\n  >>  {case['label']}")
        r = invoke_runtime("signal", case["payload"])
        if r["status"] == "SUCCESS":
            t = r["result"]["transition"]
            print(f"     → transition: {t['next']}")
            print(f"     → cause:      {t['cause']}")
        else:
            print(f"     → {r['status']} (expected): {r['error'][:80]}")

    _sep("PHASE 6 — Determinism Proof (5 runs, same input)")
    outputs = []
    for i in range(1, 6):
        r = invoke_runtime("signal", SAMPLE_INPUT)
        outputs.append(json.dumps(r["result"], sort_keys=True))
        t  = r["result"]["transition"]
        ue = r["result"]["uncertainty_envelope"]
        print(f"  Run {i}: transition={t['next']!r:<12}  sigma={ue['sigma']}  ts={t['ts']}")

    all_same = all(o == outputs[0] for o in outputs)
    print()
    if all_same:
        print("  [PASS] All 5 outputs IDENTICAL — determinism CONFIRMED.")
    else:
        print("  [FAIL] DETERMINISM FAILURE — outputs differ!")

    _sep()
    print(f"\n  EXECUTION COMPLETE  |  Determinism: {'PASS ✅' if all_same else 'FAIL ❌'}\n")
    sys.exit(0 if all_same else 1)


if __name__ == "__main__":
    run()
