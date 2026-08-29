// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingAssetAuthoring.h"

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingActors.h"
#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingIntrospectionLibrary.h"

#include "Animation/AnimSequence.h"
#include "AnimationSharingSetup.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/SkeletalMesh.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

namespace
{
	const FString AdmissionRoot =
		TEXT("/Game/__CraftBenchAdmission/t3-alerted-crowd-shares-live-poses-by-state");
	const FString FinalRoot =
		TEXT("/Game/Tasks/t3-alerted-crowd-shares-live-poses-by-state");
	const FName SetupAdmissionName(TEXT("AS_AlertCrowdSharing_Admission"));
	const FName ProcessorAdmissionName(TEXT("BP_AlertCrowdStateProcessor_Admission"));
	const FName SetupFinalName(TEXT("AS_AlertCrowdSharing"));
	const FName ProcessorFinalName(TEXT("BP_AlertCrowdStateProcessor"));

	FString ObjectPath(const FString& Root, const FName Name)
	{
		return Root + TEXT("/") + Name.ToString() + TEXT(".") + Name.ToString();
	}

	bool RefuseExisting(const FString& Root, const FName Name)
	{
		const FString PackageName = Root + TEXT("/") + Name.ToString();
		return FindPackage(nullptr, *PackageName) == nullptr
			&& !FPackageName::DoesPackageExist(PackageName);
	}

	bool SaveAsset(UObject* Asset)
	{
		UPackage* Package = Asset ? Asset->GetOutermost() : nullptr;
		if (Package == nullptr)
		{
			return false;
		}
		Package->MarkPackageDirty();
		const FString Filename = FPackageName::LongPackageNameToFilename(
			Package->GetName(), FPackageName::GetAssetPackageExtension());
		FSavePackageArgs Args;
		Args.TopLevelFlags = RF_Public | RF_Standalone;
		Args.SaveFlags = SAVE_NoError;
		Args.Error = GError;
		return UPackage::SavePackage(Package, nullptr, *Filename, Args);
	}

	bool Connect(const UEdGraphSchema_K2* Schema,
		UEdGraphPin* A, UEdGraphPin* B)
	{
		return Schema != nullptr && A != nullptr && B != nullptr
			&& Schema->TryCreateConnection(A, B);
	}

