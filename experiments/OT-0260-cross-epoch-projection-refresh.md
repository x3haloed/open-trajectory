# OT-0260 — cross-epoch projection refresh

- **Status:** promoted
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0259 subject `5c680025...`
- **Fresh actors:** zero

## Prediction error

**Expected:** the compact opportunity projection would remain an active aid as
the subject waited, woke, and entered another epoch. **Observed:** after successful
post-wait contact and correction, the active projection still names the saturated
resilience epoch while the latest coordination epoch has two unledgered public
surfaces. **Uncertain:** whether a generic freshness guard and deterministic
refresh are sufficient to keep selector state aligned without actor or researcher
target choice. **Evidence:** exact OT-0259 successor `5c680025...`.

## Frozen hypothesis and gates

A generic pre-selector freshness guard over latest epoch identity, visible-source
digest, and ledger digest can route stale state to projection refresh before any
actor is authorized. The existing AST resolver must then derive exactly the two
unledgered coordination opportunities and keep selection, world, scoring, and
admission authority false.

Promotion requires held-out detection of epoch, source, ledger, and missing-
projection staleness; no refresh for exact current descriptors; fail-closed
malformed source; exact agreement with the active-epoch resolver; zero actors;
unchanged operational, wait/wake, and provider state; an open successor whose
next operation is `expanded-select`; and retained routing and identity floors.

## Result

All freshness fixtures passed. The guard detected the live epoch mismatch plus
held-out source, ledger, and missing-projection changes; exact fresh state did
not refresh; malformed source failed closed. The generic resolver derived
exactly the two unledgered coordination surfaces.

Zero-actor successor `c319bade...` preserves operational, provider, and wait/wake
state, carries a current non-authoritative projection, and is open with
`expanded-select` next. The stale-projection prediction error is resolved;
behavioral use by a fresh actor remains unclaimed.
