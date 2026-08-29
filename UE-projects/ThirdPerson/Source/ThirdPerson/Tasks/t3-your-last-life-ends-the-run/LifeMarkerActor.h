// Copyright CraftBench. All Rights Reserved.
//
// One of the three painted marker discs for task t3-your-last-life-ends-the-run --
// the disc a runner stands on when the run opens, and the number painted on it.
//
// Supplied and working: the disc, and a painted number that always shows whatever
// PaintedLives currently says.
//
// PaintedLives is the marker's own; read it, do not write it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LifeMarkerActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ALifeMarkerActor : public AActor
{
	GENERATED_BODY()

public:
	ALifeMarkerActor();

	/** The flat 300 cm disc you can see and stand on. Non-colliding. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Marker")
	UStaticMeshComponent* DiscMesh = nullptr;

	/** The number painted on this disc, floating just above it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Marker")
	UTextRenderComponent* PaintedNumber = nullptr;

	/** The number painted on THIS marker. Never more than six, never less than one,
	 *  and the three markers in the level are not painted the same. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Marker")
	int32 PaintedLives = 3;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Keeps the paint and the number the same thing. */
	void RefreshPaint();

	int32 PaintedShown = -1;
};
