"""
Tests for the QCG compatibility adapter in api_server.py.

No access to the QCG repository is needed: the requests below are sample QCG
payloads shaped like QCG's CapabilityDispatchRequest / HybridSubmitRequest.
`production_execute` is replaced by a fake in most tests so they are fast and
deterministic; one test (skipped if qiskit-aer is missing) runs the REAL
execution pipeline on AerSimulator.

Run from the repo root:   pytest tests/test_qcg_adapter.py -v
"""
import json
import logging
import os
import re
import sys
import threading
import time
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("RUNTIME_API_KEY", "unit-test-key")

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402

API_KEY = "unit-test-key-for-qcg-adapter"
INVOCATION_KEYS = {
    "invocation_id", "service_id", "operation", "status", "response",
    "duration_ms", "trust_method", "evidence", "error",
}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

GHZ_WORKLOAD = {
    "workload_id": "wl-001",
    "workload_type": "SIMULATION",
    "problem_size": 3,
    "num_qubits": 3,
    "shots": 1024,
    "seed": 42,
    "gate_sequence": [
        {"gate": "h", "qubits": [0]},
        {"gate": "cx", "qubits": [0, 1]},
        {"gate": "cx", "qubits": [1, 2]},
    ],
}


def dispatch_body(**over):
    body = {
        "service_id": "QCG-HYBRID-RUNTIME",
        "operation": "hybrid_submit",
        "payload": dict(GHZ_WORKLOAD),
        "version": "1.0.0",
        "invocation_id": "a7b2dfe8-433e-43eb-9044-da445803f9a9",
    }
    body.update(over)
    return body


class FakeExecutor:
    """Stand-in for production_execute that records how it was called."""

    def __init__(self, result=None, delay=0.0):
        self.calls = []
        self.delay = delay
        self.finished = threading.Event()
        self.result = result or {
            "status": "SUCCESS", "provider": "aer", "backend_name": "aer_simulator",
            "counts": {"000": 512, "111": 512},
        }

    def __call__(self, circuit, requirements):
        self.calls.append((circuit, requirements))
        if self.delay:
            time.sleep(self.delay)
        self.finished.set()
        return dict(self.result)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(api_server, "_RUNTIME_API_KEY", API_KEY)
    monkeypatch.delenv("QCG_ADAPTER_TIMEOUT_SECONDS", raising=False)
    return TestClient(api_server.app, raise_server_exceptions=False)


@pytest.fixture()
def fake(monkeypatch):
    f = FakeExecutor()
    monkeypatch.setattr(api_server, "production_execute", f)
    return f


AUTH = {"X-API-Key": API_KEY}


# ── Success + response shape ──────────────────────────────────────────────────

def test_dispatch_success_returns_invocation_result_and_labels_simulator(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH)
    body = r.json()
    assert r.status_code == 200
    assert set(body) == INVOCATION_KEYS                      # exactly QCG's nine keys
    assert body["status"] == "SUCCESS"
    assert body["service_id"] == "QCG-HYBRID-RUNTIME"
    assert body["operation"] == "hybrid_submit"
    assert body["trust_method"] == "CLASSICAL"               # simulator => never HYBRID
    assert body["error"] is None
    resp = body["response"]
    assert resp["classification"] == "QUANTUM_SIMULATED"
    assert resp["execution_path"] == "SIMULATED"
    assert resp["is_simulator"] is True
    assert resp["physical_qpu_execution_verified"] is False
    assert resp["backend_name"] == "aer_simulator"
    assert resp["measurement_counts"] == {"000": 512, "111": 512}
    assert re.fullmatch(r"[0-9a-f]{64}", resp["result_hash"])
    assert body["evidence"]["classification"] == "QUANTUM_SIMULATED"
    assert body["evidence"]["provenance_available"] is False
    assert "merkle_root" not in body["evidence"]             # Marine has no ledger: nothing faked
    assert resp["request_metadata"]["workload_type"] == "SIMULATION"


