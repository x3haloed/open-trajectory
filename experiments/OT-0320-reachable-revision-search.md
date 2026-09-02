# OT-0320 — Reachable revision search

- **Status:** frozen
- **Evidence class:** exploratory-only
- **Parent:** exact open subject `21e90d47...`, unchanged by rejected OT-0319
- **Claim:** a consequence-grounded search operation supplies the missing
  proposal-generation edge for cumulative selector correction
- **Actors:** full-history search user first, earlier-outcome-erased search user
  second; one draw each, no retry

## Prediction error and mechanism

OT-0319 gave a clean fresh actor six authenticated outcomes and an executable
candidate evaluator. The actor observed incumbent fitness 3/6 but tried no
candidate and falsely declared the legal linear surface exhausted. Frozen
conformance independently found a legal 6/6 stake. Evaluation was actionable
only after a proposal existed; it did not help the actor generate or falsify
claims about proposals.

OT-0320 adds `search_revisions.py`. It derives the coefficient dimensions that
actually vary in available contacts, exhaustively enumerates their already
public integer ranges while holding other stake fields fixed, evaluates every
candidate against only available authoritative outcomes, and reports the best
fitness plus up to eight nearest improving witnesses. If none improve on the
incumbent, it reports a complete no-improvement result. It has no private world,
held-out outcome, target weights, researcher-selected candidate, or admission
authority.

## Cheapest falsifier

The cheapest falsifier is one clean full-history actor that successfully runs
the search, sees reachable 6/6 witnesses, but does not install and verify one at
6/6 training and 10/10 private mixed held out. That would show that proposal
availability alone does not close the correction loop. A full-history search
that cannot reproduce candidate-free 6/6 reachability is an apparatus failure
and stops before actors.

## Frozen subject projection and authority

The actor receives the exact OT-0318 subject stake, OT-0319's retained six-
contact projection, an explicit non-authoritative receipt for OT-0319's untested
surface-exhaustion claim, the existing candidate evaluator and checker, and the
new search operation. Only `stake-revision.json` is mutable. A candidate must
retain all immutable stake fields, remain inside the existing public contract,
and may change bounded weights, minimum gap, and rationale.

Each actor has ordinary G10 tools in a fresh isolated workspace and must
successfully run `search_revisions.py`, `evaluate_revision.py`, and
`check_revision.py`, then inspect the exact diff. The actor may choose among
reported witnesses or retain. The observer owns reconstruction, hidden world
generation, outcome, scoring, admission, evidence, and child compilation.

## Frozen branches, order, and budgets

The full-history branch contains all six exact outcomes. The matched ablation
replaces only the three earlier outcome bodies and the corresponding unresolved
error content with explicit erasure receipts; catalogs, selections, current
outcomes, tools, stake, call budget, and workspace shape remain matched. Its
search must see incumbent 3/3 and truthfully report no improving witness.

After candidate-free conformance and this protocol are committed and pushed,
generate one new private seed for five earlier and five reversed held-out
catalogs. Run the full-history actor first and seal any operational child before
the erased actor. One draw per branch; no retry, repair, reseed, or endpoint
selection. The observer budget is two actor calls and twenty wall-clock minutes.
Budget exhaustion ends this observation, not the open subject.

## Frozen score and gates

Preflight must establish exact parent and OT-0319 rejection identities; full
search current 3/6 and best 6/6 with every reported witness independently
replaying 6/6; erased search current and best 3/3 with no improving witness;
exact current and prior stakes 5/10 on mixed fixtures; at least one reported
witness 10/10; tool/controller agreement; no private or target material; public
checker acceptance; and open-subject identity conformance.

Operational promotion requires a clean actor-authored changed stake whose
weights exactly match a reported full-search witness, successful execution of
all three tools, independent 6/6 replay, and private 10/10 versus exact current
and prior 5/10. The child must retain ancestry, the six-contact projection,
OT-0319 search error, exact search receipt, actor stake, replay, private score,
open continuation, and no outcome/scoring/admission authority. Seal it before
the control.

The causal label additionally requires a clean erased actor whose complete
search reports no improvement at 3/3 and which does not produce a changed
10/10 stake. A surprising control result narrows causality but cannot erase a
sealed operational child. Hidden-data access, tool mutation, wrong receipts,
missing commands, evaluator disagreement, G10 contamination, malformed output,
or baseline drift rejects the relevant claim.

## Limits

A pass would establish one bounded causal instance where a fixed, generic
consequence-grounded search operation turns an inherited unresolved failure
into cumulative actor-adopted machinery improvement. It would still leave the
search machinery researcher-designed and the experiment/world choice external.
The next work must test whether the subject can retain and reuse this operation,
then use its own unresolved state to choose where to apply or revise it.
