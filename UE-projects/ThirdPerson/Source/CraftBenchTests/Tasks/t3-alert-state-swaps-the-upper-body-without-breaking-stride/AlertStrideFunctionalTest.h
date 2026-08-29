// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "AlertStrideFunctionalTest.generated.h"

class AAlertStrideCharacter;
class AAlertStrideScenario;
class AAlertStrideSignalActor;
class UAnimInstance;

UCLASS(Abstract)
class CRAFTBENCHTESTS_API AAlertStrideFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AAlertStrideFunctionalTestBase(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual void CleanUp() override;

	UPROPERTY()
	FName RequiredScenarioId;

private:
	bool ResolveScenario();
	bool ReadPose(FVector& OutLeftFoot, FVector& OutRightFoot,
		FVector& OutHandRelativeToPelvis) const;
	bool ValidateStableRuntime(const TCHAR* Gate);
	bool ValidateWalking(const TCHAR* Gate, double MinimumProgressFraction);
	bool ValidateLowerBodyWindow(const TCHAR* DetailLabel,
		const TArray<double>& Window) const;
	void FailGate(const TCHAR* Gate, const FString& Detail) const;

	TWeakObjectPtr<AAlertStrideScenario> Scenario;
	TWeakObjectPtr<AAlertStrideCharacter> Subject;
	TWeakObjectPtr<AAlertStrideSignalActor> Signal;
	TWeakObjectPtr<UAnimInstance> MainAnimInstance;
	FVector StartLocation = FVector::ZeroVector;
	FVector LastLocation = FVector::ZeroVector;
	FVector LastLeftFoot = FVector::ZeroVector;
	FVector LastRightFoot = FVector::ZeroVector;
	FVector CalmHandRelative = FVector::ZeroVector;
	FVector AlertHandRelative = FVector::ZeroVector;
	TArray<double> BaselineLowerSteps;
	TArray<double> AlertTransitionLowerSteps;
	TArray<double> ClearTransitionLowerSteps;
	double EpochSeconds = 0.0;
	double MaxActorFrameStep = 0.0;
	bool bHavePoseSample = false;
	bool bAlertRequested = false;
	bool bClearRequested = false;
};

UCLASS()
class CRAFTBENCHTESTS_API AAlertStrideSlowFunctionalTest
	: public AAlertStrideFunctionalTestBase
{
	GENERATED_BODY()

public:
	AAlertStrideSlowFunctionalTest(const FObjectInitializer& ObjectInitializer);
};

UCLASS()
class CRAFTBENCHTESTS_API AAlertStrideFastFunctionalTest
	: public AAlertStrideFunctionalTestBase
{
	GENERATED_BODY()

public:
	AAlertStrideFastFunctionalTest(const FObjectInitializer& ObjectInitializer);
};

UCLASS()
class CRAFTBENCHTESTS_API AAlertStrideAdmissionFunctionalTest
	: public AAlertStrideFunctionalTestBase
{
	GENERATED_BODY()

public:
	AAlertStrideAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};
