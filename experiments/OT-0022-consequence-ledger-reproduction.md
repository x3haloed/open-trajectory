# OT-0022 — Consequence-ledger feasibility reproduction

- **Status:** implementation freeze pending; actor output forbidden
- **Evidence class:** exploratory-only
- **Target authority:** none; development feasibility only
- **Predecessor:** OT-0021 failed consequence-ledger pilot

## Hypothesis and sole measurement correction

OT-0021's two fresh actors passed the complete mechanism slice, but the frozen
aggregator treated three repeated proxy receipt events for each Response as six
Response identities. A fresh reproduction should pass when identity is measured
at the actor-turn boundary: exactly one identity per turn, distinct identities
across turns, and no proxy identity outside that two-element set.

This is a new experiment, not a rescore or repair of OT-0021. It uses a fresh
public task whose labels depend on a different feature, fresh actor threads and
workspaces, and a new run lock. The consequence ledger, generic expression
carrier, prompt, null control, deterministic predictor, paired receipt,
credit-neutralization rule, +4 error gate, model, inventories, and resource
limits remain unchanged.

## Cheapest falsifier, controls, and gate

Before hosted output, structural tests must prove that the fresh sealed pilot
split is absent from the rendered prompt, the completed receipt replays, the
known generic challenger gains six errors, and repeated proxy events with two
valid per-turn identities satisfy the corrected rule. Any leak, authority,
schema, budget, or deterministic replay failure rejects the implementation.

Then exactly two fresh Luna encounters run under one receipted epoch. Both must
independently produce a bounded deterministic challenger with at least four
errors of advantage, a true-credit challenger choice, a neutralized current
choice, changed committed selector identity, zero tools, exact model and stable
inventory receipts, distinct Response identities, singular catalog ETag, zero
collector errors, and frozen token/time bounds. Tests and privacy audit remain
part of the gate.

## Claim limit and freeze boundary

A pass establishes only public non-candidate carrier feasibility. It does not
promote OT-1, renew E4, or authorize a private candidate. Actor output remains
forbidden until a clean implementation commit and separate run-lock commit bind
every task, mechanism, evaluator, deployment, and evidence-lineage authority.
After output, OT-0022 passes or fails as written.

## Results and decision

Pending frozen public reproduction.

## Evidence manifest

Pending.
