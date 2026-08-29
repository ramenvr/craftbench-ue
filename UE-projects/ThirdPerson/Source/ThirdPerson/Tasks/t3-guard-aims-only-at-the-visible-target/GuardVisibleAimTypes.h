// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "Animation/AnimInstance.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "Perception/AIPerceptionTypes.h"
#include "GuardVisibleAimTypes.generated.h"

class UAIPerceptionComponent;
class UAIPerceptionStimuliSourceComponent;
class UAISenseConfig_Sight;
class UStaticMeshComponent;

namespace GuardVisibleAim
{
	THIRDPERSON_API extern const FName GuardTag;
	THIRDPERSON_API extern const FName TargetTag;
	THIRDPERSON_API extern const FName OccluderTag;
	THIRDPERSON_API extern const FName GoalTag;
}

UCLASS(BlueprintType)
class THIRDPERSON_API UGuardVisibleAimAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	UPROPERTY(BlueprintReadOnly, Category = "Guard Aim")
	TObjectPtr<AActor> PerceivedTarget;

	UPROPERTY(BlueprintReadOnly, Category = "Guard Aim")
	float GroundSpeed = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Guard Aim")
	float AimYaw = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Guard Aim")
	float AimPitch = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Guard Aim")
	float AimAlpha = 0.0f;
};

UCLASS()
class THIRDPERSON_API AGuardVisibleAimController : public AAIController
{
	GENERATED_BODY()

public:
	AGuardVisibleAimController();

	UFUNCTION(BlueprintPure, Category = "Guard Aim")
	UAIPerceptionComponent* GetSightPerception() const { return SightPerception; }

	UFUNCTION(BlueprintPure, Category = "Guard Aim")
	AActor* GetCurrentVisibleTarget() const { return CurrentVisibleTarget; }

	UFUNCTION(BlueprintPure, Category = "Guard Aim")
	int32 GetPerceptionRevision() const { return PerceptionRevision; }

	/** Verifier control-twin setup; intentionally not exposed to Blueprint. */
	void DisableSightForControl();

protected:
	virtual void OnPossess(APawn* InPawn) override;

private:
	UFUNCTION()
	void HandleTargetPerceptionUpdated(AActor* Actor, FAIStimulus Stimulus);

	UFUNCTION()
	void HandleTargetForgotten(AActor* Actor);

	UPROPERTY(VisibleAnywhere, Category = "Guard Aim")
	TObjectPtr<UAIPerceptionComponent> SightPerception;

	UPROPERTY(VisibleAnywhere, Category = "Guard Aim")
	TObjectPtr<UAISenseConfig_Sight> SightConfig;

	UPROPERTY(Transient)
	TObjectPtr<AActor> CurrentVisibleTarget;

	UPROPERTY(Transient)
	int32 PerceptionRevision = 0;
};

UCLASS()
class THIRDPERSON_API AGuardVisibleAimCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AGuardVisibleAimCharacter();
};

UCLASS()
class THIRDPERSON_API AGuardVisibleAimTarget : public AActor
{
	GENERATED_BODY()

public:
	AGuardVisibleAimTarget();

protected:
	virtual void BeginPlay() override;

public:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Aim")
	TObjectPtr<UStaticMeshComponent> VisibleBody;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Aim")
	TObjectPtr<UAIPerceptionStimuliSourceComponent> SightStimulus;
};

UCLASS()
class THIRDPERSON_API AGuardVisibleAimOccluder : public AActor
{
	GENERATED_BODY()

public:
	AGuardVisibleAimOccluder();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Aim")
	TObjectPtr<UStaticMeshComponent> BlockingBody;
};

UCLASS()
class THIRDPERSON_API AGuardVisibleAimGoal : public AActor
{
	GENERATED_BODY()

public:
	AGuardVisibleAimGoal();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard Aim")
	TObjectPtr<UStaticMeshComponent> VisibleBody;
};
