# OT-0034 — E5 weighted-selector authority calibration

- **Status:** frozen; controller execution forbidden until run lock
- **Evidence class:** public-reconstructible evaluator calibration
- **Evaluation transition:** E4 → E5 candidate
- **Candidate actor outputs:** forbidden
- **Predecessor:** OT-0033 passed learned-weight mechanism feasibility without
  target authority

## Why the regime must evolve

E4's one-candidate authorization is consumed, and its exact opportunity oracle
was calibrated for actor-authored program challengers. OT-0033 changed the
mechanism family: a generic weight carrier learned a task-specific relation
fixed only after implementation. Reusing E4 would neither establish that the
new family has a complete opportunity nor resolve whether controller task
construction leaked a solving operation.

OT-0034 changes only the evaluator's sampling and authority checks. It does not
rewrite OT-1, rescore OT-0033, run the candidate learner, or use OT-0033's
scores to select a threshold. The frozen gates follow from exact symmetry in
the task family.

## Frozen controller study

Enumerate all 384 coefficient criteria formed by every permutation of
`[1, 5, 25, 125]` and every sign assignment. For each criterion, construct the
complete eighty-pattern contact and fresh canary. Construct an opposite world
by preserving the raw event archive byte-for-byte and complementing every
sealed query outcome. Before outcome release the two worlds are therefore
indistinguishable, while every correct selection is opposite.

The controller verifies:

- the criterion state makes zero errors in the original world, its negation
  makes zero in the opposite world, and each unchanged state makes eighty in
  the other;
- a second return to the original world preserves further correction
  opportunity;
- released outcomes uniquely identify the preferred event in every pair and a
  bounded separating criterion exists;
- any unchanged selector makes exactly eighty combined errors across the paired
  worlds because predictions are identical and outcomes are complementary;
- removing outcomes deletes every preference receipt, while restoring the
  exact outcomes rescues the original world identity and oracle score; and
- reversing archive and outcome order preserves deterministic scores and
  receipts.

The fixed-state symmetry is structural and does not depend on OT-0033's learned
weights. Zero and positive/negative unit-axis snapshots are executed as anchor
checks; byte-identical pre-outcome projections plus complementary outcomes
prove the same result for every possible unchanged selector.

## Candidate-authority audit

Parse the frozen OT-0033 source and compute the transitive call graph reachable
from `learn`. Reject if that graph reaches task-seed derivation, hidden
coefficients, task/split construction, run-lock validation, protocol execution,
or publication. Also reject dynamic introspection, file access, imports, `eval`,
or `exec` in the reachable graph. The callable must accept only the source
snapshot and completed encounter projection.

This is a causal authority check, not a semantic claim that every generic
learner output is novel. A future candidate must still use a fresh task fixed
after its implementation, pass a prospectively frozen novelty review, and
couple the selector to the promoted OT-0 system.

## Promotion gate

Promote E5 for exactly one fresh integration candidate only if every criterion,
paired-world, oracle-opportunity, fixed-state symmetry, deletion, rescue,
placebo, authority-reachability, deterministic replay, test, evidence, and
privacy gate passes. Any failure rejects OT-0034 as written. No criterion may be
removed, no candidate output may be inspected, and no gate may be repaired
after controller output.

The integration candidate must be separately frozen and must retain E2's
hosted-epoch and fresh-boundary anchors, E3's restored OT-1 definition, and E4's
controller ownership, controls, ablations, temporal chain, and one-candidate
limit. OT-0034 itself contains no OT-1 evidence.
