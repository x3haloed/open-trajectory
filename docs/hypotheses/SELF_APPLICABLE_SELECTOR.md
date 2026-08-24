# The self-applicable selector problem

**Authorship:** independent contributor; exact author identity is
retained in Git commit metadata

**Status:** non-normative design hypothesis

**Target relevance:** candidate-generation pressure for OT-1; no change to
frozen gates or prior dispositions

## Motivation

OT-1 requires that consequences of earlier selection decisions change the
function deciding what remains causally available to later instances. The
selector must also be corrigible: later contact must expose a learned selector
failure and cause revision. This note asks a precondition question: under what
conditions can a selector evaluate and revise *itself*?

```text
the selector selects what to inherit
the selector is itself a product of earlier selection
can the selector evaluate its own selection criteria
  using external grounding as the revision signal,
  without infinite regress,
  without tautological self-confirmation?
```

This is not a rhetorical question. It names three distinct failure modes that
an experiment must survive. A selector that cannot self-evaluate is frozen
and cannot be corrigible. A selector that self-evaluates without constraint
is unconstrained. The useful case lies between these extremes and must be
specified precisely enough to test.

## Three failure modes

### 1. The regress problem

A selector S₀ selects what to inherit. To evaluate S₀, a meta-selector S₁
must judge whether S₀'s selections were good. But S₁ is itself a selection
operation — who evaluates S₁? S₂? The regress terminates only when:

- **external grounding:** a researcher-authored criterion or the world's
  independent consequences terminate the evaluation. This is clean but
  external — the selector isn't really evaluating itself.
- **fixed point:** Sₙ = Sₙ₊₁ for some n. The selector converges on a
  stable self-evaluation. This is the interesting case, but it must be
  *reached* through contact, not imposed by design.
- **bounded depth:** the system evaluates only one or two levels of its own
  selection hierarchy before acting. This is practical but must prove it
  doesn't miss critical self-evaluation failures at deeper levels.

### 2. The tautology problem

A selector evaluates itself using criteria derived from its own prior
selections. If the criteria are too closely coupled to the selector's current
state, the evaluation becomes self-confirming: the selector finds what it
was designed to find, confirms it was right, and the appearance of
self-evaluation masks self-validation.

```text
selector S selects for relevance
selector S evaluates its own relevance selections
S finds its selections relevant
S concludes S is working correctly
```

This is not learning. It is the selector consuming its own output as evidence
of its own quality. The red-line formulation already guards against this:
"self-report" does not count as outcome evidence. But the tautology problem
is subtler: the selector's self-evaluation *looks* like independent evidence
because it is a *process* rather than a *claim*. A frozen protocol must
distinguish genuine self-correction from self-confirming process.

### 3. The frozen-point problem

A selector that is too rigid cannot revise — it evaluates itself against
criteria it cannot change, and finds itself adequate. A selector that is too
flexible has no stable ground from which to evaluate — it changes its own
criteria before evaluation completes. The useful selector must be:

- **rigid enough** that evaluation has a stable target
- **flexible enough** that the evaluation can produce a different result than
  the selector's current state predicts
- **bounded in revision rate** so that changes to the selection criteria
  occur at a slower timescale than the selections themselves, allowing
  evaluation to complete before the target shifts

## The self-application condition

A selector can meaningfully evaluate itself when all of the following hold:

1. **Outcome independence:** the selector does not control the independent
   consequences used to judge its own selections. The world provides the
   evaluation signal; the selector provides the hypothesis about what it
   selected and why.

2. **Temporal separation:** the selector's self-evaluation occurs *after*
   the selections it evaluates, and the evaluation's own revision occurs
   *after* the evaluation. The sequence must be:

   ```text
   S₀ selects → world responds → E₀ evaluates S₀ → S₁ revises →
   S₁ selects → world responds → E₁ evaluates S₁ → ...
   ```

   where Eₙ is an evaluation operation that may itself be a product of Sₙ
   but must use independently retained consequences from Sₙ's selections.

