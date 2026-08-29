// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT "climb-anywhere" for task t2-ladder-climb-volume.
// Models anti-gaming note #2: the climb seams work but are NOT gated on the
// ladder volume — a climb request ascends anywhere on the map. Expected
// verdict: FAIL at checkpoint 1 via "climb engaged away from the ladder" (the
// fixture's away-side probe rises when it must not).

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "LadderCharacter.generated.h"

UCLASS()
class THIRDPERSON_API ALadderCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ALadderCharacter();

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category = "Climb")
	void DoClimbStart();

	UFUNCTION(BlueprintCallable, Category = "Climb")
	void DoClimbEnd();

private:
	static constexpr float ClimbSpeed = 300.0f;

	bool bClimbRequested = false;
	bool bClimbingMode = false;
};
