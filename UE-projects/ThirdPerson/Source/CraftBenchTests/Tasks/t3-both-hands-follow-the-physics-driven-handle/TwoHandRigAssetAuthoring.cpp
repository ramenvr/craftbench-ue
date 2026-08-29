// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandRigAssetAuthoring.h"

#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandPhysicsActors.h"
#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandPhysicsFunctionalTest.h"
#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandRigIntrospectionLibrary.h"

#include "Animation/AnimBlueprint.h"
#include "Animation/AnimSequence.h"
#include "AnimationGraphSchema.h"
#include "AnimGraphNode_ControlRig.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "ControlRig.h"
#include "ControlRigBlueprintLegacy.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "RigVMModel/Nodes/RigVMUnitNode.h"
#include "RigVMModel/Nodes/RigVMVariableNode.h"
#include "RigVMModel/RigVMController.h"
#include "RigVMModel/RigVMGraph.h"
#include "Rigs/RigHierarchyController.h"
#include "Rigs/RigHierarchyElements.h"
#include "Units/Execution/RigUnit_BeginExecution.h"
#include "Units/Hierarchy/RigUnit_GetControlTransform.h"
#include "Units/Hierarchy/RigUnit_SetControlTransform.h"
#include "Units/Highlevel/Hierarchy/RigUnit_FABRIK.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

namespace
{
	constexpr TCHAR MannyMeshPath[] =
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple");
	constexpr TCHAR IdleSequencePath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle");
	constexpr TCHAR CubePath[] = TEXT("/Engine/BasicShapes/Cube.Cube");
	const FName LeftControl(TEXT("hand_l_target"));
	const FName RightControl(TEXT("hand_r_target"));

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

	UEdGraph* FindAnimGraph(UAnimBlueprint* Blueprint)
	{
		TArray<UEdGraph*> Graphs;
		if (Blueprint) Blueprint->GetAllGraphs(Graphs);
		for (UEdGraph* Graph : Graphs)
		{
			if (Graph && Graph->GetFName() == UEdGraphSchema_K2::GN_AnimGraph)
			{
				return Graph;
			}
		}
		return nullptr;
	}

	template <typename TNode>
	TNode* AddAnimNode(UEdGraph* Graph, int32 X, int32 Y)
	{
		TNode* Node = NewObject<TNode>(Graph);
		if (Node)
		{
			Graph->AddNode(Node, false, false);
			Node->CreateNewGuid();
			Node->PostPlacedNewNode();
			Node->AllocateDefaultPins();
			Node->NodePosX = X;
			Node->NodePosY = Y;
		}
		return Node;
	}

	UEdGraphPin* PosePin(UEdGraphNode* Node, EEdGraphPinDirection Direction)
	{
		if (Node)
		{
			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (Pin && Pin->Direction == Direction
					&& UAnimationGraphSchema::IsPosePin(Pin->PinType))
				{
					return Pin;
				}
			}
		}
		return nullptr;
	}

	bool SetRigDefault(
		URigVMController* Controller, const URigVMNode* Node,
		const TCHAR* Pin, const FString& Value)
	{
		return Controller && Node && Controller->SetPinDefaultValue(
			Node->GetNodePath() + TEXT(".") + Pin, Value,
			true, false, false, false, true);
	}

	bool LinkRig(
		URigVMController* Controller, const URigVMNode* Source,
		const TCHAR* SourcePin, const URigVMNode* Target, const TCHAR* TargetPin)
	{
		return Controller && Source && Target && Controller->AddLink(
			Source->GetNodePath() + TEXT(".") + SourcePin,
			Target->GetNodePath() + TEXT(".") + TargetPin, false, false);
	}
}

