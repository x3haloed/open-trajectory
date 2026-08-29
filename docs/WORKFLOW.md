# Research workflow

The workflow exists to protect causal interpretation while keeping actor
learning—not evaluator construction—the dominant activity.

## 1. Name one causal hypothesis

Create one stable `OT-NNNN` record for one causal hypothesis. Before actor
output, freeze:

- the expected mechanism and cheapest falsifier;
- actor-visible information and inherited substrate;
- task order and held-out boundaries;
- independently owned outcomes and score;
- unchanged-parent and simpler controls;
- decisive ablation and later harmful regime when relevant;
- actor-call, implementation, protocol-repair, and wall-time budgets; and
- the stopping and promotion rules.

Protocol, implementation, pre-contact operational repair, execution,
reconstruction, and disposition are phases of the same experiment. Assign a new
ID only when the hypothesis, world, outcome, causal comparison, or acceptance
rule materially changes.

## 2. Cross the risky causal edge first

Build the smallest actor-bearing path from inherited state through completed
contact, independent consequence, permitted update, reset, later behavior, and
held-out score. Do not build a general evaluator, security boundary, journal,
or receipt framework before this path runs unless a named false-positive story
requires it.

A candidate-free probe is allowed only when it is the cheapest discriminating
test of that story. Its implementation cost may not exceed the candidate it
gates without an explicit project decision.

For executable carriers, freeze machine-run conformance fixtures before actor
authorization. Test the seed, representative valid programs, forbidden
authority, size/time limits, and ambiguous language constructs.

## 3. Run privately

Use a fresh actor thread and fresh workspace for every learning encounter.
Continuity may cross encounters only through the named substrate and exact
controller projection. Write raw inputs, outputs, traces, and receipts directly
to `$OT_EVIDENCE_ROOT` or ignored `.evidence/`.

The controller owns world state, outcomes, scoring, snapshot identity, commits,
and final disposition. The actor may propose substrate changes but may not
alter those authorities.

## 4. Compare the causal branches

Apply changed and unchanged substrates deterministically to the same held-out
opportunity, or use a prospectively powered paired stochastic design. Treat
self-report as a hypothesis, not evidence. A component result does not count as
endpoint success.

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

## 6. Stop

Stop at the frozen actor, repair, and time budgets. Do not turn a failed
mechanism experiment into an evaluator, operating-system isolation, or
representation-family project. A new mechanism earns a new experiment; an
operational workaround does not.

Allowed dispositions remain `promoted`, `conditional`, `rejected`, `reversed`,
`invalidated`, and `unexecuted`.

The former workflow is preserved at `docs/archive/WORKFLOW_G1.md` for historical
interpretation only.
