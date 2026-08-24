# OT-0024 — Expanded-decision portfolio feasibility

- **Status:** failed at frozen decision-carrier gate; portfolio untested
- **Evidence class:** exploratory-only
- **Target authority:** none; development feasibility only
- **Predecessor:** OT-0023 decision-carrier failure

## Hypothesis and sole carrier change

OT-0023 never evaluated its portfolio because the first natural three-way
decision expression used 65 AST nodes against the inherited binary carrier's
64-node limit. OT-0024 tests whether the portfolio topology is feasible when
that one carrier has a prospectively frozen 128-node limit. Its byte limit
remains 512. Portfolio size, actor authorship, prospective timing, consequence
ledger, controller authority, credit neutralization, +4 gate, deployment, and
resources are unchanged.

The fresh public task moves the useful relation to the fourth feature. A useful
selector must retain examples from both sequence halves; first-only and last-
only hypotheses each fail. This task is tracked development evidence and is not
an E4 candidate.

## Cheapest falsifier, controls, and gate

Before hosted output, a known bounded portfolio must replay with three distinct
programs, at least two selection sets, a useful cross-half alternative, a true-
credit commit, a neutralized current choice, and exact identity. A synthetic
decision larger than 64 but no larger than 128 nodes must validate only under
the new carrier. The prompt must exclude the sealed split.

Then exactly two fresh Luna encounters run. Each must author three distinct
alternatives and one prospective choice rule. The chosen alternative must change
selection and gain at least four errors; full credit neutralization must choose
current. Freshness, zero tools, exact model, inventory, Response identity, ETag,
collector, replay, identity, resource, test, audit, privacy, and evidence gates
must all pass.

## Claim limit and freeze boundary

A pass establishes public representation feasibility only. It cannot promote
OT-1, renew E4, or authorize a private candidate. Actor output is forbidden
until a clean implementation commit and separate run-lock commit bind every
authority. OT-0024 is not adjusted after output.

The clean protocol and implementation commit is
`447b0d5b097b9f844f03d7d5430d67eae3cffdbc`.
`spec/ot-0024-run-lock.json` binds it and every runtime authority before the
first hosted actor output.

## Results and decision

OT-0024 failed during the first actor encounter, before portfolio comparison or
commit. The actor returned the exact output schema and three textually distinct
selector alternatives. All three passed the depth-8 carrier and deterministic
execution, and all three produced distinct selection sets on the sealed split.

The structured-output schema admitted a decision string of exactly 512
characters, but two non-ASCII characters made its UTF-8 carrier size 516 bytes
against the frozen 512-byte limit. Independent parsing also found invalid Python
expression syntax. The controller rejected it, preserved the failure, and did
not release actor 2. The 128-node expansion therefore did not yield a scored
portfolio.

Final disposition: `failed`. OT-0024 is not rescored, repaired, or retried.
Together, OT-0023 and OT-0024 close free-form Python text as the prospective
multiway decision carrier: one natural rule exceeded the node cap, and the next
hit the byte boundary with invalid syntax. Raising either bound again would be
post-result gate chasing. The remaining credible carrier path is an exact
bounded structured decision representation whose semantics are directly
interpreted, not inferred or compiled from prose; it must preserve actor
authorship, allow neutralization to change the choice, and receive a new task,
actors, protocol, and run lock.

## Evidence manifest

`evidence/manifests/OT-0024/ot-0024-portfolio-pilot-001.json`
