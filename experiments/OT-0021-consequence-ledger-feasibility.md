# OT-0021 — Consequence-ledger carrier feasibility

- **Status:** failed as frozen; mechanism slice positive, receipt gate invalid
- **Evidence class:** exploratory-only
- **Target authority:** none; development feasibility only
- **Predecessor:** OT-0020 invalidated E4 candidate

## Hypothesis

OT-0020's complete worker showed that the whole-program carrier could execute,
commit, and eventually recover, but its one-step receipt discarded the raw
completed encounter and prior actor-authored selector history that OT-1 permits.
An append-only, strictly bounded consequence ledger may carry enough evidence
for fresh actors to author useful deterministic challengers without supplying a
researcher strategy, future outcome, fixed-control menu, E4 witness, or commit
authority.

This record tests only carrier feasibility on one tracked public non-candidate
task. It cannot promote OT-1, renew E4, or justify a private candidate run.

## Frozen mechanism and cheapest falsifier

`src/open_trajectory_harness/ot0021_trace.py` projects only a completed earlier
encounter: raw archive events, queries, independent outcomes, deterministic
predictions and per-query errors under the current selector, the selector's
expression and identity, and the controller's completed decision. Receipt
hashes bind every entry. Stages must be contiguous, complete, append-only, at
most five entries, and at most 49,152 canonical bytes.

Before any hosted output, reject the projection if structural tests find the
sealed pilot evaluation, hidden future outcomes, E4 construction state, exact
witnesses, or fixed-control identities in the rendered actor prompt. Reject it
if receipt reconstruction, deterministic replay, entry order, or byte/entry
budgets fail.

If those checks pass, run exactly two fresh Luna encounters under one pinned
hosted epoch. Both receive the same generic OT-0016 expression contract, null
selector and decision seeds, and the same completed consequence ledger. The
sealed public evaluation is not rendered into either prompt or workspace.

## Frozen controls, scoring, and gate

The unchanged selector is `[]`; the controller-owned predictor, interpreter,
paired comparison receipt, true and credit-neutralized decision replay, commit
ledger, and expression bounds are inherited unchanged from OT-0016. Each actor
must independently return a valid selector and prospective decision rule with
zero tools. On the sealed public evaluation, each selector must change the
selected identities and gain at least four errors over the unchanged selector.
Each rule must choose the challenger under true credit and current under credit
neutralization.

The two actor threads and workspaces must be fresh, Response identities must be
distinct, the effective model must be exact Luna, direct inventories must match
the frozen three-tool identity, catalog ETag must be singular, collector errors
must be zero, total use must remain under 60,000 input and 4,000 output tokens,
and the run must finish within 300 seconds. Full tests and the privacy audit are
part of the gate.

## Freeze boundary

Actor output is forbidden until a clean implementation commit and a separate
run-lock commit bind the public task, prompt, schema, trace projector, evaluator,
shared carrier, acceptance rule, backend pair, dependency/TLS identity, and
successful OT-0020 inventory pilot. After output, the pilot is passed or failed
as written and is not repaired.

The clean protocol and implementation commit is
`94c307ef61906c233ba9d0db1132740dd35f0b93`.
`spec/ot-0021-run-lock.json` binds it and every listed runtime authority before
the first hosted actor output.

## Results and decision

The frozen pilot failed. Both fresh actors independently returned valid bounded
selector and decision expressions with zero tools. Both selectors changed the
retained identities, changed predictions, and beat the null selector by six
errors against the required four. Both prospective rules chose the challenger
under the true paired receipt, chose current under credit neutralization, and
produced deterministic changed commits. The mechanism, model, inventory,
freshness, parse, authority, resource, collector, test, and audit gates passed.

The response-receipt gate failed because the implementation counted receipt
events rather than distinct Response identities. The proxy emitted three
identical receipt events for each completed Response, producing six events.
The sealed actor records contain exactly one Response identity per turn and two
distinct identities across turns, which was the protocol's intended property,
but OT-0021's frozen scoring expression required exactly two raw events. The
pilot is therefore `failed` and is not rescored or repaired.

This is positive exploratory evidence for the consequence-ledger carrier but
not a passing feasibility result. A separately numbered pilot may correct the
prospective receipt aggregation, use fresh actors and a fresh public task, and
otherwise preserve the mechanism and thresholds. OT-0021 itself has no OT-1 or
E4 authority.

## Evidence manifest

`evidence/manifests/OT-0021/ot-0021-trace-pilot-001.json`
