# Evidence, privacy, and reconstruction contract

## Central truth

A real artifact is retained outside Git under its content identity. Git stores
only a bounded, sanitized manifest sufficient to identify, classify, verify,
and—when permitted—reconstruct those bytes.

## Evidence classes

Every manifest declares one class:

1. **public-reconstructible** — the bytes can be regenerated from checked-in
   code and public hashed inputs, or fetched from a stable public source and
   hash-verified.
2. **private-reproducible** — the manifest, protocol, and hash are public, but
   the bytes require private, personal, or licensed inputs. Only an authorized
   holder can reproduce the complete claim.
3. **exploratory-only** — the evidence is incomplete, unavailable, or lacks an
   independent reconstruction path. It may guide the next experiment but may
   not support a public or private reproduction claim.

Classification is about the weakest indispensable input. A public summary of a
private transcript remains `private-reproducible` unless the claim is rerun on
public evidence.

Evidence class describes artifact availability and reconstruction, not causal
validity. An `exploratory-only` actor-generation artifact may still support a
bounded **causal-observation claim** when every actor input/output is retained
and the independent downstream comparison is deterministic and complete. Such
a claim does not promote generation reproducibility, model attribution,
frequency, or cross-deployment reliability. Missing or confounded causal
evidence remains hypothesis-only regardless of storage class.

## Hosted actor provenance

Hosted evidence has two legitimate levels. Do not force the stronger level
when the claim does not require it.

For a bounded causal observation, retain the requested model alias, exact actor
inputs and outputs, client/tool identity when exposed, fresh-context boundary,
time window, and an explicit inventory of unavailable provenance fields. The
actor output becomes a content-addressed historical input to the independently
reconstructed controller comparison. This does not reproduce its generation.

For model-specific attribution or generative reproduction, a hosted model that
exposes no immutable checkpoint may be held fixed only within a prospectively
defined deployment epoch. The raw evidence must additionally retain:

- the requested model alias and every server-reported effective model;
- the model-catalog payload digest and direct model-catalog ETag digest;
- the exact client binary and receipt-implementation identities;
- a private response identifier for every actor turn, with only hashes or an
  aggregate receipt digest entering tracked summaries;
- the frozen original/reproduction window and counterbalanced condition order;
- proof that the epoch fields stayed constant across both workers.

The receipt is an operational identity for the observed deployment, not a
claim about exact weights. A missing, malformed, or changing epoch field
invalidates the model-specific or generative-reproduction claim, not an
otherwise complete bounded causal observation. Deployment-epoch evidence is at
most `private-reproducible`: it is time-bounded and cannot by itself support a
public reconstruction recipe for the hosted deployment.

## Longitudinal trajectory evidence

A longitudinal continual-adaptation claim requires an ordered causal record,
not only an aggregate curve. For every scored encounter, raw evidence must bind:

- the prediction or action recorded before the outcome;
- the independently owned outcome and score receipt;
- the substrate identity before and after the permitted update;
- the update decision, including an explicit no-op when active state is
  preserved;
- for each nonterminal encounter, the exact bounded projection consumed by the
  next fresh actor; for the terminal encounter, a terminal projection receipt
  or explicit final audit-consumer receipt; and
- the frozen regime, task, encounter, and evaluator identities.

The reconstruction path must begin from the initial inherited substrate and
replay the ordered receipts to recover every later substrate identity and
projection, including the terminal state. A summary statistic, final snapshot,
or selected pair of endpoints cannot substitute for that chain. Tracked
summaries may publish bounded trajectory statistics; raw per-encounter records
remain in the external evidence store under their content identities.

The trajectory receipt must also bind the evaluator implementation identity,
candidate seed/updater implementation identity, task-derivation identity, and
proof that candidate implementation preceded fresh stream derivation. Hidden
task seeds, schedules, references, and heldouts remain private inputs and enter
tracked summaries only through allowed digests.

