# OT-0292 — Recovered-package content isolation

- **Status:** preflight passed; live output sealed pending freeze commit
- **Evidence class:** exploratory-only
- **Parent:** OT-0291 zero-actor isolation rejection
- **Invocation:** unchanged two content-free openings
- **Fresh actors:** one target selector, no retry

## Hypothesis

OT-0291 rejected because its inherited isolation proxy confused legitimate
package identity with hidden package content. If public-seed isolation directly
forbids current sealed reference sources, undisclosed cases, and the full
sealed-case collection while permitting the recovery receipt's content-free
package digest, all three prospective branches should pass without weakening
the information boundary. The unchanged live wake and selection can then test
whether recovered provision causes pursuit to resume.

## Frozen correction

Replace only OT-0291's `seed_excludes_sealed` result. The corrected predicate
reads the generated actor seed and rejects any current sealed reference source,
any case beyond the four disclosed cases for a target, the complete sealed-case
collection, or a filename containing `sealed`. It does not reject the full
package digest by itself because that digest is deliberately retained in the
provider recovery receipt and grants no package content.

Inject one example of each forbidden content class into an otherwise-valid seed
and require rejection. Preserve OT-0291's exact failed receipt and demonstrate
that the legitimate full-package digest is present in the clean seed.

## Prospective gates and limits

All unchanged OT-0291 gates must pass, including actor-free scanner wake, three
target branches at exact 2/6, correction routing, scar and recovery continuity,
route 16/16, and identity 18/18. Each injected leak must fail the corrected
predicate. Any other mechanism change, digest removal from the subject, actor
during wake, retry, G10 failure, or sealed-content exposure rejects.

Passing is one bounded recovered-world wake and selected consequence. It does
not establish correction or complete another world cycle. Live output remains
sealed until design and passing preflight are pushed.

## Preflight result

The corrected fixture passes. The clean seed retains the full-package digest
through the recovery receipt while excluding the current sealed sources, hidden
cases, full case collection, and sealed filenames. Injecting each of those four
content classes makes the predicate fail. All three unchanged choice branches
reach unresolved 2/6 consequence and correction routing with invalidity lineage
exact, route 16/16, and identity 18/18. Preflight receipt `1de8c346...`.
