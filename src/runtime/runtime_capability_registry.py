# src/runtime/runtime_capability_registry.py
# Runtime Capability Registry — Marine Intelligence System
# UPDATED: dependency graph validation + typed attachment validation
#
# PUBLIC API:
#   register_capability(descriptor) -> None
#   discover_capability(capability_id) -> CapabilityDescriptor
#   list_capabilities() -> list[dict]
#   validate_attachment(capability_id, inputs) -> dict  ← NOW TYPED
#   validate_dependency_graph(capability_id) -> dict    ← NEW
#   get_capability_health(capability_id) -> dict
#   get_registry_summary() -> dict

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Exceptions ────────────────────────────────────────────────────────────────

class RegistryError(Exception):
    pass


class CapabilityNotFound(RegistryError):
    pass


class DependencyError(RegistryError):
    """Raised when a capability's declared dependencies are not satisfied."""
    pass


# ── Descriptor ────────────────────────────────────────────────────────────────

@dataclass
class CapabilityDescriptor:
    capability_id:      str
    owner:              str
    version:            str
    capability_class:   str
    inputs:             List[str]
    outputs:            List[str]
    dependencies:       List[str]
    authority_ceiling:  str
    negative_authority: List[str]
    description:        str = ""

    def descriptor_id(self) -> str:
        seed = f"{self.capability_id}:{self.owner}:{self.version}:{self.capability_class}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "capability_id":      self.capability_id,
            "owner":              self.owner,
            "version":            self.version,
            "capability_class":   self.capability_class,
            "inputs":             self.inputs,
            "outputs":            self.outputs,
            "dependencies":       self.dependencies,
            "authority_ceiling":  self.authority_ceiling,
            "negative_authority": self.negative_authority,
            "description":        self.description,
            "descriptor_id":      self.descriptor_id(),
        }


# ── Health tracker ─────────────────────────────────────────────────────────────

@dataclass
class CapabilityHealth:
    capability_id:    str
    invocation_count: int = 0
    success_count:    int = 0
    failure_count:    int = 0
    last_status:      str = "UNKNOWN"
    last_error:       Optional[str] = None

    def record_success(self) -> None:
        self.invocation_count += 1
        self.success_count    += 1
        self.last_status       = "SUCCESS"
        self.last_error        = None

    def record_failure(self, error: str) -> None:
        self.invocation_count += 1
        self.failure_count    += 1
        self.last_status       = "FAILED"
        self.last_error        = error

    def health_status(self) -> str:
        if self.invocation_count == 0:
            return "IDLE"
        if self.failure_count == 0:
            return "HEALTHY"
        ratio = self.failure_count / self.invocation_count
        return "DEGRADED" if ratio < 0.1 else "UNHEALTHY"

    def to_dict(self) -> dict:
        return {
            "capability_id":    self.capability_id,
            "invocation_count": self.invocation_count,
            "success_count":    self.success_count,
            "failure_count":    self.failure_count,
            "last_status":      self.last_status,
            "last_error":       self.last_error,
            "health_status":    self.health_status(),
        }


# ── Registry ──────────────────────────────────────────────────────────────────

