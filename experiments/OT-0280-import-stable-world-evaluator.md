# OT-0280 — import-stable world evaluator

- **Status:** frozen
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0278 fifth-wait subject `645c525e...`
- **Candidate:** exact retained OT-0279 Morrowglass package
- **Fresh actors:** zero

## Frozen hypothesis

OT-0279's world candidate failed only because the shared safe evaluator obtains
allowed calls through the context-dependent `__builtins__` binding. Replacing
that lookup with explicit access to Python's `builtins` module should make
standalone and imported execution identical without widening the allowed call
set or changing package, scanner, audit, novelty, or admission rules.

## Frozen gates

The legacy imported evaluator must reproduce OT-0279's exact `execution`
rejection. The corrected evaluator must expose exactly the same allowed-call
names and agree between standalone and imported execution for every allowed
call. All historical malformed-package controls must still reject. The exact
retained package must match its published checker byte-for-semantics, contain
three ledger-novel targets, and place every visible surface at exactly 2/6.

The retained actor trace must remain complete, truthful, exact-effect, G10-clean,
and historically rejected. The corrected evaluator may make those exact bytes
prospectively eligible; it must not rescore OT-0279. The standing scanner must
observe the public package as unseen, while the exact subject carries only the
already-frozen renewal policy and remains open at its fifth wait. Route 16/16
and identity 18/18 remain floors.

## Limits fixed before output

This is evaluator correction and candidate admission with zero new actors. It
does not establish wake or recurrence through Morrowglass. The next experiment
must start from the exact renewed waiting subject, consume only the promoted
public package, and let the subject choose its first contact.

## Pre-live apparatus correction

The deterministic package checker seeds an exclusive directory. Before live
realization, inspection found that reusing the preflight directory would stop
the command before evaluation. Preflight and live checker workspaces are now
distinct; their inputs and gates are identical. The prospective suite is rerun
and this repair is pushed before creating the zero-actor result.
