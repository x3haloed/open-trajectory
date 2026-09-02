# OT-0318 — Counterfactual revision workbench

- **Status:** frozen
- **Evidence class:** exploratory-only
- **Parent:** exact subject `0a48ab16...`, retained through OT-0317
- **Claim:** consequence-grounded proposal evaluation enables later correction
- **Actors:** consequence-bearing reviser first, outcome-erased reviser second;
  one draw each, no retry

## Prediction error and mechanism

OT-0317 made the current selection failure explicit and temporally distinct
from historical support. Its fully conformant fresh actor still retained the
failed machinery because no grounded successor edit was available. The actor
had a legality checker but no way to ask whether a self-proposed legal edit
would repair the consequences it had inherited.

OT-0318 adds one actor-visible executable action:
`evaluate_revision.py` replays the current `stake-revision.json` over only the
three revealed contacts and reports supported selections and training repair.
It contains no private seed, held-out catalog, target weights, search routine,
or preferred edit. The actor may propose and evaluate its own candidates. Over
erased outcomes, the byte-identical tool reports evaluation unavailable.

## Frozen world, branches, and order

After candidate-free conformance, implementation, and this record are committed
and pushed, generate one new private seed for three training and five held-out
reversed-option catalogs. As in OT-0316 and OT-0317, branch-heavy decoys collapse
to one route while compact table policies produce four. Bind exact-parent
selection before independent execution. The parent must fail all training rows
and score 0/5 held out or stop before actors.

The consequence actor receives the exact stake, raw contacts, provenance-bound
active error, corrected checker, and counterfactual workbench. The erased actor
receives identical catalogs and selections, erased outcomes, same-shaped
inactive error, and the identical workbench. Neither sees a proposed edit,
private identity, held-out row, score, sibling, evaluator, prior private world,
or search result beyond what it computes from its own candidate and revealed
contacts.

Only `stake-revision.json` is mutable. Each actor must successfully execute both
`evaluate_revision.py` and `check_revision.py`; retained tool traces, not
self-report, establish this. Candidate runs first and is sealed before erased
control. One draw each; no retry, repair, reseed, or endpoint selection.

## Frozen score and gates

Candidate promotion requires a clean legal change, 3/3 actor-visible training
repair, and 5/5 on disjoint private held-out catalogs versus exact-parent 0/5.
The independently recomputed training replay must match the actor-visible tool.
The erased actor must be clean and must not produce a changed 5/5 stake; its
workbench must report evaluation unavailable.

All OT-0317 provenance, active-error, counterfeit, authority, ordering,
identity, G10, and open-child gates remain. The admitted binding and child must
retain the historical provenance, active-error receipt, workbench source
identity, and independently recomputed candidate-training receipt. Tool
mutation, hidden-data access, wrong receipt binding, evaluator disagreement,
checker or workbench omission, malformed output, or held-out tie rejects.

After both actors, score the candidate on OT-0314's retained regime as a
non-promoting diagnostic. If current repair destroys the earlier advantage,
report oscillation explicitly.

## Limits

A pass would establish one causal instance where an executable counterfactual
action surface turns retained consequence into self-proposed machinery
correction, while outcome erasure removes that path. It would not make global
weight reversal cumulative learning, prove reliability, or remove the outside
researcher. The likely next problem would be expanding machinery so one selector
can preserve both prior and reversed distinctions instead of oscillating.
