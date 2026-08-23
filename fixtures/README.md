# Small fixtures only

Tracked binary fixtures must be at most 64 KiB and accompanied by a provenance
or deterministic reconstruction note. Larger fixtures belong in the external
evidence store and are referenced by manifest.

`ot-0002/` contains the frozen public inputs for the fresh-agent boundary
experiment: actor output schema and prompt, sandbox and inventory declarations,
task order, and deterministic evaluator identity. Run-specific canaries,
thread identifiers, paths, events, and outputs are generated directly under
`$EVIDENCE` and never enter this directory.
