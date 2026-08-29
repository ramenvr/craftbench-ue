// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimAssetAuthoring.h"

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimFunctionalTest.h"
#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimTypes.h"
#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimVerifierLibrary.h"

#include "AI/NavigationSystemBase.h"
#include "AI/NavigationSystemConfig.h"
#include "Animation/AimOffsetBlendSpace.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/BlendSpace.h"
#include "AnimationGraphSchema.h"
#include "AnimGraphNode_BlendSpacePlayer.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_RotationOffsetBlendSpace.h"
#include "AssetCompilingManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/WorldSettings.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "NavigationData.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

namespace
{
	constexpr TCHAR LocomotionPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run.BS_Idle_Walk_Run");
	constexpr TCHAR AimOffsetPath[] =
		TEXT("/Game/Characters/Mannequins/Anims/Rifle/AIM/AO_Rifle.AO_Rifle");

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
		if (Blueprint)
		{
			Blueprint->GetAllGraphs(Graphs);
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

	UEdGraphPin* PosePin(UEdGraphNode* Node, EEdGraphPinDirection Direction)
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

	template <typename TNode>
	TNode* AddNode(UEdGraph* Graph, const int32 X, const int32 Y)
	{
		TNode* Node = NewObject<TNode>(Graph);
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

	UK2Node_VariableGet* AddVariable(
		UEdGraph* Graph, const FName Name, const int32 X, const int32 Y)
	{
		UK2Node_VariableGet* Node = AddNode<UK2Node_VariableGet>(Graph, X, Y);
		if (Node)
		{
			Node->VariableReference.SetSelfMember(Name);
			Node->ReconstructNode();
		}
		return Node;
	}

	bool ConnectVariable(const UEdGraphSchema* Schema,
		UK2Node_VariableGet* Get, UEdGraphNode* Target, const TCHAR* PinName)
	{
		const FName VariableName = Get
			? Get->VariableReference.GetMemberName() : NAME_None;
		UEdGraphPin* Output = Get ? Get->FindPin(VariableName, EGPD_Output) : nullptr;
		UEdGraphPin* Input = Target ? Target->FindPin(PinName, EGPD_Input) : nullptr;
		return Schema && Output && Input
			&& Schema->TryCreateConnection(Output, Input);
	}
}

FString UGuardVisibleAimAssetAuthoring::BuildAnimGraph(
	UAnimBlueprint* AnimBlueprint, const bool bCompleteAimOverlay)
{
	if (AnimBlueprint == nullptr
		|| AnimBlueprint->ParentClass != UGuardVisibleAimAnimInstance::StaticClass())
	{
		return TEXT("FAIL GUARD_AIM_ANIMBP_INPUT");
	}
	UEdGraph* Graph = FindAnimGraph(AnimBlueprint);
	TArray<UAnimGraphNode_Root*> Roots;
	if (Graph)
	{
		Graph->GetNodesOfClass(Roots);
	}
	if (Graph == nullptr || Roots.Num() != 1)
	{
		return FString::Printf(TEXT("FAIL GUARD_AIM_ROOT count=%d"), Roots.Num());
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
	Roots[0]->NodePosX = 700;
	Roots[0]->NodePosY = 0;
	UBlendSpace* Locomotion = LoadObject<UBlendSpace>(nullptr, LocomotionPath);
	UAimOffsetBlendSpace* AimOffset = LoadObject<UAimOffsetBlendSpace>(
		nullptr, AimOffsetPath);
	if (Locomotion == nullptr || AimOffset == nullptr
		|| Locomotion->GetSkeleton() != AnimBlueprint->TargetSkeleton
		|| AimOffset->GetSkeleton() != AnimBlueprint->TargetSkeleton)
	{
		return TEXT("FAIL GUARD_AIM_STOCK_ASSET_OR_SKELETON");
	}
	UAnimGraphNode_BlendSpacePlayer* Base =
		AddNode<UAnimGraphNode_BlendSpacePlayer>(Graph, -650, 0);
	UK2Node_VariableGet* Speed = AddVariable(Graph, TEXT("GroundSpeed"), -900, 220);
	if (Base == nullptr || Speed == nullptr || !Base->Node.SetBlendSpace(Locomotion))
	{
		return TEXT("FAIL GUARD_AIM_BASE_NODE");
	}
	const UEdGraphSchema* Schema = Graph->GetSchema();
	if (!ConnectVariable(Schema, Speed, Base, TEXT("X")))
	{
		return TEXT("FAIL GUARD_AIM_SPEED_CONNECTION");
	}
	UEdGraphNode* FinalWriter = Base;
	if (bCompleteAimOverlay)
	{
		UAnimGraphNode_RotationOffsetBlendSpace* Aim =
			AddNode<UAnimGraphNode_RotationOffsetBlendSpace>(Graph, 50, 0);
		UK2Node_VariableGet* Yaw = AddVariable(Graph, TEXT("AimYaw"), -250, 230);
		UK2Node_VariableGet* Pitch = AddVariable(Graph, TEXT("AimPitch"), -250, 330);
		UK2Node_VariableGet* Alpha = AddVariable(Graph, TEXT("AimAlpha"), -250, 430);
		if (Aim == nullptr || Yaw == nullptr || Pitch == nullptr || Alpha == nullptr
			|| !Aim->Node.SetBlendSpace(AimOffset))
		{
			return TEXT("FAIL GUARD_AIM_OFFSET_NODE");
		}
		Aim->Node.AlphaInputType = EAnimAlphaInputType::Float;
		Aim->Node.LODThreshold = -1;
		if (!Schema->TryCreateConnection(PosePin(Base, EGPD_Output),
				PosePin(Aim, EGPD_Input))
			|| !ConnectVariable(Schema, Yaw, Aim, TEXT("X"))
			|| !ConnectVariable(Schema, Pitch, Aim, TEXT("Y"))
			|| !ConnectVariable(Schema, Alpha, Aim, TEXT("Alpha")))
		{
			return TEXT("FAIL GUARD_AIM_OFFSET_CONNECTIONS");
		}
		FinalWriter = Aim;
	}
	if (!Schema->TryCreateConnection(PosePin(FinalWriter, EGPD_Output),
		PosePin(Roots[0], EGPD_Input)))
	{
		return TEXT("FAIL GUARD_AIM_FINAL_CONNECTION");
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(AnimBlueprint);
	FKismetEditorUtilities::CompileBlueprint(AnimBlueprint);
	if (AnimBlueprint->Status != BS_UpToDate || !SaveAsset(AnimBlueprint))
	{
		return FString::Printf(TEXT("FAIL GUARD_AIM_COMPILE_SAVE status=%d"),
			static_cast<int32>(AnimBlueprint->Status));
	}
	const FString Readback = UGuardVisibleAimVerifierLibrary::InspectAnimBlueprint(
		AnimBlueprint, bCompleteAimOverlay);
	if (!Readback.Contains(TEXT("\"probe_ok\":true")))
	{
		return TEXT("FAIL GUARD_AIM_SAME_PROCESS_READBACK ") + Readback;
	}
	return FString::Printf(
		TEXT("PASS GUARD_AIM_ANIMGRAPH complete=%d route=%s readback=%s"),
		bCompleteAimOverlay ? 1 : 0,
		bCompleteAimOverlay
			? TEXT("Locomotion>AimOffset(additive)>Output")
			: TEXT("Locomotion>Output"), *Readback);
}

FString UGuardVisibleAimAssetAuthoring::ConfigureGuard(
	AGuardVisibleAimCharacter* Guard, UAnimBlueprint* AnimBlueprint)
{
	if (Guard == nullptr || AnimBlueprint == nullptr
		|| AnimBlueprint->GeneratedClass == nullptr || Guard->GetMesh() == nullptr
		|| !AnimBlueprint->GeneratedClass->IsChildOf(
			UGuardVisibleAimAnimInstance::StaticClass()))
	{
		return TEXT("FAIL GUARD_AIM_GUARD_CONFIG_INPUT");
	}
	Guard->Modify();
	Guard->GetMesh()->Modify();
	Guard->GetMesh()->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	Guard->GetMesh()->SetAnimInstanceClass(AnimBlueprint->GeneratedClass);
	Guard->GetMesh()->VisibilityBasedAnimTickOption =
		EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Guard->GetMesh()->bEnableUpdateRateOptimizations = false;
	return Guard->GetMesh()->GetAnimClass() == AnimBlueprint->GeneratedClass
		? FString::Printf(TEXT("PASS guard=%s anim=%s"),
			*Guard->GetPathName(), *AnimBlueprint->GetPathName())
		: TEXT("FAIL GUARD_AIM_GUARD_CONFIG_READBACK");
}

FString UGuardVisibleAimAssetAuthoring::BuildNavigation(
	UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr || World->WorldType != EWorldType::Editor
		|| !World->IsInitialized())
	{
		return TEXT("FAIL GUARD_AIM_NAV_WORLD");
	}
	TArray<ANavMeshBoundsVolume*> BoundsVolumes;
	for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
	{
		BoundsVolumes.Add(*It);
	}
	if (BoundsVolumes.Num() != 1
		|| !BoundsVolumes[0]->HasActorRegisteredAllComponents()
		|| !BoundsVolumes[0]->GetComponentsBoundingBox(true).IsValid)
	{
		return FString::Printf(TEXT("FAIL GUARD_AIM_NAV_BOUNDS count=%d"),
			BoundsVolumes.Num());
	}
	AWorldSettings* Settings = World->GetWorldSettings();
	UNavigationSystemConfig* Config = Settings
		? Settings->GetNavigationSystemConfig() : nullptr;
	UClass* NavigationClass = Config
		? Config->NavigationSystemClass.ResolveClass() : nullptr;
	if (Settings == nullptr || Config == nullptr
		|| Settings->GetNavigationSystemConfigOverride() != nullptr
		|| Config->GetOuter() != Settings || Config->HasAnyFlags(RF_Transient)
		|| !Settings->IsNavigationSystemEnabled()
		|| NavigationClass != UNavigationSystemV1::StaticClass())
	{
		return TEXT("FAIL GUARD_AIM_NAV_CONFIG");
	}
	Settings->SetNavigationSystemConfigOverride(Config);
	FNavigationSystem::AddNavigationSystemToWorld(
		*World, FNavigationSystemRunMode::EditorMode, Config, true, true);
	UNavigationSystemV1* Navigation =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	if (Navigation == nullptr)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return TEXT("FAIL GUARD_AIM_NAV_CREATE");
	}
	constexpr uint8 AsyncLoadLock =
		static_cast<uint8>(ENavigationBuildLock::AsyncLoadLock);
	constexpr uint8 OtherLocks = static_cast<uint8>(
		ENavigationBuildLock::NoUpdateInEditor
		| ENavigationBuildLock::NoUpdateInPIE
		| ENavigationBuildLock::InitialLock
		| ENavigationBuildLock::Custom);
	FAssetCompilingManager::Get().FinishAllCompilation();
	const int32 PendingCompiles =
		FAssetCompilingManager::Get().GetNumRemainingAssets();
	if (!Navigation->IsNavigationBuildingLocked(AsyncLoadLock)
		|| Navigation->IsNavigationBuildingLocked(OtherLocks)
		|| PendingCompiles != 0)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return FString::Printf(
			TEXT("FAIL GUARD_AIM_NAV_LOCK async=%d other=%d compiles=%d"),
			Navigation->IsNavigationBuildingLocked(AsyncLoadLock) ? 1 : 0,
			Navigation->IsNavigationBuildingLocked(OtherLocks) ? 1 : 0,
			PendingCompiles);
	}
	Navigation->RemoveNavigationBuildLock(
		AsyncLoadLock, UNavigationSystemV1::ELockRemovalRebuildAction::NoRebuild);
	Navigation->OnNavigationBoundsUpdated(BoundsVolumes[0]);
	Navigation->Build();
	TArray<ARecastNavMesh*> Recasts;
	for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
	{
		Recasts.Add(*It);
	}
	ARecastNavMesh* Recast = Recasts.Num() == 1 ? Recasts[0] : nullptr;
	const bool bBuilt = Recast
		&& Navigation->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate) == Recast
		&& Recast->GetNumActiveTiles() > 0
		&& !Navigation->IsNavigationBuildInProgress()
		&& Navigation->GetNumRemainingBuildTasks() == 0;
	if (!bBuilt)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return FString::Printf(
			TEXT("FAIL recast=%d default=%d active_tiles=%d building=%d tasks=%d"),
			Recasts.Num(), Recast && Navigation->GetDefaultNavDataInstance(
				FNavigationSystem::DontCreate) == Recast ? 1 : 0,
			Recast ? Recast->GetNumActiveTiles() : 0,
			Navigation->IsNavigationBuildInProgress() ? 1 : 0,
			Navigation->GetNumRemainingBuildTasks());
	}
	FEnumProperty* RuntimeGenerationProperty = FindFProperty<FEnumProperty>(
		ANavigationData::StaticClass(), TEXT("RuntimeGeneration"));
	FNumericProperty* UnderlyingProperty = RuntimeGenerationProperty
		? RuntimeGenerationProperty->GetUnderlyingProperty() : nullptr;
	void* RuntimeGenerationValue = RuntimeGenerationProperty
		? RuntimeGenerationProperty->ContainerPtrToValuePtr<void>(Recast)
		: nullptr;
	if (RuntimeGenerationProperty == nullptr || UnderlyingProperty == nullptr
		|| RuntimeGenerationValue == nullptr)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return TEXT("FAIL GUARD_AIM_NAV_RUNTIME_PROPERTY");
	}
	Recast->Modify();
	UnderlyingProperty->SetIntPropertyValue(
		RuntimeGenerationValue,
		static_cast<int64>(ERuntimeGenerationType::Dynamic));
	Recast->MarkPackageDirty();
	const bool bRuntimeDynamic =
		Recast->GetRuntimeGenerationMode() == ERuntimeGenerationType::Dynamic
		&& Recast->SupportsRuntimeGeneration();
	Settings->SetNavigationSystemConfigOverride(nullptr);
	return FString::Printf(
		TEXT("%s recast=%d default=1 runtime_dynamic=%d runtime_supported=%d active_tiles=%d building=%d tasks=%d"),
		bRuntimeDynamic ? TEXT("PASS") : TEXT("FAIL"), Recasts.Num(),
		Recast->GetRuntimeGenerationMode() == ERuntimeGenerationType::Dynamic
			? 1 : 0,
		Recast->SupportsRuntimeGeneration() ? 1 : 0,
		Recast->GetNumActiveTiles(),
		Navigation->IsNavigationBuildInProgress() ? 1 : 0,
		Navigation->GetNumRemainingBuildTasks());
}

