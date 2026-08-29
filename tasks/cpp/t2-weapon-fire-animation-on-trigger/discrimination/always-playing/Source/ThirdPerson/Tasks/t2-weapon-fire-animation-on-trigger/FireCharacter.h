// Gaming variant "always-playing" for t2-weapon-fire-animation-on-trigger:
// a firing-looking animation loops from BeginPlay, fire request or not.
// Expected death: checkpoint 0 — "already playing before any fire request".

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "FireCharacter.generated.h"

class UAnimSequence;

UCLASS()
class THIRDPERSON_API AFireCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AFireCharacter();

	UFUNCTION(BlueprintCallable, Category = "Combat")
	void DoFireStart();

protected:
	virtual void BeginPlay() override;

private:
	UPROPERTY(EditAnywhere, Category = "Combat")
	TObjectPtr<UAnimSequence> FireClip;
};
