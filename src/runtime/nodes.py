# src/runtime/nodes.py
import hashlib
def _sha256(d): return hashlib.sha256(d.encode()).hexdigest()
def init_node_hash(nid): return _sha256(f"INIT:{nid}")
class DistributedNode:
    def __init__(self,node_id):
        self.node_id=node_id; self.received_invocations=[]; self.replay_log=[]
        self.execution_hash=init_node_hash(node_id); self.propagated_events=[]
    def receive(self,env_dict):
        self.received_invocations.append(dict(env_dict))
        self.replay_log.append({"event":"RECEIVED","node":self.node_id,"invocation_id":env_dict["invocation_id"],"sequence_id":env_dict["sequence_id"],"trace_id":env_dict["trace_id"],"from_node":env_dict["node_origin"],"timestamp":env_dict["timestamp"]})
        self._update_hash(env_dict["invocation_id"])
    def record_propagation(self,env_dict,to_node):
        self.propagated_events.append({"to_node":to_node,"invocation_id":env_dict["invocation_id"],"sequence_id":env_dict["sequence_id"],"trace_id":env_dict["trace_id"]})
        self.replay_log.append({"event":"PROPAGATED","node":self.node_id,"invocation_id":env_dict["invocation_id"],"sequence_id":env_dict["sequence_id"],"to_node":to_node})
    def _update_hash(self,iid): self.execution_hash=_sha256(f"{self.execution_hash}:{iid}")
    def reset(self):
        self.received_invocations=[]; self.replay_log=[]
        self.execution_hash=init_node_hash(self.node_id); self.propagated_events=[]
    def status(self):
        return {"node_id":self.node_id,"received_count":len(self.received_invocations),"propagated_count":len(self.propagated_events),"execution_hash":self.execution_hash,"replay_log_count":len(self.replay_log)}
    def received_invocation_ids(self): return [e["invocation_id"] for e in self.received_invocations]
Node_A=DistributedNode("Node_A"); Node_B=DistributedNode("Node_B"); Node_C=DistributedNode("Node_C")
ALL_NODES={"Node_A":Node_A,"Node_B":Node_B,"Node_C":Node_C}
def reset_all_nodes():
    for n in ALL_NODES.values(): n.reset()