def test_workload_is_mapped_onto_existing_circuit_request(client, fake):
    client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH)
    circuit, req = fake.calls[0]
    assert (circuit.num_qubits, circuit.shots, circuit.seed) == (3, 1024, 42)
    assert circuit.gate_sequence == GHZ_WORKLOAD["gate_sequence"]
    assert req.require_simulator is True and req.require_real_hardware is False


def test_submit_endpoint_success(client, fake):
    r = client.post("/hybrid/submit", headers=AUTH, json={
        "workload": GHZ_WORKLOAD, "workload_type": "SIMULATION", "problem_size": 3,
    })
    body = r.json()
    assert r.status_code == 200 and set(body) == INVOCATION_KEYS
    assert body["service_id"] == "MARINE-QUANTUM-RUNTIME"
    assert body["response"]["classification"] == "QUANTUM_SIMULATED"
    assert body["invocation_id"] == body["evidence"]["trace_id"] == r.headers["x-trace-id"]


def test_unrecognised_workload_keys_are_reported_not_silently_used(client, fake):
    payload = dict(GHZ_WORKLOAD, hamiltonian={"x": 1})
    body = client.post("/hybrid/dispatch", json=dispatch_body(payload=payload), headers=AUTH).json()
    assert body["status"] == "SUCCESS"
    assert body["response"]["ignored_fields"] == ["hamiltonian"]


# ── Trace ID propagation ──────────────────────────────────────────────────────

def test_invocation_id_becomes_trace_id_when_no_header(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH)
    inv = "a7b2dfe8-433e-43eb-9044-da445803f9a9"
    body = r.json()
    assert body["invocation_id"] == inv
    assert body["evidence"]["trace_id"] == inv
    assert body["response"]["trace_id"] == inv
    assert r.headers["x-trace-id"] == inv
    assert body["response"]["marine_execution_result"]["trace_id"] == inv
    assert body["response"]["marine_execution_result"]["instrumentation"]["trace_id"] == inv


def test_x_trace_id_header_wins_and_invocation_id_is_echoed_unchanged(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers={**AUTH, "X-Trace-ID": "BHQ-TEST-001"})
    body = r.json()
    assert r.headers["x-trace-id"] == body["evidence"]["trace_id"] == "BHQ-TEST-001"
    assert body["invocation_id"] == "a7b2dfe8-433e-43eb-9044-da445803f9a9"


def test_trace_id_generated_when_nothing_supplied(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(invocation_id=""), headers=AUTH)
    body = r.json()
    assert UUID_RE.match(r.headers["x-trace-id"])
    assert body["invocation_id"] == body["evidence"]["trace_id"] == r.headers["x-trace-id"]


def test_invalid_invocation_id_is_echoed_but_not_used_as_trace(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(invocation_id="not a valid trace id!"), headers=AUTH)
    body = r.json()
    assert body["invocation_id"] == "not a valid trace id!"
    assert UUID_RE.match(body["evidence"]["trace_id"])
    assert r.headers["x-trace-id"] == body["evidence"]["trace_id"]


def test_malformed_x_trace_id_header_is_rejected_with_fresh_trace(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers={**AUTH, "X-Trace-ID": "bad id\twith spaces"})
    assert r.status_code == 400
    assert r.json()["status"] == "INVALID_TRACE_ID"
    assert r.json()["trace_id"] == r.headers["x-trace-id"]
    assert fake.calls == []


