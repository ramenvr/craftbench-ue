// Copyright CraftBench. All Rights Reserved.
//
// The figure that has to get across the yard, for task
// t1-walks-around-the-marked-ground-to-the-goal. Everything it needs to MOVE is
// supplied and working: a body, a facing, and one call that walks it toward a point
// for one frame. Nothing decides where it should be going.

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

private:
	UPROPERTY()
	UMaterialInstanceDynamic* BodyMaterial = nullptr;
};
