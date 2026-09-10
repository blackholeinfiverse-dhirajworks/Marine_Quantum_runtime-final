# Integration Guide — Marine Quantum Runtime (QCG Ecosystem)

> **To the developer asking for Base API URL / Swagger / Auth headers:**  
> This runtime is a **Python library**, not a deployed HTTP service. There is no
> running web server, no `/api/v1/` endpoint, and no API key header — yet.
> Section 1 explains the Python integration path (what works today).
> Section 6 shows the REST wrapper path (what you'd add to expose HTTP endpoints).
> Both paths produce the same execution result; choose based on your architecture.

---

## Table of Contents

1. [Quick Start — Python Integration (Works Today)](#1-quick-start--python-integration)
2. [API Base URLs](#2-api-base-urls)
3. [Authentication](#3-authentication)
4. [Endpoints & Documentation](#4-endpoints--documentation)
5. [Core Integration Examples](#5-core-integration-examples)
6. [REST Wrapper — Exposing HTTP Endpoints](#6-rest-wrapper)
7. [Provider Configuration](#7-provider-configuration)
8. [Error Reference](#8-error-reference)
9. [Ecosystem Federation](#9-ecosystem-federation)
10. [Known Limitations & Open Stubs](#10-known-limitations)

---

## 1. Quick Start — Python Integration

### Prerequisites

```bash
# Minimum (stdlib only — signal, governance, distributed execution all work)
python --version   # 3.8+

# Recommended (enables real Aer quantum simulation)
pip install qiskit qiskit-aer

# Optional (for IBM Quantum real hardware — requires IBM_QUANTUM_TOKEN)
pip install qiskit-ibm-runtime

# Optional (if you want to expose HTTP endpoints — see Section 6)
pip install fastapi uvicorn
```

### Clone & Verify

```bash
git clone https://github.com/dhirajchavan-works/Marine-quantum-runtime.git
cd Marine-quantum-runtime

# Verify everything runs
python run/run_signal.py                # exit 0, determinism PASS
python run/run_governance.py            # exit 0, 46/46 checks
python run/run_ecosystem_integration.py # exit 0, 33/33 checks (requires qiskit)
```

### Minimum Working Integration (3 lines)

```python
import sys
sys.path.insert(0, "/path/to/Marine-quantum-runtime")

from invoke_runtime import invoke_runtime

result = invoke_runtime("signal", {
    "node_id":      "qnode_01",
    "energy_delta": 0.0001,
    "iterations":   120,
    "confidence":   0.92,
    "variance":     0.002,
})
print(result["status"])   # SUCCESS
print(result["result"])   # {"engine_event_version": "2.0", ...}
```

---

## 2. API Base URLs

> ⚠️ **Current state:** This runtime has no deployed HTTP server.
> The URLs below are placeholders for when a REST wrapper is added (see Section 6).

### Python Import Path (what exists today)

```python
# Local development — no URL, direct import
sys.path.insert(0, "[PATH_TO_REPO]")
from invoke_runtime import invoke_runtime
from src.runtime.capability_runtime import invoke_capability
from src.quantum.production_runtime import production_execute
```

### HTTP Base URLs (placeholders — populate when REST wrapper is deployed)

| Environment | Base URL | Status |
|-------------|----------|--------|
| **Local**   | `http://localhost:[INSERT_PORT_HERE]` | Not deployed — see Section 6 to run locally |
| **Staging** | `https://[INSERT_STAGING_HOST_HERE]/api/v1` | Not deployed |
| **Production** | `https://[INSERT_PRODUCTION_HOST_HERE]/api/v1` | Not deployed |

### Module Entry Points (Python API — available now)

| Module | Import path | Entry function |
|--------|-------------|----------------|
| Signal generator | `from invoke_runtime import invoke_runtime` | `invoke_runtime("signal", payload)` |
| Quantum pipeline | `from invoke_runtime import invoke_runtime` | `invoke_runtime("quantum_pipeline", payload)` |
| Distributed QApp | `from invoke_runtime import invoke_runtime` | `invoke_runtime("distributed_qapp", payload)` |
| Operational monitor | `from invoke_runtime import invoke_runtime` | `invoke_runtime("operational_monitor", payload)` |
| Capability platform | `from src.runtime.capability_runtime import invoke_capability` | `invoke_capability(capability_id, payload)` |
| Quantum production | `from src.quantum.production_runtime import production_execute` | `production_execute(circuit, requirements)` |

---

## 3. Authentication

### Current State

There is no authentication layer. The runtime is a library — calling code
is responsible for its own auth. No API key, no JWT, no OAuth token.

### When a REST wrapper is added (Section 6), recommended auth pattern:

```bash
# API Key in header (recommended for service-to-service)
curl -H "X-API-Key: [INSERT_API_KEY_HERE]" \
     https://[INSERT_HOST_HERE]/api/v1/signal

# Bearer JWT (if user-facing auth is added)
curl -H "Authorization: Bearer [INSERT_JWT_TOKEN_HERE]" \
     https://[INSERT_HOST_HERE]/api/v1/signal
```

### Ecosystem credentials (provider-specific, not runtime auth)

```bash
# IBM Quantum — set before running quantum_pipeline with real hardware
export IBM_QUANTUM_TOKEN="[INSERT_IBM_TOKEN_HERE]"

# IonQ — set before running quantum_pipeline with IonQ backends
export IONQ_API_KEY="[INSERT_IONQ_KEY_HERE]"
```

Neither of these is required for local simulation (AerSimulator or the
stdlib local simulator). Both providers fail closed with `CREDENTIALS_REQUIRED`
if the env var is not set — no silent fake execution.

---

## 4. Endpoints & Documentation

### OpenAPI / Swagger

> **Not available** — no HTTP server exists yet.  
> Swagger URL placeholder: `[INSERT_SWAGGER_URL_HERE]`  
> (e.g. `http://localhost:8000/docs` if using FastAPI — see Section 6)

### Current Python API surface (canonical reference)

#### `invoke_runtime(module_name, payload) → dict`

The root gateway. Always returns:

```json
{
  "status":             "SUCCESS | FAILED | VALIDATION_ERROR | MODULE_NOT_FOUND",
  "module":             "<module_name>",
  "execution_id":       "<sha256_hex_64_chars>",
  "deterministic_hash": "<sha256_hex_64_chars>",
  "duration_ms":        0.0,
  "output":             { },
  "result":             { },
  "errors":             []
}
```

#### `invoke_capability(capability_id, payload) → dict`

Full capability platform stack (dependency check → authority check → typed
attachment validation → replay authority → execution → evidence → observability).

```json
{
  "status":             "SUCCESS | VALIDATION_ERROR | DEPENDENCY_ERROR | AUTHORITY_DENIED | REPLAY_DENIED | FAILED",
  "capability_id":      "signal",
  "invocation_id":      "<sha256_hex_64_chars>",
  "deterministic_hash": "<sha256_hex_64_chars>",
  "duration_ms":        0.0,
  "output":             { },
  "errors":             [],
  "replay_authority":   { "decision": "PERMIT | DENY" },
  "provenance_ref":     "<sha256_hex_64_chars>",
  "dependency_check":   { "valid": true },
  "authority_check":    { "permitted": true }
}
```

#### `production_execute(circuit, requirements, limits) → dict`

```json
{
  "status":               "SUCCESS | LIMIT_EXCEEDED | NO_BACKEND_AVAILABLE | EXECUTION_FAILED",
  "result":               {
    "provider_name":      "aer | local_simulator | ibm_runtime | ionq",
    "backend_name":       "<backend_id>",
    "measurement_counts": { "000": 490, "111": 534 },
    "shots_used":         1024,
    "is_simulator":       true,
    "seed":               42,
    "execution_time_ms":  91.2
  },
  "routing":              { "final_provider": "aer", "final_backend": "aer_simulator" },
  "execution_limits":     { },
  "provider_capabilities":{ },
  "errors":               []
}
```

---

## 5. Core Integration Examples

### Example A — Signal State Classification (Python)

```python
import sys
sys.path.insert(0, "/path/to/Marine-quantum-runtime")
from invoke_runtime import invoke_runtime

payload = {
    "node_id":      "qnode_01",   # string, non-empty
    "energy_delta": 0.0001,       # float >= 0.0
    "iterations":   120,          # int >= 0
    "confidence":   0.92,         # float in [0.0, 1.0]
    "variance":     0.002,        # float >= 0.0
}

result = invoke_runtime("signal", payload)

# result["status"] is always one of: SUCCESS, VALIDATION_ERROR, FAILED
if result["status"] == "SUCCESS":
    event = result["output"]
    transition = event["transition"]
    print(f"State: {transition['next']}")          # CONVERGED | SUSPENDED | DIVERGED
    print(f"Cause: {transition['cause']}")
    print(f"Sigma: {event['uncertainty_envelope']['sigma']}")
else:
    print(f"Error: {result['errors']}")
```

**Expected response (SUCCESS):**

```json
{
  "status": "SUCCESS",
  "module": "signal",
  "execution_id": "d3ad48e72f75957cbfd0dc7ab1699633...",
  "deterministic_hash": "42a8cbd540e0ad222116d84579addc81...",
  "duration_ms": 0.8,
  "output": {
    "engine_event_version": "2.0",
    "node_ref": "qnode_01",
    "transition": {
      "prev": "ACTIVE",
      "next": "CONVERGED",
      "cause": "confidence=0.92>=0.85, variance=0.002<=0.005, energy_delta=0.0001<=0.005",
      "seq": 1,
      "ts": "2026-01-01T02:00:00Z"
    },
    "uncertainty_envelope": {
      "confidence": 0.92,
      "sigma": 0.04472136
    }
  },
  "errors": []
}
```

**Validation error response:**

```json
{
  "status": "VALIDATION_ERROR",
  "module": "signal",
  "errors": ["Input validation failed (1 error(s)):\n  • Field 'confidence' = 1.5: must be a float in [0.0, 1.0]."]
}
```

---

### Example B — Quantum Corrosion Assessment (Python)

```python
result = invoke_runtime("quantum_pipeline", {
    "salinity":                    35.2,   # [0.0, 50.0] ppt
    "temperature_celsius":         18.5,   # [-5.0, 45.0] °C
    "pH":                          7.8,    # [0.0, 14.0]
    "material_oxidation_potential": 0.44,  # [-2.0, 2.0] V
    "dissolved_oxygen_mgl":        6.5,    # [0.0, 20.0] mg/L
    "current_density_mAcm2":       0.12,   # [0.0, 10.0] mA/cm²
})

if result["status"] == "SUCCESS":
    out = result["output"]
    event = out["deterministic_event"]
    print(f"Risk:   {event['risk_level']}")          # LOW|MODERATE|ELEVATED|CRITICAL
    print(f"Signal: {event['signal']}")              # HOLD | INCREASE_ANODE_CURRENT
    print(f"Degrad: {out['degradation_probability']}")
```

---

### Example C — Quantum Circuit (Production Execute, Python)

```python
from src.quantum.production_runtime import production_execute
from src.quantum.providers.base import CircuitSpec, BackendRequirements

# Define a 3-qubit GHZ circuit in provider-agnostic gate format
circuit = CircuitSpec(
    num_qubits=3,
    gate_sequence=[
        {"gate": "h",  "qubits": [0]},
        {"gate": "cx", "qubits": [0, 1]},
        {"gate": "cx", "qubits": [1, 2]},
    ],
    shots=4096,
    seed=42,
)

# Route to best available healthy backend (Aer if installed, else local_simulator)
result = production_execute(
    circuit,
    requirements=BackendRequirements(require_simulator=True),
)

if result["status"] == "SUCCESS":
    counts = result["result"]["measurement_counts"]
    provider = result["result"]["provider_name"]
    print(f"Provider: {provider}")
    print(f"Counts: {counts}")   # e.g. {'000': 2011, '111': 2085}
```

---

### Example D — cURL (placeholder — requires REST wrapper from Section 6)

> These commands will **not work** until a REST wrapper is deployed.
> Replace `[INSERT_HOST_HERE]` with your actual host.

```bash
# Signal state classification
curl -X POST https://[INSERT_HOST_HERE]/api/v1/invoke/signal \
  -H "Content-Type: application/json" \
  -H "X-API-Key: [INSERT_API_KEY_HERE]" \
  -d '{
    "node_id":      "qnode_01",
    "energy_delta": 0.0001,
    "iterations":   120,
    "confidence":   0.92,
    "variance":     0.002
  }'
```

```bash
# Provider health check
curl https://[INSERT_HOST_HERE]/api/v1/health/providers \
  -H "X-API-Key: [INSERT_API_KEY_HERE]"
```

```bash
# Dashboard telemetry
curl https://[INSERT_HOST_HERE]/api/v1/dashboard \
  -H "X-API-Key: [INSERT_API_KEY_HERE]"
```

---

## 6. REST Wrapper

To expose this runtime as an HTTP API, add FastAPI as a thin wrapper. The
runtime itself does not change — only an entrypoint file is added.

### Install

```bash
pip install fastapi uvicorn
```

### `api_server.py` (add to repo root)

```python
"""
Minimal FastAPI wrapper for Marine Quantum Runtime.
Production use: add auth middleware, rate limiting, and structured logging.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from invoke_runtime import invoke_runtime
from src.runtime.capability_runtime import invoke_capability, get_dashboard_json
from src.quantum.providers import provider_registry

app = FastAPI(
    title="Marine Quantum Runtime API",
    version="1.0.0",
    description="Sovereign Quantum Runtime Capability — BHIV Ecosystem",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["[INSERT_ALLOWED_ORIGINS_HERE]"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Auth (replace with real implementation) ──────────────────────────────────

VALID_API_KEYS = {"[INSERT_API_KEY_HERE]"}  # load from env/secrets in production

def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key

# ── Request models ────────────────────────────────────────────────────────────

class InvokeRequest(BaseModel):
    payload: Dict[str, Any]

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "runtime": "marine-quantum-runtime", "version": "1.0.0"}

@app.get("/api/v1/health/providers", dependencies=[Depends(verify_api_key)])
def provider_health():
    return provider_registry.backend_health()

@app.post("/api/v1/invoke/{module_name}", dependencies=[Depends(verify_api_key)])
def invoke(module_name: str, request: InvokeRequest):
    result = invoke_runtime(module_name, request.payload)
    if result["status"] not in ("SUCCESS", "VALIDATION_ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return result

@app.post("/api/v1/capability/{capability_id}", dependencies=[Depends(verify_api_key)])
def capability(capability_id: str, request: InvokeRequest):
    result = invoke_capability(capability_id, request.payload)
    return result

@app.get("/api/v1/dashboard", dependencies=[Depends(verify_api_key)])
def dashboard():
    return get_dashboard_json()

@app.get("/docs")  # FastAPI serves OpenAPI/Swagger at /docs automatically
def redirect_docs():
    return {"swagger": "/docs", "redoc": "/redoc", "openapi": "/openapi.json"}
```

### Run locally

```bash
uvicorn api_server:app --reload --port 8000

# Swagger UI available at:
open http://localhost:8000/docs
```

### Test with cURL after starting the server

```bash
# Health (no auth required)
curl http://localhost:8000/health

# Signal invocation
curl -X POST http://localhost:8000/api/v1/invoke/signal \
  -H "Content-Type: application/json" \
  -H "X-API-Key: [INSERT_API_KEY_HERE]" \
  -d '{"payload": {"node_id":"qnode_01","energy_delta":0.0001,"iterations":120,"confidence":0.92,"variance":0.002}}'

# Provider health
curl http://localhost:8000/api/v1/health/providers \
  -H "X-API-Key: [INSERT_API_KEY_HERE]"
```

---

## 7. Provider Configuration

The runtime ships with 4 quantum execution providers. All share the same
`ExecutionResult` output schema — caller code never needs to know which
backend ran the circuit.

| Provider | Always Available | Requires |
|----------|-----------------|----------|
| `local_simulator` | ✅ Yes (stdlib) | Nothing |
| `aer` | ✅ If installed | `pip install qiskit qiskit-aer` |
| `ibm_runtime` | ❌ Credentials required | `IBM_QUANTUM_TOKEN` + `pip install qiskit-ibm-runtime` |
| `ionq` | ❌ Credentials required | `IONQ_API_KEY` |

### Selecting a specific backend

```python
from src.quantum.providers.base import BackendRequirements

# Force Aer (fails if not installed)
req = BackendRequirements(preferred_provider="aer")

# Force real hardware (fails if no credentials)
req = BackendRequirements(require_real_hardware=True)

# Let the router pick the best available (recommended for resilience)
req = BackendRequirements(require_simulator=True)
```

### Checking backend availability before submitting

```python
from src.quantum.providers import provider_registry

for h in provider_registry.backend_health():
    print(f"{h['provider_name']:15} {h['backend_name']:25} {h['status']}")

# Output:
# local_simulator aer_simulator              AVAILABLE
# aer             aer_simulator              AVAILABLE (if qiskit-aer installed)
# ibm_runtime     ibm_brisbane_proxy         CREDENTIALS_REQUIRED
# ionq            ionq_aria_proxy            CREDENTIALS_REQUIRED
```

### Adding a new provider (no existing file changes required)

```python
from src.quantum.providers.base import (
    QuantumExecutionProvider, QuantumExecutionBackend,
    BackendCapabilities, BackendHealth, BackendStatus,
    CircuitSpec, ExecutionResult,
)
from src.quantum.providers import provider_registry

class MyBackend(QuantumExecutionBackend):
    def __init__(self):
        self.name = "my_backend"
        self.capabilities = BackendCapabilities(
            max_qubits=20, max_shots=10000, supports_noise=True,
            native_gates=["h","cx"], is_simulator=True, is_real_hardware=False,
        )
    def execute(self, circuit: CircuitSpec) -> ExecutionResult:
        # Your execution logic here
        return ExecutionResult(
            provider_name="my_provider", backend_name=self.name,
            measurement_counts={"0"*circuit.num_qubits: circuit.shots},
            shots_used=circuit.shots, is_simulator=True,
            seed=circuit.seed, execution_time_ms=1.0,
        )
    def health(self, seq):
        return BackendHealth(
            provider_name="my_provider", backend_name=self.name,
            status=BackendStatus.AVAILABLE, reason="custom backend",
            last_checked_seq=seq,
        )

class MyProvider(QuantumExecutionProvider):
    def __init__(self):
        self.provider_name = "my_provider"
        self._backend = MyBackend()
    def list_backends(self): return [self._backend]
    def get_backend(self, name): return self._backend if name == self._backend.name else None

# One call — zero changes to any existing file
provider_registry.register_provider(MyProvider())
```

---

## 8. Error Reference

### `invoke_runtime` status codes

| Status | Meaning | Action |
|--------|---------|--------|
| `SUCCESS` | Execution completed | Use `result["output"]` |
| `VALIDATION_ERROR` | Input failed schema check | Fix payload fields; see `errors[]` |
| `FAILED` | Internal execution error | See `errors[]`; retry or escalate |
| `MODULE_NOT_FOUND` | Unknown module name | Check spelling; valid: `signal`, `quantum_pipeline`, `distributed_qapp`, `operational_monitor` |

### `invoke_capability` status codes

| Status | Meaning | Action |
|--------|---------|--------|
| `SUCCESS` | Full stack execution completed | Use `result["output"]` |
| `VALIDATION_ERROR` | Typed attachment failed | Check field types and bounds; see `errors[]` |
| `DEPENDENCY_ERROR` | Required dependency not registered | Register dependency before invoking |
| `AUTHORITY_DENIED` | Action exceeds capability's ceiling | Review authority matrix; don't bypass |
| `REPLAY_DENIED` | Already executed; replay authority rejected | Use `replay()` method on authority to verify |
| `CAPABILITY_NOT_FOUND` | `capability_id` not registered | Check `list_capabilities()` for valid IDs |
| `FAILED` | Execution error | See `errors[]`; retry with backoff |

### `production_execute` status codes

| Status | Meaning | Action |
|--------|---------|--------|
| `SUCCESS` | Circuit executed on a healthy backend | Use `result["result"]["measurement_counts"]` |
| `LIMIT_EXCEEDED` | `num_qubits` or `shots` over limits | Reduce circuit size or shot count |
| `NO_BACKEND_AVAILABLE` | All backends UNAVAILABLE | Check `backend_health()`; add credentials or install Aer |
| `ROUTING_FAILED` | No backend satisfied requirements | Relax `BackendRequirements`; check `routing["attempted"]` |
| `EXECUTION_FAILED` | Backend threw an unexpected error | See `errors[]`; try fallback provider |

### Signal transition states

| State | Meaning | Action required |
|-------|---------|-----------------|
| `CONVERGED` | Node stable — all convergence criteria met | Automatic decisions enabled |
| `SUSPENDED` | Node marginal — below confidence floor or high variance | Human review recommended |
| `DIVERGED` | Node unstable — energy spike or runaway iterations | Human review mandatory; do not act autonomously |

---

## 9. Ecosystem Federation

This runtime participates in the BHIV ecosystem as a **consumer** of external
authority services. It never decides replay legitimacy, governance, or
evidence ownership itself.

### Attaching Pritesh's Replay Authority

```python
from src.runtime.capability_runtime import attach_replay_authority
from src.governance.replay_legitimacy import CanonicalReplayAuthority

# Development (allows repeat execution for testing)
attach_replay_authority(CanonicalReplayAuthority(allow_re_execution=True))

# Production (deny replay — attach Pritesh's real authority when available)
# attach_replay_authority(PriteshCanonicalReplayAuthority(...))
```

### Attaching a persistent evidence ledger

```python
from src.runtime.capability_runtime import attach_evidence_ledger
from src.runtime.persistent_history import PersistentHistory

attach_evidence_ledger(PersistentHistory(path="/var/log/bhiv/runtime_history.jsonl"))
# Or: attach_evidence_ledger(PriteshEvidenceLedger(...))
```

### Federation runtime (for Kanishk / Pritesh direct integration)

```python
from src.federation.federation_runtime import FederationRuntime
from src.governance.replay_legitimacy import CanonicalReplayAuthority
from src.runtime.persistent_history import PersistentHistory

fed = FederationRuntime(
    replay_authority  = CanonicalReplayAuthority(allow_re_execution=False),
    evidence_ledger   = PersistentHistory(path="[INSERT_LEDGER_PATH_HERE]"),
    # provenance_api  = [INSERT_PRITESH_PROVENANCE_API_HERE],
    # timeline_sink   = [INSERT_TIMELINE_SINK_HERE],
)

result = fed.federated_execute(
    capability_id = "signal",
    payload       = {"node_id": "qnode_01", "energy_delta": 0.0001,
                     "iterations": 120, "confidence": 0.92, "variance": 0.002},
    execute_fn    = lambda p: invoke_runtime("signal", p)["output"],
)
print(result["status"])          # SUCCESS | REPLAY_DENIED
print(result["replay_decision"]) # {"decision": "PERMIT", ...}
```

---

## 10. Known Limitations

| Item | Status | Path to resolution |
|------|--------|--------------------|
| IBM Runtime real execution | Credentials + network required | Set `IBM_QUANTUM_TOKEN`, install `qiskit-ibm-runtime` |
| IonQ real execution | Credentials + network required | Set `IONQ_API_KEY` |
| Distributed transport | In-process simulation only | Jaffer Ali owns real network transport layer |
| Governance pre-approval hook | Not yet wired | Raj owns enforcement integration |
| HTTP API / REST endpoints | Not deployed | Use Section 6 FastAPI wrapper locally |
| Swagger / OpenAPI | No URL yet | `[INSERT_SWAGGER_URL_HERE]` — generated by FastAPI at `/docs` |
| Real screenshots for testing | Text captures only | Run locally with `python run/run_ecosystem_integration.py` |

Full list with remediation steps: see `KNOWN_LIMITATIONS.md` in the repository root.

---

## Appendix A — State Transition Table (Signal Module)

| Condition (checked in priority order) | `next` state |
|---------------------------------------|--------------|
| `energy_delta > 0.01` | `DIVERGED` |
| `iterations > 500` | `DIVERGED` |
| `confidence < 0.70` | `SUSPENDED` |
| `variance > 0.01` | `SUSPENDED` |
| `confidence >= 0.85` AND `variance <= 0.005` AND `energy_delta <= 0.005` | `CONVERGED` |
| (fallback) | `SUSPENDED` |

`sigma = sqrt(variance)` — always.  
`prev = "INITIALISING"` if `iterations == 0`, else `"ACTIVE"`.

---

## Appendix B — Quick Reference: Valid Payload Fields

### Signal / Governance / Monitoring

```jsonc
{
  "node_id":      "string, non-empty",
  "energy_delta": "float >= 0.0",
  "iterations":   "int >= 0",
  "confidence":   "float in [0.0, 1.0]",
  "variance":     "float >= 0.0"
}
```

### Quantum Pipeline

```jsonc
{
  "salinity":                    "float in [0.0, 50.0]",
  "temperature_celsius":         "float in [-5.0, 45.0]",
  "pH":                          "float in [0.0, 14.0]",
  "material_oxidation_potential":"float in [-2.0, 2.0]",
  "dissolved_oxygen_mgl":        "float in [0.0, 20.0]",
  "current_density_mAcm2":       "float in [0.0, 10.0]"
}
```

### Distributed QApp

```jsonc
{
  "qapp_id":    "string, non-empty",
  "node_origin":"string, non-empty",
  "sequence_id":"int >= 1",
  "data":       { /* signal payload */ },
  "contract_version": "string (optional, default: 'qapp-v1.0')"
}
```

---

*For integration questions, contact Dhiraj Chavan (Marine Intelligence System / BHIV Core).*  
*Repository: `https://github.com/dhirajchavan-works/Marine-quantum-runtime`*
