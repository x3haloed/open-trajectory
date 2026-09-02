# OT-0294 — Shared live isolation authority

- **Status:** preflight passed; live output sealed pending freeze commit
- **Evidence class:** exploratory-only
- **Parent:** OT-0293 live isolation-authority rejection
- **Invocation:** unchanged two content-free openings from the OT-0290 parent
- **Fresh actors:** one target selector, no retry

## Hypothesis

OT-0293 rejected because prospective and live isolation checks had separate
authorities. Installing the already-conformed content-based predicate at the
shared helper used by both paths should preserve the hidden-information boundary
and allow the otherwise-valid scanner wake, selection, 2/6 consequence, and
correction route to enter the lineage.

## Frozen correction

The shared three-argument `seed_excludes_sealed` helper now delegates to
OT-0292's content-based current-package predicate. The prospective selection
fixture is restored to its original implementation so it calls that same
helper; the live gate already calls it. Offered-world driver precedence remains
unchanged. No actor, world, evaluator, or subject compilation logic changes.

## Prospective gates and limits

Preserve the exact OT-0293 rejected invocation and require that it contains a
G10-clean actor, 2/6 world consequence, correction route, and failed isolation
gate. The helper installed in the fixture module and the helper called by live
evaluation must be the same function object. A clean generated seed must pass
through that helper, while all four OT-0292 injected hidden-content controls
remain rejected. The actual driver sequence and all inherited gates remain
green.

Any separate branch-local override, changed precedence, leaked hidden content,
actor during wake, actor/G10 failure, retry, non-2/6 consequence, or lost
invalidity lineage rejects. Passing establishes one bounded handoff into
correction, not correction success or a complete recurrence. Live output stays
sealed until design and passing preflight are pushed.

## Preflight result

The fixture passes. Prospective selection and live acceptance resolve to the
same shared content-based helper. A clean seed passes that exact helper; all
four inherited hidden-content controls fail it. OT-0293's clean actor, 2/6
consequence, correction route, and isolation-only rejection remain exact, as do
the corrected live driver, three selection branches, route 16/16, and identity
18/18. Preflight receipt `f0adbb1b...`.
