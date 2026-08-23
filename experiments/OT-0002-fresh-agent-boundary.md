# OT-0002 — Fresh-agent encounter and substrate boundary

- **Status:** conditional
- **Evidence class:** exploratory-only
- **Target:** OT-1 infrastructure
- **Protocol-origin commit:** `6fe31a5f724a13bbc1bd4ebccd270c739dd6562a`
- **Frozen implementation commit:**
  `a270a296008284711d755a98c59324b7d28e0c32`
- **Frozen run lock:** `spec/ot-0002-run-lock.json`; execution remains
  prohibited until this lock and record are committed in a clean worktree

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

The hypothesis, cheapest falsifier, candidate and controls, task order, scoring
rule, resource budget, red-line review, promotion gate, implementation commit,
and all fixed-input identities were sealed before actor execution in
`spec/ot-0002-acceptance.json` and `spec/ot-0002-run-lock.json`.

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

Run `ot-0002-appserver-001` executed against `codex-cli 0.149.0` through the
Codex app-server backend using the drifting `gpt-5.6-luna` alias. The clean
execution commit was `8fa080f7bde5d2f7238e596b51810fea64db7cbd` and the
predating frozen implementation commit was
`a270a296008284711d755a98c59324b7d28e0c32`.

The categorical boundary results passed:

- the projection canary was recovered in 10/10 projection encounters and 0/10
  null-substrate encounters;
- no forbidden canary or denied-network reachability was recovered;
- all 20 backend thread identifiers and all 20 workspace identities were
  distinct;
- 10/10 direct denial checks and 8/8 deliberately opened positive controls
  passed;
- all actor outputs parsed, and the deterministic summary reconstruction
  matched twice within the original process.

The run did not pass the promotion gate. It consumed 347,604 input tokens
against the frozen limit of 80,000, although its 11,672 output tokens, 22 actor
turns, and 333.88 wall seconds remained within their frozen limits. The backend
did not provide a direct complete inventory of model-visible built-in tools,
and no second clean process regenerated byte-identical raw evidence.

One evidence-tooling defect was also preserved rather than corrected after
unsealing: completed turn snapshots summarized tool calls as zero, while the
raw event stream contains 26 command executions (52 start/completion events).
The raw events therefore preserve the actions, but the derived per-turn tool
count is not reliable for this run.

## Evidence manifests

- `evidence/manifests/OT-0002/ot-0002-appserver-001.json` identifies the raw
  exploratory artifact by SHA-256
  `2ebce1c9f539833575aadd531320d0930fa9c8041ccd27c6711413dac7148e98`
  and byte count 1,309,426. Local byte verification passed. No independent
  reconstruction was completed.

## Decision, limitations, and next experiment

**Disposition: conditional.** The tested local app-server envelope supports the
fresh-thread, fresh-workspace, denied-network, declared-MCP, and opaque
projection boundary, but the result is not promoted because the frozen
resource budget was exceeded and two promotion requirements remain
unavailable. This disposition does not establish learning and does not
authorize OT-0003.
