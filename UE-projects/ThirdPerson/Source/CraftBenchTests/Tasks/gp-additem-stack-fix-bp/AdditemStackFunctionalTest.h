// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AAdditemStackFunctionalTest — the gp-additem-stack-fix-bp fixture (the
// Edit(Debug) family's second member, reusing the door-hitch lane). The
// level places one host actor tagged 'StackHost' carrying the shipped
// inventory component whose Blueprint the agent EDITS in place; the
// baseline's add path mishandles the already-have-this-item case (a
// control-flow defect), and the graded fix is STACKING behavior, observed
// through the component's own reflected functions.
//
// Contract driven (typed ProcessEvent marshaling — the sprint seam idiom
// extended to parameters):
//   AddItem(ItemId: Name, Count: int)        mutator
//   GetItemCount(ItemId: Name) -> int        per-item total
//   GetStackCount() -> int                   number of distinct stacks
//
// Gates, each a distinct FinishTest(Failed) literal (ASCII only):
//   resolve      exactly one tagged host
//   seam         the three functions exist with the contracted shapes
//   empty start  GetStackCount()==0 before any AddItem
//   first add    AddItem registers a new item (the baseline PASSES this)
//   stacking     repeat AddItem accumulates (THE gate the baseline fails)
//   no dup stack repeat AddItem must not mint a second stack
//   isolation    a different item neither corrupts nor is corrupted
//
// No gameplay tags anywhere in this fixture (Editor-module native-tag
// hazard documented; actor tags are plain FNames).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"

#include "AdditemStackFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AAdditemStackFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AAdditemStackFunctionalTest(const FObjectInitializer& ObjectInitializer);

	/** Resolves the tagged host + the component carrying the inventory
	 *  seam, then sets the checkpoint schedule. */
	virtual void PrepareTest() override;

protected:
	/** The phase sequencer: drives the contract and evaluates the gates. */
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Finds, on any component of the host, the three reflected functions
	 *  with the contracted parameter shapes. Returns the owning component
	 *  (and fills the function pointers) or nullptr. */
	UObject* ResolveInventorySeam();

	/** Typed ProcessEvent wrappers; each returns false on a marshaling
	 *  mismatch (callers fail closed through the seam gate's literal). */
	bool CallAddItem(const FName ItemId, const int32 Count);
	bool CallGetItemCount(const FName ItemId, int32& OutCount);
	bool CallGetStackCount(int32& OutCount);

	TWeakObjectPtr<AActor> Host;
	TWeakObjectPtr<UObject> Inventory;
	UFunction* AddItemFn = nullptr;
	UFunction* GetItemCountFn = nullptr;
	UFunction* GetStackCountFn = nullptr;
};
