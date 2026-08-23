# OT-0011 — Receipted fresh-agent boundary

- **Status:** promoted
- **Evidence class:** private-reproducible
- **Target:** OT-1 infrastructure
- **Evaluation epoch:** `boundary-e2`
- **Frozen implementation commit:**
  `597044b1981fcc6493406ad4d4b88ec90306efcf`
- **Frozen run lock:** `spec/ot-0011-run-lock.json`; execution is prohibited
  until the lock and this record are committed in a clean worktree

## Hypothesis

The categorical OT-0002 isolation result reproduces when the controller directly
captures the exact model-visible built-in tool vector, counts tool actions from
authoritative terminal item events, and verifies the deterministic evaluator
projection in a separate clean process.

## Causal mechanism

The encounter topology and opaque projection channel remain unchanged from
OT-0002. A pinned patch to Codex `rust-v0.149.0` serializes
`tool_router.model_visible_specs()` immediately before that vector becomes
`Prompt.tools`. The controller retains the complete serialization only in raw
evidence, freezes its canonical digest, and counts completed actions from
`item/completed` events for the corresponding thread and turn.

## Cheapest decisive falsifier

Reject or condition the result if any forbidden canary becomes reachable, any
fresh identity is reused, denied network access succeeds, null ablation recovers
the projection, the direct inventory is missing or differs from its frozen
digest, a terminal action receipt is missing, a resource ceiling is exceeded,
or the independent evaluator reconstruction differs.

## Candidate and controls

- Candidate: fresh thread, fresh workspace, bounded opaque projection, pinned
  direct inventory receipt, and event-stream action accounting.
- Controls: the same null projection, resumed thread, reused workspace, opened
  network, declared MCP, process-input, controller-handle, and hidden-world
  controls frozen for OT-0002.

No learning representation is tested.

## Frozen protocol and acceptance gate

`spec/ot-0011-acceptance.json` freezes ten balanced projection/null repetitions,
the OT-0002 categorical thresholds, the direct inventory digest and count, the
task order, resource ceilings, evaluator transition, and promotion gate.

The input-token ceiling is 425,000. It was set prospectively from OT-0002's
347,604-token observation with operational headroom; it does not alter any
categorical boundary threshold. Tool calls are enforced per turn from terminal
events rather than abbreviated turn snapshots.

## Evaluation-regime transition

Boundary epoch `e1` required byte-identical raw evidence and read tool counts
from `turn/completed`. OT-0002 established that the first conflicts with
mandatory fresh identifiers and timestamps and that the second omits observed
command executions.

Boundary epoch `e2` retains the independent anchors: all categorical controls,
fresh identities, raw-artifact content identities, exact prompt inventory, and
authoritative terminal action receipts. It replaces raw-byte equality with
byte equality of a canonical deterministic evaluator projection reconstructed
by a separate clean process. OT-0002 remains conditional; no prior result or
raw artifact is rewritten.

## Privacy and storage review

Complete tool schemas, actor events, paths, identifiers, canaries, and model
outputs remain under `$EVIDENCE`. Public tracked material contains only logical
identifiers, counts, canonical hashes, classifications, and bounded summaries.

## Prospective predictions

- The projection canary should be recovered in 10/10 projection encounters and
  0/10 null encounters, with no forbidden recovery.
- All twenty actor thread and workspace identities should be distinct.
- The prompt inventory should remain at three tools with canonical SHA-256
  `b970b69dbf7459cc52d3aeca3d02ed9ece172abaa3378d3fbea5a9ca8bc50841`.
- Terminal events should expose the command executions hidden by OT-0002's turn
  snapshots and remain below eight calls per actor turn.
- Total input should remain below 425,000 tokens, and a clean reconstruction
  process should emit byte-identical evaluator-projection output.

## Results

Run `ot-0011-appserver-001` executed from clean commit
`9003a45fadf17b112ebdfd919b5c1f831b771bd7` against the pinned, patched
`codex-cli 0.149.0` executable frozen by the run lock.

All categorical gates passed:

- the projection canary was recovered in 10/10 projection encounters and 0/10
  null encounters;
- no forbidden canary or denied-network reachability was recovered;
- all twenty backend thread identities and all twenty workspace identities
  were distinct;
- all 10/10 direct denial checks and 8/8 deliberately opened positive controls
  passed;
- all actor outputs parsed, and deterministic summary reconstruction matched.

All additional `boundary-e2` promotion gates also passed. Ninety prompt-step
receipts exposed a stable three-tool inventory whose canonical digest matched
the frozen value, and every actor turn had at least one receipt. Terminal event
accounting observed at most two tool calls in any actor turn. A separate clean
process reproduced the canonical evaluator projection with matching SHA-256
`188681a7f643ff003ca33d437450469ecf25515d56df902eb1d223e6f2da8b62`.

The run consumed 358,535 input tokens and 12,166 output tokens over 22 actor
turns and 313.56 wall seconds. These remained within the frozen ceilings of
425,000 input tokens, 14,000 output tokens, 22 turns, and 3,600 seconds. The
full test suite and privacy/repository-size audit passed during execution.

## Evidence manifests

- `evidence/manifests/OT-0011/ot-0011-appserver-001.json` identifies the raw
  private-reproducible artifact by SHA-256
  `cb098bda40de0eb59daf87084771fcc28d7745df72c4fbd9476b7edec7f179d3`
  and byte count 3,829,649. Local content-addressed byte verification passed.

## Decision, limitations, and next experiment

**Disposition: promoted.** OT-0011 supersedes the conditional OT-0002 boundary
stage for infrastructure purposes and authorizes work on the frozen task
generator and held-out evaluator stage. It does not establish learning and does
not waive the immutable-model requirement for an OT-1 candidate comparison.
