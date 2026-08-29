// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GuardVisibleAimFunctionalTest.generated.h"

class AGuardVisibleAimCharacter;
class AGuardVisibleAimGoal;
class AGuardVisibleAimOccluder;
class AGuardVisibleAimTarget;
class UGuardVisibleAimAnimInstance;
class USceneComponent;

UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API AGuardVisibleAimScenario : public AActor
{
	GENERATED_BODY()

public:
	AGuardVisibleAimScenario();

	UPROPERTY(VisibleAnywhere, Category = "CraftBench")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName ScenarioId;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TSubclassOf<UGuardVisibleAimAnimInstance> ExpectedAnimClass;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimCharacter> MainGuard;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimCharacter> ControlGuard;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimTarget> VisibleTarget;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimTarget> OccludedDecoy;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimOccluder> DecoyOccluder;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimOccluder> SwitchOccluder;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimGoal> MainGoal;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AGuardVisibleAimGoal> ControlGoal;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FVector SwitchOpenLocation = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FVector SwitchBlockedLocation = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	float ExpectedYawSign = 1.0f;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	float ExpectedPitchSign = 1.0f;
};

UCLASS(Abstract)
class CRAFTBENCHTESTS_API AGuardVisibleAimFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AGuardVisibleAimFunctionalTestBase(
		const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void StartTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName ScenarioTag;

	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	TWeakObjectPtr<AGuardVisibleAimScenario> Scenario;
	FVector MainStart = FVector::ZeroVector;
	FVector ControlStart = FVector::ZeroVector;
	FVector MainAtBlock = FVector::ZeroVector;
	FVector ControlAtBlock = FVector::ZeroVector;
	double PrepareEpoch = 0.0;
	double MaxMainFrameStep = 0.0;
	double MaxControlFrameStep = 0.0;
	double MaxActorFacingError = 0.0;
	FVector LastMain = FVector::ZeroVector;
	FVector LastControl = FVector::ZeroVector;
	int32 RevisionBeforeBlock = 0;
	int32 RevisionAfterForget = 0;
	bool bEverMovingMain = false;
	bool bEverMovingControl = false;

	bool EnsureRuntimeNavigationReady(FString& OutDetail);
	bool ResolveWorld(FString& OutDetail);
	bool CheckPerceivedIdentity(bool bExpectedVisible, FString& OutDetail) const;
	bool CheckAimOverlay(bool bExpectedActive, FString& OutDetail) const;
	bool CheckMovementPhase(const FVector& MainPhaseStart,
		const FVector& ControlPhaseStart, FString& OutDetail) const;
	void MoveSwitchOccluder(bool bBlocked);
	void EmitTelemetry(int32 CheckpointIndex, double TimeSeconds) const;
	void FailGate(const TCHAR* Gate, int32 CheckpointIndex,
		double TimeSeconds, const FString& Detail);
};

UCLASS()
class CRAFTBENCHTESTS_API AGuardVisibleAimLeftHighFunctionalTest
	: public AGuardVisibleAimFunctionalTestBase
{
	GENERATED_BODY()

public:
	AGuardVisibleAimLeftHighFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};

UCLASS()
class CRAFTBENCHTESTS_API AGuardVisibleAimRightLowFunctionalTest
	: public AGuardVisibleAimFunctionalTestBase
{
	GENERATED_BODY()

public:
	AGuardVisibleAimRightLowFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};

UCLASS()
class CRAFTBENCHTESTS_API AGuardVisibleAimAdmissionFunctionalTest
	: public AGuardVisibleAimFunctionalTestBase
{
	GENERATED_BODY()

public:
	AGuardVisibleAimAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};
