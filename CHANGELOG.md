
---

## [Gap Closure Sprint] — Governance, Observability, Registry Hardening
**Date:** June 2026
**Author:** Dhiraj Chavan

### Added
- `src/governance/` — new layer: authority_matrix.py, decision_ledger.py, semantic_registry.py, doctrine_registry.py, replay_legitimacy.py
- `src/runtime/sequence_registry.py` — per-capability isolated sequence counters
- `src/runtime/persistent_history.py` — JSONL append-only evidence log, survives restart
- `src/contracts/typed_attachment.py` — type + bounds validation, not key-presence only
- `src/monitoring/metrics_export.py` — dict, JSONL, Prometheus text export
- `src/monitoring/otel_adapter.py` — OpenTelemetry-compatible spans/metrics/gauges, no otel-sdk dependency
- `run/run_governance.py` — 46 executable checks proving every gap-closure item
- `STUBS_REGISTRY.md` — honest declaration of every stub: what it replaces, owner, risk
- `Review_packets/task_gap_closure_review.md` — full accounting against prior review findings

### Changed
- `src/runtime/runtime_capability_registry.py` — added validate_dependency_graph(), negotiate_version(), detect_conflicts(), hot_attach(), hot_detach(); validate_attachment() now uses typed validation
- `src/runtime/capability_runtime.py` — real CanonicalReplayAuthority wired by default (was PERMIT-always stub); PersistentHistory wired by default (was in-memory-only stub); per-capability SequenceRegistry (was global shared counter); dependency graph and authority matrix checks added to invocation pipeline

### Fixed
- Global sequence counter bug: two different capabilities previously shared one seq namespace
- Attachment validation previously checked only key presence, not types or bounds
- Authority matrix action mismatch: `invoke_capability` action was being checked against a capability's right to execute itself, conflated with its right to orchestrate other capabilities. Split into `check_execution()` (primary action per capability) vs `invoke_other_capability` (orchestration).

### Honest Declarations
- Quantum circuit, physical hull engine, distributed network transport remain stubs — declared with owner and risk in `STUBS_REGISTRY.md`
- Governance pre-approval hook and enforcement engine integration not yet wired — declared as NOT IMPLEMENTED, not silently assumed
