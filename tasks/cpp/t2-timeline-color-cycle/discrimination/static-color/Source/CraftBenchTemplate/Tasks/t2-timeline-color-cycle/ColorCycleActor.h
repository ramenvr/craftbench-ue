// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "static-color" for task t2-timeline-color-cycle.
// Models anti-gaming note #1: the CycleColor parameter is created and set to
// green ONCE at BeginPlay and never updated — the readable-parameter gate
// passes, but the color never moves. Expected: FAIL at cp1 via
// "the color never changes".

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

protected:
	virtual void BeginPlay() override;

	/** The visible cube. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* DisplayMesh;

	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> CycleMid;
};
