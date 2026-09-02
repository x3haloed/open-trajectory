# OT-0293 — Offered-world driver precedence

- **Status:** rejected at live isolation authority after consequence
- **Evidence class:** exploratory-only
- **Parent:** OT-0292 exact post-wake routing rejection
- **Invocation:** unchanged two content-free openings from the OT-0290 parent
- **Fresh actors:** one target selector, no retry

## Hypothesis

OT-0292's live branch was unreachable because generic environment expansion
outranked an already-active streamed-world offer. Giving that offer explicit
`expanded-select` precedence in the live derivation function, while retaining
the corrected hidden-content gate, should make the frozen scanner wake and
selection path causally reachable. The actual prospective driver—not merely a
downstream fixture—must produce `wake-world`, then `expanded-select`.

## Frozen correction

When `active_streamed_world_offer` is present, derive `expanded-select` before
delegating to the inherited generic derivation function. Otherwise preserve the
inherited result exactly. No other substrate, isolation, actor, world,
evaluator, or acceptance logic changes.

## Prospective gates and limits

Preserve OT-0292's exact rejected invocation and its zero-actor post-wake
subject. Reconstructing wake from the OT-0290 parent must reproduce that exact
subject. The actual live driver must derive the two-step wake/selection sequence;
the inherited driver must still demonstrate its rejected `expand-environment`
result on the offered subject, while no-offer derivation remains unchanged. All
OT-0292 content-isolation controls and selection branches must continue to pass.

Any broader precedence change, different wake subject, actor during wake,
sealed-content leak, actor/G10 rejection, retry, non-2/6 consequence, or failure
to derive correction rejects. Passing remains one bounded recovered-world
handoff into selected consequence, not a complete recurrence. Live output stays
sealed until design and passing preflight are pushed.

## Preflight result

The fixture passes. It reconstructs exact post-wake subject `3fcb9e39...`,
preserves OT-0292's no-actor rejection, and shows the inherited driver returns
the rejected `expand-environment` route while the corrected driver returns
`expanded-select`. A no-offer control remains `wait-provider`. All inherited
content-isolation controls and three 2/6 selection branches remain green, with
route 16/16 and identity 18/18. Preflight receipt `0fcea3cc...`.

## Live result

Both live operations become reachable. Actor-free wake reproduces exact
`3fcb9e39...`; the corrected driver then authorizes one fresh external-workspace
selector. Its seven commands are G10-clean, it chooses `count_crates`, and
sealed authority returns unresolved 2/6 consequence with correction next.

The invocation nevertheless rejects because its final `public_seed_only` gate
calls the inherited digest-proxy helper directly. OT-0292 replaced only the
fixture result, so preflight and live evaluation have separate isolation
authorities. The candidate successor `293d80f6...` is non-authoritative and the
post-wake parent remains current. Preserve the rejection. The next design must
install the corrected predicate at the shared helper called by both paths and
assert preflight/live predicate identity before actor authorization.
