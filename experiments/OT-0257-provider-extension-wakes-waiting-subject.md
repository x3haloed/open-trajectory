# OT-0257 — provider extension wakes the waiting subject

- **Status:** frozen
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0256 waiting subject `a4eea95b...`
- **Fresh actors:** zero

## Frozen hypothesis

A real provider-catalog extension can satisfy the exact retained wait condition
and wake the same subject without an experiment-specific runtime dispatch or a
fresh actor concealing the wake-up transition.

The extended provider adds one previously unseen, inspectable coordination
world. Its observation must change the provider cursor, name that world as
available, and satisfy `unseen-world-available`. Only then may the transition
discharge the old wait handle and retain a durable world offer for the next
environment-expansion encounter.

## Frozen gates

Promotion requires the exact OT-0256 parent and receipt; the old provider still
empty; the extended provider returning exactly one unseen world; a seen-world
control returning empty; the old wait receipt preserved; one causally bound
discharge receipt; one immutable world offer; no actor, epoch, ledger, driver,
projection, or pursuit change; open continuation; exact identity and routing
floors; and idempotent re-observation of the already offered world.

This experiment promotes wake-up and durable offer retention only. A later
fresh actor must inspect the offer, author contact, and receive independent
world consequence before resumed interaction is established.