class RuntimeCapabilityRegistry:

    def __init__(self) -> None:
        self._descriptors: Dict[str, CapabilityDescriptor] = {}
        self._health:      Dict[str, CapabilityHealth]     = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, descriptor: CapabilityDescriptor) -> None:
        cid = descriptor.capability_id
        if cid in self._descriptors:
            raise RegistryError(
                f"Capability '{cid}' already registered. "
                "De-register first or use a new version string."
            )
        if not descriptor.negative_authority:
            raise RegistryError(
                f"Capability '{cid}' must declare at least one negative_authority entry."
            )
        self._descriptors[cid] = descriptor
        self._health[cid]      = CapabilityHealth(capability_id=cid)

    def deregister(self, capability_id: str) -> None:
        if capability_id not in self._descriptors:
            raise CapabilityNotFound(f"Cannot deregister unknown capability '{capability_id}'.")
        del self._descriptors[capability_id]
        del self._health[capability_id]

    # ── Discovery ─────────────────────────────────────────────────────────────

    def discover(self, capability_id: str) -> CapabilityDescriptor:
        if capability_id not in self._descriptors:
            available = sorted(self._descriptors.keys())
            raise CapabilityNotFound(
                f"Capability '{capability_id}' not found. Registered: {available}"
            )
        return self._descriptors[capability_id]

    def list_capabilities(self) -> List[dict]:
        return [d.to_dict() for d in self._descriptors.values()]

    # ── Dependency Graph Validation (NEW) ─────────────────────────────────────

    def validate_dependency_graph(self, capability_id: str) -> dict:
        """
        Verify that all declared dependencies of a capability are registered.
        Returns {valid, missing_dependencies, resolved}.
        
        Fixes: discover_capability() was returning descriptors without
        confirming their dependencies were available.
        """
        try:
            desc = self.discover(capability_id)
        except CapabilityNotFound as exc:
            return {"valid": False, "missing_dependencies": [], "resolved": [],
                    "error": str(exc)}
        missing  = []
        resolved = []
        for dep in desc.dependencies:
            if dep in self._descriptors:
                resolved.append(dep)
            else:
                missing.append(dep)
        return {
            "valid":                len(missing) == 0,
            "capability_id":        capability_id,
            "declared_dependencies": desc.dependencies,
            "resolved":             resolved,
            "missing_dependencies": missing,
        }

    def validate_dependency_graph_all(self) -> dict:
        """Validate dependency graph for every registered capability."""
        results  = {}
        all_ok   = True
        for cid in self._descriptors:
            result = self.validate_dependency_graph(cid)
            results[cid] = result
            if not result["valid"]:
                all_ok = False
        return {"all_valid": all_ok, "results": results}

    # ── Typed Attachment Validation (UPDATED) ─────────────────────────────────

    def validate_attachment(self, capability_id: str, inputs: dict) -> dict:
        """
        Full typed validation of attachment inputs.
        Checks types and bounds, not only key presence.
        
        Uses src/contracts/typed_attachment.validate_typed() when a schema exists.
        Falls back to key-presence check when no schema is registered.
        """
        desc = self.discover(capability_id)

        # Prefer typed schema if available
        try:
            from src.contracts.typed_attachment import validate_typed
            typed_result = validate_typed(capability_id, inputs)
            return {
                "valid":         typed_result["valid"],
                "missing":       typed_result.get("missing", []),
                "type_errors":   typed_result.get("errors", []),
                "capability_id": capability_id,
                "version":       desc.version,
                "validation":    "TYPED",
            }
        except ImportError:
            pass

        # Fallback: key-presence only (legacy)
        missing = [k for k in desc.inputs if k not in inputs]
        return {
            "valid":         len(missing) == 0,
            "missing":       missing,
            "type_errors":   [],
            "capability_id": capability_id,
            "version":       desc.version,
            "validation":    "KEY_PRESENCE_ONLY",
        }

    # ── Capability Hot Attach / Detach (NEW) ──────────────────────────────────

    def hot_attach(self, descriptor: CapabilityDescriptor) -> dict:
        """
        Attach a capability at runtime without restarting.
        If already registered with same descriptor_id, returns idempotent OK.
        If registered with different descriptor_id, raises RegistryError.
        """
        cid = descriptor.capability_id
        if cid in self._descriptors:
            existing_id = self._descriptors[cid].descriptor_id()
            new_id      = descriptor.descriptor_id()
            if existing_id == new_id:
                return {"status": "IDEMPOTENT", "capability_id": cid,
                        "note":   "Same descriptor already registered"}
            raise RegistryError(
                f"Cannot hot-attach '{cid}': already registered with different descriptor_id. "
                "Deregister first."
            )
        self.register(descriptor)
        return {"status": "ATTACHED", "capability_id": cid,
                "descriptor_id": descriptor.descriptor_id()}

    def hot_detach(self, capability_id: str) -> dict:
        """Remove a capability at runtime. Confirms removal."""
        if capability_id not in self._descriptors:
            raise CapabilityNotFound(
                f"Cannot hot-detach '{capability_id}': not registered."
            )
        self.deregister(capability_id)
        return {"status": "DETACHED", "capability_id": capability_id}

    # ── Version Negotiation (NEW) ─────────────────────────────────────────────

    def negotiate_version(
        self, capability_id: str, consumer_version: str
    ) -> dict:
        """
        Check whether the registered capability version is compatible
        with what a consumer requires.
        
        Compatibility rule: major versions must match.
        """
        desc = self.discover(capability_id)
        try:
            reg_major  = int(desc.version.split(".")[0])
            con_major  = int(consumer_version.split(".")[0])
            compatible = reg_major == con_major
        except (ValueError, IndexError):
            return {
                "compatible":          False,
                "capability_id":       capability_id,
                "registered_version":  desc.version,
                "consumer_version":    consumer_version,
                "reason":              "Could not parse version strings",
            }
        return {
            "compatible":         compatible,
            "capability_id":      capability_id,
            "registered_version": desc.version,
            "consumer_version":   consumer_version,
            "reason":             "Major versions match" if compatible else
                                  f"Major version mismatch: registered={reg_major} consumer={con_major}",
        }

    # ── Conflict Detection (NEW) ──────────────────────────────────────────────

    def detect_conflicts(self) -> dict:
        """
        Scan all registered capabilities for authority conflicts.
        A conflict exists when a capability's declared actions overlap
        with another capability's negative authority.
        """
        conflicts = []
        cap_list  = list(self._descriptors.values())
        for i, cap_a in enumerate(cap_list):
            for cap_b in cap_list[i + 1:]:
                # Check if cap_a's outputs appear in cap_b's negative authority
                for neg in cap_b.negative_authority:
                    for out in cap_a.outputs:
                        if out.lower() in neg.lower():
                            conflicts.append({
                                "source":    cap_a.capability_id,
                                "target":    cap_b.capability_id,
                                "conflict":  f"'{cap_a.capability_id}' outputs '{out}' "
                                             f"which '{cap_b.capability_id}' negatively declares: '{neg}'",
                            })
        return {
            "conflict_count": len(conflicts),
            "conflicts":      conflicts,
            "status":         "CLEAN" if not conflicts else "CONFLICTS_DETECTED",
        }

    # ── Health ────────────────────────────────────────────────────────────────

    def get_health(self, capability_id: str) -> dict:
        if capability_id not in self._health:
            raise CapabilityNotFound(f"No health record for '{capability_id}'.")
        return self._health[capability_id].to_dict()

    def record_invocation_result(
        self, capability_id: str, success: bool, error: Optional[str] = None
    ) -> None:
        if capability_id not in self._health:
            raise CapabilityNotFound(
                f"Cannot record for unknown capability '{capability_id}'."
            )
        if success:
            self._health[capability_id].record_success()
        else:
            self._health[capability_id].record_failure(error or "unknown error")

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_registry_summary(self) -> dict:
        health_all     = {cid: h.to_dict() for cid, h in self._health.items()}
        overall_healthy = sum(
            1 for h in self._health.values()
            if h.health_status() in ("HEALTHY", "IDLE")
        )
        dep_graph = self.validate_dependency_graph_all()
        conflicts = self.detect_conflicts()
        return {
            "registered_count":  len(self._descriptors),
            "healthy_count":     overall_healthy,
            "capabilities":      self.list_capabilities(),
            "health":            health_all,
            "registry_health":   "HEALTHY" if overall_healthy == len(self._descriptors)
                                 else "DEGRADED",
            "dependency_graph":  dep_graph,
            "conflicts":         conflicts,
        }


