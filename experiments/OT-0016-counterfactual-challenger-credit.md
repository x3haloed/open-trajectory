# OT-0016 — Counterfactual challenger credit

- **Status:** rejected under E3
- **Evidence class:** private-reproducible
- **Target:** OT-1 — Emergent Corrigible Inheritance Selection
- **Frozen implementation commit:** `20cb3600fd9d3098645e9b32625d4166593d37dd`
- **Predecessor:** OT-0005 deterministic executable selector

## Hypothesis

OT-0005's direct update path asked a fresh actor to synthesize the next
selector from one aggregate consequence receipt. Later disposable probes made
that receipt richer but still did not produce a repeated
improvement-harm-correction chain.

The successor hypothesis is that selector credit must become an explicit
decision object before commit. Given the same released calibration contact, an
actor-authored challenger and the current selector are applied and scored by
the controller in paired deterministic branches. The same proposal
prospectively includes a bounded actor-authored decision expression. After the
comparison seals, the controller executes that expression deterministically to
retain the current selector or commit the challenger. The receipt, proposal,
decision-rule application, and commit are separately content addressed.

The useful selector operation must still be invented by the actor. The
controller supplies a generic carrier and paired consequences, not a menu of
selection strategies and not the program to use.

## Causal mechanism

```text
released contact and independent outcomes
-> fresh actor authors bounded challenger
-> controller evaluates current and challenger on the same calibration split
-> protected paired consequence receipt
-> controller replays the prospectively authored decision expression
-> controller commits the exact receipted choice
-> complete context reset
-> deterministic held-out branch comparison
```

Unlike OT-0005, proposal does not immediately mutate the selector. Unlike a
researcher-selected tournament, the controller does not choose the lower-error
program. It validates identities, produces the paired receipt, executes the
actor-authored prospective decision expression twice, and commits that exact
choice. Held-out outcomes remain unavailable until all compared decisions
seal.

The first implemented causal slice is
`src/open_trajectory_harness/ot0016_credit.py`. It reuses OT-0005's bounded
expression interpreter and deterministic prediction instrument while adding a
controller-owned propose/compare/decide/commit ledger, issued-receipt registry,
and a separate bounded deterministic decision-expression carrier. Unit tests
use a fixed public synthetic fixture; they are mechanism tests, not candidate
evidence.

## Cheapest decisive falsifier

Abandon this credit-assignment path if a bounded non-candidate pilot cannot
reliably complete the exact causal slice from challenger proposal through a
valid paired receipt to a receipt-bound commit decision, or if actors ignore
clear counterfactual losses often enough that a frozen resource envelope
cannot support the temporal experiment.

Subject to a valid later run, reject the OT-1 candidate if no actor-invented
operation changes deterministic selections and improves held-out behavior over
the unchanged selector in both workers; if the advantage survives exact
selector-change ablation; if no learned operation later becomes harmful; or if
the system does not revise or abandon that operation and recover while
retaining capacity for another correction.

## Candidate and controls

The prospective candidate is a bounded actor-authored pure selector expression
plus a bounded actor-authored decision expression that is sealed before its
paired comparison and deterministically returns `current` or `challenger`. The
seed expressions are `[]` and `"current"`; neither contains a useful selection
or credit operation.

Required controls before execution:

- unchanged-current selector on the same held-out cases;
- fixed most-recent, first-seen verbatim, naive-nearest, and no-persistence
  selectors under the same active-inheritance budget;
- identical-program comparison placebo with distinct snapshot identities;
- selector-change ablation preserving proposal, receipt, archive, and predictor;
- deterministic credit ablation applying the exact decision expression to a
  controller-issued alternative receipt while preserving selector programs,
  selections, application code, and downstream predictor;
- later harmful regime, correction branch, and correction-capacity canary; and
- clean two-worker reproduction under one receipted hosted epoch.

The implemented causal slice removes fresh-actor variance from receipt
application. Distinct decision-rule snapshot identities with byte-identical
expressions must return the same choice, and changing only controller-issued
outcomes must change the choice when the rule claims to use those consequences.
The frozen ablation changes only the three outcome-credit scalars in the
decision projection. Selector identities, selections, predictions, Boolean
change fields, decision-rule source, interpreter, and application code remain
identical. A useful commit is credit-causal only when the exact rule chooses
the challenger under true credit and the current selector under that
neutralized projection.

