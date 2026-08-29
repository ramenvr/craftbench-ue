// Copyright CraftBench. All Rights Reserved.
//
// The mast beside the gate for task t3-reach-the-exit-before-they-see-you.
//
// REFERENCE SOLUTION. The supplied mast is three switches and nothing else; everything
// below the switches is the answer. The mast is the host because the yard is fixed --
// every watcher, post, crate, the wall, the truck, the plate, the gate and this mast
// are placed in a level that is not writable -- so a brand new class would never be
// instantiated.
//
// Every number is read at the point of use, never cached: the sergeant re-sets the
// watchers' numbers and swaps their rounds between rounds, and nothing announces it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthMastActor.generated.h"

class AStealthGateActor;
class AStealthStartPlateActor;
class AStealthWatcherActor;
class UMaterialInterface;
class UPointLightComponent;
class USceneComponent;
class UStaticMeshComponent;
struct FCollisionQueryParams;

UCLASS()
class THIRDPERSON_API AStealthMastActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthMastActor();

	/** Where the mast stands. The ROOT, unscaled, and at floor level: the actor's own
	 *  location is the foot of the mast. Nothing is hung off a scaled component here --
	 *  a scaled parent multiplies every child's offset, and a lamp 300 cm up a column
	 *  scaled 6x is 1,800 cm up. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	USceneComponent* Anchor = nullptr;

	/** The mast you can see. No collision at all. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UStaticMeshComponent* Column = nullptr;

	/** The three lamp housings, top to bottom. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UStaticMeshComponent* RunningShade = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UStaticMeshComponent* AwayShade = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UStaticMeshComponent* CaughtShade = nullptr;

	/** The three lights themselves. Dark as shipped. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UPointLightComponent* RunningLight = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UPointLightComponent* AwayLight = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mast")
	UPointLightComponent* CaughtLight = nullptr;

	/** THE SWITCHES. One per light; each lights it or puts it out, and neither knows
	 *  about the other two. */
	UFUNCTION(BlueprintCallable, Category = "Mast")
	void SetRunningLit(bool bNewLit);

	UFUNCTION(BlueprintCallable, Category = "Mast")
	void SetAwayLit(bool bNewLit);

	UFUNCTION(BlueprintCallable, Category = "Mast")
	void SetCaughtLit(bool bNewLit);

	UFUNCTION(BlueprintPure, Category = "Mast")
	bool IsRunningLit() const { return bRunningLit; }

	UFUNCTION(BlueprintPure, Category = "Mast")
	bool IsAwayLit() const { return bAwayLit; }

	UFUNCTION(BlueprintPure, Category = "Mast")
	bool IsCaughtLit() const { return bCaughtLit; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Throws one light, and swaps its housing's look so the state reads at a glance
	 *  as well as in the light itself. */
	void Throw(UPointLightComponent* Light, UStaticMeshComponent* Shade, bool bNewLit);

	/** Paints the board: exactly one of the three burns, always. */
	void ShowOutcome();

	/** Can this watcher see the runner at this instant? Flat (the yard is level), from
	 *  where the watcher is standing to where the runner is standing, against the
	 *  watcher's OWN two numbers, read live. Inclusive at both edges. Then the line
	 *  between those two spots must be clear of anything solid. */
	bool CanSee(const AStealthWatcherActor* Watcher, const FVector& RunnerAt,
				const FCollisionQueryParams& Ignore) const;

	/** Every watcher stands still, and the only lamps still burning belong to whoever
	 *  could see the runner AT THE INSTANT the round ended. Called on the frame a round
	 *  ends and held for as long as it stays ended. */
	void StandDown();

	/** 0 running, 1 away, 2 caught. The first ending wins and nothing later replaces
	 *  it; a fresh plate number, and only that, puts it back to running. */
	int32 Outcome = 0;

	/** The plate's number as the mast last saw it. When it changes, a round began. */
	int32 SeenRoundIndex = -1;

	/** WHO WAS LOOKING when the round ended. Latched on that one frame and held until
	 *  the plate clicks again -- it cannot be re-derived later, because by then the
	 *  watchers are frozen and the runner has walked somewhere else, so asking "who can
	 *  see the runner" gives a different (usually empty) answer. Empty for a round that
	 *  ended at the gate: nobody caught anybody. */
	UPROPERTY()
	TArray<AStealthWatcherActor*> CaughtBy;

	/** Resolved once: the placed cast never changes, only its numbers do. */
	UPROPERTY()
	TArray<AStealthWatcherActor*> Watchers;

	UPROPERTY()
	AStealthStartPlateActor* Plate = nullptr;

	UPROPERTY()
	AStealthGateActor* Gate = nullptr;

	bool bRunningLit = false;
	bool bAwayLit = false;
	bool bCaughtLit = false;

	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;
};
