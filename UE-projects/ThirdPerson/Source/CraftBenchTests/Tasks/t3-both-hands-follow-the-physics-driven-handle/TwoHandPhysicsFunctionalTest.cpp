// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandPhysicsFunctionalTest.h"

#include "Animation/AnimClassInterface.h"
#include "AnimNode_ControlRig.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "ControlRig.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "Rigs/RigHierarchy.h"
#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandPhysicsActors.h"
#include "UObject/UnrealType.h"

namespace
{
	const FName BodyBones[] = {TEXT("pelvis"), TEXT("foot_l"), TEXT("foot_r")};
	const FName LeftControl(TEXT("hand_l_target"));
	const FName RightControl(TEXT("hand_r_target"));
	constexpr double CheckpointOffsets[] = {0.50, 0.75, 1.80, 1.90, 3.20, 3.30};
	constexpr bool bUsesWorldPostActorTick = true;
	constexpr bool bThresholdsFrozen = true;
	constexpr double FrozenHandleDisplacementMin = 4.0;
	constexpr double FrozenHandErrorMax = 18.0;
	constexpr double FrozenControlErrorMax = 2.0;
	constexpr double FrozenBodyTranslationMax = 8.0;
	constexpr double FrozenBodyAngularMaxDegrees = 15.0;

	bool IsFiniteTransform(const FTransform& Value)
	{
		return !Value.ContainsNaN() && Value.GetRotation().IsNormalized();
	}

	FString ExpectedAnimClass(const bool bAdmission)
	{
		return bAdmission
			? TEXT("/Game/__CraftBenchAdmission/t3-both-hands-follow-the-physics-driven-handle/ABP_TwoHandPhysicsAdmission.ABP_TwoHandPhysicsAdmission_C")
			: TEXT("/Game/Tasks/t3-both-hands-follow-the-physics-driven-handle/ABP_TwoHandPhysics.ABP_TwoHandPhysics_C");
	}

	FString ExpectedRigClass(const bool bAdmission)
	{
		return bAdmission
			? TEXT("/Game/__CraftBenchAdmission/t3-both-hands-follow-the-physics-driven-handle/CR_TwoHandPhysicsAdmission.CR_TwoHandPhysicsAdmission_C")
			: TEXT("/Game/Tasks/t3-both-hands-follow-the-physics-driven-handle/CR_TwoHandPhysics.CR_TwoHandPhysics_C");
	}
}

ATwoHandPhysicsFunctionalTest::ATwoHandPhysicsFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

FString ATwoHandPhysicsFunctionalTest::GetAuthoredContractFacts()
{
	TArray<FString> Offsets;
	for (const double Offset : CheckpointOffsets)
	{
		Offsets.Add(FString::Printf(TEXT("%.2f"), Offset));
	}
	return FString::Printf(
		TEXT("authored_contract=1 runtime_observed=0 world_post_delegate=%d world_clock=1 checkpoint_count=%d checkpoint_offsets=%s gates=4"),
		bUsesWorldPostActorTick ? 1 : 0, UE_ARRAY_COUNT(CheckpointOffsets),
		*FString::Join(Offsets, TEXT(",")));
}

void ATwoHandPhysicsFunctionalTest::HarnessError(const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Error,
		FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Detail));
}

void ATwoHandPhysicsFunctionalTest::FinishProblem(const FString& Detail)
{
	constexpr TCHAR SubmissionPrefix[] = TEXT("SUBMISSION: ");
	if (Detail.StartsWith(SubmissionPrefix))
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("BothHandsTrackSamePhysicalHandle: ")
				+ Detail.RightChop(FCString::Strlen(SubmissionPrefix)));
		return;
	}
	HarnessError(Detail);
}

