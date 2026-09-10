# src/runtime/envelope.py
import hashlib, json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
_ANCHOR=datetime(2026,1,1,0,0,0,tzinfo=timezone.utc)
def _sha256(d): return hashlib.sha256(d.encode()).hexdigest()
def compute_payload_hash(p): return _sha256(json.dumps(p,sort_keys=True,separators=(",",":")))
def compute_trace_id(qapp_id,node_origin,seq): return _sha256(f"trace:{qapp_id}:{node_origin}:{seq}")
def compute_invocation_id(trace_id,payload_hash,seq): return _sha256(f"invoke:{trace_id}:{payload_hash}:{seq}")
def compute_timestamp(seq): return (_ANCHOR+timedelta(seconds=seq*60)).strftime("%Y-%m-%dT%H:%M:%SZ")
@dataclass(frozen=True)
class QAppExecutionEnvelope:
    trace_id:str; qapp_id:str; node_origin:str; invocation_id:str
    payload_hash:str; sequence_id:int; timestamp:str; contract_version:str
    @classmethod
    def create(cls,qapp_id,node_origin,payload,sequence_id,contract_version="qapp-v1.0"):
        ph=compute_payload_hash(payload); tid=compute_trace_id(qapp_id,node_origin,sequence_id)
        iid=compute_invocation_id(tid,ph,sequence_id); ts=compute_timestamp(sequence_id)
        return cls(trace_id=tid,qapp_id=qapp_id,node_origin=node_origin,invocation_id=iid,
                   payload_hash=ph,sequence_id=sequence_id,timestamp=ts,contract_version=contract_version)
    def to_dict(self):
        return {"trace_id":self.trace_id,"qapp_id":self.qapp_id,"node_origin":self.node_origin,
                "invocation_id":self.invocation_id,"payload_hash":self.payload_hash,
                "sequence_id":self.sequence_id,"timestamp":self.timestamp,"contract_version":self.contract_version}