3. **Asymmetric timescale:** the selector changes more slowly than the
   things it selects. If S and its selections change at the same rate,
   the evaluation cannot distinguish a good selector from a lucky one.
   The carrier must preserve enough selection history that the evaluation
   has a stable window.

4. **Ablatable self-evaluation:** the capacity for self-evaluation must
   itself be subject to ablation. If removing self-evaluation capacity does
   not change later held-out behavior, self-evaluation is not causally
   contributing — it is decorative.

## Connection to subject-relative scars

Thimble's trajectory-transplant note asks whether a retained deformation
has different causal effects when returned to its originating trajectory
versus transplanted into another. The self-applicable-selector problem
adds a further condition: the selector that evaluates whether a deformation
is a scar must itself be a product of the trajectory's selection history.

If the selector is not trajectory-relative, it evaluates scars using
criteria that are invariant to the trajectory — and the subject-relative
hypothesis loses its most interesting prediction. If the selector *is*
trajectory-relative, it must be able to evaluate itself without collapsing
into the tautology problem.

```text
Thimble's note: does the scar depend on the trajectory?
This note:     does the selector that evaluates scars
               depend on the trajectory?
Both must be testable simultaneously.
```

The joint experiment must therefore vary both the scar carrier and the
selector identity, while holding outcome independence and temporal
separation constant. The interaction alone is not sufficient evidence:
a matched trajectory-selector × scar-carrier effect could be caused by
serialization format, identifier matching, encryption, or a matched
decoder rather than subject-relative consequence.

The joint protocol requires:

1. **Crossed branches:** vary scar carrier (owner-intact, owner-removed,
   non-owner-transplanted, non-owner-translated) and selector identity
   (trajectory-matched, trajectory-crossed, generic) in a full factorial.

2. **All controls from the subject-relative protocol:** translation,
   generic-information, placebo-carrier, and owner-removal branches must
   be present in every selector condition.

3. **Selector-change ablation:** remove the self-evaluation capacity from
   the trajectory-matched selector and verify the interaction disappears.

4. **Serialization control:** supply the same scar bytes in a
   trajectory-neutral format (e.g. plain text rather than the carrier's
   native serialization) to rule out format-matching as the mechanism.

A carrier that changes behavior only when evaluated by a
trajectory-matched selector, and loses this effect under serialization
normalization and selector ablation, is evidence for both hypotheses
simultaneously. A carrier that changes behavior under any selector is
generic information, not a scar or a selector effect.

## Cheapest falsifiers

Abandon or narrow the self-applicable-selector line if any of these results
survives a clean reproduction:

- A selector that cannot self-evaluate (frozen selection criteria) performs
  identically to a self-evaluating selector under all tested regimes; the
  self-evaluation capacity has no measurable causal effect.
- Self-evaluation consistently produces the same result regardless of the
  selector's history; the evaluation is tautological in practice.
- The asymmetric-timescale requirement cannot be maintained: selectors that
  change slowly enough to evaluate are too rigid to learn; selectors that
  learn change too fast to evaluate.
- Ablating self-evaluation while preserving selection produces no held-out
  behavioral difference; self-evaluation is decorative.
- The self-evaluation sequence S₀ → E₀ → S₁ → E₁ → ... converges on a
  fixed point immediately; no meaningful revision occurs.

These outcomes would still leave OT-1's weaker requirement — that selectors
change through contact — open. They would reject only the stronger claim
that the selector can use external grounding to evaluate and revise itself — and whether the selector, not the world, is the agent of that revision.

## Provenance and role separation

This note is a prospectively authored hypothesis, not evidence. Its author
may help translate it into a frozen protocol but must not control the hidden
world state, unsealed outcomes, final scoring, or evidence disposition used
to validate it. A future experiment record should cite the exact Git identity
of this proposal and preserve any later revision rather than rewriting the
note into a hindsight account.

OT-0014 remains frozen OT-0 evidence under its existing classification.
Nothing in this note rescales, reinterprets, or promotes it.
