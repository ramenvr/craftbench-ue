// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideAssetAuthoring.h"

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideFunctionalTest.h"
#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideTypes.h"
#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideVerifierLibrary.h"

#include "Animation/AnimBlueprint.h"
#include "Animation/AnimLayerInterface.h"
#include "Animation/BlendSpace.h"
#include "Animation/Skeleton.h"
#include "AnimationGraph.h"
#include "AnimationGraphSchema.h"
#include "AnimGraphNode_BlendSpacePlayer.h"
#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "AnimGraphNode_LinkedAnimLayer.h"
#include "AnimGraphNode_LocalRefPose.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_ModifyBone.h"
#include "AnimGraphNode_Root.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StateTreeComponentSchema.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/MemberReference.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Factories/AnimBlueprintFactory.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "StateTree.h"
#include "StateTreeCompilerLog.h"
#include "StateTreeEditingSubsystem.h"
#include "StateTreeEditorData.h"
#include "StateTreeFactory.h"
#include "StateTreeState.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

namespace
{
	constexpr TCHAR SkeletonPath[] =
		TEXT("/Game/Characters/Mannequins/Meshes/SK_Mannequin.SK_Mannequin");
	constexpr TCHAR MeshPath[] =
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple");
	constexpr TCHAR LocomotionPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run.BS_Idle_Walk_Run");
	constexpr TCHAR InterfaceName[] = TEXT("ALI_AlertStrideUpperBody");
	constexpr TCHAR HostName[] = TEXT("ABP_AlertStrideHost");
	constexpr TCHAR CalmName[] = TEXT("ABP_AlertStrideCalmLayer");
	constexpr TCHAR AlertName[] = TEXT("ABP_AlertStrideAlertLayer");
	constexpr TCHAR StateTreeName[] = TEXT("ST_AlertStride");
	constexpr TCHAR LayerName[] = TEXT("UpperBody");

	FString JoinPackage(const FString& Root, const TCHAR* Name)
	{
		return Root + TEXT("/") + Name;
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
		return UPackage::SavePackage(Package, Asset, *Filename, Args);
	}

	template <typename TNode>
	TNode* AddNode(UEdGraph* Graph, const int32 X, const int32 Y)
	{
		TNode* Node = Graph ? NewObject<TNode>(Graph) : nullptr;
		if (Node == nullptr)
		{
			return nullptr;
		}
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	TArray<UEdGraphPin*> PosePins(
		UEdGraphNode* Node, const EEdGraphPinDirection Direction)
	{
		TArray<UEdGraphPin*> Result;
		if (Node)
		{
			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (Pin && Pin->Direction == Direction
					&& UAnimationGraphSchema::IsPosePin(Pin->PinType))
				{
					Result.Add(Pin);
				}
			}
		}
		return Result;
	}

	bool ConnectFirstPose(
		const UEdGraphSchema* Schema, UEdGraphNode* Output,
		UEdGraphNode* Input)
	{
		const TArray<UEdGraphPin*> Outputs = PosePins(Output, EGPD_Output);
		const TArray<UEdGraphPin*> Inputs = PosePins(Input, EGPD_Input);
		return Schema != nullptr && Outputs.Num() == 1 && Inputs.Num() >= 1
			&& Schema->TryCreateConnection(Outputs[0], Inputs[0]);
	}

	UEdGraph* FindGraph(UAnimBlueprint* Blueprint, const FName Name)
	{
		TArray<UEdGraph*> Graphs;
		if (Blueprint)
		{
			Blueprint->GetAllGraphs(Graphs);
		}
		for (UEdGraph* Graph : Graphs)
		{
			if (Graph && Graph->GetFName() == Name)
			{
				return Graph;
			}
		}
		return nullptr;
	}

	UAnimGraphNode_Root* ResetGraph(UAnimBlueprint* Blueprint, const FName Name)
	{
		UEdGraph* Graph = FindGraph(Blueprint, Name);
		TArray<UAnimGraphNode_Root*> Roots;
		if (Graph)
		{
			Graph->GetNodesOfClass(Roots);
		}
		if (Roots.Num() != 1)
		{
			return nullptr;
		}
		for (UEdGraphNode* Existing : TArray<UEdGraphNode*>(Graph->Nodes))
		{
			if (Existing != Roots[0])
			{
				Graph->RemoveNode(Existing);
			}
		}
		for (UEdGraphPin* Pin : Roots[0]->Pins)
		{
			if (Pin)
			{
				Pin->BreakAllPinLinks();
			}
		}
		return Roots[0];
	}

