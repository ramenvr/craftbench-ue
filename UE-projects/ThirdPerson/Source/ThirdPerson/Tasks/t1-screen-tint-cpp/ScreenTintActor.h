// Copyright CraftBench. All Rights Reserved.
//
// The screen effect for task t1-screen-tint-cpp. Everything needed to SHOW
// something is supplied and working: an unbound post-process component that covers the
// whole level, with two settings already overridden and already visible. Nothing
// drives either of them.
//
// One of the two is the readout the task is about. The other is supplied at a fixed
// value and must still read that value at the end of the run.

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
};
