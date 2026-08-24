# OT-0006 — Bounded-slice durable-goal failure isolation

- **Status:** frozen; execution pending
- **Evidence class:** private-reproducible if all gates pass
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

Pending.
