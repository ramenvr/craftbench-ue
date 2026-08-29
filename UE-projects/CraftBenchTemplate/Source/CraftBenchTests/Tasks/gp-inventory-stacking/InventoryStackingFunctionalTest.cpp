// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AInventoryStackingFunctionalTest implementation. Resolves the host by tag,
// casts via the substrate header, and drives the fixed operation contract at a
// 5-checkpoint schedule, asserting total quantity + occupied-slot invariants
// (with named failure messages). No internal state is read — only the contract's
// return values are observed.

#include "InventoryStackingFunctionalTest.h"

#include "InventoryHostActor.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName InventoryRootTag(TEXT("InventoryRoot"));
	static const FName StoneType(TEXT("Stone"));
	static const FName WoodType(TEXT("Wood"));
}

AInventoryStackingFunctionalTest::AInventoryStackingFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void AInventoryStackingFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, not by class — the agent may subclass the host.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, InventoryRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'InventoryRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Cast<AInventoryHostActor>(Found[0]);
	if (Host == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The 'InventoryRoot' actor is not an AInventoryHostActor (or a subclass); cannot drive the inventory contract."));
		return;
	}

	SetCheckpointSchedule({ 0.5, 1.5, 2.5, 3.5, 4.5 });
}

void AInventoryStackingFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (Host == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("Host went null mid-test."));
		return;
	}

	// Small helper macros via lambdas for named-assertion failures.
	auto FailTotal = [&](const TCHAR* Type, int32 Expected, int32 Got)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At t=%.2fs (checkpoint %d): expected total %s == %d; found %d."),
				TimeSeconds, CheckpointIndex, Type, Expected, Got));
	};
	auto FailOccupied = [&](int32 Expected, int32 Got)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At t=%.2fs (checkpoint %d): expected %d occupied slot(s); found %d."),
				TimeSeconds, CheckpointIndex, Expected, Got));
	};

	switch (CheckpointIndex)
	{
		case 0:
		{
			// AddItem(Stone,7): 7 < cap(10) -> one partial slot.
			const bool bFit = Host->AddItem(StoneType, 7);
			if (!bFit) { FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT("At t=%.2fs: AddItem(Stone,7) returned false; 7 units should fit."), TimeSeconds)); return; }
			const int32 Total = Host->GetTotalQuantity(StoneType);
			if (Total != 7) { FailTotal(TEXT("Stone"), 7, Total); return; }
			const int32 Occ = Host->GetOccupiedSlotCount();
			if (Occ != 1) { FailOccupied(1, Occ); return; }
			break;
		}
		case 1:
		{
			// AddItem(Stone,2): fill the partial 7-stack to 9 -> still ONE slot.
			Host->AddItem(StoneType, 2);
			const int32 Total = Host->GetTotalQuantity(StoneType);
			if (Total != 9) { FailTotal(TEXT("Stone"), 9, Total); return; }
			const int32 Occ = Host->GetOccupiedSlotCount();
			if (Occ != 1) { FailOccupied(1, Occ); return; }  // must fill partial, not open a new slot
			break;
		}
		case 2:
		{
			// AddItem(Stone,8): 9+8=17, cap 10 -> 10 + 7 across TWO slots.
			Host->AddItem(StoneType, 8);
			const int32 Total = Host->GetTotalQuantity(StoneType);
			if (Total != 17) { FailTotal(TEXT("Stone"), 17, Total); return; }
			const int32 Occ = Host->GetOccupiedSlotCount();
			if (Occ != 2) { FailOccupied(2, Occ); return; }  // spill at cap
			break;
		}
		case 3:
		{
			// AddItem(Wood,25): Wood caps at 20 (NOT 10) -> 20 + 5 across two slots.
			Host->AddItem(WoodType, 25);
			const int32 WoodTotal = Host->GetTotalQuantity(WoodType);
			if (WoodTotal != 25) { FailTotal(TEXT("Wood"), 25, WoodTotal); return; }
			const int32 StoneTotal = Host->GetTotalQuantity(StoneType);
			if (StoneTotal != 17) { FailTotal(TEXT("Stone"), 17, StoneTotal); return; }
			const int32 Occ = Host->GetOccupiedSlotCount();
			if (Occ != 4) { FailOccupied(4, Occ); return; }  // Stone:2 + Wood:2 — Wood cap must be 20
			break;
		}
		case 4:
		{
			// RemoveItem(Stone,15): 17-15=2 -> Stone collapses to one slot; Wood:2 stays.
			const int32 Removed = Host->RemoveItem(StoneType, 15);
			if (Removed != 15) { FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT("At t=%.2fs: RemoveItem(Stone,15) returned %d; expected 15."), TimeSeconds, Removed)); return; }
			const int32 StoneTotal = Host->GetTotalQuantity(StoneType);
			if (StoneTotal != 2) { FailTotal(TEXT("Stone"), 2, StoneTotal); return; }
			const int32 Occ = Host->GetOccupiedSlotCount();
			if (Occ != 3) { FailOccupied(3, Occ); return; }  // 1 Stone slot + 2 Wood slots; emptied slots freed
			// All five legs verified — the base finishes the test as success.
			break;
		}
		default:
			break;
	}
}
