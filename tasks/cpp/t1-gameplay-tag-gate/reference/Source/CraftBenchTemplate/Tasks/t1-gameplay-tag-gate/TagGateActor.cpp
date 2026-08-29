// Copyright CraftBench. All Rights Reserved.
//
// ATagGateActor reference implementation for task t1-gameplay-tag-gate.
// One container, one HasTag query, one looping timer:
//   - BeginPlay adds the gate marker (present at gameplay start, per the
//     prompt) and starts a 0.5 s looping timer (first fire at 0.5 s — inside
//     the prompt's 0.6 s first-line window).
//   - Each fire emits CRAFTBENCH_TAG_GATE_TICK on LogTemp/Display only while
//     the marker is present, so an external remove stops the very next fire
//     and a re-add resumes within one period (0.5 s <= 0.6 s window).

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
}
