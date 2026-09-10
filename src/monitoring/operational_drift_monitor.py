# src/monitoring/operational_drift_monitor.py
from dataclasses import dataclass
from typing import List
DRIFT_CONFIDENCE_FLOOR=0.75; DRIFT_VARIANCE_CEILING=0.008; WINDOW_SIZE=10
@dataclass
class DriftEvent:
    node_id:str; event_type:str; value:float; threshold:float; seq:int; message:str
    def to_dict(self): return {"node_id":self.node_id,"event_type":self.event_type,"value":self.value,"threshold":self.threshold,"seq":self.seq,"message":self.message}
class OperationalDriftMonitor:
    def __init__(self,window_size=WINDOW_SIZE):
        self.window_size=window_size; self._windows={}; self._drift_log=[]; self._event_count=0
    def ingest(self,event):
        node_id=event.get("node_ref",event.get("node_id","UNKNOWN"))
        if node_id not in self._windows: self._windows[node_id]=[]
        self._windows[node_id].append(event)
        if len(self._windows[node_id])>self.window_size: self._windows[node_id].pop(0)
        self._event_count+=1; detected=self._check_drift(node_id,event)
        self._drift_log.extend(detected); return detected
    def _check_drift(self,node_id,event):
        detected=[]; ue=event.get("uncertainty_envelope",{}); seq=event.get("transition",{}).get("seq",0)
        sigma=ue.get("sigma",0.0); variance=sigma**2; window=self._windows[node_id]
        if len(window)>=3:
            avg_conf=sum(e.get("uncertainty_envelope",{}).get("confidence",1.0) for e in window)/len(window)
            if avg_conf<DRIFT_CONFIDENCE_FLOOR:
                detected.append(DriftEvent(node_id=node_id,event_type="CONFIDENCE_DEGRADATION",value=round(avg_conf,6),threshold=DRIFT_CONFIDENCE_FLOOR,seq=seq,message=f"Rolling avg confidence {avg_conf:.4f} below floor {DRIFT_CONFIDENCE_FLOOR}"))
        if variance>DRIFT_VARIANCE_CEILING:
            detected.append(DriftEvent(node_id=node_id,event_type="VARIANCE_SPIKE",value=round(variance,8),threshold=DRIFT_VARIANCE_CEILING,seq=seq,message=f"Variance {variance:.6f} exceeds ceiling {DRIFT_VARIANCE_CEILING}"))
        next_state=event.get("transition",{}).get("next","")
        if next_state in("DIVERGED","SUSPENDED") and len(window)>=2:
            prev_state=window[-2].get("transition",{}).get("next","")
            if prev_state=="CONVERGED":
                detected.append(DriftEvent(node_id=node_id,event_type="STATE_SHIFT",value=0.0,threshold=0.0,seq=seq,message=f"State shifted CONVERGED → {next_state}"))
        return detected
    def summary(self):
        return {"events_ingested":self._event_count,"drift_events":len(self._drift_log),"nodes_monitored":list(self._windows.keys()),"drift_log":[d.to_dict() for d in self._drift_log[-20:]]}
    def reset(self): self._windows.clear(); self._drift_log.clear(); self._event_count=0
def run(payload):
    monitor=OperationalDriftMonitor(); events=payload.get("events",[payload])
    all_drift=[]
    for evt in events:
        drift=monitor.ingest(evt); all_drift.extend(d.to_dict() for d in drift)
    return {"module":"operational_monitor","status":"SUCCESS","result":{**monitor.summary(),"new_drift_events":all_drift},"error":None}
