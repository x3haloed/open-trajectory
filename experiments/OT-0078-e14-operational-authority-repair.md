# OT-0078 — E14 operational-authority repair

- **Disposition:** `unexecuted`
- **Scope:** candidate-free prospective runtime, journal-seal, and failure-
  preservation repair of the invalidated OT-0077 evaluator
- **Base result commit:** `d92f0a8f68c20da07308e7b50616a3f68939704f`
- **Candidate outputs:** zero
- **Actor turns / hosted-model calls:** zero
- **E14 status before execution:** not promoted
- **Learner authorization before execution:** none

## Hypothesis and bounded claim

The unchanged OT-0077 scientific evaluator can complete inside its frozen
900-second authority budget if independent repository verification overlaps
the public probe and scientific workload, and if the final journal seal verifies
already validated durable segment identities without semantically decoding the
complete causal payload a second time on the critical path.

The separate failure-preservation hypothesis is that a descriptor-relative
streaming snapshot with its own 536,870,912-byte bound can summarize the exact
expected public journal without reusing the 134,217,728-byte compressed-raw
bound or loading the entire journal into memory. Within the frozen byte bound
and segment-count bound, authority, inventory, identity, content, or same-inode
mutation failures must fail closed and may not degrade to an `unreadable`
summary. If the byte bound is exceeded, a `bounded-unreadable` summary must
retain the primary failure, make no content-identity validation claim, and still
hard-fail discrepancies visible from the fully enumerated and pinned metadata.
Exceeding the 4,096-segment inventory bound is itself a hard preservation
failure, never a `bounded-unreadable` receipt.

OT-0078 changes no task distribution, horizon, task order, reference,
comparator, intervention, threshold, scoring rule, causal receipt, reset rule,
rollback rule, reconstruction rule, private-seed rule, 900-second deadline, or
promotion claim. A complete private-anchor pass would promote only E14 and
authorize at most one separately frozen actor-bearing inherited-substrate
candidate. It would not itself demonstrate model learning, machinery
refinement, representation escape, cross-domain development, or Open
Developmental Trajectory.

## Preserved scientific protocol

The OT-0077 prospective identities remain frozen as historical inputs:

- plan SHA-256
  `bae447edbe3cd80e7e8c3a2e4ff4e9defb8acc65e9ccc58c2976a9d065de2035`;
- acceptance SHA-256
  `4a79e7cc4b82ec40d7f2a37de32716b79e4049a4af1fcc45f8551dd16a63965d`;
- task protocol SHA-256
  `7deb8a7b01ecdf57716958956f810f67487bd24b88e98073055d2d55e1c41b48`;
- implementation commit
  `8b550a29993bca6a8e849c8c05bb425faad9c73b`;
- invalidation record SHA-256
  `4e6868fa988ec93ca0ad57239070812c21b008911607026aba58a672b79bb03f`;
  and
- failure-manifest SHA-256
  `f2de64e870a23dc032160eed6b32f6bdf2f9c02c4092355307f3cecf3bf659d3`.

OT-0078 inherits the exact 23-condition inventory, 242-slot changing and
recurring stream, two online-admissible positive references, four global
required controls, two matched-frozen controls, two reported adaptive
comparators, identity placebo, six reference-specific causal interventions,
ten paired families, primary and independent shadow scoring, rollback suite,
fresh resets, reconstruction, and all causal and authority defects.

The P-frozen OT-0078 identities are:

- acceptance SHA-256
  `404744328532bb9c565674e56e5971346020a9da08ab297f72f5beb8a689ecc9`;
- task protocol SHA-256
  `bd8608ffa864f984c5331a98d7669d783e22eb118645f23a8228392606ab24d0`;
- public vector: 128 rows, 127,949 canonical bytes, SHA-256
  `a645282da3986557ce10dfdc9a550482107fea0f7ccaab0748deedafccb1d603`;
  and
- OT-0078 wrapped public task SHA-256 values, in seed order:
  `62afdb93fe460b74d858a30d969adecd31c857ce578a00a10f0102e697ab2495`,
  `1917e74443f907b398dad4445023f6b5a7f64e8f253875039edf91cd88e90b6b`,
  `6f1d31dcb8b50f9a3827ff7b3e118cf8f181f81542e80b2fa6daa03f1cbe0e1b`,
  and
  `d4f9048026b16987641de9d055d27a2a939877fee277787e3dce1ddd14d1e62a`.

## Frozen operational repair

1. Start the exact full repository tests and evidence/privacy audit as bounded,
   independently captured verification authorities at the beginning of the
   900-second checkpoint. Run the public design probe and scientific workload
   concurrently with them. Bind both observed verification results before
   primary or shadow scoring. A missing, timed-out, nonzero, or output-invalid
   verification retains its gate failure.
2. Preserve every existing per-encounter append and durability synchronization.
   When a lineage seals, retain a controller-owned identity derived from its
   already canonical, fully validated chain and its exact durable encoded bytes.
