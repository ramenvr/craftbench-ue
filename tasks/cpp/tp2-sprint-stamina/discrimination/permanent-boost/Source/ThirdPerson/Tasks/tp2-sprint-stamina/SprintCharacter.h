// GAMING VARIANT (anti-gaming note #2): both seams exist, but DoSprintStart
// applies a permanent 1.7x boost — no stamina, nothing ever reverts it.
// Expected: PASSES cp0/cp1, FAILS cp2 ("after stamina exhaustion").

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "SprintCharacter.generated.h"

UCLASS()
class THIRDPERSON_API ASprintCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ASprintCharacter();

	UFUNCTION(BlueprintCallable, Category="Sprint")
	void DoSprintStart();

	UFUNCTION(BlueprintCallable, Category="Sprint")
	void DoSprintEnd();
};
