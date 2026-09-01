# OT-0202 — canonical stake compilation

- **Status:** design frozen; not run
- **Evidence class:** exploratory-only
- **Target:** exact new-ID repair of OT-0201's incompatible successor compiler
- **Parent:** exact OT-0199 open successor `08c877ff...`
- **Renewal:** exact OT-0200 actor proposal `ee6e0a23...`
- **Actor budget:** six active contact authors and six matched renewal-erased
  controls
- **Observer budget:** one complete driver invocation; 55 minutes

OT-0201's behavior is not reused for promotion. Its exact renewal proposal,
suite-level evaluator, contact interface, interleaving, controls, floors, and
gates remain unchanged.

The sole compiler repair maps actor field `pursuit_id` to canonical
`active_developmental_stake.stake_id`. The compiled stake must contain exactly
`stake_id`, `property`, `target_set`, `question`, `rationale`,
`success_condition`, and `surrender_condition`; `pursuit_id` must be absent.

Before actor authorization, preflight must reconstruct the candidate, pass
runtime identity conformance, and feed it through the production OT-0184
selector-repair seed constructor, which directly consumes
`active_developmental_stake.stake_id`. The emitted active-stake artifact must
equal the candidate stake exactly.

Promotion again requires twelve clean fresh actors, active 6/6, controls at
most 2/6, advantage at least four, exact renewal, canonical candidate, route
16/16, identity 18/18, and an open successor. On passage install the renewal,
active-01 contact and consequence, then open generalized mechanism invention.
