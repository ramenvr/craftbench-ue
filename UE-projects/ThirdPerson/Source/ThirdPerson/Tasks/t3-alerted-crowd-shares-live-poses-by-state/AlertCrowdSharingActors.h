// Copyright CraftBench. All Rights Reserved.
// Supplied runtime scaffold for task t3-alerted-crowd-shares-live-poses-by-state.

#pragma once

#include "CoreMinimal.h"
#include "AnimationSharingTypes.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "AlertCrowdSharingActors.generated.h"

class UAnimationSharingSetup;

UENUM(BlueprintType)
enum class EAlertCrowdSharingState : uint8
{
	Ordinary = 0,
	Alerted = 1,
};

/** Visible, moving subject whose public facts are consumed by the submitted
 * Animation Sharing state-processor Blueprint. */
UCLASS(BlueprintType)
class THIRDPERSON_API AAlertCrowdSharingSubject : public ACharacter
{
	GENERATED_BODY()

public:
	AAlertCrowdSharingSubject();
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Crowd")
	FName SubjectIdentity;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Crowd")
	int32 SlotIndex = INDEX_NONE;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Crowd")
	FName CrowdGroup;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Crowd")
	bool bAlerted = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Crowd")
	bool bSharingEligible = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Movement")
	FVector TravelDirection = FVector::ForwardVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Movement", meta = (ClampMin = "1.0"))
	float TravelSpeed = 145.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|Movement")
	bool bTravelEnabled = true;
};

/** Native shell for the editable BP state processor. It owns registration
 * safety and eligibility only; the submitted BP must read the live alert fact
 * and override EvaluateAlertState for state selection. */
UCLASS(Abstract, Blueprintable)
class THIRDPERSON_API UAlertCrowdSharingStateProcessorBase
	: public UAnimationSharingStateProcessor
{
	GENERATED_BODY()

public:
	virtual void ProcessActorState_Implementation(
		int32& OutState, AActor* InActor, uint8 CurrentState,
		uint8 OnDemandState, bool& bShouldProcess) override;

	virtual UEnum* GetAnimationStateEnum_Implementation() override;

	UFUNCTION(BlueprintNativeEvent, BlueprintPure, Category = "CraftBench|Crowd")
	EAlertCrowdSharingState EvaluateAlertState(
		const AAlertCrowdSharingSubject* Subject) const;
	virtual EAlertCrowdSharingState EvaluateAlertState_Implementation(
		const AAlertCrowdSharingSubject* Subject) const;

	UFUNCTION(BlueprintPure, Category = "CraftBench|Crowd")
	static EAlertCrowdSharingState ResolveAlertStateFromFlag(bool bAlerted);
};

/** One-shot runtime bootstrap. The setup remains a soft reference so the empty
 * submission map loads; absent/incomplete submission assets cannot create a
 * manager and therefore cannot be implemented by the fixture. */
UCLASS(BlueprintType)
class THIRDPERSON_API AAlertCrowdSharingHost : public AActor
{
	GENERATED_BODY()

public:
	AAlertCrowdSharingHost();
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "CraftBench|Crowd")
	TSoftObjectPtr<UAnimationSharingSetup> SharingSetup;

private:
	void InitializeSharingOnce();
};
