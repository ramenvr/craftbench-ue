// Copyright CraftBench. All Rights Reserved.
//
// A carved plaque for task t3-forge-turns-what-you-bring-into-what-you-need.
//
// One recipe, carved as one line: "TIER 1 : ORE ORE ORE -> INGOT". The step up it is,
// then the units it needs, then the single thing they make. The slab, the carving you
// can see, the three parsers, and the number saying how close you have to stand to read
// it are all supplied and working. Nothing here knows where the character is, and
// nothing here decides anything.
//
// THE CARVING IS THE HALL'S, NOT YOURS. CarvedText and ReadReachUu are how the wall
// re-carves itself part way through the run: they are written from outside, by name,
// while the level is playing. Keep them as properties with these names and these
// types.
//
// GetInputs()/GetOutput()/GetTier() RE-PARSE CarvedText ON EVERY CALL and cache
// nothing, so asking at the moment you need the answer costs you nothing and is always
// current.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RecipePlaqueActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ARecipePlaqueActor : public AActor
{
	GENERATED_BODY()

public:
	ARecipePlaqueActor();

	/** The slab you can see. Non-colliding: a wall you can bump into is a wall that
	 *  can jam a walk, and none of this task is about walking into things. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plaque")
	UStaticMeshComponent* Slab = nullptr;

	/** The same line a human reads off the wall. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plaque")
	UTextRenderComponent* Carving = nullptr;

	/** The recipe, written the way it is carved: "TIER n :", then the units, then
	 *  "->", then the single thing they make. Read it off the plaque: the wall is
	 *  re-carved part way through the run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Plaque")
	FString CarvedText;

	/** How close somebody has to stand before they can read THIS plaque. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Plaque")
	float ReadReachUu = 300.0f;

	/** Every unit this recipe needs, repeats included: "ORE ORE COAL" is three
	 *  entries, two of them ORE. The "TIER n :" the carving opens with is not one of
	 *  them. Re-parsed on every call. */
	UFUNCTION(BlueprintPure, Category = "Plaque")
	TArray<FName> GetInputs() const;

	/** Which step up this recipe is, as carved: 1 for "TIER 1 : ...". Zero when the
	 *  carving does not open with a step. Re-parsed on every call. */
	UFUNCTION(BlueprintPure, Category = "Plaque")
	int32 GetTier() const;

	/** The single thing this recipe makes. NAME_None when the carving does not
	 *  parse. Re-parsed on every call. */
	UFUNCTION(BlueprintPure, Category = "Plaque")
	FName GetOutput() const;

	/** Rewrites the visible carving from CarvedText. Presentation only -- it decides
	 *  nothing. Supplied so the wall's re-carve and your own code write the same
	 *  face. */
	UFUNCTION(BlueprintCallable, Category = "Plaque")
	void RefreshCarving();

protected:
	virtual void BeginPlay() override;
};