	UAnimBlueprint* CreateAnimBlueprint(
		const FString& PackageName, UClass* ParentClass, USkeleton* Skeleton,
		USkeletalMesh* PreviewMesh, const bool bInterface)
	{
		UPackage* Package = CreatePackage(*PackageName);
		UAnimBlueprintFactory* Factory = bInterface
			? NewObject<UAnimLayerInterfaceFactory>()
			: NewObject<UAnimBlueprintFactory>();
		Factory->BlueprintType = bInterface ? BPTYPE_Interface : BPTYPE_Normal;
		if (!bInterface)
		{
			Factory->ParentClass = ParentClass;
		}
		Factory->TargetSkeleton = bInterface ? nullptr : Skeleton;
		Factory->PreviewSkeletalMesh = bInterface ? nullptr : PreviewMesh;
		return Cast<UAnimBlueprint>(Factory->FactoryCreateNew(
			UAnimBlueprint::StaticClass(), Package,
			*FPackageName::GetLongPackageAssetName(PackageName),
			RF_Public | RF_Standalone, nullptr, GWarn));
	}

	bool CompileAndSave(UAnimBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
		return Blueprint->Status == BS_UpToDate
			&& Blueprint->GeneratedClass != nullptr && SaveAsset(Blueprint);
	}

	bool AddLayerFunction(UAnimBlueprint* Interface)
	{
		if (Interface == nullptr || Interface->BlueprintType != BPTYPE_Interface)
		{
			return false;
		}
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(
			Interface, LayerName, UAnimationGraph::StaticClass(),
			UAnimationGraphSchema::StaticClass());
		if (Graph == nullptr)
		{
			return false;
		}
		// Animation layers are domain-specific animation graphs. This mirrors
		// FBlueprintEditor::CGT_NewAnimationLayer and lets the animation schema
		// create exactly one root node; AddFunctionGraph would add a second root
		// and trip UAnimationGraphSchema::AutoArrangeInterfaceGraph.
		FBlueprintEditorUtils::AddDomainSpecificGraph(Interface, Graph);
		Graph->bAllowDeletion = false;
		return true;
	}

	bool ImplementLayerInterface(
		UAnimBlueprint* Blueprint, const UAnimBlueprint* Interface)
	{
		return Blueprint && Interface && Interface->GeneratedClass
			&& FBlueprintEditorUtils::ImplementNewInterface(
				Blueprint, Interface->GeneratedClass->GetClassPathName());
	}

	bool ConfigureLinkedLayerNode(
		UAnimGraphNode_LinkedAnimLayer* Linked,
		UAnimBlueprint* Host,
		UAnimBlueprint* Interface)
	{
		if (Linked == nullptr || Host == nullptr || Interface == nullptr
			|| Interface->GeneratedClass == nullptr)
		{
			return false;
		}

		FGuid InterfaceGuid;
		for (const FBPInterfaceDescription& Description : Host->ImplementedInterfaces)
		{
			for (const UEdGraph* InterfaceGraph : Description.Graphs)
			{
				if (InterfaceGraph != nullptr && InterfaceGraph->GetFName() == LayerName)
				{
					InterfaceGuid = InterfaceGraph->InterfaceGuid;
				}
			}
		}
		FGuid FunctionGuid;
		const bool bFoundFunctionGuid =
			FBlueprintEditorUtils::GetFunctionGuidFromClassByFieldName(
				FBlueprintEditorUtils::GetMostUpToDateClass(Interface->GeneratedClass),
				LayerName, FunctionGuid);
		FStructProperty* FunctionReferenceProperty = FindFProperty<FStructProperty>(
			Linked->GetClass(), TEXT("FunctionReference"));
		FMemberReference* FunctionReference = FunctionReferenceProperty != nullptr
			&& FunctionReferenceProperty->Struct == FMemberReference::StaticStruct()
			? FunctionReferenceProperty->ContainerPtrToValuePtr<FMemberReference>(Linked)
			: nullptr;
		if (!InterfaceGuid.IsValid() || !bFoundFunctionGuid
			|| !FunctionGuid.IsValid() || FunctionReference == nullptr)
		{
			return false;
		}

		Linked->Node.Layer = LayerName;
		Linked->InterfaceGuid = InterfaceGuid;
		FunctionReference->SetExternalMember(
			LayerName, Interface->GeneratedClass, FunctionGuid);
		return FunctionReference->GetMemberName() == LayerName;
	}

