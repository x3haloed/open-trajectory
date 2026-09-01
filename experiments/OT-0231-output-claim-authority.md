# OT-0231 — output-claim authority

- **Status:** frozen; not yet run
- **Evidence class:** deterministic-transition
- **Operational parent:** exact OT-0229 subject `2ecb779c...`
- **Prediction-error input:** rejected OT-0230 receipt `fb05c537...`
- **Actor budget:** none

## Frozen transition

G8 correctly separated changed-path self-report from mechanical effects, but
OT-0230 revealed that its caller still made descriptive target identity
authoritative. The output schema requires only a nonempty `selected_target`;
the exact workspace decision, G6, G7, public execution, diff, and trace already
establish the selected operation.

G9 separates schema/action transport validity, authoritative workspace semantics,
mechanical G8 effects, and descriptive output claims. Output identity is causal
authority only when the frozen contract explicitly declares it authoritative.
Otherwise it is classified `exact`, `qualified-consistent`, or `inconsistent`
for provenance. OT-0230 remains rejected.

Promote only if G9 passes ten held-out cases, preserves all seven hard anchors,
improves three descriptive-identity cases from incumbent 0/3 to 3/3, reconstructs
the OT-0230 workspace decision as mechanically eligible but unadmitted, preserves
the unresolved parent operation, and passes identity, route, reconstruction, and
privacy.

## Result

Not yet run.
