// Copyright CraftBench. All Rights Reserved.
//
// A figure that walks the lane for task t1-mud-wade-cpp. It
// arrives visible, animated by the ordinary walk, and moving at its normal top speed.
// Nothing about the mud is built: it walks straight through the patch unchanged.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "MudHeroCharacter.generated.h"

class UAnimInstance;
class UAnimSequenceBase;

UCLASS()
class THIRDPERSON_API AMudHeroCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AMudHeroCharacter();

	/** The supplied heavy wade. Loaded here so it is always resolvable; nothing
	 *  plays it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mud")
	UAnimSequenceBase* WadeMotion = nullptr;

	/** The figure's normal top speed, in units per second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mud")
	float NormalTopSpeed = 500.0f;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** True while this figure is standing on the tagged patch. */
	bool IsOnMud() const;

	void EnterMud();
	void LeaveMud();

	bool bWading = false;
	/** The animation blueprint the figure walks with when it is not wading. */
	TSubclassOf<UAnimInstance> OrdinaryWalkClass;
};
