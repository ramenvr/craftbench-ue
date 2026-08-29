// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AInventoryStackingFunctionalTest — L2 verifier fixture for task
// gp-inventory-stacking (the g2-1 "Inventory" port). Placed in
// L_InventoryStacking.umap alongside the InventoryRoot-tagged host. PIE-native:
// resolves the host by tag, then drives the host's fixed operation contract
// (AddItem/RemoveItem/GetTotalQuantity/GetOccupiedSlotCount) at a checkpoint
// schedule and asserts the evolving (total, occupied-slot) invariants. Caps come
// from the project data table (Stone=10, Wood=20), so a hard-coded single cap
// fails one type.
//
// Checkpoint contract (seconds since the PIE world began play, 60Hz):
//   t=0.5  AddItem(Stone,7)  -> total 7,  occupied 1   (partial single slot)
//   t=1.5  AddItem(Stone,2)  -> total 9,  occupied 1   (filled partial, no new slot)
//   t=2.5  AddItem(Stone,8)  -> total 17, occupied 2   (spill at cap 10 -> 10+7)
//   t=3.5  AddItem(Wood,25)  -> Wood 25, Stone 17, occupied 4 (Wood caps at 20)
//   t=4.5  RemoveItem(Stone,15)==15 -> Stone 2, occupied 3 (Stone collapses to 1 slot)

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "InventoryStackingFunctionalTest.generated.h"

class AInventoryHostActor;

UCLASS()
class CRAFTBENCHTESTS_API AInventoryStackingFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AInventoryStackingFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	UPROPERTY()
	AInventoryHostActor* Host = nullptr;
};
