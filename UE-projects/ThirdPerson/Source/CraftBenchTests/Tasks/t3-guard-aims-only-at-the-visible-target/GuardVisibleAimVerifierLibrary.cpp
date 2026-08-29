// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimVerifierLibrary.h"

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimTypes.h"

#include "Animation/AimOffsetBlendSpace.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/BlendSpace.h"
#include "AnimationGraphSchema.h"
#include "AnimGraphNode_BlendSpacePlayer.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_RotationOffsetBlendSpace.h"
#include "AnimGraphNode_Slot.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_VariableGet.h"

namespace
{
	constexpr TCHAR LocomotionPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run.BS_Idle_Walk_Run");
	constexpr TCHAR AimOffsetPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Rifle/AIM/AO_Rifle.AO_Rifle");

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

	UEdGraphPin* PosePin(const UEdGraphNode* Node, EEdGraphPinDirection Direction)
	{
		if (Node == nullptr)
		{
			return nullptr;
		}
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->Direction == Direction
				&& UAnimationGraphSchema::IsPosePin(Pin->PinType))
			{
				return Pin;
			}
		}
		return nullptr;
	}

	bool LinkedFrom(const UEdGraphPin* Input, const UEdGraphNode* Node)
	{
		return Input && Input->LinkedTo.Num() == 1
			&& Input->LinkedTo[0]
			&& Input->LinkedTo[0]->GetOwningNode() == Node;
	}

	bool LinkedVariable(const UEdGraphNode* Node, const TCHAR* PinName,
		const FName VariableName)
	{
		const UEdGraphPin* Pin = Node ? Node->FindPin(PinName, EGPD_Input) : nullptr;
		const UEdGraphPin* Source = Pin && Pin->LinkedTo.Num() == 1
			? Pin->LinkedTo[0] : nullptr;
		const UK2Node_VariableGet* Get = Source
			? Cast<UK2Node_VariableGet>(Source->GetOwningNode()) : nullptr;
		return Get && Get->VariableReference.IsSelfContext()
			&& Get->VariableReference.GetMemberName() == VariableName
			&& Source->PinName == VariableName;
	}
}

FString UGuardVisibleAimVerifierLibrary::InspectAnimBlueprint(
	const UAnimBlueprint* AnimBlueprint, const bool bExpectAimOverlay)
{
	UEdGraph* Graph = FindAnimGraph(AnimBlueprint);
	TArray<UAnimGraphNode_Root*> Roots;
	TArray<UAnimGraphNode_BlendSpacePlayer*> LocomotionNodes;
	TArray<UAnimGraphNode_RotationOffsetBlendSpace*> AimNodes;
	TArray<UAnimGraphNode_Slot*> SlotNodes;
	if (Graph)
	{
		Graph->GetNodesOfClass(Roots);
		Graph->GetNodesOfClass(LocomotionNodes);
		Graph->GetNodesOfClass(AimNodes);
		Graph->GetNodesOfClass(SlotNodes);
	}
	UAnimGraphNode_Root* Root = Roots.Num() == 1 ? Roots[0] : nullptr;
	UAnimGraphNode_BlendSpacePlayer* Locomotion =
		LocomotionNodes.Num() == 1 ? LocomotionNodes[0] : nullptr;
	UAnimGraphNode_RotationOffsetBlendSpace* Aim =
		AimNodes.Num() == 1 ? AimNodes[0] : nullptr;
	const bool bIdentity = AnimBlueprint && AnimBlueprint->ParentClass
		== UGuardVisibleAimAnimInstance::StaticClass()
		&& AnimBlueprint->GeneratedClass
		&& AnimBlueprint->GeneratedClass->IsChildOf(
			UGuardVisibleAimAnimInstance::StaticClass());
	const bool bLocomotionAsset = Locomotion
		&& GetPathNameSafe(Locomotion->Node.GetBlendSpace()) == LocomotionPath;
	const bool bSpeedFeed = LinkedVariable(
		Locomotion, TEXT("X"), TEXT("GroundSpeed"));
	const bool bAimAsset = Aim && Aim->Node.GetBlendSpace()
		&& Aim->Node.GetBlendSpace()->IsA<UAimOffsetBlendSpace>()
		&& GetPathNameSafe(Aim->Node.GetBlendSpace()) == AimOffsetPath;
	const bool bAimFeeds = Aim
		&& LinkedVariable(Aim, TEXT("X"), TEXT("AimYaw"))
		&& LinkedVariable(Aim, TEXT("Y"), TEXT("AimPitch"))
		&& LinkedVariable(Aim, TEXT("Alpha"), TEXT("AimAlpha"));
	const bool bDirectBase = Aim && LinkedFrom(PosePin(Aim, EGPD_Input), Locomotion);
	const UEdGraphNode* ExpectedWriter = bExpectAimOverlay
		? static_cast<UEdGraphNode*>(Aim)
		: static_cast<UEdGraphNode*>(Locomotion);
	const bool bFinalRoute = Root && ExpectedWriter
		&& LinkedFrom(PosePin(Root, EGPD_Input), ExpectedWriter);
	const bool bNoMontageSlot = SlotNodes.Num() == 0;
	const bool bShape = Graph && Roots.Num() == 1
		&& LocomotionNodes.Num() == 1
		&& AimNodes.Num() == (bExpectAimOverlay ? 1 : 0);
	const bool bPass = bIdentity && bShape && bLocomotionAsset && bSpeedFeed
		&& bFinalRoute && bNoMontageSlot
		&& (!bExpectAimOverlay || (bAimAsset && bAimFeeds && bDirectBase));
	return FString::Printf(
		TEXT("{\"probe_ok\":%s,\"expect_aim\":%s,\"identity\":%s,\"root_count\":%d,\"locomotion_count\":%d,\"aim_count\":%d,\"slot_count\":%d,\"locomotion_asset\":%s,\"ground_speed_feed\":%s,\"aim_offset_asset\":%s,\"aim_coordinate_feeds\":%s,\"locomotion_is_base_pose\":%s,\"direct_final_route\":%s,\"no_montage_slot\":%s}"),
		bPass ? TEXT("true") : TEXT("false"),
		bExpectAimOverlay ? TEXT("true") : TEXT("false"),
		bIdentity ? TEXT("true") : TEXT("false"), Roots.Num(),
		LocomotionNodes.Num(), AimNodes.Num(), SlotNodes.Num(),
		bLocomotionAsset ? TEXT("true") : TEXT("false"),
		bSpeedFeed ? TEXT("true") : TEXT("false"),
		bAimAsset ? TEXT("true") : TEXT("false"),
		bAimFeeds ? TEXT("true") : TEXT("false"),
		bDirectBase ? TEXT("true") : TEXT("false"),
		bFinalRoute ? TEXT("true") : TEXT("false"),
		bNoMontageSlot ? TEXT("true") : TEXT("false"));
}