	bool BuildEvaluateGraph(UBlueprint* Blueprint)
	{
		const FName FunctionName(
			GET_FUNCTION_NAME_CHECKED(UAlertCrowdSharingStateProcessorBase,
				EvaluateAlertState));
		UFunction* OverrideFunction = nullptr;
		UClass* OverrideClass = FBlueprintEditorUtils::GetOverrideFunctionClass(
			Blueprint, FunctionName, &OverrideFunction);
		if (Blueprint == nullptr || OverrideClass == nullptr
			|| OverrideFunction == nullptr)
		{
			return false;
		}
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(
			Blueprint, FunctionName, UEdGraph::StaticClass(),
			UEdGraphSchema_K2::StaticClass());
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(
			Blueprint, Graph, false, OverrideClass);

		UK2Node_FunctionEntry* Entry = nullptr;
		UK2Node_FunctionResult* Result = nullptr;
		for (UEdGraphNode* Node : TArray<UEdGraphNode*>(Graph->Nodes))
		{
			if (UK2Node_FunctionEntry* EntryNode =
				Cast<UK2Node_FunctionEntry>(Node))
			{
				Entry = EntryNode;
			}
			else if (UK2Node_FunctionResult* ResultNode =
				Cast<UK2Node_FunctionResult>(Node))
			{
				Result = ResultNode;
			}
			else
			{
				// UE creates a parent-call node for this override. The authored
				// graph must derive its result only from the live Subject fact.
				Graph->RemoveNode(Node);
			}
		}
		UK2Node_VariableGet* AlertGet = NewObject<UK2Node_VariableGet>(Graph);
		AlertGet->VariableReference.SetExternalMember(
			GET_MEMBER_NAME_CHECKED(AAlertCrowdSharingSubject, bAlerted),
			AAlertCrowdSharingSubject::StaticClass());
		Graph->AddNode(AlertGet, false, false);
		AlertGet->CreateNewGuid();
		AlertGet->PostPlacedNewNode();
		AlertGet->AllocateDefaultPins();
		AlertGet->NodePosX = -200;
		AlertGet->NodePosY = 120;

		UK2Node_CallFunction* Resolve = NewObject<UK2Node_CallFunction>(Graph);
		Resolve->FunctionReference.SetExternalMember(
			GET_FUNCTION_NAME_CHECKED(UAlertCrowdSharingStateProcessorBase,
				ResolveAlertStateFromFlag),
			UAlertCrowdSharingStateProcessorBase::StaticClass());
		Graph->AddNode(Resolve, false, false);
		Resolve->CreateNewGuid();
		Resolve->PostPlacedNewNode();
		Resolve->AllocateDefaultPins();
		Resolve->NodePosX = 100;
		Resolve->NodePosY = 120;

		const UEdGraphSchema_K2* Schema =
			Cast<UEdGraphSchema_K2>(Graph->GetSchema());
		return Entry != nullptr && Result != nullptr
			&& Connect(Schema,
				Entry->FindPin(TEXT("Subject"), EGPD_Output),
				AlertGet->FindPin(UEdGraphSchema_K2::PN_Self, EGPD_Input))
			&& Connect(Schema, AlertGet->GetValuePin(),
				Resolve->FindPin(TEXT("bAlerted"), EGPD_Input))
			&& Connect(Schema,
				Resolve->FindPin(UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Result->FindPin(UEdGraphSchema_K2::PN_ReturnValue, EGPD_Input));
	}

	FString AuthorAssets(const FString& Root, const FName SetupName,
		const FName ProcessorName, const bool bCompleted)
	{
		if (!RefuseExisting(Root, SetupName)
			|| !RefuseExisting(Root, ProcessorName))
		{
			return TEXT("FAIL ASHARING_REFUSE_EXISTING");
		}
		USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr,
			TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
		UAnimSequence* Ordinary = LoadObject<UAnimSequence>(nullptr,
			TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.MF_Unarmed_Walk_Fwd"));
		UAnimSequence* Alerted = LoadObject<UAnimSequence>(nullptr,
			TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd.MF_Unarmed_Jog_Fwd"));
		if (Mesh == nullptr || Mesh->GetSkeleton() == nullptr
			|| Ordinary == nullptr || Alerted == nullptr
			|| Ordinary->GetSkeleton() != Mesh->GetSkeleton()
			|| Alerted->GetSkeleton() != Mesh->GetSkeleton())
		{
			return TEXT("FAIL ASHARING_STOCK_ASSET_PREFLIGHT");
		}

		UPackage* ProcessorPackage = CreatePackage(
			*(Root + TEXT("/") + ProcessorName.ToString()));
		UBlueprint* Processor = FKismetEditorUtilities::CreateBlueprint(
			UAlertCrowdSharingStateProcessorBase::StaticClass(), ProcessorPackage,
			ProcessorName, BPTYPE_Normal, UBlueprint::StaticClass(),
			UBlueprintGeneratedClass::StaticClass());
		if (Processor == nullptr || (bCompleted && !BuildEvaluateGraph(Processor)))
		{
			return TEXT("FAIL ASHARING_BP_AUTHOR");
		}
		FKismetEditorUtilities::CompileBlueprint(Processor);
		if (Processor->Status != BS_UpToDate || Processor->GeneratedClass == nullptr)
		{
			return TEXT("FAIL ASHARING_BP_COMPILE");
		}
		FAssetRegistryModule::AssetCreated(Processor);

		UPackage* SetupPackage = CreatePackage(
			*(Root + TEXT("/") + SetupName.ToString()));
		UAnimationSharingSetup* Setup = NewObject<UAnimationSharingSetup>(
			SetupPackage, SetupName, RF_Public | RF_Standalone | RF_Transactional);
		if (Setup == nullptr)
		{
			return TEXT("FAIL ASHARING_SETUP_AUTHOR");
		}
		FPerSkeletonAnimationSharingSetup& Skeleton =
			Setup->SkeletonSetups.AddDefaulted_GetRef();
		Skeleton.Skeleton = Mesh->GetSkeleton();
		Skeleton.SkeletalMesh = Mesh;
		Skeleton.StateProcessorClass = Processor->GeneratedClass;
		Setup->ScalabilitySettings.UseBlendTransitions = FPerPlatformBool(false);
		Setup->ScalabilitySettings.MaximumNumberConcurrentBlends = FPerPlatformInt(1);
		if (bCompleted)
		{
			FAnimationStateEntry& OrdinaryState =
				Skeleton.AnimationStates.AddDefaulted_GetRef();
			OrdinaryState.State =
				static_cast<uint8>(EAlertCrowdSharingState::Ordinary);
			OrdinaryState.AnimationSetups.AddDefaulted_GetRef().AnimSequence = Ordinary;
			FAnimationStateEntry& AlertState =
				Skeleton.AnimationStates.AddDefaulted_GetRef();
			AlertState.State =
				static_cast<uint8>(EAlertCrowdSharingState::Alerted);
			AlertState.AnimationSetups.AddDefaulted_GetRef().AnimSequence = Alerted;
		}
		FAssetRegistryModule::AssetCreated(Setup);
		if (!SaveAsset(Processor) || !SaveAsset(Setup))
		{
			return TEXT("FAIL ASHARING_SAVE");
		}
		if (!bCompleted)
		{
			return FString::Printf(TEXT(
				"PASS EMPTY_SCAFFOLD setup=%s processor=%s states=0 graph=absent"),
				*Setup->GetPathName(), *Processor->GetPathName());
		}
		const FString SetupDetail =
			UAlertCrowdSharingIntrospectionLibrary::InspectSharingSetup(
				Setup, Processor);
		const FString GraphDetail =
			UAlertCrowdSharingIntrospectionLibrary::InspectStateProcessorGraph(
				Processor);
		if (!SetupDetail.StartsWith(TEXT("PASS "))
			|| !GraphDetail.StartsWith(TEXT("PASS ")))
		{
			return TEXT("FAIL ASHARING_SAME_PROCESS_READBACK setup={")
				+ SetupDetail + TEXT("} graph={") + GraphDetail + TEXT("}");
		}
		return FString::Printf(TEXT(
			"PASS SAVED exact_assets=2 setup={%s} graph={%s}"),
			*SetupDetail, *GraphDetail);
	}

	FString InspectAssets(const FString& Root, const FName SetupName,
		const FName ProcessorName, const bool bExpectedComplete)
	{
		UAnimationSharingSetup* Setup = LoadObject<UAnimationSharingSetup>(
			nullptr, *ObjectPath(Root, SetupName));
		UBlueprint* Processor = LoadObject<UBlueprint>(
			nullptr, *ObjectPath(Root, ProcessorName));
		if (Setup == nullptr || Processor == nullptr
			|| Processor->Status != BS_UpToDate
			|| Processor->GeneratedClass == nullptr
			|| Processor->GeneratedClass->GetSuperClass()
				!= UAlertCrowdSharingStateProcessorBase::StaticClass()
			|| Setup->SkeletonSetups.Num() != 1)
		{
			return TEXT("FAIL ASHARING_FINAL_IDENTITY");
		}

		const FPerSkeletonAnimationSharingSetup& Skeleton =
			Setup->SkeletonSetups[0];
		USkeletalMesh* ExpectedMesh = LoadObject<USkeletalMesh>(nullptr,
			TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
		if (ExpectedMesh == nullptr || ExpectedMesh->GetSkeleton() == nullptr
			|| Skeleton.SkeletalMesh != ExpectedMesh
			|| Skeleton.Skeleton != ExpectedMesh->GetSkeleton()
			|| Skeleton.StateProcessorClass.Get() != Processor->GeneratedClass)
		{
			return TEXT("FAIL ASHARING_FINAL_STOCK_OR_PROCESSOR_IDENTITY");
		}

		if (!bExpectedComplete)
		{
			return Skeleton.AnimationStates.IsEmpty()
				&& Processor->FunctionGraphs.IsEmpty()
				? FString::Printf(TEXT(
					"PASS EMPTY exact_assets=2 expected_complete=0 setup=%s processor=%s states=0 graph=absent"),
					*Setup->GetPathName(), *Processor->GetPathName())
				: TEXT("FAIL ASHARING_FINAL_NOT_EMPTY");
		}

		const FString SetupDetail =
			UAlertCrowdSharingIntrospectionLibrary::InspectSharingSetup(
				Setup, Processor);
		const FString GraphDetail =
			UAlertCrowdSharingIntrospectionLibrary::InspectStateProcessorGraph(
				Processor);
		return SetupDetail.StartsWith(TEXT("PASS "))
			&& GraphDetail.StartsWith(TEXT("PASS "))
			? FString::Printf(TEXT(
				"PASS COMPLETE exact_assets=2 expected_complete=1 setup={%s} graph={%s}"),
				*SetupDetail, *GraphDetail)
			: FString::Printf(TEXT("FAIL setup={%s} graph={%s}"),
				*SetupDetail, *GraphDetail);
	}
}

FString UAlertCrowdSharingAssetAuthoring::AuthorAdmissionAssets()
{
	return AuthorAssets(AdmissionRoot, SetupAdmissionName,
		ProcessorAdmissionName, true);
}

FString UAlertCrowdSharingAssetAuthoring::InspectAdmissionAssets()
{
	const FString Detail = InspectAssets(AdmissionRoot, SetupAdmissionName,
		ProcessorAdmissionName, true);
	return Detail.StartsWith(
		TEXT("PASS COMPLETE exact_assets=2 expected_complete=1 "))
		? Detail.Replace(
			TEXT("PASS COMPLETE exact_assets=2 expected_complete=1 "),
			TEXT("PASS exact_assets=2 "))
		: Detail;
}

FString UAlertCrowdSharingAssetAuthoring::AuthorEmptyFinalScaffold()
{
	return AuthorAssets(FinalRoot, SetupFinalName, ProcessorFinalName, false);
}

FString UAlertCrowdSharingAssetAuthoring::AuthorReferenceAssets()
{
	return AuthorAssets(FinalRoot, SetupFinalName, ProcessorFinalName, true);
}

FString UAlertCrowdSharingAssetAuthoring::InspectFinalAssets(
	const bool bExpectedComplete)
{
	return InspectAssets(FinalRoot, SetupFinalName, ProcessorFinalName,
		bExpectedComplete);
}
