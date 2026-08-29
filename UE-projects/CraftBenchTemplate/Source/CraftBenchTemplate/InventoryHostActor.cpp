// Copyright CraftBench. All Rights Reserved.
//
// AInventoryHostActor implementation for task gp-inventory-stacking. The
// constructor stamps the "InventoryRoot" identity tag. The four operations are
// empty stubs; the required behavior is specified in the task prompt and is the
// agent's to implement.

#include "InventoryHostActor.h"

AInventoryHostActor::AInventoryHostActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("InventoryRoot"));
	ItemTypeTable = nullptr;
}

bool AInventoryHostActor::AddItem(FName /*ItemType*/, int32 /*Count*/)
{
	return false;
}

int32 AInventoryHostActor::RemoveItem(FName /*ItemType*/, int32 /*Count*/)
{
	return 0;
}

int32 AInventoryHostActor::GetTotalQuantity(FName /*ItemType*/) const
{
	return 0;
}

int32 AInventoryHostActor::GetOccupiedSlotCount() const
{
	return 0;
}
