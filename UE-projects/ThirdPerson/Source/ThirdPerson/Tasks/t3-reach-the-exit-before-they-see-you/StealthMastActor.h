// Copyright CraftBench. All Rights Reserved.
//
// The mast beside the gate for task t3-reach-the-exit-before-they-see-you.
//
// It carries the three lights the yard is read by -- running, away and caught -- and
// each of them has a switch that works. That is all it is: three switches and nothing
// that decides when to throw them. All three ship dark.
//
// The mast has no state of its own, on purpose. There is no "current outcome" property
// here to set: the three lights ARE the outcome, and they are the only thing anyone
// outside the yard can read.
//
// NON-COLLIDING to a line: the yard promises that the mast never blocks anything.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthMastActor.generated.h"

class UMaterialInterface;
class UPointLightComponent;
class USceneComponent;
class UStaticMeshComponent;

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

private:
	/** Throws one light, and swaps its housing's look so the state reads at a glance
	 *  as well as in the light itself. Swapped wholesale rather than driven by a
	 *  material parameter: not every prototype material in this substrate carries a
	 *  colour parameter, and a set that silently does nothing leaves the state
	 *  invisible while looking like it worked. */
	void Throw(UPointLightComponent* Light, UStaticMeshComponent* Shade, bool bNewLit);

	bool bRunningLit = false;
	bool bAwayLit = false;
	bool bCaughtLit = false;

	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;
};
