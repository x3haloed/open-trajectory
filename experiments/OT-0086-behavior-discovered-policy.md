# OT-0086 — behavior-discovered policy contact

- **Status:** unexecuted
- **Evidence class:** exploratory-only
- **Target:** cross-environment OT-2R and consequence-grounded discovery
- **Claim scopes sought:** `operational-transition`, bounded
  `causal-observation`
- **Parent:** exact OT-0085 open subject
- **Actor budget:** at most three discovery actors and three implementation
  actors
- **Observer budget:** one complete driver invocation; 60 minutes

## Hypothesis

Starting from OT-0085's exact open subject, a fresh actor can inspect a complete
dispatch system, run its public observation program, and formulate a candidate
frontier from behavioral regret rather than source stubs or a supplied menu.
The inherited developmental selector can choose one proposed intervention, a
separate fresh actor can implement it, and independent held-out consequence can
admit and retain a better policy while the exact subject remains open.

The narrower causal prediction is that the admitted improvement depends on
composition of the environment's timeliness and reliability signals. After the
operational successor is sealed, neutralizing reliability should remove the
candidate's advantage over the unchanged policy.

## Cheapest falsifier

Reject operational contact if the discovery actor cannot formulate three
distinct interventions from the complete code and public outcome observations;
if an observer must supply the chosen policy idea; if the selected patch is
invalid, regresses any public confirmation case, or fails the frozen held-out
gain; or if no admitted successor appears within three attempts.

Reject the bounded composition interpretation if the operational successor is
not sealed before ablation, or if the candidate retains a material advantage
when reliability is neutralized under the same held-out cases.

## Starting subject

Materialize `open-subject-after-discovered-contact` through its OT-0085 manifest
and verify byte identity, internal seal, sounding runtime, exact digest
`90cba459564f3a4080c106a6d24616ce947e3b99b79cf9636d4d9e477f2b4998`,
and opening `inspect-and-select-environmental-intervention`.

## Complete behavioral world

The actor receives one isolated Python repository with no TODO,
`NotImplementedError`, incomplete function, failing public test, candidate list,
or preferred target. Its declared command `python3 observe.py` executes the
unchanged policy on frozen public dispatch scenarios and emits per-case JSON
containing the selected worker, completion time, reliability, realized expected
score, best available score, and regret.

The repository contains:

- `dispatch/world.py`: complete, actor-visible completion-time and expected-score
  semantics;
- `dispatch/signals.py`: complete timeliness and reliability signals;
- `dispatch/policy.py`: a complete valid policy choosing the fastest worker;
- `dispatch/public_cases.py`: frozen public scenarios; and
- `observe.py` plus passing policy-ABI and world-floor tests.

The public cases include regimes where speed alone is correct, where reliability
dominates among on-time workers, and where lateness changes the choice. They are
evidence used to author proposals and cannot establish future gain.

Hidden cases are derived and sealed before actor authorization. They vary job
cost, deadline, value, lateness penalty, worker speed, and worker reliability.
They are never actor-visible. The world score is the sum of actor-visible
`expected_score` values; the oracle independently takes the best valid worker
per case.

## Actor-authored intervention frontier

The discovery actor may edit exactly `frontier.json`. A complete
`frontier-contract.json` requires exactly three distinct intervention proposals.
Each proposal contains:

- `target_path = dispatch/policy.py` and
  `target_symbol = choose_worker`, both validated against the complete source;
- a distinct bounded `implementation_opening` and `rationale`;
- `axis_chord`, `reversibility`, `immediate_gain`, and `axis_lumen` in `[0, 4]`;
  and
- `collision`, `held_repeat`, `irreversible_closure`, and `world_invalid`.

The same target may appear three times because the candidates are alternative
behavioral interventions, not researcher-enumerated files. The driver derives
each stable identity from target plus implementation opening and rejects
duplicate identities. The actor does not provide a trusted identifier or
directly select an intervention.

Before authorization, conformance proves the template is complete but rejects
placeholders, a representative three-proposal frontier passes, duplicate
openings fail, target/symbol validation reaches the real complete policy, the
public observation command runs, and all floor tests pass.

## Selection and implementation

After binding the actor-authored frontier, apply the exact inherited selector:

1. reject inherited flags and previously denied candidate identities;
2. require `axis_chord >= developmental_selector.threshold`;
3. rank descending by `axis_chord`, `reversibility`, `immediate_gain`, then
   `axis_lumen`; and
4. break ties by derived identity.

A separate fresh actor receives the exact selected proposal and a fresh copy of
the complete repository. It may edit exactly `dispatch/policy.py`. The public
ABI is:

```text
choose_worker(job, workers) -> one existing worker id
```

The patch is audited and bound before hidden consequence.

## World score and admission

The observer evaluates unchanged and candidate policies from the same clean
parent on identical cases.

- Both policies must return a valid worker on every public and hidden case.
- The candidate may lose no public case relative to the unchanged policy.
- On hidden cases, candidate total expected score must exceed the unchanged
  total by at least `25.0` and reach at least `95%` of the oracle improvement
  over unchanged.
- All repository floor tests must pass with the candidate source.

An invalid or regressing patch stops the observation and preserves the last
valid open subject. A valid non-improving patch compiles a world-owned denial
and opens a fresh discovery actor with that candidate identity unavailable.
At most three attempts may occur. The researcher may not supply a proposal,
choose a retry, repair code, or change cases, thresholds, or score after output.

Passing admission retains the bound actor-authored frontier, selected proposal,
policy source, unchanged/candidate/oracle receipt, and new tool-world capability.
It increments the capability ledger by exactly one, marks the subject sounding,
and reopens at `inspect-and-select-environmental-intervention`.

## Post-seal causal ablation

Only after writing the exact sealed operational successor, replay the unchanged
and candidate policies on the same hidden cases with every worker reliability
set to `1.0`. Speed, deadline, value, lateness penalty, case order, policy code,
and resources remain unchanged.

The bounded composition claim passes when the candidate's original hidden gain
meets promotion but its reliability-neutralized gain is less than `5.0`. The
ablation is observational and cannot mutate, delay, or veto the successor.

## Frozen predictions

- The first discovery actor will use `python3 observe.py`, recognize that the
  fastest-worker policy leaves reliability-dependent regret, and formulate
  three distinct complete-policy interventions.
- It will rank a timeliness/reliability composition above threshold, and the
  inherited selector will choose it.
- A separate implementation actor will edit only `dispatch/policy.py`, preserve
  the public floor, and reach at least 95% of the hidden oracle improvement.
- The exact successor will retain the behavioral frontier and policy capability
  and reopen sounding.
- Reliability neutralization will reduce candidate advantage below `5.0`.

## Researcher-causation inventory

- **Researcher-owned:** complete world code, public/hidden cases, score,
  thresholds, isolation, outcome execution, and admission authority.
- **Subject-owned:** inspection and live observation, candidate formulation and
  assessment, inherited selection, patch content, denial-shaped retry,
  capability retention, and next opening.
- **Removed here:** supplied candidate catalog, unfinished-source markers, and
  experiment-specific target selection.

This remains a bounded synthetic dispatch world. Passing would establish one
cross-environment behavioral discovery, not open-world search, generation
frequency, arbitrary-policy learning, or subject ownership of world/admission.

## Observation and subject stopping

The observer stops after one admitted successor and its ablation, three
exhausted attempts, material contamination, or 60 minutes. Only independently
supported admitted state may close the subject. Every other endpoint preserves
the exact last valid subject as open or quarantined from that parent.
