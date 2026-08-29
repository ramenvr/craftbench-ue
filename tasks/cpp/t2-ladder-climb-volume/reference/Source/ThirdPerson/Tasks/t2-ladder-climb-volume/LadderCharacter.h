// Copyright CraftBench. All Rights Reserved.
//
// ALadderCharacter — reference solution for task t2-ladder-climb-volume.
// Climb requests arm a flag; climbing runs only while the character is inside
// the ladder volume's reach, ascends at a steady rate, holds height when the
// climb is ended mid-ladder, and hands back to normal falling the moment the
// character leaves the ladder's reach (which also clears the request).

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

	/** Requests a climb. Ignored (and not retained) unless the character is
	 *  currently at the ladder. */
	UFUNCTION(BlueprintCallable, Category = "Climb")
	void DoClimbStart();

	/** Ends a climb request; a climber mid-ladder holds its height. */
	UFUNCTION(BlueprintCallable, Category = "Climb")
	void DoClimbEnd();

private:
	/** True while the character overlaps the ladder's marked reach. */
	bool IsAtLadder() const;

	/** Steady climb rate, units per second (the disclosed contract value). */
	static constexpr float ClimbSpeed = 300.0f;

	bool bClimbRequested = false;
	bool bClimbingMode = false;
};
