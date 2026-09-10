#!/usr/bin/env python3
# run/run_quantum_pipeline.py
# Quantum Pipeline entry point — Task 8 proof.
#
# Usage:  python run/run_quantum_pipeline.py

import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.invoke_runtime import invoke_runtime

SAMPLE_INPUT = {
    "salinity": 35.2,
    "temperature_celsius": 18.5,
    "pH": 7.8,
    "material_oxidation_potential": 0.44,
    "dissolved_oxygen_mgl": 6.5,
    "current_density_mAcm2": 0.12,
}

FAILURE_INPUTS = [
    {"label": "salinity out of range",
     "payload": {**SAMPLE_INPUT, "salinity": 999.0}},
    {"label": "negative dissolved oxygen",
     "payload": {**SAMPLE_INPUT, "dissolved_oxygen_mgl": -5.0}},
    {"label": "missing pH",
     "payload": {k: v for k, v in SAMPLE_INPUT.items() if k != "pH"}},
    {"label": "pH out of range",
     "payload": {**SAMPLE_INPUT, "pH": 20.0}},
]


def _sep(title=""):
    line = "-" * 60
    print(f"\n{line}\n  {title}\n{line}" if title else line)


def run():
    print("\n" + "=" * 60)
    print("  Marine Quantum Runtime — Quantum Pipeline")
    print("  BHIV Core Interface | Task 8")
    print("=" * 60)

    _sep("PHASE 1 — Single Quantum Execution")
    print("\nInput:")
    print(json.dumps(SAMPLE_INPUT, indent=2))
    result = invoke_runtime("quantum_pipeline", SAMPLE_INPUT)
    if result["status"] != "SUCCESS":
        print(f"\n  [FAIL] {result['error']}")
        sys.exit(1)
    r = result["result"]
    print("\nOutput:")
    print(f"  degradation_probability  : {r['degradation_probability']}")
    print(f"  confidence_score         : {r['confidence_score']}")
    print(f"  recommended_anode_current: {r['recommended_anode_current']} mA")
    print(f"  dominant_state           : {r['dominant_state']}")
    print(f"  shots_used               : {r['shots_used']}")
    de = r.get("deterministic_event", {})
    print(f"  risk_level               : {de.get('risk_level')}")
    print(f"  action_required          : {de.get('action_required')}")
    print(f"  signal                   : {de.get('signal')}")

    _sep("PHASE 2 — Failure Cases")
    for case in FAILURE_INPUTS:
        print(f"\n  >>  {case['label']}")
        fr = invoke_runtime("quantum_pipeline", case["payload"])
        print(f"     → status: {fr['status']}")
        if fr["error"]:
            print(f"     → error:  {str(fr['error'])[:80]}")

    _sep("PHASE 3 — Determinism Proof (5 runs, same input + same seed)")
    outputs = []
    for i in range(1, 6):
        r2 = invoke_runtime("quantum_pipeline", SAMPLE_INPUT)
        key = json.dumps({
            "degradation_probability": r2["result"]["degradation_probability"],
            "dominant_state": r2["result"]["dominant_state"],
        }, sort_keys=True)
        outputs.append(key)
        print(f"  Run {i}: degradation={r2['result']['degradation_probability']}  "
              f"dominant={r2['result']['dominant_state']}  "
              f"risk={r2['result']['deterministic_event']['risk_level']}")

    all_same = all(o == outputs[0] for o in outputs)
    print()
    print(f"  [{'PASS' if all_same else 'FAIL'}] All 5 outputs IDENTICAL — determinism {'CONFIRMED' if all_same else 'FAILED'}.")

    _sep()
    print(f"\n  EXECUTION COMPLETE  |  Determinism: {'PASS ✅' if all_same else 'FAIL ❌'}\n")
    sys.exit(0 if all_same else 1)


if __name__ == "__main__":
    run()
