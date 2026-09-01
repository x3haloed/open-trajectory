# Open Trajectory

Open Trajectory is an empirical research program for continuing subjects across
fresh agent contexts and model-turn endings.

It asks four questions:

1. Does inherited external state improve later behavior?
2. Do completed consequences improve how inheritance itself works?
3. Can later consequences correct those improvements when they become harmful?
4. Can the subject itself carry what matters next until the research program is
   an observer rather than the cause of continuation?

The preferred experiment starts from the last valid open subject, gives fresh
actors the declared real tool condition, binds actor-authored contact before
independent consequence, and follows the subject's own next opening. Controls
bound causal claims after an operational successor is sealed; they do not own
or terminate the lineage.

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
- `OT-0087`: one operational actor-originated pursuit handoff across a fresh
  successor; and
- `OT-0088`: a rejected unseen-world continuation whose primary route selected
  the pursuit-aligned contact but whose successor carrier failed on an exact
  lifecycle literal before hidden consequence.
- `OT-0089`: one promoted hidden-admitted continuation with harness-derived
  liveness, alongside a clean rejection of its stronger pursuit-conditioned
  target-selection prediction.
- `OT-0090`: one promoted confirmation-driven renewal that adds a hidden-valid
  verifier without policy mutation and exposes the next gap: assimilating
  consequence before carrying the opening onward.
- `OT-0091`: a rejected mandatory-revision test showing that unchanged pursuit
  can preserve genuinely missing contact rather than constitute repetition.
- `OT-0092`: one promoted end-to-end loop from retained stake through
  actor-authored contact and independent consequence to fresh-actor pursuit
  retirement, with an outcome-erased control.
- `OT-0093`: one rejected self-allocation attempt that localized an apparatus
  ontology error: the actor retired the saturated pursuit and produced a
  hidden-valid generic allocator, while the frozen gate required the dead
  pursuit to remain an actionable contact.
- `OT-0094`: one rejected live-frontier correction whose actor passed the
  frontier and allocator conditions post hoc but exposed an overbroad lexical
  traversal rule in the contained-effects audit.
- `OT-0095`: one rejected normalized-audit correction that admitted contained
  tool use and exposed an unpublished all-string choice ABI.
- `OT-0096`: one rejected typed-choice run that reached exact binding and then
  exposed a substantive failure to embody the retained compositional selector.
- `OT-0097`: one rejected consequence-correction run whose fresh actor repaired
  observed cases locally but did not generalize the complete priority.
- `OT-0098`: one rejected iterated-correction run whose second fresh corrector
  improved the allocator to six of eight disjoint cases while leaving two
  semantic errors.
- `OT-0099`: one rejected third-correction run that fixed regret direction and
  reached seven of nine new cases, leaving only Boolean-threshold semantics.
- `OT-0100`: one rejected threshold-correction run whose fourth fresh corrector
  generalized fully and caused an admitted joint implementation before a final
  assimilation ABI mismatch.
- `OT-0101`: one promoted derived-retention run carrying the exact corrected
  allocator through grounded fresh assimilation; its outcome-erased control
  did not reproduce the correction.
- `OT-0102`: one rejected two-cycle recurrence run whose inherited opening
  caused a novel oracle-valid joint contact before an ordered multi-file audit
  defect stopped the first promotion.
- `OT-0103`: one promoted fixed-driver run reconstructing that first cycle and
  completing a second fresh cycle; its exact open successor binds an allocator
  challenge as the next interface.
- `OT-0104`: one rejected cross-interface continuation whose subject binding
  entered allocator contact directly, but whose authored frontier artifact had
  an under-specified wrapper shape and out-of-bounds decoy values.

The negative carrier experiments `OT-0048`–`OT-0069` remain useful evidence:
changing expression, predicate, transducer, topology, or partition
representations did not reliably solve grounded inherited-state revision.

See [the current frontier](docs/FRONTIER.md), [the research program](PROGRAM.md),
and [claim regime G3](docs/CLAIM_REGIME.md). The former cumulative ledger is
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
python3 scripts/verify.py fast
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
- [docs/archive/](docs/archive/) — displaced program, workflow, epoch, harness,
  and research-landscape history; preserved as evidence, not live authority.
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — evidence and privacy contract.
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — experiment lifecycle.
- `scripts/verify.py` — fast active checks and explicit archival verification.
- `experiments/` — immutable experiment plans and results.
- `evidence/manifests/` — sanitized content identities.
- `src/open_trajectory_evidence/` — evidence recording and audit tools.
