# Open Trajectory

Open Trajectory is a falsification-first research program for persistent agents
that learn from contact, author durable goals, and earn wider authority through
independent evidence.

The repository is intentionally split across two storage classes:

```text
Git repository                    External evidence store
-------------------------------   ----------------------------------
targets and red lines             raw model/tool transcripts
experiment protocols              datasets and checkpoints
small deterministic fixtures      generated outputs and traces
content hashes and manifests  ←→  content-addressed evidence objects
summaries with bounded claims      private or licensed material
```

The public repository is the authority for what was claimed. The external
store is the authority for the bytes supporting locally reproducible claims.
A checked-in manifest joins them without publishing machine paths, usernames,
environment variables, hostnames, or raw evidence.

## Current evidence horizon

The repository currently realizes the evidence-publication path, not OT-1:

```text
real artifact
→ SHA-256 content identity
→ external object store
→ sanitized public manifest
→ independent manifest/reprovided-byte verification
→ repository privacy and size audit
```

No learning, self-direction, or TAAA result is claimed yet.

## Quick start

Requires Python 3.11 or newer. The evidence CLI has no runtime dependencies;
the test environment is pinned separately.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-test.lock
python3 -m pip install --no-deps -e .
python3 -m unittest discover -s tests
ot-evidence audit
```

Record an artifact. Its raw bytes go into the ignored external store; the
manifest goes into Git:

```bash
ot-evidence record \
  --experiment OT-0001 \
  --artifact-id leak-control-result \
  --kind test-result \
  --input /path/to/result.json \
  --recipe 'python -m experiments.ot_0001.run --case leak-control'
```

Verify against the local object store:

```bash
ot-evidence verify evidence/manifests/OT-0001/leak-control-result.json
```

An independent verifier can provide reconstructed bytes without reproducing
the original storage path:

```bash
ot-evidence verify MANIFEST.json --artifact RECONSTRUCTED_RESULT.json
```

Install the same audit as a local pre-commit hook:

```bash
git config core.hooksPath .githooks
```

CI runs the audit and tests on every push and pull request.

## Repository map

- [TARGET.md](TARGET.md) — normative research targets and stopping conditions.
- [RED_LINES.md](RED_LINES.md) — shortcuts and leak classes that do not count.
- [PROGRAM.md](PROGRAM.md) — staged research program.
- [docs/RESEARCH_LANDSCAPE.md](docs/RESEARCH_LANDSCAPE.md) — non-normative
  hypothesis map for widening candidate generation.
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — evidence, privacy, and reconstruction contract.
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — experiment lifecycle and promotion rules.
- `spec/` — validated generic and experiment-specific run contracts.
- `fixtures/encounter-specs/` — small complete instances used to test those contracts.
- `experiments/` — small, append-only public experiment records.
- `evidence/manifests/` — sanitized content-addressed receipts only.
- `src/open_trajectory_evidence/` — recording, verification, and audit tool.
