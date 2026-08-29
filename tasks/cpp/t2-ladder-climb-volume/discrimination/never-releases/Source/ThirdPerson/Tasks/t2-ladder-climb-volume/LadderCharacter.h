// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT "never-releases" for task t2-ladder-climb-volume.
// Models anti-gaming note #4: entry is volume-gated and DoClimbEnd holds
// correctly, but leaving the ladder's reach never ends the climb — the
// character keeps ascending into the sky past the ladder's top. Expected
// verdict: FAIL at checkpoint 4 via "still ascending or hovering after
// leaving the ladder".

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
	bool IsAtLadder() const;

	static constexpr float ClimbSpeed = 300.0f;

	bool bClimbRequested = false;
	bool bClimbingMode = false;
};
