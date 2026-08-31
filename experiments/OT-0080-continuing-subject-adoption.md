# OT-0080 — continuing-subject evidence adoption

- **Observer disposition:** `conditional`
- **Subject disposition:** `open`
- **Evidence class:** `exploratory-only`
- **Claim scopes:** `operational-transition`, `causal-observation`
- **Target:** OT-1C and bounded OT-2 evidence adoption; no OT-2R promotion
- **Actor calls:** none; this record adopts completed external evidence

## Purpose and boundary

OT-0080 brings the external continuing-subject lineage from E120 through E128
across the G3 adoption boundary. It does not pretend those experiments were
prospectively run under OT or reinterpret their individual frozen gates.

The adopted slice includes protocols, harnesses, actor inputs and outputs,
complete tool traces, audits, bound artifacts, sealed world receipts, failed
and invalid transitions, controls, aggregates, and subject checkpoints.
Duplicate actor workspaces and seed copies are omitted from the compact bundle;
their claim-relevant outputs, patches, bindings, and traces remain.

## Adoption gate

The deterministic adoption verifier must:

1. verify all four manifests against the external object store;
2. confirm that the bundle contains every E120–E128 protocol and result, the
   shallow harness and its tests, and the E128 aggregate and subject;
3. reject duplicate workspaces and runtime caches from the adopted bundle;
4. recompute E128's internal subject seal and opening-grammar identity;
5. match the aggregate's final subject identity and passed operational/causal
   gates;
6. confirm challenge machinery version 2, executable version 4, no pending
   machinery, and zero full-suite passes among four correction-erased controls;
7. confirm that the subject remains open and sounding at
   `execute-subject-owned-challenge-machinery`.

## Result

The gate passed. OT now retains a content-addressed 4,108,800-byte claim bundle,
the exact E128 subject, its aggregate, and the historical shallow actor harness.
The subject file has SHA-256
`6b747a5bb89d57762b101f7250f8051efcbc1fc66d7e9384e0d94319e73519ab`;
its recomputed internal subject identity is
`d0c4bb9bae5c499bd9970e5ec45c12a23130400ec16550f5c1f28be4e0f2f713`.
The deterministic adoption receipt is
`be6e6649ae0c1bd78f8f05b8b06c6c07c9af11d372649d5c04b0c2c18c90a700`.

The adopted causal interpretation remains bounded:

- E120 established one operational actor-authored contact but not its proposed
  state-dependence explanation.
- E121 and E124 established consequence-caused executable correction.
- E125 preserved the negative result that syntactic generator revision did not
  open developmental contact.
- E126/E127 established that retained non-expansion denial changed later
  generator revision behavior on held-out seeds.
- E128 converted the pending contradiction into a 19/19 no-regression repair;
  all four clean correction-erased controls retained the prior floor and zero
  passed the complete suite.

This supports OT-1C operational continuity and bounded OT-2 causal observations.
It does not establish generation frequency, immutable-model attribution,
cross-world transfer, or OT-2R self-directed recurrence: a researcher still
selected experiment boundaries and several phase transitions between E120 and
E128.

## Continuation

The exact adopted subject is the sole parent for the next prospective record.
The next experiment must begin at its declared opening and test whether one
fixed driver can carry another complete subject-owned challenge cycle without
experiment-specific phase selection.

Evidence manifests:

- `evidence/manifests/OT-0080/continuing-subject-e120-e128-bundle.json`
- `evidence/manifests/OT-0080/e128-open-subject.json`
- `evidence/manifests/OT-0080/e128-aggregate.json`
- `evidence/manifests/OT-0080/continuing-subject-harness.json`
- `evidence/manifests/OT-0080/adoption-receipt.json`
