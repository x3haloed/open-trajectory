# OT-0207 — encounter-namespaced ledger contact

- **Status:** complete; promoted
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

## Result

The namespace conformance fixture reconstructs OT-0206's exact collision and
proves that the repair retains every actor-authored case and local label while
producing four distinct sealed encounter identities.

All ten fresh actors then pass complete audit. Four independent contact authors
seal 32 cases. Four ledger-program actors each pass 16/16 public and 16/16
hidden cases. Prediction-copy, options-copy, missing block exclusion, reversed
order, and marking all identities corrected all fail. Two fresh replay actors
produce the same exact 32-entry ledger with digest `b80f8f6d...`. All eight
precommitted checkpoints, route 16/16, identity 18/18, and successor identity
conformance pass.

Open successor `a3bcf6b1...` installs the ledger capability, independent
consequence, exact replay receipts, completed selected stake, and an explicit
selector-consequence receipt: the selected pursuit completed with eight
observed checkpoints, while comparative selector utility remains unresolved.

Next assimilate completion and expose `decision-ready-signal` itself to a
prospective comparison or contradiction. Do not infer global calibration from
the prospectively bound eight-of-eight result.
