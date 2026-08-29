// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AAdditemStackFunctionalTest implementation. The base owns the PIE lever,
// fixed timestep, and the checkpoint clock; this fixture owns the seam
// resolution (typed-parameter reflection) and the stacking gates. All FAIL
// message text is ASCII-only (the cp1252 log read-back rule); every gate
// fails through its OWN literal (the named-FAIL placement law).

#include "AdditemStackFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName StackHostTag(TEXT("StackHost"));
	static const FName AddItemName(TEXT("AddItem"));
	static const FName GetItemCountName(TEXT("GetItemCount"));
	static const FName GetStackCountName(TEXT("GetStackCount"));

	static const FName WoodId(TEXT("Wood"));
	static const FName StoneId(TEXT("Stone"));

	// Checkpoint schedule: the calls are synchronous; three checkpoints
	// keep the log phases legible. TimeLimit = last + margin (base).
	constexpr double CpFirstAdd = 0.5;
	constexpr double CpStacking = 1.0;
	constexpr double CpIsolation = 1.5;

	/** True iff Function's parameter list matches the expected shape:
	 *  the given (name-insensitive positional) input types and, when
	 *  bWantsIntReturn, exactly one int return property. Tolerant of
	 *  parameter NAMES (agents rename); intolerant of types/arity. */
	bool MatchesShape(const UFunction* Function, const int32 NameInputs,
	                  const int32 IntInputs, const bool bWantsIntReturn)
	{
		if (Function == nullptr)
		{
			return false;
		}
		int32 Names = 0, Ints = 0, Returns = 0, Others = 0;
		for (TFieldIterator<FProperty> It(Function);
		     It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			if (It->PropertyFlags & CPF_ReturnParm)
			{
				Returns += (CastField<FIntProperty>(*It) != nullptr) ? 1 : 100;
				continue;
			}
			if (It->PropertyFlags & CPF_OutParm)
			{
				// A BP function's single output arrives as an out parm when
				// not marked return; accept an int out as the return slot.
				if (CastField<FIntProperty>(*It) != nullptr)
				{
					Returns += 1;
					continue;
				}
				Others += 1;
				continue;
			}
			if (CastField<FNameProperty>(*It) != nullptr) { Names += 1; }
			else if (CastField<FIntProperty>(*It) != nullptr) { Ints += 1; }
			else { Others += 1; }
		}
		return Others == 0 && Names == NameInputs && Ints == IntInputs
			&& Returns == (bWantsIntReturn ? 1 : 0);
	}

	/** Writes the positional Name/int inputs into Buffer, calls, and (when
	 *  OutInt is non-null) reads the int return/out parm back. */
	bool InvokeTyped(UObject* Target, UFunction* Function, const FName* NameArg,
	                 const int32* IntArg, int32* OutInt)
	{
		if (Target == nullptr || Function == nullptr)
		{
			return false;
		}
		TArray<uint8> Buffer;
		Buffer.SetNumZeroed(FMath::Max<int32>(Function->ParmsSize, 1));
		for (TFieldIterator<FProperty> It(Function);
		     It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->InitializeValue_InContainer(Buffer.GetData());
		}
		bool bWroteName = false, bWroteInt = false;
		for (TFieldIterator<FProperty> It(Function);
		     It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			if (It->PropertyFlags & (CPF_ReturnParm | CPF_OutParm))
			{
				continue;
			}
			if (const FNameProperty* NameProp = CastField<FNameProperty>(*It))
			{
				if (NameArg != nullptr && !bWroteName)
				{
					NameProp->SetPropertyValue_InContainer(Buffer.GetData(), *NameArg);
					bWroteName = true;
				}
			}
			else if (const FIntProperty* IntProp = CastField<FIntProperty>(*It))
			{
				if (IntArg != nullptr && !bWroteInt)
				{
					IntProp->SetPropertyValue_InContainer(Buffer.GetData(), *IntArg);
					bWroteInt = true;
				}
			}
		}
		// Every input the caller supplied must have found a home, or the call
		// about to be made is NOT the call the caller asked for — do not make
		// it. (Pre-merge review 2026-08-12: without this, the void-returning
		// AddItem path reported success unconditionally, so its marshaling
		// gate could only ever fire on a null target. Note the flag rather
		// than an early return: InitializeValue_InContainer above must always
		// be paired with the DestroyValue_InContainer sweep below.)
		const bool bInputsBound =
			(NameArg == nullptr || bWroteName) && (IntArg == nullptr || bWroteInt);
		bool bReadOut = false;
		if (bInputsBound)
		{
			Target->ProcessEvent(Function, Buffer.GetData());
			bReadOut = (OutInt == nullptr);
			if (OutInt != nullptr)
			{
				for (TFieldIterator<FProperty> It(Function);
				     It && (It->PropertyFlags & CPF_Parm); ++It)
				{
					if (!(It->PropertyFlags & (CPF_ReturnParm | CPF_OutParm)))
					{
						continue;
					}
					if (const FIntProperty* IntProp = CastField<FIntProperty>(*It))
					{
						*OutInt = IntProp->GetPropertyValue_InContainer(Buffer.GetData());
						bReadOut = true;
						break;
					}
				}
			}
		}
		for (TFieldIterator<FProperty> It(Function);
		     It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->DestroyValue_InContainer(Buffer.GetData());
		}
		return bInputsBound && bReadOut;
	}
}

AAdditemStackFunctionalTest::AAdditemStackFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

