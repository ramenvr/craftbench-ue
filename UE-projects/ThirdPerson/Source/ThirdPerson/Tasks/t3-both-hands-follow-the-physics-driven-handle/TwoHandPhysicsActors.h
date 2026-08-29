// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "GameFramework/Character.h"
#include "GameFramework/Actor.h"
#include "TwoHandPhysicsActors.generated.h"

class UPhysicsConstraintComponent;
class USceneComponent;
class UStaticMeshComponent;

/**
 * Supplied world mechanism.  The simulated body is constrained to its own
 * anchor; it is deliberately independent of the character and either hand.
 */
UCLASS(Blueprintable)
class THIRDPERSON_API ATwoHandPhysicsHandle : public AActor
{
	GENERATED_BODY()

public:
	ATwoHandPhysicsHandle();
	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "Two Hand Physics")
	void ApplyWorldImpulse(const FVector& WorldImpulse);

	UFUNCTION(BlueprintPure, Category = "Two Hand Physics")
	FTransform GetLeftGripWorldTransform() const;

	UFUNCTION(BlueprintPure, Category = "Two Hand Physics")
	FTransform GetRightGripWorldTransform() const;

	UFUNCTION(BlueprintPure, Category = "Two Hand Physics")
	UStaticMeshComponent* GetAnchorBody() const { return AnchorBody; }

	UFUNCTION(BlueprintPure, Category = "Two Hand Physics")
	UStaticMeshComponent* GetHandleBody() const { return HandleBody; }

	UFUNCTION(BlueprintPure, Category = "Two Hand Physics")
	UPhysicsConstraintComponent* GetPhysicsConstraint() const { return Constraint; }

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	FName ScenarioId = NAME_None;

	/** Asymmetric local endpoints; the two fixture instances use different values. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	FTransform LeftGripLocal = FTransform(FRotator::ZeroRotator, FVector(0.0, -48.0, 0.0));

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	FTransform RightGripLocal = FTransform(FRotator::ZeroRotator, FVector(0.0, 48.0, 0.0));

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	TObjectPtr<UStaticMeshComponent> AnchorBody;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	TObjectPtr<UStaticMeshComponent> HandleBody;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Two Hand Physics")
	TObjectPtr<UPhysicsConstraintComponent> Constraint;
};

/**
 * Supplied playable surface.  Tick only copies two physical grip transforms
 * into component-space inputs.  It never writes a bone, runs IK, or moves the
 * handle; the editable Control Rig and AnimGraph must perform the pose solve.
 */
UCLASS(Blueprintable)
class THIRDPERSON_API ATwoHandRigCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ATwoHandRigCharacter();
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Two Hand Physics")
	TObjectPtr<ATwoHandPhysicsHandle> TrackedHandle;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient,
		Category = "Two Hand Physics")
	FTransform LeftHandTarget = FTransform::Identity;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient,
		Category = "Two Hand Physics")
	FTransform RightHandTarget = FTransform::Identity;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient,
		Category = "Two Hand Physics")
	int32 TargetSampleSerial = 0;
};

/**
 * Native input bridge for the supplied Animation Blueprint.  The class is a
 * transport surface only; it contains no Control Rig, IK, or pose-writer code.
 */
UCLASS(Abstract, Blueprintable, BlueprintType)
class THIRDPERSON_API UTwoHandRigAnimInstanceBase : public UAnimInstance
{
	GENERATED_BODY()

public:
	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Two Hand Physics")
	FTransform LeftHandTarget = FTransform::Identity;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Two Hand Physics")
	FTransform RightHandTarget = FTransform::Identity;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Two Hand Physics")
	bool bRigEnabled = false;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Two Hand Physics")
	int32 TargetSampleSerial = 0;
};
