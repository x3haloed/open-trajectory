# Experiment ledger

Experiment records are append-only public interpretations and receipt indexes.
Raw evidence does not belong here.

Copy `TEMPLATE.md` to `OT-NNNN-short-name.md` before running a serious
experiment. Assign an ID once and never reuse it.

Current unexecuted protocol drafts:

- [`OT-0015-crossed-scar-selector.md`](OT-0015-crossed-scar-selector.md) —
  crosses subject-relative scar carriers with selector identity while keeping
  scar and selector verdicts separate.
- [`OT-0016-counterfactual-challenger-credit.md`](OT-0016-counterfactual-challenger-credit.md)
  — valid E3 rejection of counterfactual challenger credit; the run also
  exposed that E3's aggregate task sampler did not observe exact causal-chain
  feasibility.
- [`OT-0017-exact-causal-opportunity.md`](OT-0017-exact-causal-opportunity.md)
  — controller-only E4 checkpoint; direct construction was feasible, but the
  fresh promotion anchor rejected E4 because the canary ablation was not
  path-complete.
- [`OT-0018-path-complete-e4-calibration.md`](OT-0018-path-complete-e4-calibration.md)
  — frozen controller-only successor checkpoint with path-complete canary
  removal and paired rescue.
