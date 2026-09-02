# OT-0346 — Toolchain-cache denial attribution

- **Status:** frozen; not yet executed
- **Evidence class:** exploratory-only
- **Source observation:** rejected OT-0345 fresh successor
- **Fresh actors:** none; exact retained-output reconstruction only

## Evaluation-regime checkpoint

G11 rejects actor-visible permission denials unless an already classified
incidental runtime-cache exception applies. OT-0345 exposed a narrower case:
every command exited zero, the public checker emitted an objective pass, all
declared effects were exact and contained, and the only visible denied writes
were macOS developer-tool attempts to create `xcrun_db-*` cache files under the
system temporary tree. The runtime also retained one unattributed filesystem
sandbox warning. These cache attempts did not affect the actor's work, but G11
correctly refuses to infer that from generic `Operation not permitted` text.

G13 is a prospective attribution layer before G11, not a generic permission
exception. It may classify a retained sandbox event as immaterial only when all
commands complete with exit zero; at least one checker emits valid JSON; every
visible `Operation not permitted` line exactly names an `xcrun_db-*` file under
the macOS `/var/folders/.../T/` cache shape; there is no other denial text; every
runtime violation is filesystem-only with `path=unknown`; and all existing
semantic, exact-effect, trace, denial, outside-effect, protected-path,
suspicious-command, and path-confinement gates pass.

## Frozen anchors and falsifier

The OT-0345 trace is development evidence and cannot promote G13. First compare
G13 on a held-out bundle containing successful `git` and Python-checker cache
denials plus generic file denial, wrong cache root, failed command, failed
checker, unsafe command, outside effect, protected access, incomplete trace,
concrete runtime path, and an additional unrecognized denial. G13 must recover
only the two cache cases. It must also leave all 15/15 G11 and 10/10 G12 anchors
unchanged.

Any counterfeit acceptance, hard-anchor regression, failure to classify the
exact OT-0345 trace, output or subject mismatch, hidden-case regression, or
failure to materialize the later successor rejects.

## Exact reconstruction and claim boundary

After promotion only, apply G13 once to the exact retained OT-0345 audit,
events, stderr, output, actor-derived public and hidden results, and corrected
pre-actor subject. If it classifies, change only audit attribution and actor
acceptance, then compile the successor exactly as OT-0345 would have. Require
the resulting subject to carry and materialize the actor-authored next contact
without private state while preserving the exact 40/40 floor.

OT-0345 remains historically rejected. OT-0346 can promote only corrected
operational reconstruction of the already-produced actor transition. It adds
no actor frequency, policy-origin, world-distribution, or autonomous carrier-
invention claim.
