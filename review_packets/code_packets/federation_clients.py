# src/federation/federation_clients.py
# Federation Client Layer — Phase 2: Runtime Federation.
#
# HARD BOUNDARY (from the ecosystem brief, "You DO NOT own"):
#   Replay Authority, Governance, Evidence legitimacy, Runtime execution
#   ordering, Dashboard authority, Physical execution engine.
#
# Every client class below is a CONSUMER. It calls out to an injected
# external system via dependency injection and reports what that system
# decided. None of these classes contain decision logic of their own.
#
# HONEST DECLARATION: "live federation" against Kanishk's actual deployed
# execution engine, Pritesh's actual quantum platform, or Raj's actual
# governance service cannot be proven from this sandbox — those systems are
# not reachable from here. What IS proven: every client correctly calls
# out to ANY object implementing the expected interface, correctly handles
# PERMIT/DENY/ACK/NACK responses, and correctly fails closed (not open) if
# no authority is attached. The reference implementations used for testing
# (CanonicalReplayAuthority, PersistentHistory from the governance-layer
# sprint) are local stand-ins for what would be Pritesh's/Kanishk's real
# systems in production — swapping them out is a single constructor argument,
# not a code change.

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

_ANCHOR = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _ts(seq: int) -> str:
    return (_ANCHOR + timedelta(seconds=seq * 60)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(d: str) -> str:
    return hashlib.sha256(d.encode("utf-8")).hexdigest()


class FederationUnavailableError(Exception):
    """Raised when a required federation dependency is not attached. Fails closed."""
    pass


# ── Replay Authority Client (consumes Pritesh's CanonicalReplayAuthority) ─────

class ReplayAuthorityClient:
    """
    Consumes a replay authority. Never decides replay legitimacy itself.
    Fails closed (DENY) if no authority is attached — this runtime does not
    self-authorize execution in the absence of governance.
    """

    def __init__(self, authority: Optional[Any] = None) -> None:
        self._authority = authority

    def attach(self, authority: Any) -> None:
        self._authority = authority

    def check(self, capability_id: str, payload: dict) -> dict:
        if self._authority is None:
            return {
                "decision": "DENY", "reason": "No replay authority attached — fail closed",
                "authority": "NONE", "capability_id": capability_id,
            }
        return self._authority.check(capability_id, payload)

    def is_attached(self) -> bool:
        return self._authority is not None


# ── Evidence Client (consumes Pritesh's Execution Evidence API) ───────────────

class EvidenceClient:
    """Pushes execution evidence to an injected ledger. Owns no legitimacy decision."""

    def __init__(self, ledger: Optional[Any] = None) -> None:
        self._ledger = ledger
        self._buffered: List[dict] = []

    def attach(self, ledger: Any) -> None:
        self._ledger = ledger

    def push(self, record: dict) -> dict:
        if self._ledger is None:
            self._buffered.append(record)
            return {"status": "BUFFERED_LOCALLY", "reason": "No evidence ledger attached"}
        result = self._ledger.append(record)
        return {"status": "PUSHED", "ledger_entry": result}

    def is_attached(self) -> bool:
        return self._ledger is not None

    def buffered_count(self) -> int:
        return len(self._buffered)


# ── Provenance Client (consumes Pritesh's Execution Provenance APIs) ──────────

class ProvenanceClient:
    """Pushes ExecutionRecord-shaped provenance data. Owns no provenance authority."""

    def __init__(self, provenance_api: Optional[Any] = None) -> None:
        self._api = provenance_api
        self._local_chain: List[dict] = []
        self._chain_hash: str = "0" * 64

    def attach(self, provenance_api: Any) -> None:
        self._api = provenance_api

    def record(self, capability_id: str, input_hash: str, output_hash: str, status: str) -> dict:
        record = {
            "capability_id": capability_id, "input_hash": input_hash,
            "output_hash": output_hash, "status": status,
        }
        if self._api is not None and hasattr(self._api, "record"):
            return self._api.record(record)
        # Local fallback chain — proves the client-side contract works even
        # without Pritesh's real provenance service attached.
        self._chain_hash = _sha256(f"{self._chain_hash}:{json.dumps(record, sort_keys=True)}")
        entry = {**record, "chain_hash": self._chain_hash}
        self._local_chain.append(entry)
        return {"status": "RECORDED_LOCAL_FALLBACK", "entry": entry}

    def is_attached(self) -> bool:
        return self._api is not None

    def local_chain(self) -> List[dict]:
        return list(self._local_chain)


# ── Capability Registry Client (registers with an external ecosystem registry) ─

class CapabilityRegistryClient:
    """
    Registers this runtime's capabilities with an external ecosystem-level
    registry (e.g. a future BHIV-wide registry spanning Kanishk's and
    Pritesh's runtimes too). Falls back to local-only registration.
    """

    def __init__(self, external_registry: Optional[Any] = None) -> None:
        self._external = external_registry
        self._registered_locally: List[dict] = []

    def attach(self, external_registry: Any) -> None:
        self._external = external_registry

    def register(self, descriptor: dict) -> dict:
        self._registered_locally.append(descriptor)
        if self._external is not None and hasattr(self._external, "register_capability"):
            try:
                self._external.register_capability(descriptor)
                return {"status": "REGISTERED_EXTERNAL", "descriptor_id": descriptor.get("capability_id")}
            except Exception as exc:
                return {"status": "EXTERNAL_REGISTRATION_FAILED", "error": str(exc),
                        "fallback": "LOCAL_ONLY"}
        return {"status": "REGISTERED_LOCAL_ONLY", "descriptor_id": descriptor.get("capability_id")}

    def is_attached(self) -> bool:
        return self._external is not None


# ── Health Client (publishes health to an external aggregator) ────────────────

class HealthClient:
    def __init__(self, external_health_sink: Optional[Any] = None) -> None:
        self._sink = external_health_sink

    def attach(self, sink: Any) -> None:
        self._sink = sink

    def publish(self, health_payload: dict) -> dict:
        if self._sink is not None and hasattr(self._sink, "ingest_health"):
            self._sink.ingest_health(health_payload)
            return {"status": "PUBLISHED_EXTERNAL"}
        return {"status": "NO_EXTERNAL_SINK", "payload": health_payload}

    def is_attached(self) -> bool:
        return self._sink is not None


# ── Execution Ledger Client ────────────────────────────────────────────────────

class ExecutionLedgerClient:
    """Consumes an external execution ledger. This runtime does not own ledger ordering."""

    def __init__(self, ledger: Optional[Any] = None) -> None:
        self._ledger = ledger

    def attach(self, ledger: Any) -> None:
        self._ledger = ledger

    def append(self, entry: dict) -> dict:
        if self._ledger is not None and hasattr(self._ledger, "append"):
            return self._ledger.append(entry)
        return {"status": "NO_EXTERNAL_LEDGER", "entry": entry}

    def is_attached(self) -> bool:
        return self._ledger is not None


# ── Execution Timeline Client ──────────────────────────────────────────────────

class ExecutionTimelineClient:
    """Publishes execution timeline events to an external timeline aggregator."""

    def __init__(self, timeline_sink: Optional[Any] = None) -> None:
        self._sink = timeline_sink
        self._local_timeline: List[dict] = []

    def attach(self, sink: Any) -> None:
        self._sink = sink

    def publish_event(self, event: dict) -> dict:
        self._local_timeline.append(event)
        if self._sink is not None and hasattr(self._sink, "ingest_event"):
            self._sink.ingest_event(event)
            return {"status": "PUBLISHED_EXTERNAL"}
        return {"status": "LOCAL_ONLY"}

    def is_attached(self) -> bool:
        return self._sink is not None

    def local_timeline(self, limit: Optional[int] = None) -> List[dict]:
        return self._local_timeline[-limit:] if limit else list(self._local_timeline)
