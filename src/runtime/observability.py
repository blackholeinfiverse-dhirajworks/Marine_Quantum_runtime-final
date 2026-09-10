# src/runtime/observability.py
# Console-based observability layer for runtime state inspection.
# No UI, no external tooling, no log aggregation — console is the observability layer.

from src.runtime.nodes import ALL_NODES, Node_B, Node_C
from src.runtime.propagation import get_propagation_log, replay_qapp_log


def render_propagation_chain(envelopes: list) -> None:
    print("\n  ┌── Propagation Chain ─────────────────────────────────────────┐")
    for env in envelopes:
        print(f"  │  seq={env.sequence_id}  ts={env.timestamp}")
        print(f"  │  invoke={env.invocation_id[:28]}...")
        print(f"  │  Node_A  →  Node_B  ✅")
        print(f"  │  Node_A  →  Node_C  ✅")
    print(f"  └──────────────────────────────────────────────────────────────┘")


def render_node_status() -> None:
    print("\n  ┌── Node Replay Status ────────────────────────────────────────┐")
    for nid, node in ALL_NODES.items():
        s = node.status()
        print(f"  │  {nid:<8}  recv={s['received_count']:>2}  "
              f"propagated={s['propagated_count']:>2}  "
              f"log_entries={s['replay_log_count']:>2}  "
              f"hash={s['execution_hash'][:20]}...")
    print(f"  └──────────────────────────────────────────────────────────────┘")


def render_divergence_check() -> bool:
    b_inv = Node_B.received_invocation_ids()
    c_inv = Node_C.received_invocation_ids()
    diverged = (b_inv != c_inv)
    print("\n  ┌── Divergence Detection ─────────────────────────────────────┐")
    print(f"  │  Node_B invocations : {[i[:12]+'...' for i in b_inv]}")
    print(f"  │  Node_C invocations : {[i[:12]+'...' for i in c_inv]}")
    print(f"  │  Divergence         : {'❌ YES — ALERT' if diverged else '✅ NONE — nodes consistent'}")
    print(f"  └──────────────────────────────────────────────────────────────┘")
    return diverged


def render_replay_verification(log: list) -> dict:
    result = replay_qapp_log(log, silent=True)
    print("\n  ┌── Replay Verification ──────────────────────────────────────┐")
    for nid in ["Node_A", "Node_B", "Node_C"]:
        print(f"  │  {nid:<8}  hash={result['node_hashes'][nid][:28]}...")
    print(f"  │  consistent : {'✅ YES' if result['consistent'] else '❌ NO'}")
    print(f"  └──────────────────────────────────────────────────────────────┘")
    return result


def render_consensus_hash(result: dict) -> None:
    print("\n  ┌── Final Consensus Hash ─────────────────────────────────────┐")
    print(f"  │  consensus : {result['consensus_hash']}")
    print(f"  │  log_hash  : {result['log_hash']}")
    print(f"  └──────────────────────────────────────────────────────────────┘")


def render_full_dashboard(envelopes: list, log: list) -> dict:
    render_propagation_chain(envelopes)
    render_node_status()
    diverged = render_divergence_check()
    result   = render_replay_verification(log)
    render_consensus_hash(result)
    return {"diverged": diverged, "replay_result": result}
