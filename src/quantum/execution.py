# src/quantum/execution.py
import math
from src.quantum.schema import validate_corrosion_input,normalize_corrosion_input,validate_corrosion_output
from src.quantum.algorithm import simulate_circuit_classically
_ANODE_BASELINE_MA=10.0; _ANODE_SCALE_MA=200.0
def run_corrosion_qapp(payload,seed=42,shots=4096):
    if shots<512: raise ValueError(f"shots={shots} below minimum 512.")
    validated=validate_corrosion_input(payload); normalized=normalize_corrosion_input(validated)
    sim=simulate_circuit_classically(normalized,seed=seed)
    dist=sim["measurement_distribution"]; dom=sim["dominant_state"]; n=len(dom)
    hamming=sum(p*s.count("1")/n for s,p in dist.items())
    ox_f=normalized["theta_oxidation"]/math.pi; sal_f=normalized["theta_salinity"]/math.pi; oxy_f=normalized["theta_oxygen"]/math.pi
    phys=0.5*ox_f+0.3*sal_f+0.2*oxy_f; deg_p=max(0.0,min(1.0,0.60*hamming+0.40*phys))
    probs=list(dist.values()); entropy=-sum(p*math.log2(p) for p in probs if p>0)
    h_max=math.log2(2**n); conf=max(0.0,min(1.0,(1.0-entropy/h_max) if h_max>0 else 0.0))
    anode=_ANODE_BASELINE_MA+_ANODE_SCALE_MA*deg_p
    return {"degradation_probability":round(deg_p,6),"confidence_score":round(conf,6),
            "recommended_anode_current":round(anode,4),"dominant_state":dom,
            "measurement_distribution":dist,"shots_used":shots,"seed":seed}
def run(payload):
    try:
        raw=run_corrosion_qapp(payload); valid=validate_corrosion_output(raw)
        if not valid: return {"module":"quantum_pipeline","status":"CONTRACT_VIOLATION","result":None,"error":"Output failed contract validation"}
        deg_p=raw["degradation_probability"]
        risk="CRITICAL" if deg_p>=0.7 else "ELEVATED" if deg_p>=0.4 else "MODERATE" if deg_p>=0.2 else "LOW"
        action=risk in("ELEVATED","CRITICAL")
        raw["deterministic_event"]={"risk_level":risk,"action_required":action,"signal":"INCREASE_ANODE_CURRENT" if action else "HOLD","confidence":raw["confidence_score"]}
        return {"module":"quantum_pipeline","status":"SUCCESS","result":raw,"error":None}
    except Exception as exc:
        return {"module":"quantum_pipeline","status":"ERROR","result":None,"error":str(exc)}
