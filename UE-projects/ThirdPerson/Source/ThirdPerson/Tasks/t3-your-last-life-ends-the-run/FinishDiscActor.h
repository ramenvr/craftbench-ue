// Copyright CraftBench. All Rights Reserved.
//
// The wide finish disc at the far end of the floor for task
// t3-your-last-life-ends-the-run.
//
// It arrives inert. It notices bodies and blocks nothing, and it does nothing about
// what it notices. Nothing here decides that anybody has finished.
//
// DiscRadiusUu is how wide the disc is painted and how far out from its centre
// counts as standing on it. DemandedLives is the number painted on its face, and the
// painted number always shows whatever DemandedLives currently says. Read them both;
// the finish is not yours to move, resize or re-paint.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FinishDiscActor.generated.h"

class USphereComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AFinishDiscActor : public AActor
{
	GENERATED_BODY()

public:
	AFinishDiscActor();

	/** The painted disc you can see. Flat, non-colliding, walked straight over. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Finish")
	UStaticMeshComponent* DiscMesh = nullptr;

	/** The reach of the disc: query-only, overlapping everything, blocking nothing. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Finish")
	USphereComponent* DiscVolume = nullptr;

	/** The number painted on the face of the disc, floating just above it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Finish")
	UTextRenderComponent* DemandNumber = nullptr;

	/** How far out from the centre of the disc counts as standing on it, in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Finish")
	float DiscRadiusUu = 800.0f;

	/** The number painted on THIS disc. Never more than six, never less than one. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Finish")
	int32 DemandedLives = 3;

protected:
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Keeps the paint and the number the same thing. */
	void RefreshPaint();

	int32 DemandShown = -1;
};
