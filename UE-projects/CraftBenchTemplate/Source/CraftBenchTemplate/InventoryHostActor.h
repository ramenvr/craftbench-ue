// Copyright CraftBench. All Rights Reserved.
//
// AInventoryHostActor — pre-existing actor for task gp-inventory-stacking. Holds
// a stackable-item inventory whose per-type stack caps come from the project's
// data table (ItemTypeTable). The constructor stamps the "InventoryRoot"
// identity tag. The four operations below are the fixed public contract —
// implement their bodies in InventoryHostActor.cpp; do NOT change the
// signatures. No inventory logic is provided; the required behavior is specified
// in the task prompt and is the agent's to implement.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InventoryHostActor.generated.h"

class UDataTable;

UCLASS()
class CRAFTBENCHTEMPLATE_API AInventoryHostActor : public AActor
{
	GENERATED_BODY()

public:
	AInventoryHostActor();

	// The project's item-type data table (rows = FInventoryItemRow). Assigned on
	// the placed instance. Read this for each type's MaxStackSize — do not
	// hard-code the per-type caps.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Inventory")
	UDataTable* ItemTypeTable;

	// --- FIXED operation contract (implement the bodies; do not change these) ---

	// Add Count units of ItemType: fill existing partial stacks of that type
	// first, then occupy empty slots, never exceeding the type's MaxStackSize in
	// any single slot. Returns true iff all Count units fit.
	virtual bool AddItem(FName ItemType, int32 Count);

	// Remove up to Count units of ItemType, freeing any slot that reaches zero.
	// Returns the number of units actually removed.
	virtual int32 RemoveItem(FName ItemType, int32 Count);

	// Total units of ItemType currently held across all slots.
	virtual int32 GetTotalQuantity(FName ItemType) const;

	// Number of slots currently occupied (holding >= 1 unit).
	virtual int32 GetOccupiedSlotCount() const;
};