FString UGuardVisibleAimAssetAuthoring::InspectWorld(
	UObject* WorldContextObject, const bool bAdmission)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL GUARD_AIM_WORLD_NULL");
	}
	const int32 ExpectedGroups = bAdmission ? 1 : 2;
	int32 Scenarios = 0;
	int32 Fixtures = 0;
	int32 Guards = 0;
	int32 Targets = 0;
	int32 Occluders = 0;
	int32 Goals = 0;
	int32 Bounds = 0;
	int32 Recasts = 0;
	ARecastNavMesh* ExactRecast = nullptr;
	TSet<FName> ScenarioIds;
	TSet<FString> FactSignatures;
	TArray<AGuardVisibleAimScenario*> ScenarioActors;
	bool bRefs = true;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (AGuardVisibleAimScenario* Value = Cast<AGuardVisibleAimScenario>(Actor))
		{
			++Scenarios;
			ScenarioActors.Add(Value);
			ScenarioIds.Add(Value->ScenarioId);
			FactSignatures.Add(FString::Printf(TEXT("%.0f:%.0f:%s:%s"),
				Value->ExpectedYawSign, Value->ExpectedPitchSign,
				*Value->SwitchOpenLocation.ToCompactString(),
				*Value->SwitchBlockedLocation.ToCompactString()));
			TSet<const UObject*> Unique;
			Unique.Add(Value->MainGuard.Get());
			Unique.Add(Value->ControlGuard.Get());
			Unique.Add(Value->VisibleTarget.Get());
			Unique.Add(Value->OccludedDecoy.Get());
			Unique.Add(Value->DecoyOccluder.Get());
			Unique.Add(Value->SwitchOccluder.Get());
			Unique.Add(Value->MainGoal.Get());
			Unique.Add(Value->ControlGoal.Get());
			bRefs = bRefs && !Value->ScenarioId.IsNone()
				&& Value->ExpectedAnimClass != nullptr && Unique.Num() == 8
				&& Value->MainGuard && Value->ControlGuard
				&& Value->MainGuard->GetMesh()->GetAnimClass()
					== Value->ExpectedAnimClass.Get()
				&& Value->ControlGuard->GetMesh()->GetAnimClass()
					== Value->ExpectedAnimClass.Get()
				&& FVector::Dist(Value->SwitchOpenLocation,
					Value->SwitchBlockedLocation) >= 600.0f
				&& FMath::Abs(Value->ExpectedYawSign) == 1.0f
				&& FMath::Abs(Value->ExpectedPitchSign) == 1.0f;
		}
		Fixtures += Cast<AGuardVisibleAimFunctionalTestBase>(Actor) ? 1 : 0;
		Guards += Cast<AGuardVisibleAimCharacter>(Actor) ? 1 : 0;
		Targets += Cast<AGuardVisibleAimTarget>(Actor) ? 1 : 0;
		Occluders += Cast<AGuardVisibleAimOccluder>(Actor) ? 1 : 0;
		Goals += Cast<AGuardVisibleAimGoal>(Actor) ? 1 : 0;
		Bounds += Cast<ANavMeshBoundsVolume>(Actor) ? 1 : 0;
		if (ARecastNavMesh* Recast = Cast<ARecastNavMesh>(Actor))
		{
			++Recasts;
			ExactRecast = Recast;
		}
	}
	UClass* ExpectedGameMode = LoadObject<UClass>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C"));
	const AWorldSettings* WorldSettings = World->GetWorldSettings();
	const bool bPlayable = WorldSettings && ExpectedGameMode
		&& WorldSettings->DefaultGameMode == ExpectedGameMode;
	UNavigationSystemV1* Navigation =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	int32 ProjectedEndpoints = 0;
	int32 NavigablePairs = 0;
	const FVector ProjectionExtent(160.0, 160.0, 300.0);
	if (Navigation && ExactRecast)
	{
		for (AGuardVisibleAimScenario* Scenario : ScenarioActors)
		{
			for (const TPair<AGuardVisibleAimCharacter*, AGuardVisibleAimGoal*>& Pair : {
				TPair<AGuardVisibleAimCharacter*, AGuardVisibleAimGoal*>(
					Scenario->MainGuard.Get(), Scenario->MainGoal.Get()),
				TPair<AGuardVisibleAimCharacter*, AGuardVisibleAimGoal*>(
					Scenario->ControlGuard.Get(), Scenario->ControlGoal.Get())})
			{
				FNavLocation ProjectedStart;
				FNavLocation ProjectedGoal;
				const bool bStart = Pair.Key
					&& Navigation->ProjectPointToNavigation(
						Pair.Key->GetActorLocation(), ProjectedStart,
						ProjectionExtent, ExactRecast);
				const bool bGoal = Pair.Value
					&& Navigation->ProjectPointToNavigation(
						Pair.Value->GetActorLocation(), ProjectedGoal,
						ProjectionExtent, ExactRecast);
				ProjectedEndpoints += bStart ? 1 : 0;
				ProjectedEndpoints += bGoal ? 1 : 0;
				UNavigationPath* Path = bStart && bGoal
					? UNavigationSystemV1::FindPathToLocationSynchronously(
						World, ProjectedStart.Location, ProjectedGoal.Location,
						Pair.Key)
					: nullptr;
				NavigablePairs += Path && Path->IsValid() && !Path->IsPartial()
					&& Path->PathPoints.Num() >= 2 && Path->GetPathLength() > 100.0
					? 1 : 0;
			}
		}
	}
	const bool bPass = Scenarios == ExpectedGroups && Fixtures == ExpectedGroups
		&& Guards == ExpectedGroups * 2 && Targets == ExpectedGroups * 2
		&& Occluders == ExpectedGroups * 2 && Goals == ExpectedGroups * 2
		&& ScenarioIds.Num() == ExpectedGroups && bRefs
		&& (ExpectedGroups == 1 || FactSignatures.Num() == ExpectedGroups)
		&& Bounds == 1 && Recasts == 1 && ExactRecast != nullptr
		&& ExactRecast->GetRuntimeGenerationMode()
			== ERuntimeGenerationType::Dynamic
		&& ExactRecast->SupportsRuntimeGeneration()
		&& ExactRecast->GetNumActiveTiles() > 0
		&& ProjectedEndpoints == ExpectedGroups * 4
		&& NavigablePairs == ExpectedGroups * 2 && bPlayable;
	return FString::Printf(
		TEXT("%s admission=%d scenarios=%d fixtures=%d guards=%d targets=%d occluders=%d goals=%d scenario_ids=%d varying_facts=%d refs=%d nav_bounds=%d recast=%d runtime_dynamic=%d runtime_supported=%d active_tiles=%d projected_endpoints=%d navigable_pairs=%d playable=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bAdmission ? 1 : 0,
		Scenarios, Fixtures, Guards, Targets, Occluders, Goals,
		ScenarioIds.Num(), FactSignatures.Num(), bRefs ? 1 : 0, Bounds, Recasts,
		ExactRecast && ExactRecast->GetRuntimeGenerationMode()
			== ERuntimeGenerationType::Dynamic ? 1 : 0,
		ExactRecast && ExactRecast->SupportsRuntimeGeneration() ? 1 : 0,
		ExactRecast ? ExactRecast->GetNumActiveTiles() : 0,
		ProjectedEndpoints, NavigablePairs,
		bPlayable ? 1 : 0);
}
