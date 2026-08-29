// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideVerifierLibrary.h"

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideTypes.h"

#include "Animation/AnimBlueprint.h"
#include "Animation/AnimClassInterface.h"
#include "Animation/AnimLayerInterface.h"
#include "Animation/AnimNode_LinkedAnimLayer.h"
#include "Animation/BlendSpace.h"
#include "AnimationGraphSchema.h"
#include "AnimGraphNode_BlendSpacePlayer.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "AnimGraphNode_LinkedAnimLayer.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_Slot.h"
#include "Dom/JsonObject.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_VariableGet.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "StateTree.h"
#include "StateTreeEditorData.h"
#include "StateTreeState.h"
#include "UObject/UnrealType.h"

namespace
{
	constexpr TCHAR HostName[] = TEXT("ABP_AlertStrideHost");
	constexpr TCHAR CalmName[] = TEXT("ABP_AlertStrideCalmLayer");
	constexpr TCHAR AlertName[] = TEXT("ABP_AlertStrideAlertLayer");
	constexpr TCHAR StateTreeName[] = TEXT("ST_AlertStride");
	constexpr TCHAR LayerName[] = TEXT("UpperBody");
	constexpr TCHAR LocomotionPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run.BS_Idle_Walk_Run");

	FString ObjectPath(const FString& Root, const TCHAR* Name)
	{
		return Root + TEXT("/") + Name + TEXT(".") + Name;
	}

	FString PackageObjectPath(const FString& Package)
	{
		return Package + TEXT(".")
			+ FPackageName::GetLongPackageAssetName(Package);
	}

	FString SerializeFacts(const TSharedRef<FJsonObject>& Facts)
	{
		FString Output;
		const TSharedRef<
			TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<
				TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Output);
		FJsonSerializer::Serialize(Facts, Writer);
		return Output;
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

