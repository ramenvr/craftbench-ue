// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT stops-forever-on-remove (anti-gaming note #4, the
// stop-forever hack): the HasTag gate is intact, but RemoveGateTag also tears
// the looping timer down and AddGateTag never restarts it. Emission stops
// correctly when the marker is removed (checkpoint 1 passes) and then never
// resumes when it is re-added, so the FIRST gate this reaches is checkpoint
// 2's resume band.

#include "TagGateActor.h"

#include "Engine/World.h"
#include "TimerManager.h"

UE_DEFINE_GAMEPLAY_TAG_COMMENT(TAG_CraftBench_TagGate_Active, "CraftBench.TagGate.Active",
	"State marker that gates the repeating announcement for task t1-gameplay-tag-gate.");

ATagGateActor::ATagGateActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("TagGateRoot"));
}

void ATagGateActor::BeginPlay()
{
	Super::BeginPlay();

	// The marker is present at gameplay start.
	StateMarkers.AddTag(TAG_CraftBench_TagGate_Active);

	// FTimerManager ticks for real in PIE; 0.5 s looping, first fire at 0.5 s.
	GetWorldTimerManager().SetTimer(
		GateTickTimer, this, &ATagGateActor::HandleGateTick, 0.5f, /*bLoop=*/true);
}

void ATagGateActor::HandleGateTick()
{
	if (StateMarkers.HasTag(TAG_CraftBench_TagGate_Active))
	{
		UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_TAG_GATE_TICK"));
	}
}

void ATagGateActor::AddGateTag(FGameplayTag Tag)
{
	StateMarkers.AddTag(Tag);
}

void ATagGateActor::RemoveGateTag(FGameplayTag Tag)
{
	StateMarkers.RemoveTag(Tag);
	// VARIANT DELTA: tear the looping timer down on removal (a plausible
	// "clean up the timer" instinct). AddGateTag re-adds only the marker, so
	// nothing ever restarts the timer and emission never resumes.
	GetWorldTimerManager().ClearTimer(GateTickTimer);
}
