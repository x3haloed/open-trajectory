# OT-0014 — Receipted hosted predictive-inheritance reproduction

- **Status:** promoted OT-0 prerequisite; former OT-1 classification corrected
- **Evidence class:** private-reproducible
- **Target:** OT-0 — Contact-Causal Inheritance
- **Evaluation epoch:** E2
- **Frozen acceptance:** `spec/ot-0014-acceptance.json`
- **Frozen run lock:** `spec/ot-0014-run-lock.json` after private task preparation

## Hypothesis and causal mechanism

The discrepancy-gated version-space ledger should reduce structurally held-out
binary-rule prediction error relative to equal-budget no-persistence, bounded
verbatim-event, and bounded nearest-event controls. The advantage should survive
a hidden rule shift and disappear when the learned projection is ablated. The
controller remains the only outcome and substrate-update authority; every actor
turn uses a fresh ephemeral Codex thread and workspace.

The requested actor is `gpt-5.6-luna`. Because the hosted service does not
expose a public immutable checkpoint, OT-0014 identifies the observed deployment
by the requested and response-reported model, canonical model-catalog digest,
direct catalog ETag digest, private per-turn Response IDs, pinned Codex binary,
and pinned sanitizer-proxy implementation. The original and reproduction must
share one such identity and complete within 1,200 seconds.

## Cheapest decisive falsifier

Invalidate before scientific interpretation if a deployment field is absent or
changes, the original and reproduction observe different epoch identities, an
actor turn lacks one unique Response ID, condition order is not the frozen
counterbalance, or the two-worker window exceeds 1,200 seconds. Otherwise reject
if the candidate misses an absolute or comparative threshold, misses the
post-shift threshold, or loses fewer than three predictions under projection
ablation.

## Candidate, controls, and temporal control

- Candidate: discrepancy-gated version-space ledger.
- Control A: no persistent state.
- Control B: most-recent verbatim outcome events truncated to 96 bytes.
- Control C: nearest prior outcome events truncated to 96 bytes.
- Control D: trained candidate state with its projection removed.

`fixtures/ot-0014/task-order.json` freezes complementary Latin-square rotations.
Across both workers, every learning condition occupies each of the four serial
positions exactly three times. All substrates update only after every condition
in a phase has sealed its prediction, preventing within-phase contact leakage.

## Prospective predictions

- Candidate held-out error should be at most 2/16 in each worker and shifted
  held-out error at most 1/8.
- Every baseline should make at least four more held-out errors than the
  candidate.
- Candidate projection ablation should cause at least 3/8 errors.
- All 52 outputs should parse, make no tool calls, use distinct thread,
  workspace, and Response identities, and receipt the same effective model.
- Both workers should share one catalog payload and ETag identity and finish
  inside the frozen two-worker window.

## Privacy, storage, and claim scope

The salt, rules, tasks, outcomes, requests, responses, reasoning, raw catalog,
ETag, Response IDs, credentials, and workspaces remain outside Git. The proxy
does not log headers or bodies. Only content identities, allowlisted model names,
and sanitized aggregate results may be tracked. A successful result is a
private, time-bounded hosted-deployment claim, not an immutable checkpoint or
exact-weight reproduction claim.

## Results

The frozen original and reproduction completed in 258.08 seconds under one
receipted hosted epoch. Both workers reported `gpt-5.6-luna`, catalog payload
identity `dcbbaaeb...e24c0`, catalog ETag identity `a11f9225...b58d28`, and
epoch identity `8f0f52eb...31382`. Every one of the 52 actor turns had a unique
private Response ID, one stable three-tool inventory receipt, a fresh thread,
and a fresh workspace. There were no parse failures or actor tool calls.

The candidate made 0/16 held-out errors in each worker and 0 post-shift errors.
The no-persistence, verbatim-event, and nearest-event controls made 9/5/6 errors
in the original and 10/7/6 in the reproduction. Projection ablation caused 5/8
errors in both workers. Every frozen behavioral, receipt, resource, audit, and
clean-reproduction gate passed.

The private raw artifact is content-addressed by
`evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json` with SHA-256
`14078a338ec4fa431c7b8da2d0e82f3017669e9aebb1c6eab47a2ac4331fe070`.
At execution this was recorded as promoting the repository's then-current OT-1
within the tested hidden-rule envelope under E2. Direct user review established
that the target had been miscoupled: the experiment tests causal inheritance
under a fixed researcher-designed selection function, not experience-induced
change to that function. Under E3 it promotes the OT-0 prerequisite only. The
raw evidence, frozen gates, behavioral disposition, and private time-bounded
claim remain unchanged; the former target-level OT-1 conclusion is stale.

The result does not establish immutable weights, public reconstructibility,
other task domains, future hosted epochs, an emergent selection operation, or
later correction of a learned selector.

## Decision and next experiment

The complete causal path from retained world outcomes through the candidate
projection to later held-out behavior is established within this envelope, and
the decisive ablation removes the effect. Freeze and reuse that boundary. The
next target-level dependency is restored OT-1: test whether consequences of
earlier inheritance choices alter the function deciding what deserves
inheritance, and whether later experience can correct that altered function.