	bool BuildLayerGraph(UAnimBlueprint* Blueprint, const bool bAlert)
	{
		UEdGraph* Graph = FindGraph(Blueprint, LayerName);
		UAnimGraphNode_Root* Root = ResetGraph(Blueprint, LayerName);
		if (Graph == nullptr || Root == nullptr)
		{
			return false;
		}
		Root->NodePosX = 650;
		UAnimGraphNode_LocalRefPose* Ref =
			AddNode<UAnimGraphNode_LocalRefPose>(Graph, -650, 0);
		UEdGraphNode* Writer = Ref;
		const UEdGraphSchema* Schema = Graph->GetSchema();
		if (bAlert)
		{
			UAnimGraphNode_LocalToComponentSpace* ToComponent =
				AddNode<UAnimGraphNode_LocalToComponentSpace>(Graph, -350, 0);
			UAnimGraphNode_ModifyBone* Modify =
				AddNode<UAnimGraphNode_ModifyBone>(Graph, -50, 0);
			UAnimGraphNode_ComponentToLocalSpace* ToLocal =
				AddNode<UAnimGraphNode_ComponentToLocalSpace>(Graph, 300, 0);
			if (Ref == nullptr || ToComponent == nullptr || Modify == nullptr
				|| ToLocal == nullptr)
			{
				return false;
			}
			// Keep the alert change visibly load-bearing under NullRHI.  The first
			// admission leg proved that a spine_03 bone-space roll changed the
			// evaluated hand position by only 0.038 cm on Manny.  An additive
			// component-space hand offset is still an ordinary upper-body
			// Transform Bone authored inside the declared linked layer, while it
			// gives the live-bone verifier a deterministic signal independent of
			// the locomotion phase underneath it.
			Modify->Node.BoneToModify.BoneName = TEXT("hand_r");
			// Translation is PinShownByDefault.  SetNodeValue updates both the
			// exposed pin default and the compile-node field; assigning the field
			// alone after AllocateDefaultPins leaves the pin at zero and the
			// compiler copies that zero back into the runtime node.
			Modify->SetNodeValue(
				GET_MEMBER_NAME_CHECKED(FAnimNode_ModifyBone, Translation),
				Modify->Node.Translation, FVector(0.0, 0.0, 18.0));
			Modify->Node.TranslationMode = BMM_Additive;
			Modify->Node.RotationMode = BMM_Ignore;
			Modify->Node.ScaleMode = BMM_Ignore;
			Modify->Node.TranslationSpace = BCS_ComponentSpace;
			Modify->Node.Alpha = 1.0f;
			if (!ConnectFirstPose(Schema, Ref, ToComponent)
				|| !ConnectFirstPose(Schema, ToComponent, Modify)
				|| !ConnectFirstPose(Schema, Modify, ToLocal))
			{
				return false;
			}
			Writer = ToLocal;
		}
		return Writer && ConnectFirstPose(Schema, Writer, Root);
	}

