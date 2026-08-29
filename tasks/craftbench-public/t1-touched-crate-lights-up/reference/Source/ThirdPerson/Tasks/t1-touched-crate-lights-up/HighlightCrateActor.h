// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-touched-crate-lights-up.
//
// Each crate answers for ITSELF, from its OWN NoticeRadiusUu. Nothing here knows there
// are two crates, which is exactly why the yard swapping their places and giving them
// different reaches costs this solution nothing.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HighlightCrateActor.generated.h"

class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AHighlightCrateActor : public AActor
{
	GENERATED_BODY()

public:
	AHighlightCrateActor();

	/** The crate you can see. Solid: it is a prop, and it blocks. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	UStaticMeshComponent* Body = nullptr;

	/** Off when the crate has not noticed anybody, bright when it has. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	UPointLightComponent* Lamp = nullptr;

	/** How close somebody has to be before THIS crate notices them. Read it off the
	 *  crate: the two crates in the yard are not set to the same value. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Crate")
	float NoticeRadiusUu = 300.0f;

	/** THE SWITCH. Lights the crate up or puts it out. */
	UFUNCTION(BlueprintCallable, Category = "Crate")
	void SetHighlighted(bool bNewHighlighted);

	UFUNCTION(BlueprintPure, Category = "Crate")
	bool IsHighlighted() const { return bHighlighted; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	bool bHighlighted = false;

	/** The two looks the crate takes. Swapped wholesale rather than driven by a
	 *  material parameter: not every prototype material in this substrate carries a
	 *  colour parameter, and a set that silently does nothing leaves the state
	 *  invisible while looking like it worked. */
	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* PlainLook = nullptr;
};
