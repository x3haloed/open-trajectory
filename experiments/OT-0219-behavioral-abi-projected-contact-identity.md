# OT-0219 — behavioral ABI-projected contact identity

- **Status:** frozen; not yet run; no actors required
- **Evidence class:** exploratory-only
- **Target:** prospective G5 → G6 liveness-evaluator transition
- **Construction evidence:** OT-0218 pending recovery cases duplicate completed
  inputs plus an ignored `world` field
- **Parent:** exact OT-0218 operational successor `2d5a0cf4...`

## Transition reason

G5 improved continuation liveness by requiring executable unreceipted contact
and canonicalizing away prose, local case IDs, and order. It still hashes raw
case-input JSON. OT-0218 demonstrates that an actor can add a field ignored by
the callable and receive four nominally new inputs without changing any
behavioral contact.

Expected: new canonical input meant new executable contact. Observed: removing
`world` from each pending input makes it byte-identical to completed OT-0215
contact, and both installed and reference callables ignore the field. The
maintenance correction and all world receipts remain valid. Only pending
reopening liveness is invalidated.

## Incumbent G5

G5 contact identity hashes target, path, ABI label, fixed predicates, and sorted
raw case inputs. It rejects renamed or reordered duplicates but treats any raw
input-field addition as novel.

All G5/G4 hard anchors remain non-negotiable: exact ancestry, actor/workspace
freshness, bind-before-consequence, independent receipts, contained effects,
extension bounds, route and identity floors, privacy, and no retrospective
rescoring of operational outcomes.

## Challenger G6

G6 replaces raw case-input identity with a behavioral ABI projection derived
without observer-authored field lists.

For each case, execute both the installed callable and its independently frozen
reference. Recursively consider removable mapping fields in a deterministic
path order. A field is omitted from the canonical projection only when deleting
it leaves both executions valid and leaves both exact outputs unchanged. Repeat
to a fixed point. Preserve list order, scalar values, and every field whose
removal changes output or validity in either implementation.

Contact identity then hashes target, path, ABI, fixed predicates, and sorted
projected inputs. G6 liveness still requires four executable cases, no existing
independent receipt, and at least two projected inputs absent from completed
contact. Projection grants no world, scoring, or admission authority.

Using both installed and reference behavior is essential. A currently wrong
implementation may ignore a field that the admitted reference uses; such a
field remains part of contact identity.

## Construction and held-out anchors

Use the exact OT-0218 decorated recovery package only for construction. Freeze
the projection algorithm before opening a seeded held-out bundle containing:

- top-level ignored decoration on completed inputs;
- ignored nested decoration;
- multiple ignored decorations and reordered/local-renamed cases;
- genuinely new capacity, effort, probability, duration, and severity values;
- fields ignored by installed behavior but used by reference behavior;
- deletion that changes validity rather than output;
- four genuinely new projected inputs with poor prose;
- one genuinely new projected input plus three decorated duplicates;
- already-receipted projected package identity; and
- every G5 malformed/extension boundary anchor.

G6 must collapse every decorated duplicate, retain every field relevant to
either implementation, accept every genuinely new package, and reject stale or
malformed packages. G5's historical raw decisions are preserved; the bundle
measures the identified blind spot, not a retrospective reclassification of
past operational results.

The seeded bundle contains sixteen fixtures. Preflight expects G6 16/16 and
observes G5 at 12/16. Separate anchors require determinism under key and case
order, collapse of ignored top-level and nested decoration, retention of
capacity needed for validity, and retention of probability used only by the
independent relief reference.

## Promotion

Promote G6 only if:

- all held-out labels are correct and materially outperform G5 on decorated
  live/stale pairs;
- projection is deterministic under key insertion and case presentation order;
- installed/reference exceptions are identity-relevant, never silently erased;
- all prior hard anchors and G5 malformed boundaries remain exact;
- the OT-0218 correction capability and receipts remain byte-equivalent;
- the pending decorated recovery package is marked `liveness-unresolved` while
  its raw bytes remain preserved;
- route 16/16, identity 18/18, reconstruction, and privacy pass; and
- the exact successor conforms.

On promotion, future liveness uses G6. Historical world observations and
correction claims stand. G5 liveness conclusions become stale only when they
are next decision-relevant.

## Claim boundary

A pass establishes a more causally faithful contact identity for this bounded
Python/JSON interface: irrelevant decoration cannot keep the song going, while
behaviorally relevant input survives projection. It does not solve semantic
importance, adversarial equivalence in arbitrary programs, undecidable program
analysis, or observer ownership of the installed/reference interface.

## Result

Not yet run.
