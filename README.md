# marine_quantum_runtime

**Marine Intelligence System — Canonical Quantum Runtime Foundation**
**Author:** Dhiraj Chavan · BHIV Core · June 2026

> One repo. One lineage. One deterministic execution surface.
> Governance is now executable, not documented.

---

## Quick Start

```bash
# No pip installs, no arguments
python run/run_signal.py
python run/run_quantum_pipeline.py
python run/run_distributed_qapp.py
python run/run_operational_drift.py
python run/run_governance.py
```

**Requirements:** Python 3.8+ · No external dependencies · stdlib only

Exit code `0` = PASS. Exit code `1` = FAIL (reason printed before exit).

---

## REST API (New — for HTTP/QCG ecosystem integration)

```bash
pip install fastapi uvicorn qiskit qiskit-aer
export RUNTIME_API_KEY=your-secret-key
uvicorn api_server:app --reload --port 8000
# Swagger UI → http://localhost:8000/docs
```

For the QCG ecosystem integration request, the full developer guide is in
**`INTEGRATION_GUIDE.md`**. The developer reply is in **`QCG_DEVELOPER_REPLY.md`**.

---

## What's New In This Sprint

This release closes the gaps identified in the prior review: capability
dependency graphs, version negotiation, hot attach/detach, conflict detection,
typed attachment validation, per-capability sequence isolation, a real
(non-stub) Canonical Replay Authority, persistent evidence (survives restart),
a Decision Ledger, a Semantic Registry, an executable Doctrine Registry, and
metrics/OTel export adapters.

See `Review_packets/task_gap_closure_review.md` for the full accounting of
what was closed, what remains partial, and what is honestly still missing.

See `STUBS_REGISTRY.md` for every stub in the system — what it replaces, who
owns the real implementation, and what the risk is if left unaddressed.

---

## Repository Structure

```
marine_quantum_runtime/
├── README.md
├── requirements.txt
├── REVIEW_PACKET.md
├── STUBS_REGISTRY.md              ← NEW: honest stub declarations
├── RUNTIME_CAPABILITY_CONTRACT.md
├── invoke_runtime.py               ← root gateway
│
├── run/
│   ├── run_signal.py
│   ├── run_quantum_pipeline.py
│   ├── run_distributed_qapp.py
│   ├── run_operational_drift.py
│   └── run_governance.py           ← NEW: 46 executable governance checks
│
├── src/
│   ├── signal/                     ← Tasks 1–4
│   ├── quantum/                    ← Task 8
│   │
│   ├── runtime/                    ← Task 9 + capability platform
│   │   ├── envelope.py
│   │   ├── nodes.py
│   │   ├── propagation.py
│   │   ├── distributed_qapp_runner.py
│   │   ├── runtime_capability_registry.py   ← UPDATED: dependency graph, version negotiation, hot attach/detach, conflicts
│   │   ├── runtime_observability.py
│   │   ├── capability_runtime.py            ← UPDATED: real replay authority, persistent evidence, typed validation
│   │   ├── sequence_registry.py             ← NEW: per-capability isolated counters
│   │   └── persistent_history.py            ← NEW: JSONL append-only, survives restart
│   │
│   ├── governance/                 ← NEW LAYER
│   │   ├── authority_matrix.py     ← Executable authority ceilings + negative authority
│   │   ├── decision_ledger.py      ← Append-only, SHA-256-chained decision record
│   │   ├── semantic_registry.py    ← Domain meaning + invariants + known limitations
│   │   ├── doctrine_registry.py    ← 8 executable design-rule checks
│   │   └── replay_legitimacy.py    ← Real CanonicalReplayAuthority (not a stub)
│   │
│   ├── monitoring/
│   │   ├── operational_drift_monitor.py
│   │   ├── metrics_export.py       ← NEW: dict, JSONL, Prometheus text export
│   │   └── otel_adapter.py         ← NEW: OTel-compatible spans/metrics/gauges
│   │
│   └── contracts/
│       ├── qapp_contract.py
│       ├── schema_contract.py
│       ├── versioning.py
│       └── typed_attachment.py     ← NEW: type + bounds validation, not key-presence only
│
├── Review_packets/
│   ├── task_1_review.md … task_9_review.md
│   ├── task_capability_platform_review.md
│   └── task_gap_closure_review.md  ← NEW: this sprint's accounting
│
└── Docs/
    ├── architecture.md
    ├── determinism_proof.md
    ├── failure_matrix.md
    └── handover.md
```

---

## Governance API

```python
import sys; sys.path.insert(0, ".")

# Executable authority check
from src.governance.authority_matrix import check, check_execution
result = check_execution("signal")
print(result.permitted, result.reason)

# Decision ledger
from src.governance.decision_ledger import record_decision, summary
record_decision("signal", "classify_state", "PERMIT", "AuthorityMatrix", "Within ceiling")
print(summary())

# Semantic registry
from src.governance.semantic_registry import get, check_invariant
desc = get("signal")
print(desc.known_limitations)

# Doctrine registry
from src.governance.doctrine_registry import evaluate_all
result = evaluate_all({"timestamp_posture": "DETERMINISTIC", "silent_failure": False})
print(result["all_passed"])

# Real replay authority
from src.governance.replay_legitimacy import CanonicalReplayAuthority
auth = CanonicalReplayAuthority(allow_re_execution=False)
decision = auth.check("signal", payload)   # PERMIT or DENY
```

---

## Capability Platform API

```python
from src.runtime.runtime_capability_registry import (
    validate_dependency_graph, negotiate_version,
    detect_conflicts, hot_attach, hot_detach,
)

# Dependency graph
result = validate_dependency_graph("distributed_qapp")
print(result["valid"], result["missing_dependencies"])

# Version negotiation
result = negotiate_version("signal", consumer_version="4.5.0")
print(result["compatible"])

# Conflict detection
result = detect_conflicts()
print(result["status"])  # CLEAN or CONFLICTS_DETECTED
```

---

## Full Invocation Pipeline (capability_runtime.py)

```python
from src.runtime.capability_runtime import invoke_capability

result = invoke_capability("signal", {
    "node_id": "qnode_01", "energy_delta": 0.0001,
    "iterations": 120, "confidence": 0.92, "variance": 0.002
})
```

Pipeline executed on every call:
1. Capability discovery
2. Dependency graph validation
3. Authority matrix check (ceiling + negative authority)
4. Typed attachment validation (types + bounds, not just keys)
5. Real replay authority check (PERMIT/DENY based on invocation history)
6. Execution
7. Persistent evidence emission (survives restart)
8. Observability recording

---

## System-Wide Guarantees

- Same input → identical output, always
- No `datetime.now()` anywhere in core engine
- No randomness in signal, runtime, or contracts layers
- Fails loudly on bad input — no silent failures
- Append-only propagation log, decision ledger, and evidence ledger
- Replay of any log → same hash, same state
- Authority ceilings are enforced at invocation time, not just documented
- Every stub in the system is declared in `STUBS_REGISTRY.md`

---

## Known Limitations

See `STUBS_REGISTRY.md` for the full, honest list. Headline items:
- Quantum circuit execution is a deterministic classical stub (real Qiskit pipeline requires `pip install qiskit qiskit-aer`)
- Kanishk's physical hull engine is not bundled (excluded by design)
- Distributed propagation is in-process, not real network transport
- Governance pre-approval hook and Raj's enforcement engine are not yet wired

---

*Dhiraj Chavan · Marine Intelligence System · BHIV Core · June 2026*
