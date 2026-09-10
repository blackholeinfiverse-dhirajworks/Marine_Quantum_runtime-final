# Capability Attachment Doctrine
**Author:** Dhiraj Chavan | Marine Intelligence System  
**Version:** 1.0.0

---

## Core Rule

**attachment ≠ ownership transfer.**

Registering a capability descriptor grants visibility into what a module can do. It does not transfer governance authority, execution priority, or causal ordering control.

---

## Attachment Modes

| Mode | Description | When to Use |
|---|---|---|
| `embedded` | Descriptor is bundled inside the module; co-deployed by default | Core modules that always ship together |
| `sidecar` | Descriptor registered separately; module runs alongside but independently | Monitoring, telemetry, drift detection |
| `runtime_participant` | Descriptor participates in shared runtime contract; module receives invocation events | Any module that needs to act on runtime state |
| `optional_extension` | May or may not be present; runtime adapts gracefully if absent | Experimental or environment-specific capabilities |
| `api_linked` | Descriptor registered via external API; module lives outside this runtime boundary | Cross-team or cross-repo integration |

---

## Descriptor Lifecycle

```
1. AUTHORED      — QAppDescriptor constructed by module author
2. VALIDATED     — DescriptorRegistry checks for violations
3. REGISTERED    — Descriptor added to registry (append-only)
4. CONSUMED      — Runtime queries registry before invocation
5. READ-ONLY     — No mutation after registration
```

Once registered, a descriptor is immutable. Re-registration with a changed `descriptor_hash` raises `DescriptorRegistrationError`.

---

## Authority Ceilings

| Ceiling | What Is Permitted | What Is NOT Permitted |
|---|---|---|
| `READ_ONLY` | Query registry, consume events | Emit signals, invoke runtime |
| `SIGNAL_EMIT` | All above + emit state signals | Invoke or govern runtime |
| `RUNTIME_PARTICIPATE` | All above + participate in shared runtime contract | Govern execution order |
| `RUNTIME_GOVERN` | All above + set execution policy | N/A — highest ceiling |

**Escalation rule:** A module may never exceed its declared `authority_ceiling` within a session. Escalation requires re-registration with explicit governance approval.

---

## Negative Authority Declarations

Every `QAppDescriptor` carries explicit prohibitions. These are not suggestions — they are contract terms enforceable by callers.

Example for `marine_corrosion_qapp`:
```
marine_corrosion_qapp MAY NOT silently govern runtime execution order.
marine_corrosion_qapp MAY NOT escalate authority_ceiling beyond 'RUNTIME_PARTICIPATE' without re-registration.
marine_corrosion_qapp MAY NOT override FailureContract semantics.
marine_corrosion_qapp MAY NOT claim classical determinism for quantum sampling outputs.
```

---

## Schema Compatibility

Each descriptor declares a `schema_compatibility` range (e.g. `>=1.0.0,<2.0.0`). Consumers must verify compatibility before using descriptor fields.

Compatibility rules:
- Minor bumps (1.0.x → 1.1.0): additive only, backward compatible.
- Major bumps (1.x.x → 2.0.0): breaking change, requires explicit consumer upgrade.
