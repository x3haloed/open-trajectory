# OT-0075 — E14 longitudinal evaluator calibration

- **Status:** frozen unimplemented unexecuted
- **Evidence class:** private-reproducible if executed validly
- **Evaluation scope:** additive E14 longitudinal continual adaptation
- **Target:** candidate-free evaluator-visible surrogate calibration
- **Candidate, actor, and hosted output:** forbidden
- **Protocol origin:** the commit introducing this record, acceptance spec, and
  derivation module
- **Authorization before execution:** none

## Realization contract

**Capability.** Distinguish online external-state adaptation from fixed,
clock-only, causally ablated, leaky, and misbound paths over changing and
recurring reality without making compact representation a prerequisite for the
longitudinal claim.

**Envelope.** Eight independently derived deterministic private streams, 242
prequential encounters each, two materially different online-admissible
positive references, fresh empty-workspace consumer processes, a 2,048-byte
state/projection ceiling, immutable ordered receipts, rollback, and exact
private reconstruction.

**Exclusions.** OT-0075 contains no base-model actor, hosted call, candidate
substrate, learner-controlled weight update, machinery refinement, or
continual-learning evidence. It can promote only a scoped evaluator and
authorize one separately frozen actor-bearing experiment.

**Risk frontier.** The least-proven path is not parity inference. It is
fail-closed identity across prediction, independently released outcome,
versioned update, exact next projection, fresh-process consumption, branch
rewind, and reconstruction without another continuity channel.

The central truth is:

> A fresh process predicts from only the current public query and inherited
> projection; independent reality releases the outcome afterward; a bounded
> online updater produces the next versioned projection; the evaluator accepts
> improvement only when that exact chain, rather than hidden truth, clocks,
> labels, or controller caches, causes it.

## Evaluation transition and anchors

E14 is an additive target-scoped evaluator branch, not a rescore or replacement
of E13 machinery-refinement evidence. OT-0075 must preserve the shared hard
anchors: complete resets, independent outcomes, equal reachable budgets,
fail-closed ancestry, exact reconstruction, privacy, and prior dispositions.

The direct user clarification is the outcome anchor: an inherited external
substrate may connect discontinuous inference passes and count as continual
adaptation when its consequence-driven state reliably reduces prospective
prediction error as reality changes. Subject invention of the initial substrate
is not required.

OT-0075 calibrates only evaluator-visible surrogate gates. A controller
reference cannot establish immutable or receipted base-model identity, fresh
actor-thread identity, or behavior caused in a real base-model actor. Those
remain mandatory in the later actor-bearing candidate.

## Hypothesis

A frozen evaluator can identify a long, causal, reconstructible trajectory of
external-state adaptation while rejecting equal-budget nonlearning controls,
clock shortcuts, causal ablations, high-scoring hidden or future oracles,
favorable summaries without chains, and cross-case, cross-episode, cross-
lineage, stale, skipped, duplicated, or sibling-branch substitutions.

Two structurally different online references should pass from exactly the
evidence later candidates may receive:

1. a compact cached affine version space that persists solved rules and only
   the current episode's canonical GF(2) basis; and
2. a lossless append-only epistemic event log whose fixed decoder recomputes a
   linear model bank from the complete released prefix on every prediction.

Neither reference may read hidden masks, future outcomes, dwell lengths,
episode identities, the task, or evaluator scores through its prediction or
update call graph.

The compact projection is canonical
`{schema_version, models, basis}`. At prediction, it keeps cached models
consistent with the current basis; if none remain, it considers every eligible
weight-four-through-eight mask. The log projection is canonical
`{schema_version, event_count, payload_base64}`. Each append-only row is exactly
fourteen bits in the order episode-start flag, twelve public feature bits, and
released outcome; only the final byte is right-zero-padded. Its decoder retains
solved prior masks consistent with the current episode and otherwise considers
all 4,096 linear masks. Both predict strict-majority parity and use zero on a
tie. Neither persists anything outside its delivered projection.

The byte budget is the length of the complete canonical JSON projection
delivered to the fresh consumer, including its codec envelope and excluding
causal receipts. This freezes representation semantics before private anchor
derivation.

## Pre-freeze design prediction error and resolution

**Expected:** equal-budget raw history would be a nonlearning control that both
positive references beat by the frozen margin.

**Observed:** all candidate-visible epistemic rows fit losslessly in well under
2,048 bytes when packed without administrative receipt fields. An online
decoder can reconstruct the same sufficient rule evidence and match a compact
learner. In the independent 64-stream public design probe, merely changing an
otherwise plausible raw-row encoding reduced the minimum proposed margins to
single digits and invalidated many streams.

