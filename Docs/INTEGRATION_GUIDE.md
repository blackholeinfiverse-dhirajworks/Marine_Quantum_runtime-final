# Docs/INTEGRATION_GUIDE.md
# Ecosystem Integration Guide
**Author:** Dhiraj Chavan | Marine Intelligence System | June 2026

This guide is for the three named integration partners in the ecosystem
brief. Each section states exactly what this runtime expects from your
system and exactly what code change (if any) is required on your side.

---

## For Kanishk — Deterministic Execution Engine

**What this runtime needs from you:** nothing structural. Your engine can
register as a quantum/classical execution provider via the same interface
every other provider uses.

**Integration path:**
1. Implement `QuantumExecutionProvider` and `QuantumExecutionBackend` in a
   new file, e.g. `src/quantum/providers/kanishk_engine_provider.py`.
2. Your `execute()` method receives a `CircuitSpec` and must return an
   `ExecutionResult` with the standardized shape (see `Docs/PROVIDER_MODEL.md`).
3. Call `provider_registry.register_provider(YourProvider())` once at
   startup.
4. Your engine is now reachable through `route_and_execute()`,
   `DistributedRuntimeManager`, and every observability/dashboard function
   in this repo — with zero changes to any file you don't own.

**Alternative — federation as a participant, not a provider:** if your
engine is better modeled as a federation peer rather than a quantum
backend, implement the minimal interface `FederationRuntime` expects:
`replay_authority.check(capability_id, payload) -> dict` and/or
`evidence_ledger.append(record) -> dict`. See `src/federation/federation_clients.py`
for the exact contract each client expects.

**What was proven this sprint:** the registration mechanism itself, using
a fictional test provider. Your actual engine has not been integrated —
that requires your code to exist and be reachable, which it is not from
this sandbox.

---

## For Pritesh — Quantum Execution Platform

**What this runtime needs from you:**
1. A real `CanonicalReplayAuthority` implementing `.check(capability_id, payload) -> dict`
   with `decision` of `PERMIT` or `DENY`, and ideally `.record_truth()` /
   `.replay()` for the verification proof this sprint demonstrates against
   the local reference implementation (`src/governance/replay_legitimacy.py`).
2. A real `EvidenceLedger` implementing `.append(record) -> dict`, ideally
   persistent (this sprint's local reference, `PersistentHistory`, writes
   append-only JSONL — your implementation can use any storage as long as
   `append()` matches the shape).
3. If your quantum execution platform should be reachable through this
   runtime's provider abstraction (rather than this runtime calling out to
   yours), follow the same `QuantumExecutionProvider` path described above
   for Kanishk.

**Attachment is a single call:**
```python
from src.federation.federation_runtime import FederationRuntime
fed = FederationRuntime(
    replay_authority=YourRealAuthority(),
    evidence_ledger=YourRealLedger(),
)
```
No other code in this repo changes. This sprint proves the attachment
mechanism works correctly against reference implementations with the exact
same shape your real systems would need to expose.

---

## For Raj — Execution Governance

**What this runtime needs from you:** a governance approval hook. This is
declared as `NOT IMPLEMENTED` honestly in `STUBS_REGISTRY.md` (governance
sprint) and remains so this sprint — there is no pre-approval check wired
into `invoke_capability()` or `FederationRuntime` yet.

**Proposed integration path (not yet built, scoped for next sprint):**
```python
class GovernanceApprovalHook:
    def approve(self, capability_id: str, payload: dict) -> dict:
        """Return {'approved': bool, 'reason': str}"""
```
Wired as an additional fail-closed check in `FederationRuntime.federated_execute()`,
immediately before the replay authority check — same dependency-injection
pattern as every other federation client.

**What governance authority this runtime explicitly does NOT claim:**
replay legitimacy, evidence legitimacy, execution ordering, dashboard
authority — all consumed, never decided, per the ecosystem brief's explicit
boundary. Every federation client in `src/federation/federation_clients.py`
is structurally incapable of self-authorizing; `ReplayAuthorityClient`
fails closed (`DENY`) when nothing is attached.

---

## For Vinayak — Independent Testing

Run:
```bash
python run/run_ecosystem_integration.py
```
Expect exit code 0 and `24/24` checks passed. The script produces:
- Provider switching proof (Phase 7.1)
- Backend failover proof (Phase 7.2)
- Determinism validation across two real backends (Phase 7.3)
- Honest simulation-vs-hardware boundary proof (Phase 7.4)
- Real performance benchmark — classical simulation only (Phase 7.5)
- Failure injection + recovery (Phase 7.6)
- Distributed execution across 3 nodes (Phase 7.7)
- Federation fail-closed and live proof (Phase 7.8)
- Independent replay verification, including tamper detection (Phase 7.9)
- Observability v2 + dashboard telemetry proof (Phase 7.10)

Raw console output for every run is captured in `review_packets/screenshots/`
as `.txt` files — see the README there for why these are text captures, not
image screenshots, and what's still needed for the literal screenshot
deliverable.
