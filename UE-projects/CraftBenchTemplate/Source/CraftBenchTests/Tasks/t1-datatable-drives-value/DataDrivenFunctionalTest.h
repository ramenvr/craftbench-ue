// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADataDrivenFunctionalTest — L2 fixture for task t1-datatable-drives-value.
// PIE-native. Resolves the host by the "DataDrivenRoot" tag and reads its public
// ConfiguredValue float (by UPROPERTY reflection, so a subclass still works) at
// two checkpoints, asserting the value was populated from the data record's
// "Default" row (== the authored TunedValue, which is NOT disclosed to the
// agent) and stays stable.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "DataDrivenFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ADataDrivenFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ADataDrivenFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// Reads the host's ConfiguredValue float UPROPERTY by name (NaN if absent).
	float ReadConfiguredValue() const;

	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
};