bool ATwoHandPhysicsFunctionalTest::ResolveScenario(FString& OutProblem)
{
	if (GetWorld() == nullptr || ScenarioTag.IsNone())
	{
		OutProblem = TEXT("world missing or ScenarioTag is None");
		return false;
	}
	TArray<AActor*> Handles;
	TArray<AActor*> Subjects;
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), ATwoHandPhysicsHandle::StaticClass(), Handles);
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), ATwoHandRigCharacter::StaticClass(), Subjects);
	Handles = Handles.FilterByPredicate([this](const AActor* Actor)
	{
		return Actor && Actor->ActorHasTag(ScenarioTag);
	});
	Subjects = Subjects.FilterByPredicate([this](const AActor* Actor)
	{
		return Actor && Actor->ActorHasTag(ScenarioTag);
	});
	if (Handles.Num() != 1 || Subjects.Num() != 1)
	{
		OutProblem = FString::Printf(TEXT("scenario=%s handle_count=%d subject_count=%d"),
			*ScenarioTag.ToString(), Handles.Num(), Subjects.Num());
		return false;
	}
	Handle = Cast<ATwoHandPhysicsHandle>(Handles[0]);
	Subject = Cast<ATwoHandRigCharacter>(Subjects[0]);
	Mesh = Subject.IsValid() ? Subject->GetMesh() : nullptr;
	AnimInstance = Mesh.IsValid()
		? Cast<UTwoHandRigAnimInstanceBase>(Mesh->GetAnimInstance()) : nullptr;
	return Handle.IsValid() && Subject.IsValid() && Mesh.IsValid() && AnimInstance.IsValid();
}

bool ATwoHandPhysicsFunctionalTest::ValidateImmutableSubstrate(FString& OutProblem) const
{
	if (!Handle.IsValid() || !Subject.IsValid() || !Mesh.IsValid() || !AnimInstance.IsValid())
	{
		OutProblem = TEXT("resolved scenario identities are invalid");
		return false;
	}
	UStaticMeshComponent* Anchor = Handle->GetAnchorBody();
	UStaticMeshComponent* Body = Handle->GetHandleBody();
	UPhysicsConstraintComponent* Constraint = Handle->GetPhysicsConstraint();
	UPrimitiveComponent* First = nullptr;
	UPrimitiveComponent* Second = nullptr;
	FName FirstBone;
	FName SecondBone;
	if (Constraint)
	{
		Constraint->GetConstrainedComponents(First, FirstBone, Second, SecondBone);
	}
	if (Anchor == nullptr || Body == nullptr || Constraint == nullptr
		|| First != Anchor || Second != Body || !Body->IsSimulatingPhysics()
		|| !Constraint->ConstraintInstance.IsValidConstraintInstance()
		|| Constraint->IsBroken())
	{
		OutProblem = FString::Printf(
			TEXT("real constraint invalid anchor=%d body=%d constrained=%d/%d simulate=%d valid=%d broken=%d"),
			Anchor != nullptr, Body != nullptr, First == Anchor, Second == Body,
			Body && Body->IsSimulatingPhysics(),
			Constraint && Constraint->ConstraintInstance.IsValidConstraintInstance(),
			Constraint && Constraint->IsBroken());
		return false;
	}
	if (Subject->TrackedHandle != Handle.Get()
		|| Handle->GetAttachParentActor() != nullptr
		|| Subject->GetAttachParentActor() != nullptr
		|| Body->GetAttachParent() == Mesh.Get()
		|| Body->GetOwner() != Handle.Get())
	{
		OutProblem = TEXT("handle/subject ownership or attachment boundary changed");
		return false;
	}
	if (!Mesh->IsRegistered() || !Mesh->IsVisible() || Mesh->bHiddenInGame
		|| !Mesh->bRenderInMainPass || Mesh->GetSkeletalMeshAsset() == nullptr)
	{
		OutProblem = FString::Printf(TEXT("visible rig surface invalid anim=%s"),
			*GetPathNameSafe(Mesh->GetAnimClass()));
		return false;
	}
	if (GetPathNameSafe(Mesh->GetAnimClass()) != ExpectedAnimClass(IsAdmissionProbe()))
	{
		OutProblem = FString::Printf(
			TEXT("SUBMISSION: exact Animation Blueprint class changed got=%s"),
			*GetPathNameSafe(Mesh->GetAnimClass()));
		return false;
	}
	if (FirstImpulse.IsNearlyZero() || SecondImpulse.IsNearlyZero()
		|| FVector::DotProduct(FirstImpulse.GetSafeNormal(), SecondImpulse.GetSafeNormal()) > 0.75)
	{
		OutProblem = TEXT("fixture impulses are zero or insufficiently distinct");
		return false;
	}
	return true;
}

