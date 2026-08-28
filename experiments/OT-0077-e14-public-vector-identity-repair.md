# OT-0077 — E14 public-vector identity repair

- **Disposition:** `invalidated`
- **Scope:** candidate-free prospective publication-identity repair of the
  rejected OT-0076 evaluator
- **Base result commit:** `877c6b49867b1d01fe99d06e0353f311b6f50df1`
- **Candidate outputs:** zero
- **Actor turns / hosted-model calls:** zero
- **E14 status before execution:** not promoted
- **Learner authorization before execution:** none

## Result

The implementation was frozen at Git commit
`8b550a29993bca6a8e849c8c05bb425faad9c73b`. Before any private derivation,
the authoritative preparation command reran the P-frozen public checkpoint.
The public journal retained all 323 expected sealed lineage segments and all
77,924 expected encounter commits, but the shared 900-second authority budget
expired during the full-suite verification tail. The stage therefore has no
stage seal and cannot support a public-checkpoint pass.

Failure preservation then exposed a separate implementation defect. The
quarantined journal contained 324 files and 395,165,748 bytes, while the
snapshot path incorrectly reused the 134,217,728-byte compressed-raw bound.
The exact journal move succeeded, but capacity exhaustion prevented the normal
compact failure receipt from being written and masked the primary timeout at
the CLI boundary. A read-only recovery validated the retained prefix and wrote
a post-hoc compact receipt. That receipt is operational negative evidence only;
it is not a stage seal, reconstruction, evaluator promotion, or learner result.

No attempt marker, private seed, private task, derivation receipt, or run lock
was created. Candidate outputs, actor turns, hosted-model calls, and authorized
learner count remain zero.

## Disposition and authority

OT-0077 is operationally invalidated before private derivation. E14 remains
unpromoted and this experiment authorizes no learner. The 900-second wall gate
must not be enlarged after this result. A newly numbered prospective repair may
retain the exact scientific task, controls, scoring, and promotion rule while
testing a bounded execution design that completes the public checkpoint inside
the unchanged wall budget and preserves oversized failure journals without
masking authority or mutation failures.

## Evidence

- Manifest:
  `evidence/manifests/OT-0077/ot-0077-e14-public-vector-identity-repair-001-public-checkpoint-failure.json`
- Receipt SHA-256:
  `bc6757e4ca46acdb6071dcadeceff6a702651cded789bb606277693c46eecf6e`
- Evidence class: `exploratory-only`
- Retained journal status: incomplete, not torn, 323 sealed segments,
  77,924 completed encounters, no stage seal
- Retained journal aggregate SHA-256:
  `2b626f96caa21fa37ca96fa0842665a0d059bc446ff7d2bb7859a0dfd8b21760`

## Hypothesis and bounded claim

The OT-0076 matched-counterfactual evaluator can support a valid candidate-free
E14 checkpoint if its exact public schema, canonical byte count, and SHA-256
identify the same payload. OT-0077 changes only that publication identity and
the new experiment wrapper identity. It does not change a task, condition,
mechanism, comparator, score, threshold, authority rule, resource bound,
private derivation rule, reconstruction rule, or promotion claim.

A complete private-anchor pass would promote only the E14 evaluator and
authorize at most one separately frozen actor-bearing inherited-substrate
candidate. It would not itself demonstrate model learning, learning-machinery
refinement, representation escape, cross-domain development, or Open
Developmental Trajectory.

## Preserved base protocol

Inherit the complete OT-0076 scientific and lifecycle protocol identified by:

- plan SHA-256
  `97b4bfcb533e332cdbedd89697b99e8e664d0cc084e1ace1fdfd8d0600f58e84`;
- acceptance SHA-256
  `86b34d38fce63f36d103fc72d4f67197361fb5d3847d0f70ba4de46d8f1f6174`;
- task protocol SHA-256
  `dd17c5b8e7296a21cd266ae10c52833feaab79d83dc96a9d615ab30d0a6b9359`;
- public-probe SHA-256
  `d4a989b8d86f59636ee8a9c6b176f0c4e3b59e09a86b995971af963720496f1f`;
  and
- rejection record SHA-256
  `bf083e6990eed795ef5999f65a9cd131c31e720f18813dc9a43fdbffb6887919`.

This inheritance includes the exact 23-condition inventory, 242-slot changing
and recurring stream, two positive online references, four required global
controls, two reference-specific matched-frozen controls, two reported adaptive
comparators, six per-reference interventions, placebo, matched-live-lift rule,
ten paired families, stale-binding gates, complete denominator, state and
operation budgets, 19 authority defects, nine causal-path gates, five rollback
gates, fresh-process/workspace/sentinel checks, independent primary and shadow
scoring, reconstruction, privacy, and publication verification.

