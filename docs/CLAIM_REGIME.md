# Claim regime G2 — causal validity without provenance collapse

## Why G1 was replaced

The prior regime collapsed three questions into one gate:

1. Did the candidate mechanism cause the observed downstream difference?
2. Can another run regenerate the actor-authored proposal?
3. Can the hosted actor be identified as one immutable model deployment?

OT-0079 exposed the cost. Its retained actor outputs, independent outcomes,
parent comparison, ablation, and deterministic replay supported a bounded
causal observation, but missing hosted receipts erased that evidence rather
than limiting model attribution. A separate prose/implementation ambiguity
then invalidated behavior even though the admitted container methods could not
change actor information, evaluator authority, scoring, or branch comparison.

G2 replaces that regime prospectively. It does not weaken hidden-information,
outcome-authority, control, ablation, or scoring requirements.

## Claim dimensions

| Dimension | Required evidence | Missing evidence limits |
|---|---|---|
| Causal validity | frozen outcome; retained actor input/output; independent outcome; matched parent/control; decisive ablation; deterministic downstream reconstruction | the mechanism claim itself |
| Generative reproducibility | repeated actor generation under a frozen sampling/deployment contract | reproduction and reliability claims |
| Actor provenance | immutable revision or complete hosted deployment-epoch receipt | model-specific attribution |

A result with complete causal validity but incomplete generation/provenance may
carry the claim scope `causal-observation`. It says that the retained composite
subject produced the observed mechanism once. It says nothing about how often it will recur,
whether another deployment will generate it, or whether a catalog model should
receive credit.

## Protocol-deviation materiality

After candidate output, a deviation is **material** and invalidates when it can
affect any of:

- actor-visible information or continuity;
- hidden task, holdout, future outcome, or evaluator access;
- world, outcome, score, commit, or acceptance authority;
- parent/control comparability or resource equality;
- the claimed causal operation or decisive ablation; or
- safety and privacy boundaries.

Uncertain materiality fails closed. An independently auditable deviation that
cannot affect any listed dimension is disclosed as nonconformance; it removes
the corresponding protocol-conformance claim but does not erase the causal
observation. This classification is a standing rule, not a candidate-specific
exception.

## Anchor cases

- Changing a heldout, threshold, denominator, or task order after output is
  material.
- Leaking a future receipt or resuming an actor thread across a reset is
  material.
- Allowing filesystem, network, subprocess, reflection, or evaluator access
  outside a frozen carrier is material.
- Missing an immutable hosted receipt is material to model attribution and
  generative reproduction, but not to a deterministic comparison over retained
  outputs.
- A representation mismatch that admits only local, deterministic operations
  already promised by the carrier and changes no information or authority is
  nonconforming but not causally material.

## OT-0079 reassessment

OT-0079's original G1 invalidation remains in its record. Under G2, its actor
inputs and outputs are retained, fresh workspaces were used, the admitted
methods operate only on local list/dict state, imports and external authority
remain rejected, controller outcomes are independent, the unchanged-parent
comparison and selector ablation pass, and two downstream evaluations are
byte-identical. The attribute/method mismatch is nonconforming but not causally
material.

The raw artifact remains `exploratory-only` in the storage taxonomy, while the
mechanism result is `conditional` with claim scope `causal-observation`:
positive bounded evidence for coupled composition and stopping, without OT-1
promotion, actor-generation
reproducibility, model attribution, frequency, or cross-domain scope.