FString UTwoHandRigAssetAuthoring::BuildControlRig(
	UObject* ControlRigBlueprintObject, const bool bComplete)
{
	UControlRigBlueprint* Blueprint = Cast<UControlRigBlueprint>(ControlRigBlueprintObject);
	USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, MannyMeshPath);
	if (Blueprint == nullptr || Mesh == nullptr || Mesh->GetSkeleton() == nullptr)
	{
		return TEXT("FAIL TWO_HAND_RIG_AUTHOR_INPUT");
	}
	URigHierarchyController* HierarchyController = Blueprint->GetHierarchyController();
	URigVMGraph* Graph = Blueprint->GetDefaultModel();
	URigVMController* Controller = Blueprint->GetController(Graph);
	if (HierarchyController == nullptr || Graph == nullptr || Controller == nullptr)
	{
		return TEXT("FAIL TWO_HAND_RIG_AUTHOR_CONTROLLERS");
	}
	if (Blueprint->GetHierarchy()->Num() != 0 || Graph->GetNodes().Num() != 0
		|| Blueprint->GetMemberVariables().Num() != 0)
	{
		return TEXT("FAIL TWO_HAND_RIG_AUTHOR_EXPECTED_FRESH_EMPTY_ASSET");
	}

	HierarchyController->ImportBones(
		Mesh->GetRefSkeleton(), NAME_None, false, false, false, false);
	Blueprint->GetSourceHierarchyImport() = Mesh->GetSkeleton();
	Blueprint->SetPreviewMesh(Mesh);
	FRigControlSettings Settings;
	Settings.AnimationType = ERigControlAnimationType::AnimationControl;
	Settings.ControlType = ERigControlType::EulerTransform;
	Settings.bShapeVisible = true;
	const FRigControlValue Identity = FRigControlValue::Make(FEulerTransform());
	const FRigElementKey LeftKey = HierarchyController->AddControl(
		LeftControl, FRigElementKey(), Settings, Identity,
		FTransform::Identity, FTransform::Identity, false, false);
	const FRigElementKey RightKey = HierarchyController->AddControl(
		RightControl, FRigElementKey(), Settings, Identity,
		FTransform::Identity, FTransform::Identity, false, false);
	const FString TransformTypePath =
		TBaseStructure<FTransform>::Get()->GetPathName();
	if (!LeftKey.IsValid() || !RightKey.IsValid()
		|| Blueprint->AddMemberVariable(TEXT("LeftHandTarget"), TransformTypePath,
			true, false).IsNone()
		|| Blueprint->AddMemberVariable(TEXT("RightHandTarget"), TransformTypePath,
			true, false).IsNone())
	{
		return TEXT("FAIL TWO_HAND_RIG_AUTHOR_HIERARCHY_OR_VARIABLES");
	}

	if (bComplete)
	{
		URigVMUnitNode* Begin = Controller->AddUnitNode(
			FRigUnit_BeginExecution::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(-1000.0, 0.0), TEXT("ForwardSolve"), false, false);
		URigVMVariableNode* LeftVariable = Controller->AddVariableNode(
			TEXT("LeftHandTarget"), TEXT("FTransform"),
			TBaseStructure<FTransform>::Get(), true, TEXT(""),
			FVector2D(-950.0, -300.0), TEXT("LeftTargetInput"), false, false);
		URigVMVariableNode* RightVariable = Controller->AddVariableNode(
			TEXT("RightHandTarget"), TEXT("FTransform"),
			TBaseStructure<FTransform>::Get(), true, TEXT(""),
			FVector2D(-950.0, 350.0), TEXT("RightTargetInput"), false, false);
		URigVMUnitNode* SetLeft = Controller->AddUnitNode(
			FRigUnit_SetControlTransform::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(-650.0, -180.0), TEXT("SetLeftHandControl"), false, false);
		URigVMUnitNode* SetRight = Controller->AddUnitNode(
			FRigUnit_SetControlTransform::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(-400.0, 180.0), TEXT("SetRightHandControl"), false, false);
		URigVMUnitNode* GetLeft = Controller->AddUnitNode(
			FRigUnit_GetControlTransform::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(-400.0, -430.0), TEXT("GetLeftHandControl"), false, false);
		URigVMUnitNode* GetRight = Controller->AddUnitNode(
			FRigUnit_GetControlTransform::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(-150.0, 430.0), TEXT("GetRightHandControl"), false, false);
		URigVMUnitNode* LeftFabrik = Controller->AddUnitNode(
			FRigUnit_FABRIK::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(-100.0, -150.0), TEXT("SolveLeftArmFABRIK"), false, false);
		URigVMUnitNode* RightFabrik = Controller->AddUnitNode(
			FRigUnit_FABRIK::StaticStruct(), FRigUnit::GetMethodName(),
			FVector2D(250.0, 150.0), TEXT("SolveRightArmFABRIK"), false, false);
		if (!Begin || !LeftVariable || !RightVariable || !SetLeft || !SetRight
			|| !GetLeft || !GetRight || !LeftFabrik || !RightFabrik)
		{
			return TEXT("FAIL TWO_HAND_RIG_AUTHOR_NODE_CREATE");
		}
		const bool bDefaults =
			SetRigDefault(Controller, SetLeft, TEXT("Control"), LeftControl.ToString())
			&& SetRigDefault(Controller, SetLeft, TEXT("Space"), TEXT("GlobalSpace"))
			&& SetRigDefault(Controller, SetRight, TEXT("Control"), RightControl.ToString())
			&& SetRigDefault(Controller, SetRight, TEXT("Space"), TEXT("GlobalSpace"))
			&& SetRigDefault(Controller, GetLeft, TEXT("Control"), LeftControl.ToString())
			&& SetRigDefault(Controller, GetLeft, TEXT("Space"), TEXT("GlobalSpace"))
			&& SetRigDefault(Controller, GetRight, TEXT("Control"), RightControl.ToString())
			&& SetRigDefault(Controller, GetRight, TEXT("Space"), TEXT("GlobalSpace"))
			&& SetRigDefault(Controller, LeftFabrik, TEXT("StartBone"), TEXT("upperarm_l"))
			&& SetRigDefault(Controller, LeftFabrik, TEXT("EffectorBone"), TEXT("hand_l"))
			&& SetRigDefault(Controller, LeftFabrik, TEXT("Precision"), TEXT("0.100000"))
			&& SetRigDefault(Controller, LeftFabrik, TEXT("MaxIterations"), TEXT("12"))
			&& SetRigDefault(Controller, RightFabrik, TEXT("StartBone"), TEXT("upperarm_r"))
			&& SetRigDefault(Controller, RightFabrik, TEXT("EffectorBone"), TEXT("hand_r"))
			&& SetRigDefault(Controller, RightFabrik, TEXT("Precision"), TEXT("0.100000"))
			&& SetRigDefault(Controller, RightFabrik, TEXT("MaxIterations"), TEXT("12"));
		const bool bLinks =
			LinkRig(Controller, Begin, TEXT("ExecuteContext"), SetLeft, TEXT("ExecuteContext"))
			&& LinkRig(Controller, SetLeft, TEXT("ExecuteContext"), SetRight, TEXT("ExecuteContext"))
			&& LinkRig(Controller, SetRight, TEXT("ExecuteContext"), LeftFabrik, TEXT("ExecuteContext"))
			&& LinkRig(Controller, LeftFabrik, TEXT("ExecuteContext"), RightFabrik, TEXT("ExecuteContext"))
			&& LinkRig(Controller, LeftVariable, TEXT("Value"), SetLeft, TEXT("Transform"))
			&& LinkRig(Controller, RightVariable, TEXT("Value"), SetRight, TEXT("Transform"))
			&& LinkRig(Controller, GetLeft, TEXT("Transform"), LeftFabrik, TEXT("EffectorTransform"))
			&& LinkRig(Controller, GetRight, TEXT("Transform"), RightFabrik, TEXT("EffectorTransform"));
		if (!bDefaults || !bLinks)
		{
			return FString::Printf(TEXT("FAIL TWO_HAND_RIG_AUTHOR_WIRING defaults=%d links=%d"),
				bDefaults ? 1 : 0, bLinks ? 1 : 0);
		}
	}

	Blueprint->PropagateHierarchyFromBPToInstances();
	Blueprint->RecompileVM();
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate || !SaveAsset(Blueprint))
	{
		return FString::Printf(TEXT("FAIL TWO_HAND_RIG_AUTHOR_COMPILE_SAVE status=%d"),
			static_cast<int32>(Blueprint->Status));
	}
	return FString::Printf(TEXT("PASS TWO_HAND_RIG_AUTHORED complete=%d asset=%s"),
		bComplete ? 1 : 0, *Blueprint->GetPathName());
}

