// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "snap-cycle" for task t2-timeline-color-cycle.
// Models anti-gaming note #2: a repeating 2-second timer flips the color
// instantly green -> blue -> red -> green with no blending — order, period
// and coverage all read correct, but every change is a single-frame snap.
// Expected: FAIL at cp1 via "the color snaps instead of blending smoothly".

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

	void AdvanceAnchor();

	/** The visible cube. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* DisplayMesh;

	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> CycleMid;

	FTimerHandle SnapTimer;
	int32 AnchorIndex = 0;
};
