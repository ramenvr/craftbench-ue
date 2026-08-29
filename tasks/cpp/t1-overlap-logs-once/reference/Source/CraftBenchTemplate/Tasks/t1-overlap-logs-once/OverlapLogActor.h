// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-overlap-logs-once: extend AOverlapLogActor so it
// logs the required marker once per overlap. BeginPlay binds the sphere's
// begin-overlap event; the handler emits the marker on LogTemp/Display.

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

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	/** Query-only overlap volume + scene root. */
	UPROPERTY(VisibleAnywhere)
	USphereComponent* CollisionSphere;
};
