# OT-0261 — correction before projection refresh

- **Status:** promoted
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0260 subject `c319bade...`
- **Fresh actors:** zero

## Prediction error

**Expected:** projection freshness would prevent a stale selector artifact from
reaching another actor. **Observed:** the OT-0260 guard has unconditional first
precedence; stale `correct`, `contact`, `widen`, and unknown phases all route to
projection refresh instead of their inherited operations. **Uncertain:** whether
phase-aware precedence can preserve corrigibility and non-selection phases while
still forcing refresh before the next selection. **Evidence:** OT-0260
`operation_for` applied to held-out stale phase variants.

## Frozen hypothesis and gates

Correction/contact phase authority must outrank selector maintenance. Projection
freshness may intercept only an otherwise selection-capable `assimilate` state;
all other phases retain the promoted content-free operation selector.

Promotion requires held-out fresh/stale cases across `assimilate`, `correct`,
`contact`, and unknown phases; exact correction precedence improvement with no
regression; zero actors; an installed non-authoritative phase-aware policy;
unchanged operational, projection, wait/wake, and provider state; and the live
parent still routing to `expanded-select`.

## Result

The unconditional incumbent scores 3/7, incorrectly refreshing four stale
non-assimilation phases. The phase-aware challenger scores 7/7: correction,
contact, widen, and unknown routes retain inherited behavior, while stale
assimilation still refreshes before selection.

Zero-actor successor `088a3628...` changes only the non-authoritative freshness
policy and remains open with `expanded-select` next. Live sequence exercise
remains separate.
