// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GuardPatrolChaseFunctionalTest.generated.h"

class AGuardAlertSource;
class AGuardChaseTarget;
class AGuardPatrolAIController;
class AGuardPatrolCharacter;
class AGuardPatrolMarker;
class ARecastNavMesh;
class UBehaviorTree;
class UBlackboardData;

UCLASS()
class CRAFTBENCHTESTS_API AGuardPatrolChaseFunctionalTest
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AGuardPatrolChaseFunctionalTest(const FObjectInitializer& ObjectInitializer);

	UPROPERTY(EditAnywhere, Category = "Guard Patrol Chase")
	TObjectPtr<UBehaviorTree> ExpectedBehaviorTree;

	UPROPERTY(EditAnywhere, Category = "Guard Patrol Chase")
	TObjectPtr<UBlackboardData> ExpectedBlackboard;

	UPROPERTY(EditAnywhere, Category = "Guard Patrol Chase")
	FVector TargetVelocity = FVector(0.0, 135.0, 0.0);

protected:
	virtual void PrepareTest() override;
	virtual bool IsReady_Implementation() override;
	virtual void OnTimeout() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool ResolveProtectedWorld();
	bool ActiveMoveUses(FName KeyName, FString& OutDetail) const;
	void FailGate(const TCHAR* Gate, const FString& Detail);
	void EmitTelemetry(int32 CheckpointIndex, double TimeSeconds) const;

	TWeakObjectPtr<AGuardPatrolCharacter> Subject;
	TWeakObjectPtr<AGuardPatrolAIController> Controller;
	TWeakObjectPtr<AGuardAlertSource> AlertSource;
	TWeakObjectPtr<AGuardChaseTarget> Target;
	TWeakObjectPtr<AGuardPatrolMarker> MarkerA;
	TWeakObjectPtr<AGuardPatrolMarker> MarkerB;
	TWeakObjectPtr<ARecastNavMesh> RecastNavMesh;

	FVector InitialSubjectLocation = FVector::ZeroVector;
	FVector LastSubjectLocation = FVector::ZeroVector;
	FVector TargetOrigin = FVector::ZeroVector;
	double ChaseStartDistance = 0.0;
	double MaxFrameStep = 0.0;
	double BestDistanceToPostResetOther = TNumericLimits<double>::Max();
	int32 ReachedMarkerIndexAfterReset = INDEX_NONE;
	bool bAlertPublished = false;
	bool bAlertCleared = false;
	bool bObservedPostResetArrival = false;
	bool bObservedPostResetDeparture = false;
	bool bNavigationReady = false;
	int32 LastLoggedNavigationTiles = INDEX_NONE;
	FString NavigationReadinessDetail = TEXT("not-sampled");
};

/** Admission is a separate exact automation identity, not a second behavior. */
UCLASS()
class CRAFTBENCHTESTS_API AGuardPatrolChaseAdmissionTest
	: public AGuardPatrolChaseFunctionalTest
{
	GENERATED_BODY()
};
