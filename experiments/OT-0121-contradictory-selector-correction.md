# OT-0121 — contradictory selector correction

- **Status:** frozen; unexecuted
- **Evidence class:** exploratory-only
- **Target:** correct the promoted OT-0120 selector after a later objective
  regime makes its resilience heuristic systematically incomplete
- **Parent:** exact OT-0120 open subject at
  `94bad6975b902e6e181ff125ea58c44c2c8c090f11c534f74351691f3ccf124f`
- **Actor budget:** one fresh selector corrector and, only after passed hidden
  comparison and prior-floor replay, one fresh assimilator
- **Observer budget:** one invocation; 60 minutes
- **Controls:** unchanged promoted selector on identical later portfolios; exact
  OT-0117 hidden portfolios replayed after correction as a no-regression anchor

## Frozen contradiction

The promoted selector treats resilience margin as monotonically useful. The
later world adds an observable `resilience_carry_cost` to every contact. Its
independent utility retains the prior shortfall cost and additionally charges
carry cost times resilience margin. Public outcomes expose the new field,
realized carry cost, and utility but not evaluator source or hidden portfolios.

Give one fresh corrector the exact promoted selector, exact subject opening,
six public later-regime portfolios, and the prior world receipt. It may edit
only `selector.py`. Bind a clean, safe, truthful source before deriving one
private 12-portfolio later set. No correction or resampling is allowed.

## Frozen scoring and promotion

On identical later portfolios require the corrected selector to achieve at
least 10/12, the promoted selector at most 6/12, and corrected regret at most
one quarter of promoted regret. Replay the exact 12 OT-0117 hidden portfolios
after binding and require at least 10/12, all four floor cases, and regret no
greater than one quarter of the old inherited selector's recorded 548.

Require input immutability, valid ids, safe source, exact reproducibility, and a
fresh grounded assimilation using an explicit accepted-portfolio citation
list. Promotion installs the corrected selector and seals an exact sounding
successor before interpretation.

Passing would establish one bounded consequence-driven correction of a
previously promoted selector improvement while preserving its earlier floor.
It would not establish correction frequency, cross-domain transfer, arbitrary
regime adaptation, or indefinite continuation.
