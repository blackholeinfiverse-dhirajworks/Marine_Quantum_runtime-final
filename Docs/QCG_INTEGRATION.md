# QCG Integration — Marine Quantum Runtime

Marine Runtime exposes QCG-compatible endpoints **inside this repository only**.
QCG (`web_server.py`) is an external system and is never modified. Marine reads
QCG's request/response contract and mirrors it.

**Backend truth classification:** `SIMULATED AND TESTED` — Qiskit AerSimulator
(provider `aer`, backend `aer_simulator`). Physical QPU execution has **not**
been verified and is never claimed.

## Endpoints (all require `X-API-Key`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/hybrid/dispatch` | QCG `CapabilityDispatchRequest` → QCG `InvocationResult` |
| POST | `/hybrid/submit` | QCG `HybridSubmitRequest` → QCG `InvocationResult` |
| POST | `/api/v1/quantum/execute` | Existing direct execution endpoint (unchanged behavior) |
| GET | `/api/v1/quantum/backend`, `/api/v1/quantum/calibration` | Backend identity / calibration status |

Operations on `/hybrid/dispatch`: `hybrid_submit` (circuit execution),
`health_check`, `list_providers`. Anything else → `status: "SERVICE_NOT_FOUND"`
(HTTP 404). `network_status` is **not** implemented (QCG's network-coordination
contract is not part of Marine).

## Accepted request

`POST /hybrid/dispatch` — field names and defaults mirror QCG:

```json
{
  "service_id": "QCG-HYBRID-RUNTIME",
  "operation": "hybrid_submit",
  "version": "1.0.0",
  "invocation_id": "a7b2dfe8-433e-43eb-9044-da445803f9a9",
  "payload": {
    "workload_id": "wl-001",
    "workload_type": "SIMULATION",
    "problem_size": 3,
    "num_qubits": 3,
    "shots": 1024,
    "seed": 42,
    "gate_sequence": [
      {"gate": "h",  "qubits": [0]},
      {"gate": "cx", "qubits": [0, 1]},
      {"gate": "cx", "qubits": [1, 2]}
    ]
  }
}
```

**Circuit fields (Marine-defined — QCG does not specify a circuit schema):**
`num_qubits` (1–29), `gate_sequence`, optional `shots` (100–100000, default
4096), `seed` (default 42), `preferred_provider`. These map 1:1 onto the existing
`CircuitExecuteRequest`.

**QCG metadata fields (accepted, echoed in `response.request_metadata`):**
`workload_id`, `workload_type`, `problem_size`, `is_qubo_compatible`,
`requires_entanglement`, `requires_live_hardware`, `classical_fallback_acceptable`.
Only `requires_live_hardware` affects execution: `true` → hardware is required,
the simulator is NOT used, and (since no hardware is verified) the call fails
honestly.

Any other key is **not interpreted** and is listed in `response.ignored_fields`.
QUBO / abstract workloads without `num_qubits` + `gate_sequence` are rejected with
a `FAILED` result — Marine does not compile them.

> **Open item:** this payload shape is a Marine-owned initial contract. It has
> not been checked against a real request from Ganesh's adapter or QCG. Share one
> real sample before treating the schema as final.

`POST /hybrid/submit` takes QCG's `HybridSubmitRequest`
(`workload` + `workload_type`, `problem_size`, `is_qubo_compatible`,
`requires_entanglement`, `requires_live_hardware`, `classical_fallback_acceptable`).

## Response (QCG `InvocationResult`, exactly nine keys)

`invocation_id, service_id, operation, status, response, duration_ms,
trust_method, evidence, error`. (`retry_count` / `timestamp` are added by QCG's
SDK, not by the server, so Marine does not emit them.)

Captured from a local run against AerSimulator:

```json
{
  "invocation_id": "a7b2dfe8-433e-43eb-9044-da445803f9a9",
  "service_id": "QCG-HYBRID-RUNTIME",
  "operation": "hybrid_submit",
  "status": "SUCCESS",
  "response": {
    "trace_id": "a7b2dfe8-433e-43eb-9044-da445803f9a9",
    "classification": "QUANTUM_SIMULATED",
    "execution_path": "SIMULATED",
    "execution_environment": "SIMULATOR",
    "is_simulator": true,
    "physical_qpu_execution_verified": false,
    "provider_id": "aer",
    "backend_name": "aer_simulator",
    "measurement_counts": {"000": 490, "111": 534},
    "confidence": null,
    "result_hash": "ff8495e6…83000",
    "bhex_ready": null,
    "provenance_available": false,
    "request_metadata": {"workload_type": "SIMULATION", "problem_size": 3,
      "is_qubo_compatible": false, "requires_entanglement": false,
      "requires_live_hardware": false, "classical_fallback_acceptable": true},
    "ignored_fields": [],
    "marine_execution_result": { "...": "full /api/v1/quantum/execute body incl. instrumentation" }
  },
  "duration_ms": 12.3,
  "trust_method": "CLASSICAL",
  "evidence": {
    "trace_id": "a7b2dfe8-433e-43eb-9044-da445803f9a9",
    "execution_id": "EXEC-024FFC371911",
    "classification": "QUANTUM_SIMULATED",
    "execution_path": "SIMULATED",
    "backend_name": "aer_simulator",
    "result_hash": "ff8495e6…83000",
    "provenance_available": false
  },
  "error": null
}
```

### Labeling rules (QCG vocabulary)

