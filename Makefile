# Marine Quantum Runtime — Developer Makefile
.PHONY: help install install-quantum install-api verify serve \
        test test-api test-client test-all lint clean

help:
	@echo ""
	@echo "Marine Quantum Runtime"
	@echo "────────────────────────────────────────────────────────"
	@echo "  make install          No external deps — stdlib only"
	@echo "  make install-quantum  Add qiskit + qiskit-aer (real Aer sim)"
	@echo "  make install-api      Add fastapi + uvicorn (REST server)"
	@echo "  make install-client   Add requests (HTTP client mode)"
	@echo "  make verify           Run all 6 core entry points (exit 0)"
	@echo "  make serve            Start API server at localhost:8000"
	@echo "  make test             Run all 6 core test suites"
	@echo "  make test-api         Run 26-endpoint HTTP test suite"
	@echo "  make test-client      Run 42-test SDK client test suite"
	@echo "  make test-all         Run everything (exit 0 = fully green)"
	@echo "  make clean            Remove __pycache__, .pyc, log files"
	@echo ""

install:
	@python3 --version
	@echo "Core runtime has no external dependencies."

install-quantum:
	pip install qiskit qiskit-aer

install-api:
	pip install fastapi uvicorn pydantic httpx2

install-client:
	pip install requests

verify:
	@echo "── Signal (Tasks 1-4) ──────────────────────────────────"
	python3 run/run_signal.py
	@echo "── Quantum Pipeline (Task 8) ───────────────────────────"
	python3 run/run_quantum_pipeline.py
	@echo "── Distributed QApp (Task 9) ───────────────────────────"
	python3 run/run_distributed_qapp.py
	@echo "── Operational Drift (Monitoring) ──────────────────────"
	python3 run/run_operational_drift.py
	@echo "── Governance (46 checks) ──────────────────────────────"
	python3 run/run_governance.py
	@echo "── Ecosystem Integration (33 checks) ───────────────────"
	python3 run/run_ecosystem_integration.py
	@echo "── All entry points: PASS ──────────────────────────────"

serve:
	@test -n "$$RUNTIME_API_KEY" || \
	  (echo "ERROR: Set RUNTIME_API_KEY first:  export RUNTIME_API_KEY=your-key" && exit 1)
	uvicorn api_server:app --reload --port $${PORT:-8000}

test: verify

test-api:
	RUNTIME_API_KEY=test-key-ci python3 tests/test_api_endpoints.py

test-client:
	python3 tests/test_client.py

test-all: test test-api test-client
	@echo ""
	@echo "╔══════════════════════════════════════════════════╗"
	@echo "║  All test suites passed ✅                       ║"
	@echo "╚══════════════════════════════════════════════════╝"

clean:
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -f runtime_history.jsonl
	@echo "Cleaned."
