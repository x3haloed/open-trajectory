# Instructions for research agents

Before changing experiments, evidence tooling, or acceptance rules, read
`TARGET.md`, `RED_LINES.md`, `PROGRAM.md`, `docs/EVIDENCE.md`, and
`docs/WORKFLOW.md` completely.

Before proposing or selecting a candidate mechanism, also read
`docs/RESEARCH_LANDSCAPE.md`. Treat it as a non-normative hypothesis map: use it
to widen the search, not as evidence or as an implicit acceptance rule.

## Research discipline

- Freeze a hypothesis, cheapest falsifier, relevant controls, decision envelope,
  world derivation, scoring rule, observation stopping rule, and promotion gate
  before unsealing candidate results. Subject-authored task order, contact, and
  retries may remain open when they are inside the frozen envelope.
- Keep plans and results distinct. Assign a stable `OT-NNNN` experiment record
  and never reuse an ID.
- Preserve negative evidence, reversals, invalidated premises, denied authority
  petitions, and surrendered goals.
- Promote only the complete causal path relevant to a claim. Component success
  is not endpoint success.
- Keep causal validity, actor provenance, and generative reproducibility
  separate. Missing hosted deployment receipts limit model-specific and
  reproduction claims; they do not automatically erase a complete bounded
  causal observation reconstructed from retained actor outputs.
- Treat self-report as a hypothesis, never as outcome evidence.
- For executable carriers, freeze and run conformance fixtures before actor
  authorization. After output, invalidate only material or uncertain deviations
  affecting information, authority, branch comparability, scoring, acceptance,
  safety, or the claimed mechanism; disclose immaterial deviations instead.
- Create a fresh actor thread and fresh workspace for every learning encounter.
  Cross-encounter continuity may pass only through the named candidate
  substrate and the exact projection recorded by the harness.
- Keep actor, world, substrate, and evaluator authority separate. The subject
  may own continuation state, pursuit selection, actor reopening, and proposed
  substrate changes, but may not alter sealed outcomes, final scores, evidence,
  or acceptance.
- Give actors the declared tool condition, including ordinary broad tools when
  intended. Protect authority with isolated workspaces, complete trace/effect
  audit, sealed evaluator state, and quarantine—not artificial incapacity.
- Seal a valid operational successor before observational controls. Controls
  may establish or narrow a claim but may not mutate, delay, veto, or terminate
  the sealed subject.
- Record observer and subject dispositions separately. An ended turn, invalid
  encounter, failed sibling, or exhausted observer budget does not close an
  otherwise open subject.
- A subject may inherit a fully functional, researcher-designed seed substrate
  implemented in this repository. Actor invention of the seed is not required
  for longitudinal continual adaptation. Keep fixed-machinery adaptation,
  consequence-driven machinery refinement, and open developmental expansion as
  separate claims.
- External developmental lineages and substrates may enter through an explicit
  adoption boundary when their exact ancestry, actor artifacts, consequences,
  authority, and reconstruction evidence satisfy the active claim regime. Do
  not import an unexamined system or award it stronger claims merely because it
  already exists.

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
- Run `python3 scripts/verify.py fast` before reporting a bounded result or
  preparing a normal commit. Run `python3 scripts/verify.py archive` when
  changing historical harnesses, shared evidence machinery, or frozen
  reconstruction paths, and before a tagged release.
- Inspect the exact staged diff. Automated scanning does not authorize
  publication of sensitive material.

## Environment evidence

Capture only explicitly allowlisted facts. Do not run broad environment,
process, mount, credential, or package dumps into tracked output. Dependency
identity belongs in a lock file; machine-local dependency paths do not.

If a valid public artifact requires a token rejected by the privacy audit, stop
and make an explicit policy decision rather than weakening or bypassing the
gate inside an experiment change.
