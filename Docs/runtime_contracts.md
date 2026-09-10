# Runtime Contracts — Marine Intelligence System
**Author:** Dhiraj Chavan | BHIV Core / TANTRA Ecosystem  
**Schema Version:** 1.0.0  
**Date:** June 2026

---

## Purpose

This document defines the canonical runtime contract layer for the TANTRA hybrid runtime. A **contract** is an explicit, versioned declaration of what a module guarantees, what it does not guarantee, what is deterministic, and who owns what.

Contracts exist at every runtime boundary. Nothing crosses a boundary without one.

---

## Contracts Defined

### 1. `ModuleDescriptorContract`

Declares module identity, capability class, and authority ceiling.

**What is guaranteed:**
- `module_name` is immutable after registration.
- `capability_class` is one of `CLASSICAL`, `QUANTUM`, `HYBRID`.
- `authority_ceiling` is explicitly declared and enforced by the caller.
- `descriptor_id` is SHA-256 of `(module_name + schema_version + capability_class)` — always deterministic.
- Negative authority declarations are always present and non-empty.

**What is NOT guaranteed:**
- That the described module is actually running at time of consumption.
- That the declared quantum capability is available on the executing hardware.
- Forward compatibility beyond schema_version (additive evolution only).

**What is deterministic:**
- `descriptor_id` — same inputs always produce the same ID.

**Caller responsibility:**
- Must verify `capability_class` matches participation requirements before invocation.
- Must not assume authority beyond `authority_ceiling`.
- Must check `schema_version` before consuming descriptor fields.

---

### 2. `RuntimeRequest`

Canonical invocation envelope entering the TANTRA runtime.

**What is guaranteed:**
- `request_id` is SHA-256 of `(module_name + seq + sha256(payload))` — deterministic.
- `timestamp_posture` is always `"DETERMINISTIC"` — no wall-clock time in IDs.
- `ContractViolation` is raised on construction if required fields are missing or invalid.
- Payload is shallow-copied on construction — caller mutation does not affect the request.

**What is NOT guaranteed:**
- Semantic validity of payload content for the target module (that is the target module's responsibility).
- Fulfillment within any time bound.
- That `request_id` uniqueness holds if caller reuses the same `(module_name, seq, payload)` tuple — by design, same inputs → same ID.

**What is deterministic:**
- `request_id` — fully deterministic on inputs.

**Caller responsibility:**
- Must provide monotonically increasing `seq` per module.
- Must not mutate payload after constructing `RuntimeRequest`.
- Must provide a valid `participant_class` (`CLASSICAL`, `QUANTUM`, or `HYBRID`).

---

### 3. `RuntimeResponse`

Canonical result envelope leaving the TANTRA runtime.

**What is guaranteed:**
- `response_id` is SHA-256 of `(request_id + execution_status + sha256(result))` — deterministic.
- `execution_status` is one of `SUCCESS`, `FAILURE`, `PARTIAL`.
- If `execution_status == FAILURE`, `result` is `None` and `failure_contract` is set.
- `determinism_metadata` is always present with `category`, `posture`, and `chain_hash`.

**What is NOT guaranteed:**
- Execution latency bounds.
- That result content will be consumed by any downstream module.
- `PARTIAL` results are complete or safe to act on autonomously.

**What is deterministic:**
- `response_id` — deterministic on `(request_id, execution_status, result content)`.
- `determinism_metadata.chain_hash` — links to `response_id` for audit continuity.

**Caller responsibility:**
- Must check `execution_status` before consuming `result`.
- Must not assume `result` is non-None when `execution_status == FAILURE`.
- Must propagate `failure_contract` — never silently discard.

---

### 4. `FailureContract`

Structured failure descriptor. Emitted whenever a module cannot fulfil its contract.

**What is guaranteed:**
- `error_class` is non-empty.
- `message` is human-readable.
- `halt_formatted` is a `[HALT]`-prefixed string suitable for audit logs.
- `recoverable` flag is explicitly set by the failing module.

**What is NOT guaranteed:**
- That recovery is possible, regardless of `recoverable=True`.
- That the same failure won't recur on retry.

**Caller responsibility:**
- Must log or propagate `halt_formatted` — never silently discard.
- Must not retry without inspecting `recoverable`.

---

## Determinism Categories

| Category | Definition | Proof Method |
|---|---|---|
| `SEED` | Same seed → same output | Re-run with identical seed, diff outputs |
| `SIMULATION` | Same state → same simulation result | Replay identical state vector |
| `RUNTIME` | Same inputs → same invocation result | 5-run proof pattern |
| `CONTRACT` | Contract field values are deterministic on inputs | SHA-256 ID audit |
| `OBSERVABILITY` | Log/trace content is deterministic | Log diff across runs |
| `DISTRIBUTED` | Distributed execution produces consistent results | Cross-node hash comparison |
| `NONE` | Explicitly non-deterministic (e.g. hardware quantum sampling) | Documented exception |

---

## Schema Evolution Rules

1. Fields may be **added** in minor versions (additive evolution).
2. Fields may **never be removed** without a major version bump.
3. `schema_version` must be checked by consumers before using optional fields.
4. Breaking changes require a new contract class, not mutation of an existing one.

---

## Authority Ceiling Hierarchy

```
READ_ONLY
    ↓
SIGNAL_EMIT
    ↓
RUNTIME_PARTICIPATE
    ↓
RUNTIME_GOVERN          ← requires explicit escalation; never assumed
```

A module may never exceed its declared `authority_ceiling`. Callers enforce this.

---

## Known Limitations (v1.0.0)

- Contracts are validated at Python object construction time; no wire-format schema registry exists yet.
- `ModuleDescriptorContract` does not verify that the described module is actually loadable.
- `RuntimeRequest` payload shallow-copy does not protect against nested mutable objects.
- No cryptographic signing of contracts (planned for v1.1.0).
