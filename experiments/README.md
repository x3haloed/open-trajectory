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
  — rejected controller-only successor; stage-5 removal was complete, but six
  exact oracles used earlier correction and a stage-4 canary.
- [`OT-0019-full-suffix-e4-calibration.md`](OT-0019-full-suffix-e4-calibration.md)
  — passed controller-only successor; full-suffix neutralization and rescue
  promoted E4 for one new candidate experiment.
- [`OT-0020-e4-counterfactual-challenger.md`](OT-0020-e4-counterfactual-challenger.md)
  — invalidated E4 live successor preserving OT-0016's actor-authored mechanism;
  one worker completed with a negative behavioral result and one timed out, so
  no retry or promotion is permitted.
- [`OT-0021-consequence-ledger-feasibility.md`](OT-0021-consequence-ledger-feasibility.md)
  — failed public non-candidate pilot whose two mechanism slices passed; a
  frozen raw-receipt multiplicity bug failed the aggregate gate, so the result
  is not rescored and has no OT-1 or E4 authority.
- [`OT-0022-consequence-ledger-reproduction.md`](OT-0022-consequence-ledger-reproduction.md)
  — failed fresh public reproduction: the corrected Response gate passed, but
  only one of two actors produced a useful challenger, closing the one-shot
  single-challenger representation as the next path.
- [`OT-0023-contrast-portfolio-feasibility.md`](OT-0023-contrast-portfolio-feasibility.md)
  — failed public non-candidate pilot: all three selectors validated, but the
  first 65-node portfolio decision exceeded the inherited 64-node carrier by
  one node, so the portfolio itself remained untested.
- [`OT-0024-expanded-portfolio-feasibility.md`](OT-0024-expanded-portfolio-feasibility.md)
  — failed fresh public portfolio pilot: three distinct selectors validated,
  but the first multiway decision was 516 UTF-8 bytes and invalid syntax,
  closing free-form decision text as the next carrier.
