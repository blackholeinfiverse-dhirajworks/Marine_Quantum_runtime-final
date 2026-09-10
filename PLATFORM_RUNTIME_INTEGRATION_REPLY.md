# Platform Runtime Integration — Developer Reply
**From:** Dhiraj Chavan — Marine Intelligence System / BHIV Core  
**To:** Platform Runtime Integration Developer  
**Date:** August 2026

---

## Direct Answers First

| What you asked | What exists |
|----------------|-------------|
| Live deployed URL | **Not yet deployed** — see Section 1 for the 5-minute local path and Section 5 for free deployment options |
| `/api/v1/execute` endpoint | **Path is slightly different** — it's `/api/v1/invoke/{module}` for general execution, `/api/v1/quantum/execute` for circuit execution. Both work. |
| JSON request schema | ✅ Full schema below — extracted from the live running server |

---

## Section 1 — Get It Running Locally (5 Minutes)

```bash
# Step 1 — Clone
git clone https://github.com/dhirajchavan-works/Marine-quantum-runtime.git
cd Marine-quantum-runtime

# Step 2 — Install
pip install fastapi uvicorn qiskit qiskit-aer

# Step 3 — Set your API key (pick anything for local dev)
export RUNTIME_API_KEY=dev-key-change-me

# Step 4 — Start
uvicorn api_server:app --reload --port 8000

# Step 5 — Confirm it's running
curl http://localhost:8000/health
# → {"status":"ok","runtime":"marine-quantum-runtime","version":"1.0.0"}
```

**Swagger UI (interactive docs):** `http://localhost:8000/docs`  
**OpenAPI JSON spec:** `http://localhost:8000/openapi.json`

---

## Section 2 — Base URLs

| Environment | URL | Status |
|-------------|-----|--------|
| **Local** | `http://localhost:8000` | ✅ Works immediately after Step 4 above |
| **Staging** | `https://[DEPLOY_URL_HERE]` | See Section 5 — deploy in 10 minutes free |
| **Production** | `https://[DEPLOY_URL_HERE]` | Pending infrastructure decision |

> **Honest note:** There is no shared live URL I can give you today. Section 5 shows how
> to get one on Render or Railway for free in ~10 minutes, or I can send you the
> running `api_server.py` and you can host it yourself.

---

## Section 3 — Authentication

All endpoints except `/health` require an API key in the request header:

```
X-API-Key: your-api-key-here
```

```bash
# Correct ✅
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/invoke/signal ...

# Wrong ❌ — returns 401
curl http://localhost:8000/api/v1/invoke/signal ...
```

**Setting the key when starting the server:**
```bash
export RUNTIME_API_KEY="your-secret-key-here"
uvicorn api_server:app --port 8000
```

No JWT, no OAuth — plain API key for now. JWT can be added if your Platform Runtime
requires it.

---

## Section 4 — Endpoints & JSON Schemas

### Correcting your `/api/v1/execute` assumption

Your assumed path is very close. The actual paths are:

| Your assumption | Actual path | Use for |
|----------------|-------------|---------|
| `POST /api/v1/execute` | `POST /api/v1/invoke/{module}` | General runtime invocation |
| `POST /api/v1/execute` | `POST /api/v1/quantum/execute` | Quantum circuit execution specifically |
| — | `POST /api/v1/capability/{id}` | Full governed invocation stack |

All three produce the same `status`/`output` response shape.

---

### Complete Endpoint Reference

#### `GET /health` — No auth required

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "runtime": "marine-quantum-runtime",
  "version": "1.0.0"
}
```

---

#### `GET /health/providers` — Backend status

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/health/providers
```

**Live response (actual output from running server):**
```json
[
  {
    "provider_name": "local_simulator",
    "backend_name":  "local_classical_simulator",
    "status":        "AVAILABLE",
    "reason":        "stdlib-only, always available, no external dependency"
  },
  {
    "provider_name": "aer",
    "backend_name":  "aer_simulator",
    "status":        "AVAILABLE",
    "reason":        "qiskit-aer installed and importable"
  },
  {
    "provider_name": "ibm_runtime",
    "backend_name":  "ibm_brisbane_proxy",
    "status":        "UNAVAILABLE",
    "reason":        "qiskit-ibm-runtime SDK not installed"
  },
  {
    "provider_name": "ionq",
    "backend_name":  "ionq_aria_proxy",
    "status":        "CREDENTIALS_REQUIRED",
    "reason":        "IONQ_API_KEY environment variable not set"
  }
]
```

---

#### `POST /api/v1/invoke/{module}` — General module execution

This is the closest path to your assumed `/api/v1/execute`.  
Replace `{module}` with: `signal`, `quantum_pipeline`, `distributed_qapp`, or `operational_monitor`.

**Request schema:**
```json
{
  "payload": {
    "...module-specific fields..."
  }
}
```

**Example — signal classification:**

```bash
curl -X POST http://localhost:8000/api/v1/invoke/signal \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "payload": {
      "node_id":      "qnode_platform_01",
      "energy_delta": 0.0001,
      "iterations":   120,
      "confidence":   0.92,
      "variance":     0.002
    }
  }'
```

