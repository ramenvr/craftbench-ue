// Copyright CraftBench. All Rights Reserved.
//
// A crate for task t2-crate-you-carry-changes-what-you-can-do. Everything that makes
// it a crate is supplied and working: an 80 cm solid box, and its weight painted on
// it in kilograms so a person watching can read the same number the grade reads.
//
// The yard holds three of these and no two weigh the same. THE NUMBER IS NOT FIXED:
// the yard is priced while it is being laid out and re-priced part way through, so
// MassKg is the current answer and a copy taken once goes stale.
//
// Nothing here picks itself up, puts itself down, or knows the character exists.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HaulCrateActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AHaulCrateActor : public AActor
{
	GENERATED_BODY()

public:
	AHaulCrateActor();

	virtual void Tick(float DeltaSeconds) override;

	/** The crate you can see and bump into. 80 cm on a side, THE ROOT, movable,
	 *  blocking. The actor stands with the box's centre at its location, so the
	 *  yard places it at half its height and it sits on the floor. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	TObjectPtr<UStaticMeshComponent> Body;

	/** Prints MassKg every frame, so the painted number can never disagree with
	 *  the number that decides anything. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	TObjectPtr<UTextRenderComponent> WeightLabel;

	/** What this crate weighs, in kilograms. Read it off the crate when you need
	 *  it -- the yard re-prices itself part way through. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Crate")
	float MassKg = 20.0f;
};
