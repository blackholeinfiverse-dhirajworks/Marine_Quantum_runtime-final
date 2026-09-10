# invoke_runtime.py — Root-level unified invocation gateway
import hashlib, json, time, os, sys
from datetime import datetime, timezone, timedelta

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

_SUPPORTED = {"signal","quantum_pipeline","distributed_qapp","operational_monitor"}

def _sha256(d): return hashlib.sha256(d.encode()).hexdigest()
def _canonical(o): return json.dumps(o,sort_keys=True,separators=(",",":"))
def _exec_id(m,p): return _sha256(f"exec:{m}:{_canonical(p)}")
def _det_hash(r): return _sha256(_canonical(r))

def _success(m,p,out,metrics,ms):
    return {"status":"SUCCESS","module":m,"execution_id":_exec_id(m,p),
            "deterministic_hash":_det_hash(out),"duration_ms":round(ms,3),
            "metrics":metrics,"payload":p,"output":out,"result":out,"errors":[]}

def _failure(m,p,errors,ms):
    return {"status":"FAILED","module":m,"execution_id":_exec_id(m,p),
            "deterministic_hash":"","duration_ms":round(ms,3),
            "metrics":{},"payload":p,"output":None,"result":None,"errors":errors}

def invoke_runtime(module_name, payload):
    t0 = time.perf_counter()
    if module_name not in _SUPPORTED:
        ms = (time.perf_counter()-t0)*1000
        return _failure(module_name,payload,[f"UnknownModule: '{module_name}'. Supported: {sorted(_SUPPORTED)}"],ms)
    try:
        if module_name == "signal":
            from src.signal.signal_generator import run; inner=run(payload)
            if inner["status"]=="SUCCESS":
                out=inner["result"]; ms=(time.perf_counter()-t0)*1000
                t=out["transition"]; ue=out["uncertainty_envelope"]
                return _success(module_name,payload,out,{"transition":t["next"],"sigma":ue["sigma"]},ms)
            ms=(time.perf_counter()-t0)*1000
            return _failure(module_name,payload,[inner["error"]],ms)
        elif module_name == "quantum_pipeline":
            from src.quantum.execution import run; inner=run(payload)
            if inner["status"]=="SUCCESS":
                out=inner["result"]; ms=(time.perf_counter()-t0)*1000
                return _success(module_name,payload,out,{"risk":out.get("deterministic_event",{}).get("risk_level")},ms)
            ms=(time.perf_counter()-t0)*1000
            return _failure(module_name,payload,[inner.get("error","unknown")],ms)
        elif module_name == "distributed_qapp":
            from src.runtime.distributed_qapp_runner import run; inner=run(payload)
            if inner["status"]=="SUCCESS":
                out=inner["result"]; ms=(time.perf_counter()-t0)*1000
                return _success(module_name,payload,out,{"consistent":out.get("consistent")},ms)
            ms=(time.perf_counter()-t0)*1000
            return _failure(module_name,payload,[inner.get("error","unknown")],ms)
        elif module_name == "operational_monitor":
            from src.monitoring.operational_drift_monitor import run; inner=run(payload)
            if inner["status"]=="SUCCESS":
                out=inner["result"]; ms=(time.perf_counter()-t0)*1000
                return _success(module_name,payload,out,{},ms)
            ms=(time.perf_counter()-t0)*1000
            return _failure(module_name,payload,[inner.get("error","unknown")],ms)
    except Exception as exc:
        ms=(time.perf_counter()-t0)*1000
        return _failure(module_name,payload,[f"RuntimeError: {exc}"],ms)
