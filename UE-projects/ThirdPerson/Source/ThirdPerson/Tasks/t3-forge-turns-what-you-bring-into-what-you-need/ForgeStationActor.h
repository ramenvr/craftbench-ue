// Copyright CraftBench. All Rights Reserved.
//
// The forge for task t3-forge-turns-what-you-bring-into-what-you-need.
//
// Everything the forge needs to SHOW what it is holding and to SET SOMETHING DOWN is
// supplied and working: the anvil, the two faces, the shelf-stones, and the two
// switches. Nothing here notices the character, nothing here holds anything, nothing
// here knows a recipe, and nothing here decides when to throw either switch.
//
// TakeReachUu is the hall's number, read off the forge. Keep it as a property with
// this name and this type.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ForgeStationActor.generated.h"

class AIngredientHeapActor;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AForgeStationActor : public AActor
{
	GENERATED_BODY()

public:
	AForgeStationActor();

	/** How many shelf-stones the forge owns. Deliberately more than any correct run
	 *  needs -- a correct run sets down four things and never has more than three
	 *  standing at once -- so that a submission which over-crafts still has somewhere
	 *  to put the extra, and the extra stays VISIBLE instead of vanishing into a full
	 *  shelf exactly when the failure is getting worse. */
	static constexpr int32 ShelfStoneCount = 10;

	/** The anvil you can see. Solid, and only 200 uu across, so a walker can stand
	 *  well inside the forge's reach without ever touching it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Forge")
	UStaticMeshComponent* Anvil = nullptr;

	/** THE FIRST FACE: what the forge is holding. The level ships it reading "--". */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Forge")
	UTextRenderComponent* HeldFace = nullptr;

	/** THE SECOND FACE: what it could make from what it is holding right now. The
	 *  level ships it reading "--". */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Forge")
	UTextRenderComponent* CanMakeFace = nullptr;

	/** Where the forge sets things down, in the order it uses them. Named Shelf00..
	 *  Shelf09 and fixed to the forge, so where they stand is not a thing anybody has
	 *  to agree about. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Forge")
	TArray<UStaticMeshComponent*> ShelfStones;

	/** How close somebody has to be before the forge takes what they are carrying. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Forge")
	float TakeReachUu = 450.0f;

	/** What the forge sets a product down as. A heap like any other. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Forge")
	TSubclassOf<AIngredientHeapActor> ProductHeapClass;

	/** THE FIRST SWITCH. Writes both faces, verbatim. */
	UFUNCTION(BlueprintCallable, Category = "Forge")
	void ShowReadout(const FString& HeldLine, const FString& CanMakeLine);

	/** THE SECOND SWITCH. Sets one unit of ProductId down on the forge's next free
	 *  shelf-stone as a heap like any other -- walk-up-able, carry-back-able, and an
	 *  ingredient in a bigger recipe. A stone counts as free when no heap with units
	 *  still in it is standing on it, so a stone whose heap has been carried away is
	 *  free again.
	 *
	 *  NEVER SILENTLY DROPS A PRODUCT. With every stone occupied it stacks on the
	 *  last one and logs a line, because a product that vanished would be
	 *  indistinguishable from a product that was never made -- exactly when a
	 *  submission is making too many of them.
	 *
	 *  Returns the heap it set down, or nullptr if there is no world to spawn into. */
	UFUNCTION(BlueprintCallable, Category = "Forge")
	AIngredientHeapActor* EjectProduct(FName ProductId);
};
