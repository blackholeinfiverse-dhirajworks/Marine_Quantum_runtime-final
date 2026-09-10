# Reply to QCG Ecosystem Integration Request

---

**To:** QCG Ecosystem Integration Developer  
**From:** Dhiraj Chavan — Marine Intelligence System / BHIV Core  
**Re:** Integration request — Base API URL, Swagger, Auth, Sample requests

---

Hi,

Thanks for reaching out on the QCG ecosystem integration. I want to give you an accurate picture of the current state before you spend time on integration work, because there's one important thing to clarify upfront.

## Important: Current Deployment Status

**The runtime is not currently deployed as an HTTP service.** There is no live API URL, no Swagger endpoint, and no running server to hit. The runtime is a Python library that you invoke directly by import, not over HTTP.

I know that's not what your request assumed, so let me tell you exactly what you need for each of your questions, split into "what works right now" and "what we need to add for HTTP access."

---

## What You Asked For vs What Exists

### Base API URL

**Right now:** No URL. The runtime runs locally.

```bash
# How to run it locally (this is the current integration path)
git clone https://github.com/dhirajchavan-works/Marine-quantum-runtime.git
cd Marine-quantum-runtime
python run/run_signal.py          # verify it's working — exit 0 means ready
```

**If you need HTTP:** I've added `api_server.py` to the repository (see below). Once you drop it in and run it, your base URL is:

```
Local:   http://localhost:8000
Staging: https://[TO BE CONFIGURED]
Prod:    https://[TO BE CONFIGURED]
```

### Swagger / OpenAPI Documentation

**Right now:** No deployed Swagger URL.

**With the API server running locally:**
```
http://localhost:8000/docs       ← Swagger UI (interactive)
http://localhost:8000/redoc      ← ReDoc UI (reference)
http://localhost:8000/openapi.json  ← Machine-readable spec
```

FastAPI generates these automatically — no extra work needed once the server is up.

### Authentication

**Right now (Python import):** No auth needed. You import and call directly.

**With the API server:** API key in the `X-API-Key` header.

```bash
# Set before starting the server
export RUNTIME_API_KEY="your-api-key-here"

# Pass in every request header
X-API-Key: your-api-key-here
```

### Sample Request / Response

**Signal classification (the most common integration point):**

```bash
curl -X POST http://localhost:8000/api/v1/signal \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "node_id":      "qnode_01",
    "energy_delta": 0.0001,
    "iterations":   120,
    "confidence":   0.92,
    "variance":     0.002
  }'
```

Response:
```json
{
  "status": "SUCCESS",
  "module": "signal",
  "output": {
    "engine_event_version": "2.0",
    "node_ref": "qnode_01",
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

### Startup Instructions

See the next section.

---

## Getting the HTTP Server Running (5 Minutes)

I've added `api_server.py` to the repository. Here is everything you need:

```bash
# 1 — Clone
git clone https://github.com/dhirajchavan-works/Marine-quantum-runtime.git
cd Marine-quantum-runtime

# 2 — Install (quantum simulation is optional but recommended)
pip install fastapi uvicorn
pip install qiskit qiskit-aer          # optional — enables real Aer simulation

# 3 — Configure
export RUNTIME_API_KEY="choose-a-secret-key"

# 4 — Start
uvicorn api_server:app --reload --port 8000

# 5 — Open Swagger
open http://localhost:8000/docs
```

That's it. The Swagger UI gives you interactive documentation for all 18 endpoints.

---

## Available Endpoints (Summary)

| Method | Path | What It Does |
|--------|------|--------------|
| GET | `/health` | Liveness check — no auth required |
| GET | `/health/providers` | Backend health (Aer, IBM, IonQ, local sim) |
| POST | `/api/v1/signal` | Quantum node state classification |
| POST | `/api/v1/quantum/corrosion` | Marine corrosion risk assessment |
| POST | `/api/v1/quantum/execute` | Execute any quantum circuit |
| GET | `/api/v1/quantum/providers` | Provider capabilities + noise profiles |
| GET | `/api/v1/capabilities` | Registered runtime capabilities |
| POST | `/api/v1/capability/{id}` | Governed capability invocation |
| POST | `/api/v1/invoke/{module}` | Direct module invocation |
| GET | `/api/v1/dashboard` | All 6 ecosystem dashboard feeds |
| GET | `/api/v1/governance/authority-matrix` | Authority ceilings per capability |
| GET | `/api/v1/governance/decision-ledger` | Governance decision record |
| GET | `/api/v1/governance/replay-stats` | Replay authority statistics |

Full reference: `INTEGRATION_GUIDE.md` in the repository root.

---

## For QCG Ecosystem Specifically

If QCG needs to validate against live ecosystem services, the integration path is:

```python
# QCG calls the runtime via the federation layer
from src.federation.federation_runtime import FederationRuntime
from src.governance.replay_legitimacy import CanonicalReplayAuthority

# Attach QCG's replay authority (or use the reference implementation)
fed = FederationRuntime(
    replay_authority=CanonicalReplayAuthority(allow_re_execution=True)
)

result = fed.federated_execute(
    capability_id="signal",
    payload={"node_id": "qnode_qcg_01", "energy_delta": 0.0001,
             "iterations": 120, "confidence": 0.92, "variance": 0.002},
    execute_fn=lambda p: invoke_runtime("signal", p)["output"],
)
# result["replay_decision"]["decision"] == "PERMIT"
```

The `FederationRuntime` is the correct ecosystem integration point — it handles replay authority, evidence, and provenance consistently with how Pritesh's and Kanishk's layers expect to interact with us.

---

## Known Bugs Fixed Before You Integrate

During the code review I ran on the repo, I found and fixed 5 bugs before pushing. The full report is in `BUG_REPORT.md` in the repository, but the ones most likely to affect you are:

1. **Typed attachment crash on open-ended bounds** (`None` upper bound → `TypeError`). Fixed.
2. **`PersistentHistory` crash on flat filename paths** (`os.makedirs("")`). Fixed.
3. **JSON canonicalization mismatch** producing false `REPLAY_DIVERGED` verdicts. Fixed.
4. **Global sequence counter shared across capabilities** (cross-contamination). Fixed.
5. **Authority action name conflation** blocking all signal executions. Fixed.

All fixes are in the current `main` branch.

---

## What Isn't Ready Yet

Being straight with you on the gaps:

- **IBM Quantum / IonQ real hardware:** The adapters exist but require credentials and network egress we don't have in the current environment. Local `AerSimulator` works fully.
- **Production deployment URL:** Not yet. The server runs locally. Happy to discuss deployment options (Railway, Fly.io, GCP Cloud Run) if QCG needs a shared staging environment.
- **Authentication beyond API key:** Currently simple API key header. JWT can be added if QCG's auth flow requires it.

---

## Files Added to the Repository

| File | Purpose |
|------|---------|
| `api_server.py` | FastAPI REST wrapper — 18 endpoints, Swagger auto-generated |
| `INTEGRATION_GUIDE.md` | Comprehensive integration reference (Python + HTTP) |
| `BUG_REPORT.md` | All 5 bugs found and fixed, with reproduction cases |

Let me know if you hit any issues or need the server deployed to a shared environment for the QCG validation run. Happy to get on a call if the async back-and-forth is slowing things down.

**Dhiraj Chavan**  
Marine Intelligence System / BHIV Core  
`https://github.com/dhirajchavan-works/Marine-quantum-runtime`
