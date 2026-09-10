# src/signal/mapping_logic.py
import math
from typing import Tuple

DIVERGE_ENERGY=0.01; CONVERGE_ENERGY=0.005
CONFIDENCE_SUSPEND=0.70; CONFIDENCE_CONV=0.85
VARIANCE_SUSPEND=0.01; VARIANCE_CONV=0.005; ITER_DIVERGE=500

def _infer_prev_state(payload):
    return "INITIALISING" if payload["iterations"]==0 else "ACTIVE"

def _determine_next_state(payload):
    e,c,v,it = payload["energy_delta"],payload["confidence"],payload["variance"],payload["iterations"]
    if e>DIVERGE_ENERGY: return("DIVERGED",f"energy_delta={e} exceeds diverge threshold {DIVERGE_ENERGY}")
    if it>ITER_DIVERGE:  return("DIVERGED",f"iterations={it} exceeds runaway limit {ITER_DIVERGE}")
    if c<CONFIDENCE_SUSPEND: return("SUSPENDED",f"confidence={c} below suspend floor {CONFIDENCE_SUSPEND}")
    if v>VARIANCE_SUSPEND:   return("SUSPENDED",f"variance={v} exceeds suspend ceiling {VARIANCE_SUSPEND}")
    if c>=CONFIDENCE_CONV and v<=VARIANCE_CONV and e<=CONVERGE_ENERGY:
        return("CONVERGED",f"confidence={c}>={CONFIDENCE_CONV}, variance={v}<={VARIANCE_CONV}, energy_delta={e}<={CONVERGE_ENERGY}")
    return("SUSPENDED","marginal values: criteria not fully met for convergence")

def resolve_transition(payload,seq):
    prev = _infer_prev_state(payload)
    next_state,cause = _determine_next_state(payload)
    sigma = math.sqrt(payload["variance"])
    return {"transition":{"prev":prev,"next":next_state,"cause":cause,"seq":int(seq)},"sigma":sigma}
