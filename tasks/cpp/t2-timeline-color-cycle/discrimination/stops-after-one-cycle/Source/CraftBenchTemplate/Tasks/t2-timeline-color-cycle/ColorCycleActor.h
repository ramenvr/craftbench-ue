// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "stops-after-one-cycle" for task
// t2-timeline-color-cycle. Models anti-gaming note #4: one perfect
// 6-second cycle (smooth, right order, right period), then the color
// freezes forever. Movement, smoothness, order and period all read
// correct; only the continuity gate can tell. Expected: FAIL at cp1 via
// "the color stops cycling partway" (2 dominant-run transitions inside the
// trace window vs the floor of 3).

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
