# src/runtime/replay.py
# Replay safety utilities — deterministic log reconstruction.

import hashlib
import json
from typing import Optional


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def causal_sort(log: list) -> list:
    """Sort a propagation log by (sequence_id, step_order)."""
    step_order = {"ORIGIN": 0, "PROPAGATE": 1}
    return sorted(log, key=lambda e: (e["sequence_id"], step_order.get(e["step"], 99)))


def compute_replay_hash(log: list) -> str:
    """Compute a canonical hash of a sorted propagation log."""
    sorted_log = causal_sort(log)
    canonical  = json.dumps(sorted_log, sort_keys=True, separators=(",", ":"))
    return _sha256(canonical)


def verify_replay_determinism(log: list, runs: int = 5) -> dict:
    """
    Replay the same log N times and verify all consensus hashes match.
    Returns a result dict with pass/fail and hash list.
    """
    from src.runtime.propagation import replay_qapp_log
    hashes = []
    for _ in range(runs):
        result = replay_qapp_log(list(log), silent=True)
        hashes.append(result["consensus_hash"])
    all_same = len(set(hashes)) == 1
    return {
        "deterministic": all_same,
        "runs": runs,
        "consensus_hashes": hashes,
        "canonical_hash": hashes[0] if hashes else None,
    }


def verify_shuffle_convergence(log: list, trials: int = 3, seed: int = 42) -> dict:
    """
    Shuffle the log N times and replay each — all must converge to the same hash.
    """
    import random
    from src.runtime.propagation import replay_qapp_log
    random.seed(seed)
    canonical_result = replay_qapp_log(list(log), silent=True)
    canonical_hash   = canonical_result["consensus_hash"]
    results = []
    for trial in range(trials):
        shuffled = list(log)
        random.shuffle(shuffled)
        r = replay_qapp_log(shuffled, silent=True)
        match = r["consensus_hash"] == canonical_hash
        results.append({"trial": trial + 1, "match": match,
                        "consensus_hash": r["consensus_hash"]})
    all_converge = all(r["match"] for r in results)
    return {
        "all_converge": all_converge,
        "canonical_hash": canonical_hash,
        "trials": results,
    }
