// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADataDrivenFunctionalTest implementation. PIE-native: the engine ticks; the
// fixture reads the host's ConfiguredValue at checkpoints. The expected value
// mirrors the TunedValue the scaffolder authored into DT_Tuning's "Default" row
// (kept in sync here; NOT disclosed to the agent, so only a real record lookup
// matches).

#include "DataDrivenFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName DataDrivenRootTag(TEXT("DataDrivenRoot"));

	// The value the scaffolder authors into DT_Tuning's "Default" row (TunedValue).
	// Non-round + undisclosed so a hardcoded guess is implausible. Keep in sync
	// with Tools/scaffold_L_DataDriven.py.
	constexpr double ExpectedRowValue = 42.5;
	constexpr double Tolerance = 0.01;
}

ADataDrivenFunctionalTest::ADataDrivenFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ADataDrivenFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, DataDrivenRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'DataDrivenRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];
	// After BeginPlay (row lookup applied), then stable.
	SetCheckpointSchedule({ 1.0, 2.0 });
}

float ADataDrivenFunctionalTest::ReadConfiguredValue() const
{
	if (Host == nullptr)
	{
		return TNumericLimits<float>::Lowest();
	}
	FProperty* Prop = Host->GetClass()->FindPropertyByName(FName(TEXT("ConfiguredValue")));
	const FFloatProperty* FloatProp = CastField<FFloatProperty>(Prop);
	if (FloatProp == nullptr)
	{
		return TNumericLimits<float>::Lowest();
	}
	return FloatProp->GetPropertyValue_InContainer(Host);
}

void ADataDrivenFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	const float Value = ReadConfiguredValue();

	if (Value <= TNumericLimits<float>::Lowest() + 1.0f)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Could not read a float 'ConfiguredValue' UPROPERTY on the DataDrivenRoot actor."));
		return;
	}

	// idx 0 (t=1.0): value must have been populated from the record's Default row.
	// idx 1 (t=2.0): value persists.
	if (FMath::Abs(static_cast<double>(Value) - ExpectedRowValue) > Tolerance)
	{
		// Message-only literal split (2026-08-17): one Failed literal per failure
		// reason. The gate predicate and every verdict are unchanged - any
		// out-of-tolerance value still FAILs; the branch only picks the message.
		if (FMath::Abs(static_cast<double>(Value) - (-1.0)) <= Tolerance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs ConfiguredValue still reads the -1 sentinel: the DT_Tuning 'Default' row's TunedValue was never applied."),
					TimeSeconds));
			return;
		}
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs ConfiguredValue=%.4f, expected %.4f: a wrong value means it wasn't read from the DT_Tuning 'Default' record."),
				TimeSeconds, Value, ExpectedRowValue));
		return;
	}
}
