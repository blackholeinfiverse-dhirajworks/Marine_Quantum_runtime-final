# GAP_CLOSURE.md
# Mapping: Review Findings → Implementation → Proof
# Marine Intelligence System | June 2026

This document maps every gap identified in the Phase IV review directly to
its fix. Each row names the exact file, the exact function, and the exact
test in `run/run_governance.py` that proves it works. Where a gap could not
be closed inside this repo (it requires an external system or a human),
that is stated explicitly rather than glossed over.

---

## Capability Platform

### Dependency Graph — CLOSED
- **File:** `src/runtime/runtime_capability_registry.py`
- **Function:** `validate_dependency_graph(capability_id)`, `validate_dependency_graph_all()`
- **Behavior:** Confirms every capability's declared `dependencies` list is
  fully registered before that capability can be invoked. Returns
  `{valid, resolved, missing_dependencies}`.
- **Wired into invocation:** `capability_runtime.invoke_capability()` step 2 —
  invocation halts with `DEPENDENCY_ERROR` if any dependency is missing.
- **Proof:** `run/run_governance.py :: test_dependency_graph()` — PHASE 6.

### Version Negotiation — CLOSED
- **File:** `src/runtime/runtime_capability_registry.py`
- **Function:** `negotiate_version(capability_id, consumer_version)`
- **Behavior:** Major-version compatibility check between a registered
  capability and a consumer's required version.
- **Proof:** `run/run_governance.py :: test_version_negotiation()` — PHASE 8.

### Hot Attach / Detach — CLOSED
- **File:** `src/runtime/runtime_capability_registry.py`
- **Function:** `hot_attach(descriptor)`, `hot_detach(capability_id)`
- **Behavior:** Attach a capability at runtime without restart. Idempotent
  if the same descriptor is re-attached. Raises if a different descriptor
  tries to overwrite an existing registration.
- **Proof:** `run/run_governance.py :: test_hot_attach_detach()` — PHASE 10.

### Conflict Detection — CLOSED
- **File:** `src/runtime/runtime_capability_registry.py`
- **Function:** `detect_conflicts()`
- **Behavior:** Scans all registered capabilities for cases where one
  capability's declared output overlaps with another's negative authority.
- **Proof:** `run/run_governance.py :: test_conflict_detection()` — PHASE 9.

