// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT logs-per-tick (anti-gaming note #3): the overlap
// handler only arms a flag; a per-tick path then emits the marker every frame
// while armed. Silent before the overlap (checkpoint 0 passes), then floods --
// must FAIL at checkpoint 1 (exactly-once), observed >= 2.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OverlapLogActor.generated.h"

class USphereComponent;
class UPrimitiveComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AOverlapLogActor : public AActor
{
	GENERATED_BODY()

public:
	AOverlapLogActor();

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	/** Query-only overlap volume + scene root. */
	UPROPERTY(VisibleAnywhere)
	USphereComponent* CollisionSphere;

	/** VARIANT DELTA: set on the first overlap; the per-tick path logs while set. */
	bool bMarkerActive = false;
};
