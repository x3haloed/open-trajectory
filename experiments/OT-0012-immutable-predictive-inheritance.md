# OT-0012 — Immutable predictive-inheritance reproduction

- **Status:** planned
- **Evidence class:** private-reproducible if all gates pass
- **Target:** OT-1
- **Frozen implementation commit:** pending
- **Frozen run lock:** `spec/ot-0012-run-lock.json` (pending)

## Hypothesis

After one independently scored contact batch per hidden regime, the existing
discrepancy-gated version-space ledger will reduce structurally held-out binary
rule prediction error relative to no persistence, bounded verbatim events, and
bounded nearest-event retrieval under the same active-inheritance ceiling. The
advantage should survive a hidden rule shift and disappear under projection
ablation when the actor is a content-addressed local base model.

## Causal mechanism

The candidate and controls are unchanged from OT-0003. The controller owns
outcomes and substrate updates. A compact projection is the only cross-encounter
payload; every actor uses a fresh ephemeral thread, workspace, and a directly
receipted empty tool inventory inside an isolated unauthenticated Codex home.

The actor model is the 12,109,565,632-byte GPT-OSS 20B MXFP4 GGUF artifact with
SHA-256 `65d06d31a3977d553cb3af137b5c26b5f1e9297a6aaa29ae7caa98788cde53ab`.
The run lock will also bind the pinned Codex executable, LM Studio application
and CLI identities, live loaded-model configuration, selected llama.cpp runtime
tree, Harmony adapter tree, and tracked model catalog. Directory identities are
the SHA-256 of canonical sorted rows containing each relative file name, byte
length, and file SHA-256; the identity contains the total file count and bytes.

## Cheapest decisive falsifier

Reject before actor execution if any frozen model, runtime, server, catalog,
prompt, code, task, or evaluator identity differs. Reject the behavioral claim
if the candidate misses an absolute threshold, fails to beat any equal-budget
control by four held-out errors, misses the post-shift threshold, uses a tool,
fails exact JSON parsing, exceeds a resource ceiling, or loses fewer than three
predictions under projection ablation.

## Candidate, controls, and task order

- Candidate: discrepancy-gated version-space ledger.
- Control A: no persistent state.
- Control B: most-recent verbatim outcome events truncated to 96 bytes.
- Control C: nearest prior outcome events truncated to 96 bytes.
- Control D: trained candidate state with its projection removed.

Each learning condition receives identical controller-owned outcome history,
a 96-byte projection ceiling, and a 256-operation substrate-transition ceiling.
The frozen order is contact, two structural holdouts, shifted contact, two
shifted structural holdouts, then two candidate-projection ablations.

## Transport boundary

LM Studio 0.4.9 exposes GPT-OSS final outputs either as direct JSON
or with one of two observed Harmony prefixes differing only in `json` case.
The evaluator strips only those exact prefixes. Markdown, prose, alternate
framing, extra keys, wrong lengths, or non-binary values remain parse failures.

## Privacy and storage review

Model weights and raw events remain outside Git under logical local/evidence
roots. A fresh salted task manifest binds two new distinct hidden rules before
execution; only its digest enters the tracked run lock. Tracked files contain
no machine-local paths, host identity, raw output, dataset, or checkpoint.

## Prospective predictions

- Each contact batch should leave exactly one candidate rule; the hidden shift
  should advance the candidate regime exactly once.
- Candidate held-out error should be at most 2/16 in each worker and shifted
  held-out error at most 1/8.
- Every baseline should make at least four more held-out errors than the
  candidate.
- Candidate projection ablation should cause at least 3/8 errors.
- All 52 actor outputs should parse, use distinct thread/workspace identities,
  expose empty tool inventories, and make zero tool calls.

## Results

Pending.