The public worlds remain the exact four OT-0075 design seeds and 16 streams per
seed. The private world family remains exact, but OT-0077 must generate one new
256-bit private seed only after clean I and bind it to I through the OT-0077
wrapper identity. OT-0075 and OT-0076 generated no private seed, task, attempt,
or result. Eight OT-0077 private streams are used once. Reseeding, collision
replacement, task shopping, and returning to public design worlds after
unsealing are forbidden.

## Prediction error being resolved

OT-0076 required `consequence-withholding` in its exact nested public-vector
schema, but froze the byte count and digest of the otherwise identical payload
using `withholding`. The schema-conformant payload had 127,949 bytes and SHA-256
`a645282da3986557ce10dfdc9a550482107fea0f7ccaab0748deedafccb1d603`.
The alias payload had 126,413 bytes and the OT-0076 frozen digest. The public
oracle rejected OT-0076 before any private material existed.

OT-0077 freezes the schema-conformant identity. The only allowed nested key is
`consequence-withholding`; `withholding` is invalid. The canonical byte count is
127,949 and the SHA-256 is
`a645282da3986557ce10dfdc9a550482107fea0f7ccaab0748deedafccb1d603`.

## Exact public design identity

The public behavior vector contains exactly 128 rows ordered by design seed
`0..3`, case index `0..15`, then compact/log reference. Canonicalization is
UTF-8 `json.dumps(rows, sort_keys=True, separators=(',', ':'))` plus one LF.
Each row contains exactly:

- `design_seed`, `case_index`, `reference_id`;
- `live_errors`, `matched_frozen_errors`, `live_lift`,
  `matched_margin_pass`;
- `true_no_learning`;
- `stale_errors`, `stale_valid_predictions`, `stale_residual_lift`,
  `stale_two_thirds_loss_pass`, `stale_accepted_updates`,
  `stale_active_projection_changed`, and `stale_practical_margin_pass`.

`true_no_learning` contains exactly `consequence-withholding`,
`update-without-projection`, and `projection-without-update`. Each value contains
exactly `errors`, `prediction_status_trace_equal`,
`consumed_projection_trace_equal`, `terminal_projection_equal`,
`accepted_updates`, and `candidate_changed`.

All 128 rows must pass the preserved matched-margin, hard-severing, candidate-
ancestry, and stale-binding gates. The exact canonical vector must have 127,949
bytes and the SHA-256 above.

After changing only the top-level task experiment identity to `OT-0077`, the
four public wrapped task digests in seed order must be:

- `69be75695c060986bb937bc5a3aef9dcc2e8bef629b1a88179c86a42d598fc38`;
- `883f19567355037403eaffa0d5ebb4fac5e50b17b163c38a21573727deab3f16`;
- `f1f3007ce2ab78f3c756a154efbc4b6d6eb5c8975152d61c1bcc8f409596be6d`;
  and
- `efe00ac65a72f6031e9d54aa1bc2faee1eee92fc4f1cbf763a2e3ae6475a171f`.

## Frozen execution order

1. **P:** commit this plan, `spec/ot-0077-acceptance.json`, and
   `ot0077_protocol.py` before implementation.
2. **I:** implement the controller, learner import surface, receipts, workers,
   primary and shadow scorers, public oracle, and tests. No private artifact may
   exist. Reproduce the exact public vector, task digests, causal gates, scorer
   agreement, and complete test/audit regime. Commit clean I.
3. **L:** only from clean I and only after a fresh rerun of the public oracle,
   write the sole private attempt marker, generate one seed, derive the task and
   receipt, and commit the implementation-bound run lock as the direct child of
   I. Never regenerate or replace the seed.
4. Execute the eight-stream anchor once, reconstruct it from a fresh evidence
   root, record raw identity through `ot-evidence record`, rerun tests and audit,
   and publish the result without changing P, I, or L.

## Cheapest falsifier and promotion gate

Before any private write, reject OT-0077 if the implementation differs from the
exact schema, 127,949-byte count, vector digest, wrapped task digests, any public
behavioral gate, exact updater ancestry, authority defect, rollback gate, or
primary/shadow disposition. The public oracle must run before the attempt marker
or seed write.

After clean I passes, promote E14 only if both references pass all eight sealed
private streams, all ten paired families, every hard severing and stale-binding
gate, every causal/authority/rollback gate, fresh reset checks, exact clean
reconstruction, full tests, evidence/privacy audit, and publication verification
within the preserved wall budget. Any missing, invalid, timed-out, mismatched,
or unreconstructable result retains its denominator slot, rejects OT-0077, and
authorizes no learner. No threshold, task, order, baseline, implementation, or
identity may change after the private seed exists.
