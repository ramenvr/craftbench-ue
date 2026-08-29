// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "TwoHandPhysicsFunctionalTest.generated.h"

class ATwoHandPhysicsHandle;
class ATwoHandRigCharacter;
class UControlRig;
class USkeletalMeshComponent;
class UTwoHandRigAnimInstanceBase;

/**
 * Same-frame behavior verifier.  Normal PIE owns all physics and animation
 * ticks; the fixture only schedules impulses and samples engine state.
 */
UCLASS()
class CRAFTBENCHTESTS_API ATwoHandPhysicsFunctionalTest
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ATwoHandPhysicsFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION(BlueprintPure, Category = "CraftBench|TwoHandPhysics")
	static FString GetAuthoredContractFacts();

	/** Exact per-instance world identity. Final map owns Quartz and Violet. */
	UPROPERTY(EditAnywhere, Category = "CraftBench|TwoHandPhysics")
	FName ScenarioTag = NAME_None;

	UPROPERTY(EditAnywhere, Category = "CraftBench|TwoHandPhysics")
	FVector FirstImpulse = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, Category = "CraftBench|TwoHandPhysics")
	FVector SecondImpulse = FVector::ZeroVector;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual bool IsAdmissionProbe() const { return false; }

private:
	enum class ESampleLeg : uint8 { Rest, First, Between, Second, Final };

	struct FLiveSample
	{
		double WorldSeconds = 0.0;
		ESampleLeg Leg = ESampleLeg::Rest;
		FVector HandleLocation = FVector::ZeroVector;
		FVector HandleVelocity = FVector::ZeroVector;
		FVector ConstraintLinearForce = FVector::ZeroVector;
		FVector ConstraintAngularForce = FVector::ZeroVector;
		double LeftHandError = 0.0;
		double RightHandError = 0.0;
		double LeftControlError = 0.0;
		double RightControlError = 0.0;
		double FeetPelvisTranslationMax = 0.0;
		double FeetPelvisAngularMaxDegrees = 0.0;
		int32 TargetSerial = 0;
	};

	struct FDerivedMetrics
	{
		int32 Samples = 0;
		int32 FirstSamples = 0;
		int32 SecondSamples = 0;
		double FirstDisplacementMax = 0.0;
		double SecondDisplacementMax = 0.0;
		double FirstDirectionProjectionMax = 0.0;
		double SecondDirectionProjectionMax = 0.0;
		double LeftHandErrorMax = 0.0;
		double RightHandErrorMax = 0.0;
		double LeftControlErrorMax = 0.0;
		double RightControlErrorMax = 0.0;
		double FeetPelvisTranslationMax = 0.0;
		double FeetPelvisAngularMaxDegrees = 0.0;
		double ConstraintForceMax = 0.0;
		int32 FirstTargetSerial = 0;
		int32 LastTargetSerial = 0;
	};

	bool ResolveScenario(FString& OutProblem);
	bool ValidateImmutableSubstrate(FString& OutProblem) const;
	bool ResolveLiveControlRig(UControlRig*& OutRig, FString& OutProblem) const;
	bool CaptureRestPose(FString& OutProblem);
	bool SampleNow(double WorldSeconds, FLiveSample& OutSample, FString& OutProblem) const;
	bool DeriveMetrics(FDerivedMetrics& OutMetrics, FString& OutProblem) const;
	void EvaluateAdmission(const FDerivedMetrics& Metrics);
	void EvaluateFinal(const FDerivedMetrics& Metrics);
	void HarnessError(const FString& Detail);
	void FinishProblem(const FString& Detail);
	void HandleWorldPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);

	TWeakObjectPtr<ATwoHandPhysicsHandle> Handle;
	TWeakObjectPtr<ATwoHandRigCharacter> Subject;
	TWeakObjectPtr<USkeletalMeshComponent> Mesh;
	TWeakObjectPtr<UTwoHandRigAnimInstanceBase> AnimInstance;
	TArray<FLiveSample> Samples;
	FTransform RestBodyBones[3];
	FVector FirstOrigin = FVector::ZeroVector;
	FVector SecondOrigin = FVector::ZeroVector;
	ESampleLeg CurrentLeg = ESampleLeg::Rest;
	FDelegateHandle PostActorTickHandle;
	FString TelemetryProblem;
	int32 PostActorTickCallbacks = 0;
	bool bRestCaptured = false;
	bool bAggregated = false;
};

/** Maintainer-only mechanism probe. It does not freeze final thresholds. */
UCLASS()
class CRAFTBENCHTESTS_API ATwoHandPhysicsAdmissionFunctionalTest
	: public ATwoHandPhysicsFunctionalTest
{
	GENERATED_BODY()

protected:
	virtual bool IsAdmissionProbe() const override { return true; }
};

/** Distinct automation identities for the two committed world fact sets. */
UCLASS()
class CRAFTBENCHTESTS_API ATwoHandPhysicsQuartzFunctionalTest
	: public ATwoHandPhysicsFunctionalTest
{
	GENERATED_BODY()
};

UCLASS()
class CRAFTBENCHTESTS_API ATwoHandPhysicsVioletFunctionalTest
	: public ATwoHandPhysicsFunctionalTest
{
	GENERATED_BODY()
};
