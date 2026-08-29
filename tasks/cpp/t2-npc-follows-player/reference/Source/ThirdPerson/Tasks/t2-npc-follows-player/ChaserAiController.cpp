// Reference solution for task t2-npc-follows-player. See ChaserAiController.h.

#include "ChaserAiController.h"

#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

void AChaserAiController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	// Re-read the player and re-issue the chase every half second. MoveToActor
	// tracks a moving goal on its own; the periodic re-issue additionally
	// covers a goal that was relocated wholesale (or an aborted/finished
	// request) without any per-tick work.
	GetWorldTimerManager().SetTimer(
		ChaseTimer, this, &AChaserAiController::IssueChase, 0.5f, /*bLoop=*/true, /*FirstDelay=*/0.0f);
}

void AChaserAiController::OnUnPossess()
{
	GetWorldTimerManager().ClearTimer(ChaseTimer);
	Super::OnUnPossess();
}

void AChaserAiController::IssueChase()
{
	if (ACharacter* Player = UGameplayStatics::GetPlayerCharacter(this, 0))
	{
		MoveToActor(Player, /*AcceptanceRadius=*/100.0f);
	}
}
