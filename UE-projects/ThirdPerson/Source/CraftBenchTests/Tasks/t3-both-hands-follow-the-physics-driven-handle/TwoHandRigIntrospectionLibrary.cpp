// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandRigIntrospectionLibrary.h"

#include "Animation/AnimBlueprint.h"
#include "Animation/AnimClassInterface.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimNode_CustomProperty.h"
#include "AnimationGraphSchema.h"
#include "AnimGraphNode_ControlRig.h"
#include "AnimGraphNode_CopyPoseFromMesh.h"
#include "AnimGraphNode_ModifyBone.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "AnimGraphNode_TwoBoneIK.h"
#include "AnimNode_ControlRig.h"
#include "ControlRig.h"
#include "ControlRigBlueprintLegacy.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "RigVMCore/RigVMVariableDescription.h"
#include "RigVMModel/Nodes/RigVMUnitNode.h"
#include "RigVMModel/Nodes/RigVMVariableNode.h"
#include "RigVMModel/RigVMGraph.h"
#include "RigVMModel/RigVMLink.h"
#include "RigVMModel/RigVMPin.h"
#include "Rigs/RigHierarchy.h"
#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandPhysicsActors.h"
#include "Units/Execution/RigUnit_BeginExecution.h"
#include "Units/Hierarchy/RigUnit_GetControlTransform.h"
#include "Units/Hierarchy/RigUnit_SetControlTransform.h"
#include "Units/Highlevel/Hierarchy/RigUnit_FABRIK.h"
#include "UObject/UnrealType.h"

namespace
{
	const FName LeftControl(TEXT("hand_l_target"));
	const FName RightControl(TEXT("hand_r_target"));
	const FName LeftVariable(TEXT("LeftHandTarget"));
	const FName RightVariable(TEXT("RightHandTarget"));

	FString ExpectedRigPath(const bool bAdmission)
	{
		return bAdmission
			? TEXT("/Game/__CraftBenchAdmission/t3-both-hands-follow-the-physics-driven-handle/CR_TwoHandPhysicsAdmission.CR_TwoHandPhysicsAdmission")
			: TEXT("/Game/Tasks/t3-both-hands-follow-the-physics-driven-handle/CR_TwoHandPhysics.CR_TwoHandPhysics");
	}

	FString ExpectedAnimPath(const bool bAdmission)
	{
		return bAdmission
			? TEXT("/Game/__CraftBenchAdmission/t3-both-hands-follow-the-physics-driven-handle/ABP_TwoHandPhysicsAdmission.ABP_TwoHandPhysicsAdmission")
			: TEXT("/Game/Tasks/t3-both-hands-follow-the-physics-driven-handle/ABP_TwoHandPhysics.ABP_TwoHandPhysics");
	}

	UEdGraph* FindAnimGraph(const UAnimBlueprint* Blueprint)
	{
		TArray<UEdGraph*> Graphs;
		if (Blueprint)
		{
			const_cast<UAnimBlueprint*>(Blueprint)->GetAllGraphs(Graphs);
		}
		for (UEdGraph* Graph : Graphs)
		{
			if (Graph && Graph->GetFName() == UEdGraphSchema_K2::GN_AnimGraph)
			{
				return Graph;
			}
		}
		return nullptr;
	}

