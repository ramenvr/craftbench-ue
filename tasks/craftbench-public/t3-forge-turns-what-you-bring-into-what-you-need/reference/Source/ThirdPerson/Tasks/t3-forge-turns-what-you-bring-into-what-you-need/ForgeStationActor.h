// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task t3-forge-turns-what-you-bring-into-what-you-need.
//
// Everything above the "--- the answer ---" line is the supplied scaffold, unchanged.
// Below it is the whole of what a submission has to write: the carry and its cap, the
// delivery seam, the match by step, the spend, and the two faces.
//
// The forge is the only place the answer can live. All four actors are placed
// instances in a map the submission cannot edit, so a subclass would never be
// instantiated -- and the heaps, the plaques and the sign are deliberately dumb, which
// leaves exactly one thing in the hall that ticks.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ForgeStationActor.generated.h"

class ACarrySignActor;
class AIngredientHeapActor;
class ARecipePlaqueActor;
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

	// ------------------------------- the answer -------------------------------

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** How many units the character may have on them at once, READ OFF THE SIGN as it
	 *  stands this instant. The hall re-posts a different number part way through the
	 *  run, so a cap remembered from BeginPlay is wrong for the rest of it. */
	int32 CarryCapNow() const;

	/** How many units are on the character right now, across every kind. */
	int32 CarriedTotal() const;

	/** Walks up to every heap within its OWN reach and takes as much of it as there is
	 *  still room to carry -- all of it when the cap allows, part of it when it does
	 *  not, and none of it when the character is already full. What is not taken stays
	 *  standing. The set of heaps is re-queried every tick, NOT hoisted into BeginPlay:
	 *  the forge's own product is spawned mid-run and a cached list would never contain
	 *  it. */
	void CollectNearbyHeaps(const AActor& Walker);

	/** Re-reads the wall from the world. Called once a tick, never hoisted: plaques
	 *  are re-carved part way through the run. */
	void RefreshLivePlaques();

	/** Reads every plaque the walker is standing close enough to. Stores the CARVING,
	 *  not the parsed recipe, so a re-carve is detectable: a plaque whose text no
	 *  longer matches what was read is unknown again. */
	void ReadNearbyPlaques(const AActor& Walker);

	/** Hands everything carried over and makes at most one thing. */
	void TakeDelivery();

	/** The rule, once. The highest step carved among the recipes that have been read
	 *  and whose units the holdings cover with multiplicities. Null when nothing
	 *  fits. */
	ARecipePlaqueActor* ChooseRecipe(const TMap<FName, int32>& From) const;

	/** True when a plaque has been read AND still says what it said when it was. */
	bool IsKnown(const ARecipePlaqueActor& Plaque) const;

	static bool CoveredBy(const TMap<FName, int32>& Have, const TArray<FName>& Need);
	static FString FormatHeld(const TMap<FName, int32>& Held);

	/** Rewrites both faces from the holdings and the read set, but only when they
	 *  would change -- cheap, and it keeps the render side quiet on the frames where
	 *  nothing moved. */
	void RefreshFaces();

	/** What the forge is holding, by kind. */
	TMap<FName, int32> Holdings;

	/** What the walker is carrying and has not handed over yet. */
	TMap<FName, int32> Carried;

	/** Plaque name -> the carving as it read when the walker last stood at it. */
	TMap<FString, FString> CarvingsRead;

	/** The wall as it stands THIS TICK. A frame-local cache, refilled every tick --
	 *  it exists to keep one world walk per frame instead of three, not to remember
	 *  anything between frames. */
	UPROPERTY(Transient)
	TArray<ARecipePlaqueActor*> LivePlaques;

	FString LastHeldLine;
	FString LastCanMakeLine;
};
