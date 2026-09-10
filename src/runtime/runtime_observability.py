# src/runtime/runtime_observability.py
import hashlib, json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

def _sha256(d): return hashlib.sha256(d.encode()).hexdigest()
def _canonical(o): return json.dumps(o,sort_keys=True,separators=(",",":"))
def make_invocation_id(cap,seq,payload): return _sha256(f"invoke:{cap}:ph={_sha256(_canonical(payload))}")
def make_payload_hash(p): return _sha256(_canonical(p))
def make_output_hash(o): return _sha256(_canonical(o))

@dataclass(frozen=True)
class InvocationRecord:
    invocation_id:str; capability_id:str; status:str; seq:int
    duration_ms:float; error:Optional[str]; payload_hash:str; output_hash:str
    def to_dict(self):
        return {"invocation_id":self.invocation_id,"capability_id":self.capability_id,
                "status":self.status,"seq":self.seq,"duration_ms":self.duration_ms,
                "error":self.error,"payload_hash":self.payload_hash,"output_hash":self.output_hash}

class _CapMetrics:
    def __init__(self,cid):
        self.cid=cid; self._t=0; self._s=0; self._f=0
        self._ms=0.0; self._min=float("inf"); self._max=0.0; self._last="IDLE"; self._err=None
    def record(self,r):
        self._t+=1; self._ms+=r.duration_ms
        self._min=min(self._min,r.duration_ms); self._max=max(self._max,r.duration_ms)
        self._last=r.status
        if r.status=="SUCCESS": self._s+=1
        else: self._f+=1; self._err=r.error
    def to_dict(self):
        avg=self._ms/self._t if self._t>0 else 0.0
        h="IDLE" if self._t==0 else "HEALTHY" if self._f==0 else "DEGRADED" if self._f/self._t<0.25 else "UNHEALTHY"
        return {"capability_id":self.cid,"total_invocations":self._t,"success_count":self._s,
                "failure_count":self._f,"avg_latency_ms":round(avg,3),
                "min_latency_ms":round(self._min,3) if self._t>0 else 0.0,
                "max_latency_ms":round(self._max,3),"last_status":self._last,"last_error":self._err,"health":h}

class _ObsLayer:
    def __init__(self):
        self._history:List[InvocationRecord]=[]; self._metrics:Dict[str,_CapMetrics]={}; self._seq=0
    def record(self,r):
        self._history.append(r)
        if r.capability_id not in self._metrics: self._metrics[r.capability_id]=_CapMetrics(r.capability_id)
        self._metrics[r.capability_id].record(r)
    def next_seq(self):
        self._seq+=1; return self._seq
    def get_runtime_health(self):
        cap_health={cid:m.to_dict()["health"] for cid,m in self._metrics.items()}
        unhealthy=[c for c,h in cap_health.items() if h=="UNHEALTHY"]
        degraded=[c for c,h in cap_health.items() if h=="DEGRADED"]
        overall="UNHEALTHY" if unhealthy else "DEGRADED" if degraded else "HEALTHY"
        return {"overall_health":overall,"total_invocations":len(self._history),
                "capability_health":cap_health,"unhealthy_capabilities":unhealthy,"degraded_capabilities":degraded}
    def get_execution_history(self,limit=None):
        recs=self._history[-limit:] if limit else self._history
        tl=[r.to_dict() for r in recs]
        return {"total_records":len(tl),"success_count":sum(1 for r in recs if r.status=="SUCCESS"),
                "failure_count":sum(1 for r in recs if r.status!="SUCCESS"),"timeline":tl}
    def get_capability_metrics(self): return {cid:m.to_dict() for cid,m in self._metrics.items()}
    def get_runtime_heartbeat(self):
        h=self.get_runtime_health()
        return {"heartbeat":"ALIVE","overall_health":h["overall_health"],"total_invocations":len(self._history),
                "session_seq":self._seq,"active_capabilities":list(self._metrics.keys())}

_OBS=_ObsLayer()
def record_invocation(r): _OBS.record(r)
def get_runtime_health(): return _OBS.get_runtime_health()
def get_execution_history(limit=None): return _OBS.get_execution_history(limit)
def get_capability_metrics(): return _OBS.get_capability_metrics()
def get_runtime_summary():
    return {"runtime_health":_OBS.get_runtime_health(),"execution_history":_OBS.get_execution_history(),
            "capability_metrics":_OBS.get_capability_metrics()}
def get_runtime_heartbeat(): return _OBS.get_runtime_heartbeat()
def next_seq(): return _OBS.next_seq()