bool ATwoHandPhysicsFunctionalTest::ResolveLiveControlRig(
	UControlRig*& OutRig, FString& OutProblem) const
{
	OutRig = nullptr;
	UAnimInstance* Instance = AnimInstance.Get();
	IAnimClassInterface* AnimClass = Instance
		? IAnimClassInterface::GetFromClass(Instance->GetClass()) : nullptr;
	int32 NodeCount = 0;
	if (AnimClass)
	{
		for (const FStructProperty* Property : AnimClass->GetAnimNodeProperties())
		{
			if (Property && Property->Struct
				&& Property->Struct->IsChildOf(FAnimNode_ControlRig::StaticStruct()))
			{
				++NodeCount;
				FAnimNode_ControlRig* Node =
					Property->ContainerPtrToValuePtr<FAnimNode_ControlRig>(Instance);
				OutRig = Node ? Node->GetControlRig() : nullptr;
			}
		}
	}
	if (NodeCount != 1 || OutRig == nullptr
		|| GetPathNameSafe(OutRig->GetClass()) != ExpectedRigClass(IsAdmissionProbe()))
	{
		OutProblem = FString::Printf(TEXT("SUBMISSION: compiled runtime ControlRig count=%d rig_class=%s"),
			NodeCount, *GetPathNameSafe(OutRig ? OutRig->GetClass() : nullptr));
		return false;
	}
	if (OutRig->FindControl(LeftControl) == nullptr
		|| OutRig->FindControl(RightControl) == nullptr)
	{
		OutProblem = TEXT("SUBMISSION: declared hand_l_target/hand_r_target controls missing");
		return false;
	}
	return true;
}

bool ATwoHandPhysicsFunctionalTest::CaptureRestPose(FString& OutProblem)
{
	if (!Mesh.IsValid())
	{
		OutProblem = TEXT("mesh missing while capturing rest pose");
		return false;
	}
	for (int32 Index = 0; Index < UE_ARRAY_COUNT(BodyBones); ++Index)
	{
		RestBodyBones[Index] = Mesh->GetBoneTransform(BodyBones[Index], RTS_Component);
		if (!IsFiniteTransform(RestBodyBones[Index]))
		{
			OutProblem = FString::Printf(TEXT("SUBMISSION: non-finite rest body bone=%s"),
				*BodyBones[Index].ToString());
			return false;
		}
	}
	bRestCaptured = true;
	return true;
}

bool ATwoHandPhysicsFunctionalTest::SampleNow(
	double WorldSeconds, FLiveSample& OutSample, FString& OutProblem) const
{
	if (!ValidateImmutableSubstrate(OutProblem))
	{
		return false;
	}
	UControlRig* Rig = nullptr;
	if (!ResolveLiveControlRig(Rig, OutProblem))
	{
		return false;
	}
	URigHierarchy* Hierarchy = Rig->GetHierarchy();
	if (Hierarchy == nullptr)
	{
		OutProblem = TEXT("live ControlRig hierarchy missing");
		return false;
	}

	const FTransform HandleWorld = Handle->GetHandleBody()->GetComponentTransform();
	const FTransform LeftGrip = Handle->GetLeftGripWorldTransform();
	const FTransform RightGrip = Handle->GetRightGripWorldTransform();
	const FTransform LeftHand = Mesh->GetSocketTransform(TEXT("hand_l"), RTS_World);
	const FTransform RightHand = Mesh->GetSocketTransform(TEXT("hand_r"), RTS_World);
	const FTransform LeftControlValue = Hierarchy->GetGlobalTransform(
		FRigElementKey(LeftControl, ERigElementType::Control));
	const FTransform RightControlValue = Hierarchy->GetGlobalTransform(
		FRigElementKey(RightControl, ERigElementType::Control));
	if (!IsFiniteTransform(HandleWorld) || !IsFiniteTransform(LeftGrip)
		|| !IsFiniteTransform(RightGrip) || !IsFiniteTransform(LeftHand)
		|| !IsFiniteTransform(RightHand) || !IsFiniteTransform(LeftControlValue)
		|| !IsFiniteTransform(RightControlValue))
	{
		OutProblem = TEXT("SUBMISSION: non-finite hand or Control Rig transform");
		return false;
	}

	OutSample.WorldSeconds = WorldSeconds;
	OutSample.Leg = CurrentLeg;
	OutSample.HandleLocation = HandleWorld.GetLocation();
	OutSample.HandleVelocity = Handle->GetHandleBody()->GetPhysicsLinearVelocity();
	Handle->GetPhysicsConstraint()->GetConstraintForce(
		OutSample.ConstraintLinearForce, OutSample.ConstraintAngularForce);
	OutSample.LeftHandError = FVector::Distance(
		LeftHand.GetLocation(), LeftGrip.GetLocation());
	OutSample.RightHandError = FVector::Distance(
		RightHand.GetLocation(), RightGrip.GetLocation());
	OutSample.LeftControlError = FVector::Distance(
		LeftControlValue.GetLocation(), AnimInstance->LeftHandTarget.GetLocation());
	OutSample.RightControlError = FVector::Distance(
		RightControlValue.GetLocation(), AnimInstance->RightHandTarget.GetLocation());
	OutSample.TargetSerial = AnimInstance->TargetSampleSerial;
	if (bRestCaptured)
	{
		for (int32 Index = 0; Index < UE_ARRAY_COUNT(BodyBones); ++Index)
		{
			const FTransform Current = Mesh->GetBoneTransform(BodyBones[Index], RTS_Component);
			OutSample.FeetPelvisTranslationMax = FMath::Max(
				OutSample.FeetPelvisTranslationMax,
				FVector::Distance(Current.GetLocation(), RestBodyBones[Index].GetLocation()));
			OutSample.FeetPelvisAngularMaxDegrees = FMath::Max(
				OutSample.FeetPelvisAngularMaxDegrees,
				FMath::RadiansToDegrees(Current.GetRotation().AngularDistance(
					RestBodyBones[Index].GetRotation())));
		}
	}
	return true;
}

