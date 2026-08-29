# OT-0079 — consequence-addressable composition correction pilot

- **Disposition:** `unexecuted`
- **Evidence class:** `exploratory-only`
- **Target:** bounded OT-1 mechanism probe; no target promotion
- **Actor authorization:** exactly two fresh hosted actor calls after clean I
- **Claim limit:** actor-authored selector composition under deterministic local application

## Hypothesis

The failure exposed by the precursor workshop is not a lack of consequence
pressure but a split selection authority: item scores changed while an
independent cardinality rule continued to form an incoherent set.  A selector
carrier that makes selection and stopping one actor-authored program can use
the same independently owned security and motion consequences to produce a
coherent set, first improve over its unchanged parent, later become harmful,
and then correct the composition failure.

This run does not import the precursor artifact or its policies.  It begins
from a repository-authored seed selector and gives fresh actors only the named
parent source, public candidates, budget, selected set, and independent
security/motion receipt from the completed training encounter.

## Causal path

```text
parent selector source
→ deterministic selection on a public training opportunity
→ independently computed security and motion receipt
→ fresh actor authors one bounded child selector
→ controller validates and freezes the child source
→ child and unchanged parent run on the same held-out sibling
→ later public contact makes the child harmful
→ second fresh actor authors one bounded correction
→ corrected child and unchanged parent run on a second held-out sibling
```

The controller owns candidates, hidden required signals, execution, outcomes,
scores, snapshot identity, and final disposition.  Actors cannot inspect the
repository, hidden worlds, held-out siblings, controls, scores, or each other.

## Frozen carrier

Each selector is one UTF-8 Python file of at most 4,096 bytes defining exactly
`select(candidates, budget)`.  It returns a list of distinct candidate IDs.
Candidates expose only `id`, integer `risk`, integer `certainty`, integer
`effort`, and a list of opaque `signals`.  The function may use bounded Python
control flow and ordinary scalar, list, dict, and set operations.  Imports,
filesystem, network, subprocess, reflection, dynamic evaluation, attributes,
globals, and nondeterministic sources are forbidden.

The seed ranks candidates by `risk` and returns the first two.  The actor prompt
does not name or enumerate budget-aware stopping, marginal coverage, overlap,
set composition, or any candidate replacement operation.

## Frozen worlds and order

The task module contains four immutable worlds before actor output:

1. `a_train`: the seed covers security but spends 7 against budget 3.
2. `a_test`: a renamed structural sibling used only for parent/child scoring.
3. `b_train`: the adopted first child must encounter a compound-security
   failure while remaining within budget; otherwise the run rejects before the
   second actor.
4. `b_test`: a renamed structural sibling used only for the correction
   comparison.

Security passes only when the union of the selected candidates' hidden signal
coverage contains every required signal.  Motion passes only when total effort
does not exceed budget.  Completion requires both.  Utility is `10` for
completion, `0` for security-only or motion-only failure, and `-8` when motion
passes but security fails.  Selection exceptions, invalid output, duplicate or
unknown IDs, and timeout score as invalid failures.

## Controls and gates

- The unchanged seed must fail `a_test`; child 1 must complete it.
- Child 1 must then fail `b_train` and `b_test` on security while passing
  motion.  If it already completes B, the planned harmful-regime comparison is
  absent and the run rejects without reinterpretation.
- Child 2 must complete `b_test`; unchanged child 1 must fail it.
- Replacing child 2 with child 1 is the selector-change ablation and must remove
  the advantage.
- A fixed seed, a fixed effort-first selector, a fixed certainty-first
  selector, and a fixed signal-count-first selector receive the same candidate
  and budget surfaces.  Their outcomes are reported; no post-result control is
  added.
- Both child snapshots must differ bytewise from their parents and pass the
  frozen source validator.  Actor explanations and self-reports are not
  evidence.
- The complete deterministic evaluation must reconstruct byte-identically in
  two fresh local processes from the frozen selector snapshots.

## Cheapest falsifier and stop

Reject immediately on an invalid child, a failed A parent comparison, absence
of the planned B harm, a failed B correction comparison, a surviving
selector-change ablation, reconstruction mismatch, evidence failure, privacy
failure, or test failure.  Exactly one child-1 proposal and, only if eligible,
one child-2 proposal are permitted.  No coaching, repair, retry, reseeding,
world change, gate change, or third actor is authorized.

## Novelty and interpretation

This is a behavioral mechanism probe, not a promoted novelty claim.  A passing
child 2 must use its source-level program authority to produce a budget-legal
joint selection that the unchanged parent does not produce.  The useful source
operation must be absent from the seed and actor prompt.  Because the hosted
actor interface available for this run does not expose the immutable revision,
response identifiers, catalog receipt, and reproduction epoch required by
`TARGET.md`, even a complete pass remains `exploratory-only` and cannot promote
OT-1, continual machinery refinement, E14, or Open Developmental Trajectory.

## Protocol order

1. **P:** commit this record, acceptance spec, task module, prompt templates,
   and actor-surface tests before actor output.
2. **I:** implement the deterministic validator, runner, receipts, controls,
   reconstruction, and evidence command; run tests and audit; commit clean I.
3. **L:** create the sole attempt marker in the external evidence root, make at
   most the two authorized fresh actor calls, and freeze their exact outputs.
4. **R:** evaluate once, reconstruct twice, record raw identity with
   `ot-evidence record`, run the full tests and audit, and append the exact
   disposition without changing the frozen protocol.