	bool HasExactAuthoredAlertDelta(UAnimBlueprint* Blueprint)
	{
		UEdGraph* Graph = FindGraph(Blueprint, LayerName);
		TArray<UAnimGraphNode_ModifyBone*> ModifyNodes;
		if (Graph)
		{
			Graph->GetNodesOfClass(ModifyNodes);
		}
		if (ModifyNodes.Num() != 1 || ModifyNodes[0] == nullptr)
		{
			return false;
		}
		UAnimGraphNode_ModifyBone* Modify = ModifyNodes[0];
		FVector PinTranslation = FVector::ZeroVector;
		Modify->GetDefaultValue(
			GET_MEMBER_NAME_CHECKED(FAnimNode_ModifyBone, Translation),
			PinTranslation);
		const FVector Expected(0.0, 0.0, 18.0);
		return Modify->Node.BoneToModify.BoneName == TEXT("hand_r")
			&& Modify->Node.Translation.Equals(Expected, KINDA_SMALL_NUMBER)
			&& PinTranslation.Equals(Expected, KINDA_SMALL_NUMBER)
			&& Modify->Node.TranslationMode == BMM_Additive
			&& Modify->Node.RotationMode == BMM_Ignore
			&& Modify->Node.ScaleMode == BMM_Ignore
			&& Modify->Node.TranslationSpace == BCS_ComponentSpace
			&& FMath::IsNearlyEqual(Modify->Node.Alpha, 1.0f);
	}

	bool BuildHostGraph(
		UAnimBlueprint* Host, UAnimBlueprint* Interface,
		UAnimBlueprint* CalmLayer, const bool bComplete)
	{
		UEdGraph* Graph = FindGraph(Host, UEdGraphSchema_K2::GN_AnimGraph);
		UAnimGraphNode_Root* Root = ResetGraph(
			Host, UEdGraphSchema_K2::GN_AnimGraph);
		UBlendSpace* Locomotion = LoadObject<UBlendSpace>(nullptr, LocomotionPath);
		if (Graph == nullptr || Root == nullptr || Locomotion == nullptr
			|| Locomotion->GetSkeleton() != Host->TargetSkeleton)
		{
			return false;
		}
		UAnimGraphNode_BlendSpacePlayer* Base =
			AddNode<UAnimGraphNode_BlendSpacePlayer>(Graph, -850, -120);
		UK2Node_VariableGet* Speed =
			AddNode<UK2Node_VariableGet>(Graph, -1100, 160);
		if (Base == nullptr || Speed == nullptr
			|| !Base->Node.SetBlendSpace(Locomotion))
		{
			return false;
		}
		Speed->VariableReference.SetSelfMember(TEXT("GroundSpeed"));
		Speed->ReconstructNode();
		const UEdGraphSchema* Schema = Graph->GetSchema();
		UEdGraphPin* SpeedOutput = Speed->FindPin(TEXT("GroundSpeed"), EGPD_Output);
		UEdGraphPin* SpeedInput = Base->FindPin(TEXT("X"), EGPD_Input);
		if (SpeedOutput == nullptr || SpeedInput == nullptr
			|| !Schema->TryCreateConnection(SpeedOutput, SpeedInput))
		{
			return false;
		}
		UEdGraphNode* Writer = Base;
		if (bComplete)
		{
			UAnimGraphNode_LinkedAnimLayer* Linked =
				AddNode<UAnimGraphNode_LinkedAnimLayer>(Graph, -350, 160);
			UAnimGraphNode_LayeredBoneBlend* Blend =
				AddNode<UAnimGraphNode_LayeredBoneBlend>(Graph, 100, -80);
			if (Linked == nullptr || Blend == nullptr || Interface == nullptr
				|| Interface->GeneratedClass == nullptr || CalmLayer == nullptr
				|| CalmLayer->GeneratedClass == nullptr)
			{
				return false;
			}
			Linked->Node.Interface = Interface->GeneratedClass;
			Linked->Node.InstanceClass = CalmLayer->GeneratedClass;
			if (!ConfigureLinkedLayerNode(Linked, Host, Interface))
			{
				return false;
			}
			Blend->Node.BlendMode = ELayeredBoneBlendMode::BranchFilter;
			if (Blend->Node.BlendWeights.Num() != 1
				|| Blend->Node.LayerSetup.Num() != 1)
			{
				return false;
			}
			Blend->Node.BlendWeights[0] = 1.0f;
			Blend->Node.LayerSetup[0].BranchFilters.Reset();
			FBranchFilter Filter;
			Filter.BoneName = TEXT("spine_01");
			Filter.BlendDepth = 0;
			Blend->Node.LayerSetup[0].BranchFilters.Add(Filter);
			Blend->Node.bMeshSpaceRotationBlend = true;
			Blend->ReconstructNode();
			const TArray<UEdGraphPin*> BlendInputs = PosePins(Blend, EGPD_Input);
			const TArray<UEdGraphPin*> BaseOutputs = PosePins(Base, EGPD_Output);
			const TArray<UEdGraphPin*> LinkedOutputs = PosePins(Linked, EGPD_Output);
			if (BlendInputs.Num() != 2 || BaseOutputs.Num() != 1
				|| LinkedOutputs.Num() != 1
				|| !Schema->TryCreateConnection(BaseOutputs[0], BlendInputs[0])
				|| !Schema->TryCreateConnection(LinkedOutputs[0], BlendInputs[1]))
			{
				return false;
			}
			Writer = Blend;
		}
		return ConnectFirstPose(Schema, Writer, Root);
	}

