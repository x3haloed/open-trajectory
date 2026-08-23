# OT-0003 — Discrepancy-gated predictive inheritance

- **Status:** unexecuted
- **Evidence class:** exploratory-only
- **Target:** OT-1
- **Frozen implementation commit:** pending
- **Frozen run lock:** pending

## Hypothesis

After one independently scored contact batch per hidden regime, a compact
discrepancy-gated version-space ledger will reduce structurally held-out binary
rule prediction error relative to no persistence, bounded verbatim events, and
bounded nearest-event retrieval under the same active-inheritance ceiling. The
advantage should survive a hidden rule shift and disappear under projection
ablation.

## Causal mechanism

The controller retains a version space over parity rules. After a fresh actor
seals batch predictions, the controller computes outcomes from a hidden rule and
passes the resulting observations to each condition's substrate. The candidate
eliminates inconsistent hypotheses; only an outcome batch that eliminates the
entire current version space advances the regime and reinitializes hypotheses.
Its bounded rule projection is the sole causal payload to the next actor.

## Cheapest decisive falsifier

The pure substrate fails immediately if a basis contact batch does not identify
one rule, an independently contradictory batch does not reset it, or any
projection exceeds 96 bytes. The actor experiment fails if the candidate misses
the absolute held-out or post-shift thresholds, fails to beat any equal-budget
control by four errors, exceeds 256 substrate operations in a transition, uses
a tool, or does not lose at least three predictions under projection ablation.

## Candidate and controls

- Candidate: discrepancy-gated version-space ledger.
- Control A: no persistent state.
- Control B: most-recent verbatim outcome events truncated to 96 bytes.
- Control C: nearest prior outcome events selected for the current batch and
  truncated to 96 bytes.
- Control D: the trained candidate state with its projection removed.

The controller, not the actor, owns outcomes and commits updates. All four
learning conditions receive identical outcome history, a 96-byte projection
ceiling, and a 256-operation substrate-transition ceiling.

## Frozen protocol and acceptance gate

`spec/ot-0003-acceptance.json` freezes the hypothesis, controls, task family,
task order, structural holdouts, scoring margins, resource budgets, promotion
gate, and red-line review. Fixed prompt, output schema, substrate identities,
and task order live under `fixtures/ot-0003/`.

A private salted task manifest will select two distinct rules and bind every
input and outcome before actor execution. Only its digest enters the run lock;
the salt prevents trivial enumeration of the small rule family from that
digest.

## Privacy and storage review

The sealed task manifest, salt, active rules, outcomes, actor events, model
outputs, paths, and identifiers remain under `$EVIDENCE`. Actor events remain
in controller memory until all conditions close so one condition cannot inspect
another condition's prior events through the filesystem.

## Prospective predictions

- The pure ledger should identify exactly one active rule after each contact
  batch and advance its regime counter exactly once at the hidden shift.
- The candidate should make at most two of sixteen held-out errors and at most
  one of eight post-shift held-out errors.
- Each baseline should make at least four more held-out errors than the
  candidate under the 96-byte ceiling.
- Removing the candidate projection after learning should cause at least three
  errors across the two ablation batches.
- No actor should call a tool or fail output parsing.

## Results

Unexecuted.

## Evidence manifests

None.

## Decision, limitations, and next experiment

Pending. Even a full behavioral pass remains exploratory while the actor uses a
drifting model alias; OT-1 promotion requires a clean reproduction with an
immutable model revision.
