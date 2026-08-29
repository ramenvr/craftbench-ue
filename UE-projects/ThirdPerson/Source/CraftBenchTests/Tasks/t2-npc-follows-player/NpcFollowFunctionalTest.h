// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ANpcFollowFunctionalTest — L2 verifier fixture for task
// t2-npc-follows-player. Lives at
// Source/CraftBenchTests/Tasks/t2-npc-follows-player/. Placed in
// Content/Maps/t2-npc-follows-player/L_NpcFollow.umap alongside the
// "ChaserNpc"-tagged enemy character; the map's game mode (AFollowGameMode)
// spawns and possesses the "FollowHero"-tagged player character at the
// PlayerStart, so a real player pawn exists for the agent's NPC code to find.
//
// PIE-native: the engine ticks this fixture. The fixture only READS the NPC
// (positions, per-frame displacement) and MOVES the player — it relocates the
// hero once to a fixture-chosen spot mid-run and then drives it briefly with
// per-frame AddMovementInput (input is consumed per frame; never tick the
// world), so "keeps following the player" is graded against a target that
// genuinely moved twice: a big discontinuous relocation and a short walked
// leg. A solution that memorized the player's starting location, or re-read
// it exactly once when the relocation happened, ends short of the player's
// final position and fails the re-acquisition gate.
//
// Checkpoint contract (world game-time; NPC authored ~1,615uu from the
// PlayerStart):
//   t=1.0 — both actors resolved; NPC still far from the player (a solution
//           that starts the NPC on top of the player fails here); arm the
//           continuity guard; record D0
//   t=4.0 — NPC-to-player distance shrank below 55% of D0 (the follow gate);
//           then relocate the hero to the fixture-chosen far spot and start
//           driving it away
//   t=5.0 — stop driving the hero (it walked ~500uu from the relocation spot)
//   t=9.5 — NPC is within the re-acquisition tolerance of the player's
//           CURRENT position -> PASS
// From cp0 on, Tick runs a CONTINUOUS per-frame displacement guard on the
// NPC: a single-frame step larger than any legitimate walk step means the
// NPC was teleported, and the test FAILs immediately — no sampling window to
// thread. All FAIL message text is ASCII-only (the cp1252 log read-back
// rule). The FinishTest(Error) precondition paths carry a
// "HARNESS-PRECONDITION: " prefix — today they still GRADE as a FAIL
// (automation Error lands as state Fail in index.json); the prefix is the
// hook for a future runner-side routing rule.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "NpcFollowFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class CRAFTBENCHTESTS_API ANpcFollowFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ANpcFollowFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

	/** Runs the NPC continuity guard FIRST (so the frame that crosses the
	 *  final checkpoint is still covered), then chains the base checkpoint
	 *  clock, then sustains the hero's escape walk while driving. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Shared per-checkpoint guard: both actors still valid. Returns false
	 *  after raising the named FAIL. */
	bool GuardActors(int32 CheckpointIndex);

	/** 2D distance from the NPC to the player's current position. */
	double DistanceNpcToHero() const;

	TWeakObjectPtr<AActor> Npc;
	TWeakObjectPtr<ACharacter> Hero;

	/** NPC-to-player distance recorded at cp0; cp1's follow gate is a ratio
	 *  of this run-measured baseline, never an absolute. */
	double StartDistance = 0.0;

	/** Continuity guard state: last observed NPC position, valid once armed
	 *  at cp0 (dodges spawn/settle noise before the first checkpoint). */
	FVector LastNpcPos = FVector::ZeroVector;
	bool bGuardArmed = false;

	bool bDrivingHero = false;
};
