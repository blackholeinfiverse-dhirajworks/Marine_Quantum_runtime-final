# KNOWN_LIMITATIONS.md
# Quantum Runtime Capability — Ecosystem Integration
# Marine Intelligence System | BHIV Core

**Author:** Dhiraj Chavan
**Date:** June 2026

This document exists because the ecosystem brief states: "Architecture
documentation is no longer sufficient. Executable integration proof is now
mandatory." Every claim below is either backed by a passing test in
`run/run_ecosystem_integration.py` (exit 0, 24/24 checks) or explicitly
marked as not provable from this environment, with the reason stated.

---

## What Is Genuinely Real (Executable Proof Exists)

| Claim | Proof |
|---|---|
| Provider abstraction is real, not documentation | `run_ecosystem_integration.py` Phase 7.1 — registers a 5th provider (`rigetti`, fictional, for the test only) at runtime and routes to it with zero changes to `provider_registry.py`, `quantum_execution_router.py`, or `base.py` |
| Aer provider genuinely executes quantum circuits | `qiskit==2.4.2` and `qiskit-aer==0.17.2` are installed and imported live. A 3-qubit GHZ circuit run through `AerSimulator` produces a real entangled-state distribution (`{'000': ~490, '111': ~534}` out of 1024 shots) — not a fabricated number |
| Determinism holds across both real backends | 5 identical runs on `local_simulator` and 5 identical runs on `aer` (real qiskit-aer), same seed, byte-identical output each time |
| Distributed routing across multiple nodes | 9 jobs submitted to a 3-node `DistributedRuntimeManager`; all 3 nodes used via round-robin; all 9 completed |
| Retry policy is genuinely exercised | A job requiring real hardware retries `max_retries+1` times against IBM/IonQ (both honestly unavailable), then fails with the retry count logged in the event stream — not silently swallowed |
| Federation fails closed | `FederationRuntime()` with nothing attached returns `REPLAY_DENIED` for every execution attempt — the runtime never self-authorizes |
| Federation succeeds against reference implementations | The same `FederationRuntime`, with the governance-sprint's `CanonicalReplayAuthority` and `PersistentHistory` attached, executes successfully and persists evidence to disk |
| Replay verification distinguishes identical vs tampered output | `REPLAY_VERIFIED` for byte-identical replay, `REPLAY_DIVERGED` for tampered replay — both proven in the same test run |
| Observability v2 and dashboard telemetry produce real data | Built from actual job results and event logs from a real `DistributedRuntimeManager` run, not synthetic placeholder data |

---

## What Is Structurally Complete But Cannot Execute From This Sandbox

These are not stubs in the sense of "fake output." They correctly implement
the `QuantumExecutionProvider` interface, correctly report their own
unavailability, and raise explicit, honest exceptions rather than returning
fabricated results.

| Component | Why it cannot run here |
|---|---|
| IBM Runtime provider (`ibm_runtime_provider.py`) | Requires `qiskit-ibm-runtime` SDK, an `IBM_QUANTUM_TOKEN`, and network egress to IBM's cloud API. None of the three are available in this sandbox. `health()` reports `CREDENTIALS_REQUIRED` or `NETWORK_UNREACHABLE` truthfully |
| IonQ provider (`ionq_provider.py`) | Requires an `IONQ_API_KEY` and network egress to IonQ's cloud API. Same posture as IBM — honest unavailability, not fake data |
| Real quantum hardware execution (any provider) | No real QPU is reachable from this environment under any circumstance |
| Simulation-vs-hardware comparison (Phase 7.4) | Cannot be performed — there is no hardware result to compare against. The test proves the code paths exist and share an interface, not that hardware execution succeeds |
| Performance benchmark | Measures **local classical simulation timing only** (`local_simulator`: ~0.04ms avg, `aer`: ~91ms avg per circuit). This is NOT a hardware benchmark and must never be represented as one |

---

## What Cannot Be Closed From Inside This Repository At All

These require systems and people outside this codebase. No amount of code
in this repo can close them.

| Item | Why |
|---|---|
| Live federation with Kanishk's actual deployed execution engine | His engine is not running anywhere reachable from this environment. `FederationRuntime` is proven against reference implementations only — swapping to his real engine is a constructor argument away, not a code change, but the swap itself requires his system to exist and be reachable |
| Live federation with Pritesh's actual deployed quantum platform | Same reasoning. The provider abstraction is designed so his platform could be registered as a 5th provider with zero runtime changes — proven structurally in this sprint, not against his real system |
| Live execution governance with Raj's actual enforcement service | `FederationRuntime` consumes a replay authority via dependency injection and fails closed without one. It does not, and should not, implement governance logic itself |
| Independent tester evidence (Vinayak) | Requires a human running the test suite independently and signing off. This sprint produces the deterministic test suite (`run_ecosystem_integration.py`) for Vinayak to run, but cannot produce his sign-off itself |
| Screenshot evidence | This environment has no GUI and no screenshot-capture tool. `review_packets/screenshots/` contains raw console capture (`.txt`) of every test run instead, with a README explaining this substitution honestly. These are not a replacement for actual screenshots — running the scripts locally and capturing real screenshots is still required for the deliverable as literally specified |
| Cross-runtime testing with Kanishk, quantum provider testing with Pritesh | Both require coordinated test runs against systems that exist outside this repository |

---

## Architectural Decisions Worth Flagging

1. **Distributed routing is in-process, not networked.** `DistributedRuntimeManager` simulates N nodes as Python objects in one process, exactly the same honest pattern as the existing `Node_A/B/C` propagation layer from Task 9. There is no real network transport, no real partition tolerance, no real Byzantine fault handling. This is declared, not hidden.

2. **The `rigetti` provider used in the "zero runtime change" proof is fictional and test-only.** It is not registered in the production bootstrap (`provider_registry._bootstrap()`), only constructed inline inside the test to demonstrate the extension point works.

3. **`allow_re_execution=True` vs `False` on `CanonicalReplayAuthority`.** Tests use both modes depending on what's being proven. Production deployments should default to `False` (fail closed on repeat execution) per the governance-sprint's original guidance — this has not changed.

4. **Federation clients buffer locally when nothing is attached, except replay authority, which fails closed.** This is intentional asymmetry: evidence/provenance/timeline data should not be lost just because an external sink isn't attached yet, but execution permission must never be self-granted.

---

## What Would Be Required To Close The Remaining Gaps

| Gap | Required action |
|---|---|
| Real IBM execution | Install `qiskit-ibm-runtime`, set `IBM_QUANTUM_TOKEN`, run from an environment with egress to IBM's cloud API |
| Real IonQ execution | Set `IONQ_API_KEY`, run from an environment with egress to IonQ's cloud API |
| True live federation | Kanishk's and Pritesh's systems need to expose the interfaces this repo's clients already expect (`check()` for replay authority, `append()` for evidence/ledger, `record()` for provenance) — at that point, attaching them is a single constructor call, proven by the reference-implementation tests in this sprint |
| Real distributed network transport | Replace `DistributedRuntimeManager`'s in-process node objects with a real message queue or RPC layer — the job lifecycle/queue/retry logic is already separated from the transport, so this is a transport-layer swap, not a redesign |
| Independent testing sign-off | Vinayak runs `run_ecosystem_integration.py` independently and confirms exit code 0 + captures real screenshots |
