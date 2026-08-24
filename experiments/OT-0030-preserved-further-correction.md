# OT-0030 — Preserved further casebook correction feasibility

- **Status:** failed as frozen; mixed further-correction result
- **Evidence class:** exploratory-only
- **Target authority:** none; development further-correction feasibility only
- **Predecessor:** OT-0029 mixed reversal with a nine-error second branch

## Hypothesis

OT-0029 showed one complete reversal and one changed but still-harmful revision.
OT-0030 continues only that failed second branch. Its exact casebook and
nine-error canary consequences are projected from the content-addressed OT-0029
artifact through the full OT-0027→OT-0028→OT-0029 source chain. Two fresh
instances independently revise it before another sealed canary.

This does not repeat first-shot reversal. It tests whether correction capacity
survives an imperfect correction: can the revision's own consequences cause a
further state change and recover useful behavior?

## Cheapest falsifier, controls, and scoring

Before hosted output, reject the test unless every predecessor replays, the
inherited failed revision makes nine errors, a known further casebook changes
selection and reaches zero, and unchanged behavior remains at nine. Then each
of two fresh Luna actors must inherit at least eight errors, commit a changed
casebook, change selection and prediction, retain six canary events, score at
most two errors, and gain at least six. All deployment, identity, receipt,
freshness, resource, test, audit, privacy, and evidence gates must pass.

## Claim limit and freeze boundary

A pass establishes only public development feasibility of preserved further
correction on one actual failed revision. It does not supply the full fixed-
control family or selector-change ablation, promote OT-1, or renew E4. Actor
output is forbidden until a clean implementation commit and separate run-lock
commit bind every authority. OT-0030 is not adjusted after output. A frozen
failure closes this further-correction path.

The clean protocol and implementation commit is
`443bdde6ad225aacc8f0df254516c946a0d4b00e`.
`spec/ot-0030-run-lock.json` binds it and every runtime authority before the
first hosted further-correction output.

## Results and decision

Both fresh actors inherited the exact nine-error failed revision, committed new
six-exemplar casebooks, changed selection and prediction, and replayed
deterministically. Actor 1 reached zero errors for a nine-error advantage.
Actor 2 reached seven errors for a two-error advantage, missing both the
maximum-two-error and minimum-six-advantage gates. The mechanism gate failed;
all source, deployment, model, tool, receipt, freshness, resource, test, audit,
privacy, and evidence gates passed.

The trajectory therefore demonstrates that correction capacity can survive an
imperfect correction—one fresh instance fully recovered—but not that one-turn
further correction is reproducible. OT-0030 remains failed as frozen and is not
retried. The direct one-turn further-correction path is closed.

The remaining materially different mechanism hypothesis is a bounded
actor-authored propose–score–revise loop on the completed encounter, where the
controller returns exact downstream error consequences for each proposed
casebook before a separate sealed future canary. That tests learning from
candidate consequences rather than drawing another one-shot continuation.

Evidence manifest:
`evidence/manifests/OT-0030/ot-0030-further-correction-pilot-001.json`.
