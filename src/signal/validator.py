# src/signal/validator.py
REQUIRED_FIELDS = {
    "node_id":      {"type":str,  "check":lambda v:len(v.strip())>0,    "msg":"must be a non-empty string"},
    "energy_delta": {"type":float,"coerce":True,"check":lambda v:v>=0.0,"msg":"must be a float >= 0.0"},
    "iterations":   {"type":int,  "check":lambda v:v>=0,                "msg":"must be an int >= 0"},
    "confidence":   {"type":float,"coerce":True,"check":lambda v:0.0<=v<=1.0,"msg":"must be a float in [0.0, 1.0]"},
    "variance":     {"type":float,"coerce":True,"check":lambda v:v>=0.0,"msg":"must be a float >= 0.0"},
}
class ValidationError(ValueError): pass

def validate_input(payload):
    if not isinstance(payload,dict): raise ValidationError(f"Payload must be a dict, got {type(payload).__name__}.")
    errors=[]; missing=[f for f in REQUIRED_FIELDS if f not in payload]
    if missing: errors.append(f"Missing required field(s): {missing}")
    cleaned={}
    for field,spec in REQUIRED_FIELDS.items():
        if field not in payload: continue
        raw=payload[field]; typ=spec["type"]; coerce=spec.get("coerce",False)
        if coerce and not isinstance(raw,typ):
            try: raw=typ(raw)
            except: errors.append(f"Field '{field}': cannot coerce {type(raw).__name__} to {typ.__name__}."); continue
        if not isinstance(raw,typ): errors.append(f"Field '{field}': expected {typ.__name__}, got {type(raw).__name__}."); continue
        if not spec["check"](raw): errors.append(f"Field '{field}' = {raw!r}: {spec['msg']}."); continue
        cleaned[field]=raw
    if errors:
        bullet="\n  • ".join(errors)
        raise ValidationError(f"Input validation failed ({len(errors)} error(s)):\n  • {bullet}")
    return cleaned

def validate_output(event):
    errors=[]
    for k in ["engine_event_version","node_ref","transition","uncertainty_envelope"]:
        if k not in event: errors.append(f"Output missing top-level key: '{k}'")
    if "transition" in event:
        t=event["transition"]
        for k in ["prev","next","cause","seq","ts"]:
            if k not in t: errors.append(f"transition missing key: '{k}'")
        if "seq" in t and not isinstance(t["seq"],int): errors.append(f"transition.seq must be int, got {type(t['seq']).__name__}")
    if "uncertainty_envelope" in event:
        ue=event["uncertainty_envelope"]
        for k in ["confidence","sigma"]:
            if k not in ue: errors.append(f"uncertainty_envelope missing key: '{k}'")
    if errors:
        bullet="\n  • ".join(errors)
        raise ValidationError(f"Output schema validation failed:\n  • {bullet}")

def validate_contract(event):
    required=["engine_event_version","node_ref","transition","uncertainty_envelope"]
    for k in required:
        if k not in event: return {"status":"FAIL","errors":[f"Missing key: '{k}'"]}
    t=event.get("transition",{})
    for k in ["prev","next","cause","seq","ts"]:
        if k not in t: return {"status":"FAIL","errors":[f"transition missing: '{k}'"]}
    return {"status":"PASS"}
