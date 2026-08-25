# OT-0053 — Branching-ledger candidate-free calibration

- **Status:** prospectively frozen and run-locked; unexecuted
- **Evidence class:** public-reconstructible if valid
- **Target:** candidate-free representation-escape family calibration
- **Candidate actor output:** forbidden
- **Hosted model calls:** forbidden
- **Predecessor:** rejected OT-0052
- **Implementation:** `259de5597a469fe810215c9b7bde55cd82957220`

## Frozen prediction and cheapest falsifier

OT-0052 showed that a fresh revision can destroy a validated zero-error
proposal and that digest-only retention of one oversized proposal can leave too
little structure for reconstruction. The smallest materially different carrier
is a bounded branching ledger: retain up to three actor-authored structural
hypotheses with exact consequence receipts, then let a later actor author which
branch remains active and which alternatives persist.

Reject if any of OT-0048's 48 cases lacks the branching opportunity; if the
selected branch is not exclusively causal; if deletion, no-credit, invalid
selection, no-change preservation, committed-successor rollback, old-carrier,
fixed, no-persistence, verbatim, projection, scaled-holdout, contradiction,
correction, surface, order, replay, test, audit, evidence, privacy, or repository
size gates fail. Invalidate on input lock or execution failure. Candidate actor
output or a hosted call invalidates the design.

## Frozen mechanism and controls

The initial state remains the promoted four-weight selector. A provisional
ledger can hold three exact bounded arithmetic branches and per-branch
validation receipts. Invalid branches retain only identity and invalidity. A
committed ledger keeps every distinct admissible actor-authored branch and one
actor-designated active identity. The controller validates, filters invalid
syntax, and applies the active branch but never searches for or ranks a useful
one.

Calibration uses controller-private prior-active, magnitude-overfit, and compact
reference branches only to prove discrimination and opportunity. It freezes
selection of the reference as an oracle control, selected-branch deletion,
withheld consequence credit, invalid selected update, exact no-change
preservation, and exact rollback of a real committed successor. All three
branches receive the same completed contact; scaled holdouts remain independent.

Version-space and counterexample-guided synthesis are hypothesis sources for
retaining alternatives, not imported implementations or acceptance authority:
<https://arxiv.org/abs/1407.5397> and <https://arxiv.org/abs/1809.02283>.

## Promotion and claim limit

Promote only if all 48 cases and every frozen gate pass twice from a clean
locked commit. A pass authorizes at most one fresh OT-0054 candidate. It remains
candidate-free evidence that the new exoskeleton can discriminate the required
causal paths; it is not representation escape, developmental transfer, widened
OT-2, integrated development, or OT-3/TAAA evidence.

The implementation and every fixed input are bound by
`spec/ot-0053-run-lock.json`. No actor output or hosted call exists.
