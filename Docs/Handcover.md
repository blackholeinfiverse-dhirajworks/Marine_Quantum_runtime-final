
# Handover Document — Marine Intelligence Quantum Runtime

**For:** New developer continuing the build
**From:** Dhiraj Chavan
**Date:** May 2026

---

## Startup Steps

### 1. Clone and verify

```bash
git clone <repo-url>
cd marine_quantum_runtime
python --version   # Must be Python 3.8+
```

No external dependencies for core runtime. All modules use stdlib only.

### 2. Run all four entry points

```bash
# Signal layer (Tasks 1–4)
python run/run_signal.py

# Quantum pipeline (Task 8)
python run/run_quantum_pipeline.py

# Distributed QApp (Task 9)
python run/run_distributed_qapp.py

# Operational drift monitor
python run/run_operational_drift.py
```

All must exit with code `0`. Any non-zero exit is a regression.

### 3. Optional: Full quantum circuit (requires qiskit)

```bash
pip install qiskit qiskit-aer pydantic
```

The runtime degrades gracefully without these — classical stubs are used automatically.

---

## Folder Guide

| Path | What It Is |
|---|---|
| `src/invoke_runtime.py` | **Start here.** Single gateway for all runtime invocations. |
| `src/signal/` | Signal generator — Tasks 1–4. Pure functions, no side effects. |
| `src/quantum/` | Quantum pipeline — Task 8. `descriptors.py` is the QApp registry. |
| `src/runtime/` | Distributed propagation — Task 9. `envelope.py` → `nodes.py` → `propagation.py`. |
| `src/monitoring/` | Operational drift monitor. In-memory event log + drift detection. |
| `src/contracts/` | Contract governance. `qapp_contract.py` = MARINE-INT-002 v1.0.0. |
| `run/` | Entry point scripts — one per module, run directly with `python`. |
| `review_packets/` | Task-by-task design records (Tasks 1–9 + current). |
| `docs/` | Architecture, execution flow, determinism proof, failure matrix, this file. |
| `testing/` | Testing packet + evidence folder (screenshots go in `testing/testing_evidence/`). |
| `data/` | Sample JSON payloads for manual testing. |

---

## Command List

```bash
# Run all modules
python run/run_signal.py
python run/run_quantum_pipeline.py
python run/run_distributed_qapp.py
python run/run_operational_drift.py

# Use invoke_runtime directly (Python REPL)
python3 -c "
import sys; sys.path.insert(0, '.')
from src.invoke_runtime import invoke_runtime
result = invoke_runtime('signal', {
    'node_id': 'qnode_01', 'energy_delta': 0.0001,
    'iterations': 120, 'confidence': 0.92, 'variance': 0.002
})
import json; print(json.dumps(result, indent=2))
"

# Check registered QApps
python3 -c "
import sys; sys.path.insert(0, '.')
from src.quantum.descriptors import list_registered, get
print('Registered QApps:', list_registered())
desc = get('marine_corrosion_qapp')
print('Descriptor:', desc)
"

# Check module status
python3 -c "
import sys; sys.path.insert(0, '.')
from src.invoke_runtime import module_status
import json; print(json.dumps(module_status(), indent=2))
"

# Git status / commit
git status
git log --oneline -10
git add -A && git commit -m "message"
```

---

## FAQ

**Q: Why does `run_signal.py` not import from `src.signal` directly?**
A: It uses `invoke_runtime("signal", payload)` to validate the runtime surface. The direct imports are inside `src/signal/` for isolation testing.

**Q: What is `_DEFAULT_SEQ = 1` and why doesn't seq auto-increment?**
A: Sequence number monotonicity is the *caller's* responsibility. The engine is stateless — same input always produces the same output. If you need monotonic seq, implement a `SequenceRegistry` in your caller.

**Q: Why is the timestamp synthetic (`iterations × 60s`)?**
A: Determinism. Using `datetime.now()` would break the 5-run identical output proof. In production, the caller should supply a real timestamp in the payload and the engine can pass it through.

**Q: Why are `Node_A/B/C` module-level singletons?**
A: For the propagation demo, single-session state is sufficient. In production, nodes would be instantiated per session/tenant and not share module-level state.

**Q: Does the quantum circuit actually run on a quantum computer?**
A: No. `src/quantum/execution.py` uses a deterministic classical simulation stub. The full HEA circuit (in `src/quantum/algorithm.py`) requires `qiskit` + `qiskit-aer`. The design is production-ready; only the execution backend needs swapping.

**Q: What is `MARINE-INT-002 v1.0.0`?**
A: The integration contract between the quantum signal layer and BHIV Core. Defined in `src/contracts/qapp_contract.py`. It specifies required fields, valid states, and range constraints for all output events.

---

## Known Weak Spots

| Area | Risk | Mitigation |
|---|---|---|
| `seq` monotonicity | Caller can pass `seq=1` every time with no error | Add `SequenceRegistry` in caller; document as caller responsibility |
| Synthetic timestamp | Downstream system treats `ts` as real time | Add explicit warning in API docs; require caller to pass real ts in production |
| Module-level node singletons | Not safe for multi-tenant or concurrent use | Instantiate per-session in production |
| `iterations=0` + CONVERGED | Semantically invalid in real physics | Add guard rule: `iterations == 0` → force `SUSPENDED` or `INITIALISING` state |
| Classical circuit stub | Not quantum — no entanglement, no superposition | Install `qiskit` + `qiskit-aer` and swap `execution.py` backend |
| No `seq` validation in envelope | Out-of-order detection is post-propagation only | Add pre-propagation monotonicity check in `propagate_qapp_event()` |

---

## Debugging Notes

**Signal returns SUSPENDED when expecting CONVERGED:**
Check the transition table priority. `confidence < 0.70` fires before the CONVERGED rule.
Debug path: `src/signal/mapping_logic._determine_next_state()` — add print statements to trace rule firing.

**Replay hash doesn't match live hash:**
Check that `_PROPAGATION_LOG` wasn't modified between propagation and replay.
`get_propagation_log()` returns a copy — the source can't be mutated by callers.
Verify all three nodes use the same `init_node_hash()` genesis.

**`invoke_runtime` returns IMPORT_ERROR:**
Run `python3 -c "from src.invoke_runtime import module_status; print(module_status())"` from the repo root.
Ensure `ROOT` is in `sys.path` before any imports.

**QApp descriptor not found:**
`src/quantum/descriptors.py` must be imported to trigger auto-registration.
Check: `from src.quantum.descriptors import MARINE_CORROSION_QAPP`.

---

*Dhiraj Chavan · Marine Intelligence System · May 2026*
