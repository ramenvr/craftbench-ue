// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-guard-patrols-until-the-alarm-then-chases.
//
// A yard guard that paces between the posts it finds, and goes after the character
// while the supplied alarm is sounding and they are inside its own alert range.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PatrolGuardActor.generated.h"

class UCapsuleComponent;
class UMaterialInstanceDynamic;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API APatrolGuardActor : public AActor
{
	GENERATED_BODY()

public:
	APatrolGuardActor();

	/** What the guard collides with. The ROOT, and a capsule rather than the mesh: a
	 *  root component's relative location is the actor's location, so a mesh made root
	 *  and offset upward has its collision left centred on the actor origin -- half
	 *  buried in the floor, permanently penetrating, and refusing every swept move. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UCapsuleComponent* Hull = nullptr;

	/** The guard you can see. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Body = nullptr;

	/** A shoulder marker, so which way the guard faces reads at a glance. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Snout = nullptr;

	/** How fast this guard walks its route. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Guard")
	float PatrolSpeedUu = 220.0f;

	/** How fast this guard moves when it is going after somebody. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Guard")
	float ChaseSpeedUu = 520.0f;

	/** How close counts as having reached a point. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Guard")
	float ArriveRadiusUu = 120.0f;

	/** How far away something can be and still concern this guard. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Guard")
	float AlertRangeUu = 2000.0f;

	/** THE SUPPLIED LOCOMOTION. Walks the guard toward Destination at SpeedUu for one
	 *  frame, never overshooting it, and turns the guard to face the way it moved.
	 *  Height is left alone: the yard is flat. */
	UFUNCTION(BlueprintCallable, Category = "Guard")
	void StepToward(const FVector& Destination, float SpeedUu, float DeltaSeconds);

	/** True once StepToward has brought the guard inside ArriveRadiusUu of Point. */
	UFUNCTION(BlueprintPure, Category = "Guard")
	bool HasReached(const FVector& Point) const;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Red while going after somebody, dark while pacing. Decoration, not the grade. */
	void Recolour(bool bChasing);

	/** The posts, held as ACTORS. Their coordinates are staged after BeginPlay, so a
	 *  remembered position would point at where a post used to be. */
	TArray<TWeakObjectPtr<AActor>> Route;
	int32 Leg = 0;
	TWeakObjectPtr<class AAlarmPanelActor> Alarm;
	bool bWasChasing = false;

	UPROPERTY()
	UMaterialInstanceDynamic* BodyMaterial = nullptr;
};
