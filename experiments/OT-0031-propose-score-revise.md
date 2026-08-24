# OT-0031 — Bounded casebook propose–score–revise feasibility

- **Status:** frozen; hosted output forbidden until the run lock is committed
- **Evidence class:** exploratory-only
- **Target authority:** none; development learning-loop feasibility only
- **Predecessor:** OT-0030 mixed one-turn further correction

## Hypothesis

OT-0029 and OT-0030 each showed one fully successful and one incomplete
one-turn correction. The remaining bottleneck is variance in casebook synthesis,
not carrier validity or absence of correction capacity. OT-0031 changes the
learning mechanism: each of two independent branches uses one fresh actor to
author a probe, the controller scores it on the completed encounter only, and a
second fresh actor receives the exact probe and receipt before authoring the
final casebook. A separate future archive remains sealed throughout.

The source is the actual failed seven-error second branch from OT-0030,
transitively replayed through OT-0027–OT-0029. Cross-encounter continuity passes
only through the named casebook and exact consequence projections. The
controller supplies no casebook, revision, strategy, or future score.

## Cheapest falsifier, controls, and scoring

Before hosted output, reject the loop unless all sources replay, the inherited
state makes seven errors, a known final casebook reaches zero, unchanged
behavior remains at seven, candidate receipts are deterministic, and no prompt
contains the future prefix. Then exactly four fresh Luna encounters implement
two proposal/revision branches. A proposal already at at most two completed
errors may be preserved; otherwise the revision must change its identity and
strictly reduce completed error. Each final state must change source selection
and prediction, score at most two future errors, and gain at least four. Every
deployment, identity, receipt, resource, test, audit, privacy, and evidence gate
must pass.

## Claim limit and freeze boundary

A pass establishes only public development feasibility of a bounded actor-
authored propose–score–revise loop. It does not supply the full fixed-control
family or selector-change ablation, promote OT-1, or renew E4. Actor output is
forbidden until a clean implementation commit and separate run-lock commit bind
every authority. OT-0031 is not adjusted after output. A frozen failure closes
this bounded validation-loop path.

The clean protocol and implementation commit is
`aa0fc0b98deeb8242d3e5738e8251b55cd5bcbca`.
`spec/ot-0031-run-lock.json` binds it and every runtime authority before the
first hosted proposal output.