# ── Module-Level Singleton ────────────────────────────────────────────────────

_REGISTRY = RuntimeCapabilityRegistry()


def register_capability(descriptor: CapabilityDescriptor) -> None:
    _REGISTRY.register(descriptor)


def discover_capability(capability_id: str) -> CapabilityDescriptor:
    return _REGISTRY.discover(capability_id)


def list_capabilities() -> List[dict]:
    return _REGISTRY.list_capabilities()


def get_capability_health(capability_id: str) -> dict:
    return _REGISTRY.get_health(capability_id)


def validate_attachment(capability_id: str, inputs: dict) -> dict:
    return _REGISTRY.validate_attachment(capability_id, inputs)


def validate_dependency_graph(capability_id: str) -> dict:
    return _REGISTRY.validate_dependency_graph(capability_id)


def validate_dependency_graph_all() -> dict:
    return _REGISTRY.validate_dependency_graph_all()


def negotiate_version(capability_id: str, consumer_version: str) -> dict:
    return _REGISTRY.negotiate_version(capability_id, consumer_version)


def detect_conflicts() -> dict:
    return _REGISTRY.detect_conflicts()


def hot_attach(descriptor: CapabilityDescriptor) -> dict:
    return _REGISTRY.hot_attach(descriptor)


def hot_detach(capability_id: str) -> dict:
    return _REGISTRY.hot_detach(capability_id)


