// Copyright CraftBench. All Rights Reserved.
//
// A heap of raw stuff for task t3-forge-turns-what-you-bring-into-what-you-need.
//
// Everything a heap needs to SAY what it is and to BE taken is supplied and working:
// the pile you can see, the label over it, the three numbers a walker reads off it,
// and the switch that empties it. Nothing here decides when to throw that switch, and
// nothing here knows where the character is.
//
// THE THREE NUMBERS ARE THE HALL'S, NOT YOURS. IngredientId, UnitsInHeap and ReachUu
// are how the hall re-stocks itself part way through the run: they are written from
// outside, by name, while the level is playing. Keep them as properties with these
// names and these types.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IngredientHeapActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AIngredientHeapActor : public AActor
{
	GENERATED_BODY()

public:
	AIngredientHeapActor();

	/** The pile you can see. COLLISION IS OFF on purpose: the character has to be able
	 *  to stand in a heap to take it, and a solid heap would jam a route sooner or
	 *  later -- which reads as the submission's fault when it is the hall's. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Heap")
	UStaticMeshComponent* Heap = nullptr;

	/** Reads "NAME xN" -- what the heap is and how many units are in it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Heap")
	UTextRenderComponent* Label = nullptr;

	/** What this heap is. Read it off the heap: the hall re-stocks with a different
	 *  vocabulary part way through the run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Heap")
	FName IngredientId = NAME_None;

	/** How many units are standing here. Goes down by exactly what is taken, and is
	 *  zero once the last of it has been taken. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Heap")
	int32 UnitsInHeap = 0;

	/** How close somebody has to be before they can take THIS heap. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Heap")
	float ReachUu = 220.0f;

	/** THE SWITCH. Hands over AT MOST MaxUnits of what is standing here -- all of it
	 *  when MaxUnits covers the heap, and only part of it when it does not. What is
	 *  not handed over stays standing, and the label says so. Returns what was
	 *  actually handed over: 0 for a MaxUnits of zero or less, and 0 on an empty heap,
	 *  so calling it twice cannot double-count. */
	UFUNCTION(BlueprintCallable, Category = "Heap")
	int32 TakeUpTo(int32 MaxUnits);

	UFUNCTION(BlueprintPure, Category = "Heap")
	bool IsEmptied() const { return UnitsInHeap <= 0; }

	/** Rewrites the label from IngredientId/UnitsInHeap and shows or hides the pile to
	 *  match. Presentation only -- it decides nothing. Supplied so the hall's re-stock
	 *  and your own code write the same face. */
	UFUNCTION(BlueprintCallable, Category = "Heap")
	void RefreshLabel();

protected:
	virtual void BeginPlay() override;
};
