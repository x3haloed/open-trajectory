# OT-0189 — flat-schema truthful receipt-effect replication

- **Status:** design frozen; executable conformance pending; not run
- **Evidence class:** exploratory-only
- **Target:** obtain a valid replication of consequence-associated executable
  route revision after repairing OT-0187/0188's reporting interfaces
- **Parent:** exact OT-0182 open successor plus the OT-0183 mechanism, OT-0185
  route and matrix, and no actor-visible later experiment outcomes
- **Actor budget:** eight contradiction-visible repair actors and eight matched
  contradiction-erased controls
- **Observer budget:** one complete driver invocation; 80 minutes

## Frozen API-supported report contract

Use one flat response schema containing only API-supported object, property,
type, enum, const, array-bound, and string-length keywords. It admits:

- action `retain-executable-route` or `revise-executable-route`; and
- zero or one `files_changed` entry, whose only possible value is
  `executable-route.json`.

A frozen local predicate enforces the cross-field rule the flat schema cannot:
retain requires byte-exact route equality and an empty file list; revise
requires a nonempty route patch and the sole file path. The ordinary trace and
effects audit remains authoritative.

Before actor authorization, recursively scan the schema and fail on `oneOf`,
`anyOf`, `allOf`, `not`, `if`, `then`, `else`, or dependent-schema keywords.
Validate synthetic retain and revise reports against both the actual schema and
the exact local predicate. Validate both route states with the production
route checker. These fixtures must all pass before a raw run directory opens.

## Frozen replication and gate

Otherwise repeat OT-0187 unchanged under disjoint renamed cases: eight active
actors see the wider blocked-option contradiction, eight interleaved controls
see exact receipt erasure, and neither sees OT-0186/0187/0188 outcomes. Bind
every report before direct confirmation; `active-01` is the prospective
successor.

Execute each accepted route directly on six wider blocked-option, four
observation-led, and six mixed cases. Require active 8/8 at 16/16, control at
most 4/8, advantage at least four, the prospective one-sided Fisher boundary
`1/26`, original-route contextual floor 10/10 and wider failure 0/6, identity
18/18, all sixteen complete audits, exact history/surrender preservation, and
an open successor.

Promote only exact `active-01` if all gates pass. A valid rejection ends this
contrast. Passing establishes a replicated consequence-associated increase in
correct machinery revision and later direct operative use, but not receipt
exclusivity, autonomous ontology discovery, interpreter self-revision, or
indefinite recurrence.