FString UTwoHandRigAssetAuthoring::BuildAnimGraph(
	UAnimBlueprint* AnimBlueprint, UObject* ControlRigBlueprintObject,
	const bool bComplete)
{
	UControlRigBlueprint* Rig = Cast<UControlRigBlueprint>(ControlRigBlueprintObject);
	UAnimSequence* Idle = LoadObject<UAnimSequence>(nullptr, IdleSequencePath);
	if (AnimBlueprint == nullptr || Rig == nullptr || Idle == nullptr
		|| AnimBlueprint->ParentClass != UTwoHandRigAnimInstanceBase::StaticClass()
		|| Rig->GeneratedClass == nullptr)
	{
		return TEXT("FAIL TWO_HAND_ANIM_AUTHOR_INPUT");
	}
	UEdGraph* Graph = FindAnimGraph(AnimBlueprint);
	TArray<UAnimGraphNode_Root*> Roots;
	if (Graph) Graph->GetNodesOfClass(Roots);
	if (Graph == nullptr || Roots.Num() != 1)
	{
		return FString::Printf(TEXT("FAIL TWO_HAND_ANIM_AUTHOR_ROOTS count=%d"), Roots.Num());
	}
	for (UEdGraphNode* Existing : TArray<UEdGraphNode*>(Graph->Nodes))
	{
		if (Existing && Existing != Roots[0]) Graph->RemoveNode(Existing);
	}
	for (UEdGraphPin* Pin : Roots[0]->Pins)
	{
		if (Pin) Pin->BreakAllPinLinks();
	}

	UAnimGraphNode_SequencePlayer* Base =
		AddAnimNode<UAnimGraphNode_SequencePlayer>(Graph, -650, 0);
	if (Base == nullptr || !Base->Node.SetSequence(Idle)
		|| !Base->Node.SetLoopAnimation(true))
	{
		return TEXT("FAIL TWO_HAND_ANIM_AUTHOR_BASE_SEQUENCE");
	}
	UEdGraphNode* Final = Base;
	if (bComplete)
	{
		UAnimGraphNode_ControlRig* RigNode = NewObject<UAnimGraphNode_ControlRig>(Graph);
		if (RigNode == nullptr)
		{
			return TEXT("FAIL TWO_HAND_ANIM_AUTHOR_CONTROL_RIG_NODE");
		}
		UClass* GeneratedRigClass = Rig->GeneratedClass;
		if (GeneratedRigClass == nullptr || !GeneratedRigClass->IsChildOf(UControlRig::StaticClass()))
		{
			return TEXT("FAIL TWO_HAND_ANIM_AUTHOR_CONTROL_RIG_CLASS");
		}
		RigNode->Node.SetControlRigClass(TSubclassOf<UControlRig>(GeneratedRigClass));
		Graph->AddNode(RigNode, false, false);
		RigNode->CreateNewGuid();
		RigNode->PostPlacedNewNode();
		RigNode->AllocateDefaultPins();
		RigNode->ReconstructNode();
		RigNode->NodePosX = 0;
		RigNode->NodePosY = 0;
		// UE 5.8 exposes the compiler-owned custom-property mapping as a public
		// API. This maps the native AnimInstance fields directly to the two
		// public Control Rig variables without reaching into protected optional
		// pin state or creating submission-visible relay variables.
		RigNode->AddSourceTargetProperties(
			TEXT("LeftHandTarget"), TEXT("LeftHandTarget"));
		RigNode->AddSourceTargetProperties(
			TEXT("RightHandTarget"), TEXT("RightHandTarget"));
		const UEdGraphSchema* Schema = Graph->GetSchema();
		if (Schema == nullptr
			|| !Schema->TryCreateConnection(PosePin(Base, EGPD_Output),
				PosePin(RigNode, EGPD_Input)))
		{
			return TEXT("FAIL TWO_HAND_ANIM_AUTHOR_CONTROL_RIG_CONNECTIONS");
		}
		Final = RigNode;
	}
	const UEdGraphSchema* Schema = Graph->GetSchema();
	if (Schema == nullptr || !Schema->TryCreateConnection(
		PosePin(Final, EGPD_Output), PosePin(Roots[0], EGPD_Input)))
	{
		return TEXT("FAIL TWO_HAND_ANIM_AUTHOR_RESULT_CONNECTION");
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(AnimBlueprint);
	FKismetEditorUtilities::CompileBlueprint(AnimBlueprint);
	if (AnimBlueprint->Status != BS_UpToDate || !SaveAsset(AnimBlueprint))
	{
		return FString::Printf(TEXT("FAIL TWO_HAND_ANIM_AUTHOR_COMPILE_SAVE status=%d"),
			static_cast<int32>(AnimBlueprint->Status));
	}
	return FString::Printf(TEXT("PASS TWO_HAND_ANIM_AUTHORED complete=%d asset=%s"),
		bComplete ? 1 : 0, *AnimBlueprint->GetPathName());
}

FString UTwoHandRigAssetAuthoring::ConfigureScenario(
	ATwoHandPhysicsHandle* Handle, ATwoHandRigCharacter* Subject,
	UAnimBlueprint* AnimBlueprint)
{
	USkeletalMesh* Manny = LoadObject<USkeletalMesh>(nullptr, MannyMeshPath);
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, CubePath);
	if (Handle == nullptr || Subject == nullptr || AnimBlueprint == nullptr
		|| AnimBlueprint->GeneratedClass == nullptr || Manny == nullptr || Cube == nullptr
		|| Subject->GetMesh() == nullptr)
	{
		return TEXT("FAIL TWO_HAND_SCENARIO_CONFIG_INPUT");
	}
	Handle->Modify();
	Handle->GetAnchorBody()->Modify();
	Handle->GetHandleBody()->Modify();
	Handle->GetAnchorBody()->SetStaticMesh(Cube);
	Handle->GetAnchorBody()->SetRelativeScale3D(FVector(0.35, 0.35, 0.35));
	Handle->GetHandleBody()->SetStaticMesh(Cube);
	Handle->GetHandleBody()->SetRelativeLocation(FVector(45.0, 0.0, 135.0));
	Handle->GetHandleBody()->SetRelativeScale3D(FVector(0.18, 1.20, 0.18));
	Subject->Modify();
	USkeletalMeshComponent* Mesh = Subject->GetMesh();
	Mesh->Modify();
	Mesh->SetSkeletalMeshAsset(Manny);
	Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	Mesh->SetAnimInstanceClass(AnimBlueprint->GeneratedClass);
	Mesh->SetRelativeLocationAndRotation(
		FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	Mesh->VisibilityBasedAnimTickOption =
		EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Mesh->bEnableUpdateRateOptimizations = false;
	Subject->TrackedHandle = Handle;
	return Subject->TrackedHandle == Handle
		&& Mesh->GetAnimClass() == AnimBlueprint->GeneratedClass
		&& Handle->GetHandleBody()->GetStaticMesh() == Cube
		? TEXT("PASS TWO_HAND_SCENARIO_CONFIGURED mesh=Manny handle=simulated constraint=real")
		: TEXT("FAIL TWO_HAND_SCENARIO_CONFIG_READBACK");
}

FString UTwoHandRigAssetAuthoring::InspectAuthoredWorld(
	UObject* WorldContextObject, const bool bAdmission)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL TWO_HAND_MAP_WORLD_NULL");
	}
	int32 Handles = 0;
	int32 Subjects = 0;
	int32 AdmissionFixtures = 0;
	int32 FinalFixtures = 0;
	int32 QuartzFixtures = 0;
	int32 VioletFixtures = 0;
	int32 PlayerStarts = 0;
	TSet<FName> ScenarioIds;
	TSet<FString> FactSignatures;
	TSet<FName> FixtureScenarioTags;
	TSet<FString> ImpulseSignatures;
	TArray<ATwoHandPhysicsHandle*> HandleActors;
	TArray<ATwoHandRigCharacter*> SubjectActors;
	TArray<ATwoHandPhysicsFunctionalTest*> FixtureActors;
	bool bReferences = true;
	bool bFixtureLabelsExact = true;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (ATwoHandPhysicsHandle* Handle = Cast<ATwoHandPhysicsHandle>(Actor))
		{
			++Handles;
			HandleActors.Add(Handle);
			ScenarioIds.Add(Handle->ScenarioId);
			FactSignatures.Add(FString::Printf(TEXT("%s:%s:%s"),
				*Handle->ScenarioId.ToString(),
				*Handle->LeftGripLocal.GetLocation().ToCompactString(),
				*Handle->RightGripLocal.GetLocation().ToCompactString()));
			bReferences &= Handle->GetHandleBody() && Handle->GetAnchorBody()
				&& Handle->GetPhysicsConstraint()
				&& Handle->GetHandleBody()->GetStaticMesh() != nullptr;
		}
		if (ATwoHandRigCharacter* Subject = Cast<ATwoHandRigCharacter>(Actor))
		{
			++Subjects;
			SubjectActors.Add(Subject);
			bReferences &= Subject->TrackedHandle != nullptr
				&& Subject->GetMesh() && Subject->GetMesh()->GetAnimClass() != nullptr
				&& Subject->GetMesh()->GetSkeletalMeshAsset() != nullptr;
		}
		if (ATwoHandPhysicsFunctionalTest* Fixture =
			Cast<ATwoHandPhysicsFunctionalTest>(Actor))
		{
			FixtureActors.Add(Fixture);
			FixtureScenarioTags.Add(Fixture->ScenarioTag);
			ImpulseSignatures.Add(FString::Printf(TEXT("%s:%s:%s"),
				*Fixture->ScenarioTag.ToString(),
				*Fixture->FirstImpulse.ToCompactString(),
				*Fixture->SecondImpulse.ToCompactString()));
			bReferences &= !Fixture->ScenarioTag.IsNone()
				&& !Fixture->FirstImpulse.IsNearlyZero()
				&& !Fixture->SecondImpulse.IsNearlyZero()
				&& FVector::DotProduct(Fixture->FirstImpulse.GetSafeNormal(),
					Fixture->SecondImpulse.GetSafeNormal()) <= 0.75;
			if (Cast<ATwoHandPhysicsAdmissionFunctionalTest>(Fixture))
			{
				++AdmissionFixtures;
				bFixtureLabelsExact &= Fixture->GetActorLabel()
					== TEXT("TwoHandPhysicsAdmissionFunctionalTest");
			}
			else
			{
				++FinalFixtures;
				QuartzFixtures += Fixture->IsA<ATwoHandPhysicsQuartzFunctionalTest>() ? 1 : 0;
				VioletFixtures += Fixture->IsA<ATwoHandPhysicsVioletFunctionalTest>() ? 1 : 0;
				if (Fixture->IsA<ATwoHandPhysicsQuartzFunctionalTest>())
				{
					bFixtureLabelsExact &= Fixture->GetActorLabel()
						== TEXT("TwoHandPhysicsQuartzFunctionalTest");
				}
				else if (Fixture->IsA<ATwoHandPhysicsVioletFunctionalTest>())
				{
					bFixtureLabelsExact &= Fixture->GetActorLabel()
						== TEXT("TwoHandPhysicsVioletFunctionalTest");
				}
				else
				{
					bFixtureLabelsExact = false;
				}
			}
		}
		if (Cast<APlayerStart>(Actor)) ++PlayerStarts;
	}
	const int32 Expected = bAdmission ? 1 : 2;
	for (const ATwoHandPhysicsFunctionalTest* Fixture : FixtureActors)
	{
		ATwoHandPhysicsHandle* MatchingHandle = nullptr;
		int32 MatchingHandles = 0;
		int32 MatchingSubjects = 0;
		for (ATwoHandPhysicsHandle* Candidate : HandleActors)
		{
			if (Candidate && Candidate->ActorHasTag(Fixture->ScenarioTag))
			{
				MatchingHandle = Candidate;
				++MatchingHandles;
			}
		}
		for (ATwoHandRigCharacter* Candidate : SubjectActors)
		{
			if (Candidate && Candidate->ActorHasTag(Fixture->ScenarioTag))
			{
				++MatchingSubjects;
				bReferences &= Candidate->TrackedHandle == MatchingHandle;
			}
		}
		bReferences &= MatchingHandles == 1 && MatchingSubjects == 1;
	}
	const AWorldSettings* Settings = World->GetWorldSettings();
	UClass* StockGameMode = LoadObject<UClass>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C"));
	const bool bPlayable = Settings && StockGameMode
		&& Settings->DefaultGameMode == StockGameMode && PlayerStarts == 1;
	const bool bPass = Handles == Expected && Subjects == Expected
		&& ScenarioIds.Num() == Expected && FactSignatures.Num() == Expected
		&& FixtureScenarioTags.Num() == Expected
		&& ImpulseSignatures.Num() == Expected
		&& AdmissionFixtures == (bAdmission ? 1 : 0)
		&& FinalFixtures == (bAdmission ? 0 : 2)
		&& QuartzFixtures == (bAdmission ? 0 : 1)
		&& VioletFixtures == (bAdmission ? 0 : 1)
		&& bFixtureLabelsExact && bReferences && bPlayable;
	return FString::Printf(
		TEXT("%s TWO_HAND_MAP_READBACK admission=%d handles=%d subjects=%d admission_fixtures=%d final_fixtures=%d quartz=%d violet=%d fixture_labels_exact=%d scenarios=%d fixture_tags=%d varying_facts=%d impulse_facts=%d refs=%d player_start=%d playable=%d authored_contract=1 runtime_observed=0"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bAdmission ? 1 : 0,
		Handles, Subjects, AdmissionFixtures, FinalFixtures,
		QuartzFixtures, VioletFixtures, bFixtureLabelsExact ? 1 : 0,
		ScenarioIds.Num(), FixtureScenarioTags.Num(), FactSignatures.Num(),
		ImpulseSignatures.Num(), bReferences ? 1 : 0,
		PlayerStarts, bPlayable ? 1 : 0);
}
