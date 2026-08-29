// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "WorkerPlanFunctionalTest.generated.h"

class AWorkerPlanAIController;
class AWorkerPlanCharacter;
class AWorkerPlanSignalActor;
class ARecastNavMesh;
class UStateTree;

UCLASS()
class CRAFTBENCHTESTS_API AWorkerPlanFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AWorkerPlanFunctionalTest(const FObjectInitializer& ObjectInitializer);

	UPROPERTY(EditAnywhere, Category = "Worker Plan")
	TObjectPtr<UStateTree> ExpectedStateTree;

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool ResolveStaging();
	void FailGate(const TCHAR* Gate, const FString& Detail);

	TWeakObjectPtr<AWorkerPlanCharacter> Subject;
	TWeakObjectPtr<AWorkerPlanAIController> Controller;
	TWeakObjectPtr<AWorkerPlanSignalActor> Signal;
	TWeakObjectPtr<AActor> Destination;
	TWeakObjectPtr<ARecastNavMesh> RecastNavMesh;
	FVector StartLocation = FVector::ZeroVector;
	FVector LastTickLocation = FVector::ZeroVector;
	FVector LocationAtSignalClear = FVector::ZeroVector;
	int32 InitialNavigationPathPoints = 0;
	double MaxFrameStep = 0.0;
	bool bSignalPublished = false;
	bool bSignalCleared = false;
};
