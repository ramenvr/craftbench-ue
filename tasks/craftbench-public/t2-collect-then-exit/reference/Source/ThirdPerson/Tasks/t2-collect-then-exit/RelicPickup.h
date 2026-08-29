// Copyright CraftBench. All Rights Reserved.
//
// A relic standing in the arena for task t2-collect-then-exit. Walking into it
// gathers it: the relic leaves the arena for good and the exit is told once.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RelicPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ARelicPickup : public AActor
{
	GENERATED_BODY()

public:
	ARelicPickup();

	/** The contact volume: a 120 cm sphere, query-only, overlap events on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Relic")
	USphereComponent* RelicVolume = nullptr;

	/** What you can see of the relic. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Relic")
	UStaticMeshComponent* RelicMesh = nullptr;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnRelicBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

private:
	bool bGathered = false;
};