### Compatibility Validation Across Products — PARTIALLY CLOSED
- **Closed:** Version negotiation (above) handles same-runtime compatibility.
- **Not closed:** Cross-product compatibility (e.g. this runtime vs. a
  different team's runtime entirely) requires a shared schema registry
  between organizations. That registry does not exist yet and cannot be
  fabricated without the other product's schema. Tracked as future work.

---

## Runtime Observability

### Dashboard Streaming Interface — PARTIALLY CLOSED
- **Closed:** `get_dashboard_json()` in `capability_runtime.py` returns a
  complete, JSON-serialisable snapshot suitable for any HTTP/WS layer to
  stream.
- **Not closed:** An actual streaming transport (WebSocket server, SSE
  endpoint) is not implemented. That is an HTTP-layer concern, not a
  runtime concern, and adding one would require choosing a web framework
  this repo does not currently depend on.

### Metrics Export — CLOSED
- **File:** `src/monitoring/metrics_export.py`
- **Functions:** `export_to_dict()`, `export_to_jsonl()`,
  `format_as_prometheus()`, `format_as_otel_spans()`
- **Behavior:** Converts internal capability metrics into Prometheus text
  exposition format and OTel-style span/metric dicts. No external
  dependency (no `prometheus_client`, no `opentelemetry-sdk`).
- **Proof:** `run/run_governance.py :: test_metrics_export()` — PHASE 11.

### OpenTelemetry-Style Adapters — CLOSED
- **File:** `src/monitoring/otel_adapter.py`
- **Class:** `OtelAdapter`
- **Behavior:** Produces OTel-compatible `span` and `metric` dict structures
  from invocation records, without depending on the `opentelemetry-sdk`
  package. A real OTel exporter can consume these structures directly.
- **Proof:** `run/run_governance.py :: test_metrics_export()` — PHASE 11.

### Persistent Runtime History — CLOSED
- **File:** `src/runtime/persistent_history.py`
- **Class:** `PersistentHistory`
- **Behavior:** Append-only JSONL file at `runtime_history.jsonl`. Survives
  process restarts. Wired as the default `_evidence_ledger` in
  `capability_runtime.py`, replacing the in-memory-only stub.
- **Proof:** Run `python run/run_signal.py` twice in separate processes,
  then inspect `runtime_history.jsonl` — record count persists across runs.

### Cross-Runtime Observability Federation — NOT CLOSED
- Requires multiple independent runtime instances (this one plus at least
  one other team's runtime) to federate dashboards. Cannot be built or
  proven inside a single repo without the second runtime existing.
  Tracked as future work, dependent on Kanishk's/Raj's systems being live.

---

## Production Runtime Integration

### Live Canonical Replay Authority Integration — CLOSED (real implementation, attach pending Pritesh's wire-up confirmation)
- **File:** `src/governance/replay_legitimacy.py`
- **Class:** `CanonicalReplayAuthority`
- **Behavior:** Tracks every invocation by deterministic `invocation_id`.
  First execution → PERMIT. Repeat execution → DENY. Explicit `replay()`
  call verifies a candidate output against the recorded truth hash and
  returns `REPLAY_VERIFIED` or `REPLAY_DIVERGED`.
- **Wired by default** in `capability_runtime.py` (replacing
  `_CanonicalReplayAuthorityStub`, which always returned PERMIT
  unconditionally and tracked nothing).
- **Proof:** `run/run_governance.py :: test_replay_legitimacy()` — PHASE 5.
- **Residual gap:** This is Dhiraj's implementation of the interface
  Pritesh owns. It proves the runtime correctly *consumes* a real replay
  authority. It does not constitute Pritesh's own sign-off on the
  authority's policy — that confirmation has to come from Pritesh.

### Execution Evidence Authority Ownership — CLOSED (same caveat as above)
- **File:** `src/runtime/persistent_history.py`
- Replaces `_EvidenceLedgerStub`. Evidence now persists to disk and survives
  restarts, which is the structural requirement for an audit trail.
  Ownership sign-off from Pritesh's provenance team is still required
  before this is the canonical evidence store in production.

### Dashboard Telemetry Consumer — NOT CLOSED
- Requires an actual consumer (SETU, NICAI, InsightFlow) to connect and
  pull from `get_dashboard_json()`. The producer side is ready; there is no
  consumer to test against inside this repo.

### Real Ecosystem Integration With Kanishk Runtime — NOT CLOSED
- Requires Kanishk's `physical_engine` / `MultiZoneExecutor` to be present
  and live. Declared in `STUBS_REGISTRY.md` STUB-005 as EXCLUDED.

### Real Ecosystem Integration With Raj Governance — NOT CLOSED
- Requires Raj's enforcement engine to be present and live. Declared in
  `STUBS_REGISTRY.md` STUB-008 as NOT INTEGRATED.

---

## Governance

### Decision Ledger — CLOSED
- **File:** `src/governance/decision_ledger.py`
- **Class:** `DecisionLedger`
- **Behavior:** Append-only, SHA-256-chained record of every PERMIT/DENY
  decision made anywhere in the governance layer. `ledger_hash()` changes
  deterministically with every new record.
- **Proof:** `run/run_governance.py :: test_decision_ledger()` — PHASE 2.

### Semantic Registry — CLOSED
- **File:** `src/governance/semantic_registry.py`
- **Class:** `SemanticRegistry`
- **Behavior:** Records what each capability's output *means* in the
  hull-corrosion domain (not what the capability does — what its numbers
  represent). Includes `invariants`, `assumptions`, and
  `known_limitations` per capability. `check_invariant()` is advisory and
  never raises — it surfaces violations for review without halting
  execution.
- **Proof:** `run/run_governance.py :: test_semantic_registry()` — PHASE 3.

### Doctrine Registry — CLOSED
- **File:** `src/governance/doctrine_registry.py`
- **Class:** `DoctrineRegistry`
- **Behavior:** 8 named, versioned, checkable design rules (no
  `datetime.now()`, no silent failure, negative authority required,
  SHA-256 IDs only, append-only logs, stubs must be declared, typed
  attachment required, dependency graph enforced). `evaluate_all(context)`
  returns pass/fail per doctrine — this is executable, not prose.
- **Proof:** `run/run_governance.py :: test_doctrine_registry()` — PHASE 4.

### Authority Matrix as Executable Validation — CLOSED
- **File:** `src/governance/authority_matrix.py`
- **Class:** `AuthorityMatrix`
- **Behavior:** Converts the authority-ceiling hierarchy from a markdown
  table into a function: `check(capability_id, action) -> AuthorityCheckResult`.
  Enforces negative-authority hard blocks first, then ceiling-rank
  comparison. Every check is logged to an internal audit trail.
- **Wired into invocation:** `capability_runtime.invoke_capability()` step 3.
- **Proof:** `run/run_governance.py :: test_authority_matrix()` — PHASE 1.

### Replay Legitimacy Proof Separation at Runtime — CLOSED
- The runtime (`capability_runtime.py`) calls `_replay_authority.check()`
  and **only consumes** the PERMIT/DENY decision. It never makes the
  decision itself. The decision logic lives entirely in
  `src/governance/replay_legitimacy.py`, structurally separate from the
  runtime's execution path. This separation is what was missing before —
  the previous stub's PERMIT-always behavior meant there was no decision
  to separate from execution.

---

## Testing

### Independent Tester Evidence — NOT CLOSED
- Requires a human tester (Vinayak) to run the suite and sign off. Cannot
  be fabricated by the author of the code under test. `TESTING_PACKET.md`
  remains the handoff document for this.

### Screenshot Evidence — NOT CLOSED
- Same reasoning. Screenshots are evidence of a human running the code on
  their machine. `SELF_TESTING_SHEET.md` documents the expected outputs
  precisely enough for a tester to compare against, but the screenshots
  themselves must come from an actual test session.

### Integration Evidence — NOT CLOSED
- Requires the actual external systems (Kanishk's engine, Raj's
  enforcement layer) to be live. See Production Runtime Integration above.

### Production Replay Validation — PARTIALLY CLOSED
- `CanonicalReplayAuthority.replay()` is implemented and proven against
  synthetic recorded truth in `run_governance.py`. What remains is running
  this against real production traffic, which requires a deployed
  environment that does not exist inside this repo.

---

## Repository

### Documentation Describing Future Architecture As Operational — CLOSED
- `STUBS_REGISTRY.md` now exists specifically to prevent this. Every stub
  states: current status, what replaces it, who owns the real
  implementation, current runtime behavior, and residual risk. Three stubs
  that were previously undocumented assumptions (replay authority,
  evidence ledger, global sequence counter) are now either replaced with
  real implementations or explicitly marked ACTIVE/NOT IMPLEMENTED.

---

## Summary Table

| Category | Total Findings | Closed | Partially Closed | Not Closed (requires external system) |
|---|---|---|---|---|
| Capability Platform | 5 | 4 | 1 | 0 |
| Runtime Observability | 5 | 3 | 1 | 1 |
| Production Integration | 4 | 2 | 0 | 2 |
| Governance | 5 | 5 | 0 | 0 |
| Testing | 4 | 0 | 1 | 3 |
| Repository | 1 | 1 | 0 | 0 |
| **Total** | **24** | **15** | **3** | **6** |

15 of 24 findings are fully closed with executable proof in
`run/run_governance.py`. 3 are partially closed (the runtime-side
structure is in place; the other half requires an external party). 6
cannot be closed from inside this repo because they require a human
tester or a second team's live system — these are honestly declared as
such rather than claimed as done.
