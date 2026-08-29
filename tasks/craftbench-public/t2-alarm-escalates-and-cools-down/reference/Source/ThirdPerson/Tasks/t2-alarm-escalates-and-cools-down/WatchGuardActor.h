// Copyright CraftBench. All Rights Reserved.
//
// A yard guard for task t2-alarm-escalates-and-cools-down. Everything it needs to WALK
// ITS ROUND is supplied and working: a body, a facing, and a Tick that paces it between
// the two posts carrying its own RoundTag at whatever PatrolSpeedUuPerSec currently
// says. Nothing here perceives anybody, nothing here knows the panel exists, and
// nothing here ever writes its own speed.
//
// The two guards in the yard are NOT set to the same numbers. How far this one can see,
// how wide its view is, and how fast it walks are all read off THIS guard.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WatchGuardActor.generated.h"

class UCapsuleComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AWatchGuardActor : public AActor
{
	GENERATED_BODY()

public:
	AWatchGuardActor();

	/** What the guard collides with. The ROOT, and a capsule rather than the mesh: a
	 *  root component's relative location is the actor's location, so a mesh made root
	 *  and offset upward has its collision left centred on the actor origin -- half
	 *  buried in the floor, permanently penetrating, and refusing every swept move. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UCapsuleComponent* Hull = nullptr;

	/** The guard you can see. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Body = nullptr;

	/** A nose cone, so which way the guard is facing reads at a glance. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Snout = nullptr;

	/** How far THIS guard can see. Not the same on both guards. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Guard")
	float SightRangeUu = 2400.0f;

	/** How far off the way THIS guard is facing it can still see. Not the same on both
	 *  guards. The arc it covers is painted on the floor around its round. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Guard")
	float SightHalfAngleDeg = 13.0f;

	/** How fast THIS guard walks when the yard is at its lowest setting. Read it; do
	 *  not write it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Guard")
	float BasePatrolSpeedUu = 280.0f;

	/** How fast the guard is walking RIGHT NOW. This is the one that is yours to set;
	 *  the supplied round below simply walks at whatever it says. Starts at
	 *  BasePatrolSpeedUu. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Guard")
	float PatrolSpeedUuPerSec = 280.0f;

	/** Which round this guard walks: it paces between the two posts carrying this tag.
	 *  The sergeant re-tags the guards when the watch changes, and the round is
	 *  re-resolved when that happens. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Guard")
	FName RoundTag = FName(TEXT("RoundNorth"));

	/** The two ends of the round this guard is currently walking, in the order it
	 *  resolved them. Empty until the first Tick. */
	UFUNCTION(BlueprintPure, Category = "Guard")
	FVector GetRoundEndA() const { return RoundA; }

	UFUNCTION(BlueprintPure, Category = "Guard")
	FVector GetRoundEndB() const { return RoundB; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Finds the two posts tagged RoundTag and remembers their positions. Called again
	 *  whenever RoundTag changes under the guard's feet. */
	void ResolveRound();

	FVector RoundA = FVector::ZeroVector;
	FVector RoundB = FVector::ZeroVector;
	bool bRoundResolved = false;
	FName ResolvedForTag = NAME_None;

	/** Which end it is currently walking toward. */
	bool bHeadingToB = true;
};
