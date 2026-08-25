# OT-0061 — Hosted-schema preflight repair calibration

- **Status:** run-locked; unexecuted
- **Evidence class:** public-reconstructible if valid
- **Target:** candidate-free repair of OT-0060's impossible validity gate
- **Candidate output:** forbidden
- **Hosted calls:** forbidden
- **Predecessor:** operationally invalid OT-0060

## Frozen hypothesis and cheapest falsifier

OT-0060 can be repaired without changing its scientific search space by
removing only the redundant `maxLength` keyword from the actor-output schema,
retaining the safe interpreter's independent 256-byte source limit, and making
schema-subset validation a fail-closed preflight before any hosted side effect.

Reject if the repaired schema differs in any other semantic field, contains any
unsupported keyword, accepts a non-string or extra property, or if the existing
interpreter ceases to accept a 256-byte safe source and reject a 257-byte source.
Reject if the preflight can invoke a supplied hosted-start sentinel, create a
workspace, or emit candidate output when given the old invalid schema. Reject
if the complete OT-0059 32-world carrier calibration no longer passes exactly.
Any actor output or hosted model call invalidates the protocol.

## Frozen calibration and controls

Compare the immutable OT-0059 schema with a new OT-0061 schema. Canonical
recursive comparison must show exactly one deletion at
`properties.source.maxLength`, with every remaining key and value identical.
The old schema must have exactly the unsupported-keyword set `{maxLength}` and
the repaired schema must have the empty set under the already-promoted hosted
schema dialect. Draft 2020-12 validation must still accept exactly one string
field named `source`, reject missing or non-string `source`, and reject extra
properties.

Exercise the existing OT-0059 interpreter at the byte boundary with a safe
Boolean expression padded to exactly 256 UTF-8 bytes and the same expression at
257 bytes. The former must parse and the latter must fail. This is the decisive
control that schema repair does not relax the actual carrier bound.

The reusable preflight accepts a schema and a zero-argument sentinel standing
for the first hosted-side effect. With the old schema it must raise before the
sentinel runs. With the repaired schema it may return a receipt and then invoke
the sentinel exactly once. The calibration itself supplies only a local
in-memory sentinel; it must not create a workspace, start a proxy or backend,
or make a hosted call.

Run the complete OT-0059 carrier calibration in forward and reverse order and
require its same 32/32 promotion outcome, hidden-reference opportunity,
old-carrier impossibility, compression certificate, structural ablations,
interpreter safety, rollback, and surface exclusions. OT-0060 outputs, task,
sources, and private world are forbidden inputs.

## Promotion and claim limit

Promote only if every frozen comparison, byte-boundary, fail-closed sequencing,
carrier-regression, deterministic-replay, test, audit, evidence, privacy, and
repository-size gate passes without actor or hosted output. A pass confirms
only a prospective protocol repair. It does not rescore OT-0060 and is not
learner invention, representation escape, transfer, widened OT-2, integrated
development, or OT-3/TAAA evidence.

A pass authorizes at most one fresh OT-0062 learner candidate. OT-0062 must use
a newly derived private task and the unchanged OT-0060 scientific endpoints,
controls, resource limits, deployment identity, and promotion gate. It must
invoke the promoted preflight before workspace creation, proxy startup, backend
startup, or actor output. The retired OT-0060 task and outputs remain forbidden.
