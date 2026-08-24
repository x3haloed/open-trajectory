# OT-0003 — Discrepancy-gated predictive inheritance

- **Status:** conditional
- **Evidence class:** exploratory-only
- **Target:** OT-0 — Contact-Causal Inheritance (historically labeled OT-1)
- **Frozen implementation commit:**
  `3b44066062e708ab11d2dd9bcfbad613d4a4d4c0`
- **Frozen run lock:** `spec/ot-0003-run-lock.json`

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

Run `ot-0003-appserver-001` executed from clean commit
`10f3c4e8e4c77675bf21d69e6d523185ecabcf51` as two independent worker
processes using the same frozen private task manifest. Both workers completed
all 26 fresh-thread, fresh-workspace encounters.

The candidate passed every frozen scientific gate in both workers:

- candidate held-out error was 0/16 in each worker, including 0/8 after the
  hidden regime shift;
- worker 1 control errors were 6/16 for no persistence, 7/16 for bounded
  verbatim events, and 10/16 for bounded nearest-event retrieval;
- worker 2 control errors were 8/16, 11/16, and 8/16 respectively;
- projection ablation caused 3/8 errors in both workers;
- every actor output parsed, no actor called a tool, all 52 thread identities
  and all 52 workspace identities were distinct;
- the model-visible three-tool inventory was stable across 52 prompt receipts
  per worker and matched the frozen digest;
- substrate transitions used at most 88 project operations and 155 observation
  operations, below the common ceiling of 256.

Worker 1 consumed 123,182 input and 4,406 output tokens in 144.90 seconds.
Worker 2 consumed 123,260 input and 4,820 output tokens in 155.52 seconds. Both
remained below every frozen resource ceiling. The full test suite and privacy
audit passed during execution.

The result did not pass the then-current contact-causal promotion gate because the actor used
the prospectively declared drifting `gpt-5.6-luna` alias rather than an
immutable model revision.

## Evidence manifests

- `evidence/manifests/OT-0003/ot-0003-appserver-001.json` identifies the raw
  exploratory artifact by SHA-256
  `a8c0bb6ddfae3731345ee264426f651f71d6c83516c485c490c840c81afc3c21`
  and byte count 4,077,318. Local content-addressed byte verification passed.

## Decision, limitations, and next experiment

**Disposition: conditional.** The discrepancy-gated version-space ledger has a
reproduced, ablation-sensitive advantage over every frozen equal-budget control
on this private structural-holdout and regime-shift task. This supports the
candidate mechanism within the tested envelope but did not promote the
then-current target. Under E3 this is conditional OT-0 evidence and supplies no
mutable-selector evidence for restored OT-1.

The next decisive path is to repeat the frozen comparison with an immutable
model revision. If no admissible immutable Codex-compatible model can be bound,
that missing base-model identity remains an explicit promotion blocker rather
than a reason to weaken the target.
