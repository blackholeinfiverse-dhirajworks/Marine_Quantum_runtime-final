# RUNTIME_CAPABILITY_CONTRACT.md
# Marine Intelligence System — TANTRA Runtime
# Phase IV Production Transition Directive
#
# Author : Dhiraj Chavan
# Version: 1.0.0
# Date   : June 2026

---

## 1. Purpose

This contract defines what the Marine Quantum Runtime owns, what it explicitly does **not** own, and how ecosystem participants attach to it. It is a binding declaration of authority boundaries, not a design suggestion.

Every team whose capability runs through this runtime or consumes its outputs must acknowledge the boundaries below before integration.

---

## 2. Runtime Identity

| Attribute        | Value                                |
|------------------|--------------------------------------|
| Runtime name     | Marine Quantum Runtime / TANTRA Core |
| Author           | Dhiraj Chavan                        |
| Version          | 1.0.0                                |
| Schema version   | engine_event_v2.0                    |
| Entry point      | `src/runtime/capability_runtime.py`  |

---

## 3. What the Runtime OWNS

The runtime has full authority over exactly these concerns — nothing else.

### 3.1 Execution
- Receiving capability invocation requests
- Dispatching to registered capabilities through the `RuntimeCapabilityRegistry`
- Enforcing attachment validation before any execution begins
- Returning structured, schema-validated results to the caller
- Emitting deterministic `execution_id` and `deterministic_hash` per invocation

### 3.2 Capability Invocation
- Maintaining the `RuntimeCapabilityRegistry` — capability registration, discovery, versioning, health
- Calling `check()` on the attached `CanonicalReplayAuthority` before every execution
- Routing to the correct capability via the capability ID

### 3.3 Lifecycle
- Capability registration and de-registration
- Attachment validation (`validate_attachment()`)
- Per-session invocation sequencing (monotonic `seq` counter)

### 3.4 Health Reporting
- Tracking invocation outcomes per capability (success / failure counts)
- Exposing `get_runtime_health()`, `get_runtime_heartbeat()`, `get_capability_metrics()`
- Classifying capability health: IDLE | HEALTHY | DEGRADED | UNHEALTHY

### 3.5 Runtime Metrics
- Invocation timeline (append-only, never mutated)
- Per-capability latency (avg / min / max)
- Failure aggregation (structured error records)
- Dashboard-ready JSON via `get_dashboard_json()`

---

## 4. What the Runtime EXPLICITLY DOES NOT OWN

These concerns are owned by other teams. The runtime **consumes** them through bounded interfaces — it never makes decisions in their domain.

### 4.1 Governance
- **Owner: TMS Strategic layer**
- The runtime does not govern which capabilities may run, who may invoke them, or under what business rules.
- The runtime executes what the governance layer permits.

### 4.2 Replay Authority
- **Owner: Pritesh (Provenance Capability)**
- The runtime calls `CanonicalReplayAuthority.check()` before every execution.
- If the authority returns DENY, the runtime halts and returns `status=REPLAY_DENIED`.
- The runtime never makes a replay decision. The authority is attached via `attach_replay_authority()`.

### 4.3 Provenance Authority
- **Owner: Pritesh (Provenance Capability)**
- The runtime emits `ExecutionRecord` objects to the attached `EvidenceLedger` after every invocation.
- The runtime does not own, validate, or interpret the evidence. It only appends.
- The ledger is attached via `attach_evidence_ledger()`.

### 4.4 Optimization Decisions
- **Owner: Kanishk (Optimization Capability)**
- The runtime provides an attachment surface through `RuntimeCapabilityRegistry` so Kanishk's `UniversalSolverFabric` can register itself as a capability and execute through the runtime.
- No optimization logic lives inside the runtime.

### 4.5 Execution Legitimacy
- **Owner: Raj Prajapati (Routing & Enforcement layer)**
- Whether an invocation is legitimate, in the correct causal order, or authorized by business rules is Raj's domain.
- The runtime executes — legitimacy judgment is upstream.

### 4.6 Dashboard Authority
- **Owner: Future dashboard consumers (SETU, NICAI, InsightFlow, etc.)**
- The runtime exposes `get_dashboard_json()` — structured, schema-stable JSON.
- It does not render UI, aggregate across sessions, or make display decisions.

---

## 5. Upstream Dependencies (what the runtime consumes)

| Dependency                    | Owner    | Interface                                  | Behaviour if absent        |
|-------------------------------|----------|--------------------------------------------|----------------------------|
| `CanonicalReplayAuthority`    | Pritesh  | `attach_replay_authority(authority)`       | Stub returns PERMIT always |
| `EvidenceLedger`              | Pritesh  | `attach_evidence_ledger(ledger)`           | Records buffered in-memory |
| Governance approval           | TMS      | Pre-invocation approval (not yet wired)    | Not enforced (future)      |

---

## 6. Downstream Dependencies (what consumes the runtime)

| Consumer                      | What they consume                                |
|-------------------------------|--------------------------------------------------|
| Pritesh (Provenance)          | `ExecutionRecord` objects via `EvidenceLedger`   |
| Kanishk (Optimization)        | Capability attachment surface (registry)         |
| Raj (Routing/Enforcement)     | `invoke_capability()` return envelope            |
| Dashboard consumers           | `get_dashboard_json()` JSON structure            |
| SETU, NICAI, InsightFlow      | `get_active_capabilities()`, health APIs         |

---

## 7. Capability Contract Template

Every capability registering with this runtime must declare:

```python
CapabilityDescriptor(
    capability_id     = "<stable-id>",          # never changes once registered
    owner             = "<team>",
    version           = "<semver>",
    capability_class  = "SIGNAL|QUANTUM|DISTRIBUTED|MONITORING|OPTIMIZATION|PROVENANCE",
    inputs            = ["<key1>", "<key2>"],   # all required input keys
    outputs           = ["<key1>", "<key2>"],   # guaranteed output keys
    dependencies      = ["<other_cap_id>"],     # or [] if none
    authority_ceiling = "<MAX_AUTHORITY>",      # what this capability may maximally do
    negative_authority = [                      # must be non-empty
        "Must not <action_1>",
        "Must not <action_2>",
    ],
    description = "<human-readable purpose>",
)
```

Capabilities that omit `negative_authority` are rejected at registration. This is a hard requirement, not a recommendation.

---

## 8. Invocation Contract

Every call to `invoke_capability(capability_id, payload)` guarantees:

| Property                   | Guarantee                                                                     |
|----------------------------|-------------------------------------------------------------------------------|
| `invocation_id`            | SHA-256 of `(capability_id, payload)` — deterministic, replay-safe           |
| `deterministic_hash`       | SHA-256 of canonical output — same output → same hash                        |
| `replay_authority`         | Always consulted — decision included in return envelope                       |
| `provenance_ref`           | Equals `invocation_id` — key for Pritesh's ledger lookup                     |
| Attachment validation      | Always performed before execution — missing inputs halt with VALIDATION_ERROR |
| No `datetime.now()`        | Timestamps are deterministic — derived from `iterations × 60s` anchor        |

---

## 9. What this Contract Does NOT Cover

- Semantic validity of capability output (the capability's own contract covers this)
- Time-bounded execution guarantees (no SLA defined)
- Forward compatibility of output schemas beyond minor version increments
- Cross-session state (runtime is stateless across process restarts)
- Concurrent invocation safety (single-threaded; multi-threading is caller's responsibility)

---

## 10. Version History

| Version | Date      | Change                                          |
|---------|-----------|-------------------------------------------------|
| 1.0.0   | June 2026 | Initial contract — Phase IV Production Transition |
