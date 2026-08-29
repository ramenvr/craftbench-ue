// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "GameFramework/Character.h"
#include "StateTreeConditionBase.h"
#include "StateTreeTaskBase.h"
#include "AlertStrideTypes.generated.h"

class UAnimLayerInterface;
class UStateTree;
class UStateTreeComponent;

// AAlertStrideSignalActor - supplied world signal for task t3-alert-state-swaps-the-upper-body-without-breaking-stride.
UCLASS(BlueprintType)
class THIRDPERSON_API AAlertStrideSignalActor : public AActor
{
	GENERATED_BODY()

public:
	AAlertStrideSignalActor();

	UFUNCTION(BlueprintCallable, Category = "Alert Stride")
	void SetAlertActive(bool bNewAlertActive);

	UFUNCTION(BlueprintPure, Category = "Alert Stride")
	bool IsAlertActive() const { return bAlertActive; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alert Stride")
	bool bAlertActive = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alert Stride")
	int32 Revision = 0;
};

UCLASS(BlueprintType)
class THIRDPERSON_API UAlertStrideAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	UPROPERTY(BlueprintReadOnly, Category = "Alert Stride")
	float GroundSpeed = 0.0f;
};

UCLASS(BlueprintType)
class THIRDPERSON_API AAlertStrideCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AAlertStrideCharacter(const FObjectInitializer& ObjectInitializer);

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category = "Alert Stride")
	bool StartScenario(UStateTree* StateTree, AAlertStrideSignalActor* Signal,
		float WalkSpeed, FVector WorldDirection);

	UFUNCTION(BlueprintCallable, Category = "Alert Stride")
	void StopScenario();

	UFUNCTION(BlueprintPure, Category = "Alert Stride")
	TArray<FName> GetEngineActiveStateNames() const;

	UFUNCTION(BlueprintPure, Category = "Alert Stride")
	AAlertStrideSignalActor* GetSignalActor() const { return SignalActor.Get(); }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alert Stride")
	TObjectPtr<UStateTreeComponent> BehaviorStateTree;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alert Stride")
	TObjectPtr<AAlertStrideSignalActor> SignalActor;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alert Stride")
	FVector DriveDirection = FVector::ForwardVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alert Stride")
	bool bDriveEnabled = false;
};

UCLASS(BlueprintType)
class THIRDPERSON_API AAlertStrideScenario : public AActor
{
	GENERATED_BODY()

public:
	AAlertStrideScenario();

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	FName ScenarioId;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	TObjectPtr<AAlertStrideCharacter> Subject;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	TObjectPtr<AAlertStrideSignalActor> Signal;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	TObjectPtr<UStateTree> StateTree;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	TSubclassOf<UAnimLayerInterface> LayerInterfaceClass;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	TSubclassOf<UAnimInstance> CalmLayerClass;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	TSubclassOf<UAnimInstance> AlertLayerClass;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	float WalkSpeed = 220.0f;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	FVector TravelDirection = FVector::ForwardVector;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	double AlertDelay = 0.85;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	double ClearDelay = 1.75;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Alert Stride")
	double EndDelay = 2.65;
};

USTRUCT()
struct THIRDPERSON_API FAlertStrideSignalConditionInstanceData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = "Alert Stride")
	bool bExpectedAlert = true;
};

USTRUCT(meta = (DisplayName = "World alert matches", Category = "Alert Stride"))
struct THIRDPERSON_API FAlertStrideSignalCondition
	: public FStateTreeConditionCommonBase
{
	GENERATED_BODY()

	using FInstanceDataType = FAlertStrideSignalConditionInstanceData;
	virtual const UStruct* GetInstanceDataType() const override
	{
		return FInstanceDataType::StaticStruct();
	}
	virtual bool TestCondition(FStateTreeExecutionContext& Context) const override;
};

USTRUCT()
struct THIRDPERSON_API FAlertStrideLinkLayerTaskInstanceData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = "Alert Stride")
	TSubclassOf<UAnimInstance> AlertLayerClass;
};

USTRUCT(meta = (DisplayName = "Link declared alert layer", Category = "Alert Stride"))
struct THIRDPERSON_API FAlertStrideLinkLayerTask
	: public FStateTreeTaskCommonBase
{
	GENERATED_BODY()

	FAlertStrideLinkLayerTask();
	using FInstanceDataType = FAlertStrideLinkLayerTaskInstanceData;
	virtual const UStruct* GetInstanceDataType() const override
	{
		return FInstanceDataType::StaticStruct();
	}
	virtual EStateTreeRunStatus EnterState(
		FStateTreeExecutionContext& Context,
		const FStateTreeTransitionResult& Transition) const override;
	virtual void ExitState(
		FStateTreeExecutionContext& Context,
		const FStateTreeTransitionResult& Transition) const override;
};
