# OT-0344 — Held-out world-policy reuse

- **Status:** frozen; not yet executed
- **Evidence class:** exploratory-only
- **Operational parent:** exact OT-0343 child `2b0d835e...`
- **Fresh actors:** at most two: one selection/continuation actor and one
  selected-contact successor

## Hypothesis and cheapest falsifier

The exact subject asks to test its retained world-consequence policy on a fresh
catalog while preserving its global 40/40 floor. The hypothesis is that the
subject's two-stage architecture can reuse that actor-authored policy on new
world identities and order, select a world with more independently viable
non-regressive contacts than its unchanged descriptor stage, let a fresh actor
choose one such contact, and carry that choice to another fresh actor whose
correction passes independent hidden consequence.

The cheapest falsifier is any failure of exact policy reuse, selection of fewer
than the maximum admissible contacts, agreement with the descriptor-only
ablation, loss of any earned floor case, an actor choice outside the selected
world, hidden failure of the chosen correction, or failure to leave another
reachable opening after the second actor ends.

## Frozen world and information boundary

After this implementation is committed cleanly, generate one private 32-byte
seed. One deterministic derivation attempt assigns three opaque world ids,
opaque contact ids, and presentation order to three fixed structural roles.
The descriptor leader has two viable contacts, the middle world has three, and
the expansion leader has four. Descriptor features make the exact global stake
select the two-contact world by at least its retained minimum gap; the retained
policy's first metric makes it select the four-contact world. All counted
contacts preserve the inherited floor and have one executable public/hidden
boundary correction. The derivation function and role templates are public;
the seed, hidden cases, and role-to-id assignment remain outside Git.

The first actor receives the exact two-stage architecture and binding ids, the
fresh consequence receipts, a generic executable selector, and all public
contact summaries. It receives no seed, role names, hidden cases, control
result, expected id, evaluator, or admission result. The selector mechanically
applies the retained post-contact policy. The actor may choose any contact in
that selected world and changes only `next-contact.json`.

The second fresh actor receives only the bound selected contact, its public
cases, the faulty source, a public checker, and the remaining contact ids in
the same world. It changes only `source.py` and `next-opening.json`. Hidden
cases and final scoring remain observer-owned. Both actors have ordinary broad
tools in isolated workspaces under G12/G11 effect audit.

## Controls, score, and promotion

Seal the active selection and contact binding before controls. Then replay the
same catalog with only the post-contact policy erased; the unchanged
architecture must fall back to the exact descriptor stake and expose two
contacts. A direction-reversed policy must also fail the active selection.
An inadmissible high-count anchor must never win.

Operational promotion requires two clean fresh actors, exact parent and
binding ancestry, active selection of four viable contacts, actor-chosen
contact binding, public and hidden correction success, exact 40/40 floor
preservation, and an open successor carrying one of the three unused contacts.
The bounded causal claim additionally requires the policy-erased replay to
select the two-contact descriptor leader, leaving one opening after equivalent
consumption versus three for the active architecture. World identity, order,
and actor choice cannot be supplied by the observer.

This tests held-out reuse and downstream option breadth of the retained policy.
It does not recover OT-0339's failed priority-origin claim, estimate generation
frequency, or establish that viable-contact count is universally sufficient.

## Budgets and stopping

At most two fresh actors, no actor retries, no post-output protocol repair, one
private derivation attempt, and twenty observer minutes. Stop after the active
successor is sealed and deterministic controls are scored. Observer stopping
does not close an open subject.
