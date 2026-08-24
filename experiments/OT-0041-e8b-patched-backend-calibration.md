# OT-0041 — E8B patched-backend protocol calibration

- **Status:** passed; E8B promoted for one fresh candidate
- **Evidence class:** private-reproducible evaluator calibration
- **Evaluation transition:** E7 → E8B candidate
- **Candidate goal output:** forbidden
- **Predecessors:** invalidated OT-0039; rejected OT-0040

## Hypothesis and corrected causal boundary

The exact revised schema already passed twice in OT-0040. Its remaining failed
gates arose because the locked npm executable shared a version label with, but
not the bytes of, the historical tool-inventory build. Binding the previously
calibrated patched executable should restore the model-visible three-tool
receipt while preserving the schema result.

An upstream HTTP 400 is an application response, not a proxy forwarding error.
The known-invalid schema therefore must produce the explicit structured turn
error, no response identity, and no secondary exception. Whether an inventory
notification precedes that rejected model request is recorded but not scored;
successful turns must emit the exact inventory.

## Frozen paired study and promotion

OT-0041 repeats OT-0040's four null-goal turns and reverse worker order with the
same positive schema, negative schema, prompt, model, app-server interface, and
resource bounds. It changes only the pinned executable bytes and the two
receipt semantics contradicted by OT-0040.

Promote E8B for exactly one fresh self-authored-goal candidate only if both
positive canaries, both negative diagnostics, positive inventories, responses,
deployment epoch, counterbalance, fresh contexts, tools, resources, tests,
audit, evidence, and privacy gates pass. A future candidate must bind the exact
positive schema and patched backend hashes after a clean implementation commit.

OT-0041 produces no candidate goal and cannot establish OT-2. It does not
reinterpret either predecessor or change any semantic evaluation threshold.

## Result and decision

The locked execution at `74d88b749d3a0748248e90fed3108ed98c5698d5`
passed every gate in 11.71 seconds. Both revised-schema turns returned the exact
null-goal canary, distinct response identities, the requested model, and the
exact three-tool inventory. Both frozen invalid-schema turns preserved the
expected `uniqueItems` application diagnostic with no response identity,
transport error, or secondary exception. Their inventory notifications were
explicitly present.

All four turns used fresh threads and workspaces, the positive/negative order
was reversed across workers, catalogs and ETag were stable, and tool, resource,
test, audit, evidence, and privacy gates passed.

Final disposition: `promoted`. E8B authorizes exactly one fresh self-authored-
goal candidate binding the revised schema and patched backend. OT-0041 emitted
no candidate goal and is not OT-2 evidence. The private artifact is identified
by `evidence/manifests/OT-0041/ot-0041-e8b-patched-backend-calibration-001.json`.
