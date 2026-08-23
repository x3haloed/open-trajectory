# Instructions for research agents

Before changing experiments, evidence tooling, or acceptance rules, read
`TARGET.md`, `RED_LINES.md`, `PROGRAM.md`, `docs/EVIDENCE.md`, and
`docs/WORKFLOW.md` completely.

## Research discipline

- Freeze a hypothesis, cheapest falsifier, controls, task order, scoring rule,
  and promotion gate before unsealing candidate results.
- Keep plans and results distinct. Assign a stable `OT-NNNN` experiment record
  and never reuse an ID.
- Preserve negative evidence, reversals, invalidated premises, denied authority
  petitions, and surrendered goals.
- Promote only the complete causal path relevant to a claim. Component success
  is not endpoint success.
- Treat self-report as a hypothesis, never as outcome evidence.
- Create a fresh actor thread and fresh workspace for every learning encounter.
  Cross-encounter continuity may pass only through the named candidate
  substrate and the exact projection recorded by the harness.
- Keep actor, world, substrate, and evaluator authority separate. The actor may
  propose substrate changes but may not alter sealed outcomes or final scores.
- Do not import an existing memory system as an OT-1 candidate. Invent and
  evaluate substrate mechanisms inside this repository.

## Privacy and storage discipline

- Write raw outputs directly to `$OT_EVIDENCE_ROOT` or ignored `.evidence/`.
  Never stage raw evidence in Git and plan to remove it later.
- Do not place absolute paths, usernames, names from the local Git identity,
  emails, hostnames, environment dumps, secrets, or raw transcripts in tracked
  files, tool-generated summaries, experiment records, or manifests.
- Refer to paths only through logical roots such as `$REPO`, `$EVIDENCE`,
  `$DATASET`, and `$CHECKPOINT`.
- Do not commit datasets, checkpoints, archives, databases, model outputs, bulk
  traces, or generated caches. Git LFS is not an exception.
- Publish raw-artifact identity through `ot-evidence record`; do not hand-author
  manifest fields that the tool can derive.
- Run `ot-evidence audit` and the full test suite before reporting a result or
  preparing a commit.
- Inspect the exact staged diff. Automated scanning does not authorize
  publication of sensitive material.

## Environment evidence

Capture only explicitly allowlisted facts. Do not run broad environment,
process, mount, credential, or package dumps into tracked output. Dependency
identity belongs in a lock file; machine-local dependency paths do not.

If a valid public artifact requires a token rejected by the privacy audit, stop
and make an explicit policy decision rather than weakening or bypassing the
gate inside an experiment change.
