// Copyright CraftBench. All Rights Reserved.
// Runtime substrate for task t3-the-guard-resumes-patrol-after-the-chase.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "AI/Navigation/NavAgentInterface.h"
#include "BehaviorTree/Tasks/BTTask_BlackboardBase.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "GuardPatrolChaseTypes.generated.h"

class UBehaviorTree;
class UBehaviorTreeComponent;
class UBlackboardComponent;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
	FGuardAlertChanged, bool, bAlertActive, AActor*, LiveTarget);

UCLASS()
class THIRDPERSON_API AGuardAlertSource : public AActor
{
	GENERATED_BODY()

public:
	AGuardAlertSource();

	UPROPERTY(BlueprintAssignable, Category = "Guard Alert")
	FGuardAlertChanged OnAlertChanged;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Alert")
	TObjectPtr<UStaticMeshComponent> VisibleBody;

	UFUNCTION(BlueprintCallable, Category = "Guard Alert")
	void PublishAlert(AActor* InLiveTarget);

	UFUNCTION(BlueprintCallable, Category = "Guard Alert")
	void ClearAlert();

	UFUNCTION(BlueprintPure, Category = "Guard Alert")
	bool IsAlertActive() const { return bAlertActive; }

	UFUNCTION(BlueprintPure, Category = "Guard Alert")
	AActor* GetLiveTarget() const { return LiveTarget; }

private:
	UPROPERTY(Transient)
	TObjectPtr<AActor> LiveTarget;

	UPROPERTY(Transient)
	bool bAlertActive = false;
};

UCLASS()
class THIRDPERSON_API AGuardPatrolMarker : public AActor, public INavAgentInterface
{
	GENERATED_BODY()

public:
	AGuardPatrolMarker();

	virtual FVector GetNavAgentLocation() const override;
	virtual void GetMoveGoalReachTest(
		const AActor* MovingActor,
		const FVector& MoveOffset,
		FVector& GoalOffset,
		float& GoalRadius,
		float& GoalHalfHeight) const override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Patrol")
	TObjectPtr<UStaticMeshComponent> VisibleBody;
};

UCLASS()
class THIRDPERSON_API AGuardChaseTarget : public AActor
{
	GENERATED_BODY()

public:
	AGuardChaseTarget();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Chase")
	TObjectPtr<UStaticMeshComponent> VisibleBody;
};

UCLASS()
class THIRDPERSON_API AGuardPatrolCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AGuardPatrolCharacter();

	/** The exact editable tree supplied by the authored map. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Guard Decision")
	TObjectPtr<UBehaviorTree> DecisionTree;
};

UCLASS()
class THIRDPERSON_API AGuardPatrolAIController : public AAIController
{
	GENERATED_BODY()

public:
	AGuardPatrolAIController();

	UFUNCTION(BlueprintPure, Category = "Guard Decision")
	UBehaviorTreeComponent* GetGuardBehaviorTreeComponent() const
	{
		return BehaviorTreeComponent;
	}

	UFUNCTION(BlueprintPure, Category = "Guard Decision")
	UBlackboardComponent* GetGuardBlackboardComponent() const
	{
		return BlackboardComponent;
	}

	UFUNCTION(BlueprintPure, Category = "Guard Decision")
	AGuardAlertSource* GetBoundAlertSource() const { return BoundAlertSource; }

protected:
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;

private:
	void BindAlertSource();

	UFUNCTION()
	void HandleAlertChanged(bool bAlertActive, AActor* LiveTarget);

	UPROPERTY(VisibleAnywhere, Category = "Guard Decision")
	TObjectPtr<UBehaviorTreeComponent> BehaviorTreeComponent;

	UPROPERTY(VisibleAnywhere, Category = "Guard Decision")
	TObjectPtr<UBlackboardComponent> BlackboardComponent;

	UPROPERTY(Transient)
	TObjectPtr<AGuardAlertSource> BoundAlertSource;
};

/**
 * Supplied palette task. Each execution alternates between the two live tagged
 * route actors and stores that actor in the selected Blackboard object key.
 */
UCLASS()
class THIRDPERSON_API UGuardBTTask_SelectNextPatrolPoint : public UBTTask_BlackboardBase
{
	GENERATED_BODY()

public:
	UGuardBTTask_SelectNextPatrolPoint();

protected:
	virtual EBTNodeResult::Type ExecuteTask(
		UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
};
