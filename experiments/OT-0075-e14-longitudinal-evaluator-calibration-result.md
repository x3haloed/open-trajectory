# OT-0075 — E14 longitudinal evaluator calibration result

- **Disposition:** `rejected`
- **Scope:** candidate-free public-design falsifier before private derivation
- **E14 status:** not promoted
- **Learner authorization:** none

## Plan and result boundary

The prospectively frozen plan remains
`OT-0075-e14-longitudinal-evaluator-calibration.md`, together with its frozen
acceptance specification and task-derivation module. This separate record
preserves what the implemented evaluator actually showed on a declared public
design world. It does not revise, rescore, or complete the planned private
anchor run.

The cheapest public falsifier rejected the design before private preparation.
No private seed, private anchor task, authoritative anchor attempt, candidate,
actor output, or hosted-model call was generated. Consequently there is no
private anchor result, no continual-adaptation claim, and no authority to run a
learner.

## Public deterministic counterexamples

The implemented online learners and primary scorer were applied to public
design seed 0. The frozen causal rule defines
`L = immutable_errors - live_errors`,
`A = max(0, immutable_errors - intervention_errors)`, and requires
`L > 0` and `10 * A <= L` for every intervention.

Three zero-based stream indices violate that rule:

- **Case index 9, compact reference:** immutable `128`, live `19`, so
  `L = 109`. One-step-stale consequence error is `115`, so `A = 13` and
  `10A = 130 > 109`.
- **Case index 11:** immutable error is `132`. Both references have live error
  `19`, so `L = 113`. Consequence withholding, update without projection, and
  projection without update each produce error `115` for the compact reference
  (`A = 17`, `170 > 113`) and `118` for the lossless-log reference
  (`A = 14`, `140 > 113`). The compact stale-consequence branch also produces
  error `116` (`A = 16`, `160 > 113`).
- **Case index 12:** immutable error is `135`. The compact reference has live
  error `24`, so `L = 111`; each of withholding, update without projection,
  and projection without update produces error `110` (`A = 25`,
  `250 > 111`). The lossless-log reference has live error `20`, so `L = 115`;
  the same three interventions produce error `106` (`A = 29`,
  `290 > 115`).

The focused regression test reconstructs the case-index-11 compact-reference
counterexample directly from public seed 0 using the implemented learning and
scoring semantics.

## Causal diagnosis

The update and projection ablations remove consequence-driven adaptation as
intended, but their resulting predictor is the reference's fixed initial
state, not the separately chosen immutable-seed control. On some frozen public
streams that fixed initial predictor happens to outperform the immutable seed.
The causal rule counts that baseline difference as surviving learning lift,
even though no consequence-driven update reaches later predictions. The stale
case at index 9 exposes the same calibration dependence through a corrupted
consequence lineage.

This is a public evaluator-calibration failure, not evidence that either
positive reference failed to learn. Because the baseline and threshold were
P-frozen, they cannot be repaired after observing these streams. OT-0075 is
therefore rejected before its private anchor, promotes no evaluation regime,
authorizes no candidate, and may not be retried or reseeded. Any corrected
causal comparison requires a newly numbered prospective experiment.

## Additional implementation prediction errors

The public-design audit also found a distinct ancestry defect in the
update-without-projection implementation. After the first update, the receipt
chain treated the computed candidate post-state as authoritative, while the
next update was actually computed from the stale actor-visible projection.
Thus the behavioral ablation remained frozen as intended, but the named
pre-state did not cause the subsequent update. This defect is not needed for
the rejection above: consequence withholding and projection without update
independently fail the frozen score while retaining coherent no-op ancestry.
A successor must keep authoritative updater state and actor-visible projection
separate and recompute every update from the exact receipted pre-state.

An independent implementation-time replay also corrected a non-gating range
prediction in the frozen narrative. Across the four public seeds, 16 streams
per seed, and 242 predictions per stream, the compact reference has an exact
error range of `11..26` and the lossless-log reference `14..27`, not the
narrative's exploratory `14..27` and `13..27`. The canonical 128-row trajectory
payload—ordered by public seed, case, then compact/log reference, and containing
`{case_index, errors, predictions, reference_id, seed_index}`—is 76,502 bytes
with SHA-256
`be8882fef8cb6d285719b599f070e0dacfde85c858a81365c9c5af175fc79eb2`.
The implementation follows the frozen compact weight-4-through-8 fallback and
lossless-log all-mask fallback exactly; the mistaken ranges were descriptive,
not promotion gates, and do not alter the causal-rule rejection.