## Frozen protocol and acceptance gate

The machine-readable acceptance specification, task order, actor-facing seed,
proposal/decision prompt, output schemas, exact active-inheritance budget,
receipt projection, constrained task generator, resource envelope, numeric
gates, novelty rubric, controls, and outcome-credit ablation were committed
before any hidden candidate output. The separately committed run lock binds the
clean implementation, one private task identity, the pinned backend binaries,
TLS bundle, dependency lock, and every authority-bearing input. Candidate
execution remains forbidden until that lock commit is the clean execution
ancestor.

The scored worker now has one hosted turn per stage for prospective Luna
authorship and two final fresh Terra novelty reviews. All selector execution,
paired contact prediction, outcome reveal, true and credit-neutralized rule
application, commit, heldout scoring, fixed controls, protected-parent branch,
and identity placebos are deterministic controller operations. The two workers
run concurrently on the same sealed task manifest, use fresh threads and
workspaces for every encounter, and must finish inside the frozen 420-second
epoch window. This implementation is not result evidence and remains mutable
until its clean implementation commit is named by the run lock.

Before selecting numeric gates, a controller-only prospective power study must
sample fresh task manifests and measure the oracle, unchanged, fixed-control,
placebo, harm, correction, and canary distributions. It may validate whether
the task family can distinguish the frozen estimands; it may not use candidate
actor outputs or tune after candidate results. The fixed unit-test fixture is
not a power estimate and cannot justify an acceptance threshold.

The inherited OT-0005 world has this frozen pre-candidate viability gate over
256 fresh manifests:

- the per-stage best fixed control beats the best single fixed control by at
  least 2/48 mean errors and by at least 2 errors in 75% of manifests;
- no single fixed control is among the best static controls in more than 75%
  of manifests;
- at least 65% of manifests contain a transition where the prior
  contact-selected control is at least two errors worse and the current
  contact-selected control recovers at least two errors on the paired heldout;
  and
- the mean heldout regret of choosing a control from released contact rather
  than heldout outcomes is at most 2/48 errors.

This is only a task-family viability test. The per-stage best control is a
controller diagnostic, not a candidate and not an actor-visible strategy menu.
Failure rejects reuse of the inherited world for OT-0016; it does not reject
counterfactual challenger credit or OT-1.

After that gate rejected the unconditioned distribution, the next
controller-only study prospectively constrains task sampling rather than
relaxing the failed gate. An admissible manifest must have at least 4/48 errors
of per-stage dynamic advantage, at most 2/48 errors of contact-choice regret,
at least one two-error harm-and-contact-recovery transition, and at least 2/48
errors of realized contact-selected advantage over the best static control.

The sampler may try at most 128 generated manifests for each accepted one. In
64 accepted manifests, all identities must be unique and all admissibility
gates must pass; mean attempts must be at most 20, the 95th percentile at most
40, and no sample may exhaust the attempt budget. This study can establish only
that an actor-blinded, pre-candidate distribution with material selection
pressure is constructible at tolerable cost. It cannot establish candidate
learning or justify revealing the evaluator's fixed-control menu.

The first live pilot is limited to one fresh Luna actor turn, one fresh
workspace, no tool calls, the fixed public non-candidate fixture used by unit
tests, and 180 seconds. Before execution it must use the tracked seed, prompt,
and output schema; capture one direct inventory receipt, one effective-model
receipt, and one Response identity; validate both expressions without repair;
issue the paired receipt through the controller registry; replay the decision
expression; and complete its exact commit choice. Any parse, schema, carrier,
receipt, replay, inventory, tool, model, or collector failure fails the pilot.
Its selector score is mechanism-development output and cannot enter an OT-1
gate or tune the constrained task distribution.

## Privacy and storage review

Raw task manifests, rules, outcomes, proposals, expressions, comparison
receipts, commit decisions, hosted receipts, and workspaces go directly to
`$EVIDENCE`. Tracked files may contain code, public synthetic fixtures,
prospective specifications, bounded aggregate interpretations, and sanitized
content identities only.

The protected comparison receipt is actor-visible only after its calibration
predictions seal. It may include released calibration outcomes and per-query
error vectors. It must not contain held-out outcomes, future regimes, evaluator
instructions, filesystem paths, or deployment identifiers.

