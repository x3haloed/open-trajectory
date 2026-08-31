# Research workflow

The workflow exists to protect causal interpretation while keeping actor
learning—not evaluator construction—the dominant activity.

## 1. Name the observation and the subject boundary

Create one stable `OT-NNNN` record for one causal hypothesis or one bounded
operational-recurrence observation. Identify the exact starting subject and
state whether the record is testing an operational transition, a causal
mechanism, recurrence, or generation reliability. Before actor output, freeze:

- the expected mechanism and cheapest falsifier;
- actor-visible information and inherited substrate;
- the decision envelope, including what the subject may choose or author;
- world derivation and held-out boundaries;
- independently owned outcomes and score;
- unchanged-parent and simpler controls;
- decisive ablation and later harmful regime when relevant;
- actor-call, implementation, protocol-repair, and wall-time observer budgets;
- the observation stopping rule, subject closing rule, and promotion rules.

Protocol, implementation, pre-contact operational repair, execution,
reconstruction, and disposition are phases of the same experiment. Several
subject transitions may occur inside one record. Assign a new ID only when the
hypothesis, world, outcome, causal comparison, or acceptance rule materially
changes—not because a model turn ended.

## 2. Cross the risky causal edge first

Build the smallest actor-bearing path from inherited state through completed
contact, independent consequence, permitted update, reset, later behavior, and
held-out score. Do not build a general evaluator, security boundary, journal,
or receipt framework before this path runs unless a named false-positive story
requires it.

A candidate-free probe is allowed only when it is the cheapest discriminating
test of that story. Its implementation cost may not exceed the candidate it
gates without an explicit project decision.

For executable carriers, freeze machine-run conformance fixtures for the
evaluator-facing ABI and protected authority boundary before actor
authorization. Do not require arbitrary actor-authored programs to use a
researcher-selected internal representation.

## 3. Run the subject privately

Use a fresh actor thread and fresh workspace for every learning encounter.
Continuity may cross encounters only through the named substrate and exact
controller projection. Write raw inputs, outputs, traces, and receipts directly
to `$OT_EVIDENCE_ROOT` or ignored `.evidence/`.

The observer owns world state, hidden outcomes, scoring, snapshot identity,
claim disposition, and evidence publication. The subject may own continuation
state, pursuit selection, actor reopening, candidate contact machinery, and
proposed substrate changes inside the frozen envelope.

Give actors the declared tool condition, including ordinary broad tools when
that is the intended subject. Run them in isolated workspaces, retain complete
tool traces, audit actual effects, and quarantine runs that touch non-admitted
authority. Do not substitute a crippled actor for apparatus-side protection.

## 4. Seal operation, then compare causal branches

If an operational transition passes its frozen gate, seal the exact successor
before running observational controls. Controls cannot mutate, delay, or veto
that successor.

For a causal claim, apply changed and unchanged substrates deterministically to
the same held-out opportunity, or use a prospectively powered paired stochastic
design. Treat self-report as a hypothesis, not evidence. A component result
does not count as endpoint success. An operational-only record must say that it
does not establish causal frequency.

When a protocol deviation appears, invalidate only if it can affect actor
information, outcome or scoring authority, branch comparability, acceptance,
safety, or the claimed mechanism—or if materiality is uncertain. Otherwise
disclose the nonconformance and remove only the unsupported conformance claim.

## 5. Record the bounded result

Use `ot-evidence record` for raw-artifact identity. Keep causal validity,
generative reproducibility, and actor provenance separate under
`docs/CLAIM_REGIME.md`. Preserve negative results and the original interpretation
of later-reassessed evidence.

Before a normal commit or bounded result, run:

```bash
python3 scripts/verify.py fast
```

Run the archival suite when historical harnesses, shared evidence machinery, or
frozen reconstruction paths change, and before a tagged release:

```bash
python3 scripts/verify.py archive
```

Inspect the exact staged diff. Automated checks do not authorize publication of
sensitive material.

## 6. Stop observing without silently stopping the subject

Stop the research observation at the frozen actor, repair, and time budgets.
Do not turn a failed mechanism claim into an unreported evaluator,
operating-system isolation, or representation-family project. Preserve the
failure.

Then record the subject disposition separately:

- `open`: exact valid state has a mechanically reachable next opening;
- `closed`: admitted subject state or independent consequence ended it;
- `quarantined`: the latest encounter was invalid, so continuation reopens from
  the last valid parent; or
- `lost`: reconstruction or authority failure prevents safe reopening.

Observation completion is not a fifth subject disposition. A run that continues
usefully beyond the observer budget is not, for that reason, a failed run.

Allowed dispositions remain `promoted`, `conditional`, `rejected`, `reversed`,
`invalidated`, and `unexecuted`.

The former workflow is preserved at `docs/archive/WORKFLOW_G1.md` for historical
interpretation only.
