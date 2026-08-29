// Gaming variant "frozen-animation" for t2-weapon-fire-animation-on-trigger:
// the fire request starts a montage and immediately pauses it — "a montage is
// active" is true, but nothing plays.
// Expected death: checkpoint 2 — "frozen, not playing".

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
