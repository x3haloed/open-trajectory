# OT-0002 — Fresh-agent encounter and substrate boundary

- **Status:** unexecuted
- **Evidence class:** exploratory-only
- **Target:** OT-1 infrastructure
- **Protocol-origin commit:** `6fe31a5f724a13bbc1bd4ebccd270c739dd6562a`
- **Frozen execution commit:** pending; execution is prohibited until a clean
  implementation commit and the hashes required by `EncounterSpec` are recorded

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
forbidden canary. Actor recall is behavioral evidence, not proof of isolation.
The controller must also establish the boundary directly before the actor runs:

1. resolve and verify that the workspace remains beneath its declared logical
   root with no prior workspace materialized;
2. compare backend-issued thread identity digests and reject a resumed identity;
3. enumerate and hash the complete tool and MCP inventory, rejecting undeclared
   resources and servers;
4. enforce the frozen network policy with mode `denied`;
5. probe each seeded forbidden file, resource, process input, and controller
   handle through the same interfaces available to the actor, requiring a
   deterministic denial receipt.

Positive leak controls deliberately relax one boundary at a time and must make
the corresponding canary reachable. Repeat the permitted-channel trial with the
candidate substrate replaced by a null substrate.

## Candidate and controls

- Candidate: fresh-thread controller plus a minimal opaque substrate channel.
- Control A: null substrate.
- Control B: deliberately resumed thread, expected to fail the reset gate.
- Control C: deliberately reused workspace, expected to fail the reset gate.
- Control D: seeded hidden-world and controller metadata, expected unreachable.
- Control E: undeclared MCP resource and network egress attempts, expected to
  produce deterministic denial receipts.

No learning representation is being tested. The opaque substrate exists only
to establish the permitted causal edge.

## Frozen protocol and acceptance gate

- 100% recovery of permitted canaries across ten deterministic runs.
- 100% deterministic reachability of the deliberately opened channel in every
  positive leak-control run.
- 0% recovery of forbidden canaries across all channels and runs, treated only
  as supporting behavioral evidence.
- Deterministic denial receipts for every forbidden-channel probe in every
  isolation run.
- Fresh backend-issued thread identity digest and controller-verified workspace
  containment in every encounter.
- Exact projection digest and budget recorded before actor start.
- Exact clean implementation commit, model revision/stability, prompt, tool/MCP
  inventory, sandbox policy, evaluator, acceptance specification, dependency
  lock, and task-order identities recorded before actor start.
- The OT-0002 run profile validates, network policy mode is `denied`, and
  undeclared MCP resources are absent.
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
continuity and make the corresponding deterministic reachability probes pass.
Fresh threads, fresh contained workspaces, denied network egress, and a frozen
tool inventory should make all forbidden probes return denial receipts. The
primary uncertainty is whether backend or parent-agent context creates an
additional unrecorded path.

## Results

Unexecuted.

## Evidence manifests

None.

## Decision, limitations, and next experiment

Pending. Passing OT-0002 authorizes OT-0003 to begin substrate invention. It
does not establish learning.
