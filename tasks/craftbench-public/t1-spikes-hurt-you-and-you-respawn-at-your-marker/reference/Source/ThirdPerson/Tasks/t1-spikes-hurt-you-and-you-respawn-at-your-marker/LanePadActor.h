// Copyright CraftBench. All Rights Reserved.
//
// One of the two pads beside the lane for task
// t1-spikes-hurt-you-and-you-respawn-at-your-marker. Walking onto it is meant to
// make it the current pad; nothing calls SetMarkedCurrent yet.
//
// PadOrder is authored on each placed pad (1 for the one nearer the start mark,
// 2 for the one further along). Read it; do not rewrite it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LanePadActor.generated.h"

class UBoxComponent;
class UMaterialInterface;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ALanePadActor : public AActor
{
	GENERATED_BODY()

public:
	ALanePadActor();

	/** The flat 200 x 200 cm pad you can see and stand on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UStaticMeshComponent* PadMesh = nullptr;

	/** Query-only 200 x 200 x 220 cm box over the pad. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UBoxComponent* PadVolume = nullptr;

	/** 1 for the pad nearer the start mark, 2 for the one further along. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pad")
	int32 PadOrder = 0;

	/** Whether this is the current pad. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pad")
	bool bMarkedCurrent = false;

	/**
	 *  Sets the flag AND swaps the pad between its dark and bright looks in one
	 *  call, so what a reviewer sees and what the flag says can never disagree.
	 *  Use this rather than writing bMarkedCurrent directly.
	 */
	UFUNCTION(BlueprintCallable, Category = "Pad")
	void SetMarkedCurrent(bool bInMarked);

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnPadBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

private:
	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;

	UPROPERTY()
	UMaterialInterface* BrightLook = nullptr;
};
