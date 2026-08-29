// Reference solution for task gp-crafting-queue (the g2-5 "Crafting queue" port).
// Implements strict one-at-a-time FIFO crafting on the pre-existing
// ACraftQueueActor:
//   (1) BeginPlay enqueues four string-named actions and starts a repeating
//       ~1s FTimerManager timer — the "Timers" concept the prompt probes. No
//       Tick is used for the processing logic.
//   (2) Each timer fire dequeues the front action (FIFO, one per second) and
//       spawns one marker actor tagged "CraftCompleted" so the verifier can
//       count completions in order.
//   (3) When the queue empties the repeating timer is cleared so no extra
//       markers are spawned.

#include "CraftQueueActor.h"

#include "Engine/World.h"
#include "TimerManager.h"

ACraftQueueActor::ACraftQueueActor()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("CraftQueueRoot"));
}

void ACraftQueueActor::BeginPlay()
{
	Super::BeginPlay();

	// Queue exactly four named crafting actions (FIFO order of processing).
	CraftQueue.Reset();
	CraftQueue.Add(TEXT("Sword"));
	CraftQueue.Add(TEXT("Shield"));
	CraftQueue.Add(TEXT("Potion"));
	CraftQueue.Add(TEXT("Helmet"));

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	// VARIANT DELTA (burst-all-at-once): drain the whole queue inside BeginPlay
	// instead of pacing it. Every action IS processed, in the right FIFO order,
	// and the final count IS four — only the "one at a time" pacing is missing.
	// This is the shape of a submission that read the queue as a batch to flush.
	while (CraftQueue.Num() > 0)
	{
		ProcessNextCraft();
	}
}

void ACraftQueueActor::ProcessNextCraft()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	if (CraftQueue.Num() == 0)
	{
		// Queue drained — stop the repeating timer so nothing else is spawned.
		World->GetTimerManager().ClearTimer(ProcessTimerHandle);
		return;
	}

	// Dequeue the front action (strict FIFO, one at a time).
	const FString CompletedAction = CraftQueue[0];
	CraftQueue.RemoveAt(0);

	// Make the completion world-observable: spawn one marker actor tagged
	// "CraftCompleted" at this actor's location.
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* Marker = World->SpawnActor<AActor>(
		AActor::StaticClass(), GetActorLocation(), FRotator::ZeroRotator, Params);
	if (Marker != nullptr)
	{
		Marker->Tags.Add(FName("CraftCompleted"));
	}

	// If that was the last action, clear the repeating timer now so it does not
	// fire again on an empty queue.
	if (CraftQueue.Num() == 0)
	{
		World->GetTimerManager().ClearTimer(ProcessTimerHandle);
	}
}
