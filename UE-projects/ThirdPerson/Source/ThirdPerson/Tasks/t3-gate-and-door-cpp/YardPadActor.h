// Copyright CraftBench. All Rights Reserved.
//
// A floor pad, for task t3-gate-and-door-cpp.
//
// The pad is a painted mat you walk over. It knows how to answer one question, and it
// has always answered it the same way: WHO IS RESTING ON ME RIGHT NOW. A body -- a
// person or a crate, the yard has never cared which -- is resting on this pad when the
// middle of its solid shape is within ContactRadiusUu of the pad's centre measured
// flat, and the bottom of that shape is down on the pad's own level rather than in the
// air.
//
// AnsweredBarrier says which door in the yard this pad answers for. It is set on each
// placed pad as the yard is laid out, and it is not the pad's to change.
//
// Nothing in here moves a door and nothing in here decides when a door should be open.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardPadActor.generated.h"

class UBoxComponent;
class USceneComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AYardPadActor : public AActor
{
	GENERATED_BODY()

public:
	AYardPadActor();

	virtual void Tick(float DeltaSeconds) override;

	/** Root, at floor level in the middle of the mat. Everything else hangs off it
	 *  unscaled, so every relative number below is in world units, and the pad's
	 *  position IS the centre it measures from. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	USceneComponent* Mount = nullptr;

	/** The 240 x 240 cm painted mat. Flat with the floor and non-colliding: it is
	 *  walked over and slid over, never stepped up onto. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UStaticMeshComponent* Mat = nullptr;

	/** Rides up while something is resting here. A readout for whoever is watching;
	 *  nothing reads it back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UStaticMeshComponent* Marker = nullptr;

	/** The region over the mat. It notices what is near and blocks nothing, and it
	 *  reports what comes and goes to anybody who wants to hear it. It is not the
	 *  answer, though: what is RESTING here is answered by measurement, below, so
	 *  the answer is the same whether it is asked once or every frame. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UBoxComponent* PadVolume = nullptr;

	/** How far from the pad's centre, measured flat, a body may be and still be
	 *  resting on it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pad")
	float ContactRadiusUu = 100.0f;

	/** How far off the pad's own level a body's bottom may be and still count as
	 *  resting on it rather than passing over it. Generous enough that a walking
	 *  body is never missed and tight enough that a body up in the air never
	 *  counts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pad")
	float GroundedBandUu = 50.0f;

	/** The door this pad answers for. Set on each placed pad. */
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Pad")
	AActor* AnsweredBarrier = nullptr;

	/** The middle of the mat, on the floor. */
	UFUNCTION(BlueprintPure, Category = "Pad")
	FVector GetPadCentre() const;

	/** Is this one body resting on this pad right now. */
	UFUNCTION(BlueprintPure, Category = "Pad")
	bool IsBodyResting(const AActor* Body) const;

	/** Everything resting on this pad right now -- people and crates alike, in no
	 *  particular order. */
	UFUNCTION(BlueprintCallable, BlueprintPure = false, Category = "Pad")
	void GetRestingBodies(TArray<AActor*>& OutBodies) const;

	/** Is anything at all resting on this pad right now. */
	UFUNCTION(BlueprintPure, Category = "Pad")
	bool HasAnyRestingBody() const;
};