**Resolution:** under the clarified outcome, an append-only consequence history
plus a fixed online decoder is itself an external learning substrate: it updates
after contact and causes later predictions to improve. OT-0075 therefore makes
the lossless log a positive reference. A bounded verbatim recent window and
naive retrieval remain reported adaptive comparators, but promotion does not
require them to fail. Beating a lossless-history learner would establish a
stronger compression or inductive-efficiency claim and requires a separate
prospective experiment.

After that correction, independent calculations over all 64 public design
streams put compact-reference errors at 14–27 and log-reference errors at
13–27 of 242, with new-rule recovery at most twelve, recurrence recovery at
most two, and zero errors in every final sixteen-encounter episode window.
These public values shaped the frozen gates; they are not private-anchor
evidence and cannot decide promotion.

## Cheapest decisive falsifier

Before private anchor derivation, reject the design if either online reference
cannot pass on the declared public design worlds, any required nonlearning
control falls inside the frozen reference margin, any high-scoring
future/hidden oracle is accepted, any identity mutation is accepted, either
scorer changes disposition under an allowed metamorphism, a state/projection
exceeds its budget, rollback or same-suffix replay is not exact, or a fresh
worker has a continuity surface other than its canonical input.

After clean implementation, generate one controller-private 256-bit seed and
derive exactly one eight-stream anchor bundle. Any collision, invalid world,
failed gate, timeout, audit failure, or reproduction mismatch rejects OT-0075.
There is no reseed, replacement bundle, threshold change, or second attempt.

## Frozen world

Each stream contains six variable-duration episodes over twelve-bit parity
rules in the semantic order `A → B → A → C → B → A`. A query marks that a
change occurred but does not reveal which rule is active. Dwell lengths are a
hidden permutation of `32, 35, 39, 43, 45, 48`; encounter index and future
change points are absent from the consumer surface.

The first twelve features of every episode form a full-rank basis, so released
outcomes identify any active parity rule within twelve encounters. All 242
features in a stream are distinct. Recurrences therefore use structurally new
queries rather than exact replay. Hidden masks are distinct, have Hamming
weight four through eight, and never enter a consumer projection. The first two
query/outcome pairs distinguish all three hidden rules, certifying that a
previously learned rule is recognizable without making its identity public.

Every outcome is prequential learning contact: prediction is sealed first,
then the independently retained outcome is appended, then an update or explicit
no-op occurs. There are no evaluation-only heldouts in OT-0075.

## Design, implementation, and private task order

P freezes this record, `spec/ot-0075-acceptance.json`, and
`src/open_trajectory_harness/ot0075_protocol.py`, including domain tags,
derivation, task validation, one-attempt handling, budgets, controls, metrics,
defects, and promotion.

Only the four declared public design seeds may shape the evaluator. I is the
first chosen clean evaluator implementation after P. I contains both online
references, controls, primary and independently implemented shadow scorers,
fresh reset worker, validators, mutation suite, evidence path, and tests, but no
private seed, anchor task, receipt, run lock, output, or manifest.

After clean I, authoritative preparation writes one private 256-bit seed,
derived task, and derivation receipt directly under `$EVIDENCE`, then writes the
sole tracked run lock. L is I's direct child and may add only that lock. L binds
P, I, the complete I tree, private seed digest, task and receipt hashes, every
fixed input, run identity, evidence paths, and reconstruction recipe. The seed
and hidden task never enter Git.

## Controls and causal interventions

Execute every online required control through the same public queries, outcome
release, receipt validation, state ceiling, and scoring denominator:

- no persistence, predicting zero from fresh empty state;
- an immutable seed predicting parity under mask `000000001111` with receipted
  no-ops; and
- an outcome-free counter predicting encounter index modulo two.

Also compute the offline best fixed eligible parity rule, breaking equal-error
ties by smallest integer mask. It is a deliberately noncausal lower-bound
benchmark and remains authority-ineligible as a positive lineage.

Report, without requiring failure, two online adaptive comparisons: a maximum
2,048-byte suffix of canonical verbatim `{public_query, outcome}` rows with a
task-aware parity decoder; and the complete lossless epistemic log with naive
nearest-feature retrieval, using most-recent then smallest-feature tie breaks.
They remain authority-, budget-, and receipt-checked. If either improves, that
is adaptive evidence rather than a failed longitudinal gate.

Also execute consequence withholding, one-step-stale consequence,
update-without-projection, projection-without-update, wrong-lineage projection,
an identical-state/projection placebo, and state reset at every episode
boundary. For each ordinary causal intervention, let
`L = immutable_errors - live_errors` and
`A = max(0, immutable_errors - intervention_errors)`; require `L > 0` and
`10 * A <= L`. The identical placebo must remain byte- and score-identical.
For cross-episode reset, recurring-episode reset errors minus live recurring-
episode errors must be at least eight in every stream.

