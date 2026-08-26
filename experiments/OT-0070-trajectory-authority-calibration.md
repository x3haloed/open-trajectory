# OT-0070 — Trajectory authority and inactive-branch calibration

- **Status:** executed once; promoted within the frozen claim limit
- **Evidence class:** public-reconstructible
- **Evaluation epoch:** E13 trajectory-native developmental projection
- **Target:** candidate-free substrate and authority mechanics
- **Candidate output:** forbidden
- **Hosted calls:** forbidden
- **Learner authorization on pass:** none

## Frozen hypothesis and cheapest falsifier

A minimal append-only trajectory can keep an actor-channel proposal fixture and
the independent trial bound to it recoverable across a simulated complete
reset without granting that proposal active standing. A distinct actor-channel
decision fixture can name exactly one proposal for adoption or set a branch
down; the controller can update or restore an authoritative pointer using only
identity, provenance, schema, and budget checks, without scoring, diagnosing,
repairing, summarizing, or ranking proposals. These fixtures exercise a future
authority path; they are not actor output and are not described as
actor-authored or actor-selected evidence.

Reject if any scenario permits an inactive proposal to affect the active
pointer without a valid actor-channel decision fixture, loses a failed branch
after set-down or rollback, rewrites an adopted proposal, accepts a missing or
cross-bound trial, depends on concrete payload names or irrelevant append
order, or cannot project the exact named branch inside the frozen budget.
Candidate or hosted output invalidates the protocol.

This is the cheapest falsifier of the new substrate premise. It intentionally
does not ask whether a model can infer a repair. Passing serialization tests
alone is insufficient: authority separation, proposal-local world binding,
inactive recoverability, channel-selected adoption mechanics, an exclusively
derived active pointer, and append-only rollback must all compose in the same
causal path.

## Frozen generic record substrate

The substrate record is exactly the canonical JSON triple:

```text
{source, parents, payload} -> SHA-256 record identity
```

`source` is assigned from one of three non-serializable capability objects held
by distinct actor-channel, world-channel, and controller-channel append paths.
The append API accepts the capability object, never a source string. A source
name asserted inside `payload` grants no authority, and one channel cannot emit
another channel's source. Every parent must already exist. Parent order is
canonicalized. Payload is arbitrary bounded JSON; the generic store does not
understand proposal, discrepancy, score, truth, repair, merge, or standing
semantics. A record may occupy at most 4,096 canonical bytes. Re-appending the
same canonical record deduplicates it; distinct repeated acts require a
distinct parent or an explicit occurrence value in their payload.

Records are never mutated or deleted. Exact projection receives an explicit
set of record identities, emits their canonical bytes plus external-parent
headers, and fails closed above 2,048 bytes. It performs no semantic search,
summarization, ranking, or recency heuristic. The full raw trajectory must
exceed 8,192 bytes, remain outside the simulated fresh workspace, and stay
recoverable from the controller-owned store.

Canonical JSON is exactly the existing `ot0002.canonical_json` encoding:
Python `json.dumps(value, sort_keys=True, separators=(",", ":"))`, followed by
one newline and encoded as UTF-8. Record identity is the lowercase SHA-256 of
those exact bytes. Projection byte count is the length of the same encoding of
its complete projection object. Record serialization, projection
serialization, and all procedural payload schemas are frozen in
`spec/ot-0070-acceptance.json`; the implementation may not choose them after
observing a gate.

## Frozen procedural authority layer

The calibration creates exactly cases `0` through `15`. Opaque tokens are the
first sixteen lowercase hex characters of
`SHA-256("ot-0070:<case>:<role>:<index>")`. Each case is evaluated with
independent distractors appended in ascending and descending index order;
scientific summaries are sorted by case and role before comparison. The case
family and forward/reverse execution orders are frozen in the acceptance spec.
Each history exercises:

1. an active actor-channel parent fixture;
2. a provisional actor-channel child proposal fixture;
3. a world-channel exact trial fixture whose parent edge and payload bind the
   same proposal identity and whose trace includes every compact action and
   independently resolved outcome without a discrepancy label;
4. an actor-channel decision fixture that either names the proposal for
   adoption or sets it down;
5. a controller-channel pointer event recording the prior and resulting active
   identities; and
6. a later actor-channel rollback fixture followed by an append-only pointer
   event restoring the exact prior active identity.

The controller may validate only source authority, record identity, existing
parents, exact proposal/trial binding, decision ancestry, canonical schema,
and byte bounds. It may not inspect trial success, count errors, choose a
proposal, synthesize a revision, filter the trace to failures, or select a
projection head.

Every pointer event contains the previous pointer-event identity, a sequence
number, prior active identity, resulting active identity, and the exact
decision identity. The authoritative pointer is derived solely by replaying
one genesis-rooted controller-event chain. Appending a transition uses
compare-and-swap: the decision's expected pointer event and expected active
identity must equal replayed current state. Forked pointer events, stale or
replayed decisions, skipped sequences, mismatched priors, and direct pointer
writes fail closed. No mutable active field is authoritative.

The histories include two fixture decision cases: adopt a trialed proposal
exactly and set down a trialed proposal while retaining it. Incomplete or
misbound projections are validation interventions only; OT-0070 supplies no
policy mapping them to a decision. All fixture decisions are synthetic
protocol inputs, not actor output or evidence of useful judgment.

An outcome-blind deterministic consumer reads only the proposal payload named
by replayed active state and emits its opaque `state.output` string. Adding or
projecting an inactive branch cannot change this output; valid adoption must
change it to the adopted proposal's output, and rollback must restore the exact
prior output. Trial contents are unreachable from the consumer call path.

