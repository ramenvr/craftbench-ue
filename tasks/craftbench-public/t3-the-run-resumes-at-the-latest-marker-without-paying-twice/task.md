---
id: t3-the-run-resumes-at-the-latest-marker-without-paying-twice
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_LatestMarkerResume :: ALatestMarkerWriteFunctionalTest", "L_LatestMarkerResume :: ALatestMarkerResumeFunctionalTest"]
introspect: [t3_latest_marker_resume.py]
deadline_s: 2400
action_budget: 70
accepted_files: [Source/ThirdPerson/Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/RunResumePersistenceComponent.h, Source/ThirdPerson/Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/RunResumePersistenceComponent.cpp]
---

# t3-the-run-resumes-at-the-latest-marker-without-paying-twice

> **AUTHORED / TWO-PROCESS VERIFIED.** The retained map, protected SaveGame
> schema, exact-two-process L2 adapter, fixed L2I, reference overlay, and
> answer-free discrimination control are authored. A same-process travel/reload
> or Python object carried between legs is not an admissible substitute.

Resume the run at its latest marker without paying twice

## Primary concept

- `saving-and-loading-your-game` - Saving and Loading Your Game

### Composed concepts

- `ps-actors` - checkpoint and reward actor lifecycle
- `player-controllers` - normal spawn, possession, and restored player placement
- `ps-components` - player-owned persistence component

### Production-pattern justification

Checkpoint games must persist more than a transform. The save record needs the
latest checkpoint identity, the exact collected-reward set, and the authoritative
total, and a new process must rebuild world state from that record. Otherwise a
reload can duplicate rewards, resurrect collected pickups, or resume at an older
marker while appearing correct in one process.

### Concept-interaction notes

The protected world supplies checkpoint IDs/transforms, reward IDs/values,
collection order, one uncollected control, and a verifier nonce-scoped slot. The
submitted component receives those facts through protected calls. A write process
creates the slot and exits; a separately launched resume process reads it and
proves player placement, score, retired rewards, and the live control together.

## Prompt given to the agent

> Complete the supplied persistence component. Whenever the player reaches a
> supplied checkpoint or collects a supplied reward, save the latest checkpoint
> identity and transform, the exact set of collected reward identities, and the
> authoritative reward total to the supplied slot. In a fresh run, load that slot,
> restore the player at the latest checkpoint, keep collected rewards retired, and
> allow each still-uncollected reward to pay exactly once.
>
> The level changes slot name, checkpoint IDs and transforms, reward identities,
> values, and collection order. Use the supplied values and real SaveGame slot;
> do not use GameInstance memory, process statics, fixed totals, actor-name scans,
> or a hardcoded transform.
>
> Edit only `RunResumePersistenceComponent.h` and
> `RunResumePersistenceComponent.cpp` under
> `Source/ThirdPerson/Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/`.
> Do not edit the supplied SaveGame schema, actors, map, tests, project settings,
> verifier source, or any other runtime file.

## Workspace state pre-task

- Editable files: exactly the supplied
  `RunResumePersistenceComponent.h/.cpp` pair. They compile and expose the
  protected request surface but contain no save, load, restore, or retirement
  behavior.
- Protected schema: `URunResumeSaveGame`, with fields for schema version,
  run nonce, latest checkpoint ID/transform, collected reward IDs, and total.
- Protected retained map:
  `Content/Maps/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/L_LatestMarkerResume.umap`.
- The map contains a visible playable subject, two checkpoints, three rewards,
  a PlayerStart, and both verifier fixture classes. Only one fixture runs in a
  given process.
- The canonical L2 adapter launches the committed host-side protocol runner;
  that runner, not the submission, chooses and cleans the exact slot name.

## Verifier specification

This is the certified aggregate L2 contract.

L1 builds `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64
Development`, requires exactly the editable source pair in the accepted-files
manifest, and rejects changes to schema, map, fixture, config, or other source.

L2 is one aggregate result assembled from two independently launched fixed-60-Hz
NullRHI game processes using one immutable `protocol.json` and one nonce-scoped
SaveGame slot.

### Write process

