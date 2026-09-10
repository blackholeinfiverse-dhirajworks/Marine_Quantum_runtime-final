# src/runtime/propagation.py
import hashlib, json
from src.runtime.envelope import QAppExecutionEnvelope
from src.runtime.nodes import Node_A,Node_B,Node_C,init_node_hash
_ALL_NODE_IDS=["Node_A","Node_B","Node_C"]; _STEP_ORDER={"ORIGIN":0,"PROPAGATE":1}
_PROPAGATION_LOG=[]
def _sha256(d): return hashlib.sha256(d.encode()).hexdigest()
def _append(e): _PROPAGATION_LOG.append(e)
def get_propagation_log(): return list(_PROPAGATION_LOG)
def clear_propagation_log(): _PROPAGATION_LOG.clear()
def propagate_qapp_event(envelope):
    env_dict=envelope.to_dict()
    Node_A.receive(env_dict); _append({"step":"ORIGIN","from":"Node_A","to":"Node_A","invocation_id":envelope.invocation_id,"sequence_id":envelope.sequence_id,"trace_id":envelope.trace_id,"timestamp":envelope.timestamp})
    Node_A.record_propagation(env_dict,"Node_B"); Node_B.receive(env_dict); _append({"step":"PROPAGATE","from":"Node_A","to":"Node_B","invocation_id":envelope.invocation_id,"sequence_id":envelope.sequence_id,"trace_id":envelope.trace_id,"timestamp":envelope.timestamp})
    Node_A.record_propagation(env_dict,"Node_C"); Node_C.receive(env_dict); _append({"step":"PROPAGATE","from":"Node_A","to":"Node_C","invocation_id":envelope.invocation_id,"sequence_id":envelope.sequence_id,"trace_id":envelope.trace_id,"timestamp":envelope.timestamp})
def _replay_node_hashes(sorted_log):
    hashes={nid:init_node_hash(nid) for nid in _ALL_NODE_IDS}
    for e in sorted_log:
        t=e["to"]
        if t in hashes: hashes[t]=_sha256(f"{hashes[t]}:{e['invocation_id']}")
    return hashes
def _compute_consensus_hash(node_hashes):
    ordered=json.dumps({k:node_hashes[k] for k in sorted(node_hashes)},separators=(",",":")); return _sha256(ordered)
def _causal_sort(log): return sorted(log,key=lambda e:(e["sequence_id"],_STEP_ORDER.get(e["step"],99)))
def replay_qapp_log(log=None,silent=False):
    if log is None: log=_PROPAGATION_LOG
    sl=_causal_sort(log); node_hashes=_replay_node_hashes(sl)
    log_hash=_sha256(json.dumps(sl,sort_keys=True,separators=(",",":"))); consensus=_compute_consensus_hash(node_hashes)
    def inv_for(nid): return sorted(e["invocation_id"] for e in sl if e["to"]==nid)
    coverage={nid:inv_for(nid) for nid in _ALL_NODE_IDS}
    consistent=(coverage["Node_A"]==coverage["Node_B"]==coverage["Node_C"])
    return {"log_entry_count":len(sl),"node_hashes":node_hashes,"log_hash":log_hash,"consensus_hash":consensus,"consistent":consistent,"coverage":coverage}
