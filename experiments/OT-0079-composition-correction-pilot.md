# OT-0079 — consequence-addressable composition correction pilot

- **Disposition:** `invalidated`
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

## Observed behavior and invalidation

The sole authorized run passed every implemented behavioral mechanism gate.
Child 1 changed
the seed's unbudgeted two-item ranking into a feasible sequential selector.  It
completed `a_test` with `monitor + audit` at effort 3 while the unchanged seed
selected `bastion + monitor` at effort 7 and failed motion.  The planned later
regime then made child 1 harmful: on `b_test` it selected `binding + audit`,
passed motion at effort 3, missed one required signal, and scored -8.

Child 2 received only child 1, the public `b_train` contact, and the independent
failure receipt.  It authored a selector that tracked already covered signals,
ranked feasible candidates by novel signal contribution, and stopped through
the same remaining-budget loop.  On the held-out `b_test` it selected only
`fusion`, covered both required signals at effort 3, completed, and scored 10.
Replacing it with unchanged child 1 removed the advantage.  The useful
composition operation was absent from both the seed and actor prompt.

Both selector snapshots passed the implemented source validator and differed from
their parents.  Two fresh deterministic controller executions produced
byte-identical 14,357-byte evaluation files with evaluation identity
`ce60f866193d470aebcf5ade506c38cf990a0800de9f8bc60f3f863b31f73783`.
The complete raw bundle is retained outside Git with SHA-256
`da7f70af1b40291fd41a2fe408bd4413203e989f31fba305969b28805d5eaede`;
the tracked manifest is
`evidence/manifests/OT-0079/ot-0079-composition-correction-pilot-001.json`.

Post-result protocol audit invalidated the run.  The P-frozen carrier forbids
Python attributes, but the I validator interpreted that as a ban on reflective
attribute access while allowing whitelisted container methods.  Child 1 used
`list.append`; child 2 used `list.append`, `dict.get`, and `list.remove`.
Method calls are attribute syntax under the literal frozen rule, so both
children should have been rejected before scoring.  The tension with the same
frozen paragraph's permission for “ordinary scalar, list, dict, and set
operations” does not authorize choosing a favorable interpretation after
candidate output.

Final disposition: `invalidated`.  The behavior remains useful exploratory
evidence for the composition hypothesis, but it is not valid experiment
evidence.  A successor must prospectively define the exact AST surface and test
the seed plus representative valid programs against it before freeze.  It may
not reuse these actors, outputs, heldouts, or acceptance result.  OT-0079
changes no prior disposition, authorizes no learner, and does not promote OT-1,
E14, continual machinery refinement, or Open Developmental Trajectory.
