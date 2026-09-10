# HANDOVER.md
# Quantum Runtime Capability — 30-Minute Handover
**Author:** Dhiraj Chavan | Marine Intelligence System | June 2026

---

## 1. Run This First (2 minutes)

```bash
pip install qiskit qiskit-aer --break-system-packages   # one-time, if not installed
python run/run_ecosystem_integration.py                  # 33/33 checks, exit 0
```

If it exits 0: every system described in this document works. Start reading.

---

## 2. What This System Is (3 minutes)

A **Sovereign Quantum Runtime Capability** for the BHIV ecosystem. Not a
marine project. Any BHIV product attaches to it through a provider abstraction
(add a backend) or a federation client (attach an authority or ledger).

It owns:
- Quantum execution abstraction (all backends share one interface)
- Runtime capability registration + health
- Distributed job queueing and execution
- Observability (capability-level + quantum backend-level + dashboard telemetry)
- Runtime contracts and provenance participation (consumer, not owner)

It explicitly does NOT own:
- Replay authority decisions (consumed via `ReplayAuthorityClient`, fails closed if nothing attached)
- Governance / evidence legitimacy (consumed via `EvidenceClient`, `ProvenanceClient`)
- Physical execution engine (Kanishk)
- Dashboard rendering (telemetry producer only)
- Runtime execution ordering (Raj)

---

## 3. Architecture in 90 Seconds

```
  BHIV ecosystem
        │
        ▼
  FederationRuntime               ← consume replay authority, push evidence/provenance
        │
        ▼
  invoke_capability()             ← full stack: dep-graph → authority-check → typed-attach → replay → execute → evidence
        │
        ├── RuntimeCapabilityRegistry    signal / quantum_pipeline / distributed_qapp / operational_monitor
        ├── AuthorityMatrix              check ceiling + negative authority per capability
        ├── CanonicalReplayAuthority     PERMIT / DENY based on invocation history
        └── PersistentHistory            JSONL evidence log, survives restarts
        │
        ▼
  QuantumExecutionRouter          ← negotiate best healthy backend, automatic failover
        │
        ├── AerProvider           ← REAL qiskit-aer execution (installed)
        ├── LocalSimulatorProvider ← stdlib, always available
        ├── IBMRuntimeProvider    ← shape-complete, credentials required
        └── IonQProvider          ← shape-complete, API key required
        │
        ▼
  DistributedRuntimeManager       ← job queue, round-robin routing across N nodes, retry policy
        │
        ▼
  ObservabilityV2 + DashboardTelemetry  ← distributed traces, provider health, 6 dashboard feeds
```

---

## 4. Key Entry Points (5 minutes)

```python
import sys; sys.path.insert(0, ".")
from src.quantum.providers.base import CircuitSpec, BackendRequirements
from src.quantum.production_runtime import production_execute
from src.runtime.distributed_runtime_manager import DistributedRuntimeManager
from src.federation.federation_runtime import FederationRuntime
from src.runtime.capability_runtime import invoke_capability
from src.governance.replay_legitimacy import CanonicalReplayAuthority

# ─ Single quantum circuit, production surface ────────────────────────────────
circuit = CircuitSpec(num_qubits=3, shots=1024, seed=42, gate_sequence=[
    {"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0, 1]}, {"gate": "cx", "qubits": [1, 2]},
])
result = production_execute(circuit, BackendRequirements(prefer_simulator=True))

# ─ Distributed job queue ──────────────────────────────────────────────────────
mgr = DistributedRuntimeManager(node_ids=["node_1", "node_2", "node_3"])
job_id = mgr.submit_job(circuit)
completed_jobs = mgr.process_queue()

# ─ Federated execution (with governance integration) ─────────────────────────
auth = CanonicalReplayAuthority(allow_re_execution=False)
fed  = FederationRuntime(replay_authority=auth)
result = fed.federated_execute("signal", payload, execute_fn)

# ─ Capability platform invocation ─────────────────────────────────────────────
result = invoke_capability("signal", {"node_id": "qnode_01", ...})
```

---

## 5. Adding a New Provider (5 minutes)

1. Create `src/quantum/providers/your_provider.py`.
2. Implement `QuantumExecutionProvider` + `QuantumExecutionBackend` from `base.py`.
3. `your_backend.execute(circuit: CircuitSpec) -> ExecutionResult` — one method.
4. `provider_registry.register_provider(YourProvider())` — one call.
5. Done. No other file changes. Proven in `run/run_ecosystem_integration.py`.

---

## 6. File Map (5 minutes)

| What you want to touch | File |
|---|---|
| Provider interface | `src/quantum/providers/base.py` |
| Add a backend | `src/quantum/providers/your_provider.py` (new) |
| Provider registry / negotiation | `src/quantum/providers/provider_registry.py` |
| Routing + failover | `src/quantum/providers/quantum_execution_router.py` |
| Production limits + noise + hardware | `src/quantum/production_runtime.py` |
| Distributed job management | `src/runtime/distributed_runtime_manager.py` |
| Federation / ecosystem integration | `src/federation/federation_runtime.py` |
| Capability invocation pipeline | `src/runtime/capability_runtime.py` |
| Authority matrix | `src/governance/authority_matrix.py` |
| Observability v2 | `src/monitoring/observability_v2.py` |
| Dashboard telemetry | `src/monitoring/dashboard_telemetry.py` |
| All open stubs | `STUBS_REGISTRY.md` |
| Known limitations | `KNOWN_LIMITATIONS.md` |

---

## 7. Integration Points (5 minutes)

**Kanishk:** implement `QuantumExecutionProvider` for your execution engine,
register via `provider_registry.register_provider()`. No other code changes.

**Pritesh:** your `CanonicalReplayAuthority` attaches via
`FederationRuntime(replay_authority=YourAuthority())`. Your evidence ledger
attaches via `FederationRuntime(evidence_ledger=YourLedger())`. The interfaces
they must implement are in `src/federation/federation_clients.py`.

**Raj:** governance pre-approval hook is declared `NOT IMPLEMENTED` in
`STUBS_REGISTRY.md`. The attachment point is
`FederationRuntime.federated_execute()` step 3.5. Interface proposal is in
`Docs/INTEGRATION_GUIDE.md`.

**Vinayak:** `python run/run_ecosystem_integration.py`. Exit 0, 33/33.

---

## 8. Pending Work (5 minutes)

Read `KNOWN_LIMITATIONS.md`. Key items:
- IBM/IonQ providers need credentials + network egress — structural proof exists, real execution doesn't
- `FederationRuntime` is proven against reference implementations, not Kanishk's/Pritesh's actual systems
- Distributed routing is in-process, not networked — Jaffer Ali owns the real transport
- Governance pre-approval hook not yet wired — Raj owns this
- Real screenshots for deliverable — this repo has text captures only, Vinayak's machine produces real ones

---

*30 minutes elapsed. You now know the architecture, all entry points, every
integration boundary, and where the open work lives.*
