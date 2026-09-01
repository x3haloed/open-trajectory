# OT-0231 — output-claim authority

- **Status:** promoted
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

G9 passes all ten held-out cases, preserves hard anchors 7/7, and improves
descriptive identity cases from incumbent 0/3 to 3/3. The retained OT-0230
decision is causally eligible with `qualified-consistent` provenance. OT-0230
remains rejected. Exact successor `9a9c49cc...` stays open at `assimilate`,
preserves the prior operation, and carries the contact as unadmitted content.
Receipt `fb6bff59...` promotes the transition.
