# OT-0033 — Blind consequence-trained weighted selector

- **Status:** locked; final task fixed and execution pending
- **Evidence class:** public-reconstructible mechanism feasibility
- **Target authority:** none; no OT-1 or evaluation-epoch authority
- **Predecessor:** OT-0032 realized deterministic selector learning but used a
  researcher-enumerated six-pattern proposal family

## Hypothesis and novelty boundary

A generic four-weight ranking carrier can learn a materially useful selection
criterion from consequences of its own prior selections without receiving that
criterion or a solving menu. For each query pattern, a selector must retain one
of two equal-budget candidate events. A controller-hidden linear criterion
determines which event carries the correct downstream label. The candidate sees
the paired raw events, makes its selection, and receives the independently
released query outcome only after the decision. A deterministic perceptron
update uses those completed decision consequences to change the selector
weights.

The dot-product carrier and mistake-driven update are researcher-authored. The
task-specific coefficient ordering and signs are not. The task seed is derived
mechanically from the future clean implementation commit, so no task-specific
criterion can appear in the implementation and no seed can be selected after
candidate scoring. This is the cheapest test of whether learned weights can
cross OT-0032's enumerated-menu boundary. It is still development feasibility:
an independent evaluator has not admitted the learned criterion as OT-1, and
the mechanism has not yet been coupled to the promoted OT-0 system.

## Causal path

Each regime contains all eighty nonzero four-dimensional ternary directions.
Every direction defines one pair of events with opposite selector features and
opposite downstream labels. The strict inheritance budget permits exactly one
event per pair. Only the selected event's label reaches the deterministic
predictor.

```text
current weight snapshot
→ deterministic one-of-two selections
→ independently released per-query outcomes
→ mistake-derived pairwise preferences
→ bounded deterministic weight update
→ snapshot commit and exact projection
→ complete fresh restoration
→ sealed canary selection and prediction
```

The controller constructs three regimes from one post-implementation task
identity: an initial hidden criterion, its contradiction, and a subsequent
return that contradicts the corrected selector. The candidate receives neither
that sequence nor future regimes. This gives one initial invention, one later
reversal, and one further correction opportunity. Outcome-credit ablation
withholds the released consequences while preserving raw events and prior
decisions; it must prevent every update.

## Cheapest falsifier, controls, and frozen gates

Reject unless the neutral zero-weight selector starts at forty errors; every
true-credit update changes the snapshot and reaches zero on a fresh canary; the
unchanged selector reaches eighty errors at both later contradictions; both
later updates recover to zero; every credit-neutralized update leaves the exact
source snapshot unchanged; and each unchanged-selector ablation loses at least
forty errors.

The adaptive three-regime lineage must have zero aggregate canary errors and
beat every frozen equal-budget selector by at least eighty. Frozen controls are
the zero selector, positive and negative unit-axis selectors, and each learned
snapshot held unchanged across all three regimes. No fixed linear selector can
avoid the opposing-regime error because each direction and its negation are
both present.

The candidate-visible completed projection is frozen to raw event pairs, its
own source snapshot and selections, deterministic predictions, and released
outcomes. Task seed, controller-hidden coefficients, canary data, regime order,
and control identities are excluded. All task, state, receipt, selection,
prediction, score, and restoration identities must replay exactly.

Final-task candidate output is forbidden until the implementation and protocol
pass the full suite and audit, a clean implementation commit is published, and
a separate run-lock commit binds the mechanically derived task seed, task
digest, acceptance rule, implementation, evidence authorities, and predecessor
manifest. Unit fixtures use explicitly excluded development seeds and cannot
become the final task. OT-0033 is not altered after execution.

The clean protocol and implementation commit is
`d40d2c6ce5616e4a5b3a643e2a6c93c9c197c5fd`. The task seed is the required
canonical derivation from that identity; it was not sampled or selected using
candidate scores. `spec/ot-0033-run-lock.json` binds the seed, reconstructed
task identity, and every runtime authority before final-task execution.
