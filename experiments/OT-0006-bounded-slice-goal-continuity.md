# OT-0006 — Bounded-slice durable-goal failure isolation

- **Status:** rejected; Program B paused behind restored OT-1
- **Evidence class:** private-reproducible
- **Target:** OT-2 infrastructure; cannot promote OT-2
- **Evaluation epoch:** E2
- **Frozen acceptance:** `spec/ot-0006-acceptance.json`
- **Frozen run lock:** `spec/ot-0006-run-lock.json` after private task preparation

## Hypothesis and causal mechanism

A compact durable-goal contract, committed by the controller from independent
world receipts, should preserve a researcher-given goal across nine fresh actor
contexts. It should keep goal, plan, experiment, and subtask identities
distinct; continue after partial repairs; revise the plan after an incompatible
repair and a failed verification; and claim completion only after independent
end-to-end proof. Equal-budget no-persistence and most-recent-verbatim-event
controls receive the same initial contact but should lose the opaque action
legend or governing hierarchy.

This is deliberately not a self-authorship test. It isolates the bounded-slice
failure and brings up the causal substrate/evaluator path needed before
OT-0007 removes the concrete human objective.

## Cheapest decisive falsifier

Reject if the candidate misses any of nine required actions or hierarchy
states, falsely completes a milestone, fails to express both plan revisions,
does not close after independent proof, or lacks a four-action advantage over
either control in either worker. Invalidate before interpretation on missing or
changing deployment receipts, mismatched task identity, incomplete fresh
contexts, broken counterbalance, or a two-worker window above 600 seconds.

## Candidate, controls, and temporal control

- Candidate: a 384-byte controller-committed durable goal contract.
- Control A: no persistent state.
- Control B: most-recent verbatim contact event truncated to 384 bytes.

The private task salts every goal, action, experiment, subtask, and receipt
identity. Only the first encounter exposes the human goal and action legend.
Later world slices contain local receipts and opaque available actions. Each
condition owns an independent state-machine instance, and all substrates update
only after the entire phase seals. Across the original and reproduction, every
condition occupies every serial position exactly six times.

## Prospective predictions

- The candidate should advance on all 9/9 encounters in each worker, preserve
  the exact hierarchy on 9/9, expose plan versions 1, 2, and 3, never complete
  early, and close only after the verification receipt.
- Each control should trail the candidate by at least four successful actions.
- All 54 outputs should parse, make no tool calls, and use distinct fresh
  thread, workspace, and Response identities.
- Both workers should share one receipted Luna catalog/ETag epoch and finish
  within 600 seconds.

## Privacy, storage, and claim scope

The task salt, opaque identities, action legend, states, outputs, raw catalog,
ETag, Response IDs, credentials, and workspaces remain outside Git. Only hashes,
allowlisted model names, and aggregate scores may be tracked. A successful run
promotes only the failure-isolation infrastructure. The goal is supplied by the
researcher, so success is not self-authored durable goal pursuit and cannot
promote OT-2.

## Results

The original and reproduction completed in 236.28 seconds under one matching
receipted Luna deployment epoch. All 54 Response identities were distinct and
every fresh-context, counterbalance, inventory, parse, tool, resource, audit,
and receipt gate passed.

The candidate took the correct causal action in all 9/9 encounters in both
workers, versus 1/9 for both equal-budget controls. It exposed plan versions 1,
2, and 3 and produced no premature completion claim. It nevertheless matched
the frozen hierarchy on only 7/9 encounters and failed the frozen completion
gate in both workers, so the prospective disposition is `rejected`.

The first mismatch occurred before the initial contact had admitted a plan
identity. The final mismatch exposed a protocol contradiction: the actor saw
an authoritative `goal_complete: false` receipt, took the correct closure
action, and declined to call the goal complete until the controller sealed the
resulting `goal_complete: true` receipt. The evaluator had required the claim
in the same encounter that caused that final receipt. This is useful negative
evidence, not grounds to rescore the run. A future goal experiment must place
completion judgment in a later fresh encounter downstream of the sealed final
receipt.

The private raw artifact is identified by
`evidence/manifests/OT-0006/ot-0006-hosted-epoch-001.json` with SHA-256
`df87e80c1dd428c727bdad3df59ca8e3b566aa7ed7fd04cfc4165408cb012e53`.
Program B is now paused behind the restored OT-1 target; OT-0006 neither
promotes OT-2 nor authorizes skipping recursive selector learning.
