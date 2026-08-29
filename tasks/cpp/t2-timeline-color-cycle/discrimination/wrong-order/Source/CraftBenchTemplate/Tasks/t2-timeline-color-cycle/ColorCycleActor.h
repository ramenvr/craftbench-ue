// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "wrong-order" for task t2-timeline-color-cycle.
// Models anti-gaming note #3: a smooth, continuous, 6-second cycle — through
// the WRONG sequence (green -> red -> blue). Movement, smoothness and
// continuity all read correct; only the dominant-run order gate can tell.
// Expected: FAIL at cp1 via "does not cycle through green, blue and red in
// order".

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ColorCycleActor.generated.h"

class UMaterialInstanceDynamic;
class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AColorCycleActor : public AActor
{
	GENERATED_BODY()

public:
	AColorCycleActor();

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	/** The visible cube. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* DisplayMesh;

	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> CycleMid;

	UPROPERTY(EditAnywhere, Category = "Color Cycle")
	float CyclePeriod = 6.0f;
};
