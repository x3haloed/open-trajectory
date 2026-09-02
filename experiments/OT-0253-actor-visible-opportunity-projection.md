# OT-0253 — actor-visible opportunity projection

- **Status:** frozen
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0252 partial subject `7965191a...`
- **Fresh actors:** zero

## Frozen hypothesis

The active generic AST resolver already makes the correct routing decision, but
its result is not part of the compact actor-visible subject position. Binding a
derived opportunity projection into the subject can improve future move
selection without granting the projection target-choice, world, scoring,
admission, or mutation authority.

The projection reads only the active epoch's visible source and exact ledger,
extracts top-level public callables, subtracts ledgered symbols, sorts path/symbol
pairs, and fails closed on malformed source. Freeze ten cases covering no epoch,
private helpers, completed targets, two modules, async functions, latest-epoch
precedence, malformed source, source reordering, irrelevant ledger entries, and
total saturation. All must pass.

Promotion requires the projection on the exact parent to equal the already
promoted OT-0244 resolver, contain exactly one opportunity, name no hardcoded
target in this implementation, preserve every operational field and authority,
and leave the subject open at the same `expanded-select` operation. No actor or
world is invoked.

## Limits fixed before output

This experiment establishes a compact derived carrier, not improved actor
behavior. A separate fresh-actor comparison must test whether the carrier changes
selection from the exact position where OT-0252 produced a non-move.
