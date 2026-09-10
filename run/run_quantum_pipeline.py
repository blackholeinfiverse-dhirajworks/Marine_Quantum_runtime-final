#!/usr/bin/env python3
# run/run_quantum_pipeline.py — Task 8 proof
import io,json,os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
if sys.stdout.encoding and sys.stdout.encoding.lower()!="utf-8":
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
from invoke_runtime import invoke_runtime
SAMPLE_INPUT={"salinity":35.2,"temperature_celsius":18.5,"pH":7.8,"material_oxidation_potential":0.44,"dissolved_oxygen_mgl":6.5,"current_density_mAcm2":0.12}
FAILURE_INPUTS=[
    {"label":"salinity out of range","payload":{**SAMPLE_INPUT,"salinity":999.0}},
    {"label":"negative dissolved oxygen","payload":{**SAMPLE_INPUT,"dissolved_oxygen_mgl":-5.0}},
    {"label":"missing pH","payload":{k:v for k,v in SAMPLE_INPUT.items() if k!="pH"}},
]
def _sep(t=""): line="-"*60; print(f"\n{line}\n  {t}\n{line}" if t else line)
def run():
    print("\n"+"="*60); print("  Marine Quantum Runtime — Quantum Pipeline"); print("  BHIV Core Interface | Task 8"); print("="*60)
    _sep("PHASE 1 — Single Quantum Execution")
    result=invoke_runtime("quantum_pipeline",SAMPLE_INPUT)
    if result["status"]!="SUCCESS": print(f"\n  [FAIL] {result.get('errors')}"); sys.exit(1)
    r=result["result"] or result["output"]
    print(f"\n  degradation_probability : {r['degradation_probability']}")
    print(f"  confidence_score        : {r['confidence_score']}")
    print(f"  risk_level              : {r['deterministic_event']['risk_level']}")
    print(f"  signal                  : {r['deterministic_event']['signal']}")
    _sep("PHASE 2 — Failure Cases")
    for case in FAILURE_INPUTS:
        print(f"\n  >>  {case['label']}")
        fr=invoke_runtime("quantum_pipeline",case["payload"])
        print(f"     → status: {fr['status']}")
        if fr.get("errors"): print(f"     → error:  {str(fr['errors'])[:80]}")
    _sep("PHASE 3 — Determinism Proof (5 runs)")
    outputs=[]
    for i in range(1,6):
        r2=invoke_runtime("quantum_pipeline",SAMPLE_INPUT); out=r2["result"] or r2["output"]
        outputs.append(json.dumps({"deg":out["degradation_probability"],"dom":out["dominant_state"]},sort_keys=True))
        print(f"  Run {i}: degradation={out['degradation_probability']}  dominant={out['dominant_state']}")
    all_same=all(o==outputs[0] for o in outputs)
    print(f"\n  [{'PASS' if all_same else 'FAIL'}] Determinism {'CONFIRMED' if all_same else 'FAILED'}.")
    _sep(); print(f"\n  EXECUTION COMPLETE  |  Determinism: {'PASS ✅' if all_same else 'FAIL ❌'}\n")
    sys.exit(0 if all_same else 1)
if __name__=="__main__": run()
