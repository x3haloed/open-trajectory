# OT-0265 — content-free epoch-to-wait recurrence

- **Status:** promoted
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0264 subject `dd5a5be0...`
- **Fresh actors:** at most two, one selector and one corrector, no retries
- **Invocation:** repeat the same content-free `advance` entry point

## Realization contract

An outside caller may reopen the process but may not specify a target or phase.
On every invocation the harness must reload the exact prior checkpoint and derive
the next operation from subject state. Starting with one fresh opportunity, the
required sequence is selection, independent contradiction, correction,
projection refresh, empty-provider wait installation, and idempotent wait
re-observation.

## Frozen gates

Before actor authorization, prospectively realize the complete suffix. The sole
projected pair must pass registry-free admission, public execution, and sealed
2/6. Target-generic correction must pass public 4/4 and sealed 6/6 versus
unchanged 2/6. Refresh must produce zero opportunities and route to environment
expansion. The current extended provider must return empty; one open actor-free
wait must be installed, and a repeated observation must be an exact no-op.

Live invocations all use the same command and null pulse. Each invocation may
perform only the operation derived from the checkpoint. Checkpoints advance only
after their frozen gate passes. The final subject must preserve the earlier
wait/wake/provider lineage, saturate the current epoch, remain open, and carry a
second durable `unseen-world-available` wait. No resampling is permitted.

## Result

All five invocations pass through the same content-free entry point. The first
fresh actor selects the sole `coordination/radio.py::assign_relay_windows`
opportunity and receives sealed 2/6. The second fresh actor corrects it at public
4/4 and sealed 6/6 against unchanged 2/6. The next three actor-free invocations
refresh to zero opportunities, observe the extended provider empty and install a
new wait, then re-observe the same cursor as an exact no-op.

Exact open subject `d62f5fc2...` preserves the prior wait and discharge, carries
a second durable `unseen-world-available` wait, and remains conformant with the
16/16 route and 18/18 identity floors. Aggregate receipt `a3a72f20...` records
five null pulses, the exact derived operation order, and exactly two actors.

The corrector repeats the known non-authoritative changed-file reporting defect;
exact mechanical changes, clean complete trace, no outside effects, and G10 all
pass under the promoted reporting-authority regime. A later provider extension
and renewed live contact from this exact second wait remain untested.
