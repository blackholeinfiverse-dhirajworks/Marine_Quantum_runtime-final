# src/quantum/schema.py
import math
class SchemaValidationError(ValueError): pass
CORROSION_INPUT_BOUNDS = {
    "salinity":(0.0,50.0),"temperature_celsius":(-5.0,45.0),"pH":(0.0,14.0),
    "material_oxidation_potential":(-2.0,2.0),"dissolved_oxygen_mgl":(0.0,20.0),
    "current_density_mAcm2":(0.0,10.0),
}
def validate_corrosion_input(payload):
    errors=[]
    for field,(lo,hi) in CORROSION_INPUT_BOUNDS.items():
        if field not in payload: errors.append(f"Missing: '{field}'"); continue
        v=payload[field]
        try: v=float(v)
        except: errors.append(f"Field '{field}' must be numeric"); continue
        if not(lo<=v<=hi): errors.append(f"Field '{field}'={v} out of [{lo},{hi}]")
    if errors: raise SchemaValidationError("Corrosion input validation:\n"+"".join(f"  • {e}\n" for e in errors))
    return {k:float(payload[k]) for k in CORROSION_INPUT_BOUNDS}
def normalize_corrosion_input(validated):
    b=CORROSION_INPUT_BOUNDS
    def n(v,lo,hi): return math.pi*(v-lo)/(hi-lo)
    return {"theta_salinity":n(validated["salinity"],*b["salinity"]),
            "theta_temperature":n(validated["temperature_celsius"],*b["temperature_celsius"]),
            "theta_pH":n(validated["pH"],*b["pH"]),
            "theta_oxidation":n(validated["material_oxidation_potential"],*b["material_oxidation_potential"]),
            "theta_oxygen":n(validated["dissolved_oxygen_mgl"],*b["dissolved_oxygen_mgl"]),
            "theta_current":n(validated["current_density_mAcm2"],*b["current_density_mAcm2"])}
def validate_corrosion_output(r):
    req=["degradation_probability","confidence_score","recommended_anode_current","dominant_state","measurement_distribution","shots_used"]
    for k in req:
        if k not in r: return False
    if not(0<=r["degradation_probability"]<=1): return False
    if not(0<=r["confidence_score"]<=1): return False
    if r["confidence_score"]<0.5: return False
    if r["recommended_anode_current"]<0: return False
    if r["shots_used"]<512: return False
    total=sum(r["measurement_distribution"].values())
    if not(0.99<=total<=1.01): return False
    return bool(r["dominant_state"])
