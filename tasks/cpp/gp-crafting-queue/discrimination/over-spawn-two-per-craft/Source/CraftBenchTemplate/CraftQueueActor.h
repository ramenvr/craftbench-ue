// Reference solution for task gp-crafting-queue (the g2-5 "Crafting queue" port).
// Keeps the substrate constructor (tick enabled + the CraftQueueRoot tag the
// verifier resolves the host by) and adds the agent's responsibility:
//   - BeginPlay enqueues four named (string) crafting actions and starts a
//     repeating ~1s FTimerManager timer (NO tick is used for the logic);
//   - each timer fire dequeues the front action (strict FIFO, one at a time) and
//     spawns one marker actor tagged "CraftCompleted" for it;
//   - once the queue empties, the repeating timer is cleared.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CraftQueueActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ACraftQueueActor : public AActor
{
	GENERATED_BODY()

public:
	ACraftQueueActor();

	virtual void BeginPlay() override;

private:
	/** Timer handler: completes the front queued action, then advances FIFO. */
	void ProcessNextCraft();

	/** FIFO queue of crafting actions; each action is just a string name. */
	TArray<FString> CraftQueue;

	/** Handle for the repeating ~1s processing timer. */
	FTimerHandle ProcessTimerHandle;

	/** Seconds each crafting action takes to complete. */
	static constexpr float CraftDuration = 1.0f;
};
