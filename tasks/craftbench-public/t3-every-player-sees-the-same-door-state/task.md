---
id: t3-every-player-sees-the-same-door-state
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_ReplicatedDoorState :: AReplicatedDoorNetworkFunctionalTest"]
introspect: [t3_replicated_door_state.py]
deadline_s: 2400
action_budget: 65
accepted_files: [Content/Tasks/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState.uasset]
---

# t3-every-player-sees-the-same-door-state

Make every player see the same authoritative door state

## Primary concept

- `net-replicate-properties` - property replication and RepNotify

### Composed concepts

- `net-rpc` - owning-client request to server authority
- `net-actor-role` - authority, autonomous requester, and remote proxies
- `net-basics` - replicated actor lifecycle and late join

### Production-pattern justification

A persistent multiplayer door needs one server-owned state replicated to every
peer. A multicast or local animation can look correct to current clients but has
no durable value for late joiners. This task couples request authority, replicated
state, RepNotify application, and join-time actor initialization.

### Concept-interaction notes

The protected server fixture changes requesting client, toggle order, target
transform, join time, and actor identity. Server and each client independently
observe role, replicated state revision, and visible door transform. A unified
runner joins those streams by protected run nonce, peer ID, and actor NetGUID.

## Prompt given to the agent

> Complete the supplied replicated Door Blueprint. When either owning player
> requests a toggle, route that request to server authority. The server must
> change one replicated door state, and every current client must apply that
> state to the supplied target transform. A client joining later must immediately
> receive and display the current state. A second requester must toggle the same
> authoritative state for everyone.
>
> The verifier changes requester, closed/open transforms, toggle order, join
> time, and door identity. Do not change the door locally first, let clients own
> authoritative state, multicast only a transform animation, hardcode a player,
> or use candidate-authored logs as synchronization.
>
> Edit only
> `Content/Tasks/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState`.
> Do not edit the level, native base, player classes, networking settings, tests,
> server policy, target transforms, or any other asset.

## Workspace state pre-task

- Planned editable inventory: exactly one compiled Blueprint child of the
  supplied replicated-door base.
- Planned protected map:
  `Content/Maps/t3-every-player-sees-the-same-door-state/L_ReplicatedDoorState.umap`.
- The protected native base exposes player-owned request entry, server-observed
  state/transform probes, and fixture hooks but no toggle solution.
- Server and clients receive the same replicated door actor identity. The late
  client is launched only after the first authoritative revision settles.
- The baseline Blueprint contains the declared interface surfaces but no
  executable RPC/RepNotify behavior.

## Verifier specification

L1 builds Editor and Game, loads the exact Blueprint, verifies immediate native
parent and one-file inventory, and rejects submitted map/config/source/player/
alternate-door packages.

L2 is one aggregate result across a dedicated server, two initial clients, and
one late client. All peers use one immutable nonce policy and fixed-60-Hz world
clock. The server fixture owns the schedule; clients only execute peer-qualified
requests and observations. No verifier manually ticks networking, world, actors,
or replication.

The first selected client requests a toggle. Before the server revision, the
requester must not establish an authoritative local state. The server applies
exactly one revision and all initial peers converge on the supplied transform.
The runner then launches a third client, pins the same actor NetGUID/state
revision, and requires immediate convergence without a new toggle. Finally the
other initial client requests the reverse transition and every peer converges on
the next server revision.

Fixed L2 denominator: exactly four named gates.

1. `RequesterCannotChangeDoorLocally`
2. `ServerStateConvergesOnEveryPeer`
3. `LateJoinerReceivesCurrentDoorState`
4. `SecondRequesterTogglesSameAuthorityState`

L2I has a fixed denominator of exactly three checks.

1. `ClientRequestUsesServerRPC` - the reachable request path enters an exact
   server RPC and state mutation occurs only on authority.
2. `DoorStateReplicatesThroughNotify` - one replicated state/revision property
   with RepNotify drives the supplied transform on server and clients.
3. `SubmissionHasNoEphemeralReplicationSubstitute` - the exact one-file graph
   contains no transform multicast-only answer, local-player literal, candidate
   network manager, map/config edit, or extra asset.

Harness preconditions pin peer count/roles, server ownership, actor NetGUID,
replication relevancy, requester ownership, packet flow, and late-join completion.
Any failure there is infrastructure, not a candidate verdict.

## Reference solution metadata

- Candidate native LOC: 0.
- Assets edited: exactly 1 Blueprint.
- Expected graph size: approximately 20-36 nodes.
- Senior developer estimate: 12-20 hours after multi-peer harness admission.

## Anti-gaming notes

1. Local transform changes fail the pre-server requester negative control.
2. Client authority fails server state/revision ownership.
3. Multicast-only animation fails the late join snapshot.
4. Per-client door copies fail shared NetGUID and revision convergence.
5. Hardcoded requester fails reversed policy.
6. Polling another actor's candidate-authored Boolean fails exact replicated
   property/notify introspection.
7. Candidate logs cannot satisfy peer state or transform probes.

## Hidden invariants

- Requester, toggle order, transforms, join checkpoint, peer IDs, and door token
  vary per run.
- Open and closed transforms are not fixed offsets and may reverse direction.
- The late client joins after server revision one but before revision two.
- Each observation is qualified by nonce, process, connection, local role,
  server revision, actor NetGUID, and finite transform.
- No client report is accepted until the server report pins the same revision;
  wall-clock ordering alone is never authoritative.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