	void VisitPoseUpstream(UEdGraphNode* Node, TSet<UEdGraphNode*>& Visited)
	{
		if (Node == nullptr || Visited.Contains(Node))
		{
			return;
		}
		Visited.Add(Node);
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->Direction == EGPD_Input
				&& UAnimationGraphSchema::IsPosePin(Pin->PinType))
			{
				for (UEdGraphPin* Linked : Pin->LinkedTo)
				{
					VisitPoseUpstream(
						Linked ? Linked->GetOwningNode() : nullptr, Visited);
				}
			}
		}
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

	bool PinComesFrom(UEdGraphPin* Input, const UEdGraphNode* Expected)
	{
		return Input && Input->LinkedTo.Num() == 1
			&& Input->LinkedTo[0]
			&& Input->LinkedTo[0]->GetOwningNode() == Expected;
	}

	bool PinComesFromVariable(UEdGraphPin* Input, const FName VariableName)
	{
		const UK2Node_VariableGet* Variable = Input && Input->LinkedTo.Num() == 1
			? Cast<UK2Node_VariableGet>(Input->LinkedTo[0]->GetOwningNode())
			: nullptr;
		return Variable
			&& Variable->VariableReference.GetMemberName() == VariableName;
	}

	bool ImplementsExactInterface(
		const UAnimBlueprint* Blueprint, const UClass* InterfaceClass)
	{
		int32 Matches = 0;
		if (Blueprint)
		{
			for (const FBPInterfaceDescription& Description
				: Blueprint->ImplementedInterfaces)
			{
				Matches += Description.Interface == InterfaceClass ? 1 : 0;
			}
		}
		return Matches == 1;
	}

	bool InspectLayerGraph(
		UAnimBlueprint* Blueprint, const UClass* InterfaceClass,
		bool& bOutNoSlot)
	{
		bOutNoSlot = false;
		UEdGraph* Graph = FindGraph(Blueprint, LayerName);
		TArray<UAnimGraphNode_Root*> Roots;
		if (Graph)
		{
			Graph->GetNodesOfClass(Roots);
		}
		if (Graph == nullptr || Roots.Num() != 1
			|| !ImplementsExactInterface(Blueprint, InterfaceClass))
		{
			return false;
		}
		TSet<UEdGraphNode*> Reachable;
		VisitPoseUpstream(Roots[0], Reachable);
		int32 SlotCount = 0;
		for (UEdGraphNode* Node : Reachable)
		{
			SlotCount += Node->IsA<UAnimGraphNode_Slot>() ? 1 : 0;
		}
		bOutNoSlot = SlotCount == 0;
		return Reachable.Num() >= 2 && bOutNoSlot;
	}

	bool InspectHostGraph(
		UAnimBlueprint* Host, const UClass* InterfaceClass,
		const UClass* CalmClass, const bool bExpectComplete,
		bool& bOutLocomotionBase, bool& bOutNoSlot,
		bool& bOutCompiledLinked)
	{
		bOutLocomotionBase = false;
		bOutNoSlot = false;
		bOutCompiledLinked = false;
		UEdGraph* Graph = FindGraph(Host, UEdGraphSchema_K2::GN_AnimGraph);
		TArray<UAnimGraphNode_Root*> Roots;
		if (Graph)
		{
			Graph->GetNodesOfClass(Roots);
		}
		if (Graph == nullptr || Roots.Num() != 1)
		{
			return false;
		}
		TSet<UEdGraphNode*> Reachable;
		VisitPoseUpstream(Roots[0], Reachable);
		TArray<UAnimGraphNode_BlendSpacePlayer*> Bases;
		TArray<UAnimGraphNode_LinkedAnimLayer*> Linked;
		TArray<UAnimGraphNode_LayeredBoneBlend*> Blends;
		int32 Slots = 0;
		for (UEdGraphNode* Node : Reachable)
		{
			if (auto* Value = Cast<UAnimGraphNode_BlendSpacePlayer>(Node))
			{
				Bases.Add(Value);
			}
			if (auto* Value = Cast<UAnimGraphNode_LinkedAnimLayer>(Node))
			{
				Linked.Add(Value);
			}
			if (auto* Value = Cast<UAnimGraphNode_LayeredBoneBlend>(Node))
			{
				Blends.Add(Value);
			}
			Slots += Node->IsA<UAnimGraphNode_Slot>() ? 1 : 0;
		}
		bOutNoSlot = Slots == 0;
		if (!bExpectComplete)
		{
			const TArray<UEdGraphPin*> RootInputs = PosePins(Roots[0], EGPD_Input);
			UEdGraphPin* SpeedInput = Bases.Num() == 1
				? Bases[0]->FindPin(TEXT("X"), EGPD_Input) : nullptr;
			bOutLocomotionBase = Reachable.Num() == 2
				&& Bases.Num() == 1 && Linked.Num() == 0
				&& Blends.Num() == 0 && RootInputs.Num() == 1
				&& PinComesFrom(RootInputs[0], Bases[0])
				&& PinComesFromVariable(SpeedInput, TEXT("GroundSpeed"))
				&& Bases[0]->Node.GetBlendSpace()
					== LoadObject<UBlendSpace>(nullptr, LocomotionPath);
			return bOutLocomotionBase && bOutNoSlot;
		}
		if (Reachable.Num() != 4 || Bases.Num() != 1
			|| Linked.Num() != 1 || Blends.Num() != 1)
		{
			return false;
		}
		const FAnimNode_LinkedAnimLayer& LinkedNode = Linked[0]->Node;
		const FAnimNode_LayeredBoneBlend& BlendNode = Blends[0]->Node;
		const TArray<UEdGraphPin*> BlendInputs = PosePins(Blends[0], EGPD_Input);
		const TArray<UEdGraphPin*> RootInputs = PosePins(Roots[0], EGPD_Input);
		UEdGraphPin* SpeedInput = Bases[0]->FindPin(TEXT("X"), EGPD_Input);
		bOutLocomotionBase = BlendInputs.Num() == 2 && RootInputs.Num() == 1
			&& PinComesFrom(BlendInputs[0], Bases[0])
			&& PinComesFrom(BlendInputs[1], Linked[0])
			&& PinComesFrom(RootInputs[0], Blends[0])
			&& PinComesFromVariable(SpeedInput, TEXT("GroundSpeed"))
			&& Bases[0]->Node.GetBlendSpace()
				== LoadObject<UBlendSpace>(nullptr, LocomotionPath)
			&& BlendNode.BlendMode == ELayeredBoneBlendMode::BranchFilter
			&& BlendNode.LayerSetup.Num() == 1
			&& BlendNode.LayerSetup[0].BranchFilters.Num() == 1
			&& BlendNode.LayerSetup[0].BranchFilters[0].BoneName
				== TEXT("spine_01")
			&& BlendNode.BlendWeights.Num() == 1
			&& FMath::IsNearlyEqual(BlendNode.BlendWeights[0], 1.0f)
			&& LinkedNode.Interface == InterfaceClass
			&& LinkedNode.InstanceClass == CalmClass
			&& LinkedNode.Layer == LayerName;

		const IAnimClassInterface* ClassInterface = Host && Host->GeneratedClass
			? IAnimClassInterface::GetFromClass(Host->GeneratedClass) : nullptr;
		int32 CompiledLinkedCount = 0;
		if (ClassInterface)
		{
			for (const FStructProperty* Property
				: ClassInterface->GetLinkedAnimLayerNodeProperties())
			{
				CompiledLinkedCount += Property && Property->Struct
					&& Property->Struct->IsChildOf(
						FAnimNode_LinkedAnimLayer::StaticStruct()) ? 1 : 0;
			}
		}
		bOutCompiledLinked = CompiledLinkedCount == 1;
		return bOutLocomotionBase && bOutNoSlot && bOutCompiledLinked;
	}

	bool InspectStateTree(
		UStateTree* Tree, const UClass* AlertClass,
		const bool bExpectComplete)
	{
		const UStateTreeEditorData* Data = Tree
			? Cast<UStateTreeEditorData>(Tree->EditorData) : nullptr;
		const UStateTreeState* Root = Data && Data->SubTrees.Num() == 1
			? Data->SubTrees[0].Get() : nullptr;
		if (Tree == nullptr || !Tree->IsReadyToRun() || Root == nullptr
			|| Root->Name != TEXT("Root"))
		{
			return false;
		}
		if (!bExpectComplete)
		{
			return Root->Children.Num() == 1 && Root->Children[0]
				&& Root->Children[0]->Name == TEXT("Calm")
				&& Root->Children[0]->Transitions.Num() == 0;
		}
		if (Root->Children.Num() != 2 || Root->Children[0] == nullptr
			|| Root->Children[1] == nullptr
			|| Root->Children[0]->Name != TEXT("Calm")
			|| Root->Children[1]->Name != TEXT("Alert"))
		{
			return false;
		}
		const UStateTreeState* Calm = Root->Children[0].Get();
		const UStateTreeState* Alert = Root->Children[1].Get();
		if (Calm->Transitions.Num() != 1 || Alert->Transitions.Num() != 1
			|| Alert->Tasks.Num() != 1)
		{
			return false;
		}
		const FStateTreeTransition& ToAlert = Calm->Transitions[0];
		const FStateTreeTransition& ToCalm = Alert->Transitions[0];
		const bool bLinks = ToAlert.State.Name == TEXT("Alert")
			&& ToCalm.State.Name == TEXT("Calm")
			&& ToAlert.Trigger == EStateTreeTransitionTrigger::OnTick
			&& ToCalm.Trigger == EStateTreeTransitionTrigger::OnTick
			&& ToAlert.Conditions.Num() == 1 && ToCalm.Conditions.Num() == 1
			&& ToAlert.Conditions[0].Node.GetScriptStruct()
				== FAlertStrideSignalCondition::StaticStruct()
			&& ToCalm.Conditions[0].Node.GetScriptStruct()
				== FAlertStrideSignalCondition::StaticStruct();
		if (!bLinks)
		{
			return false;
		}
		const FAlertStrideSignalConditionInstanceData* AlertCondition =
			ToAlert.Conditions[0].GetInstance().GetPtr<
				FAlertStrideSignalConditionInstanceData>();
		const FAlertStrideSignalConditionInstanceData* CalmCondition =
			ToCalm.Conditions[0].GetInstance().GetPtr<
				FAlertStrideSignalConditionInstanceData>();
		const FAlertStrideLinkLayerTaskInstanceData* LinkData =
			Alert->Tasks[0].GetInstance().GetPtr<
				FAlertStrideLinkLayerTaskInstanceData>();
		return bLinks && AlertCondition && AlertCondition->bExpectedAlert
			&& CalmCondition && !CalmCondition->bExpectedAlert
			&& Alert->Tasks[0].Node.GetScriptStruct()
				== FAlertStrideLinkLayerTask::StaticStruct()
			&& LinkData && LinkData->AlertLayerClass == AlertClass;
	}
}