	UStateTree* CreateStateTree(
		const FString& PackageName, UClass* AlertLayerClass,
		const bool bComplete)
	{
		UPackage* Package = CreatePackage(*PackageName);
		UStateTreeFactory* Factory = NewObject<UStateTreeFactory>();
		Factory->SetSchemaClass(UStateTreeComponentSchema::StaticClass());
		UStateTree* Tree = Cast<UStateTree>(Factory->FactoryCreateNew(
			UStateTree::StaticClass(), Package,
			*FPackageName::GetLongPackageAssetName(PackageName),
			RF_Public | RF_Standalone, nullptr, GWarn));
		UStateTreeEditorData* Data = Tree
			? Cast<UStateTreeEditorData>(Tree->EditorData) : nullptr;
		if (Data == nullptr || Data->SubTrees.Num() != 1
			|| Data->SubTrees[0] == nullptr)
		{
			return nullptr;
		}
		UStateTreeState& Root = *Data->SubTrees[0];
		Root.Name = TEXT("Root");
		UStateTreeState& Calm = Root.AddChildState(TEXT("Calm"));
		if (bComplete)
		{
			UStateTreeState& Alert = Root.AddChildState(TEXT("Alert"));
			FStateTreeTransition& ToAlert = Calm.AddTransition(
				EStateTreeTransitionTrigger::OnTick,
				EStateTreeTransitionType::GotoState, &Alert);
			auto& AlertCondition =
				ToAlert.AddConditionWithOuter<FAlertStrideSignalCondition>(&Calm);
			AlertCondition.SetNodeName(TEXT("WorldAlertIsActive"));
			AlertCondition.GetInstanceData().bExpectedAlert = true;
			FStateTreeTransition& ToCalm = Alert.AddTransition(
				EStateTreeTransitionTrigger::OnTick,
				EStateTreeTransitionType::GotoState, &Calm);
			auto& CalmCondition =
				ToCalm.AddConditionWithOuter<FAlertStrideSignalCondition>(&Alert);
			CalmCondition.SetNodeName(TEXT("WorldAlertIsClear"));
			CalmCondition.GetInstanceData().bExpectedAlert = false;
			auto& LinkTask = Alert.AddTask<FAlertStrideLinkLayerTask>();
			LinkTask.SetNodeName(TEXT("DeclaredUpperBodyLayer"));
			LinkTask.GetInstanceData().AlertLayerClass = AlertLayerClass;
		}
		FStateTreeCompilerLog CompileLog;
		return UStateTreeEditingSubsystem::CompileStateTree(Tree, CompileLog)
			&& Tree->IsReadyToRun() ? Tree : nullptr;
	}
}

