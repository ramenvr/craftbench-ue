// Copyright CraftBench. All Rights Reserved.
//
// The gate at the far end of the yard for task t3-reach-the-exit-before-they-see-you.
//
// It is already built and working: it knows, at any moment, whether somebody is
// standing in it. Nothing here decides what that means.
//
// NON-COLLIDING to a line: the yard promises that the gate never blocks anything.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthGateActor.generated.h"

class UBoxComponent;
class USceneComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AStealthGateActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthGateActor();

	/** Where the gate stands. The ROOT, unscaled, and at floor level: the actor's own
	 *  location is the middle of the gateway, on the floor. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	USceneComponent* Anchor = nullptr;

	/** The gateway itself. It reports what is inside it and blocks nothing. Fixed to
	 *  the anchor, so nothing can drift between the gate and what it notices. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	UBoxComponent* GateVolume = nullptr;

	/** The two uprights and the lintel you can see. No collision at all. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	UStaticMeshComponent* PostLeft = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	UStaticMeshComponent* PostRight = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	UStaticMeshComponent* Lintel = nullptr;

	/** True while somebody is standing in the gateway. Asked live, so it is right
	 *  even for somebody who arrived without walking in. */
	UFUNCTION(BlueprintPure, Category = "Gate")
	bool IsSomebodyStandingInIt() const;
};
