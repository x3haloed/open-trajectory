# OT-0013 — Capped direct predictive-inheritance reproduction

- **Status:** frozen; execution pending
- **Evidence class:** private-reproducible if all gates pass
- **Target:** OT-1
- **Frozen implementation commit:** `09ae5ebe03cf99159870b4f3fa6bbd70db9b791e`
- **Frozen run lock:** `spec/ot-0013-run-lock.json`

## Prediction error motivating the successor

OT-0012 verified its frozen identities and completed seven clean encounters,
but its uncapped Codex-to-LM-Studio actor spent more than 180 seconds reasoning
on encounter eight. The incomplete run was preserved as invalid evidence. A
synthetic direct-Responses pilot then showed that the same model returns strict
JSON under an explicit 256-token cap in about 163--166 seconds for the
deliberately ambiguous control prompt. Three parallel requests completed in the
same envelope supported by the frozen server configuration.

## Hypothesis and causal mechanism

The scientific hypothesis, candidate, controls, hidden parity-rule task,
structural holdouts, regime shift, and ablation are unchanged. The transport is
new: each encounter is one independent LM Studio Responses request containing
an exact empty `tools` array, no `previous_response_id`, strict JSON schema,
low reasoning effort, and a 256-token output cap. Conditions within a phase are
submitted concurrently in frozen order, awaited as one wave, and only then do
controller-owned outcomes update all substrates.

The actor model is the 12,109,565,632-byte GPT-OSS 20B MXFP4 GGUF artifact with
SHA-256 `65d06d31a3977d553cb3af137b5c26b5f1e9297a6aaa29ae7caa98788cde53ab`.
The run lock will bind the model, LM Studio application and CLI, selected
llama.cpp runtime tree, Harmony adapter tree, live loaded-process configuration,
request fixture, prompt, substrates, task order, evaluator, and implementation.

## Cheapest decisive falsifier

Reject before actor execution if a frozen identity differs. Reject the run if
any request contains tools or prior-response context, exceeds its output cap,
times out, lacks a strict final JSON message, or violates isolation or resource
ceilings. Reject the behavioral claim if the candidate misses an absolute or
comparative threshold, misses the post-shift threshold, or loses fewer than
three predictions under projection ablation.

## Prospective predictions

- Each contact batch should leave exactly one candidate rule; the hidden shift
  should advance the candidate regime exactly once.
- Candidate held-out error should be at most 2/16 in each worker and shifted
  held-out error at most 1/8.
- Every baseline should make at least four more held-out errors than the
  candidate.
- Candidate projection ablation should cause at least 3/8 errors.
- All 52 responses should parse, use distinct response and workspace identities,
  contain zero tool calls, and receipt exact empty request inventories.
- Each worker should complete in at most 3,600 seconds.

## Privacy and storage review

Model weights, the salted task manifest, requests, responses, reasoning, exact
outcomes, response IDs, and workspaces remain outside Git under logical local
or evidence roots. Only fixed public inputs, content identities, and sanitized
aggregate scores may be tracked.

## Results

Pending.
