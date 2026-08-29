// DISCRIMINATION VARIANT hard-coded-cap (anti-gaming note #2) for task
// gp-inventory-stacking. Header is the reference's: the whole delta is in
// InventoryHostActor.cpp's MaxStackFor, which returns a hard-coded 10 for every
// item type instead of reading that type's MaxStackSize from the data table.

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
