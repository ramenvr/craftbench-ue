// Reference solution for task gp-inventory-stacking (the g2-1 "Inventory" port).
// Keeps the substrate constructor (the InventoryRoot tag + the ItemTypeTable
// reference) and the fixed operation contract, and adds the agent's
// responsibility: a fixed pool of slots, and data-table-driven add/remove math
// (fill-partial-first, spill at the per-type cap read from ItemTypeTable, free
// slots on empty).

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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Inventory")
	UDataTable* ItemTypeTable;

	virtual bool AddItem(FName ItemType, int32 Count);
	virtual int32 RemoveItem(FName ItemType, int32 Count);
	virtual int32 GetTotalQuantity(FName ItemType) const;
	virtual int32 GetOccupiedSlotCount() const;

protected:
	virtual void BeginPlay() override;

private:
	struct FInvSlot
	{
		FName Type = NAME_None;
		int32 Count = 0;
	};

	TArray<FInvSlot> Slots;
	static constexpr int32 SlotCapacity = 20;

	int32 MaxStackFor(FName ItemType) const;
	UDataTable* ResolveTable() const;
};
