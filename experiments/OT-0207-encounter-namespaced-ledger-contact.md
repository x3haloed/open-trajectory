# OT-0207 — encounter-namespaced ledger contact

- **Status:** design frozen; not run
- **Evidence class:** exploratory-only
- **Target:** prospective repair of OT-0206's actor-local/global-identity
  collision
- **Parent:** exact OT-0205 open successor `3e06b644...`
- **Base driver:** hash-pinned OT-0206 implementation `ceba5d53...`
- **Actor budget:** unchanged four contact, four ledger-program, and two replay
  actors
- **Observer budget:** one complete driver invocation; 55 minutes

OT-0206 remains rejected. This experiment retains its exact hypothesis,
selected stake, selector, actor prompts, actor order, public/hidden split,
ledger language, five negative controls, eight checkpoints, inherited floors,
stopping rule, and all-of-gates promotion decision.

The sole behavioral repair is at world-bank sealing. After an actor's suite has
passed its complete local contract and audit, the observer records the actor's
`suite_id` as `local_suite_id` and assigns the compositional identity
`sealed-encounter-N`, where `N` is the already-frozen encounter index. The raw
actor workspace and output are unchanged. Ledger actors receive the normalized
sealed bank; encounter identity no longer depends on coordination among actors
that cannot observe one another.

Preflight must reproduce OT-0206's exact rejection, confirm all four prior
contact outputs were locally accepted, confirm a collision exists among their
local labels, and prove that deterministic encounter namespacing makes all four
identities distinct while retaining every local label and case unchanged.

The cheapest falsifier and promotion gate remain OT-0206's. A pass establishes
independent consequence and replay for the subject-selected ledger pursuit, not
global calibration or comparative utility of `decision-ready-signal`.
