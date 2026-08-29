// Reference solution for task t2-npc-follows-player.
//
// AChaserAiController — minimal chasing brain: on possession it starts a
// half-second re-issue loop that MoveToActor()s the current player character.
// Re-issuing (rather than trusting one long-lived move request) keeps the
// chase honest through the player being relocated wholesale: every half
// second the goal is re-read from the live world.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "ChaserAiController.generated.h"

UCLASS()
class THIRDPERSON_API AChaserAiController : public AAIController
{
	GENERATED_BODY()

protected:
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;

private:
	void IssueChase();

	FTimerHandle ChaseTimer;
};
