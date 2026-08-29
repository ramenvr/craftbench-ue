// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT "teleport-to-top" for task t2-ladder-climb-volume.
// Models anti-gaming note #3: the volume gate is honored (the away-side probe
// passes), but "climbing" is a one-frame snap to the ladder's top instead of
// a steady ascent. Expected verdict: FAIL at the fixture's per-frame
// ascent-continuity guard via "ascent jumped discontinuously".

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

	UFUNCTION(BlueprintCallable, Category = "Climb")
	void DoClimbStart();

	UFUNCTION(BlueprintCallable, Category = "Climb")
	void DoClimbEnd();

private:
	/** The ladder actor the character currently overlaps, else nullptr. */
	AActor* FindLadder() const;
};
