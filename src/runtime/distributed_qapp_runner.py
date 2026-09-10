# src/runtime/distributed_qapp_runner.py
import random
from src.runtime.envelope import QAppExecutionEnvelope
from src.runtime.nodes import reset_all_nodes
from src.runtime.propagation import propagate_qapp_event,replay_qapp_log,get_propagation_log,clear_propagation_log
QAPP_ID="bhiv.corrosion.delta.v1"; NODE_ORIGIN="Node_A"; CONTRACT_VERSION="qapp-v1.0"
DEFAULT_PAYLOADS=[
    {"node_id":"qnode_01","energy_delta":0.0001,"iterations":120,"confidence":0.92,"variance":0.002},
    {"node_id":"qnode_02","energy_delta":0.003,"iterations":340,"confidence":0.87,"variance":0.004},
    {"node_id":"qnode_03","energy_delta":0.00005,"iterations":55,"confidence":0.98,"variance":0.0008},
]
def run(payload):
    payloads=payload.get("payloads",DEFAULT_PAYLOADS)
    prove_det=payload.get("prove_determinism",True); silent=payload.get("silent",False)
    reset_all_nodes(); clear_propagation_log()
    envelopes=[QAppExecutionEnvelope.create(qapp_id=QAPP_ID,node_origin=NODE_ORIGIN,payload=pl,sequence_id=i,contract_version=CONTRACT_VERSION) for i,pl in enumerate(payloads,1)]
    for env in envelopes: propagate_qapp_event(env)
    log=get_propagation_log(); result=replay_qapp_log(log,silent=silent)
    det_proof=None; shuffle_proof=None
    if prove_det:
        hashes=[replay_qapp_log(list(log),silent=True)["consensus_hash"] for _ in range(5)]
        det_proof={"deterministic":len(set(hashes))==1,"runs":5,"consensus_hashes":hashes}
        random.seed(42); shuffled=list(log); random.shuffle(shuffled)
        rs=replay_qapp_log(shuffled,silent=True)
        shuffle_proof={"converges":rs["consensus_hash"]==result["consensus_hash"],"consensus_hash":rs["consensus_hash"]}
    return {"module":"distributed_qapp","status":"SUCCESS","result":{"envelopes_propagated":len(envelopes),"log_entries":len(log),"consensus_hash":result["consensus_hash"],"log_hash":result["log_hash"],"consistent":result["consistent"],"determinism_proof":det_proof,"shuffle_proof":shuffle_proof},"error":None}
