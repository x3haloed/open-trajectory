# OT-0018 — Path-complete E4 calibration

- **Status:** frozen; not run
- **Evidence class:** exploratory-only
- **Evaluation transition:** E3 → E4 successor checkpoint
- **Candidate actor outputs:** forbidden
- **Predecessor:** OT-0017 exact causal-opportunity checkpoint

## Hypothesis

OT-0017 rejected E4 promotion because its stage-5 ablation removed only the
planned recent-selection canary. The exact oracle correctly switched to nearest
or first-seen selection in all 64 tasks. E4 may still be calibrated if a
prospectively defined intervention removes every possible fixed-control canary
route and a paired rescue restores the exact witness, without weakening any
temporal, lineage, deployment, authority, privacy, or diversity anchor.

## Frozen intervention

Start from the same direct constructor and unchanged exact witness. At stage 5,
find two feature vectors on which the private canary rule and the protected
first-seen selector both predict zero. Rebuild only that stage's clean event
schedule so its recent suffix contains six copies of one such vector. Set the
contact queries to eight copies of that vector and heldout queries to seven
copies plus the second vector. This is a valid-schema controller
counterfactual, not a candidate task distribution.

The intervention is path-complete only if no-persistence and all three fixed
selectors have zero contact and heldout error at stage 5. Then no proposal can
have strict contact advantage from any current mode, so no exact witness can
contain the required later canary. The paired rescue restores the untouched
stage-5 events and splits byte-for-byte and must restore the complete base error
grid and exact-witness signature.

## Frozen study

Construct exactly 64 tasks from one new master seed in a single uninterrupted
controller-only run. Load the private OT-0017 feasibility and promotion-anchor
receipts only as exclusion sets. No semantic fingerprint or private rule
profile may recur from either prior bundle or within this study.

Every base must pass the inherited schema, direct planned path, unchanged exact
witness, contact/heldout separation, and the prior construction limits. Event-
identity and query-order placebos must preserve the complete error grid and
witness signature on all 64 bases. Replicate the OT-0017 stage-2 and stage-4
structural ablations; each may retain an alternate exact witness in at most 25%
of tasks.

For all 64 path-complete canary interventions:

- inherited schema validation must pass;
- every fixed-control contact and heldout error at stage 5 must be zero;
- the planned path and every exact witness must disappear; and
- restoring the untouched base stage must reproduce the base error grid and
  exact-witness signature exactly.

## Promotion gate

Promote E4 for one new candidate experiment only if every exclusion, base,
diversity, construction, placebo, replicated-ablation, route-completeness,
canary-removal, and rescue gate passes. Any failure rejects this successor
checkpoint as written. Do not rescore OT-0016, reinterpret OT-0017, change the
25% sensitivity limit, or reuse any prior task.

Raw tasks, witnesses, interventions, and rescues go directly to `$EVIDENCE`.
Tracked evidence may contain only a content-addressed manifest and aggregate
result.

## Results and decision

Pending.

## Evidence manifest

Pending.
