# OT-0001 — Harness honesty

- **Status:** conditional
- **Evidence class:** public-reconstructible
- **Target:** infrastructure
- **Frozen commit:** pending initial commit

## Hypothesis

The repository can retain independently verifiable experiment receipts without
committing raw evidence or machine-local identity.

## Causal mechanism

A deterministic harness result is written directly into the ignored evidence
store, copied into content-addressed storage, and represented publicly only by
a schema-constrained manifest. A repository audit rejects privacy and storage
violations before publication.

## Cheapest decisive falsifier

Run the test and audit harness, record its result, verify the external object,
then verify a separately supplied copy against the same public manifest.

## Candidate and controls

- Candidate: external content-addressed objects plus public manifests.
- Leak controls: absolute home path, representative credential, forbidden raw
  data extension, and unconstrained public-evidence classification.

## Frozen protocol and acceptance gate

1. All unit leak controls pass.
2. The repository audit passes on the publishable tree.
3. The generated result contains no path or environment value.
4. Local-object and re-supplied-byte verification both pass.
5. No raw result is visible to Git.

## Privacy and storage review

The output contains only check names, counts, and booleans. It is generated
under `.evidence/`, which is ignored. The public manifest is schema constrained.

## Prospective predictions

The selected design should pass all five gates. The most likely initial failure
is the leak detector recognizing its own test patterns.

## Results

The predicted self-match occurred and was corrected by constructing detector
literals without embedding the forbidden byte sequence in source. Final
verification is recorded in the linked manifest.

## Evidence manifests

- `evidence/manifests/OT-0001/harness-result.json`

## Decision, limitations, and next experiment

Conditional infrastructure promotion. This proves the local publication path
and preventive audit on the initial tree. It does not prove historical Git
remediation, remote object durability, or any learning result.

