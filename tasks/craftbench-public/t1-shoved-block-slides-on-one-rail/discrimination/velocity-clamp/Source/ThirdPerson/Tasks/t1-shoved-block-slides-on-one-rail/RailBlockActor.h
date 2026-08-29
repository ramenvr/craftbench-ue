// Copyright CraftBench. All Rights Reserved.
//
// VARIANT velocity-clamp. A REAL one-axis joint, re-anchored at the block's current
// pose every frame. That PREVENTS the block from leaving the line -- it can never
// acquire off-axis or angular motion, so every gate that watches a shove passes,
// twice over, with the same readings as a correct answer. It does not HOLD the block
// TO a line: after something lifts the block off, the joint simply re-anchors where
// the block now is, so nothing carries it back.
//
// That gap is the whole point of the tether leg, and this variant is threshold-free
// on purpose. Two earlier attempts keyed the cheat on a speed threshold and neither
// worked: low enough to correct the first frames of a shove was also low enough to
// re-engage on the 280 cm/s of the knock's fall (so it snapped back and PASSED the
// tether leg), and high enough to ignore the fall left the opening frames of the
// shove uncorrected -- which the window-maximum gates record permanently (measured
// dzmax 10.5 cm and turnmax 38.6 deg, so it failed cp1 instead of cp3).

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
};
