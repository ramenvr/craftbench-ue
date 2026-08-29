---
id: t3-dash-responds-now-and-converges-later
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_PredictedDash :: APredictedDashNetworkFunctionalTestA", "L_PredictedDash :: APredictedDashNetworkFunctionalTestB"]
introspect: [t3_predicted_dash_convergence.py]
deadline_s: 2400
action_budget: 80
accepted_files: [Source/ThirdPerson/Tasks/t3-dash-responds-now-and-converges-later/PredictedDashMovementComponent.h, Source/ThirdPerson/Tasks/t3-dash-responds-now-and-converges-later/PredictedDashMovementComponent.cpp]
---

# t3-dash-responds-now-and-converges-later

> **AUTHORED / COMMITTED-HEAD DISCRIMINATION PASS.** The retained map, dedicated authority,
> autonomous owner, simulated observer, emulated latency/loss, correction
> telemetry, and authority-owned accounting are implemented. Three fresh
> admission rounds (06-08) each passed both reversed-order policies and all five
> gates with protected inputs unchanged. On commit `fe1fce76`, the production
> reference passed L1/L2/L2I while the byte-identical live baseline passed L1 and
> failed both network scenarios as behavior (not harness) plus three structural
> checks. Committed-head refgate and branch integration remain the publication
> boundary.

Make dash respond now and converge later

## Primary concept

- `networked-movement-cmc` - Character Movement prediction and correction

### Composed concepts

- `net-actor-role` - authority, autonomous proxy, and simulated proxy
- `net-rpc` - validated request metadata
- `net-replicate-properties` - authoritative energy/cooldown state
- `ps-components` - custom CharacterMovementComponent and SavedMove lifecycle

### Production-pattern justification

A responsive multiplayer movement ability must participate in CharacterMovement
prediction rather than teleporting or waiting for a round trip. The autonomous
proxy should react immediately, the server should accept or reject from its own
policy, corrections should converge every role, and authoritative cost/cooldown
must apply once only for accepted movement.

### Concept-interaction notes

The protected server varies direction, magnitude, latency/loss profile, starting
energy, cooldown, and accept/reject policy. Role-qualified telemetry independently
records input, SavedMove flags/data, prediction start, server validation, correction,
simulated-proxy movement, and authoritative accounting.

## Prompt given to the agent

> Complete the supplied predicted dash movement component. When the autonomous
> player requests a dash, make it respond through CharacterMovement prediction
> before server acknowledgement. Send the request through custom move data so
> the server can validate the supplied policy. Accepted dashes must converge on
> server, owner, and simulated proxy and apply energy/cooldown exactly once.
> Rejected dashes must correct the owner back and apply no cost or cooldown.
>
> The verifier changes direction, delay/loss, energy, cooldown, and acceptance.
> Do not teleport, multicast transforms, launch only on the server, spend on both
> client and server, trust a client acceptance flag, or hardcode policy values.
>
> Edit only `PredictedDashMovementComponent.h` and
> `PredictedDashMovementComponent.cpp` under
> `Source/ThirdPerson/Tasks/t3-dash-responds-now-and-converges-later/`.
> Do not edit the supplied character, policy, map, tests, network settings, or
> other source.

## Workspace state pre-task

- Editable inventory: exactly the custom movement-component `.h/.cpp` pair. The
  live baseline compiles with ordinary CharacterMovement but no dash move.
- The protected character constructs that component as its default movement
  component and exposes verifier-owned request/policy/accounting hooks.
- Retained protected map:
  `Content/Maps/t3-dash-responds-now-and-converges-later/L_PredictedDash.umap`.
- The dedicated server owns acceptance policy and authoritative energy/cooldown.
  Clients cannot edit or infer hidden policy except through observed outcome.

## Verifier specification

L1 builds Editor, Game, and required server target; enforces the exact editable
source pair and rejects submitted character, policy, map, config, alternate move
component, or extra source.

L2 aggregates a dedicated server, one autonomous owner, and at least one simulated
client under two fixture policies and verifier-owned packet emulation. Each policy
contains accepted and rejected requests with different direction, energy, and
delay/loss. Ordinary engine/world/network clocks drive all samples; no manual tick
or transform repair is permitted.

For accepted movement, the owner must begin bounded dash displacement before
server acknowledgement, the server must validate matching move data, and server/
owner/simulated transforms must converge after correction/replication. Exactly one
authoritative energy delta and cooldown epoch occur. For rejected movement, the
owner may predict initially but must roll back within the correction window, while
energy and cooldown remain unchanged on authority and converge unchanged to peers.

Fixed L2 denominator: exactly five named gates.

1. `AutonomousProxyRespondsBeforeAcknowledgement`
2. `ServerAndOwnerConvergeAfterCorrection`
3. `SimulatedProxyObservesOneDash`
4. `DashCostAppliesExactlyOnce`
5. `RejectedDashRollsBackWithoutCost`

L2I has a fixed denominator of exactly four checks.

1. `DashUsesCustomSavedMove` - client prediction data allocates a custom
   `FSavedMove_Character` that records/compresses the dash request.
2. `DashUsesCharacterNetworkMoveData` - request direction/nonce required by
   authority travels through custom CharacterMovement network move data and
   server validation, not a transform RPC.
3. `AcceptedAccountingIsAuthorityOwned` - energy/cooldown mutation is reachable
   only from the authoritative accepted path and replicates outward.
4. `SubmissionHasNoTransformReplicationShortcut` - accepted files are the exact
   component pair and contain no transform multicast, client-authoritative state,
   map/config/character edit, or extra implementation surface.

Harness preconditions pin all roles, actor/network IDs, packet profile, movement
mode, ground, finite transforms, input epoch, server policy, correction channel,
and telemetry completeness. A missing role or correction is infrastructure.

## Reference solution metadata

- Native reference LOC: within the planned 260-420 range across the two files.
- Assets edited by the reference: 0.
- Senior developer estimate: 20-32 hours after the network harness is certified.

## Anti-gaming notes

1. Server-only launch fails pre-acknowledgement owner response.
2. Client-only launch fails convergence and simulated-proxy evidence.
3. Transform RPC/multicast fails SavedMove/move-data introspection and correction.
4. Double-sided spending fails exact authoritative revision/delta.
5. Client-declared acceptance fails server hidden policy reversal.
6. Always accepting fails rejected rollback/no-cost policy.
7. Cosmetic animation or telemetry flags cannot create role-qualified movement.
8. Hardcoded direction/cost fails the alternate fixture and request values.

## Hidden invariants

- Direction, magnitude, delay, packet loss, starting energy, cooldown, request
  nonce, and accept/reject policy vary by fixture/run.
- Accepted and rejected requests share plausible client-side inputs; only server
  policy distinguishes them.
- Owner response is compared with server acknowledgement using synchronized
  verifier epochs and sequence IDs, not cross-machine wall clock.
- Convergence requires bounded positional/velocity error over a retained window,
  not a single crossing sample.
- Cost/cooldown use authoritative revision numbers so duplicate prediction,
  replay, and correction cannot be counted as additional applications.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
