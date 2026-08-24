# OT-0022 — Consequence-ledger feasibility reproduction

- **Status:** failed; receipt correction valid, mechanism not reproduced
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

The clean protocol and implementation commit is
`b8a8ace5dc2988f7c747689615efa057734e9461`.
`spec/ot-0022-run-lock.json` binds it and every runtime authority before the
first hosted actor output.

## Results and decision

The frozen response-identity correction passed. Each actor turn receipted
exactly one Response identity, the two identities were distinct, and the six
proxy receipt events contained only those identities. Model, inventory, ETag,
collector, freshness, parse, tool, resource, test, and audit gates all passed.

The mechanism gate failed. Actor 1 authored a changed deterministic selector
that gained six errors, committed under true credit, and lost the commit under
credit neutralization. Actor 2 changed selection but retained six examples from
only the positive label/feature side of the public relation. That removed the
contrast needed by the deterministic predictor, produced zero advantage, and
caused its prospective rule to keep current. This was a correct controller
decision but not the required useful challenger.

Final disposition: `failed`. The consequence ledger can support useful
selector invention, but a single one-shot whole-program challenger was not
reliable across the two fresh actors and two public feature relations. OT-0022
is not retried or relaxed. Together with OT-0020 and OT-0021, this closes the
single-challenger whole-program representation as the next credible path even
when richer raw consequence evidence is available. A successor must change the
actor-authored representation or credit topology, not merely sample again or
tune this prompt.

## Evidence manifest

`evidence/manifests/OT-0022/ot-0022-trace-pilot-001.json`
