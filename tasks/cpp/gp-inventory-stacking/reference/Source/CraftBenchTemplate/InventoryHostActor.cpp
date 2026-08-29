// Reference solution for task gp-inventory-stacking (the g2-1 "Inventory" port).
// Data-table-driven inventory: per-type stack caps come from ItemTypeTable
// (with a load-by-path fallback), slots fill partial-first then spill at the cap,
// and emptied slots are freed.

#include "InventoryHostActor.h"

#include "InventoryItemRow.h"
#include "Engine/DataTable.h"

AInventoryHostActor::AInventoryHostActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("InventoryRoot"));
	ItemTypeTable = nullptr;
}

void AInventoryHostActor::BeginPlay()
{
	Super::BeginPlay();
	Slots.Reset();
	Slots.SetNum(SlotCapacity);  // a fixed pool of empty slots
}

UDataTable* AInventoryHostActor::ResolveTable() const
{
	if (ItemTypeTable != nullptr)
	{
		return ItemTypeTable;
	}
	// Fallback to the known project path if the instance reference wasn't wired.
	return LoadObject<UDataTable>(nullptr, TEXT("/Game/Data/DT_InventoryItemTypes.DT_InventoryItemTypes"));
}

int32 AInventoryHostActor::MaxStackFor(FName ItemType) const
{
	if (const UDataTable* Table = ResolveTable())
	{
		if (const FInventoryItemRow* Row = Table->FindRow<FInventoryItemRow>(ItemType, TEXT("MaxStackFor"), false))
		{
			if (Row->MaxStackSize > 0)
			{
				return Row->MaxStackSize;
			}
		}
	}
	return 1;  // safe default when the type is unknown
}

bool AInventoryHostActor::AddItem(FName ItemType, int32 Count)
{
	if (Count <= 0)
	{
		return true;
	}
	const int32 MaxStack = MaxStackFor(ItemType);
	int32 Remaining = Count;

	// 1) fill existing partial stacks of this type first
	for (FInvSlot& S : Slots)
	{
		if (Remaining <= 0)
		{
			break;
		}
		if (S.Count > 0 && S.Type == ItemType && S.Count < MaxStack)
		{
			const int32 Add = FMath::Min(MaxStack - S.Count, Remaining);
			S.Count += Add;
			Remaining -= Add;
		}
	}

	// 2) then occupy empty slots, capping each at MaxStack
	for (FInvSlot& S : Slots)
	{
		if (Remaining <= 0)
		{
			break;
		}
		if (S.Count == 0)
		{
			const int32 Add = FMath::Min(MaxStack, Remaining);
			S.Type = ItemType;
			S.Count = Add;
			Remaining -= Add;
		}
	}

	return Remaining == 0;
}

int32 AInventoryHostActor::RemoveItem(FName ItemType, int32 Count)
{
	if (Count <= 0)
	{
		return 0;
	}
	int32 ToRemove = Count;
	int32 Removed = 0;
	for (FInvSlot& S : Slots)
	{
		if (ToRemove <= 0)
		{
			break;
		}
		if (S.Count > 0 && S.Type == ItemType)
		{
			const int32 Take = FMath::Min(S.Count, ToRemove);
			S.Count -= Take;
			ToRemove -= Take;
			Removed += Take;
			if (S.Count == 0)
			{
				S.Type = NAME_None;  // free the emptied slot
			}
		}
	}
	return Removed;
}

int32 AInventoryHostActor::GetTotalQuantity(FName ItemType) const
{
	int32 Total = 0;
	for (const FInvSlot& S : Slots)
	{
		if (S.Count > 0 && S.Type == ItemType)
		{
			Total += S.Count;
		}
	}
	return Total;
}

int32 AInventoryHostActor::GetOccupiedSlotCount() const
{
	int32 N = 0;
	for (const FInvSlot& S : Slots)
	{
		if (S.Count > 0)
		{
			++N;
		}
	}
	return N;
}
