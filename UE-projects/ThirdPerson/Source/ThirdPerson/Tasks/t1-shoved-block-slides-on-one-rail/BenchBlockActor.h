// Copyright CraftBench. All Rights Reserved.
//
// The block body both blocks in this level are made of. Everything physical
// about them lives here, so the pair are identical bodies by construction
// rather than by promise.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BenchBlockActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ABenchBlockActor : public AActor
{
	GENERATED_BODY()

public:
	ABenchBlockActor();

	/** The 60 cm cube. It is the root, and it is what the world's physics moves. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bench")
	UStaticMeshComponent* Block = nullptr;

	/** Floats above the block and prints how far it is off the painted rail line and
	 *  how far it has turned. A plain cube shows neither: 121 degrees of yaw on a cube
	 *  looks like 31, and without the numbers a still cannot say which block tracked
	 *  the rail. Presentation only -- nothing reads it back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bench")
	UTextRenderComponent* Readout = nullptr;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	FVector RailDir = FVector::ForwardVector;
	FVector RailRight = FVector::RightVector;
	FVector RailPoint = FVector::ZeroVector;
	FQuat StartRotation = FQuat::Identity;
	FVector StartLocation = FVector::ZeroVector;
	bool bRailKnown = false;
};
