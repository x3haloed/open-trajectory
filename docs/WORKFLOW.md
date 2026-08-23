# Research workflow

## 1. Freeze the claim

Create an experiment record before execution. State the hypothesis, causal
mechanism, cheapest decisive falsifier, candidate, controls, task order,
splits, scoring rule, resource budget, red-line review, and promotion gate.

## 2. Run privately

Raw inputs, outputs, traces, and receipts go directly to the external evidence
store. Do not create them in a tracked directory and move them later.

## 3. Publish receipts

Use `ot-evidence record` to content-address the artifact and create a sanitized
manifest. Add only compact interpretation and bounded claims to the experiment
record.

## 4. Audit before interpretation becomes authoritative

Run:

```bash
ot-evidence audit
python3 -m unittest discover -s tests
```

Inspect the staged diff. The automated audit is a minimum gate, not permission
to publish personally identifying prose intentionally placed in a report.

## 5. Assign a disposition

Allowed dispositions are `promoted`, `conditional`, `rejected`, `reversed`,
`invalidated`, and `unexecuted`. A plan is never evidence. A component result
cannot promote a complete-path claim.

## 6. Preserve reversals

Never rewrite a failed experiment into a clean hindsight narrative. Add a new
record, link the superseded evidence, state which premise changed, and preserve
both manifests.

