# Agent harness architecture

## Purpose

The harness exists to answer one causal question:

> Did prior contact, transmitted exclusively through candidate substrate S,
> reduce a fresh agent's error on a later held-out encounter?

It is not a continuous assistant product and does not preserve a canonical
long-lived agent thread. Ordinary thread continuity would create an unmeasured
inheritance channel and make OT-1 uninterpretable.

## Selected topology

```text
                         sealed task/outcome authority
                                  ┌─────────┐
                                  │  world  │
                                  └────┬────┘
                                       │ task / receipt
                                       ▼
┌────────────┐ starts fresh    ┌───────────────────┐
│ Codex actor│ ◀────────────── │ experiment        │
│ thread +   │ ──────────────▶ │ controller        │
│ workspace  │ prediction/action└──────┬────────────┘
└──────┬─────┘                          │ observe / project
       │ candidate-specific MCP         ▼
       │ or initial projection    ┌──────────────┐
       └────────────────────────▶ │ substrate S  │
                                  └──────┬───────┘
                                         │ immutable snapshot identity
                                         ▼
                                  ┌──────────────┐
                                  │ evidence     │
                                  │ recorder     │
                                  └──────────────┘
```

One controller is the authority for episode order and lifecycle. One world is
the authority for task truth and outcomes. One candidate substrate is the only
cross-encounter inheritance channel. One evidence recorder binds all of them by
content identity.

The judge is a consumer of sealed evidence, not a second authority over world
truth. A model judge may interpret results but cannot override deterministic
scores or receipts.

## Codex execution backends

The controller owns an adapter interface so experiments do not depend on a
single orchestration embodiment.

### Backend A — Codex SDK or app server

Start one new Codex thread per encounter, stream typed events, and close or
archive the thread after the encounter. The official Codex SDK supports
starting, continuing, and resuming threads programmatically. This program uses
new threads for learning trials; resume is reserved for within-encounter
recovery tests.

The controller supplies thread-scoped sandbox policy, working directory,
model, tool configuration, and resource budget. Raw events go directly to the
external evidence store. Only normalized receipts and hashes enter Git.

The run specification records whether the backend exposes an immutable model
revision or only a drifting alias. A drifting alias is admissible for OT-0002
harness development when declared, but it cannot support a promoted OT-1
comparison whose target requires a frozen base model.

`spec/encounter-run.schema.json` defines the reusable run contract.
`spec/ot-0002-run.schema.json` adds the denied-network requirement, and
`spec/ot-1-promoted-run.schema.json` adds the immutable-model requirement.

### Backend B — Codex as an MCP server

For a broader orchestrator, Codex CLI may run as an MCP server. The controller
still enforces a fresh encounter identity and workspace and must retain the
same event, budget, and evidence semantics as Backend A.

Official documentation recommends the Codex SDK for coding-focused Codex
threads and Codex-as-MCP when Codex is one specialist in a broader orchestrated
workflow:

- https://learn.chatgpt.com/docs/codex-sdk
- https://learn.chatgpt.com/docs/codex-mcp-server

### Backend C — Native Codex subagents

A supervising Codex run may create subagents in crafted directories for early
experiments. This is admissible only when the run records fresh-agent identity,
workspace identity, exact initial projection, tools, model, budget, and full
events. It must not rely on parent conversation context as unrecorded input.

Backend C is useful for cheap pilot work. Backend A or B is preferred for
promoted results because the controller can enforce and inspect lifecycle
boundaries directly.

## Encounter lifecycle

Every encounter follows the same controller-owned sequence:

1. Resolve a frozen `EncounterSpec`; verify its clean implementation commit,
   protocol identities, tool inventory, and every input manifest.
2. Create a new workspace beneath `$EVIDENCE/sandboxes/<run>/<encounter>`.
3. Resolve the workspace and prove containment beneath its declared root.
   Enforce the hashed network policy, materialize only the permitted task
   surface, and keep answers and future state outside that workspace. OT-0002
   requires network mode `denied`.
