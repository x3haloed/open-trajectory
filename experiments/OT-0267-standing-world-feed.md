# OT-0267 — standing world feed

- **Status:** promoted
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0266 subject `d3ef7b33...`
- **Fresh actors:** zero
- **Claim:** provider-interface operational transition and matched visibility test

## Hypothesis and cheapest falsifier

A content-addressed, schema-bounded feed scanner can replace per-world provider
code while preserving the exact subject's current developmental position. Hold
the subject and one new package fixed: the installed catalog-specific provider
must remain empty while the standing scanner reports that package as unseen.
Failure to distinguish them, any target/scoring authority, or any change to the
live correction state falsifies the transition.

## Frozen interface and controls

A package contains only a bounded `world_id` and two to eight visible Python
sources at relative two-component `.py` paths. Every source must parse and expose
a non-private top-level callable. The scanner canonicalizes package and catalog
identity, filters worlds already consumed or actively offered, rejects malformed
or duplicate-id snapshots as a whole, and chooses the lexically first unseen
world. It has no selection, scoring, admission, outcome, or actor authority.

Positive fixtures vary world ids, paths, functions, source order, and catalog
order. Negative fixtures cover traversal, absolute/deep/non-Python paths,
malformed/private-only/oversized source, empty packages, invalid ids, unknown
fields, and conflicting duplicate ids. Seen and active-offer controls must not
reoffer a world. The exact successor must preserve all operational, provider,
wait/wake, epoch, ledger, projection, and pursuit state and still route the
fourth-epoch contradiction to correction. This record does not claim a live
future wake or world-package generation.

## Result

All controls pass with zero actors. The old catalog-specific provider reports
empty on the held-out package while the standing scanner reports it available.
Two structurally different positive packages, catalog/source order invariance,
seen and active-offer filtering, thirteen malformed-package cases, and duplicate
ids behave as frozen. All five external authorities remain false.

Exact open successor `f02cf7cd...` retains the scanner source and logical
`$WORLD_FEED` interface while preserving every operational field and the
fourth-epoch correction-before-refresh route. Route 16/16, identity 18/18, and
subject conformance pass. Aggregate receipt `d75632a3...` records the bounded
transition.

This makes feed discovery independent of per-world harness code but does not
show a live future wake. The held-out fixture was frozen with the scanner; the
next test requires a fresh independent world package authored only after this
interface was committed, then eventual discovery through these exact bytes.