## Prospective predictions

- An identical-program placebo produces identical selections, predictions,
  errors, and a zero paired advantage.
- A tampered, rehashed-forged, replayed, crossed-parent, stale, or merely
  content-addressed but controller-unissued receipt cannot authorize a
  commit.
- A committed challenger has exactly the prospective content identity named by
  its proposal and paired receipt.
- An actor-authored decision expression replays identically, identical-policy
  snapshots make identical choices, and a controller-issued credit ablation
  changes only the receipt evidence rather than model sampling.
- Explicit paired credit produces more valid and useful selector decisions
  than OT-0005's direct post-stage synthesis under a prospectively comparable
  envelope.
- At least one useful committed operation is absent from the seed and is
  materially used, later contradicted, corrected, and causally ablatable.

The substrate predictions already have unit coverage. They do not establish
the behavioral claims.

## Results

No candidate actor output or hidden candidate result exists. A first
unit test incorrectly expected one absolute score from the randomized OT-0005
task generator. The observed score differed across fresh manifests. The test
was replaced with a fixed public fixture, and prospective distributional power
analysis is now an explicit pre-freeze obligation. No acceptance score was
changed because none exists for OT-0016.

The frozen 256-manifest controller-only study then rejected reuse of the
inherited OT-0005 task distribution. Three gates passed: the sample count was
exact, contact-selected fixed controls had 1.488 mean errors of regret against
the per-stage heldout oracle (maximum 2), and 85.55% of manifests contained a
two-error harm-and-contact-recovery transition (minimum 65%). The dominant-
static gate also passed: the largest best-static winner share was 68.75%
(maximum 75%).

The two decisive adaptivity gates failed. The per-stage fixed-control oracle
beat the best static control by only 1.824 mean errors over 48 predictions
(minimum 2), and only 51.95% of manifests achieved a two-error dynamic
advantage (minimum 75%). Fixed naive-nearest averaged 7.383 total errors and
fixed most-recent 8.602, while the per-stage oracle averaged 4.605. The world
contains useful transitions, but too often one frozen selector is close enough
to the stage oracle for the intended recursive comparison.

This is a task-distribution rejection, not an OT-1 candidate rejection. The
gate remains unchanged.

The prospectively constrained sampler then passed its separate 64-manifest
feasibility gate. Every accepted manifest had a unique identity and passed all
four per-manifest constraints. Mean sampling cost was 10.875 attempts, the
95th percentile was 29 attempts (maximum 40), and the maximum was 36 (budget
128). Across accepted manifests, mean dynamic advantage was 4.609 errors, mean
contact-choice regret was 0.906, and the contact-selected control beat the best
static control by 3.703 mean errors. The sampler rejected 632 generated
manifests before accepting 64.

This positive result establishes only that a suitably pressured, actor-blinded
distribution can be constructed at tolerable controller cost. Because
admissibility is defined using evaluator-owned fixed controls, none of those
control identities, modes, or gate values may enter actor prompts or candidate
workspaces.

Live pilot 001 failed before commit. The one fresh Luna actor returned
schema-valid output with no tool calls and a valid effective-model and Response
receipt, but authored JavaScript for both expressions because the generic
carrier prompt had not named its Python syntax. The controller rejected the
selector without repair. The top-level failure summary also omitted already
captured deployment receipts because validation raised before the summary copy;
the retained raw actor result contains them. The harness now copies collector
state in `finally`, and the carrier prompt specifies Python syntax, allowed
constructs, mapping subscripts, and forbidden JavaScript without adding a
selection strategy. Pilot 001 remains failed; any successor is a new pilot,
not a repair or reinterpretation.

Live pilot 002 used the clarified carrier and the pinned patched backend. It
completed the full causal slice: schema-valid Python expressions, no tool
calls, one inventory receipt, one model and Response identity, changed
selection and prediction, a six-error public-fixture advantage, deterministic
decision replay, and an exact challenger commit. It nevertheless failed the
frozen pilot gate because the proxy recorded one generic upstream-forwarding
error after the turn completed. Earlier OT-0004, OT-0005, and OT-0014 raw
artifacts contain no collector errors under the same patched backend. A new
diagnostic pilot therefore freezes one additional setup behavior: wait one
bounded second after the terminal turn so trailing SSE forwarding can complete
before app-server shutdown. Its gate is otherwise identical and pilot 002
remains failed.

