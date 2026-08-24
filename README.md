# Open Trajectory

Open Trajectory is a falsification-first research program for persistent agents
whose experience can change what they carry forward, later correct that
selection function, author durable goals, and earn wider authority through
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

The repository has established a narrow OT-0 contact-causal inheritance result:

```text
independent world outcome
→ bounded inherited projection
→ complete thread/workspace reset
→ lower structural-heldout error in a fresh instance
→ loss of the advantage under projection ablation
→ clean reproduction in one receipted hosted epoch
```

OT-0014 supports that claim only within its private, time-bounded hidden-rule
envelope. It does not establish OT-1. The inheritance-selection function was
researcher-designed and fixed; no experience-induced selector change, emergent
selection operation, or later selector correction has yet been demonstrated.
OT-0004 remains an invalidated negative result: its free-form selector changed
state, but stochastic selector and predictor branches prevented causal
attribution and its aggregate behavior missed every target-level gate.
OT-0005 removed that attribution confound with deterministic program execution
and a passing identity-program placebo in its complete worker, but was rejected
at its frozen carrier gate and did not produce recursive correction.
OT-0020 later failed the exact-opportunity E4 endpoint, and OT-0021 through
OT-0025 progressively falsified the richer-trace, single-challenger, and
free-form portfolio carriers without target authority. OT-0026, the final
public development falsifier, used an exact actor-authored stack score
program plus the already-validated structured decision list. OT-0026 was
invalidated by a post-encounter controller failure before result sealing, so it
has no scientific carrier outcome and provides neither OT-1 evidence nor E4
authorization.
OT-0027 tested the materially different exemplar representation. Both actors
committed valid casebooks but optimized positive-label frequency, converged on
the same non-discriminative selection, and gained zero errors. This closes the
direct exemplar path without OT-1 or E4 authority.
OT-0028 passed its public development falsifier. Two fresh actors continued one
actual failed OT-0027 trajectory, committed different revised casebooks, and
independently reduced future error from eight to zero. This establishes one
consequence-induced correction slice only, with no OT-1 or E4 authority.
OT-0029 carried the first useful OT-0028 casebook into a later harmful
encounter. One fresh actor reversed from sixteen to zero canary errors; the
other reached nine and missed the frozen gate. The mixed experiment failed and
provides no OT-1 or E4 authority.
OT-0030 continued the failed nine-error OT-0029 revision. One fresh instance
recovered to zero; the other reached seven, so the frozen preserved-correction
gate failed. It demonstrates remaining correction capacity but not reproducible
one-turn further correction, and has no OT-1 or E4 authority.
OT-0031 tested two independent four-encounter proposal/score/revision branches.
Both revision actors received exact candidate receipts and changed state, but
neither improved completed or future error. The frozen validation-loop path is
closed without OT-1 or E4 authority.
OT-0032 passed its frozen deterministic walking skeleton. Completed outcomes
changed the initial six-pattern state from eight errors to a zero-error learned
state; later contradiction raised the unchanged state to sixteen errors, and a
second update committed a different zero-error state. The unchanged-state
ablation incurred sixteen errors, while the learned states' aggregate error was
zero against eight for the best fixed control. This establishes public
mechanism feasibility for outcome-optimized selector state only. The optimizer
family and world remain researcher-authored, so it is not OT-1 or E4 evidence.
OT-0033 passed its post-implementation blind-criterion falsifier. Completed
selection errors changed a generic four-weight selector through three fresh
regimes with contact errors `40 → 80 → 80` and zero errors on every post-update
canary. Withholding outcome credit prevented every change; unchanged selectors
retained `40 → 80 → 80` canary errors; and the adaptive aggregate beat the best
frozen control, zero errors versus eighty. The task-specific criterion was
mechanically fixed only after the implementation commit. This is public
learned-criterion feasibility, not an OT-1 or evaluator-authorized result.
OT-0034 passed the controller-only E5 calibration. All 384 weighted criteria
passed opposite-world indistinguishability, fixed-state symmetry, outcome
deletion/rescue, order placebos, and exact opportunity checks. Static
reachability found no task, seed, hidden-criterion, dynamic, file, import, or
execution authority available to the learner. E5 now authorizes exactly one
fresh OT-0 integration candidate; the calibration itself is not OT-1 evidence.
No OT-2 self-direction or OT-3 TAAA result is claimed.

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
- [docs/hypotheses/](docs/hypotheses/) — attributed, non-normative design
  proposals that do not alter frozen gates.
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — evidence, privacy, and reconstruction contract.
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — experiment lifecycle and promotion rules.
- `spec/` — validated generic and experiment-specific run contracts.
- `fixtures/encounter-specs/` — small complete instances used to test those contracts.
- `experiments/` — small, append-only public experiment records.
- `evidence/manifests/` — sanitized content-addressed receipts only.
- `src/open_trajectory_evidence/` — recording, verification, and audit tool.