## Frozen world, reset, and resource boundaries

A deterministic resolver behind the world-channel capability produces every
`resolved_output` from the case token and trial input. Actor and controller
channels can request a trial but cannot emit or alter a world-channel record.
For the quality placebo, two cloned histories receive structurally valid trials
that differ only in whether proposal outputs equal the independently resolved
outputs. The same actor-channel adoption fixture must receive the same protocol
validation and pointer-transition verdict in both histories. This proves that
the controller path validates provenance rather than trial quality; it does not
make either adoption a good decision.

Each exact branch projection is passed on standard input to a new Python
process whose current directory is a newly created empty workspace. The parent
keeps the full trajectory only in memory and serializes no store path or
nonprojected record. The reset worker may inspect and validate only the
projection bytes. Lookup of the known omitted active parent and an unrelated
record identity must fail closed. This is a deterministic reset-boundary
calibration, not a model encounter.

Execute exactly `forward-1`, `reverse-1`, `forward-2`, `reverse-2`, using case
orders frozen in the acceptance spec. The complete run allows 120 wall
seconds, five seconds per reset process, a raw artifact of at most 1 MiB, and
zero actor turns, actor tool calls, or hosted calls. Exceeding any bound
invalidates the run.

## Frozen interventions and controls

For every case require:

- the exact proposal-plus-trial projection fits within 2,048 bytes while the
  full trajectory exceeds 8,192 bytes;
- excluding either named node makes the branch projection incomplete;
- a valid sibling trial cannot support adoption of the selected proposal;
- a trial whose parent edge and payload binding disagree fails closed;
- a decision naming a missing, untrialed, or non-ancestor proposal fails
  closed and preserves the exact active pointer;
- a world source asserted only inside actor-channel payload has no world
  authority, and controller-channel attempts to emit actor or world source
  likewise fail;
- controller attempts to alter a world result produce no valid world-channel
  record, while matching and nonmatching quality-placebo trials receive the
  same provenance and transition verdicts;
- a valid actor-channel fixture adoption names one proposal and the controller
  adopts those exact bytes without rewrite;
- set-down changes no active identity and preserves the proposal and trial;
- rollback appends a new pointer event, restores the exact previous active
  identity, and preserves parent, successor, sibling, and rejected branches;
- replay from genesis reconstructs every active identity and consumer output;
  stale, duplicate, forked, and non-compare-and-swap pointer transitions fail
  closed, and no direct pointer-write API exists;
- inactive branch addition or projection does not change consumer output,
  adoption changes it only to the selected proposal output, and rollback
  restores the exact prior output;
- every reset worker starts in an empty workspace with only the canonical
  projection on standard input, validates the two projected records, and fails
  lookup of controller-store and nonprojected identities;
- consistent opaque-token alpha-renaming preserves every structural result;
- permuting independent distractor appends and parent input order preserves
  every structural result; and
- the exact four-run sequence stays within the frozen wall-time, per-reset,
  artifact-size, actor, tool, and hosted-call bounds and produces
  byte-identical normalized summaries.

No control is required to fail merely because record order or incidental names
change. Only causal-edge or authority misbinding is a decisive negative.

## Promotion gate and claim limit

Promote only if all sixteen cases pass twice in forward and reverse order;
every record identity, projection byte count, pointer transition, set-down,
rollback, provenance failure, binding failure, alpha-renaming check, order
placebo, and deterministic replay matches the frozen acceptance spec; actor
and hosted output remain absent; and tests, evidence audit, privacy, and
repository-size gates pass.

A pass establishes only a public deterministic trajectory/authority primitive:
inactive actor-channel branches can retain exact causal history while active
state and observable application are separately derived from an append-only
controller pointer chain. It authorizes no learner and is
not evidence of useful revision, endogenous projection, selector learning,
representation escape, developmental transfer, widened OT-2, consciousness,
personhood, general autonomy, unrestricted self-development, or OT-3/TAAA.

A rejection closes only this exact procedural substrate. An operational
invalidation preserves the artifact and requires a newly numbered prospective
repair. No result changes any OT-0048 through OT-0069 disposition.

## Sealed disposition

The sole locked execution at Git commit
`bfda7009c788a8e0f5f8eeaa621ddf6460550117` promoted. All sixteen cases passed
in each of `forward-1`, `reverse-1`, `forward-2`, and `reverse-2`; the four
normalized summaries had the same SHA-256 identity
`39f24a21a09b883349fa7bdebecac26a863af2b475124f01eb6a104e7ea64f83`.
Every full trajectory occupied 22,904 canonical bytes and every selected
proposal-plus-trial projection occupied 1,406 bytes. All frozen authority,
binding, reset, set-down, rollback, quality-placebo, order, renaming, resource,
test, audit, and artifact gates passed.

The public raw artifact contains 172,251 bytes with SHA-256
`a846269a8fd427f242006dcd17eb090a41928573f2ea8df09203133178dd89e0`.
Its content-addressed receipt is
`evidence/manifests/OT-0070/ot-0070-trajectory-authority-calibration-001.json`.
The execution produced zero candidate outputs, actor turns, actor tool calls,
hosted calls, or learner authorizations.

This promotion removes only the procedural substrate premise: an inactive
proposal and its independently owned trial can retain exact causal standing
across a bounded fresh-process projection while a replay-derived pointer alone
controls application, and set-down or rollback deletes nothing. It is not
evidence that an actor can identify useful history, author a repair, revise a
projection practice, or transfer developmental machinery.
