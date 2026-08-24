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
   not support a promoted result.

Classification is about the weakest indispensable input. A public summary of a
private transcript remains `private-reproducible` unless the claim is rerun on
public evidence.

## Hosted deployment-epoch evidence

A hosted model that exposes no immutable checkpoint may be held fixed only
within a prospectively defined deployment epoch. The raw evidence must retain:

- the requested model alias and every server-reported effective model;
- the model-catalog payload digest and direct model-catalog ETag digest;
- the exact client binary and receipt-patch identities;
- a private response identifier for every actor turn, with only hashes or an
  aggregate receipt digest entering tracked summaries;
- the frozen original/reproduction window and counterbalanced condition order;
- proof that the epoch fields stayed constant across both workers.

The receipt is an operational identity for the observed deployment, not a
claim about exact weights. A missing, malformed, or changing epoch field
invalidates the run. This evidence is at most `private-reproducible`: it is
time-bounded and cannot by itself support a public reconstruction recipe for
the hosted deployment.

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
