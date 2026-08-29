// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT unconditional-emission (anti-gaming note #1): the
// looping timer emits on EVERY fire and never consults the marker set - the
// actor reacts to its own timer lifecycle instead of the state marker.
// The accessors still mutate the container (so both prepare-time reflection
// checks pass) and the 0.5 s period still satisfies checkpoint 0, so the
// FIRST gate this reaches is checkpoint 1's stop-on-remove assertion.

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
	// VARIANT DELTA: the marker set is never queried, so an external
	// RemoveGateTag cannot stop the line.
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_TAG_GATE_TICK"));
}

void ATagGateActor::AddGateTag(FGameplayTag Tag)
{
	StateMarkers.AddTag(Tag);
}

void ATagGateActor::RemoveGateTag(FGameplayTag Tag)
{
	StateMarkers.RemoveTag(Tag);
}