def test_concurrent_requests_keep_separate_trace_ids(client, monkeypatch):
    monkeypatch.setattr(api_server, "production_execute", FakeExecutor(delay=0.05))
    results = {}

    def worker(i):
        c = TestClient(api_server.app)
        r = c.post("/hybrid/dispatch", json=dispatch_body(invocation_id=f"INV-{i:03d}"), headers=AUTH)
        b = r.json()
        results[i] = (b["invocation_id"], b["evidence"]["trace_id"], r.headers["x-trace-id"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(results[i] == (f"INV-{i:03d}",) * 3 for i in range(12))


# ── Invalid requests ──────────────────────────────────────────────────────────

def test_missing_circuit_fields_returns_failed_envelope_and_does_not_execute(client, fake):
    payload = {"workload_type": "OPTIMIZATION", "is_qubo_compatible": True, "problem_size": 8}
    r = client.post("/hybrid/dispatch", json=dispatch_body(payload=payload), headers=AUTH)
    body = r.json()
    assert r.status_code == 422 and set(body) == INVOCATION_KEYS
    assert body["status"] == "FAILED"
    assert "num_qubits" in body["error"] and "gate_sequence" in body["error"]
    assert body["evidence"]["trace_id"] == r.headers["x-trace-id"]
    assert body["response"]["classification"] == "CLASSICAL" and body["response"]["execution_path"] == "BLOCKED"
    assert fake.calls == []


def test_out_of_range_qubit_is_rejected_with_trace(client, fake):
    payload = dict(GHZ_WORKLOAD, gate_sequence=[{"gate": "h", "qubits": [7]}])
    r = client.post("/hybrid/dispatch", json=dispatch_body(payload=payload), headers=AUTH)
    body = r.json()
    assert r.status_code == 422 and body["status"] == "FAILED"
    assert "out of range" in body["error"]
    assert body["evidence"]["trace_id"] == r.headers["x-trace-id"]
    assert fake.calls == []


@pytest.mark.parametrize("bad", [
    {"problem_size": "abc"},
    {"is_qubo_compatible": "yes"},
    {"workload_type": 5},
    {"shots": 5},
    {"num_qubits": 0},
])
def test_bad_field_types_return_failed_envelope_not_500(client, fake, bad):
    r = client.post("/hybrid/dispatch", json=dispatch_body(payload=dict(GHZ_WORKLOAD, **bad)), headers=AUTH)
    body = r.json()
    assert r.status_code == 422 and body["status"] == "FAILED" and set(body) == INVOCATION_KEYS
    assert fake.calls == []


def test_request_envelope_validation_error_carries_trace(client, fake):
    r = client.post("/hybrid/dispatch", json={"payload": "not-an-object"}, headers={**AUTH, "X-Trace-ID": "ERR-ENV"})
    assert r.status_code == 422
    assert r.json()["trace_id"] == "ERR-ENV" and r.headers["x-trace-id"] == "ERR-ENV"


def test_unknown_operation_is_service_not_found(client, fake):
    r = client.post("/hybrid/dispatch", json=dispatch_body(operation="network_status"), headers=AUTH)
    body = r.json()
    assert set(body) == INVOCATION_KEYS
    assert body["status"] == "SERVICE_NOT_FOUND" and body["response"] is None
    assert "network_status" in body["error"]
    assert body["evidence"]["trace_id"] == r.headers["x-trace-id"]


def test_health_check_operation(client, fake):
    body = client.post("/hybrid/dispatch", json=dispatch_body(operation="health_check", payload={}), headers=AUTH).json()
    assert set(body) == INVOCATION_KEYS and body["status"] == "SUCCESS"
    assert body["response"]["status"] == "ok"


# ── Authentication ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,body", [
    ("/hybrid/dispatch", dispatch_body()),
    ("/hybrid/submit", {"workload": GHZ_WORKLOAD}),
])
def test_missing_or_wrong_api_key_is_rejected_with_trace(client, fake, path, body):
    r = client.post(path, json=body, headers={"X-Trace-ID": "ERR-AUTH"})
    assert r.status_code == 401 and r.json()["trace_id"] == "ERR-AUTH"
    r = client.post(path, json=body, headers={"X-API-Key": "wrong", "X-Trace-ID": "ERR-AUTH2"})
    assert r.status_code == 401 and r.json()["trace_id"] == "ERR-AUTH2"
    assert fake.calls == []


def test_api_key_never_appears_in_responses_or_logs(client, fake, caplog):
    caplog.set_level(logging.DEBUG)
    r1 = client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH)
    r2 = client.post("/hybrid/dispatch", json=dispatch_body(), headers={"X-API-Key": "wrong-key-value"})
    assert API_KEY not in r1.text and API_KEY not in r2.text and "wrong-key-value" not in r2.text
    assert API_KEY not in caplog.text and "wrong-key-value" not in caplog.text


# ── Timeout ───────────────────────────────────────────────────────────────────

