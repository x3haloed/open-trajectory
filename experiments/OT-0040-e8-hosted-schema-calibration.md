# OT-0040 — E8 hosted schema and failure-path calibration

- **Status:** rejected as frozen; no E8 candidate authorized
- **Evidence class:** private-reproducible evaluator calibration
- **Evaluation transition:** E7 → E8 candidate
- **Candidate goal and task outputs:** forbidden
- **Predecessor:** OT-0039 invalidated before actor output

## Why the regime evolves

OT-0039 remains invalidated. Its standards-valid nested JSON Schema used
`uniqueItems`, which the exact hosted structured-output dialect rejected before
an actor result. The harness then indexed a missing inventory receipt and
masked the upstream diagnostic with `IndexError`. E7 is consumed and OT-0039 is
not retried or rescored.

OT-0040 changes only transport calibration and failure evidence handling. It
does not change the OT-2 outcome, E7 goal-quality evaluator, temporal sequence,
selector path, controls, task family, or behavioral thresholds.

## Frozen paired hosted study

Two workers each receive two fresh empty workspaces and threads. One turn sends
the exact frozen OT-0039 schema and must fail with its known `uniqueItems`
diagnostic. The other sends the reduced future-candidate schema and must return
one fixed object with `goal_contract: null`, null hierarchy, `unknown` status,
and action `schema-canary`. Worker order is reversed.

The reduced schema removes backend-unsupported structural keywords and leaves
exact array lengths, uniqueness, identifier formats, ordering, and semantic
contract equality to the already frozen controller validator. It retains every
contract field. The canary contains no telemetry, target, value thesis, goal,
or candidate score.

The failure-safe collector must return an explicit absent-inventory receipt and
the upstream diagnostic for each negative turn without raising. Positive turns
must provide exact outputs, distinct response identities, the requested model,
and exact stable tool inventories. Both workers share one catalog/ETag epoch.

## Promotion gate

Promote E8 for exactly one fresh self-authored-goal candidate only if all four
turns, counterbalance, schema, failure-path, response, deployment, inventory,
tool, parse, resource, test, audit, evidence, and privacy gates pass. A future
candidate task must be derived after its clean implementation commit and must
bind this exact reduced schema by hash.

OT-0040 contains no candidate goal or OT-2 evidence. A pass does not reinterpret
OT-0039 or authorize changing any semantic evaluator threshold.

## Result and decision

The locked execution at `211243675bcf8d17680301c1bf7a2813c4216238`
completed all four turns in 6.86 seconds.
Both frozen OT-0039 schemas failed with the expected `uniqueItems` and
`invalid_json_schema` diagnostics. Both revised schemas returned the exact
null-goal canary with distinct response IDs, the requested model, one ETag,
stable catalogs, no tools, and no parse failures. Thus the revised transport
schema is hosted-compatible and produced no candidate goal.

The frozen failure-safe and inventory gates failed. Contrary to the protocol's
prediction, an ordinary upstream HTTP schema rejection produced no proxy
forwarding exception. More importantly, none of the four turns emitted a
model-visible inventory receipt. The locked executable had the same `0.149.0`
version string as prior studies but a different byte identity: it was the
unpatched npm binary, not the previously calibrated tool-receipt build.

Final disposition: `rejected`. No E8 candidate is authorized, and OT-0039
remains invalidated. The revised model is that backend version labels cannot
substitute for patched binary identity, and a normal application-level HTTP
error is not a proxy transport error. A new checkpoint must bind the historical
patched binary, require exact positive inventories, preserve negative turn
errors without secondary exceptions, and allow negative inventory presence to
be explicitly either present or absent. The private artifact is identified by
`evidence/manifests/OT-0040/ot-0040-e8-hosted-schema-calibration-001.json`.
