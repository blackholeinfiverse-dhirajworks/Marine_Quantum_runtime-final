
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

---

## [QCG Integration + REST API Sprint] — July 2026
**Author:** Dhiraj Chavan

### Context
QCG ecosystem integration request received. The requesting developer assumed the
runtime was a deployed HTTP service. This sprint:
1. Adds an HTTP REST wrapper (`api_server.py`) with Swagger auto-generation
2. Writes a comprehensive integration guide for all QCG integration paths
3. Documents all 5 bugs found during code review with executable reproduction cases
4. Provides a standalone 26-endpoint API test suite for independent validation

### Added
- `api_server.py` — FastAPI REST wrapper, 18 endpoints, 26-test suite, 26/26 passing
- `tests/test_api_endpoints.py` — Standalone API test suite (no HTTP server needed)
- `INTEGRATION_GUIDE.md` — Python + HTTP integration reference; all code examples live-validated
- `BUG_REPORT.md` — 5 confirmed bugs with minimal executable reproductions
- `QCG_DEVELOPER_REPLY.md` — Structured developer reply addressing the integration request
- `.env.example` — All environment variable documentation
- `Makefile` — `make verify`, `make serve`, `make test`, `make test-api`
- `Dockerfile` — Multi-stage: `core` (stdlib + FastAPI) and `quantum` (+ Aer)
- `docker-compose.yml` — One-command containerised deployment

### Bugs Fixed (all pre-existing, all confirmed with executable reproduction)
- BUG-001: `TypeError` crash on `None` upper bound in `typed_attachment.py`
- BUG-002: `FileNotFoundError` from `os.makedirs("")` in `persistent_history.py`
- BUG-003: JSON canonicalization mismatch causing false `REPLAY_DIVERGED` verdicts
- BUG-004: Global sequence counter shared across capabilities (cross-contamination)
- BUG-005: Authority action conflation blocking all `signal` executions (AUTHORITY_DENIED)
- BUG-006 (new): Unknown module names returning HTTP 500 instead of 404 in `api_server.py`

### Test Results
| Suite | Tests | Result |
|---|---|---|
| `run_signal.py` | Determinism + failure cases | ✅ PASS |
| `run_quantum_pipeline.py` | Determinism + failure cases | ✅ PASS |
| `run_distributed_qapp.py` | Propagation + replay + shuffle | ✅ PASS |
| `run_operational_drift.py` | Drift detection + determinism | ✅ PASS |
| `run_governance.py` | 46 governance checks | ✅ 46/46 |
| `run_ecosystem_integration.py` | 33 integration checks | ✅ 33/33 |
| `tests/test_api_endpoints.py` | 26 HTTP endpoint tests | ✅ 26/26 |
