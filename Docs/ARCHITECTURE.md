# Docs/ARCHITECTURE.md
# Quantum Runtime Capability — Architecture
**Author:** Dhiraj Chavan | Marine Intelligence System | July 2026

---

## System Boundary

This runtime is a **Sovereign Quantum Runtime Capability** in the BHIV
ecosystem. It is no longer scoped to marine hull simulation. Any BHIV
product attaches to it via the provider abstraction or the federation
client interface.

**Owned by this runtime:**
- Quantum execution abstraction (provider/backend interface)
- Runtime capability registration, discovery, versioning, health
- Distributed job lifecycle (queue, route, retry, cancel)
- Runtime contracts and schema enforcement
- Provenance participation (consumer-side only)
- Observability (capability-level + quantum backend-level)
- Dashboard telemetry production (not rendering)

**Explicitly NOT owned:**
- Replay authority decisions → consumed from Pritesh via `ReplayAuthorityClient`
- Governance/evidence legitimacy → consumed, not decided
- Physical execution engine → Kanishk
- Dashboard rendering → downstream consumers
- Runtime execution ordering → Raj

---

## Layer Map

```
┌─────────────────────────────────────────────────────────────────┐
│                     BHIV Ecosystem Boundary                     │
│                                                                 │
│  Kanishk's Engine    Pritesh's Platform    Raj's Governance     │
│       ▲                     ▲                    ▲              │
│       │                     │                    │              │
└───────┼─────────────────────┼────────────────────┼─────────────┘
        │  ProviderInterface  │  FederationClients │  AuthMatrix
        │                     │                    │
┌─────────────────────────────────────────────────────────────────┐
│                Quantum Runtime Capability                        │
│                                                                 │
│  invoke_capability()          production_execute()              │
│       │                              │                          │
│  CapabilityRegistry         QuantumExecutionRouter              │
│  AuthorityMatrix            ├── AerProvider (REAL)              │
│  SequenceRegistry           ├── LocalSimulatorProvider (REAL)   │
│  ReplayAuthorityClient      ├── IBMRuntimeProvider (adapter)    │
│  EvidenceClient             └── IonQProvider (adapter)          │
│  PersistentHistory                   │                          │
│       │                   DistributedRuntimeManager             │
│       │                   ├── node_1 ──┐                        │
│       │                   ├── node_2   ├── JobQueue             │
│       │                   └── node_3 ──┘   RetryPolicy          │
│       │                              │                          │
│  ObservabilityV2          DashboardTelemetry                    │
│  ├── distributed traces   ├── replay_dashboard_telemetry        │
│  ├── execution graphs     ├── runtime_dashboard_telemetry       │
│  ├── provider health      ├── quantum_dashboard_telemetry       │
│  ├── capability utilization├── operations_dashboard_telemetry  │
│  └── success/failure trends├── health_dashboard_telemetry      │
│                            └── governance_dashboard_telemetry   │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Is Real vs Structurally Ready

| Component | Status | Evidence |
|---|---|---|
| Signal generator (Tasks 1–4) | Real | 5-run determinism proof, `run_signal.py` |
| AerProvider quantum execution | Real | GHZ circuit: `{'000': ~490, '111': ~534}` from actual `AerSimulator` |
| LocalSimulatorProvider | Real | stdlib, always available |
| IBM Runtime adapter | Shape-complete | health() returns honest CREDENTIALS_REQUIRED |
| IonQ adapter | Shape-complete | health() returns honest CREDENTIALS_REQUIRED |
| Provider registry + negotiation | Real | 5th fictional provider registered at runtime in Phase 7.1 |
| Quantum execution router + failover | Real | IBM/IonQ failover path exercised in Phase 7.2 |
| Distributed runtime manager (N nodes) | Real in-process | 9 jobs, 3 nodes, round-robin, all proven |
| Federation clients (7 clients) | Real interface | fail-closed proven; live against reference implementations proven |
| CanonicalReplayAuthority | Real implementation | PERMIT/DENY/REPLAY_VERIFIED/REPLAY_DIVERGED all proven |
| PersistentHistory | Real (JSONL, survives restart) | restart persistence proven in isolation |
| Production runtime (limits + noise + HW) | Real | limit enforcement, identical output surface proven |
| Observability v2 | Real | 7 sections built from real DistributedRuntimeManager data |
| Dashboard telemetry (6 feeds) | Real | all 6 produced from real data, no errors |
| Governance layer (authority, ledger, doctrine) | Real | 46/46 governance checks |

---

## Data Flows

### Single circuit submission
```
CircuitSpec → production_execute() → BackendRequirements → route_and_execute()
    → negotiate_with_health() → AerBackend.execute() → ExecutionResult
    → ObservabilityV2 → DashboardTelemetry
```

### Federated capability invocation
```
payload → invoke_capability() → dependency_graph_check → authority_matrix_check
    → typed_attachment_validate → CanonicalReplayAuthority.check() → execute()
    → PersistentHistory.append() → ObservabilityLayer.record()
    → FederationRuntime.federated_execute() → EvidenceClient.push()
    → ProvenanceClient.record() → TimelineClient.publish_event()
```

### Distributed job lifecycle
```
submit_job() → QUEUED → process_queue() → ROUTING (round-robin node select)
    → RUNNING → route_and_execute() + retry_policy → COMPLETED/FAILED
    → event_log() + queue_statistics() + observability_v2.build_all_traces()
```

---

## Determinism Invariants

No change from the governance sprint. All still hold:
- No `datetime.now()` in core logic
- All IDs are SHA-256 of deterministic inputs
- Same input → same output (proven across both real backends with seeding)
- Append-only logs and ledgers (propagation log, decision ledger, evidence)
- OTel spans are seq-derived, not wall-clock derived

---

*Architecture reflects the state after Phases 1–9 of the Ecosystem Integration Sprint.*
*See `KNOWN_LIMITATIONS.md` for what is not yet real.*