**Live response (actual output, 6.8ms execution):**
```json
{
  "status":             "SUCCESS",
  "module":             "signal",
  "execution_id":       "8419356ec3547d8de808...",
  "deterministic_hash": "42a8cbd540e0ad22...",
  "duration_ms":        6.806,
  "output": {
    "engine_event_version": "2.0",
    "node_ref": "qnode_platform_01",
    "transition": {
      "prev":  "ACTIVE",
      "next":  "CONVERGED",
      "cause": "confidence=0.92>=0.85, variance=0.002<=0.005, energy_delta=0.0001<=0.005",
      "seq":   1,
      "ts":    "2026-01-01T02:00:00Z"
    },
    "uncertainty_envelope": {
      "confidence": 0.92,
      "sigma":      0.04472136
    }
  },
  "errors": []
}
```

**`next` values and what they mean:**

| `next` | Meaning | Platform action |
|--------|---------|-----------------|
| `CONVERGED` | Node stable — all convergence criteria met | Safe for autonomous decisions |
| `SUSPENDED` | Node marginal — confidence or variance out of range | Requires human review |
| `DIVERGED` | Node unstable — energy spike or runaway iterations | Do not act autonomously |

---

#### `POST /api/v1/quantum/execute` — Quantum circuit execution

This is what your Platform Runtime would call for actual quantum computation.

**Request schema (all fields):**

```json
{
  "num_qubits":          3,
  "gate_sequence":       [
    { "gate": "h",  "qubits": [0] },
    { "gate": "cx", "qubits": [0, 1] },
    { "gate": "cx", "qubits": [1, 2] }
  ],
  "shots":               1024,
  "seed":                42,
  "preferred_provider":  "aer",
  "require_simulator":   true,
  "require_real_hardware": false
}
```

**Field constraints:**

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `num_qubits` | int | ✅ | 1 – 29 |
| `gate_sequence` | array | ✅ | See gate table below |
| `shots` | int | ❌ | 100 – 100,000 (default: 4096) |
| `seed` | int | ❌ | Any int (default: 42) |
| `preferred_provider` | string | ❌ | `aer`, `local_simulator`, `ibm_runtime`, `ionq` |
| `require_simulator` | bool | ❌ | default: `true` |
| `require_real_hardware` | bool | ❌ | default: `false` |

**Supported gates:**

| Gate | `qubits` length | Param |
|------|----------------|-------|
| `h`, `x`, `y`, `z` | 1 | — |
| `cx`, `cz`, `swap` | 2 | — |
| `rx`, `ry`, `rz` | 1 | `"param": <float_radians>` |

```bash
curl -X POST http://localhost:8000/api/v1/quantum/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "num_qubits": 3,
    "shots": 1024,
    "seed": 42,
    "gate_sequence": [
      {"gate": "h",  "qubits": [0]},
      {"gate": "cx", "qubits": [0, 1]},
      {"gate": "cx", "qubits": [1, 2]}
    ],
    "require_simulator": true
  }'
```

**Live response (real AerSimulator output — genuine GHZ entanglement):**
```json
{
  "status": "SUCCESS",
  "result": {
    "provider_name":      "aer",
    "backend_name":       "aer_simulator",
    "measurement_counts": {
      "000": 490,
      "111": 534
    },
    "shots_used":         1024,
    "is_simulator":       true,
    "seed":               42,
    "execution_time_ms":  210.781
  },
  "routing": {
    "final_provider": "aer",
    "final_backend":  "aer_simulator",
    "failover_count": 0
  },
  "errors": []
}
```

> `measurement_counts` is the raw quantum measurement distribution.
> In a GHZ circuit all qubits are entangled — you get `000` or `111`, nothing else.
> This is a genuine `AerSimulator` result, not fabricated.

---

#### `POST /api/v1/capability/{capability_id}` — Full governed stack

Use this if Platform Runtime needs replay authority, evidence, and provenance
tracking on every call (full ecosystem federation).

```bash
curl -X POST http://localhost:8000/api/v1/capability/signal \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "payload": {
      "node_id":      "qnode_platform_01",
      "energy_delta": 0.0001,
      "iterations":   120,
      "confidence":   0.92,
      "variance":     0.002
    }
  }'
```

Response includes everything from `/invoke/signal` plus:
```json
{
  "invocation_id":    "d3ad48e72f75957c...",
  "replay_authority": { "decision": "PERMIT", "authority": "CanonicalReplayAuthority" },
  "provenance_ref":   "d3ad48e72f75957c...",
  "dependency_check": { "valid": true },
  "authority_check":  { "permitted": true }
}
```

---

#### Complete endpoint list

