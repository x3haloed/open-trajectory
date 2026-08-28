# OT-0076 — E14 matched-counterfactual evaluator repair

- **Disposition:** `unexecuted`
- **Scope:** candidate-free prospective repair of the rejected OT-0075
  longitudinal evaluator
- **Base plan commit:** `bff7f6d972fa7acce4386dca210b0907c9fd22b3`
- **OT-0075 rejection commit:**
  `c854105f4459121ba264e80cd6cf7dd982852e38`
- **Candidate outputs:** zero
- **Actor turns / hosted-model calls:** zero
- **E14 status before execution:** not promoted
- **Learner authorization before execution:** none

## Hypothesis and bounded claim

The OT-0075 world, references, controls, and longitudinal metrics can support a
valid candidate-free E14 checkpoint if each reference's contact-caused lift is
measured against that same reference frozen at its exact initial state, rather
than against an unrelated immutable parity mask, and if authoritative updater
state is kept causally distinct from the projection delivered to the next
fresh consumer.

A complete private-anchor pass would promote only the E14 evaluator and
authorize at most one separately frozen actor-bearing inherited-substrate
candidate. It would not itself demonstrate model learning, machinery
refinement, representation escape, cross-domain development, or Open
Developmental Trajectory.

## Preserved base protocol

Except for the replacements frozen below, inherit the exact OT-0075 plan,
acceptance rule, task family, reference mechanisms, controls, comparators,
stream schedule, metrics, resource bounds, receipts, authority defects,
rollback gates, P/I/L order, one-attempt rule, reconstruction rule, privacy
rule, and promotion boundary identified by:

- base plan SHA-256
  `101f0e40c33373187099a1c004048d6d4d30ed4536bd9e6af28e30bc2569863d`;
- base acceptance SHA-256
  `792df3f94b148242e135d5ced87dec2b5299e7e73a912c91f27afcf6b6ce39c0`;
- base task protocol SHA-256
  `7c208df7fc2571f5128af908eb01c81c635968d59633ab390845bbacc87587de`;
  and
- rejection record SHA-256
  `90f751190ac718b989be6d36f75756cf45d091c6afbc70f285125901f234a591`.

The public design worlds are exactly the four OT-0075 public design seeds and
their 16 streams. This deliberate distribution preservation isolates the
evaluator repair. OT-0075 generated no private seed, task, or attempt. OT-0076
must generate one fresh 256-bit private seed only after clean I and bind it to
I through the preserved derivation family and the OT-0076 wrapper identity.
Eight derived private streams are used once. Reseeding, collision replacement,
task shopping, and returning to the public worlds after unsealing are
forbidden.

## Prediction error being resolved

OT-0075 used the immutable-seed control as the baseline for every causal
intervention. On several public streams, a reference frozen at its initial
state outperformed that different immutable rule. The scorer counted this
static prior difference as surviving learning even when no consequence-driven
state reached later predictions. OT-0075 was therefore rejected before private
derivation.

Its update-without-projection implementation also receipted one state as the
next update parent while actually computing from the stale actor projection.
That ancestry defect did not cause the score rejection, but OT-0076 must repair
it prospectively.

## Exact condition inventory

Every stream contains exactly 23 opaque, order-independent conditions:

- two positive online references: compact cached affine version space and the
  lossless epistemic-log linear bank;
- four global required controls: no persistence, immutable seed, outcome-free
  encounter clock, and offline best fixed eligible rule;
- two reference-specific matched-frozen controls, each initialized from the
  exact positive reference state and thereafter receipting no-ops;
- two reported adaptive comparators from OT-0075;
- for each reference, consequence withholding, one-step-stale consequence,
  update without projection, projection without update, wrong-lineage
  projection, and cross-episode state reset; and
- one identical immutable-state/projection placebo.

Condition labels and execution order have no scoring authority. Every lineage
has an independently derived opaque identity and complete 242-slot denominator.

## Matched live lift

For reference `r` in independently derived stream `s`, let:

- `B[r,s]` be errors of the matched-frozen control from the exact initial state
  of `r`;
- `E[r,s]` be live reference errors; and
- `L[r,s] = B[r,s] - E[r,s]`.

Require `20 * L[r,s] >= 242` in every public-design and private-anchor stream.
The two references must also retain every OT-0075 cumulative, rolling,
recovery, late-window, relearning, global-control, reset, state, operation, and
authority gate.

The ten paired reference/control families are the eight reference-by-global-
control pairs plus each reference against its own matched-frozen control. Both
references must win all ten pairs in all eight private streams. The frozen
familywise sign bound is `10 / 2^8 = 0.0390625 <= 0.05`.

## Hard path severings

For consequence withholding, update without projection, and projection
without update, let
`A[r,s,i] = max(0, B[r,s] - intervention_errors[r,s,i])`.
Require `A = 0` and exact equality with the matched-frozen control for:

- all 242 predictions and validity statuses;
- every projection digest consumed by a prediction process; and
- the terminal delivered projection.

The three conditions remain causally distinct:

- consequence withholding retains the independently scored world outcome but
  delivers no updater consequence and receipts a no-op;
