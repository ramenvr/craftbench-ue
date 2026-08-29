// GAMING VARIANT (stops-after-brief-follow): a genuine chase that gives up
// for good after three seconds — enough to look alive on any early sample,
// never following again. A casual manual test ("it came at me!") passes; a
// player who then moves elsewhere is never pursued.

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
	void GiveUp();

	FTimerHandle ChaseTimer;
	FTimerHandle GiveUpTimer;
};