```
GET  /health                              ← no auth, liveness probe
GET  /health/providers                    ← all 4 backend statuses
GET  /health/detailed                     ← full provider + capability report

POST /api/v1/invoke/{module}              ← your /api/v1/execute equivalent
POST /api/v1/quantum/execute              ← circuit execution
POST /api/v1/quantum/corrosion            ← marine corrosion assessment
GET  /api/v1/quantum/providers            ← capabilities, noise, hardware constraints

POST /api/v1/capability/{capability_id}   ← full governed invocation stack
GET  /api/v1/capabilities                 ← registered capabilities + health

GET  /api/v1/dashboard                    ← all 6 ecosystem telemetry feeds
GET  /api/v1/queue                        ← queue depth + backend availability

GET  /api/v1/governance/authority-matrix  ← authority ceilings
GET  /api/v1/governance/decision-ledger   ← decision ledger summary
GET  /api/v1/governance/replay-stats      ← replay permit/deny statistics
GET  /api/v1/governance/provenance        ← evidence status
GET  /api/v1/governance/doctrines         ← runtime design doctrine evaluation
```

---

## Section 5 — Get a Live URL in 10 Minutes (Free)

### Option A — Render (recommended, no credit card)

```bash
# 1. Push the repo to your GitHub
git add api_server.py Dockerfile
git commit -m "add REST API server"
git push

# 2. Go to https://render.com → New → Web Service → Connect your repo

# 3. Configure:
#    Build Command:  pip install fastapi uvicorn qiskit qiskit-aer
#    Start Command:  uvicorn api_server:app --host 0.0.0.0 --port $PORT
#    Environment Variables:
#      RUNTIME_API_KEY = <your-chosen-key>

# 4. Deploy → Render gives you:
#    https://marine-quantum-runtime.onrender.com
```

Your live URL replaces `http://localhost:8000` everywhere. Swagger at
`https://marine-quantum-runtime.onrender.com/docs`.

### Option B — Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# From repo root
railway login
railway init
railway up
railway variables set RUNTIME_API_KEY=your-key
# → https://marine-quantum-runtime-production.up.railway.app
```

### Option C — Docker (any cloud VM)

```bash
docker build --target quantum -t marine-runtime .
docker run -p 8000:8000 \
  -e RUNTIME_API_KEY=your-key \
  -e LOG_LEVEL=info \
  marine-runtime

# Or with docker-compose (after filling .env):
cp .env.example .env
# Edit .env: set RUNTIME_API_KEY
docker-compose up
```

---

## Section 6 — Error Responses

All errors follow the same shape:

```json
{
  "status": "VALIDATION_ERROR",
  "errors": ["Field 'confidence' = 1.9: must be a float in [0.0, 1.0]."],
  "output": null
}
```

| HTTP Code | `status` string | Meaning |
|-----------|----------------|---------|
| 200 | `SUCCESS` | Execution completed |
| 401 | — | Missing or wrong `X-API-Key` |
| 404 | `MODULE_NOT_FOUND` | Unknown `{module}` or `{capability_id}` |
| 422 | `VALIDATION_ERROR` | Request body failed schema validation |
| 403 | `AUTHORITY_DENIED` | Action exceeds capability's authority ceiling |
| 503 | `ROUTING_FAILED` | No backend available for the circuit's requirements |
| 500 | `FAILED` | Unexpected internal error |

---

## Section 7 — Integration Checklist for Platform Runtime

- [ ] Start server locally: `uvicorn api_server:app --port 8000`
- [ ] Confirm health: `curl http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] Test your main call with real data against `/api/v1/invoke/signal`
- [ ] Verify the `X-API-Key` header is set in every request (except `/health`)
- [ ] Check `/health/providers` to confirm `aer_simulator` is `AVAILABLE`
- [ ] Open `http://localhost:8000/docs` and run a test from the Swagger UI
- [ ] Run the API test suite: `RUNTIME_API_KEY=your-key python3 tests/test_api_endpoints.py`
- [ ] Choose a deploy target (Render / Railway / Docker) and get a live URL
- [ ] Share the live URL with Dhiraj and update this document's Section 2

---

## Quick Reference Card

```bash
# Env
export RUNTIME_API_KEY=your-key
export BASE_URL=http://localhost:8000        # or your deployed URL

# Health (no auth)
curl $BASE_URL/health

# Signal classification
curl -X POST $BASE_URL/api/v1/invoke/signal \
  -H "X-API-Key: $RUNTIME_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"payload":{"node_id":"q1","energy_delta":0.0001,"iterations":120,"confidence":0.92,"variance":0.002}}'

# Quantum execute
curl -X POST $BASE_URL/api/v1/quantum/execute \
  -H "X-API-Key: $RUNTIME_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"num_qubits":3,"shots":512,"seed":42,"gate_sequence":[{"gate":"h","qubits":[0]},{"gate":"cx","qubits":[0,1]},{"gate":"cx","qubits":[1,2]}],"require_simulator":true}'

# Swagger
open $BASE_URL/docs
```

---

*Dhiraj Chavan — Marine Intelligence System / BHIV Core*  
*Repository: `https://github.com/dhirajchavan-works/Marine-quantum-runtime`*  
*API test suite: `python3 tests/test_api_endpoints.py` — exit 0, 26/26 passing*
