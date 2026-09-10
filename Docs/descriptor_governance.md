# Descriptor Governance — Marine Intelligence System
**Author:** Dhiraj Chavan | BHIV Core / TANTRA Ecosystem  
**Version:** 1.0.0

---

## Registration Rules

1. Each `qapp_id` may only be registered once per session.
2. Re-registration with the same `descriptor_hash` is a no-op (idempotent).
3. Re-registration with a different `descriptor_hash` raises `DescriptorRegistrationError`.
4. The registry is append-only — no deletion or overwrite within a session.

---

## Lifecycle

```
AUTHORED
  ↓  QAppDescriptor constructed
VALIDATED
  ↓  DescriptorRegistry checks capability_class, attachment_mode, authority_ceiling
REGISTERED
  ↓  descriptor_hash computed; registered=True
CONSUMED
  ↓  invoke_runtime.py queries registry before invocation
READ-ONLY
     No mutation after registration
```

---

## Pre-Registered Descriptors (v1.0.0)

| qapp_id | capability_class | attachment_mode | authority_ceiling |
|---|---|---|---|
| `marine_corrosion_qapp` | QUANTUM | runtime_participant | RUNTIME_PARTICIPATE |
| `classical_drift_monitor` | CLASSICAL | sidecar | RUNTIME_PARTICIPATE |
| `hybrid_hull_participant` | HYBRID | runtime_participant | RUNTIME_PARTICIPATE |

---

## Negative Authority Declarations — Why They Exist

Every descriptor carries explicit prohibitions. This is not documentation — it is a contract term. Callers must check negative declarations before invoking.

Example: `marine_corrosion_qapp MAY NOT claim classical determinism for quantum sampling outputs.`

This prevents callers from treating quantum simulation output as runtime-deterministic when it is only simulation-deterministic (seed-dependent).

---

## Schema Compatibility

Each descriptor declares `schema_compatibility` (e.g. `>=1.0.0`). Consumers must check this field before using optional descriptor fields introduced in minor versions.

---

## Dependency Declaration

Descriptors declare their dependencies (other `qapp_id` values they depend on). The registry does not auto-resolve dependencies — it records them. Callers are responsible for ensuring all declared dependencies are registered before invocation.

`hybrid_hull_participant` depends on `marine_corrosion_qapp` and `classical_drift_monitor`. Both must be registered before `invoke_hybrid_runtime()` is called.
