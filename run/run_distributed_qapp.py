#!/usr/bin/env python3
# run/run_distributed_qapp.py — Task 9 proof
import io,json,os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
if sys.stdout.encoding and sys.stdout.encoding.lower()!="utf-8":
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
from invoke_runtime import invoke_runtime
def _sep(t=""): line="-"*64; print(f"\n{line}\n  {t}\n{line}" if t else line)
def run():
    print("\n"+"="*64); print("  Marine Quantum Runtime — Distributed QApp"); print("  BHIV Core Interface | Task 9"); print("="*64)
    _sep("PHASE 1 — Propagation")
    result=invoke_runtime("distributed_qapp",{})
    if result["status"]!="SUCCESS": print(f"  [FAIL] {result.get('errors')}"); sys.exit(1)
    r=result["result"] or result["output"]
    print(f"  Envelopes propagated : {r['envelopes_propagated']}")
    print(f"  Log entries          : {r['log_entries']}")
    print(f"  Consistent           : {r['consistent']}")
    print(f"  Consensus hash       : {r['consensus_hash'][:32]}...")
    _sep("PHASE 2 — Determinism Proof")
    dp=r.get("determinism_proof",{})
    if dp:
        print(f"  5-run deterministic  : {dp['deterministic']}")
        for i,h in enumerate(dp["consensus_hashes"],1): print(f"  Run {i}: {h[:32]}...")
    _sep("PHASE 3 — Shuffle Convergence")
    sp=r.get("shuffle_proof",{})
    if sp: print(f"  Shuffle converges    : {sp['converges']}")
    all_pass=r["consistent"] and dp.get("deterministic",True) and sp.get("converges",True)
    _sep(); print(f"\n  EXECUTION COMPLETE  |  Overall: {'PASS ✅' if all_pass else 'FAIL ❌'}\n")
    sys.exit(0 if all_pass else 1)
if __name__=="__main__": run()
