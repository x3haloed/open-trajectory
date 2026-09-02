# OT-0346 — Toolchain-cache denial attribution

- **Status:** executed — G13 promoted; exact operational rescue reconstructed
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

## Result

G13 recovered both held-out successful toolchain-cache cases and rejected all
10 counterfeits, passing 12/12 overall. G11 remained 15/15 and G12 remained
10/10. Only after that promotion, the exact OT-0345 development trace changed
from G11 rejection to G13 attribution. Every command had exited zero; all
visible denial lines matched the bounded macOS `xcrun_db-*` cache shape; the
checker result, semantic evaluation, exact changes, contained effects, and
unattributed runtime warning all matched retained bytes.

Exact reconstruction installs contact consequence `35e262ff...` without
resampling. The fresh actor's correction remains 3/3 public and 5/5 hidden, and
its selected next contact is now backed by the subject-held public frontier.
Exact open child `94399d16...` preserves the global 40/40 floor and materializes
the next workspace without private derivation state. Aggregate `36314aa0...`
is corrected operational-only evidence; OT-0345 remains rejected and no new
causal or generation claim is added.
