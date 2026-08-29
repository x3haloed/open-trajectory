# Open Trajectory

Open Trajectory is an empirical research program for developmental loops across
fresh agent contexts.

It asks three questions:

1. Does inherited external state improve later behavior?
2. Do completed consequences improve how inheritance itself works?
3. Can later consequences correct those improvements when they become harmful?

The repository favors small actor-bearing causal experiments over evaluator and
containment infrastructure. Stronger claims require stronger evidence, but the
strongest available provenance tier is not an entrance requirement for a
bounded causal observation.

## Current state

The strongest footholds are:

- `OT-0014`: bounded contact-causal inheritance;
- `OT-0037`: bounded deterministic selector improvement and correction;
- `OT-0045`: bounded durable goal pursuit; and
- `OT-0079`: conditional bounded evidence that making composition and stopping
  one consequence-addressable program repaired a split-authority failure.

The negative carrier experiments `OT-0048`–`OT-0069` remain useful evidence:
changing expression, predicate, transducer, topology, or partition
representations did not reliably solve grounded inherited-state revision.

See [the current frontier](docs/FRONTIER.md), [the research program](PROGRAM.md),
and [claim regime G2](docs/CLAIM_REGIME.md). The former cumulative ledger is
archived at [docs/archive/PROGRAM_G1.md](docs/archive/PROGRAM_G1.md).

## Repository authority

```text
Git repository                    External evidence store
-------------------------------   ----------------------------------
targets and red lines             raw model/tool transcripts
experiment records                generated outputs and traces
small deterministic fixtures      datasets and checkpoints
content hashes and manifests  ←→  content-addressed evidence objects
bounded interpretations           private or licensed material
```

Raw evidence never enters Git. Sanitized manifests identify retained artifacts
without publishing machine-local paths or secrets.

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-test.lock
python3 -m pip install --no-deps -e .
python3 -m unittest discover -s tests
ot-evidence audit
```

Record and verify an artifact:

```bash
ot-evidence record \
  --experiment OT-0001 \
  --artifact-id result \
  --kind test-result \
  --input $EVIDENCE/result.json

ot-evidence verify evidence/manifests/OT-0001/result.json
```

## Repository map

- [TARGET.md](TARGET.md) — target definitions and claim boundaries.
- [RED_LINES.md](RED_LINES.md) — causal shortcuts that do not count.
- [PROGRAM.md](PROGRAM.md) — compact current program policy.
- [docs/FRONTIER.md](docs/FRONTIER.md) — sole current decision surface.
- [docs/RESEARCH_LANDSCAPE.md](docs/RESEARCH_LANDSCAPE.md) — non-normative
  hypothesis map.
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — evidence and privacy contract.
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — experiment lifecycle.
- `experiments/` — immutable experiment plans and results.
- `evidence/manifests/` — sanitized content identities.
- `src/open_trajectory_evidence/` — evidence recording and audit tools.