void ATwoHandPhysicsFunctionalTest::HandleWorldPostActorTick(
	UWorld* World, ELevelTick, float)
{
	if (World != GetWorld() || !IsRunning() || !bRestCaptured
		|| !TelemetryProblem.IsEmpty())
	{
		return;
	}
	++PostActorTickCallbacks;
	FLiveSample Sample;
	if (!SampleNow(World->GetTimeSeconds(), Sample, TelemetryProblem))
	{
		return;
	}
	Samples.Add(Sample);
}

bool ATwoHandPhysicsFunctionalTest::DeriveMetrics(
	FDerivedMetrics& OutMetrics, FString& OutProblem) const
{
	if (!TelemetryProblem.IsEmpty())
	{
		OutProblem = TelemetryProblem;
		return false;
	}
	const FVector FirstDirection = FirstImpulse.GetSafeNormal();
	const FVector SecondDirection = SecondImpulse.GetSafeNormal();
	for (const FLiveSample& Sample : Samples)
	{
		++OutMetrics.Samples;
		OutMetrics.LeftHandErrorMax = FMath::Max(OutMetrics.LeftHandErrorMax,
			Sample.LeftHandError);
		OutMetrics.RightHandErrorMax = FMath::Max(OutMetrics.RightHandErrorMax,
			Sample.RightHandError);
		OutMetrics.LeftControlErrorMax = FMath::Max(OutMetrics.LeftControlErrorMax,
			Sample.LeftControlError);
		OutMetrics.RightControlErrorMax = FMath::Max(OutMetrics.RightControlErrorMax,
			Sample.RightControlError);
		OutMetrics.FeetPelvisTranslationMax = FMath::Max(
			OutMetrics.FeetPelvisTranslationMax, Sample.FeetPelvisTranslationMax);
		OutMetrics.FeetPelvisAngularMaxDegrees = FMath::Max(
			OutMetrics.FeetPelvisAngularMaxDegrees, Sample.FeetPelvisAngularMaxDegrees);
		OutMetrics.ConstraintForceMax = FMath::Max(OutMetrics.ConstraintForceMax,
			Sample.ConstraintLinearForce.Size());
		if (OutMetrics.FirstTargetSerial == 0 && Sample.TargetSerial > 0)
		{
			OutMetrics.FirstTargetSerial = Sample.TargetSerial;
		}
		OutMetrics.LastTargetSerial = FMath::Max(
			OutMetrics.LastTargetSerial, Sample.TargetSerial);
		if (Sample.Leg == ESampleLeg::First)
		{
			++OutMetrics.FirstSamples;
			const FVector Delta = Sample.HandleLocation - FirstOrigin;
			OutMetrics.FirstDisplacementMax = FMath::Max(
				OutMetrics.FirstDisplacementMax, Delta.Size());
			OutMetrics.FirstDirectionProjectionMax = FMath::Max(
				OutMetrics.FirstDirectionProjectionMax,
				FVector::DotProduct(Delta, FirstDirection));
		}
		else if (Sample.Leg == ESampleLeg::Second)
		{
			++OutMetrics.SecondSamples;
			const FVector Delta = Sample.HandleLocation - SecondOrigin;
			OutMetrics.SecondDisplacementMax = FMath::Max(
				OutMetrics.SecondDisplacementMax, Delta.Size());
			OutMetrics.SecondDirectionProjectionMax = FMath::Max(
				OutMetrics.SecondDirectionProjectionMax,
				FVector::DotProduct(Delta, SecondDirection));
		}
	}
	if (OutMetrics.Samples <= 0 || OutMetrics.FirstSamples <= 0
		|| OutMetrics.SecondSamples <= 0 || PostActorTickCallbacks <= 0
		|| OutMetrics.FirstTargetSerial <= 0
		|| OutMetrics.LastTargetSerial <= OutMetrics.FirstTargetSerial)
	{
		OutProblem = FString::Printf(
			TEXT("telemetry incomplete callbacks=%d samples=%d first=%d second=%d serial=%d..%d"),
			PostActorTickCallbacks, OutMetrics.Samples, OutMetrics.FirstSamples,
			OutMetrics.SecondSamples, OutMetrics.FirstTargetSerial,
			OutMetrics.LastTargetSerial);
		return false;
	}
	return true;
}