- projection without update delivers the current consequence to an explicit
  no-op updater and preserves exact state and projection bytes; and
- update without projection computes every valid candidate post-state from the
  exact immediately prior authoritative post-state and current released
  outcome, receipts that candidate and its ancestry, but delivers the exact
  frozen actor projection. At least one candidate state must differ from its
  pre-state. The candidate-state chain and actor-projection chain may diverge
  only in this intervention and must each validate independently.

Changing immutable-seed predictions or errors while holding all matched traces
fixed must not change any hard-severing disposition.

## Temporal consequence binding

One-step-stale consequence is not a causal null because prior labels can carry
real information. It is a separately scored temporal-binding intervention.
It delivers zero at encounter zero and the exact prior encounter outcome
thereafter. At least one update must be accepted and at least one delivered
projection must change before any later fail-closed rejection.

Let `S[r,s]` be stale errors and
`R[r,s] = max(0, B[r,s] - S[r,s])`, the lift surviving stale binding. Require:

- `3 * R[r,s] <= L[r,s]`, so at least two-thirds of matched live lift is lost;
  and
- `20 * (S[r,s] - E[r,s]) >= 242`, so stale binding is also worse than live by
  the frozen practical margin.

Invalid or inconsistent stale states fail closed, retain every denominator
slot, and cannot become authority-eligible.

## Projection, update, and receipt causality

The implementation must carry two explicit variables: authoritative updater
state and actor-visible projection. Every update consumes the exact bytes named
by its pre-state receipt. Every prediction consumer receives only the exact
projection named by its projection receipt. No controller cache, prior process,
task loader, response chain, filesystem state, hidden schedule, or future
outcome may bridge the two.

For the live references, each next projection must be the canonical projection
of the exact post-state. For update without projection, every candidate update
must descend from the prior authoritative state while the next fresh consumer
receives the frozen projection. Wrong-lineage projection must fail closed before
positive scoring. Rewind, same-suffix replay, alternate sibling isolation,
terminal audit consumption, and exact reconstruction remain required.

## Public design result frozen before I

An independent pure replay of all four public seeds, 16 streams, two
references, two matched baselines, and declared interventions produced 128 of
128 passing reference-stream rows under the rules above. The canonical
126,413-byte design-vector payload has SHA-256
`ec69c3fc99c062a7430ea95d46f93827008605cceec5ae1c1c118f4a3090ed7b`.
It is a canonical JSON array ordered by public seed `0..3`, case `0..15`, then
compact/log reference. Each row has exactly `design_seed`, `case_index`,
`reference_id`, `live_errors`, `matched_frozen_errors`, `live_lift`,
`matched_margin_pass`, `true_no_learning`, `stale_errors`,
`stale_valid_predictions`, `stale_residual_lift`,
`stale_two_thirds_loss_pass`, `stale_accepted_updates`, and
`stale_active_projection_changed`, plus `stale_practical_margin_pass`. The
three `true_no_learning` entries each
contain exactly `errors`, prediction/status and consumed/terminal projection
equality, accepted-update count, and whether a candidate changed. This vector
attests behavior, not receipt ancestry; the separate exact-pre-state receipt
gate remains mandatory.

The four preserved base-family canonical task digests in seed order are
`04be3d8a015bde4d462abfa57722896607e9aded76d92d46ce24f2952f1a0250`,
`70e43a7896b7606df13d0f2a9b369c3105203be205b84c9205379c3aca89b5a7`,
`b25084ca908889a7a7711cbeac48a567d423cb3a780608c25762905e09cc03af`,
and `6d1641038482943167bdde0166dc937456fc8e73361c9ae823918e68546eee93`.
After replacing only the top-level experiment identity with `OT-0076`, the
wrapped task digests are
`8e70ed7907cbce684e4a03fe02f2b14b58714763954f4cec5ce5b57f0fc0deb8`,
`def07836fb74f7f9c31d76b536c5bec46ff7e7112bc9e4ce8f8bb1fc00b7a8e1`,
`e4325bc6e29b59b67706ddda8adc0c4c4379bc96d6d67abb6fa24af3fa04e32f`,
and `bb00f00648f72b33c9c8b3360d23a1827cf3491ef6b3344eeba22ed5c51435a5`.
The implementation must reproduce that schema and digest before private
preparation. A digest mismatch or any public gate failure rejects OT-0076 and
forbids private derivation.

## Cheapest falsifier and promotion gate

Before private preparation, reject if the implementation cannot reproduce all
public matched-baseline, hard-severing, stale-binding, update-ancestry,
authority-defect, rollback, scorer-agreement, budget, and design-vector gates.

After clean I passes those checks, create the one sealed seed and run the eight
private streams exactly once. Promote E14 only if both references pass every
stream, all ten paired families, every intervention and causal-path gate,
primary/shadow agreement, fresh-process/workspace/sentinel checks, exact clean
reconstruction, full tests, evidence/privacy audit, and publication verification
within the frozen budget. Any missing, invalid, timed-out, mismatched, or
unreconstructable result is a retained-denominator failure and authorizes no
learner. No threshold, task, order, baseline, or implementation may change
after the private seed exists.
