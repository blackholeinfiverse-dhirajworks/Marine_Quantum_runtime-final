# Docs/TESTING_GUIDE.md
# Testing Guide — Quantum Runtime Capability
**Author:** Dhiraj Chavan | Marine Intelligence System | July 2026

---

## Quick Start (Vinayak)

```bash
# Install Aer (enables real quantum simulation checks)
pip install qiskit qiskit-aer --break-system-packages

# Run the ecosystem integration proof
python run/run_ecosystem_integration.py
```

Expected: exit code 0, `33 / 33` checks passed.

---

## Full Test Suite

Run all six entry points in order. All must exit 0.

```bash
python run/run_signal.py              # 6 checks  — Signal generator, determinism
python run/run_quantum_pipeline.py    # 3 checks  — HEA circuit, quantum output
python run/run_distributed_qapp.py    # 7 phases  — Distributed propagation, consensus
python run/run_operational_drift.py   # 4 phases  — Drift detection, observability
python run/run_governance.py          # 46 checks — Authority, ledger, doctrines, replay
python run/run_ecosystem_integration.py # 33 checks — Full ecosystem integration
```

---

## What Each Test Phase Proves

### run_ecosystem_integration.py phases

| Phase | What it proves |
|---|---|
| 7.1 Provider switching | `local_simulator` and `aer` both execute same circuit. New provider registered at runtime, zero file changes. |
| 7.2 Backend failover | IBM + IonQ both honestly unavailable; failover attempt audit trail present; no fake success. |
| 7.3 Determinism | 5 identical runs on `local_simulator` (stdlib), 5 identical runs on `aer` (real qiskit-aer), each byte-identical. |
| 7.4 Sim vs hardware | Hardware path fails with explicit honest reason, not fake data. |
| 7.4b Production readiness | Limits enforce, noise profiles correct, hardware constraints correct, identical output schemas from both backends. |
| 7.5 Benchmark | 10-run avg/min/max for both real backends. Local sim ~0.04ms, Aer ~91ms. |
| 7.6 Failure injection | Impossible qubit count fails cleanly; subsequent valid job recovers. |
| 7.7 Distributed execution | 9 jobs across 3 nodes, all 3 nodes used, all 9 completed. |
| 7.8 Federation | Nothing attached → fail closed. Reference authority attached → success, evidence persisted. |
| 7.9 Replay verification | Identical payload → REPLAY_VERIFIED. Tampered payload → REPLAY_DIVERGED. |
| 7.10 Observability | All 7 v2 sections produced. All 6 dashboard telemetry feeds produced from real data. |

---

## Independent Validation Steps (for Vinayak)

1. **Clone the repo fresh** — do not use anyone else's working copy.
2. `pip install qiskit qiskit-aer --break-system-packages`
3. `python run/run_ecosystem_integration.py` — expect exit 0.
4. Capture your terminal output as a screenshot.
5. Check: does the GHZ circuit produce non-zero counts for both `000` and `111`?
   This confirms real Aer execution, not a fake classical output.
6. Check Phase 7.3: are the 5 `aer` runs truly identical? They must be — same
   seed means same qiskit-aer output.
7. Check Phase 7.8: does the "nothing attached" test return `REPLAY_DENIED`?
   This proves fail-closed behavior.

---

## Adding a New Provider — Test Procedure

1. Write `src/quantum/providers/your_provider.py` implementing
   `QuantumExecutionProvider` + `QuantumExecutionBackend`.
2. Add `provider_registry.register_provider(YourProvider())` to
   `provider_registry._bootstrap()`.
3. Run `python run/run_ecosystem_integration.py` — all existing 33 checks
   must still pass (no regressions from adding a provider).
4. Add a provider-specific check to Phase 7.1 to prove your backend executes.

---

## Known Test Environment Limitations

- IBM and IonQ providers will always report `CREDENTIALS_REQUIRED` or
  `NETWORK_UNREACHABLE` in this sandbox. This is expected and correct.
- No real quantum hardware is reachable. Phase 7.4 proves this is honestly
  declared, not faked.
- `runtime_history.jsonl` (persistent evidence log) is created in the repo
  root on first run and appended to on subsequent runs. Add it to `.gitignore`.
  It is already in `.gitignore` in this repo.

---

## Determinism Contract

These outputs are **always identical** for the same seed:

| Component | Seed mechanism |
|---|---|
| `local_simulator` | `random.Random(seed)` — pure Python |
| `aer` (qiskit-aer) | `seed_simulator=seed` in all three injection points |
| Signal generator | `anchor + (iterations × 60s)` — no datetime.now() |
| Invocation IDs | `SHA-256(canonical(payload))` — deterministic |
| Decision ledger hashes | SHA-256 chain from deterministic inputs |

If any of these ever produce non-identical output for the same input and seed,
it is a regression. File a bug.
