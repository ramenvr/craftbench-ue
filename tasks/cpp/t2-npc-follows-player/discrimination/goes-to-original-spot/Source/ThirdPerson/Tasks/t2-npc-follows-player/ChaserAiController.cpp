// GAMING VARIANT (goes-to-original-spot). See header.

#include "ChaserAiController.h"

#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

void AChaserAiController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
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
	if (!bSpotCached)
	{
		if (ACharacter* Player = UGameplayStatics::GetPlayerCharacter(this, 0))
		{
			CachedSpot = Player->GetActorLocation();
			bSpotCached = true;
		}
	}
	if (bSpotCached)
	{
		MoveToLocation(CachedSpot, /*AcceptanceRadius=*/100.0f);
	}
}
