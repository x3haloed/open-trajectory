# OT-0267 — standing world feed

- **Status:** frozen
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