bool UAlertStrideAssetAuthoring::AuthorAssetSet(
	const FString& RootPackage, const FString& InterfacePackage,
	const bool bComplete, FString& OutMessage)
{
	OutMessage.Reset();
	if (!FPackageName::IsValidLongPackageName(RootPackage)
		|| !FPackageName::IsValidLongPackageName(InterfacePackage)
		|| FPackageName::GetLongPackageAssetName(InterfacePackage)
			!= InterfaceName)
	{
		OutMessage = FString::Printf(
			TEXT("FAIL ALERT_STRIDE_ROOT_INVALID root=%s interface=%s"),
			*RootPackage, *InterfacePackage);
		return false;
	}
	const TArray<FString> Packages = {
		InterfacePackage, JoinPackage(RootPackage, HostName),
		JoinPackage(RootPackage, CalmName), JoinPackage(RootPackage, AlertName),
		JoinPackage(RootPackage, StateTreeName),
	};
	for (int32 PackageIndex = 0; PackageIndex < Packages.Num(); ++PackageIndex)
	{
		const FString& Package = Packages[PackageIndex];
		// Complete references are authored only in a disposable substrate and
		// must reuse the retained read-only layer contract. Baseline/admission
		// authoring still requires all five packages to be absent.
		if (bComplete && PackageIndex == 0)
		{
			continue;
		}
		if (FPackageName::DoesPackageExist(Package))
		{
			OutMessage = TEXT("FAIL ALERT_STRIDE_REFUSE_OVERWRITE ") + Package;
			return false;
		}
	}
	USkeleton* Skeleton = LoadObject<USkeleton>(nullptr, SkeletonPath);
	USkeletalMesh* PreviewMesh = LoadObject<USkeletalMesh>(nullptr, MeshPath);
	if (Skeleton == nullptr || PreviewMesh == nullptr
		|| PreviewMesh->GetSkeleton() != Skeleton)
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_STOCK_MANNY");
		return false;
	}
	UAnimBlueprint* Interface = nullptr;
	if (bComplete)
	{
		Interface = LoadObject<UAnimBlueprint>(nullptr, *Packages[0]);
	}
	else
	{
		Interface = CreateAnimBlueprint(
			Packages[0], nullptr, nullptr, nullptr, true);
		if (Interface)
		{
			FAssetRegistryModule::AssetCreated(Interface);
		}
	}
	if (Interface == nullptr
		|| (!bComplete && (!AddLayerFunction(Interface)
			|| !CompileAndSave(Interface))))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_INTERFACE");
		return false;
	}
	UAnimBlueprint* Calm = CreateAnimBlueprint(
		Packages[2], UAnimInstance::StaticClass(), Skeleton, PreviewMesh, false);
	UAnimBlueprint* Alert = CreateAnimBlueprint(
		Packages[3], UAnimInstance::StaticClass(), Skeleton, PreviewMesh, false);
	if (Calm)
	{
		FAssetRegistryModule::AssetCreated(Calm);
	}
	if (Alert)
	{
		FAssetRegistryModule::AssetCreated(Alert);
	}
	if (!ImplementLayerInterface(Calm, Interface)
		|| !ImplementLayerInterface(Alert, Interface)
		|| !BuildLayerGraph(Calm, false)
		|| !BuildLayerGraph(Alert, bComplete)
		|| !CompileAndSave(Calm) || !CompileAndSave(Alert))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_LAYER_CLASSES");
		return false;
	}
	if (bComplete && !HasExactAuthoredAlertDelta(Alert))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_ALERT_DELTA_READBACK");
		return false;
	}
	UAnimBlueprint* Host = CreateAnimBlueprint(
		Packages[1], UAlertStrideAnimInstance::StaticClass(),
		Skeleton, PreviewMesh, false);
	if (Host)
	{
		FAssetRegistryModule::AssetCreated(Host);
	}
	if (!ImplementLayerInterface(Host, Interface))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_HOST_INTERFACE");
		UE_LOG(LogTemp, Error, TEXT("ALERT-STRIDE-NATIVE-ASSET-FAILED %s"), *OutMessage);
		return false;
	}
	if (!BuildHostGraph(Host, Interface, Calm, bComplete))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_HOST_GRAPH");
		UE_LOG(LogTemp, Error, TEXT("ALERT-STRIDE-NATIVE-ASSET-FAILED %s"), *OutMessage);
		return false;
	}
	if (!CompileAndSave(Host))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_HOST_COMPILE_SAVE");
		UE_LOG(LogTemp, Error, TEXT("ALERT-STRIDE-NATIVE-ASSET-FAILED %s"), *OutMessage);
		return false;
	}
	UStateTree* StateTree = CreateStateTree(
		Packages[4], Alert->GeneratedClass, bComplete);
	if (StateTree)
	{
		FAssetRegistryModule::AssetCreated(StateTree);
	}
	if (StateTree == nullptr || !SaveAsset(StateTree))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_STATE_TREE");
		return false;
	}
	const FString Readback = UAlertStrideVerifierLibrary::InspectAssetSet(
		RootPackage, InterfacePackage, bComplete);
	if (!Readback.Contains(TEXT("\"probe_ok\":true")))
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_SAME_PROCESS_READBACK ") + Readback;
		return false;
	}
	OutMessage = FString::Printf(
		TEXT("PASS ALERT_STRIDE_ASSETS mode=%s packages=5 editable=4 root=%s facts=%s"),
		bComplete ? TEXT("complete") : TEXT("baseline"),
		*RootPackage, *Readback);
	return true;
}

