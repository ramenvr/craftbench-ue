// Copyright CraftBench. All Rights Reserved.
//
// The block that stands on the painted rail.

#pragma once

#include "CoreMinimal.h"
#include "BenchBlockActor.h"
#include "RailBlockActor.generated.h"

class UPhysicsConstraintComponent;

UCLASS()
class THIRDPERSON_API ARailBlockActor : public ABenchBlockActor
{
	GENERATED_BODY()

public:
	ARailBlockActor();

protected:
	virtual void BeginPlay() override;

	/** Holds the block to the painted rail: one translation free, the other two
	 *  and all three rotations locked. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rail")
	UPhysicsConstraintComponent* RailJoint = nullptr;
};