def test_timeout_reports_TIMEOUT_with_trace_and_is_never_success(client, monkeypatch):
    slow = FakeExecutor(delay=0.8)
    monkeypatch.setattr(api_server, "production_execute", slow)
    monkeypatch.setenv("QCG_ADAPTER_TIMEOUT_SECONDS", "0.2")
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers={**AUTH, "X-Trace-ID": "TMO-001"})
    body = r.json()
    assert r.status_code == 504 and set(body) == INVOCATION_KEYS
    assert body["status"] == "TIMEOUT"
    assert body["status"] != "SUCCESS"
    assert body["evidence"]["trace_id"] == "TMO-001" and r.headers["x-trace-id"] == "TMO-001"
    assert body["response"]["measurement_counts"] is None          # no result reported
    assert body["response"]["marine_execution_result"] is None
    assert body["response"]["classification"] == "CLASSICAL" and body["response"]["execution_path"] == "BLOCKED"
    assert "MAY_STILL_BE_RUNNING" in body["response"]["background_execution"]
    assert "timeout" in body["error"].lower()
    assert any(rec["trace_id"] == "TMO-001" and rec["execution_status"] == "TIMEOUT"
               for rec in api_server._execution_log_snapshot())
    assert slow.finished.wait(3)        # background run finishes; its result stays discarded


def test_timeout_is_recorded_in_calibration_instrumentation(client, monkeypatch):
    monkeypatch.setattr(api_server, "production_execute", FakeExecutor(delay=0.6))
    monkeypatch.setenv("QCG_ADAPTER_TIMEOUT_SECONDS", "0.1")
    client.post("/hybrid/dispatch", json=dispatch_body(invocation_id="TMO-CAL"), headers=AUTH)
    log = api_server._execution_log_snapshot()
    assert any(rec["trace_id"] == "TMO-CAL" and rec["execution_status"] == "TIMEOUT" for rec in log)
    time.sleep(0.8)


def test_default_timeout_is_25_seconds_and_bad_values_fall_back(monkeypatch):
    monkeypatch.delenv("QCG_ADAPTER_TIMEOUT_SECONDS", raising=False)
    assert api_server._qcg_timeout_seconds() == 25.0
    for bad in ("abc", "-3", "0", "nan", "inf", ""):
        monkeypatch.setenv("QCG_ADAPTER_TIMEOUT_SECONDS", bad)
        assert api_server._qcg_timeout_seconds() == 25.0
    monkeypatch.setenv("QCG_ADAPTER_TIMEOUT_SECONDS", "7.5")
    assert api_server._qcg_timeout_seconds() == 7.5


# ── Honest simulator / hardware labeling ──────────────────────────────────────

def test_live_hardware_request_never_runs_on_simulator_and_is_not_reported_live(client, monkeypatch):
    f = FakeExecutor(result={"status": "NO_BACKEND_AVAILABLE", "errors": ["no real hardware backend available"]})
    monkeypatch.setattr(api_server, "production_execute", f)
    payload = dict(GHZ_WORKLOAD, requires_live_hardware=True)
    r = client.post("/hybrid/dispatch", json=dispatch_body(payload=payload), headers=AUTH)
    body = r.json()
    _, req = f.calls[0]
    assert req.require_real_hardware is True and req.require_simulator is False
    assert r.status_code == 503 and body["status"] == "FAILED"
    assert body["response"]["classification"] != "QUANTUM_LIVE"
    assert body["response"]["physical_qpu_execution_verified"] is False
    assert body["trust_method"] == "CLASSICAL"
    assert "no real hardware" in body["error"]


def test_classical_fallback_flag_does_not_block_simulator_runs(client, fake):
    payload = dict(GHZ_WORKLOAD, classical_fallback_acceptable=False)
    body = client.post("/hybrid/dispatch", json=dispatch_body(payload=payload), headers=AUTH).json()
    _, req = fake.calls[0]
    assert req.require_simulator is True and req.require_real_hardware is False
    assert body["status"] == "SUCCESS"
    assert body["response"]["request_metadata"]["classical_fallback_acceptable"] is False


