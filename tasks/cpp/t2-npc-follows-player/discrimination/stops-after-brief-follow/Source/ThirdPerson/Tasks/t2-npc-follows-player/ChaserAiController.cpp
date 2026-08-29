// GAMING VARIANT (stops-after-brief-follow). See header.

#include "ChaserAiController.h"

#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

void AChaserAiController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	GetWorldTimerManager().SetTimer(
		ChaseTimer, this, &AChaserAiController::IssueChase, 0.5f, /*bLoop=*/true, /*FirstDelay=*/0.0f);
	// Give up for good at 3.0s — after the chase has visibly closed most of
	// the gap, before the player ever moves.
	GetWorldTimerManager().SetTimer(
		GiveUpTimer, this, &AChaserAiController::GiveUp, 3.0f, /*bLoop=*/false);
}

void AChaserAiController::OnUnPossess()
{
	GetWorldTimerManager().ClearTimer(ChaseTimer);
	GetWorldTimerManager().ClearTimer(GiveUpTimer);
	Super::OnUnPossess();
}

void AChaserAiController::IssueChase()
{
	if (ACharacter* Player = UGameplayStatics::GetPlayerCharacter(this, 0))
	{
		MoveToActor(Player, /*AcceptanceRadius=*/100.0f);
	}
}

void AChaserAiController::GiveUp()
{
	GetWorldTimerManager().ClearTimer(ChaseTimer);
	StopMovement();
}
