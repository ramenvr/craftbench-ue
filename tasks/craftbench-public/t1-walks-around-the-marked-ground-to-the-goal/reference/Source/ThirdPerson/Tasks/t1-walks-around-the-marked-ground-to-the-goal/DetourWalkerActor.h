// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-walks-around-the-marked-ground-to-the-goal.
//
// A figure that PLANS a route round whichever patch is out of bounds, and re-plans
// when the yard changes which one that is.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DetourWalkerActor.generated.h"

class UCapsuleComponent;
class UMaterialInstanceDynamic;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ADetourWalkerActor : public AActor
{
	GENERATED_BODY()

public:
	ADetourWalkerActor();

	/** What the walker collides with. The ROOT, and a capsule rather than the mesh:
	 *  a root component's relative location IS the actor's location, so a mesh made
	 *  root and offset upward leaves its collision centred on the actor origin, half
	 *  buried in the floor and permanently penetrating it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Walker")
	UCapsuleComponent* Hull = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Walker")
	UStaticMeshComponent* Body = nullptr;

	/** A cone on the front, so which way the walker faces reads at a glance. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Walker")
	UStaticMeshComponent* Snout = nullptr;

	/** How fast this figure walks. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Walker")
	float WalkSpeedUu = 340.0f;

	/** How close counts as having reached a point. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Walker")
	float ArriveRadiusUu = 110.0f;

	/** THE SUPPLIED LOCOMOTION. Walks the figure toward Destination at SpeedUu for
	 *  one frame, never overshooting it, turning it to face the way it moved. Height
	 *  is left alone: the yard is flat. */
	UFUNCTION(BlueprintCallable, Category = "Walker")
	void StepToward(const FVector& Destination, float SpeedUu, float DeltaSeconds);

	UFUNCTION(BlueprintPure, Category = "Walker")
	bool HasReached(const FVector& Point) const;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Whichever patch the yard currently says is out of bounds, or null. */
	class AMarkedGroundActor* OutOfBoundsPatch() const;
	/** True when a point is too close to the forbidden paint to plan through. */
	bool Blocked(const FVector& P, const class AMarkedGroundActor* Forbidden) const;
	/** Search the yard for a route to the goal that keeps off the forbidden paint. */
	bool Replan();

	TArray<TWeakObjectPtr<class AMarkedGroundActor>> Patches;
	TWeakObjectPtr<AActor> Goal;
	/** The area worth searching, taken from what the walker can see rather than
	 *  written down: its own position, the goal, and the patches' footprints. */
	FBox Field = FBox(ForceInit);

	TArray<FVector> Plan;
	int32 Leg = 0;
	/** Which patch the current plan was made against, so a swap forces a re-plan. */
	TWeakObjectPtr<class AMarkedGroundActor> PlannedAgainst;

	UPROPERTY()
	UMaterialInstanceDynamic* BodyMaterial = nullptr;
};