3. Before the stage seal, pin the journal-root and segment-directory
   authorities and resolve both exact inventories. Re-open `stage-open.otj`
   without symlink following and require exact equality to its creation-time
   canonical bytes, SHA-256, byte count, and inode/generation identity. For
   every segment, re-open without symlink following, stream its bytes, and
   require exact SHA-256 and byte-count equality to the writer-owned identity.
   Rebind the stage-open leaf, every segment leaf, both directories, and the
   unchanged segment inventory after capture. Construct canonical stage-seal
   bytes only from these reverified stage-open and segment identities, install
   the complete seal atomically and exclusively, re-open `stage-seal.otj`
   without symlink following, and require exact equality to those canonical
   bytes, SHA-256, byte count, and inode/generation identity through final
   return. Then rebind every leaf and directory again. The journal-root
   inventory must change only from `{stage-open.otj, segments/}` to that exact
   set plus `stage-seal.otj`; the segment-directory inventory and generation
   must remain unchanged. Reject every other root or segment-directory
   transition. Do not parse hundreds of thousands of causal receipts a second
   time on this critical path.
4. Quarantine failure journals through pinned evidence-store authority. Stream
   the exact bounded inventory into an immutable temporary copy while recording
   per-leaf identity and generation, validate the copy, then rebind every live
   leaf and both directory inventories. The failure-journal aggregate bound is
   536,870,912 bytes and 4,096 segments. Inside both bounds, every content and
   metadata discrepancy hard-fails. Byte-capacity exhaustion writes the compact
   primary-failure receipt with an explicit `bounded-unreadable` journal status
   and no content-validation claim; metadata-visible authority, inventory,
   symlink, or generation discrepancies still hard-fail. Segment-count capacity
   exhaustion hard-fails preservation without an unreadable downgrade.
5. Keep raw-result publication at its existing 134,217,728-byte compressed
   bound. The larger journal-failure bound does not enlarge candidate state,
   projection, raw results, Git artifacts, or published model output.

## Frozen execution order

1. **P:** commit this plan, `spec/ot-0078-acceptance.json`, and
   `ot0078_protocol.py` before implementation.
2. **I:** implement only the new wrapper identity and the operational repair.
   No OT-0078 private artifact may exist. Reproduce the exact public vector,
   wrapped task digests, causal gates, primary/shadow disposition, full tests,
   audit, hard-wall races, and oversized-journal failure preservation. Commit a
   clean implementation.
3. **L:** only from clean I and only after the complete public checkpoint passes
   inside 900 seconds, write the sole OT-0078 attempt marker, generate one fresh
   256-bit seed, derive the private task and receipt, and commit the
   implementation-bound run lock as the direct child of I. Never regenerate or
   replace the seed.
4. Execute the eight-stream anchor once, reconstruct it from a fresh evidence
   root, record raw identity through `ot-evidence record`, rerun tests and audit,
   and publish the result without changing P, I, or L.

## Cheapest falsifier

Before any private write, reject OT-0078 if any of the following occurs:

- the P-frozen acceptance, protocol, public-vector, or wrapped-task identity
  differs;
- any public scientific, causal, control, intervention, authority, rollback,
  reset, primary/shadow, or expected-disposition gate differs from OT-0077;
- any verification result is unavailable or not bound before scoring;
- the public journal lacks exactly 323 sealed segments and 77,924 completed
  encounters;
- the complete checkpoint lacks a valid stage seal or exceeds 900 seconds;
- final seal verification accepts stage-open, journal-root, segment-directory,
  or segment replacement; symlink substitution; reversible same-inode
  mutation; inventory change; byte-count change; or digest change; or
- stage publication accepts any journal-root transition other than the exact
  atomic addition of one canonical `stage-seal.otj` leaf, or any segment-
  directory inventory or generation transition; or
- final seal verification accepts `stage-seal.otj` substitution, replacement,
  symlink substitution, reversible same-inode mutation, byte-count change,
  digest change, or inode/generation change before return; or
- a within-bound authority, inventory, symlink, generation, digest, byte-count,
  content, or mutation discrepancy is downgraded to a readable or unreadable
  compact receipt; or
- byte-capacity exhaustion masks the primary failure, claims content identity,
  or accepts a discrepancy visible from fully enumerated pinned metadata; or
- segment-count capacity exhaustion produces `bounded-unreadable` rather than a
  hard preservation failure.

Any failure authorizes no seed, private task, anchor, evaluator promotion, or
learner. The retained OT-0077 journal is negative evidence and may be used only
to test failure preservation; it may not be treated as a completed OT-0078
scientific stage.

## Promotion gate

After clean I passes the public checkpoint, promote E14 only if both positive
references pass all eight newly derived private streams, all ten paired
families, every hard severing and stale-binding gate, every base causal,
authority, rollback, and reset gate, exact clean reconstruction, full tests,
evidence/privacy audit, and publication verification inside the unchanged
900-second wall budget. Missing, invalid, timed-out, mismatched, or
unreconstructable slots remain in the denominator and reject OT-0078.

On promotion, authorize exactly one separately P-frozen actor-bearing
inherited-substrate learner. On any other disposition, authorize zero. No
private task, threshold, task order, comparator, implementation, or identity
may change after the seed exists.
