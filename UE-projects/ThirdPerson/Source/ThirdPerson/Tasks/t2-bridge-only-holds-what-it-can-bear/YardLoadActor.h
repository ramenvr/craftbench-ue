// Copyright CraftBench. All Rights Reserved.
//
// A crate for task t2-bridge-only-holds-what-it-can-bear. It carries one number -- what
// it weighs -- and one piece of behaviour that is NOT the graded decision: it keeps its
// feet on whatever is directly beneath it.
//
// That is why a crate follows a sagging deck down, and why it falls when the deck it was
// standing on drops out, WITHOUT a solution having to do anything about it. It does not
// simulate physics (so nobody can shove it and nothing jitters) and it never moves
// sideways on its own -- where a crate stands is the yard's business.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardLoadActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AYardLoadActor : public AActor
{
	GENERATED_BODY()

public:
	AYardLoadActor();

	/** The crate you can see: a 120 cm cube, the root, solid, and NOT simulating
	 *  physics. The actor stands with the cube's centre at its location. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Load")
	UStaticMeshComponent* Body = nullptr;

	/** What THIS crate weighs. Read it off the crate: the three crates in the yard do
	 *  not weigh the same, and the yard stamps fresh weights each time it opens. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Load")
	float WeightKg = 200.0f;

protected:
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Traces straight down from the crate's middle and either sits on what it finds or
	 *  accelerates toward it. Deliberately a single trace from the middle: the yard
	 *  never sets a crate down straddling an edge, so there is nothing for a
	 *  four-corner version to resolve that this does not. */
	void KeepFeetOnWhateverIsBelow(float DeltaSeconds);

	double FallSpeed = 0.0;
};