def test_unidentified_backend_is_never_labeled_live(client, monkeypatch):
    f = FakeExecutor(result={"status": "SUCCESS", "provider": "mystery", "backend_name": "mystery_qpu",
                             "counts": {"0": 1024}})
    monkeypatch.setattr(api_server, "production_execute", f)
    body = client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH).json()
    assert body["status"] == "SUCCESS"
    assert body["response"]["classification"] == "UNVERIFIED"
    assert body["response"]["classification"] != "QUANTUM_LIVE"
    assert body["trust_method"] == "CLASSICAL"
    assert body["response"]["is_simulator"] is None


def test_contradictory_non_simulator_flag_on_aer_is_not_trusted(client, monkeypatch):
    f = FakeExecutor(result={"status": "SUCCESS", "backend_name": "aer_simulator",
                             "is_simulator": False, "counts": {"0": 1024}})
    monkeypatch.setattr(api_server, "production_execute", f)
    body = client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH).json()
    assert body["response"]["classification"] != "QUANTUM_LIVE"


def test_runtime_failure_is_reported_as_failed_with_error(client, monkeypatch):
    f = FakeExecutor(result={"status": "EXECUTION_FAILED", "errors": ["backend crashed"]})
    monkeypatch.setattr(api_server, "production_execute", f)
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers=AUTH)
    body = r.json()
    assert r.status_code == 503 and body["status"] == "FAILED" and "backend crashed" in body["error"]
    assert body["response"]["measurement_counts"] is None


def test_unexpected_exception_does_not_leak_internals(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail")
    monkeypatch.setattr(api_server, "production_execute", boom)
    r = client.post("/hybrid/dispatch", json=dispatch_body(), headers={**AUTH, "X-Trace-ID": "ERR-500"})
    assert r.status_code == 500
    assert "secret-internal-detail" not in r.text
    body = r.json()
    assert body["status"] == "FAILED" and body["evidence"]["trace_id"] == "ERR-500"
    assert r.headers["x-trace-id"] == "ERR-500"


# ── Regression: the existing endpoint is unchanged ────────────────────────────

def test_existing_quantum_execute_endpoint_behaviour_is_preserved(client, fake):
    body = {"num_qubits": 3, "shots": 1024, "seed": 42, "gate_sequence": GHZ_WORKLOAD["gate_sequence"]}
    r = client.post("/api/v1/quantum/execute", json=body, headers={**AUTH, "X-Trace-ID": "BHQ-TEST-001"})
    out = r.json()
    assert r.status_code == 200 and out["status"] == "SUCCESS"
    assert out["trace_id"] == "BHQ-TEST-001" and r.headers["x-trace-id"] == "BHQ-TEST-001"
    assert out["backend_name"] == "aer_simulator" and out["is_simulator"] is True
    assert out["measurement_counts"] == {"000": 512, "111": 512} and out["counts"] == {"000": 512, "111": 512}
    assert out["execution_id"].startswith("EXEC-")
    assert {"trace_id", "execution_id", "execution_timestamp", "num_qubits", "shots", "seed",
            "duration_ms", "execution_status"} <= set(out["instrumentation"])
    bad = client.post("/api/v1/quantum/execute", headers={**AUTH, "X-Trace-ID": "ERR-Q"},
                      json={"num_qubits": 3, "gate_sequence": [{"gate": "h", "qubits": [9]}]})
    assert bad.status_code == 422 and bad.json()["trace_id"] == "ERR-Q"


# ── Real execution pipeline (skipped when Aer is not installed) ───────────────

def test_real_aer_run_through_adapter(client):
    pytest.importorskip("qiskit_aer")
    r = client.post("/hybrid/dispatch", json=dispatch_body(invocation_id="REAL-AER-001"), headers=AUTH)
    body = r.json()
    assert r.status_code == 200, body
    assert body["status"] == "SUCCESS"
    counts = body["response"]["measurement_counts"]
    assert sum(counts.values()) == 1024 and set(counts) <= {"000", "111"}
    assert body["response"]["classification"] == "QUANTUM_SIMULATED"
    assert body["response"]["physical_qpu_execution_verified"] is False
    assert body["evidence"]["trace_id"] == "REAL-AER-001"
