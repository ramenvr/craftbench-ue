// Copyright CraftBench. All Rights Reserved.
//
// The spiked slab. It slides its rail on its own and costs 25 health per touch.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpikeSlabActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ASpikeSlabActor : public AActor
{
	GENERATED_BODY()

public:
	ASpikeSlabActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Spikes")
	UStaticMeshComponent* SlabMesh = nullptr;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION()
	void OnSlabBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void OnSlabEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	FVector RailFrom = FVector::ZeroVector;
	FVector RailTo = FVector::ZeroVector;
	FVector Heading = FVector::ForwardVector;
	/** When each character may next be hurt. A touch that ends and immediately
	 *  begins again is the same touch: the engine's overlap edges flicker as the
	 *  slab steps past a capsule, and without this the same pass cost 50. Real
	 *  passes are ~2 s apart, so nothing legitimate is missed. */
	TMap<TWeakObjectPtr<AActor>, double> ArmedAt;
};
