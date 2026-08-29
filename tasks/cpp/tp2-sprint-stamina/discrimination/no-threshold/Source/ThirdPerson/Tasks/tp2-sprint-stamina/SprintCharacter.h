// GAMING VARIANT (anti-gaming note #3): full drain/regen/auto-stop, but the
// re-sprint floor is missing — a request succeeds whenever stamina > 0.
// Expected: PASSES cp0-cp2, FAILS cp3 ("below-threshold sprint request").

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

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category="Sprint")
	void DoSprintStart();

	UFUNCTION(BlueprintCallable, Category="Sprint")
	void DoSprintEnd();

private:
	float Stamina = 100.f;
	bool bSprinting = false;
	float BaseMaxWalkSpeed = 0.f;
};
