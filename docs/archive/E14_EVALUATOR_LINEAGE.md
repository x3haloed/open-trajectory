# E14 evaluator lineage archive

OT-0075 through OT-0078 tested and repeatedly repaired a prospective E14
evaluator. The lineage produced useful negative evidence about public-vector
identity, operational authority, reconstruction, and security boundaries, but
it never authorized a learner and is not part of the active research program.

The complete source and test surface is retained in Git at commit
`7b443429f8f6fdeb341227c0ef5582fc99d6cdc0`. Run:

```sh
python3 scripts/verify.py archive
```

That command first verifies the current active program, then creates a
temporary detached worktree at the archival commit and runs its complete test
suite and privacy audit. This preserves executable historical reconstruction
without making every active change carry the E14 implementation indefinitely.

The tracked experiment records and evidence manifests remain in the current
tree as the public account of what happened. The archival commit is historical
evidence, not current authority or a source of learner authorization.