FString UAlertStrideVerifierLibrary::InspectAssetSet(
	const FString& RootPackage, const FString& InterfacePackage,
	const bool bExpectComplete)
{
	TSharedRef<FJsonObject> Facts = MakeShared<FJsonObject>();
	Facts->SetStringField(TEXT("root"), RootPackage);
	Facts->SetStringField(TEXT("interface_package"), InterfacePackage);
	Facts->SetBoolField(TEXT("expected_complete"), bExpectComplete);
	UAnimBlueprint* Interface = LoadObject<UAnimBlueprint>(
		nullptr, *PackageObjectPath(InterfacePackage));
	UAnimBlueprint* Host = LoadObject<UAnimBlueprint>(
		nullptr, *ObjectPath(RootPackage, HostName));
	UAnimBlueprint* Calm = LoadObject<UAnimBlueprint>(
		nullptr, *ObjectPath(RootPackage, CalmName));
	UAnimBlueprint* Alert = LoadObject<UAnimBlueprint>(
		nullptr, *ObjectPath(RootPackage, AlertName));
	UStateTree* Tree = LoadObject<UStateTree>(
		nullptr, *ObjectPath(RootPackage, StateTreeName));
	const bool bInventory = Interface && Host && Calm && Alert && Tree
		&& Interface->GeneratedClass && Host->GeneratedClass
		&& Calm->GeneratedClass && Alert->GeneratedClass;
	const UClass* InterfaceClass = Interface ? Interface->GeneratedClass : nullptr;
	bool bCalmNoSlot = false;
	bool bAlertNoSlot = false;
	const bool bCalmLayer = bInventory && InspectLayerGraph(
		Calm, InterfaceClass, bCalmNoSlot);
	const bool bAlertLayer = bInventory && InspectLayerGraph(
		Alert, InterfaceClass, bAlertNoSlot);
	bool bLocomotionBase = false;
	bool bHostNoSlot = false;
	bool bCompiledLinked = false;
	const bool bHost = bInventory && InspectHostGraph(
		Host, InterfaceClass, Calm ? Calm->GeneratedClass : nullptr,
		bExpectComplete, bLocomotionBase, bHostNoSlot, bCompiledLinked);
	const bool bTree = bInventory && InspectStateTree(
		Tree, Alert ? Alert->GeneratedClass : nullptr, bExpectComplete);
	const bool bInterface = bInventory
		&& Interface->BlueprintType == BPTYPE_Interface
		&& InterfaceClass->IsChildOf(UAnimLayerInterface::StaticClass())
		&& FindGraph(Interface, LayerName) != nullptr;
	const bool bNoSlots = bCalmNoSlot && bAlertNoSlot && bHostNoSlot;
	const bool bPass = bInventory && bInterface && bCalmLayer && bAlertLayer
		&& bHost && bTree && bNoSlots;
	Facts->SetBoolField(TEXT("probe_ok"), bPass);
	Facts->SetBoolField(TEXT("inventory_exact"), bInventory);
	Facts->SetBoolField(TEXT("declared_layer_interface"), bInterface);
	Facts->SetBoolField(TEXT("state_tree_calm_alert_bidirectional"), bTree);
	Facts->SetBoolField(TEXT("host_linked_layer_route"), bHost);
	Facts->SetBoolField(TEXT("locomotion_is_base_pose"), bLocomotionBase);
	Facts->SetBoolField(TEXT("compiled_linked_node_present"), bCompiledLinked);
	Facts->SetBoolField(TEXT("calm_layer_implements_interface"), bCalmLayer);
	Facts->SetBoolField(TEXT("alert_layer_implements_interface"), bAlertLayer);
	Facts->SetBoolField(TEXT("no_slot_or_montage_route"), bNoSlots);
	return SerializeFacts(Facts);
}
