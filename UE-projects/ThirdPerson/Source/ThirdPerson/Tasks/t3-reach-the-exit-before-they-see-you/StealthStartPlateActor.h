// Copyright CraftBench. All Rights Reserved.
//
// The plate at the start line for task t3-reach-the-exit-before-they-see-you.
//
// It is already built and working: every time somebody steps onto it, its number goes
// up by one, and the number is painted in the air above it so anybody watching can
// read it. Nothing else here decides anything -- the plate does not know what a round
// is, only that somebody stepped on it again.
//
// NON-COLLIDING to a line: the yard promises that the plate never blocks anything.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthStartPlateActor.generated.h"

class UBoxComponent;
class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AStealthStartPlateActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthStartPlateActor();

	/** Where the plate lies. The ROOT, unscaled, and at floor level: the actor's own
	 *  location is the middle of the pad, on the floor. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	USceneComponent* Anchor = nullptr;

	/** The region just above the pad. It reports what enters and leaves and blocks
	 *  nothing at all. Fixed to the anchor, so nothing can drift between what you step
	 *  on and what notices you. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	UBoxComponent* PlateVolume = nullptr;

	/** The 240 x 240 cm pad painted on the floor. Non-colliding: the yard promises the
	 *  plate never blocks anything, at any height. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	UStaticMeshComponent* Pad = nullptr;

	/** The plate's number, painted in the air above it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	UTextRenderComponent* Face = nullptr;

	/** How many times somebody has stepped onto this plate. Starts at nothing and
	 *  clicks up by one on every fresh step. Read it; the plate writes it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Plate")
	int32 RoundIndex = 0;

	UFUNCTION(BlueprintPure, Category = "Plate")
	int32 GetRoundIndex() const { return RoundIndex; }

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void OnPlateBeginOverlap(UPrimitiveComponent* OverlappedComponent,
							 AActor* OtherActor,
							 UPrimitiveComponent* OtherComp,
							 int32 OtherBodyIndex,
							 bool bFromSweep,
							 const FHitResult& SweepResult);

	void RepaintFace();
};