Also bind the prospectively frozen derivation-function identity, domain tag,
clean implementation identity, private-seed digest, derived-stream digest,
attempt count, and any collision disposition. The private seed is generated
only after clean implementation and remains an external input; an implementation
identity alone is not the hidden anchor. A promoted anchor or candidate stream
has exactly one allowed derivation attempt unless the pre-implementation
protocol fixed a different deterministic collision rule.

For each reset boundary, raw evidence also binds an opaque fresh-process
instance identity, the exact empty workspace before and after consumption, an
allowlisted environment fingerprint, absence of response chaining, and the
result of prospectively planted forbidden-channel sentinels. The consumer call
graph must exclude undeclared filesystem, network, tool, subprocess, task-
loader, and controller-cache continuity. Rewind/replay evidence binds the
checkpoint, byte-exact same-suffix reconstruction, isolated alternate branch,
inactive sibling, and rejection of a projection substituted across branches.

A candidate-free evaluator checkpoint must label its controller references as
surrogates. Their prediction and update call graphs may consume only the current
public query, their bounded inherited state, and outcomes previously released
in order. High-scoring future- or hidden-truth oracles are retained only as
negative authority tests. Such a checkpoint cannot supply fresh base-model
identity or actor-behavior evidence and therefore cannot itself support a
continual-adaptation claim.

Machinery-refinement evidence additionally binds the incumbent and candidate
machinery identities, their common parent, the bounded delta, proposal and
adoption receipts, the author/tune, adoption-validation, and sealed post-
adoption confirmation partitions, the exact common starting content identity
and matched encounter evidence for both branches, and any rollback or
replacement lineage. The proposal and frozen commit rule predate validation.
If validation selects among alternatives, a disjoint confirmation window must
evaluate the selected child. Evidence used to author, tune, or select a change
cannot establish its claimed future benefit.

## Public manifest

A manifest contains only:

- schema version;
- experiment and logical artifact identifiers;
- artifact kind and media type;
- SHA-256 and exact byte count;
- evidence class;
- a logical reconstruction recipe or public HTTPS source when applicable;
- an allowlisted environment fingerprint;
- hashes of indispensable input manifests;
- limitations and claim scope.

Forbidden fields include source path, current directory, home directory,
username, hostname, raw environment, command transcript, secret, and arbitrary
metadata maps.

## External object store

`OT_EVIDENCE_ROOT` selects a machine-local or mounted evidence root. If unset,
the tool uses the ignored `.evidence/` directory. Objects are stored at:

```text
$OT_EVIDENCE_ROOT/objects/sha256/<first-two-hex>/<full-sha256>
```

The path is an implementation detail and never enters a public manifest. The
same manifest can be verified against any store containing the identified
object or against explicitly supplied reconstructed bytes.

Backups, encryption, remote synchronization, and retention of this store are
operator responsibilities and are deliberately outside the public repository's
authority.

## Reconstruction levels

- **Manifest verification:** schema, identifiers, hashes, byte counts, privacy,
  and repository policy are internally valid.
- **Byte verification:** supplied or locally present bytes match the manifest.
- **Process reproduction:** the frozen recipe regenerates matching bytes.
- **Independent reproduction:** another environment performs process
  reproduction without access to the original raw object.

Reports must name the highest level actually completed.

## Safe environment fingerprint

The recorder captures only OS family, machine architecture, Python
implementation/version, and Git commit/dirty boolean when available. It never
captures environment values, path-valued executable metadata, username,
hostname, or installed-package locations.

Dependency identity belongs in checked-in lock files and their hashes, not in
an unconstrained `pip freeze` dump that may contain editable local paths or
private package sources.

## Publication gate

Before every commit and in CI:

1. enumerate the exact tracked tree;
2. reject heavyweight files and aggregate repository growth beyond policy;
3. reject raw-evidence locations and forbidden heavyweight extensions;
4. scan text for absolute home paths and high-confidence secret patterns;
5. validate every evidence manifest and reject forbidden keys or values;
6. run the test suite.

This prevents new leaks. It cannot erase secrets already committed to Git
history; any historical leak requires credential rotation when applicable and
explicit history remediation before publication.
