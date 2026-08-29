// Copyright CraftBench. All Rights Reserved.
//
// VARIANT one-shot-rail. The rail is real and it is RELEASED once the first slide
// is over -- the most common wrong implementation in this family. Every first-shove
// gate passes; the second shove throws the block off the line exactly as it does
// the twin.
//
// The release is EVENT-driven (the first slide has run and stopped), not clocked at
// a fixed time: a timer at 6 s released it after the second shove had already been
// delivered, so the rail was still holding during both and the leg PASSED the whole
// task (measured 2026-08-17).

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
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rail")
	UPhysicsConstraintComponent* RailJoint = nullptr;

private:
	bool bHasSlid = false;
	bool bReleased = false;
};
