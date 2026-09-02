# OT-0297 — Consequence-earned isolation

- **Status:** preflight passed; live output sealed pending freeze commit
- **Evidence class:** exploratory-only
- **Parent:** OT-0296 zero-actor developmental-isolation rejection
- **Invocation:** unchanged two content-free openings from exact OT-0295 parent
- **Fresh actors:** one target selector, no retry

## Hypothesis

Isolation can track developmental position. A surface whose ledger entry is
verified by both correction and independent-success receipts may contribute its
learned source to future actor seeds; unresolved surfaces must remain sealed.
Under that rule, post-correction refresh and renewed selection should become
live without leaking either remaining surface.

## Frozen mechanism and gates

Replace only the shared isolation predicate. It reads the exact subject already
present in the generated seed. A package target is earned only when its ledger
entry is `verified-local` and has nonempty correction and independent-success
receipt lists. For every unearned target, forbid its reference source and cases
beyond the four public rows. Continue forbidding the full sealed-case collection
and any filename containing `sealed`.

Preflight must preserve OT-0296's rejection, prove exactly one earned and two
unearned targets, prove the earned reference source is present and permitted,
and reject reference source plus hidden case for each unearned target, the full
case collection, a sealed filename, and a status-only counterfeit. Both target
branches, the live driver, route 16/16, and identity 18/18 remain unchanged.

Any receipt-free status authority, unresolved leak, actor during refresh,
preselected target, actor/G10 failure, retry, non-2/6 consequence, or lost
lineage rejects. Passing is renewed selection after one learned surface, not a
complete cycle. Live output stays sealed until design and preflight are pushed.

## Preflight result

The scored fixture passes. Exactly one target is earned by verified status plus
both receipt classes; its learned reference source is present and permitted.
Both unresolved targets remain protected: their reference sources and hidden
cases, the full case collection, and a sealed filename all fail. A status-only
counterfeit also fails. Both unchanged renewed-selection branches reach 2/6
consequence and correction with route 16/16 and identity 18/18. Preflight
receipt `772b116d...`.
