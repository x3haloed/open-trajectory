# Open Trajectory

Open Trajectory is a falsification-first research program for fresh-context
agents whose base model is held under an immutable-revision or receipted hosted-
epoch identity rule while experience accumulates in an external substrate,
improves later predictions as reality changes, and eventually improves the
learning machinery itself.

The primary evidence ladder is:

```text
contact-causal inheritance
→ longitudinal continual adaptation
→ continual machinery refinement
→ Open Developmental Trajectory
```

The subject may inherit a fully functional researcher-designed seed substrate.
The first question is whether its external state updates across inference
passes and causally lowers future prediction error over a long changing stream.
Only the stronger second question asks whether experience improves how that
substrate represents, retrieves, selects, or updates what later instances
inherit.

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

The repository contains several bounded causal footholds:

- **OT-0014:** inherited external state reduced held-out error after complete
  resets in one private, time-bounded hidden-rule envelope. The learning
  machinery was fixed.
- **OT-0037:** completed consequences trained and corrected a generic weighted
  inheritance selector in one publicly reconstructible synthetic domain.
- **OT-0045:** a durable goal contract supported bounded private, time-limited
  goal pursuit in one synthetic domain.
- **OT-0049 through OT-0069:** multiple prospectively tested structural
  carriers failed to produce reliable complete construction and correction
  across two fresh lineages. These negative results localize a one-shot
  inherited-state revision problem; they do not falsify continual adaptation.
- **OT-0070 and OT-0073:** append-only history, active-pointer, projection, and
  reconstruction mechanics were exercised without actor output. Later verifier
  probing exposed a missing fail-closed E13 case/regime binding, so reliance on
  OT-0073's recorded promotion and authorization is suspended pending a
  prospective repair. These are not learning results.

What is still missing is the direct demonstration at the center of the project:
many fresh inference passes from a base held under the existing identity rule,
coupled only by a declared external substrate across a changing and recurring
stream, with prediction error improving reliably relative to equal-budget
controls and no learner-controlled model-weight update.

## Current direction

Prospective E14 design makes longitudinal continual adaptation the immediate
frontier. OT-0075 was rejected on its public design worlds before any private
seed or learner existed: its causal-loss statistic compared ablations with an
unrelated immutable rule and could count a fixed prior difference as surviving
learning. OT-0076 prospectively repairs that gate with a reference-specific
matched-frozen counterfactual and separate updater-state/projection ancestry.
Before a learner runs, its one sealed anchor must still calibrate the stream,
horizon, prequential loss, recovery, recurrence, controls, causal ablations,
receipts, and exact reconstruction.

After that foothold, the program will test incremental learning-machinery
refinement: a bounded, versioned actor-specified change competes prospectively
with its unchanged parent, must improve later learning, and must remain revisable
or recoverable when subsequent contact makes it harmful. Representation escape
remains a stronger later test of developmental expansion, not the entrance exam
for continual learning.

OT-0074 records suspension before any task or actor output. The underlying E13
authorization remains unspent and is not repurposed for E14 or transferable to
a new E13 candidate. E14 is not promoted and authorizes no learner until the
candidate-free held-out anchor checkpoint passes. No prior experiment is
rescored. See
[the E14 epoch](docs/LONGITUDINAL_CONTINUAL_LEARNING_EPOCH.md) and
[the complete program ledger](PROGRAM.md).

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
- [PROGRAM.md](PROGRAM.md) — staged research program and preserved result ledger.
- [docs/LONGITUDINAL_CONTINUAL_LEARNING_EPOCH.md](docs/LONGITUDINAL_CONTINUAL_LEARNING_EPOCH.md)
  — prospective E14 evaluation transition and next-work boundary.
- [docs/RESEARCH_LANDSCAPE.md](docs/RESEARCH_LANDSCAPE.md) — non-normative
  hypothesis map for widening candidate generation.
- [docs/hypotheses/](docs/hypotheses/) — attributed, non-normative design
  proposals that do not alter frozen gates.
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — evidence, privacy, and reconstruction contract.
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — experiment lifecycle and promotion rules.
- `spec/` — validated generic and experiment-specific run contracts.
- `fixtures/encounter-specs/` — small complete instances used to test those contracts.
- `experiments/` — small, append-only public experiment records.
- `evidence/manifests/` — sanitized content-addressed receipts only.
- `src/open_trajectory_evidence/` — recording, verification, and audit tool.
