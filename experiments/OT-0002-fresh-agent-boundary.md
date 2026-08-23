# OT-0002 — Fresh-agent encounter and substrate boundary

- **Status:** unexecuted
- **Evidence class:** exploratory-only
- **Target:** OT-1 infrastructure
- **Frozen commit:** pending

## Hypothesis

A product-owned controller can execute consecutive Codex encounters such that
the named candidate substrate is the only causal channel from encounter `k` to
encounter `k+1`.

## Causal mechanism

Each encounter receives a fresh actor thread and workspace. The controller owns
the hidden world and sealed receipts, while the substrate emits one bounded,
hashed projection and accepts one declared post-contact observation.

## Cheapest decisive falsifier

Run two encounters with unique canary facts introduced separately through:

1. the permitted substrate projection;
2. a prior actor thread only;
3. a prior workspace only;
4. hidden world state;
5. controller-only metadata.

The next actor must recover the substrate canary and fail to recover every
forbidden canary. Repeat with the candidate substrate replaced by a null
substrate.

## Candidate and controls

- Candidate: fresh-thread controller plus a minimal opaque substrate channel.
- Control A: null substrate.
- Control B: deliberately resumed thread, expected to fail the reset gate.
- Control C: deliberately reused workspace, expected to fail the reset gate.
- Control D: seeded hidden-world and controller metadata, expected unreachable.

No learning representation is being tested. The opaque substrate exists only
to establish the permitted causal edge.

## Frozen protocol and acceptance gate

- 100% recovery of permitted canaries across ten deterministic runs.
- 0% recovery of forbidden canaries across all channels and runs.
- Fresh logical thread and workspace identity in every encounter.
- Exact projection digest and budget recorded before actor start.
- Complete action, tool, usage, receipt, and reset evidence.
- Deterministic world receipts reproduce from the frozen task seed.
- Privacy and repository-size audits pass.

Any forbidden-canary recovery kills learning experiments until the channel is
identified and removed.

## Privacy and storage review

Raw Codex events, thread identifiers, workspaces, and canary values remain
under `$EVIDENCE`. Public receipts contain only logical IDs, hashes, counts,
backend version, and pass/fail classifications.

## Prospective predictions

Native thread resume and workspace reuse should both transmit forbidden
continuity. Fresh threads plus fresh workspaces should remove those channels;
the primary uncertainty is whether backend or parent-agent context creates an
additional unrecorded path.

## Results

Unexecuted.

## Evidence manifests

None.

## Decision, limitations, and next experiment

Pending. Passing OT-0002 authorizes OT-0003 to begin substrate invention. It
does not establish learning.

