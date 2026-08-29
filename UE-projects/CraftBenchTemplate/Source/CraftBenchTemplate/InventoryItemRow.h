// Copyright CraftBench. All Rights Reserved.
//
// Substrate-provided row struct for task gp-inventory-stacking (the g2-1
// "Inventory" port). Defines the externally-stored, per-item-type configuration
// the inventory reads — here just the maximum stack size for a slot. The agent
// does NOT edit this; it reads MaxStackSize from the project's data table whose
// rows are this struct.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "InventoryItemRow.generated.h"

USTRUCT(BlueprintType)
struct FInventoryItemRow : public FTableRowBase
{
	GENERATED_BODY()

	// Maximum number of units of this item type that may occupy a single slot.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Inventory")
	int32 MaxStackSize = 1;
};