void ATwoHandPhysicsFunctionalTest::EvaluateAdmission(const FDerivedMetrics& Metrics)
{
	if (Metrics.FirstDisplacementMax <= UE_KINDA_SMALL_NUMBER
		|| Metrics.SecondDisplacementMax <= UE_KINDA_SMALL_NUMBER
		|| Metrics.FirstDirectionProjectionMax <= UE_KINDA_SMALL_NUMBER
		|| Metrics.SecondDirectionProjectionMax <= UE_KINDA_SMALL_NUMBER
		|| Metrics.LeftControlErrorMax > FrozenControlErrorMax
		|| Metrics.RightControlErrorMax > FrozenControlErrorMax
		|| Metrics.LeftHandErrorMax > FrozenHandErrorMax * 2.0
		|| Metrics.RightHandErrorMax > FrozenHandErrorMax * 2.0
		|| !FMath::IsFinite(Metrics.LeftHandErrorMax)
		|| !FMath::IsFinite(Metrics.RightHandErrorMax)
		|| !FMath::IsFinite(Metrics.FeetPelvisTranslationMax))
	{
		HarnessError(TEXT("admission did not produce finite two-leg physics/pose telemetry"));
	}
}

void ATwoHandPhysicsFunctionalTest::EvaluateFinal(const FDerivedMetrics& Metrics)
{
	if (Metrics.FirstDisplacementMax < FrozenHandleDisplacementMin
		|| Metrics.SecondDisplacementMax < FrozenHandleDisplacementMin
		|| Metrics.ConstraintForceMax <= UE_KINDA_SMALL_NUMBER)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("HandleMovesThroughRealConstraint: first=%.3f second=%.3f force=%.3f"),
			Metrics.FirstDisplacementMax, Metrics.SecondDisplacementMax,
			Metrics.ConstraintForceMax));
		return;
	}
	UE_LOG(LogTemp, Display, TEXT("HandleMovesThroughRealConstraint: PASS"));

	if (Metrics.LeftHandErrorMax > FrozenHandErrorMax
		|| Metrics.RightHandErrorMax > FrozenHandErrorMax
		|| Metrics.LeftControlErrorMax > FrozenControlErrorMax
		|| Metrics.RightControlErrorMax > FrozenControlErrorMax)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("BothHandsTrackSamePhysicalHandle: hand=%.3f/%.3f control=%.3f/%.3f"),
			Metrics.LeftHandErrorMax, Metrics.RightHandErrorMax,
			Metrics.LeftControlErrorMax, Metrics.RightControlErrorMax));
		return;
	}
	UE_LOG(LogTemp, Display, TEXT("BothHandsTrackSamePhysicalHandle: PASS"));

	if (Metrics.SecondDirectionProjectionMax < FrozenHandleDisplacementMin
		|| FVector::DotProduct(FirstImpulse.GetSafeNormal(),
			SecondImpulse.GetSafeNormal()) > 0.75)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TrackingRespondsToSecondImpulseDirection: projection=%.3f"),
			Metrics.SecondDirectionProjectionMax));
		return;
	}
	UE_LOG(LogTemp, Display, TEXT("TrackingRespondsToSecondImpulseDirection: PASS"));

	if (Metrics.FeetPelvisTranslationMax > FrozenBodyTranslationMax
		|| Metrics.FeetPelvisAngularMaxDegrees > FrozenBodyAngularMaxDegrees)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("FeetAndPelvisPreserveBasePose: translation=%.3f angular=%.3f"),
			Metrics.FeetPelvisTranslationMax,
			Metrics.FeetPelvisAngularMaxDegrees));
		return;
	}
	UE_LOG(LogTemp, Display, TEXT("FeetAndPelvisPreserveBasePose: PASS"));
}

void ATwoHandPhysicsFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	FString Problem;
	if (!ResolveScenario(Problem) || !ValidateImmutableSubstrate(Problem))
	{
		FinishProblem(Problem);
		return;
	}
	PostActorTickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(
		this, &ATwoHandPhysicsFunctionalTest::HandleWorldPostActorTick);
	const double Start = GetWorld()->GetTimeSeconds();
	TArray<double> Schedule;
	for (const double Offset : CheckpointOffsets)
	{
		Schedule.Add(Start + Offset);
	}
	SetCheckpointSchedule(Schedule);
}

void ATwoHandPhysicsFunctionalTest::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	if (PostActorTickHandle.IsValid())
	{
		FWorldDelegates::OnWorldPostActorTick.Remove(PostActorTickHandle);
		PostActorTickHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}

void ATwoHandPhysicsFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double)
{
	if (!TelemetryProblem.IsEmpty())
	{
		FinishProblem(TelemetryProblem);
		return;
	}
	FString Problem;
	switch (CheckpointIndex)
	{
	case 0:
		if (!CaptureRestPose(Problem))
		{
			FinishProblem(Problem);
		}
		break;
	case 1:
		FirstOrigin = Handle->GetHandleBody()->GetComponentLocation();
		CurrentLeg = ESampleLeg::First;
		Handle->ApplyWorldImpulse(FirstImpulse);
		break;
	case 2:
		CurrentLeg = ESampleLeg::Between;
		break;
	case 3:
		SecondOrigin = Handle->GetHandleBody()->GetComponentLocation();
		CurrentLeg = ESampleLeg::Second;
		Handle->ApplyWorldImpulse(SecondImpulse);
		break;
	case 4:
	{
		CurrentLeg = ESampleLeg::Final;
		FDerivedMetrics Metrics;
		if (!DeriveMetrics(Metrics, Problem))
		{
			FinishProblem(Problem);
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("[CB-TWO-HAND-METRICS] mode=%s runtime_observed=1 scenario=%s callbacks=%d samples=%d first_n=%d second_n=%d displacement=%.6f/%.6f direction=%.6f/%.6f hand_error=%.6f/%.6f control_error=%.6f/%.6f body=%.6f/%.6f constraint_force=%.6f thresholds_frozen=%d"),
			IsAdmissionProbe() ? TEXT("admission") : TEXT("final"),
			*ScenarioTag.ToString(), PostActorTickCallbacks, Metrics.Samples,
			Metrics.FirstSamples, Metrics.SecondSamples,
			Metrics.FirstDisplacementMax, Metrics.SecondDisplacementMax,
			Metrics.FirstDirectionProjectionMax,
			Metrics.SecondDirectionProjectionMax, Metrics.LeftHandErrorMax,
			Metrics.RightHandErrorMax, Metrics.LeftControlErrorMax,
			Metrics.RightControlErrorMax, Metrics.FeetPelvisTranslationMax,
			Metrics.FeetPelvisAngularMaxDegrees, Metrics.ConstraintForceMax,
			bThresholdsFrozen ? 1 : 0);
		bAggregated = true;
		if (IsAdmissionProbe())
		{
			EvaluateAdmission(Metrics);
		}
		else
		{
			EvaluateFinal(Metrics);
		}
		break;
	}
	case 5:
		if (!bAggregated)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("FeetAndPelvisPreserveBasePose: aggregation did not run before sentinel"));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded,
			IsAdmissionProbe()
				? TEXT("TWO-HAND-PHYSICS-ADMISSION PASS runtime ControlRig and two-leg telemetry admitted; thresholds frozen")
				: TEXT("All four two-hand physics gates passed through the final sentinel."));
		break;
	default:
		break;
	}
}