	void VisitAnimUpstream(UEdGraphNode* Node, TSet<UEdGraphNode*>& Visited)
	{
		if (Node == nullptr || Visited.Contains(Node))
		{
			return;
		}
		Visited.Add(Node);
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->Direction == EGPD_Input)
			{
				for (UEdGraphPin* Linked : Pin->LinkedTo)
				{
					VisitAnimUpstream(Linked ? Linked->GetOwningNode() : nullptr, Visited);
				}
			}
		}
	}

	bool HasExactPropertyMappings(const FAnimNode_ControlRig& Node)
	{
		const FArrayProperty* SourceArray = FindFProperty<FArrayProperty>(
			FAnimNode_CustomProperty::StaticStruct(), TEXT("SourcePropertyNames"));
		const FArrayProperty* DestArray = FindFProperty<FArrayProperty>(
			FAnimNode_CustomProperty::StaticStruct(), TEXT("DestPropertyNames"));
		const FNameProperty* SourceName = SourceArray
			? CastField<FNameProperty>(SourceArray->Inner) : nullptr;
		const FNameProperty* DestName = DestArray
			? CastField<FNameProperty>(DestArray->Inner) : nullptr;
		if (SourceArray == nullptr || DestArray == nullptr
			|| SourceName == nullptr || DestName == nullptr)
		{
			return false;
		}
		FScriptArrayHelper Sources(SourceArray,
			SourceArray->ContainerPtrToValuePtr<void>(&Node));
		FScriptArrayHelper Dests(DestArray,
			DestArray->ContainerPtrToValuePtr<void>(&Node));
		if (Sources.Num() != 2 || Dests.Num() != 2)
		{
			return false;
		}
		return SourceName->GetPropertyValue(Sources.GetRawPtr(0)) == LeftVariable
			&& DestName->GetPropertyValue(Dests.GetRawPtr(0)) == LeftVariable
			&& SourceName->GetPropertyValue(Sources.GetRawPtr(1)) == RightVariable
			&& DestName->GetPropertyValue(Dests.GetRawPtr(1)) == RightVariable;
	}

	bool IsPoseLinkedFromSequence(UAnimGraphNode_ControlRig* Node)
	{
		if (Node == nullptr)
		{
			return false;
		}
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->Direction == EGPD_Input
				&& UAnimationGraphSchema::IsPosePin(Pin->PinType)
				&& Pin->LinkedTo.Num() == 1)
			{
				return Pin->LinkedTo[0]->GetOwningNode()
					&& Pin->LinkedTo[0]->GetOwningNode()->IsA<UAnimGraphNode_SequencePlayer>();
			}
		}
		return false;
	}

	bool HasPublicTransformVariable(
		const UControlRigBlueprint* Blueprint, const FName Name)
	{
		for (const FRigVMGraphVariableDescription& Variable : Blueprint->GetMemberVariables())
		{
			if (Variable.Name == Name && Variable.bPublic
				&& (Variable.CPPType == TEXT("FTransform")
					|| Variable.CPPType.EndsWith(TEXT("Transform"))))
			{
				return true;
			}
		}
		return false;
	}

	bool IsExecutionReachable(
		const URigVMGraph* Graph, const URigVMNode* Begin, const URigVMNode* Target)
	{
		TSet<const URigVMNode*> Visited;
		TArray<const URigVMNode*> Pending;
		Pending.Add(Begin);
		while (Pending.Num() > 0)
		{
			const URigVMNode* Current = Pending.Pop();
			if (Current == Target)
			{
				return true;
			}
			if (Current == nullptr || Visited.Contains(Current))
			{
				continue;
			}
			Visited.Add(Current);
			for (const URigVMLink* Link : Graph->GetLinks())
			{
				if (Link && Link->GetSourceNode() == Current
					&& Link->GetSourcePin() && Link->GetTargetPin()
					&& Link->GetSourcePin()->GetCPPType().Contains(TEXT("ExecuteContext"))
					&& Link->GetTargetPin()->GetCPPType().Contains(TEXT("ExecuteContext")))
				{
					Pending.Add(Link->GetTargetNode());
				}
			}
		}
		return false;
	}

	bool HasRigDataLink(
		const URigVMGraph* Graph, const URigVMNode* Source,
		const URigVMNode* Target, const TCHAR* TargetLeaf)
	{
		for (const URigVMLink* Link : Graph->GetLinks())
		{
			if (Link && Link->GetSourceNode() == Source && Link->GetTargetNode() == Target
				&& Link->GetTargetPin()
				&& Link->GetTargetPin()->GetName() == TargetLeaf)
			{
				return true;
			}
		}
		return false;
	}

	FString InspectRig(const UControlRigBlueprint* Blueprint, const bool bComplete)
	{
		if (Blueprint == nullptr || Blueprint->GetHierarchy() == nullptr)
		{
			return TEXT("FAIL RigUsesIndependentHandControls missing_control_rig");
		}
		URigHierarchy* Hierarchy = Blueprint->GetHierarchy();
		for (const FName Bone : {FName(TEXT("upperarm_l")), FName(TEXT("hand_l")),
			FName(TEXT("upperarm_r")), FName(TEXT("hand_r")),
			FName(TEXT("pelvis")), FName(TEXT("foot_l")), FName(TEXT("foot_r"))})
		{
			if (!Hierarchy->Contains(FRigElementKey(Bone, ERigElementType::Bone)))
			{
				return FString::Printf(TEXT("FAIL RigUsesIndependentHandControls missing_bone=%s"),
					*Bone.ToString());
			}
		}
		if (!Hierarchy->Contains(FRigElementKey(LeftControl, ERigElementType::Control))
			|| !Hierarchy->Contains(FRigElementKey(RightControl, ERigElementType::Control))
			|| !HasPublicTransformVariable(Blueprint, LeftVariable)
			|| !HasPublicTransformVariable(Blueprint, RightVariable))
		{
			return TEXT("FAIL RigUsesIndependentHandControls controls_or_public_targets_missing");
		}

		const URigVMGraph* Graph = Blueprint->GetDefaultModel();
		if (Graph == nullptr)
		{
			return TEXT("FAIL RuntimeControlRigComposesOverBasePose rigvm_graph_missing");
		}
		TArray<const URigVMNode*> Begins;
		TArray<const URigVMNode*> Sets;
		TArray<const URigVMNode*> Gets;
		TArray<const URigVMNode*> Fabriks;
		TMap<FName, const URigVMVariableNode*> VariableNodes;
		int32 UnitCount = 0;
		TArray<FString> Banned;
		for (const URigVMNode* Node : Graph->GetNodes())
		{
			const URigVMUnitNode* Unit = Cast<URigVMUnitNode>(Node);
			const UScriptStruct* Struct = Unit ? Unit->GetScriptStruct() : nullptr;
			UnitCount += Unit ? 1 : 0;
			if (Struct == FRigUnit_BeginExecution::StaticStruct()) Begins.Add(Node);
			if (Struct == FRigUnit_SetControlTransform::StaticStruct()) Sets.Add(Node);
			if (Struct == FRigUnit_GetControlTransform::StaticStruct()) Gets.Add(Node);
			if (Struct == FRigUnit_FABRIK::StaticStruct()) Fabriks.Add(Node);
			const FString StructName = GetNameSafe(Struct);
			if (StructName.Contains(TEXT("TwoBoneIK"))
				|| StructName.Contains(TEXT("SetBone"))
				|| (StructName.Contains(TEXT("SetTransform"))
					&& Struct != FRigUnit_SetControlTransform::StaticStruct())
				|| StructName.Contains(TEXT("SetTranslation"))
				|| StructName.Contains(TEXT("SetRotation"))
				|| StructName.Contains(TEXT("SetPose"))
				|| StructName.Contains(TEXT("Mirror")))
			{
				Banned.Add(StructName);
			}
			if (const URigVMVariableNode* Variable = Cast<URigVMVariableNode>(Node))
			{
				VariableNodes.Add(Variable->GetVariableName(), Variable);
				if (Variable->GetVariableName().ToString().Contains(TEXT("Mirror")))
				{
					Banned.Add(Variable->GetVariableName().ToString());
				}
			}
		}
		if (Banned.Num() != 0)
		{
			return TEXT("FAIL NoDirectTransformTwoBoneIKOrMirror nodes=")
				+ FString::Join(Banned, TEXT(","));
		}
		if (!bComplete)
		{
			return (UnitCount == 0 && VariableNodes.Num() == 0)
				? TEXT("PASS RIG_BASELINE skeleton=1 controls=2 public_targets=2 units=0")
				: TEXT("FAIL RIG_BASELINE expected_empty_forward_solve");
		}
		if (UnitCount != 7 || Begins.Num() != 1 || Sets.Num() != 2
			|| Gets.Num() != 2 || Fabriks.Num() != 2
			|| VariableNodes.Num() != 2
			|| !VariableNodes.Contains(LeftVariable)
			|| !VariableNodes.Contains(RightVariable))
		{
			return FString::Printf(
				TEXT("FAIL RuntimeControlRigComposesOverBasePose units=%d begin=%d set=%d get=%d fabrik=%d variables=%d"),
				UnitCount, Begins.Num(), Sets.Num(), Gets.Num(), Fabriks.Num(),
				VariableNodes.Num());
		}
		for (const URigVMNode* Fabrik : Fabriks)
		{
			if (!IsExecutionReachable(Graph, Begins[0], Fabrik))
			{
				return TEXT("FAIL RuntimeControlRigComposesOverBasePose disconnected_fabrik");
			}
		}
		TSet<FName> SolvedEffectors;
		TSet<FName> ReadControls;
		TSet<FName> SetControls;
		TMap<FName, const URigVMNode*> SetByControl;
		TMap<FName, const URigVMNode*> GetByControl;
		TMap<FName, const URigVMNode*> FabrikByEffector;
		for (const URigVMNode* Set : Sets)
		{
			const URigVMPin* Pin = Set->FindPin(TEXT("Control"));
			if (Pin)
			{
				const FName Control(*Pin->GetDefaultValue());
				SetControls.Add(Control);
				SetByControl.Add(Control, Set);
			}
		}
		for (const URigVMNode* Get : Gets)
		{
			const URigVMPin* Pin = Get->FindPin(TEXT("Control"));
			if (Pin)
			{
				const FName Control(*Pin->GetDefaultValue());
				ReadControls.Add(Control);
				GetByControl.Add(Control, Get);
			}
		}
		for (const URigVMNode* Fabrik : Fabriks)
		{
			const URigVMPin* Effector = Fabrik->FindPin(TEXT("EffectorBone"));
			if (Effector)
			{
				const FName EffectorName(*Effector->GetDefaultValue());
				SolvedEffectors.Add(EffectorName);
				FabrikByEffector.Add(EffectorName, Fabrik);
			}
		}
		const bool bExactSetControls = SetControls.Num() == 2
			&& SetControls.Contains(LeftControl) && SetControls.Contains(RightControl);
		const bool bExactReadControls = ReadControls.Num() == 2
			&& ReadControls.Contains(LeftControl) && ReadControls.Contains(RightControl);
		const bool bExactEffectors = SolvedEffectors.Num() == 2
			&& SolvedEffectors.Contains(TEXT("hand_l"))
			&& SolvedEffectors.Contains(TEXT("hand_r"));
		if (!bExactSetControls || !bExactReadControls || !bExactEffectors)
		{
			return TEXT("FAIL RigUsesIndependentHandControls asymmetric_route_mismatch");
		}
		const URigVMNode* LeftSet = SetByControl.FindRef(LeftControl);
		const URigVMNode* RightSet = SetByControl.FindRef(RightControl);
		const URigVMNode* LeftGet = GetByControl.FindRef(LeftControl);
		const URigVMNode* RightGet = GetByControl.FindRef(RightControl);
		const URigVMNode* LeftFabrik = FabrikByEffector.FindRef(TEXT("hand_l"));
		const URigVMNode* RightFabrik = FabrikByEffector.FindRef(TEXT("hand_r"));
		if (!HasRigDataLink(Graph, VariableNodes.FindRef(LeftVariable),
				LeftSet, TEXT("Transform"))
			|| !HasRigDataLink(Graph, VariableNodes.FindRef(RightVariable),
				RightSet, TEXT("Transform"))
			|| !HasRigDataLink(Graph, LeftGet, LeftFabrik, TEXT("EffectorTransform"))
			|| !HasRigDataLink(Graph, RightGet, RightFabrik, TEXT("EffectorTransform")))
		{
			return TEXT("FAIL RigUsesIndependentHandControls left_right_data_routes_mismatch");
		}
		return TEXT("PASS RIG_COMPLETE controls=2 public_targets=2 set_controls=2 get_controls=2 fabrik=2 independent_effectors=2 banned=0 reachable=1");
	}

	FString InspectAnimGraph(
		const UAnimBlueprint* Blueprint, const UControlRigBlueprint* Rig,
		const bool bComplete)
	{
		if (Blueprint == nullptr
			|| Blueprint->ParentClass != UTwoHandRigAnimInstanceBase::StaticClass())
		{
			return TEXT("FAIL RuntimeControlRigComposesOverBasePose wrong_anim_parent");
		}
		UEdGraph* Graph = FindAnimGraph(Blueprint);
		TArray<UAnimGraphNode_Root*> Roots;
		if (Graph) Graph->GetNodesOfClass(Roots);
		if (Graph == nullptr || Roots.Num() != 1)
		{
			return FString::Printf(TEXT("FAIL RuntimeControlRigComposesOverBasePose roots=%d"),
				Roots.Num());
		}
		TSet<UEdGraphNode*> Reachable;
		VisitAnimUpstream(Roots[0], Reachable);
		TArray<UAnimGraphNode_ControlRig*> RigNodes;
		int32 Sequences = 0;
		TArray<FString> Banned;
		for (UEdGraphNode* Node : Reachable)
		{
			if (UAnimGraphNode_ControlRig* RigNode = Cast<UAnimGraphNode_ControlRig>(Node))
			{
				RigNodes.Add(RigNode);
			}
			Sequences += Node->IsA<UAnimGraphNode_SequencePlayer>() ? 1 : 0;
			if (Node->IsA<UAnimGraphNode_TwoBoneIK>()) Banned.Add(TEXT("TwoBoneIK"));
			if (Node->IsA<UAnimGraphNode_ModifyBone>()) Banned.Add(TEXT("ModifyBone"));
			if (Node->IsA<UAnimGraphNode_CopyPoseFromMesh>()) Banned.Add(TEXT("CopyPose"));
			if (Node->GetClass()->GetName().Contains(TEXT("Mirror"))) Banned.Add(TEXT("Mirror"));
		}
		if (Banned.Num() != 0)
		{
			return TEXT("FAIL NoDirectTransformTwoBoneIKOrMirror anim_nodes=")
				+ FString::Join(Banned, TEXT(","));
		}
		if (!bComplete)
		{
			return RigNodes.Num() == 0 && Sequences == 1
				&& Reachable.Num() == 2
				? TEXT("PASS ANIM_BASELINE base_sequence=1 control_rig=0")
				: FString::Printf(
					TEXT("FAIL ANIM_BASELINE reachable=%d sequence=%d control_rig=%d"),
					Reachable.Num(), Sequences, RigNodes.Num());
		}
		if (RigNodes.Num() != 1 || Sequences != 1 || Reachable.Num() != 3
			|| !IsPoseLinkedFromSequence(RigNodes[0])
			|| RigNodes[0]->Node.GetControlRigAssetReference().GetBlueprintClass()
				!= Rig->GeneratedClass
			|| !HasExactPropertyMappings(RigNodes[0]->Node))
		{
			return FString::Printf(
				TEXT("FAIL RuntimeControlRigComposesOverBasePose reachable=%d sequence=%d control_rig=%d base_link=%d rig_class=%d property_mappings=%d"),
				Reachable.Num(), Sequences, RigNodes.Num(),
				RigNodes.Num() == 1 && IsPoseLinkedFromSequence(RigNodes[0]),
				RigNodes.Num() == 1
					&& RigNodes[0]->Node.GetControlRigAssetReference().GetBlueprintClass()
						== Rig->GeneratedClass,
				RigNodes.Num() == 1 && HasExactPropertyMappings(RigNodes[0]->Node));
		}
		UClass* GeneratedClass = Blueprint->GeneratedClass;
		UAnimInstance* DefaultInstance = GeneratedClass
			? Cast<UAnimInstance>(GeneratedClass->GetDefaultObject()) : nullptr;
		IAnimClassInterface* Interface = GeneratedClass
			? IAnimClassInterface::GetFromClass(GeneratedClass) : nullptr;
		int32 CompiledNodes = 0;
		FAnimNode_ControlRig* CompiledNode = nullptr;
		if (DefaultInstance && Interface)
		{
			for (const FStructProperty* Property : Interface->GetAnimNodeProperties())
			{
				if (Property && Property->Struct
					&& Property->Struct->IsChildOf(FAnimNode_ControlRig::StaticStruct()))
				{
					++CompiledNodes;
					CompiledNode = Property->ContainerPtrToValuePtr<FAnimNode_ControlRig>(DefaultInstance);
				}
			}
		}
		if (CompiledNodes != 1 || CompiledNode == nullptr
			|| CompiledNode->GetControlRigAssetReference().GetBlueprintClass()
				!= Rig->GeneratedClass
			|| !HasExactPropertyMappings(*CompiledNode))
		{
			return FString::Printf(
				TEXT("FAIL RuntimeControlRigComposesOverBasePose compiled_nodes=%d class=%s property_mappings=%d"),
				CompiledNodes, *GetPathNameSafe(
					CompiledNode
						? CompiledNode->GetControlRigAssetReference().GetBlueprintClass().Get()
						: nullptr),
				CompiledNode && HasExactPropertyMappings(*CompiledNode));
		}
		return TEXT("PASS ANIM_COMPLETE base_sequence=1 runtime_control_rig=1 compiled_node=1 exact_property_mappings=2 banned=0");
	}
}

