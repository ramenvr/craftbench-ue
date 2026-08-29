// Copyright CraftBench. All Rights Reserved.
//
// VARIANT spoofed-motion. See the .cpp: the block is written along the rail rather
// than held to it.

#pragma once

#include "CoreMinimal.h"
#include "BenchBlockActor.h"
#include "RailBlockActor.generated.h"

UCLASS()
class THIRDPERSON_API ARailBlockActor : public ABenchBlockActor
{
	GENERATED_BODY()

public:
	ARailBlockActor();

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	FVector RailDir = FVector::ForwardVector;
	FVector StartLocation = FVector::ZeroVector;
	FRotator StartRotation = FRotator::ZeroRotator;
	double Travelled = 0.0;
	bool bSliding = false;
};
