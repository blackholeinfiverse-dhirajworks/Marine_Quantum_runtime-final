# src/federation/federation_runtime.py
# Federation Runtime — orchestrates all federation clients on every execution.
#
# This is the "live ecosystem participant" referenced in Phase 2. It is
# proven LIVE against the reference implementations from the governance
# sprint (CanonicalReplayAuthority, PersistentHistory) — see the honest
# declaration in federation_clients.py for exactly what "live" means here
# versus what would require Kanishk's/Pritesh's/Raj's actual running systems.

import hashlib
import json
from typing import Any, Dict, Optional

from src.federation.federation_clients import (
    ReplayAuthorityClient, EvidenceClient, ProvenanceClient,
    CapabilityRegistryClient, HealthClient, ExecutionLedgerClient,
    ExecutionTimelineClient,
)


def _sha256(d: str) -> str:
    return hashlib.sha256(d.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class FederationRuntime:
    """
    Wires together every federation client. A capability execution that
    flows through this class is checked against replay authority, has
    evidence pushed, provenance recorded, and timeline events published —
    using whatever is attached, failing closed when nothing is attached.
    """

    def __init__(
        self,
        replay_authority: Optional[Any] = None,
        evidence_ledger:  Optional[Any] = None,
        provenance_api:   Optional[Any] = None,
        capability_registry: Optional[Any] = None,
        health_sink:      Optional[Any] = None,
        execution_ledger: Optional[Any] = None,
        timeline_sink:    Optional[Any] = None,
    ) -> None:
        self.replay     = ReplayAuthorityClient(replay_authority)
        self.evidence   = EvidenceClient(evidence_ledger)
        self.provenance = ProvenanceClient(provenance_api)
        self.registry   = CapabilityRegistryClient(capability_registry)
        self.health     = HealthClient(health_sink)
        self.ledger     = ExecutionLedgerClient(execution_ledger)
        self.timeline   = ExecutionTimelineClient(timeline_sink)
        self._seq = 0

    def attachment_status(self) -> dict:
        return {
            "replay_authority":    self.replay.is_attached(),
            "evidence_ledger":     self.evidence.is_attached(),
            "provenance_api":      self.provenance.is_attached(),
            "capability_registry": self.registry.is_attached(),
            "health_sink":         self.health.is_attached(),
            "execution_ledger":    self.ledger.is_attached(),
            "timeline_sink":       self.timeline.is_attached(),
        }

    def federated_execute(
        self, capability_id: str, payload: dict, execute_fn
    ) -> dict:
        """
        Runs execute_fn(payload) only after replay authority PERMITs.
        Pushes evidence, records provenance, publishes timeline events
        regardless of outcome. execute_fn must return a dict result.
        """
        self._seq += 1

        replay_decision = self.replay.check(capability_id, payload)
        self.timeline.publish_event({
            "event": "REPLAY_CHECK", "seq": self._seq,
            "capability_id": capability_id, "decision": replay_decision.get("decision"),
        })

        if replay_decision.get("decision") != "PERMIT":
            self.evidence.push({
                "capability_id": capability_id, "status": "REPLAY_DENIED",
                "payload_hash": _sha256(_canonical(payload)),
            })
            return {
                "status": "REPLAY_DENIED", "capability_id": capability_id,
                "replay_decision": replay_decision, "result": None,
            }

        try:
            result = execute_fn(payload)
            status = "SUCCESS"
            error  = None
        except Exception as exc:
            result = None
            status = "EXECUTION_FAILED"
            error  = str(exc)

        input_hash  = _sha256(_canonical(payload))
        output_hash = _sha256(_canonical(result)) if result is not None else ""

        self.evidence.push({
            "capability_id": capability_id, "status": status,
            "payload_hash": input_hash, "output_hash": output_hash, "error": error,
        })
        prov = self.provenance.record(capability_id, input_hash, output_hash, status)
        self.timeline.publish_event({
            "event": "EXECUTION_COMPLETE", "seq": self._seq,
            "capability_id": capability_id, "status": status,
        })

        return {
            "status":           status,
            "capability_id":    capability_id,
            "replay_decision":  replay_decision,
            "result":           result,
            "error":            error,
            "provenance":       prov,
        }
