// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-screen-tint.
//
// The vignette follows how fast the character is ACTUALLY moving, as a fraction of the
// top speed it has RIGHT NOW -- both read off the character every frame, so neither is
// a number written down here that could go stale when the yard changes one of them.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ScreenTintActor.generated.h"

class UPostProcessComponent;

UCLASS()
class THIRDPERSON_API AScreenTintActor : public AActor
{
	GENERATED_BODY()

public:
	AScreenTintActor();

	/** Unbound, so it applies wherever the character is standing. Its Settings are a
	 *  plain public struct: read them, write them, nothing here gets in the way. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Screen Tint")
	UPostProcessComponent* Screen = nullptr;

	/** What the vignette reads when nothing is happening. Supplied. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Screen Tint")
	float RestVignette = 0.0f;

	/** What the vignette reads when the character is going flat out. Supplied. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Screen Tint")
	float FullVignette = 0.9f;

	/** The OTHER setting. Supplied at this value and not part of the task; it must
	 *  still read this at every checkpoint. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Screen Tint")
	float SuppliedFringe = 0.6f;

	/** Reads the vignette back off the component, for anyone who wants it. */
	UFUNCTION(BlueprintPure, Category = "Screen Tint")
	float CurrentVignette() const;

	/** Sets the vignette on the component. THE SUPPLIED SWITCH -- nothing calls it. */
	UFUNCTION(BlueprintCallable, Category = "Screen Tint")
	void SetVignette(float NewVignette);

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
};
