// Copyright CraftBench. All Rights Reserved.
//
// A watcher for task t3-reach-the-exit-before-they-see-you. Everything it needs to
// WALK ITS ROUND is supplied and working: a body, a facing, and a Tick that paces it
// between the two posts carrying its own RoundTag at whatever PaceUuPerSec currently
// says -- and stands stock still while that says nothing. Its head lamp is supplied
// and working too: it has a switch, and nothing here ever throws it.
//
// Nothing here perceives anybody, nothing here knows the mast exists, and nothing
// here ever writes its own pace.
//
// The watchers in the yard are NOT set to the same numbers. How far this one can see,
// how wide its view is, and how fast it walks are all read off THIS watcher -- and the
// sergeant may re-set any of them, and swap which round it walks, part way through the
// night.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthWatcherActor.generated.h"

class UCapsuleComponent;
class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AStealthWatcherActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthWatcherActor();

	/** What the watcher collides with. The ROOT, and a capsule rather than the mesh: a
	 *  root component's relative location is the actor's location, so a mesh made root
	 *  and offset upward has its collision left centred on the actor origin -- half
	 *  buried in the floor, permanently penetrating, and refusing every swept move. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Watcher")
	UCapsuleComponent* Hull = nullptr;

	/** The watcher you can see. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Watcher")
	UStaticMeshComponent* Body = nullptr;

	/** A nose cone, so which way the watcher is facing reads at a glance. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Watcher")
	UStaticMeshComponent* Snout = nullptr;

	/** The lamp on its head. Dark as shipped; nothing here decides when to throw it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Watcher")
	UPointLightComponent* HeadLamp = nullptr;

	/** How far THIS watcher can see. Not the same on every watcher, and it can be
	 *  re-set during the night. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Watcher")
	float SightReachUu = 2200.0f;

	/** How far off the way THIS watcher is facing it can still see. Not the same on
	 *  every watcher, and it can be re-set during the night. The arc it covers is
	 *  painted on the floor around its round. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Watcher")
	float SightHalfAngleDeg = 30.0f;

	/** How fast THIS watcher walks its round when a round is running. Read it; do not
	 *  write it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Watcher")
	float BasePaceUuPerSec = 300.0f;

	/** How fast the watcher is walking RIGHT NOW. This is the one that is yours to
	 *  set; the supplied round below simply walks at whatever it says, and stands
	 *  stock still while it says nothing. Starts at BasePaceUuPerSec. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Watcher")
	float PaceUuPerSec = 300.0f;

	/** Which round this watcher walks: it paces between the two posts carrying this
	 *  tag. The sergeant re-tags the watchers when the watch changes, and the round is
	 *  re-resolved when that happens. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Watcher")
	FName RoundTag = FName(TEXT("RoundEast"));

	/** THE SWITCH on the head lamp. */
	UFUNCTION(BlueprintCallable, Category = "Watcher")
	void SetLampLit(bool bNewLit);

	UFUNCTION(BlueprintPure, Category = "Watcher")
	bool IsLampLit() const { return bLampLit; }

	/** The two ends of the round this watcher is currently walking, in the order it
	 *  resolved them. */
	UFUNCTION(BlueprintPure, Category = "Watcher")
	FVector GetRoundEndA() const { return RoundA; }

	UFUNCTION(BlueprintPure, Category = "Watcher")
	FVector GetRoundEndB() const { return RoundB; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Finds the two posts tagged RoundTag and remembers their positions. Called again
	 *  whenever RoundTag changes under the watcher's feet. */
	void ResolveRound();

	bool bLampLit = false;

	/** The two looks the head takes. Swapped wholesale rather than driven by a
	 *  material parameter: not every prototype material in this substrate carries a
	 *  colour parameter, and a set that silently does nothing leaves the state
	 *  invisible while looking like it worked. */
	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;

	FVector RoundA = FVector::ZeroVector;
	FVector RoundB = FVector::ZeroVector;
	bool bRoundResolved = false;
	FName ResolvedForTag = NAME_None;

	/** Which end it is currently walking toward. */
	bool bHeadingToB = true;
};
