# OT-0019 — Full-suffix E4 calibration

- **Status:** passed; E4 promoted for one candidate experiment
- **Evidence class:** exploratory-only
- **Evaluation transition:** E3 → E4 successor checkpoint
- **Candidate actor outputs:** forbidden
- **Predecessor:** OT-0018 path-complete E4 calibration

## Hypothesis

OT-0018 removed every stage-5 selector route, but six exact witnesses placed
harm/correction at stage 3 and used stage 4 as the later canary. With two useful
pre-harm commits required after stage 0, stage 3 is the earliest possible
correction. Stages 4 and 5 are therefore the complete remaining suffix in which
the required preserved correction capacity can appear.

The E4 oracle is calibrated if neutralizing every selector route across both
suffix stages removes every exact witness and restoring both untouched stages
rescues the exact base signature, while all prior anchors remain satisfied.

## Frozen intervention and rescue

For each of stages 4 and 5, select two feature vectors on which both the private
stage rule and protected first-seen selector predict zero. Rebuild the stage's
event schedule with six clean copies of one vector in the recent suffix and set
contact/heldout queries to repetitions of the two common-zero vectors. Preserve
stage 4's exact nine-noise schedule outside the suffix and stage 5's clean
schedule.

The intervention is complete only if no-persistence and all three fixed
selectors have zero contact and heldout error at both stages. From any selector
history, neither stage can then contain a strictly contact-favored commit. The
paired rescue restores the untouched stage-4 and stage-5 records byte-for-byte
and must reproduce the base error grid and exact-witness signature.

This is a controller-only valid-schema counterfactual, not a candidate task
distribution or actor-visible strategy.

## Frozen study and controls

Construct exactly 64 fresh direct tasks in one uninterrupted run. Load the
private OT-0017 feasibility bundle, OT-0017 rejected anchor, and OT-0018 rejected
calibration only as exclusion sets. No semantic fingerprint or private rule
profile may recur from those 144 bases or within this study.

Every base must pass the inherited schema, direct planned path, unchanged exact
witness, contact/heldout separation, and construction limits. Event-identity
and query-order placebos must preserve the full error grid and witness signature
in all tasks. Replicate the stage-2 and stage-4 OT-0017 structural ablations;
each may retain an exact witness in at most 25% of tasks.

All 64 full-suffix interventions must pass schema validation, show a zero error
grid for every fixed selector at both suffix stages, break the planned path,
and contain no exact witness. All 64 paired rescues must reproduce the complete
base error grid and exact-witness signature.

## Promotion gate

Promote E4 for one new candidate experiment only if every exclusion, base,
diversity, cost, placebo, replicated-ablation, full-suffix deletion, and rescue
gate passes. Any failure rejects OT-0019 as written. Do not rescore prior
experiments, change the 25% threshold, or reuse any prior task.

Raw evidence goes directly to `$EVIDENCE`; Git receives only its content-
addressed manifest and aggregate interpretation.

## Results and decision

The frozen study passed every promotion gate. All 64 fresh bases validated the
inherited schema, direct planned path, exact witness, split separation,
construction limits, exclusions, and semantic/rule-profile uniqueness. Both
placebos were invariant on all 64 tasks.

The replicated stage-2 ablation retained an exact witness in 15/64 tasks
(23.4375%, below the frozen 25% maximum); the stage-4 ablation retained none.
Every full-suffix intervention had a zero error grid for every selector at
stages 4 and 5, broke the planned path, and removed the exact witness. All 64
paired rescues restored the complete base grid and witness signature. Mean
construction cost was 8.328125 counted candidates, p95 was 9, and maximum was
10.

Final disposition: `promoted`. E4 is authorized for exactly one new candidate
experiment. This is evaluator calibration evidence only: it contains no actor
output, does not establish OT-1, and does not rescore OT-0016 through OT-0018.

## Evidence manifest

`evidence/manifests/OT-0019/ot-0019-full-suffix-e4-calibration-001.json`
