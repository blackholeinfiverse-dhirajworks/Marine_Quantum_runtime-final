#!/usr/bin/env python3
# run/run_operational_drift.py — Monitoring proof
import io,json,os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
if sys.stdout.encoding and sys.stdout.encoding.lower()!="utf-8":
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
from invoke_runtime import invoke_runtime
SIGNAL_STREAM=[
    {"node_id":"qnode_01","energy_delta":0.0001,"iterations":50,"confidence":0.93,"variance":0.001},
    {"node_id":"qnode_01","energy_delta":0.001,"iterations":150,"confidence":0.72,"variance":0.006},
    {"node_id":"qnode_01","energy_delta":0.005,"iterations":250,"confidence":0.58,"variance":0.012},
    {"node_id":"qnode_01","energy_delta":0.0001,"iterations":380,"confidence":0.92,"variance":0.002},
]
def _sep(t=""): line="-"*60; print(f"\n{line}\n  {t}\n{line}" if t else line)
def run():
    print("\n"+"="*60); print("  Marine Quantum Runtime — Operational Drift Monitor"); print("="*60)
    _sep("PHASE 1 — Full Stream")
    result=invoke_runtime("operational_monitor",{"events":SIGNAL_STREAM})
    if result["status"]!="SUCCESS": print(f"  [FAIL]"); sys.exit(1)
    r=result["result"] or result["output"]
    print(f"  Events ingested : {r['events_ingested']}")
    print(f"  Drift events    : {r['drift_events']}")
    _sep("PHASE 2 — Determinism (5 runs)")
    outputs=[]
    for i in range(1,6):
        r2=invoke_runtime("operational_monitor",{"events":SIGNAL_STREAM}); out=r2["result"] or r2["output"]
        key=json.dumps({"ei":out["events_ingested"],"de":out["drift_events"]},sort_keys=True)
        outputs.append(key); print(f"  Run {i}: ingested={out['events_ingested']}  drift={out['drift_events']}")
    all_same=all(o==outputs[0] for o in outputs)
    print(f"\n  [{'PASS' if all_same else 'FAIL'}] Determinism {'CONFIRMED' if all_same else 'FAILED'}.")
    _sep(); print(f"\n  EXECUTION COMPLETE  |  Determinism: {'PASS ✅' if all_same else 'FAIL ❌'}\n")
    sys.exit(0 if all_same else 1)
if __name__=="__main__": run()
