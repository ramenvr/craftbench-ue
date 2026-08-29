// Gaming variant "no-animation" for t2-weapon-fire-animation-on-trigger:
// the seam exists (the empty-leg gate passes) but firing plays nothing.
// Expected death: checkpoint 1 — "no firing animation started".

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

	/** Requests one firing animation. Parameterless + reflected, per the
	 *  project's Do* input-seam convention. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	void DoFireStart();

private:
	/** The one-shot clip the fire plays (wired in the constructor). */
	UPROPERTY(EditAnywhere, Category = "Combat")
	TObjectPtr<UAnimSequence> FireClip;
};
