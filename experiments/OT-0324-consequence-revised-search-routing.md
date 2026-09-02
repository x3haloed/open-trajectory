# OT-0324 — Consequence-revised search routing

- **Status:** frozen
- **Evidence class:** exploratory-only
- **Parent:** exact OT-0323 subject `aba1513f...`
- **Claim:** consequence can revise the executable machinery that chooses among
  future openings, and a later fresh actor can use that retained revision to
  reach improvement that the unchanged active-router branch misses.

## Frozen hypothesis

OT-0323's router invokes search on any front where the incumbent fails at least
one contact, then breaks ties by opaque front identity. When two such fronts are
available, it will choose a failure-bearing front where bounded search is
already saturated instead of a front with reachable gain. Given the completed
route consequence and both public search summaries, a fresh actor can revise
the router. A later fresh actor using that retained source will select reachable
gain under new identities and reversed offer order, repair the stake, preserve
the cumulative 20/20 floor, and reach 25/25. The unchanged active binding will
retain the same proposal and evidence but route to the saturated dead end.

## Cheapest falsifier

Fail if the incumbent router does not choose the saturated failure-bearing
front, the machinery actor does not produce a safe conformant changed router,
the changed router does not generalize to new front identities/order, its
successor does not reach 25/25 without regression, or an unchanged-active-
binding control reaches the same endpoint.

## Frozen protocol

1. Bind exact parent `aba1513f...`, OT-0323 promotion, executable search, and
   incumbent router identities before private contact.
2. Generate diagnostic summaries for two three-contact fronts. The first has
   incumbent 2/3 and complete bounded best 2/3, so failure exists but no
   improvement is reachable. The second has incumbent 0/3 and bounded best
   3/3. The incumbent router must choose the first by opaque identity.
3. Open one fresh broad-tool machinery actor with the incumbent router, both
   summaries, its failed route consequence, public executable fixtures, and a
   one-file mutation envelope. It may edit only `route_search.py`; it must run
   the checker and inspect the exact diff. Controller validation independently
   enforces the visible interface, safe source boundary, public fixtures, G10,
   and changed source.
4. Compile the same actor-authored router proposal and consequence into two
   exact branches. Both retain the complete proposal source and receipt. The
   candidate binds it active; the matched control leaves the old router active.
5. Derive a new private held-out two-front offer with new identities and
   reversed offer order. Bind both routes before successor actors. The
   candidate must select the reachable-gain front; the unchanged binding must
   select the failure-bearing saturated front.
6. Open one fresh broad-tool stake actor per route in isolated workspaces with
   identical search, workbench, checker, schema, and budgets. Seal a valid
   candidate child before opening the unchanged-router actor.
7. Score both stakes on five new call-margin cases plus the parent's twenty-case
   cumulative floor. Useful and decoy programs differ only in call count within
   each case; all other public features and source bytes match.

## Frozen gates

Promotion requires all of:

- preflight identity, source, authority, feature-isolation, diagnostic route,
  actor ABI, safe-execution, public-generalization, and 25/25 reachability
  checks pass before authorization;
- the diagnostic incumbent route selects a 2/3, best-2/3 front while another
  offered front is 0/3, best-3/3;
- the machinery actor is clean, changes only `route_search.py`, passes its
  visible checker, and produces a source distinct from the incumbent;
- both comparison branches retain the exact same proposal source, correction
  evidence, outcomes, and tools; only active-router binding differs;
- on new identities and reversed offer order, changed routing selects reachable
  gain and unchanged routing selects the saturated failure-bearing front;
- the changed-route successor is clean, adopts an inherited-search witness,
  replays 3/3, preserves 20/20, and reaches 25/25;
- the operational child is sealed before the unchanged-route successor;
- the unchanged-route successor is clean, finds no improving search candidate,
  retains exactly, and remains 20/25;
- the exact final child is open and retains the actor-authored router source,
  its proposal/correction ancestry, active binding, route, and stake revision.

Material authority violations quarantine the encounter. Candidate operational
success without the unchanged-active causal separation is conditional only.
Otherwise reject and reopen exact parent `aba1513f...`.

## Scope

One passing run would be bounded OT-2 evidence that completed consequence
improved executable future-move selection across fresh actors. It would not be
a reliability estimate, proof that the learned rule is optimal or permanently
corrigible, autonomous world generation, or full OT-2R recurrence.