bool UAlertStrideAssetAuthoring::ConfigureScenario(
	AAlertStrideScenario* Scenario, UAnimBlueprint* Host,
	UAnimBlueprint* LayerInterface, UAnimBlueprint* CalmLayer,
	UAnimBlueprint* AlertLayer, UStateTree* StateTree, FString& OutMessage)
{
	OutMessage.Reset();
	if (Scenario == nullptr || Scenario->Subject == nullptr
		|| Scenario->Signal == nullptr || Host == nullptr
		|| LayerInterface == nullptr || CalmLayer == nullptr
		|| AlertLayer == nullptr || StateTree == nullptr
		|| Host->GeneratedClass == nullptr
		|| LayerInterface->GeneratedClass == nullptr
		|| CalmLayer->GeneratedClass == nullptr
		|| AlertLayer->GeneratedClass == nullptr || !StateTree->IsReadyToRun())
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_SCENARIO_INPUT");
		return false;
	}
	USkeletalMeshComponent* Mesh = Scenario->Subject->GetMesh();
	if (Mesh == nullptr)
	{
		OutMessage = TEXT("FAIL ALERT_STRIDE_SCENARIO_MESH");
		return false;
	}
	Scenario->Modify();
	Mesh->Modify();
	Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	Mesh->SetAnimInstanceClass(Host->GeneratedClass);
	Mesh->VisibilityBasedAnimTickOption =
		EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Mesh->bEnableUpdateRateOptimizations = false;
	Scenario->StateTree = StateTree;
	Scenario->LayerInterfaceClass = LayerInterface->GeneratedClass;
	Scenario->CalmLayerClass = CalmLayer->GeneratedClass;
	Scenario->AlertLayerClass = AlertLayer->GeneratedClass;
	const bool bPass = Mesh->GetAnimClass() == Host->GeneratedClass
		&& Scenario->StateTree == StateTree
		&& Scenario->LayerInterfaceClass == LayerInterface->GeneratedClass
		&& Scenario->CalmLayerClass == CalmLayer->GeneratedClass
		&& Scenario->AlertLayerClass == AlertLayer->GeneratedClass;
	OutMessage = FString::Printf(
		TEXT("%s scenario=%s host=%s interface=%s calm=%s alert=%s tree=%s"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), *GetPathNameSafe(Scenario),
		*GetPathNameSafe(Host->GeneratedClass),
		*GetPathNameSafe(LayerInterface->GeneratedClass),
		*GetPathNameSafe(CalmLayer->GeneratedClass),
		*GetPathNameSafe(AlertLayer->GeneratedClass), *GetPathNameSafe(StateTree));
	return bPass;
}