def record_invocation_result(
    capability_id: str, success: bool, error: Optional[str] = None
) -> None:
    _REGISTRY.record_invocation_result(capability_id, success, error)


def get_registry_summary() -> dict:
    return _REGISTRY.get_registry_summary()


# ── Built-In Capability Descriptors ──────────────────────────────────────────

_BUILTIN_CAPABILITIES = [
    CapabilityDescriptor(
        capability_id     = "signal",
        owner             = "Dhiraj Chavan",
        version           = "4.0.0",
        capability_class  = "SIGNAL",
        inputs            = ["node_id", "energy_delta", "iterations", "confidence", "variance"],
        outputs           = ["engine_event_version", "node_ref", "transition", "uncertainty_envelope"],
        dependencies      = [],
        authority_ceiling = "STATE_CLASSIFICATION",
        negative_authority = [
            "Must not enforce execution policy",
            "Must not control causal ordering",
            "Must not perform replay decisions",
            "Must not write to any external store",
        ],
        description = "Quantum node state signal generator.",
    ),
    CapabilityDescriptor(
        capability_id     = "quantum_pipeline",
        owner             = "Dhiraj Chavan",
        version           = "1.0.0",
        capability_class  = "QUANTUM",
        inputs            = ["salinity", "temperature_celsius", "pH",
                             "material_oxidation_potential", "dissolved_oxygen_mgl",
                             "current_density_mAcm2"],
        outputs           = ["degradation_probability", "confidence_score",
                             "recommended_anode_current", "deterministic_event"],
        dependencies      = [],
        authority_ceiling = "QUANTUM_EXECUTION",
        negative_authority = [
            "Must not make autonomous hull maintenance decisions",
            "Must not override governance layer",
            "Must not perform provenance recording",
            "Must not control replay authority",
        ],
        description = "Marine corrosion quantum pipeline via HEA circuit.",
    ),
    CapabilityDescriptor(
        capability_id     = "distributed_qapp",
        owner             = "Dhiraj Chavan / Jaffer Ali",
        version           = "1.0.0",
        capability_class  = "DISTRIBUTED",
        inputs            = ["qapp_id", "node_origin", "sequence_id", "data"],
        outputs           = ["consistent", "consensus_hash", "log_hash", "envelope"],
        dependencies      = ["signal"],
        authority_ceiling = "DISTRIBUTED_PROPAGATION",
        negative_authority = [
            "Must not own replay authority",
            "Must not make optimization decisions",
            "Must not govern execution legitimacy",
            "Must not act as provenance authority",
        ],
        description = "3-node distributed QApp propagation runtime.",
    ),
    CapabilityDescriptor(
        capability_id     = "operational_monitor",
        owner             = "Dhiraj Chavan",
        version           = "1.0.0",
        capability_class  = "MONITORING",
        inputs            = ["events"],
        outputs           = ["events_ingested", "drift_events", "nodes_monitored", "drift_log"],
        dependencies      = ["signal"],
        authority_ceiling = "OBSERVABILITY",
        negative_authority = [
            "Must not trigger remediation actions autonomously",
            "Must not own execution governance",
            "Must not persist drift logs to external systems",
            "Must not control operational schedules",
        ],
        description = "Operational drift monitor — confidence, variance, state-shift detection.",
    ),
]

for _cap in _BUILTIN_CAPABILITIES:
    _REGISTRY.register(_cap)