A deliberately leaky outcome/future oracle and a hidden-rule oracle may score
perfectly but must be rejected on authority and ablation grounds. A negative
lineage carrying an apparent reference label must remain negative; condition
labels and execution order have no scoring authority.

## Metrics and power

The independent stream is the inferential unit. Encounters within a recursive
stream are not treated as independent samples. Freeze cumulative prequential
errors, sixteen-encounter rolling errors, eight-encounter sustained recovery,
post-change excess error, recurrence recovery, relearning savings, and
live-versus-seed lift. Change-point errors remain in cumulative loss. Recovery
is the zero-based earliest offset `r <= dwell - 8` after which every remaining
episode prediction is correct; it is the full dwell if no such offset exists.

For both online references in every stream:

- `errors * 6 <= 242`;
- every contiguous sixteen-encounter window has at most twelve errors;
- recovery is at most twelve encounters for new rules and eight for recurrences;
- the final sixteen encounters of every episode have zero errors;
- summed new-rule recovery minus summed recurrence recovery is at least twelve;
  and
- against every required nonlearning control,
  `20 * (control_errors - reference_errors) >= 242`.

Both references must beat all four controls in all eight paired streams. Under
a sign-symmetric null, the union bound for the eight reference/control families
is `8 / 2^8 = 0.03125`, below the frozen familywise 0.05 level. Integer counts
and cross multiplication are authoritative; no floating-point or per-encounter
pseudoreplication decides promotion. Invalid, timed-out, or missing predictions
count as errors while the denominator remains 242.

## Fail-closed causal and reset path

Every authoritative lineage binds case, lineage, encounter, episode boundary,
query, pre-state, delivered projection, fresh consumer, sealed prediction,
outcome, update or no-op, post-state, and next consumer. The terminal projection
must be consumed by an audit worker. Fresh-process receipts bind an empty
workspace before and after, response-chain absence, an allowlisted environment,
and no filesystem, network, tool, subprocess, or task-loader authority in the
reference call graph.

Generated well-formed mutations must reject future or hidden access,
post-outcome prediction, wrong parent/state, cross-case, cross-lineage,
cross-episode, stale, skipped, duplicated, reordered, sibling-branch, missing-
terminal, favorable-summary-only, denominator, and budget substitutions for the
intended reason.

At a frozen checkpoint, rewind the active reference state and replay the same
suffix byte-exactly. Execute a distinct alternate suffix from the same parent,
prove sibling state cannot affect the active projection, and reject cross-
branch substitution.

## Metamorphic and scorer independence

Task-level query-ID alpha renaming and isolated case-order reversal must
preserve normalized metrics and disposition. Condition-ID shuffle is applied
to completed traces. Label complement is also trace-level: simultaneously
complement sealed predictions and outcomes after execution without rerunning a
learner. This preserves error semantics without pretending that the pure parity
task family is closed under label complement. The primary and shadow scorers
may share canonical JSON and hashing primitives but no metric or promotion
helper. They must independently reach the exact same decision.

## Privacy, evidence, and publication

The private seed, hidden masks, task, per-encounter chains, and raw outputs go
directly to `$EVIDENCE`. Git may contain only the run lock, a sanitized
content-addressed result manifest, bounded aggregate interpretation, and
allowed digests. No machine path or environment dump is recorded.

The authoritative run executes once from clean L, reconstructs the complete raw
artifact from the private seed and ordered rules in a separate fresh evidence
root, and compares exact bytes before publication. A valid result is therefore
private-reproducible, not public-reconstructible.

## Promotion and claim limit

Promote E14 only if every anchor stream, reference, control limitation,
intervention, authority mutation, metamorphism, rollback/replay check, reset
receipt, independent scorer, reconstruction, test, evidence, and privacy gate
passes. A pass authorizes exactly one separately frozen actor-bearing
experiment. Any failure authorizes none.

OT-0075 can establish only that the scoped evaluator has a viable,
discriminating, causal candidate-free opportunity. It cannot establish that a
base-model instance learns, that weights are immutable, that the later
candidate seed is useful, that machinery self-refines, or that Open
Developmental Trajectory has been reached.

## Prospective predictions

- Both online references pass every stream with cumulative error below one
  sixth and visibly faster recovery on recurring rules.
- All four required nonlearning controls remain outside the per-stream margin;
  adaptive comparator trajectories are reported without forced failure.
- Withholding, stale, delivery, update, and lineage interventions remove at
  least nine tenths of live lift.
- Perfect hidden/future oracles are rejected despite favorable loss.
- Every identity and ancestry mutation fails closed.
- Exact rewind, branch isolation, reconstruction, tests, and privacy audit pass.

These are frozen predictions, not results.

## Results

Unexecuted. No private anchor seed or task exists at P.

## Evidence manifests

None.

## Decision, limitations, and next experiment

No disposition and no learner authorization exist before the sole anchor run.
