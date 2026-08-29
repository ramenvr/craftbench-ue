// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-timeline-color-cycle. The actor drives a
// dynamic material instance every tick, piecewise-lerping green -> blue ->
// red -> green on a 6-second world-time cycle and publishing the current
// color through the disclosed "CycleColor" vector parameter.

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

	/** The visible cube. Ships with the engine basic-shape mesh and its
	 *  default material. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* DisplayMesh;

	/** Runtime material instance carrying the CycleColor parameter. */
	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> CycleMid;

	/** Full cycle length in seconds (green at 0, blue at 1/3, red at 2/3). */
	UPROPERTY(EditAnywhere, Category = "Color Cycle")
	float CyclePeriod = 6.0f;
};