| Situation | `classification` | `execution_path` | `trust_method` |
|---|---|---|---|
| Ran on AerSimulator | `QUANTUM_SIMULATED` | `SIMULATED` | `CLASSICAL` |
| Succeeded but backend not positively identified as a simulator | `UNVERIFIED` | `UNVERIFIED` | `CLASSICAL` |
| Failed / rejected / timed out (nothing usable executed) | `CLASSICAL` | `BLOCKED` | `CLASSICAL` |

Marine **never** emits `QUANTUM_LIVE` or `HYBRID` trust. `UNVERIFIED` is not a QCG
enum value; it is used deliberately instead of guessing. `evidence` carries only
what Marine can attest (trace ID, execution ID, classification, backend, SHA-256
of the counts). `merkle_root` / `evidence_chain_head` are omitted — Marine has no
evidence ledger.

### `status` and HTTP codes

| `status` | HTTP | When |
|---|---|---|
| `SUCCESS` | 200 | executed |
| `FAILED` | 422 | invalid workload / structural circuit error |
| `FAILED` | 503 / 500 | backend unavailable, execution failed, internal error |
| `TIMEOUT` | 504 | exceeded `QCG_ADAPTER_TIMEOUT_SECONDS` |
| `SERVICE_NOT_FOUND` | 404 | unknown `operation` |

Auth failures return the standard `401` JSON (`{"status","detail","trace_id"}`),
not an `InvocationResult`. **Note:** QCG's own server returns HTTP 200 for every
`InvocationResult`; Marine uses real HTTP codes. Confirm QCG's SDK handles
non-2xx responses the way you expect.

## Trace ID

Precedence: valid `X-Trace-ID` header → valid `invocation_id` → generated UUID4.
The effective ID is returned in the `X-Trace-ID` response header,
`evidence.trace_id`, `response.trace_id`, the nested execution result and every
log line (`[trace_id=...]`). `invocation_id` is always echoed unchanged. IDs must
match `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`; a malformed *header* returns 400, a
malformed `invocation_id` is echoed but not adopted as the trace ID.

## Timeout behavior (read this)

Each `hybrid_submit` runs in a worker thread (pool size
`QCG_ADAPTER_MAX_WORKERS`). If it exceeds `QCG_ADAPTER_TIMEOUT_SECONDS` (default
**25**) the caller receives `status: "TIMEOUT"` (HTTP 504) with the trace ID and
**no result**; it is never reported as a success. **Aer cannot be cancelled once
running**, so the run may continue in the background until it finishes; its
result is discarded (`response.background_execution` says
`MAY_STILL_BE_RUNNING`, or `CANCELLED_BEFORE_START` if it never started). A
`TIMEOUT` record is added to the instrumentation log; when the background run
finishes it appends its own final record with the same `execution_id`. A
timed-out job occupies a worker until it ends, which is why the pool is bounded.

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `RUNTIME_API_KEY` | **yes** | — | `X-API-Key` for all protected endpoints. Never hardcoded or logged. |
| `QCG_ADAPTER_TIMEOUT_SECONDS` | no | `25` | Per-request timeout. Invalid / non-positive values fall back to 25. |
| `QCG_ADAPTER_MAX_WORKERS` | no | `4` | Worker threads for adapter executions. |
| `LOG_LEVEL`, `ALLOWED_ORIGINS`, `IBM_QUANTUM_TOKEN`, `IONQ_API_KEY` | no | — | Unchanged. |

QCG's README lists Marine's `X-API-Key` as externally blocked, i.e. QCG does not
hold it. Hand the key to the QCG operators out-of-band; do not commit it.

## Deploy (Render)

1. Replace `api_server.py` in the GitHub repo; add `tests/test_qcg_adapter.py` and
   `docs/QCG_INTEGRATION.md`. No new dependencies.
2. Confirm `RUNTIME_API_KEY` is set in Render → Environment (optionally the two
   `QCG_ADAPTER_*` variables).
3. Manual Deploy → Deploy latest commit. Start command is unchanged:
   `uvicorn api_server:app --host 0.0.0.0 --port $PORT`.
4. Smoke test (replace `$KEY`):

```bash
BASE=https://marine-quantum-runtime-final.onrender.com
curl -s -X POST $BASE/hybrid/dispatch \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" -H "X-Trace-ID: BHQ-TEST-001" \
  -d '{"service_id":"QCG-HYBRID-RUNTIME","operation":"hybrid_submit","invocation_id":"inv-001",
       "payload":{"num_qubits":3,"shots":1024,"seed":42,"gate_sequence":[
         {"gate":"h","qubits":[0]},{"gate":"cx","qubits":[0,1]},{"gate":"cx","qubits":[1,2]}]}}'
```

Expect `status: "SUCCESS"`, `classification: "QUANTUM_SIMULATED"`,
`evidence.trace_id: "BHQ-TEST-001"`, and the `X-Trace-ID` response header.
The first call after idle may take 30–60 s (Render cold start).

## Tests

```bash
pip install pytest httpx
pytest tests/test_qcg_adapter.py -v
```

34 tests: success and response shape, workload→circuit mapping, trace ID
precedence/generation/concurrency, invalid requests, authentication (and that the
key never appears in responses or logs), timeout, simulator-vs-hardware labeling,
and a regression check that `/api/v1/quantum/execute` is unchanged. One test runs
the real pipeline and is skipped if `qiskit-aer` is not installed.

## Not implemented / not verified

- QCG orchestration, QUBO solving, `network_status`, evidence-ledger / Merkle proofs.
- Physical QPU execution and calibration (`BLOCKED` — no hardware verified).
- End-to-end test with a real QCG instance or Ganesh's adapter.
