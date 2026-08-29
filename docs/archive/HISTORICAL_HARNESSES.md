# Historical harness archive

The completed OT-0002 through OT-0078 harnesses produced the observations,
negative results, and protocol failures recorded in `experiments/`. They are
not imported by the active OT-0079 mechanism and no longer remain in the live
package merely to make every new change carry their implementation surface.

OT-0075 through OT-0078 in particular tested and repeatedly repaired a
prospective E14 evaluator. That lineage produced useful negative evidence about
public-vector identity, operational authority, reconstruction, and security
boundaries, but it never authorized a learner.

The complete source and test surface is retained in Git at commit
`7b443429f8f6fdeb341227c0ef5582fc99d6cdc0`. Run:

```sh
python3 scripts/verify.py archive
```

That command first verifies the current active program, then creates a
temporary detached worktree at the archival commit and runs all 697 historical
tests plus its privacy audit. This preserves executable reconstruction without
making every active change carry every completed experiment indefinitely.

The tracked experiment records and evidence manifests remain in the current
tree as the public account of what happened. The archival commit is historical
evidence, not current authority, current library code, or a source of learner
authorization.