The runner proves the slot absent, launches only
`ALatestMarkerWriteFunctionalTest`, and provides the nonce/slot through a
verifier-owned environment/config seam established before process startup. The
fixture possesses the visible player, reaches the first checkpoint, collects a
reward, reaches the later checkpoint, collects another reward, and leaves one
control untouched. It validates the live total and exact actor lifecycle, loads
the saved slot through `UGameplayStatics::LoadGameFromSlot`, emits the protected
record facts, and exits cleanly.

The runner then records only process evidence and the slot file hash/size. It
must discard the first UE process completely before launching the resume leg.

### Resume process

A new UE process runs only `ALatestMarkerResumeFunctionalTest` with the same
immutable protocol and slot name. Before candidate callbacks it pins a newly
spawned/possessed player and fresh map actors. It then observes the component's
ordinary load/restore path, exact checkpoint transform, score, collected reward
retirement, and uncollected control. Attempts to collect retired rewards must not
change the total; the control must remain visible and increase the total exactly
once by its supplied value.

Fixed aggregate L2 denominator: exactly seven named gates.

1. `FreshNonceScopedSlotBeginsEmpty`
2. `NewestCheckpointRecordIsSerialized`
3. `CollectedRewardIdentitySetIsSerialized`
4. `ResumeUsesLatestMarkerTransform`
5. `RewardTotalRestoresExactly`
6. `AlreadyCollectedRewardsDoNotPayTwice`
7. `UncollectedControlStillPaysOnce`

L2I has a fixed denominator of exactly three checks.

1. `UsesSuppliedSaveGameSchema` - save/load calls operate on the supplied slot
   and exact `URunResumeSaveGame` fields; no parallel candidate schema exists.
2. `PersistsIdentitySetAndAuthoritativeTotal` - collected IDs, latest checkpoint,
   and total all flow from supplied request data into the saved object and back
   into restore/retirement behavior.
3. `SubmissionHasNoInProcessPersistenceSubstitute` - accepted files are exactly
   the component pair and contain no mutable process static, GameInstance-owned
   cache, hardcoded slot/facts, map, config, schema, or fixture edit.

The L2 result exists only if both processes emit authoritative JSON for their
exact test path and the aggregate audit validates slot lifecycle, nonces, hashes,
timestamps, exit state, and all seven gates. Infrastructure failure is never
reinterpreted as a graded candidate failure.

## Reference solution metadata

- Native LOC: 185 across the two editable files (118 implementation, 67 public
  surface; the header intentionally matches the supplied scaffold).
- Assets edited by the solution: 0.
- Retained verifier map: one 53,700-byte `.umap`; the solution overlay contains
  only the accepted source pair.
- Certified evidence: L1 Editor/Game PASS, two-process L2 7/7 PASS, L2I 3/3
  PASS, and answer-free L1 PASS followed by named
  `NewestCheckpointRecordIsSerialized` FAIL.

## Anti-gaming notes

1. GameInstance or static memory disappears with the write process.
2. Saving only a transform fails checkpoint identity/schema and reward retirement.
3. A fixed total fails changed values and collection order.
4. Rebuilding collected IDs from a fixed list fails nonce-scoped hidden facts.
5. Destroying every reward fails the uncollected live control.
6. Hiding rewards without persisted identity fails fresh actor lifecycle and
   post-resume collection attempts.
7. Loading an arbitrary or hardcoded slot fails exact nonce/slot evidence.
8. Teleporting an old player object is impossible because the resume player and
   process identities are new and pinned.

## Hidden invariants

- Every run uses a unique high-entropy nonce and slot name under a fresh output
  root; stale slots are a harness error.
- Checkpoint order, transforms, reward IDs, values, and collection order vary.
- The latest checkpoint is not the checkpoint with the lexically greatest ID or
  largest coordinate.
- Collected rewards include non-contiguous identities; one otherwise equivalent
  reward remains uncollected.
- The runner deletes only its exact nonce-scoped slot after retaining evidence.
  Cleanup failure is reported and never broadened to other save files.
- No Python object from the write leg supplies gameplay state to the resume leg;
  only immutable fixture policy and the engine SaveGame slot cross the boundary.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