4. Ask the candidate substrate to produce its bounded inheritance projection.
5. Start a fresh actor thread with the projection, task, tools, and budgets.
6. Require prospective predictions before consequential actions or outcome
   revelation.
7. Seal the actor's final action and prediction.
8. Let the world produce an independently retained receipt and score.
9. Give the candidate substrate the declared observation—not arbitrary access
   to controller or world state—and commit a new immutable snapshot.
10. Close the actor, preserve raw events externally, and publish sanitized
    manifests.

No step may resume the prior encounter's actor thread.

## Backend-independent substrate contract

The contract deliberately avoids assuming that inheritance is text, vectors,
rules, code, weights, graphs, or a database:

```text
initialize(candidate_config) -> snapshot_0
project(snapshot_k, encounter_spec, byte_budget) -> projection_k
observe(snapshot_k, sealed_contact_receipt) -> update_proposal
commit(snapshot_k, update_proposal) -> snapshot_k+1
inspect(snapshot_k) -> content-addressed diagnostic receipt
```

`projection` is the exact causal payload available to the next actor. Its byte
count, digest, construction time, and tool-call budget are recorded. Candidate
implementations may expose MCP tools in addition to an initial projection, but
all responses count against the same declared inheritance budget.

The controller—not the actor—calls `commit`. An actor may author an update
proposal, but contact receipts and the committed snapshot remain external
authorities.

## World boundary

Worlds run in directories or processes the actor cannot inspect. A world
exposes only:

- the current task surface;
- permitted actions;
- receipts released at declared points;
- final scores after predictions are sealed.

Hidden rules, held-out cases, future regime changes, evaluator prompts, and
answer keys never appear in actor-accessible files, process arguments, tool
descriptions, logs, or MCP resources.

OT-0002 must deliberately insert one leak through each relevant channel and
prove the harness detects or prevents it. The controller must inspect the
backend-issued thread identity, resolved workspace containment, complete tool
and MCP inventory, network policy, and seeded resource reachability directly.
Actor failure to repeat a canary is supporting behavioral evidence only; it is
not proof that the canary was inaccessible.

## Judge separation

A separate critic is used when an error-producing perspective must be distinct
from the maker. For promoted evidence:

- deterministic evaluation outranks model judgment;
- the judge reads controller-selected sealed evidence, not actor-selected
  excerpts;
- the judge cannot change world receipts;
- judge prompt, model, tools, and evidence set are frozen and recorded;
- actor and judge workspaces are separate;
- disagreements remain evidence rather than being silently reconciled.

## Required receipts

Each encounter produces external raw evidence and public manifests for:

- encounter specification and task-input identities;
- protocol-origin and clean implementation commits, acceptance-specification,
  dependency-lock, prompt, task-order, and evaluator identities;
- actor backend, exact model revision and stability classification, backend-
  issued thread identity digest, sandbox policy, tool/MCP inventory, and budgets;
- exact inheritance projection and substrate snapshot digests;
- prospective predictions and timestamps/order;
- permitted actions and world receipts;
- score and evaluator identity;
- substrate update proposal and committed successor digest;
- reset proof showing no prior workspace or thread was resumed;
- usage and failure disposition.

Identifiers published to Git must be logical or hashed. Raw thread identifiers,
workspace paths, and process environment remain external.

## Promotion boundary

A backend is research-ready only after OT-0002 proves:

- actor tasks execute in real fresh workspaces;
- consecutive encounters use fresh actor threads;
- resolved workspaces remain beneath their declared roots, the OT-0002 network
  policy denies egress, and the complete tool/MCP inventory matches its frozen
  digest;
- removing the candidate projection removes all intended inheritance;
- seeded forbidden files, resources, process inputs, and controller handles
  produce deterministic denial receipts, while deliberately opened positive
  controls are reachable;
- event and usage receipts are complete enough to enforce budgets;
- a reconstructed run produces the same deterministic world receipts;
- privacy and repository-size audits pass.

Until then, agent runs are harness-development evidence, not learning evidence.
