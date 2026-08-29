// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "GameFramework/Character.h"
#include "Navigation/PathFollowingComponent.h"
#include "StateTreeConditionBase.h"
#include "StateTreeTaskBase.h"
#include "WorkerPlanStateTreeTypes.generated.h"

class UStateTree;
class UStateTreeAIComponent;

UCLASS(BlueprintType)
class THIRDPERSON_API AWorkerPlanSignalActor : public AActor
{
	GENERATED_BODY()

public:
	AWorkerPlanSignalActor();

	UFUNCTION(BlueprintCallable, Category = "Worker Plan")
	void PublishPlan(AActor* NewDestination);

	UFUNCTION(BlueprintCallable, Category = "Worker Plan")
	void ClearSignal();

	UFUNCTION(BlueprintPure, Category = "Worker Plan")
	bool IsSignalActive() const { return bSignalActive; }

	UFUNCTION(BlueprintPure, Category = "Worker Plan")
	AActor* GetPlanDestination() const { return PlanDestination.Get(); }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan")
	bool bSignalActive = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan")
	int32 PlanRevision = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan")
	TObjectPtr<AActor> PlanDestination;
};

UCLASS(BlueprintType)
class THIRDPERSON_API AWorkerPlanAIController : public AAIController
{
	GENERATED_BODY()

public:
	AWorkerPlanAIController(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "Worker Plan")
	bool ConfigureStateTree(UStateTree* StateTree);

	AWorkerPlanSignalActor* ResolveSignalActor();
	void RecordSignalRead(bool bPassed);
	void RecordNavigationEnter(EPathFollowingRequestResult::Type Result);
	void RecordNavigationExit();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan")
	TObjectPtr<UStateTreeAIComponent> StateTreeComponent;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan|Telemetry")
	int32 SignalReadCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan|Telemetry")
	int32 PassingSignalReadCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan|Telemetry")
	int32 NavigationEnterCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan|Telemetry")
	int32 NavigationExitCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Worker Plan|Telemetry")
	TEnumAsByte<EPathFollowingRequestResult::Type> LastMoveRequestResult = EPathFollowingRequestResult::Failed;

private:
	TWeakObjectPtr<AWorkerPlanSignalActor> CachedSignalActor;
};

UCLASS(BlueprintType)
class THIRDPERSON_API AWorkerPlanCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AWorkerPlanCharacter(const FObjectInitializer& ObjectInitializer);
};

USTRUCT()
struct THIRDPERSON_API FWorkerPlanSignalConditionInstanceData
{
	GENERATED_BODY()
};

USTRUCT(meta = (DisplayName = "Separate plan signal is active", Category = "Worker Plan"))
struct THIRDPERSON_API FWorkerPlanSignalCondition : public FStateTreeConditionCommonBase
{
	GENERATED_BODY()

	using FInstanceDataType = FWorkerPlanSignalConditionInstanceData;
	virtual const UStruct* GetInstanceDataType() const override { return FInstanceDataType::StaticStruct(); }
	virtual bool TestCondition(FStateTreeExecutionContext& Context) const override;
};

USTRUCT()
struct THIRDPERSON_API FWorkerPlanNavigateTaskInstanceData
{
	GENERATED_BODY()
};

USTRUCT(meta = (DisplayName = "Navigate to the published plan", Category = "Worker Plan"))
struct THIRDPERSON_API FWorkerPlanNavigateTask : public FStateTreeTaskCommonBase
{
	GENERATED_BODY()

	FWorkerPlanNavigateTask();
	using FInstanceDataType = FWorkerPlanNavigateTaskInstanceData;
	virtual const UStruct* GetInstanceDataType() const override { return FInstanceDataType::StaticStruct(); }
	virtual EStateTreeRunStatus EnterState(
		FStateTreeExecutionContext& Context,
		const FStateTreeTransitionResult& Transition) const override;
	virtual void ExitState(
		FStateTreeExecutionContext& Context,
		const FStateTreeTransitionResult& Transition) const override;
};