UObject* AAdditemStackFunctionalTest::ResolveInventorySeam()
{
	if (!Host.IsValid())
	{
		return nullptr;
	}
	// The component carrying the contract is found by its SEAM, never by
	// class: any component (or the actor itself) exposing all three
	// reflected functions with the contracted shapes qualifies —
	// mechanism-free by design (agents may reparent/rename the component).
	TArray<UObject*> Candidates;
	Candidates.Add(Host.Get());
	for (UActorComponent* Component : Host->GetComponents())
	{
		if (Component != nullptr)
		{
			Candidates.Add(Component);
		}
	}
	for (UObject* Candidate : Candidates)
	{
		UFunction* Add = Candidate->FindFunction(AddItemName);
		UFunction* Item = Candidate->FindFunction(GetItemCountName);
		UFunction* Stack = Candidate->FindFunction(GetStackCountName);
		if (MatchesShape(Add, 1, 1, false)
			&& MatchesShape(Item, 1, 0, true)
			&& MatchesShape(Stack, 0, 0, true))
		{
			AddItemFn = Add;
			GetItemCountFn = Item;
			GetStackCountFn = Stack;
			return Candidate;
		}
	}
	return nullptr;
}

bool AAdditemStackFunctionalTest::CallAddItem(const FName ItemId, const int32 Count)
{
	return InvokeTyped(Inventory.Get(), AddItemFn, &ItemId, &Count, nullptr);
}

bool AAdditemStackFunctionalTest::CallGetItemCount(const FName ItemId, int32& OutCount)
{
	return InvokeTyped(Inventory.Get(), GetItemCountFn, &ItemId, nullptr, &OutCount);
}

bool AAdditemStackFunctionalTest::CallGetStackCount(int32& OutCount)
{
	return InvokeTyped(Inventory.Get(), GetStackCountFn, nullptr, nullptr, &OutCount);
}

void AAdditemStackFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, StackHostTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'StackHost' (the inventory holder) in the running level; found %d."), Found.Num()));
		return;
	}
	Host = Found[0];

	Inventory = ResolveInventorySeam();
	if (!Inventory.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No component on the host exposes the inventory contract: reflected 'AddItem' (name + whole number), 'GetItemCount' (name -> whole number) and 'GetStackCount' (-> whole number) - the interface is broken."));
		return;
	}

	int32 InitialStacks = -1;
	if (!CallGetStackCount(InitialStacks))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("GetStackCount() could not be driven through reflection (marshaling mismatch) - the interface is broken."));
		return;
	}
	if (InitialStacks != 0)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("The inventory did not start empty: GetStackCount() returned %d before any AddItem (expected 0)."), InitialStacks));
		return;
	}

	SetCheckpointSchedule({ CpFirstAdd, CpStacking, CpIsolation });
}

void AAdditemStackFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Inventory.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("The inventory component became invalid mid-run (checkpoint %d)."), CheckpointIndex));
		return;
	}

	// A marshaling failure fails through its OWN literal (the named-FAIL
	// placement law): "the harness could not drive the contract" is a
	// different fact from "the behavior is wrong", and no MATRIX row credits
	// this token — a broken seam is an UNCREDITED fault, never a scored gate.
	// (Review catch 2026-08-12: these returns were dropped, so a mid-run
	// marshaling mismatch would have surfaced as a misleading "did not
	// register" / "did not stack" and been credited to the model.)
	const auto FailMarshaling = [this](const TCHAR* Call) -> void
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("MARSHALING-FAULT: %s could not be driven through reflection mid-run - the contract changed shape after PrepareTest resolved it."), Call));
	};

	int32 Count = -1;
	switch (CheckpointIndex)
	{
	case 0:  // the first add must register (the BASELINE passes this)
		if (!CallAddItem(WoodId, 3))
		{
			FailMarshaling(TEXT("AddItem"));
			return;
		}
		if (!CallGetItemCount(WoodId, Count))
		{
			FailMarshaling(TEXT("GetItemCount"));
			return;
		}
		if (Count != 3)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("A first AddItem did not register: GetItemCount('Wood') returned %d after AddItem('Wood', 3) (expected 3)."), Count));
			return;
		}
		break;

	case 1:  // THE gates: stacking + no duplicate stack
		if (!CallAddItem(WoodId, 2))
		{
			FailMarshaling(TEXT("AddItem"));
			return;
		}
		if (!CallGetItemCount(WoodId, Count))
		{
			FailMarshaling(TEXT("GetItemCount"));
			return;
		}
		if (Count != 5)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Adding to an existing stack did not stack: GetItemCount('Wood') returned %d after AddItem('Wood', 3) then AddItem('Wood', 2) (expected 5)."), Count));
			return;
		}
		if (!CallGetStackCount(Count))
		{
			FailMarshaling(TEXT("GetStackCount"));
			return;
		}
		if (Count != 1)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The repeat AddItem minted a duplicate stack: GetStackCount() returned %d with only one distinct item added (expected 1)."), Count));
			return;
		}
		break;

	case 2:  // isolation: a different item is independent, both directions
	{
		if (!CallAddItem(StoneId, 4))
		{
			FailMarshaling(TEXT("AddItem"));
			return;
		}
		int32 Stone = -1, Wood = -1, Stacks = -1;
		if (!CallGetItemCount(StoneId, Stone) || !CallGetItemCount(WoodId, Wood)
			|| !CallGetStackCount(Stacks))
		{
			FailMarshaling(TEXT("a contract read"));
			return;
		}
		if (Stone != 4 || Wood != 5 || Stacks != 2)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("A later AddItem for a different item corrupted state: Wood=%d Stone=%d stacks=%d (expected 5, 4 and 2)."), Wood, Stone, Stacks));
			return;
		}
		// All gates green: the base finishes past the last checkpoint.
		break;
	}

	default:
		break;
	}
}
