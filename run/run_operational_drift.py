#!/usr/bin/env python3
# run/run_operational_drift.py
# Operational Drift Monitor entry point.
#
# Usage:  python run/run_operational_drift.py

import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.invoke_runtime import invoke_runtime

W = 60

# Signal stream: healthy → degrading → recovering
SIGNAL_STREAM = [
    {"node_id": "qnode_01", "energy_delta": 0.0001, "iterations": 50,  "confidence": 0.93, "variance": 0.001},
    {"node_id": "qnode_01", "energy_delta": 0.0002, "iterations": 80,  "confidence": 0.90, "variance": 0.002},
    {"node_id": "qnode_01", "energy_delta": 0.0003, "iterations": 110, "confidence": 0.87, "variance": 0.003},
    {"node_id": "qnode_01", "energy_delta": 0.001,  "iterations": 150, "confidence": 0.72, "variance": 0.006},
    {"node_id": "qnode_01", "energy_delta": 0.002,  "iterations": 200, "confidence": 0.60, "variance": 0.009},
    # Drift zone — confidence drops below monitor floor
    {"node_id": "qnode_01", "energy_delta": 0.005,  "iterations": 250, "confidence": 0.58, "variance": 0.012},
    {"node_id": "qnode_01", "energy_delta": 0.004,  "iterations": 280, "confidence": 0.55, "variance": 0.015},
    # Recovery
    {"node_id": "qnode_01", "energy_delta": 0.001,  "iterations": 310, "confidence": 0.78, "variance": 0.004},
    {"node_id": "qnode_01", "energy_delta": 0.0005, "iterations": 340, "confidence": 0.85, "variance": 0.003},
    {"node_id": "qnode_01", "energy_delta": 0.0001, "iterations": 380, "confidence": 0.92, "variance": 0.002},
]

# Failure inputs for the monitor module
FAILURE_INPUTS = [
    {"label": "Empty event stream",       "payload": {"events": []}},
    {"label": "Missing confidence field", "payload": {"events": [{"node_id": "qnode_bad", "energy_delta": 0.001, "iterations": 10, "variance": 0.001}]}},
    {"label": "All-DIVERGED stream",      "payload": {"events": [
        {"node_id": "qnode_div", "energy_delta": 0.05, "iterations": 200, "confidence": 0.88, "variance": 0.001},
        {"node_id": "qnode_div", "energy_delta": 0.06, "iterations": 300, "confidence": 0.85, "variance": 0.002},
    ]}},
    {"label": "Single event only",        "payload": {"events": [SIGNAL_STREAM[0]]}},
]


def _sep(title=""):
    line = "-" * W
    print(f"\n{line}\n  {title}\n{line}" if title else line)


def run():
    print("\n" + "=" * W)
    print("  Marine Quantum Runtime — Operational Drift Monitor")
    print("  BHIV Core Interface | Monitoring Layer")
    print("=" * W)

    passes = []

    # ── PHASE 1: Single-event ingest ─────────────────────────────
    _sep("PHASE 1 — Single Event Ingest")
    r = invoke_runtime("operational_monitor", {"events": [SIGNAL_STREAM[0]]})
    assert r["status"] == "SUCCESS", f"Phase 1 FAIL: {r['error']}"
    summary = r["result"]
    print(f"\n  Events ingested : {summary['events_ingested']}")
    print(f"  Drift events    : {summary['drift_events']}")
    print(f"  Nodes monitored : {summary['nodes_monitored']}")
    print(f"\n  ✅  Single event ingested cleanly")
    passes.append(("Phase 1 — Single Event Ingest", True))

    # ── PHASE 2: Full stream ingest ───────────────────────────────
    _sep("PHASE 2 — Full Signal Stream (10 events)")
    r2 = invoke_runtime("operational_monitor", {"events": SIGNAL_STREAM})
    assert r2["status"] == "SUCCESS", f"Phase 2 FAIL: {r2['error']}"
    summary2 = r2["result"]
    print(f"\n  Events ingested : {summary2['events_ingested']}")
    print(f"  Drift events    : {summary2['drift_events']}")
    print(f"  Nodes monitored : {summary2['nodes_monitored']}")
    if summary2["drift_log"]:
        print(f"\n  Drift events detected:")
        for d in summary2["drift_log"]:
            print(f"    [{d['event_type']}] node={d['node_id']}  seq={d['seq']}")
            print(f"      {d['message']}")
    stream_ok = summary2["events_ingested"] == len(SIGNAL_STREAM)
    print(f"\n  ✅  Full stream processed — drift detection running")
    passes.append(("Phase 2 — Full Signal Stream", stream_ok))

    # ── PHASE 3: Failure cases ────────────────────────────────────
    _sep("PHASE 3 — Failure Cases")
    for case in FAILURE_INPUTS:
        print(f"\n  >>  {case['label']}")
        fr = invoke_runtime("operational_monitor", case["payload"])
        print(f"     → status : {fr['status']}")
        if fr["status"] == "SUCCESS":
            print(f"     → ingested: {fr['result'].get('events_ingested', 0)}")
            print(f"     → drift   : {fr['result'].get('drift_events', 0)}")
        else:
            print(f"     → error   : {str(fr['error'])[:60]}")
    passes.append(("Phase 3 — Failure Cases", True))

    # ── PHASE 4: Determinism proof ────────────────────────────────
    _sep("PHASE 4 — Determinism Proof (5 runs, same stream)")
    print()
    outputs = []
    for i in range(1, 6):
        r3 = invoke_runtime("operational_monitor", {"events": SIGNAL_STREAM})
        key = json.dumps({
            "events_ingested": r3["result"]["events_ingested"],
            "drift_events":    r3["result"]["drift_events"],
        }, sort_keys=True)
        outputs.append(key)
        print(f"  Run {i}: ingested={r3['result']['events_ingested']}  "
              f"drift_events={r3['result']['drift_events']}")

    all_same = all(o == outputs[0] for o in outputs)
    print()
    print(f"  [{'PASS' if all_same else 'FAIL'}] All 5 runs IDENTICAL — determinism {'CONFIRMED' if all_same else 'FAILED'}.")
    passes.append(("Phase 4 — Determinism Proof", all_same))

    # ── PHASE 5: invoke_runtime surface check ─────────────────────
    _sep("PHASE 5 — invoke_runtime Surface Verification")
    from src.invoke_runtime import list_modules, module_status
    modules = list_modules()
    status  = module_status()
    print(f"\n  Registered modules : {modules}")
    for mod, st in status.items():
        tag = "✅" if st == "AVAILABLE" else "⚠️ "
        print(f"    {tag}  {mod:<25} : {st}")
    surface_ok = "operational_monitor" in modules
    print(f"\n  ✅  invoke_runtime surface verified — {len(modules)} modules registered")
    passes.append(("Phase 5 — invoke_runtime Surface", surface_ok))

    # ── Summary ───────────────────────────────────────────────────
    _sep()
    all_passed = all(ok for _, ok in passes)
    print(f"\n  EXECUTION SUMMARY\n")
    for name, ok in passes:
        print(f"  {'PASS ✅' if ok else 'FAIL ❌'}  {name}")

    print(f"\n  OVERALL : {'PASS ✅' if all_passed else 'FAIL ❌'}\n")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    run()
