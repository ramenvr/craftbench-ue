// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingIntrospectionLibrary.h"

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingActors.h"

#include "Animation/AnimSequence.h"
#include "AnimationSharingInstances.h"
#include "AnimationSharingSetup.h"
#include "AnimationSharingTypes.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/SkeletalMesh.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_VariableGet.h"

namespace
{
	const TCHAR MannyMeshPath[] =
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple");
	const TCHAR OrdinaryAnimationPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.MF_Unarmed_Walk_Fwd");
	const TCHAR AlertAnimationPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd.MF_Unarmed_Jog_Fwd");
	const FName EvaluateName(
		GET_FUNCTION_NAME_CHECKED(UAlertCrowdSharingStateProcessorBase,
			EvaluateAlertState));
	const FName ResolveFunctionName(
		GET_FUNCTION_NAME_CHECKED(UAlertCrowdSharingStateProcessorBase,
			ResolveAlertStateFromFlag));

	bool Linked(const UEdGraphPin* A, const UEdGraphPin* B)
	{
		return A != nullptr && B != nullptr && A->LinkedTo.Contains(B)
			&& B->LinkedTo.Contains(A);
	}

	UEdGraph* FindFunctionGraph(const UBlueprint* Blueprint, const FName Name)
	{
		if (Blueprint != nullptr)
		{
			for (UEdGraph* Graph : Blueprint->FunctionGraphs)
			{
				if (Graph != nullptr && Graph->GetFName() == Name)
				{
					return Graph;
				}
			}
		}
		return nullptr;
	}
}

FString UAlertCrowdSharingIntrospectionLibrary::InspectSharingSetup(
	const UAnimationSharingSetup* Setup,
	const UBlueprint* ProcessorBlueprint)
{
	if (Setup == nullptr || ProcessorBlueprint == nullptr
		|| ProcessorBlueprint->GeneratedClass == nullptr
		|| ProcessorBlueprint->ParentClass
			!= UAlertCrowdSharingStateProcessorBase::StaticClass()
		|| ProcessorBlueprint->GeneratedClass->GetSuperClass()
			!= UAlertCrowdSharingStateProcessorBase::StaticClass())
	{
		return TEXT("FAIL ASHARING_PROCESSOR_CLASS parent_or_generated_class_invalid");
	}
	if (Setup->SkeletonSetups.Num() != 1)
	{
		return FString::Printf(TEXT("FAIL ASHARING_SKELETON_SETUP_COUNT actual=%d"),
			Setup->SkeletonSetups.Num());
	}
	const FPerSkeletonAnimationSharingSetup& SkeletonSetup =
		Setup->SkeletonSetups[0];
	if (GetPathNameSafe(SkeletonSetup.SkeletalMesh) != MannyMeshPath
		|| SkeletonSetup.Skeleton == nullptr
		|| SkeletonSetup.SkeletalMesh->GetSkeleton() != SkeletonSetup.Skeleton)
	{
		return FString::Printf(TEXT(
			"FAIL ASHARING_SKELETON_IDENTITY mesh=%s skeleton=%s"),
			*GetPathNameSafe(SkeletonSetup.SkeletalMesh),
			*GetPathNameSafe(SkeletonSetup.Skeleton));
	}
	if (SkeletonSetup.StateProcessorClass.Get()
		!= ProcessorBlueprint->GeneratedClass
		|| SkeletonSetup.BlendAnimBlueprint != nullptr
		|| SkeletonSetup.AdditiveAnimBlueprint != nullptr)
	{
		return TEXT("FAIL ASHARING_PROCESSOR_OR_BLEND_PATH wrong class or independent blend BP");
	}
	if (SkeletonSetup.AnimationStates.Num() != 2
		|| Setup->ScalabilitySettings.UseBlendTransitions.Default)
	{
		return FString::Printf(TEXT(
			"FAIL ASHARING_STATE_COUNT_OR_BLEND states=%d blends=%d"),
			SkeletonSetup.AnimationStates.Num(),
			Setup->ScalabilitySettings.UseBlendTransitions.Default ? 1 : 0);
	}

	const TCHAR* ExpectedPaths[2] = {
		OrdinaryAnimationPath, AlertAnimationPath};
	for (int32 StateIndex = 0; StateIndex < 2; ++StateIndex)
	{
		const FAnimationStateEntry& State =
			SkeletonSetup.AnimationStates[StateIndex];
		if (State.State != StateIndex || State.bOnDemand
			|| State.AnimationSetups.Num() != 1)
		{
			return FString::Printf(TEXT(
				"FAIL ASHARING_STATE_ENTRY index=%d value=%d ondemand=%d setups=%d"),
				StateIndex, State.State, State.bOnDemand ? 1 : 0,
				State.AnimationSetups.Num());
		}
		const FAnimationSetup& Animation = State.AnimationSetups[0];
		if (GetPathNameSafe(Animation.AnimSequence) != ExpectedPaths[StateIndex]
			|| Animation.AnimBlueprint != nullptr
			|| Animation.NumRandomizedInstances.Default != 1
			|| !Animation.Enabled.Default)
		{
			return FString::Printf(TEXT(
				"FAIL ASHARING_ANIMATION_ENTRY index=%d asset=%s anim_bp=%s permutations=%d enabled=%d"),
				StateIndex, *GetPathNameSafe(Animation.AnimSequence),
				*GetPathNameSafe(Animation.AnimBlueprint.Get()),
				Animation.NumRandomizedInstances.Default,
				Animation.Enabled.Default ? 1 : 0);
		}
	}
	return FString::Printf(TEXT(
		"PASS setup=%s skeleton_setups=1 states=2 permutations=1+1 blends=0 processor=%s ordinary=%s alerted=%s"),
		*Setup->GetPathName(), *ProcessorBlueprint->GeneratedClass->GetPathName(),
		OrdinaryAnimationPath, AlertAnimationPath);
}