FString UTwoHandRigIntrospectionLibrary::InspectAssets(
	const UObject* ControlRigBlueprintObject,
	const UObject* AnimBlueprintObject,
	const bool bExpectComplete,
	const bool bAdmission)
{
	const UControlRigBlueprint* Rig = Cast<UControlRigBlueprint>(ControlRigBlueprintObject);
	const UAnimBlueprint* Anim = Cast<UAnimBlueprint>(AnimBlueprintObject);
	if (GetPathNameSafe(Rig) != ExpectedRigPath(bAdmission)
		|| GetPathNameSafe(Anim) != ExpectedAnimPath(bAdmission))
	{
		return FString::Printf(TEXT("FAIL EXACT_ASSET_ID rig=%s anim=%s"),
			*GetPathNameSafe(Rig), *GetPathNameSafe(Anim));
	}
	FString RigResult = InspectRig(Rig, bExpectComplete);
	if (!RigResult.StartsWith(TEXT("PASS")))
	{
		return RigResult;
	}
	FString AnimResult = InspectAnimGraph(Anim, Rig, bExpectComplete);
	if (!AnimResult.StartsWith(TEXT("PASS")))
	{
		return AnimResult;
	}
	return FString::Printf(
		TEXT("PASS TWO_HAND_ASSET_READBACK admission=%d complete=%d %s %s"),
		bAdmission ? 1 : 0, bExpectComplete ? 1 : 0, *RigResult, *AnimResult);
}