Live pilot 003 passed that unchanged gate with the bounded drain. The fresh
Luna turn completed in 18.13 seconds with schema-valid output, zero tool calls,
one direct inventory receipt, one effective-model identity, one Response
identity, and zero collector errors. On the fixed public non-candidate fixture,
the actor-authored selector changed selection and prediction, gained six
errors over the null selector, and the prospectively authored decision
expression replayed deterministically and committed the exact receipted
challenger. This validates carrier usability and the live causal slice only;
the public fixture and its score cannot support or tune any candidate gate.

The locked hosted epoch completed both workers in 72.01 seconds and is a valid
E3 rejection, not an invalidated run. Both workers used the same sealed task
and hosted epoch. Every freshness, parse, tool, deterministic replay, identity
placebo, deployment receipt, inventory, counterbalance, resource, audit, and
test gate passed. Both independent Terra review pairs unanimously passed the
frozen novelty rubric.

Neither worker passed the behavioral gates. Worker 1 made credit-causal useful
commits at stages 0 and 1 and a four-error same-stage correction at stage 3,
where its unchanged selector was four errors worse than its protected parent.
Stage 0 had no prior consequence and therefore could not count toward the two
required consequence-caused pre-harm commits. No later useful canary commit
occurred. Its committed lineage had 9 errors, above the limit of 8, and beat
the strongest fixed controls by only 2 and 4 errors rather than 6. Worker 2
made only the stage-0 useful commit, then retained it through every later
stage. Its lineage had 13 errors and failed both the absolute and comparative
gates. Thus neither worker formed the frozen temporal chain and clean
behavioral reproduction failed.

A post-result controller-only diagnostic did not alter this disposition or any
score. It exposed that the accepted task itself could not realize the frozen
chain even for an evaluator-owned oracle over the four hidden controls. The
manifest offered only one consequence-driven pre-harm improvement; stage 2 had
a three-way contact tie with no contact recovery; and stages 4 and 5 offered no
later useful selector change. The constrained sampler admitted the task because
it checked aggregate dynamic advantage and one harm/recovery transition but
did not check the exact ordered acceptance chain or lineage thresholds.

The same diagnostic exposed a novelty-observation gap. Actor proposals were
overwhelmingly sequence-sorting programs, yet the reviewer packet omitted the
hidden fixed-control-equivalence verdict needed to enforce the rubric's ban on
researcher-supplied control operations. Reviewer unanimity therefore does not
establish the required novelty. These findings make E3 unsuitable for another
candidate comparison; they do not invalidate the rejection or convert it into
positive mechanism evidence.

## Evidence manifests

`evidence/manifests/OT-0016/ot-0016-inherited-world-power-001.json`

`evidence/manifests/OT-0016/ot-0016-constrained-sampler-001.json`

`evidence/manifests/OT-0016/ot-0016-pilot-001.json`

`evidence/manifests/OT-0016/ot-0016-pilot-002.json`

`evidence/manifests/OT-0016/ot-0016-pilot-003.json`

`evidence/manifests/OT-0016/ot-0016-hosted-epoch-001.json`

## Decision, limitations, and next experiment

Current disposition: `rejected` under E3.

The controller-owned causal slice, deterministic credit application,
actor-facing carrier, constrained task distribution, acceptance evaluator, and
full private-task worker were implemented and validly executed. Reusing the
unconditioned OT-0005 world remains rejected, and E3's constrained sampler is
now closed because aggregate admission did not guarantee the ordered causal
opportunities demanded by its own final gate.

A successor evaluation regime must be a new experiment and epoch. Before any
new candidate output it must require an evaluator-owned oracle witness for the
complete two-useful-commit, later-harm, correction, and canary sequence plus
lineage feasibility. It must also give novelty review a controller-derived,
actor-blinded fixed-control-equivalence verdict. The failed OT-0016 manifest is
construction evidence only; promotion of that successor regime requires fresh
heldout controller-only manifests rather than rescoring OT-0016.

OT-0016 does not establish that paired feedback is sufficient, that an actor
can invent a non-control useful operation, that the selector is corrigible,
that subject-relative scars exist, or that OT-1 is satisfied.