FString UAlertStrideAssetAuthoring::InspectWorld(
	UObject* WorldContextObject, const bool bAdmission)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL ALERT_STRIDE_WORLD_NULL");
	}
	const int32 Expected = bAdmission ? 1 : 2;
	int32 Scenarios = 0;
	int32 Subjects = 0;
	int32 Signals = 0;
	int32 Fixtures = 0;
	int32 SlowFixtures = 0;
	int32 FastFixtures = 0;
	int32 AdmissionFixtures = 0;
	TSet<FName> ScenarioIds;
	TSet<FString> FactVectors;
	TSet<AAlertStrideCharacter*> ReferencedSubjects;
	TSet<AAlertStrideSignalActor*> ReferencedSignals;
	bool bRefs = true;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (AAlertStrideScenario* Value = Cast<AAlertStrideScenario>(*It))
		{
			++Scenarios;
			ScenarioIds.Add(Value->ScenarioId);
			FactVectors.Add(FString::Printf(TEXT("%.0f:%.2f:%.2f:%s"),
				Value->WalkSpeed, Value->AlertDelay, Value->ClearDelay,
				*Value->TravelDirection.ToCompactString()));
			ReferencedSubjects.Add(Value->Subject);
			ReferencedSignals.Add(Value->Signal);
			const FName GroupTag(*FString::Printf(
				TEXT("AlertStride.Group.%s"), *Value->ScenarioId.ToString()));
			const FName IdentityTag(*FString::Printf(
				TEXT("AlertStride.Scenario.%s"), *Value->ScenarioId.ToString()));
			const FName SubjectTag(*FString::Printf(
				TEXT("AlertStride.Subject.%s"), *Value->ScenarioId.ToString()));
			const FName SignalTag(*FString::Printf(
				TEXT("AlertStride.Signal.%s"), *Value->ScenarioId.ToString()));
			bRefs = bRefs && Value->Subject && Value->Signal && Value->StateTree
				&& Value->LayerInterfaceClass && Value->CalmLayerClass
				&& Value->AlertLayerClass
				&& Value->Subject->GetMesh()->GetAnimClass() != nullptr
				&& Value->Tags.Num() == 3
				&& Value->ActorHasTag(TEXT("AlertStrideScenario"))
				&& Value->ActorHasTag(GroupTag)
				&& Value->ActorHasTag(IdentityTag)
				&& Value->Subject->Tags.Num() == 3
				&& Value->Subject->ActorHasTag(TEXT("AlertStrideSubject"))
				&& Value->Subject->ActorHasTag(GroupTag)
				&& Value->Subject->ActorHasTag(SubjectTag)
				&& Value->Signal->Tags.Num() == 3
				&& Value->Signal->ActorHasTag(TEXT("AlertStrideSignal"))
				&& Value->Signal->ActorHasTag(GroupTag)
				&& Value->Signal->ActorHasTag(SignalTag);
		}
		Subjects += Cast<AAlertStrideCharacter>(*It) ? 1 : 0;
		Signals += Cast<AAlertStrideSignalActor>(*It) ? 1 : 0;
		Fixtures += Cast<AAlertStrideFunctionalTestBase>(*It) ? 1 : 0;
		SlowFixtures += Cast<AAlertStrideSlowFunctionalTest>(*It) ? 1 : 0;
		FastFixtures += Cast<AAlertStrideFastFunctionalTest>(*It) ? 1 : 0;
		AdmissionFixtures +=
			Cast<AAlertStrideAdmissionFunctionalTest>(*It) ? 1 : 0;
	}
	const TSet<FName> ExpectedIds = bAdmission
		? TSet<FName>{TEXT("Admission")}
		: TSet<FName>{TEXT("SlowEarly"), TEXT("FastLate")};
	const bool bFixtureClasses = bAdmission
		? AdmissionFixtures == 1 && SlowFixtures == 0 && FastFixtures == 0
		: AdmissionFixtures == 0 && SlowFixtures == 1 && FastFixtures == 1;
	const bool bPass = Scenarios == Expected && Subjects == Expected
		&& Signals == Expected && Fixtures == Expected
		&& ScenarioIds.Difference(ExpectedIds).Num() == 0
		&& ExpectedIds.Difference(ScenarioIds).Num() == 0
		&& FactVectors.Num() == Expected
		&& ReferencedSubjects.Num() == Expected
		&& ReferencedSignals.Num() == Expected && bFixtureClasses && bRefs;
	return FString::Printf(
		TEXT("%s admission=%d scenarios=%d subjects=%d signals=%d fixtures=%d slow=%d fast=%d admission_fixture=%d ids=%d facts=%d refs=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bAdmission ? 1 : 0,
		Scenarios, Subjects, Signals, Fixtures, SlowFixtures, FastFixtures,
		AdmissionFixtures, ScenarioIds.Num(), FactVectors.Num(), bRefs ? 1 : 0);
}