FString UAlertCrowdSharingIntrospectionLibrary::InspectStateProcessorGraph(
	const UBlueprint* ProcessorBlueprint)
{
	if (ProcessorBlueprint == nullptr || ProcessorBlueprint->GeneratedClass == nullptr
		|| ProcessorBlueprint->Status != BS_UpToDate
		|| ProcessorBlueprint->ParentClass
			!= UAlertCrowdSharingStateProcessorBase::StaticClass()
		|| ProcessorBlueprint->GeneratedClass->GetSuperClass()
			!= UAlertCrowdSharingStateProcessorBase::StaticClass())
	{
		return TEXT("FAIL ASHARING_BP_COMPILE_OR_PARENT");
	}
	UEdGraph* Graph = FindFunctionGraph(ProcessorBlueprint, EvaluateName);
	if (Graph == nullptr || Graph->Nodes.Num() != 4)
	{
		return FString::Printf(TEXT("FAIL ASHARING_GRAPH_SHAPE nodes=%d"),
			Graph ? Graph->Nodes.Num() : -1);
	}

	UK2Node_FunctionEntry* Entry = nullptr;
	UK2Node_FunctionResult* Result = nullptr;
	UK2Node_VariableGet* AlertGet = nullptr;
	UK2Node_CallFunction* Resolve = nullptr;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		Entry = Entry ? Entry : Cast<UK2Node_FunctionEntry>(Node);
		Result = Result ? Result : Cast<UK2Node_FunctionResult>(Node);
		if (UK2Node_VariableGet* Candidate = Cast<UK2Node_VariableGet>(Node))
		{
			if (Candidate->VariableReference.GetMemberName() ==
				GET_MEMBER_NAME_CHECKED(AAlertCrowdSharingSubject, bAlerted)
				&& Candidate->VariableReference.GetMemberParentClass()
					== AAlertCrowdSharingSubject::StaticClass())
			{
				AlertGet = Candidate;
			}
		}
		if (UK2Node_CallFunction* Candidate = Cast<UK2Node_CallFunction>(Node))
		{
			if (Candidate->FunctionReference.GetMemberName() == ResolveFunctionName
				&& Candidate->GetTargetFunction()
					== UAlertCrowdSharingStateProcessorBase::StaticClass()
						->FindFunctionByName(ResolveFunctionName))
			{
				Resolve = Candidate;
			}
			else
			{
				return FString::Printf(TEXT("FAIL ASHARING_FORBIDDEN_CALL function=%s"),
					*Candidate->FunctionReference.GetMemberName().ToString());
			}
		}
	}
	const UEdGraphPin* SubjectPin = Entry
		? Entry->FindPin(TEXT("Subject"), EGPD_Output) : nullptr;
	const UEdGraphPin* AlertSelf = AlertGet
		? AlertGet->FindPin(UEdGraphSchema_K2::PN_Self, EGPD_Input) : nullptr;
	const UEdGraphPin* AlertValue = AlertGet ? AlertGet->GetValuePin() : nullptr;
	const UEdGraphPin* ResolveInput = Resolve
		? Resolve->FindPin(TEXT("bAlerted"), EGPD_Input) : nullptr;
	const UEdGraphPin* ResolveOutput = Resolve
		? Resolve->FindPin(UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output) : nullptr;
	const UEdGraphPin* ResultInput = Result
		? Result->FindPin(UEdGraphSchema_K2::PN_ReturnValue, EGPD_Input) : nullptr;
	if (Entry == nullptr || Result == nullptr || AlertGet == nullptr
		|| Resolve == nullptr || !Linked(SubjectPin, AlertSelf)
		|| !Linked(AlertValue, ResolveInput)
		|| !Linked(ResolveOutput, ResultInput))
	{
		return TEXT("FAIL ASHARING_GRAPH_WIRING live Subject.bAlerted is not load-bearing");
	}
	for (const UEdGraph* Other : ProcessorBlueprint->FunctionGraphs)
	{
		if (Other != nullptr && Other != Graph && Other->Nodes.Num() > 0)
		{
			return TEXT("FAIL ASHARING_EXTRA_FUNCTION_GRAPH");
		}
	}
	for (const UEdGraph* Ubergraph : ProcessorBlueprint->UbergraphPages)
	{
		if (Ubergraph != nullptr && Ubergraph->Nodes.Num() > 0)
		{
			return TEXT("FAIL ASHARING_EVENT_GRAPH_NOT_EMPTY");
		}
	}
	return FString::Printf(TEXT(
		"PASS processor=%s compile=up_to_date graph=EvaluateAlertState nodes=4 live_alert_get=1 exact_resolver=1 extra_graphs=0"),
		*ProcessorBlueprint->GetPathName());
}
