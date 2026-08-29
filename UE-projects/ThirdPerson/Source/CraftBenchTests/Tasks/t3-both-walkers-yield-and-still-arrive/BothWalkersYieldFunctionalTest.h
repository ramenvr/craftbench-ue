// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "BothWalkersYieldFunctionalTest.generated.h"

class AAIController;
class AWalkerYieldCharacter;
class UCharacterMovementComponent;
class USceneComponent;

UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API AWalkerYieldScenarioActor : public AActor
{
	GENERATED_BODY()

public:
	AWalkerYieldScenarioActor();

	UPROPERTY(VisibleAnywhere, Category = "CraftBench")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName ScenarioId;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TSubclassOf<AWalkerYieldCharacter> ExpectedWalkerClass;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Pair")
	FName PairATag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Pair")
	FName PairBTag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Solo")
	FName SoloATag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Solo")
	FName SoloBTag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Goals")
	FName PairAGoalTag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Goals")
	FName PairBGoalTag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Goals")
	FName SoloAGoalTag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Goals")
	FName SoloBGoalTag;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Facts", meta = (ClampMin = "100.0"))
	float PairASpeed = 260.0f;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Facts", meta = (ClampMin = "100.0"))
	float PairBSpeed = 240.0f;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Facts", meta = (ClampMin = "20.0"))
	float PairARadius = 42.0f;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Facts", meta = (ClampMin = "20.0"))
	float PairBRadius = 48.0f;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Facts", meta = (ClampMin = "10.0"))
	float AcceptanceRadius = 70.0f;
};

UCLASS(Abstract)
class CRAFTBENCHTESTS_API ABothWalkersYieldFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ABothWalkersYieldFunctionalTestBase(
		const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void StartTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName ScenarioTag;

	virtual void OnCheckpoint(
		int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FTrackedWalker
	{
		FName SubjectTag;
		FName GoalTag;
		TWeakObjectPtr<AWalkerYieldCharacter> Character;
		TWeakObjectPtr<AAIController> Controller;
		TWeakObjectPtr<AActor> Goal;
		FVector Start = FVector::ZeroVector;
		FVector GoalLocation = FVector::ZeroVector;
		FVector PathDirection = FVector::ForwardVector;
		FVector LastLocation = FVector::ZeroVector;
		double PathLength = 0.0;
		double LastProgress = 0.0;
		double MaxProgress = 0.0;
		double MaxLateralDeviation = 0.0;
		double CurrentSteeringAngle = 0.0;
		double MaxSteeringAngle = 0.0;
		double MaxConflictSteeringAngle = 0.0;
		double MaxFrameStep = 0.0;
		double CurrentStallSeconds = 0.0;
		double MaxStallSeconds = 0.0;
		float Speed = 0.0f;
		float Radius = 0.0f;
		int32 MoveRequestResult = -1;
		bool bAvoidanceRegistrationSeen = false;
		bool bAvoidanceDataSeen = false;
		bool bStayedWalking = true;
	};

	TWeakObjectPtr<AWalkerYieldScenarioActor> Scenario;
	TArray<FTrackedWalker> Walkers;
	double PrepareEpochSeconds = 0.0;
	double MinPairClearance = TNumericLimits<double>::Max();
	double MinPreContactClearance = TNumericLimits<double>::Max();
	double ClosestPairCenterDistance = TNumericLimits<double>::Max();
	bool bMoveRequestsIssued = false;
	bool bConflictWindowObserved = false;
	FString AdmissionControl;
	bool bPermanentDetourInjected = false;

	bool EnsureRuntimeNavigationReady();
	bool ResolveScenarioAndWalkers();
	bool ResolveOneByTag(FName Tag, AActor*& OutActor, FString& OutDetail) const;
	bool ConfigureTrackedWalker(
		FTrackedWalker& Tracked, FName SubjectTag, FName GoalTag,
		float Speed, float Radius, FString& OutDetail);
	bool IssueMoveRequests(FString& OutDetail);
	void SampleDense(float DeltaSeconds);
	bool IsCollisionHealthy(const FTrackedWalker& Tracked, FString& OutDetail) const;
	bool ArePinnedIdentitiesValid(FString& OutDetail) const;
	void LogCheckpoint(int32 CheckpointIndex, double TimeSeconds) const;
	void FailGate(const TCHAR* Gate, double TimeSeconds, int32 CheckpointIndex,
		const FString& Detail);

	static constexpr double ConflictObservationRadiusUu = 720.0;
	static constexpr double PreContactClearanceUu = 24.0;
	static constexpr double FrozenMinSteeringAngleDeg = 3.0;
	static constexpr double FrozenPairOverSoloAngleDeg = 1.5;
	static constexpr double FrozenPairOverSoloLateralUu = 12.0;
	static constexpr double FrozenMinClearanceUu = 4.0;
	static constexpr double FrozenMaxStallSeconds = 0.75;
	static constexpr double FrozenMaxFrameStepUu = 28.0;
	static constexpr double FrozenArrivalBandUu = 115.0;
};

UCLASS()
class CRAFTBENCHTESTS_API ABothWalkersYieldLayoutAFunctionalTest
	: public ABothWalkersYieldFunctionalTestBase
{
	GENERATED_BODY()

public:
	ABothWalkersYieldLayoutAFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};

UCLASS()
class CRAFTBENCHTESTS_API ABothWalkersYieldLayoutBFunctionalTest
	: public ABothWalkersYieldFunctionalTestBase
{
	GENERATED_BODY()

public:
	ABothWalkersYieldLayoutBFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};

UCLASS()
class CRAFTBENCHTESTS_API ABothWalkersYieldAdmissionFunctionalTest
	: public ABothWalkersYieldFunctionalTestBase
{
	GENERATED_BODY()

public:
	ABothWalkersYieldAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer);
};
