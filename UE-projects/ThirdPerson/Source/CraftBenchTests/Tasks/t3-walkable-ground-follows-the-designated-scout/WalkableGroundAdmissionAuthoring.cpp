// Copyright CraftBench. All Rights Reserved.

#include "WalkableGroundAdmissionAuthoring.h"

#include "AI/NavigationSystemConfig.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "EdGraph/EdGraph.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SCS_Node.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavigationData.h"
#include "NavigationInvokerComponent.h"
#include "UObject/SavePackage.h"
#include "WalkableGroundAdmissionFunctionalTest.h"
#include "WalkableGroundAdmissionTypes.h"

namespace
{
	FString Fail(const TCHAR* Gate, const FString& Detail)
	{
		const FString Message = FString::Printf(
			TEXT("FAIL %s %s"), Gate, *Detail);
		UE_LOG(LogTemp, Error, TEXT("WALKABLE-GROUND-AUTHORING %s"), *Message);
		return Message;
	}

	bool ClassPathMatches(const FSoftClassPath& Path, const UClass* Expected)
	{
		return Expected != nullptr
			&& Path.ToString() == Expected->GetPathName();
	}

	bool SaveBlueprint(UBlueprint* Blueprint)
	{
		UPackage* Package = Blueprint ? Blueprint->GetOutermost() : nullptr;
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
		return UPackage::SavePackage(Package, Blueprint, *Filename, Args);
	}

	int32 CountGraphNodes(const UBlueprint* Blueprint)
	{
		int32 Count = 0;
		if (Blueprint != nullptr)
		{
			for (const UEdGraph* Graph : Blueprint->UbergraphPages)
			{
				Count += Graph ? Graph->Nodes.Num() : 0;
			}
			for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
			{
				Count += Graph ? Graph->Nodes.Num() : 0;
			}
		}
		return Count;
	}

	void RemoveAllGraphNodes(UBlueprint* Blueprint)
	{
		const auto RemoveFromGraph = [Blueprint](UEdGraph* Graph)
		{
			if (Graph == nullptr)
			{
				return;
			}
			TArray<UEdGraphNode*> Nodes = Graph->Nodes;
			for (UEdGraphNode* Node : Nodes)
			{
				FBlueprintEditorUtils::RemoveNode(
					Blueprint, Node, /*bDontRecompile=*/true);
			}
			Graph->NotifyGraphChanged();
		};
		for (UEdGraph* Graph : Blueprint->UbergraphPages)
		{
			RemoveFromGraph(Graph);
		}
		// A component-bearing Blueprint may own a UserConstructionScript
		// function graph. Leaving that graph present after deleting its required
		// entry node is an invalid Blueprint, even though it has zero executable
		// behavior. Remove the empty function graph itself so the supplied and
		// reference assets retain the strict zero-node answer surface.
		const TArray<UEdGraph*> FunctionGraphs = Blueprint->FunctionGraphs;
		for (UEdGraph* Graph : FunctionGraphs)
		{
			if (Graph != nullptr)
			{
				FBlueprintEditorUtils::RemoveGraph(
					Blueprint, Graph, EGraphRemoveFlags::MarkTransient);
			}
		}
	}
}

FString UWalkableGroundAdmissionAuthoring::ConfigureAdmissionWorld(
	UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr || World->WorldType != EWorldType::Editor)
	{
		return Fail(TEXT("WORLD"), TEXT("expected initialized Editor world"));
	}
	AWorldSettings* WorldSettings = World->GetWorldSettings();
	if (WorldSettings == nullptr
		|| WorldSettings->GetNavigationSystemConfigOverride() != nullptr)
	{
		return Fail(TEXT("WORLD_SETTINGS"),
			TEXT("missing world settings or transient config override present"));
	}
	UNavigationSystemConfig* Config = WorldSettings->GetNavigationSystemConfig();
	if (Config == nullptr || Config->GetOuter() != WorldSettings
		|| Config->HasAnyFlags(RF_Transient))
	{
		return Fail(TEXT("NAV_CONFIG"),
			FString::Printf(TEXT("persistent world-owned config required; actual=%s"),
				*GetPathNameSafe(Config)));
	}

	WorldSettings->Modify();
	Config->Modify();
	Config->NavigationSystemClass = FSoftClassPath(
		UWalkableGroundAdmissionNavigationSystem::StaticClass());
	Config->SupportedAgentsMask = FNavAgentSelector();
	Config->SupportedAgentsMask.MarkInitialized();

	// Admission source maps must not serialize a whole-map Recast answer. The
	// configured navigation system creates its dynamic Recast in the PIE world.
	World->SetNavigationSystem(nullptr);
	int32 RemovedNavData = 0;
	TArray<ANavigationData*> NavigationDataActors;
	for (TActorIterator<ANavigationData> It(World); It; ++It)
	{
		NavigationDataActors.Add(*It);
	}
	for (ANavigationData* NavigationData : NavigationDataActors)
	{
		if (NavigationData != nullptr && NavigationData->Destroy())
		{
			++RemovedNavData;
		}
	}

	WorldSettings->MarkPackageDirty();
	Config->MarkPackageDirty();
	return FString::Printf(TEXT(
		"PASS config=%s navigation_system_class=%s removed_nav_data=%d "
		"serialized_nav_data=0 override=0"),
		*Config->GetClass()->GetPathName(),
		*Config->NavigationSystemClass.ToString(), RemovedNavData);
}

FString UWalkableGroundAdmissionAuthoring::InspectAdmissionWorld(
	UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return Fail(TEXT("WORLD"), TEXT("world is null"));
	}
	const AWorldSettings* WorldSettings = World->GetWorldSettings();
	const UNavigationSystemConfig* Config = WorldSettings
		? WorldSettings->GetNavigationSystemConfig() : nullptr;
	if (WorldSettings == nullptr || Config == nullptr
		|| WorldSettings->GetNavigationSystemConfigOverride() != nullptr
		|| Config->GetOuter() != WorldSettings
		|| Config->HasAnyFlags(RF_Transient)
		|| !ClassPathMatches(Config->NavigationSystemClass,
			UWalkableGroundAdmissionNavigationSystem::StaticClass()))
	{
		return Fail(TEXT("NAV_CONFIG"), FString::Printf(
			TEXT("persistent=%d override=%d class=%s"),
			Config && Config->GetOuter() == WorldSettings
				&& !Config->HasAnyFlags(RF_Transient) ? 1 : 0,
			WorldSettings && WorldSettings->GetNavigationSystemConfigOverride()
				? 1 : 0,
			Config ? *Config->NavigationSystemClass.ToString() : TEXT("None")));
	}

	int32 ScoutCount = 0;
	int32 FixtureCount = 0;
	int32 BoundsCount = 0;
	int32 LoadedNavDataCount = 0;
	int32 DynamicNavDataCount = 0;
	AWalkableGroundAdmissionScout* ExactScout = nullptr;
	FBox Bounds(ForceInit);
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor->GetClass() == AWalkableGroundAdmissionScout::StaticClass())
		{
			++ScoutCount;
			ExactScout = CastChecked<AWalkableGroundAdmissionScout>(Actor);
		}
		if (Actor->GetClass()
			== AWalkableGroundInvokerAdmissionFunctionalTest::StaticClass())
		{
			++FixtureCount;
		}
		if (Actor->GetClass() == ANavMeshBoundsVolume::StaticClass())
		{
			++BoundsCount;
			Bounds = Actor->GetComponentsBoundingBox(true);
		}
		if (ANavigationData* NavigationData = Cast<ANavigationData>(Actor))
		{
			LoadedNavDataCount += NavigationData->HasAnyFlags(RF_WasLoaded) ? 1 : 0;
			DynamicNavDataCount +=
				NavigationData->GetRuntimeGenerationMode()
					== ERuntimeGenerationType::Dynamic ? 1 : 0;
		}
	}
	if (ScoutCount != 1 || FixtureCount != 1 || BoundsCount != 1
		|| ExactScout == nullptr || !Bounds.IsValid)
	{
		return Fail(TEXT("CARDINALITY"), FString::Printf(
			TEXT("scout=%d fixture=%d bounds=%d bounds_valid=%d"),
			ScoutCount, FixtureCount, BoundsCount, Bounds.IsValid ? 1 : 0));
	}
	const bool bBoundsSpanAllZones = Bounds.Min.X < -6200.0
		&& Bounds.Max.X > 6200.0 && Bounds.Min.Y < -1200.0
		&& Bounds.Max.Y > 1200.0;
	UNavigationInvokerComponent* Invoker = ExactScout->GetNavigationInvoker();
	const bool bInvokerExact = Invoker != nullptr
		&& Invoker->GetOwner() == ExactScout
		&& FMath::IsNearlyEqual(Invoker->GetGenerationRadius(), 1600.0f)
		&& FMath::IsNearlyEqual(Invoker->GetRemovalRadius(), 2200.0f);
	if (!bBoundsSpanAllZones || !bInvokerExact || LoadedNavDataCount != 0)
	{
		return Fail(TEXT("MAP_CONTRACT"), FString::Printf(
			TEXT("bounds_span_all=%d invoker_exact=%d loaded_nav_data=%d "
				"dynamic_runtime_nav_data=%d"),
			bBoundsSpanAllZones ? 1 : 0, bInvokerExact ? 1 : 0,
			LoadedNavDataCount, DynamicNavDataCount));
	}
	return FString::Printf(TEXT(
		"PASS scout=1 fixture=1 bounds=1 bounds_span_all=1 "
		"invoker_exact=1 loaded_nav_data=0 dynamic_runtime_nav_data=%d "
		"navigation_system_class=%s"),
		DynamicNavDataCount, *Config->NavigationSystemClass.ToString());
}

FString UWalkableGroundAdmissionAuthoring::InspectProductionWorld(
	UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return Fail(TEXT("PRODUCTION_WORLD"), TEXT("world is null"));
	}
	const AWorldSettings* WorldSettings = World->GetWorldSettings();
	const UNavigationSystemConfig* Config = WorldSettings
		? WorldSettings->GetNavigationSystemConfig() : nullptr;
	UClass* ExpectedScoutClass = LoadObject<UClass>(nullptr,
		TEXT("/Game/Tasks/t3-walkable-ground-follows-the-designated-scout/"
			 "BP_DesignatedScout.BP_DesignatedScout_C"));
	UClass* ExpectedGameMode = LoadObject<UClass>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
			 "BP_ThirdPersonGameMode_C"));
	if (WorldSettings == nullptr || Config == nullptr
		|| WorldSettings->GetNavigationSystemConfigOverride() != nullptr
		|| Config->GetOuter() != WorldSettings
		|| Config->HasAnyFlags(RF_Transient)
		|| !ClassPathMatches(Config->NavigationSystemClass,
			UWalkableGroundAdmissionNavigationSystem::StaticClass())
		|| ExpectedScoutClass == nullptr || ExpectedGameMode == nullptr
		|| WorldSettings->DefaultGameMode != ExpectedGameMode)
	{
		return Fail(TEXT("PRODUCTION_CONFIG"), FString::Printf(
			TEXT("config=%s nav_class=%s scout_class=%s game_mode=%s"),
			*GetPathNameSafe(Config),
			Config ? *Config->NavigationSystemClass.ToString() : TEXT("None"),
			*GetPathNameSafe(ExpectedScoutClass),
			*GetPathNameSafe(WorldSettings
				? WorldSettings->DefaultGameMode.Get() : nullptr)));
	}

	int32 ScoutCount = 0;
	int32 FixtureCount = 0;
	int32 BoundsCount = 0;
	int32 FloorCount = 0;
	int32 PlayerStartCount = 0;
	int32 LoadedNavDataCount = 0;
	ADesignatedScoutCharacter* ExactScout = nullptr;
	FBox Bounds(ForceInit);
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor->GetClass() == ExpectedScoutClass)
		{
			++ScoutCount;
			ExactScout = CastChecked<ADesignatedScoutCharacter>(Actor);
		}
		if (Actor->GetClass() == AWalkableGroundFunctionalTest::StaticClass())
		{
			++FixtureCount;
		}
		if (Actor->GetClass() == ANavMeshBoundsVolume::StaticClass())
		{
			++BoundsCount;
			Bounds = Actor->GetComponentsBoundingBox(true);
		}
		FloorCount += Actor->ActorHasTag(TEXT("WalkableGroundFloor")) ? 1 : 0;
		PlayerStartCount += Actor->IsA<APlayerStart>() ? 1 : 0;
		if (const ANavigationData* NavigationData = Cast<ANavigationData>(Actor))
		{
			LoadedNavDataCount +=
				NavigationData->HasAnyFlags(RF_WasLoaded) ? 1 : 0;
		}
	}
	TArray<UNavigationInvokerComponent*> Invokers;
	if (ExactScout != nullptr)
	{
		ExactScout->GetComponents<UNavigationInvokerComponent>(Invokers);
	}
	USkeletalMeshComponent* Mesh = ExactScout ? ExactScout->GetMesh() : nullptr;
	const bool bBoundsSpanAllZones = Bounds.IsValid && Bounds.Min.X < -6200.0
		&& Bounds.Max.X > 6200.0 && Bounds.Min.Y < -1200.0
		&& Bounds.Max.Y > 1200.0;
	const bool bBaselineEmpty = Invokers.IsEmpty();
	const bool bVisibleMesh = Mesh != nullptr
		&& Mesh->GetSkeletalMeshAsset() != nullptr
		&& Mesh->GetAnimClass() != nullptr && Mesh->IsVisible()
		&& !Mesh->bHiddenInGame;
	if (ScoutCount != 1 || FixtureCount != 1 || BoundsCount != 1
		|| FloorCount != 1 || PlayerStartCount != 1
		|| LoadedNavDataCount != 0 || !bBoundsSpanAllZones
		|| !bBaselineEmpty || !bVisibleMesh
		|| !ExactScout->ActorHasTag(TEXT("WalkableGroundDesignatedScout")))
	{
		return Fail(TEXT("PRODUCTION_MAP_CONTRACT"), FString::Printf(
			TEXT("scout=%d fixture=%d bounds=%d floor=%d player_start=%d "
				 "loaded_nav=%d span=%d baseline_empty=%d invoker_count=%d "
				 "visible=%d tag=%d"),
			ScoutCount, FixtureCount, BoundsCount, FloorCount,
			PlayerStartCount, LoadedNavDataCount,
			bBoundsSpanAllZones ? 1 : 0, bBaselineEmpty ? 1 : 0,
			Invokers.Num(),
			bVisibleMesh ? 1 : 0,
			ExactScout && ExactScout->ActorHasTag(
				TEXT("WalkableGroundDesignatedScout")) ? 1 : 0));
	}
	return FString::Printf(TEXT(
		"PASS scout=1 fixture=1 bounds=1 floor=1 player_start=1 "
		"loaded_nav_data=0 bounds_span_all=1 baseline_empty=1 "
		"invoker_count=0 visible=1 "
		"subject_tag=1 game_mode_exact=1 navigation_system_class=%s"),
		*Config->NavigationSystemClass.ToString());
}

FString UWalkableGroundAdmissionAuthoring::ConfigureDesignatedScoutBlueprint(
	UBlueprint* Blueprint, bool bWithInvoker,
	float GenerationRadius, float RemovalRadius)
{
	if (Blueprint == nullptr || Blueprint->SimpleConstructionScript == nullptr
		|| !FMath::IsFinite(GenerationRadius)
		|| !FMath::IsFinite(RemovalRadius)
		|| GenerationRadius < 600.0f || RemovalRadius <= GenerationRadius
		|| RemovalRadius > 5000.0f)
	{
		return Fail(TEXT("BLUEPRINT_INPUT"),
			TEXT("invalid asset/SCS or radii"));
	}
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->ParentClass != ADesignatedScoutCharacter::StaticClass()
		|| Blueprint->GeneratedClass == nullptr
		|| Blueprint->GeneratedClass->GetSuperClass()
			!= ADesignatedScoutCharacter::StaticClass())
	{
		return Fail(TEXT("BLUEPRINT_PARENT"),
			*GetPathNameSafe(Blueprint->ParentClass));
	}

	ADesignatedScoutCharacter* CDO = Blueprint->GeneratedClass
		->GetDefaultObject<ADesignatedScoutCharacter>();
	USkeletalMeshComponent* Mesh = CDO ? CDO->GetMesh() : nullptr;
	USkeletalMesh* Manny = LoadObject<USkeletalMesh>(nullptr,
		TEXT("/Game/Characters/Mannequins/Meshes/"
			 "SKM_Manny_Simple.SKM_Manny_Simple"));
	UClass* MannyAnim = LoadObject<UClass>(nullptr,
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/"
			 "ABP_Unarmed.ABP_Unarmed_C"));
	if (CDO == nullptr || Mesh == nullptr || Manny == nullptr || MannyAnim == nullptr)
	{
		return Fail(TEXT("BLUEPRINT_STOCK"), FString::Printf(
			TEXT("cdo=%s mesh=%s manny=%s anim=%s"),
			*GetPathNameSafe(CDO), *GetPathNameSafe(Mesh),
			*GetPathNameSafe(Manny), *GetPathNameSafe(MannyAnim)));
	}
	CDO->Modify();
	Mesh->Modify();
	CDO->Tags.AddUnique(TEXT("WalkableGroundDesignatedScout"));
	Mesh->SetSkeletalMeshAsset(Manny);
	Mesh->SetAnimInstanceClass(MannyAnim);
	Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	Mesh->SetRelativeLocation(FVector(0.0, 0.0, -90.0));
	Mesh->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	Mesh->SetVisibility(true);
	Mesh->SetHiddenInGame(false);
	RemoveAllGraphNodes(Blueprint);

	USimpleConstructionScript* SCS = Blueprint->SimpleConstructionScript;
	TArray<USCS_Node*> ExistingInvokerNodes;
	for (USCS_Node* Node : SCS->GetAllNodes())
	{
		if (Node != nullptr
			&& Node->ComponentClass == UNavigationInvokerComponent::StaticClass())
		{
			ExistingInvokerNodes.Add(Node);
		}
	}
	if (ExistingInvokerNodes.Num() > 1)
	{
		return Fail(TEXT("BLUEPRINT_INVOKER_COUNT"),
			FString::FromInt(ExistingInvokerNodes.Num()));
	}
	USCS_Node* InvokerNode = ExistingInvokerNodes.IsEmpty()
		? nullptr : ExistingInvokerNodes[0];
	if (!bWithInvoker && InvokerNode != nullptr)
	{
		SCS->RemoveNode(InvokerNode);
		InvokerNode = nullptr;
	}
	if (bWithInvoker && InvokerNode == nullptr)
	{
		InvokerNode = SCS->CreateNode(
			UNavigationInvokerComponent::StaticClass(), TEXT("NavigationInvoker"));
		if (InvokerNode == nullptr)
		{
			return Fail(TEXT("BLUEPRINT_INVOKER_CREATE"), Blueprint->GetPathName());
		}
		SCS->AddNode(InvokerNode);
	}
	if (bWithInvoker)
	{
		UNavigationInvokerComponent* Template =
			Cast<UNavigationInvokerComponent>(InvokerNode->ComponentTemplate);
		if (Template == nullptr)
		{
			return Fail(TEXT("BLUEPRINT_INVOKER_TEMPLATE"),
				Blueprint->GetPathName());
		}
		Template->Modify();
		Template->SetGenerationRadii(GenerationRadius, RemovalRadius);
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate || CountGraphNodes(Blueprint) != 0
		|| !SaveBlueprint(Blueprint))
	{
		return Fail(TEXT("BLUEPRINT_SAVE"), FString::Printf(
			TEXT("status=%d graph_nodes=%d"),
			static_cast<int32>(Blueprint->Status), CountGraphNodes(Blueprint)));
	}
	return bWithInvoker
		? InspectDesignatedScoutBlueprint(Blueprint)
		: InspectDesignatedScoutBlueprintShell(Blueprint);
}

FString UWalkableGroundAdmissionAuthoring::InspectDesignatedScoutBlueprint(
	UBlueprint* Blueprint)
{
	if (Blueprint == nullptr)
	{
		return Fail(TEXT("BLUEPRINT"), TEXT("asset is null"));
	}
	UBlueprintGeneratedClass* GeneratedClass =
		Cast<UBlueprintGeneratedClass>(Blueprint->GeneratedClass);
	const bool bClassExact = Blueprint->ParentClass
		== ADesignatedScoutCharacter::StaticClass()
		&& GeneratedClass != nullptr
		&& GeneratedClass->GetSuperClass()
			== ADesignatedScoutCharacter::StaticClass();
	const bool bCompileExact = Blueprint->Status == BS_UpToDate;
	if (!bClassExact || !bCompileExact || Blueprint->SimpleConstructionScript == nullptr)
	{
		return Fail(TEXT("BLUEPRINT_CLASS"), FString::Printf(
			TEXT("parent=%s generated_super=%s status=%d scs=%d"),
			*GetPathNameSafe(Blueprint->ParentClass),
			*GetPathNameSafe(GeneratedClass ? GeneratedClass->GetSuperClass() : nullptr),
			static_cast<int32>(Blueprint->Status),
			Blueprint->SimpleConstructionScript ? 1 : 0));
	}

	int32 InvokerNodeCount = 0;
	UNavigationInvokerComponent* InvokerTemplate = nullptr;
	for (USCS_Node* Node : Blueprint->SimpleConstructionScript->GetAllNodes())
	{
		if (Node != nullptr
			&& Node->ComponentClass == UNavigationInvokerComponent::StaticClass())
		{
			++InvokerNodeCount;
			InvokerTemplate = Cast<UNavigationInvokerComponent>(
				Node->GetActualComponentTemplate(GeneratedClass));
		}
	}
	int32 GraphNodeCount = 0;
	for (const UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		GraphNodeCount += Graph ? Graph->Nodes.Num() : 0;
	}
	for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		GraphNodeCount += Graph ? Graph->Nodes.Num() : 0;
	}
	const float GenerationRadius = InvokerTemplate
		? InvokerTemplate->GetGenerationRadius() : 0.0f;
	const float RemovalRadius = InvokerTemplate
		? InvokerTemplate->GetRemovalRadius() : 0.0f;
	const bool bRadiiValid = FMath::IsFinite(GenerationRadius)
		&& FMath::IsFinite(RemovalRadius) && GenerationRadius >= 600.0f
		&& RemovalRadius > GenerationRadius && RemovalRadius <= 5000.0f;
	const bool bOwnerExact = InvokerNodeCount == 1 && InvokerTemplate != nullptr
		&& InvokerTemplate->GetOuter() != nullptr;
	if (!bOwnerExact || !bRadiiValid || GraphNodeCount != 0)
	{
		return Fail(TEXT("BLUEPRINT_STRUCTURE"), FString::Printf(
			TEXT("owner_exact=%d component_count=%d radii_valid=%d generation=%.1f "
				"removal=%.1f graph_nodes=%d"),
			bOwnerExact ? 1 : 0, InvokerNodeCount, bRadiiValid ? 1 : 0,
			GenerationRadius, RemovalRadius, GraphNodeCount));
	}
	return FString::Printf(TEXT(
		"PASS class_exact=1 compile_exact=1 owner_exact=1 component_count=1 "
		"radii_valid=1 generation=%.1f removal=%.1f graph_nodes=0"),
		GenerationRadius, RemovalRadius);
}

FString UWalkableGroundAdmissionAuthoring::
	InspectDesignatedScoutBlueprintShell(UBlueprint* Blueprint)
{
	if (Blueprint == nullptr || Blueprint->SimpleConstructionScript == nullptr)
	{
		return Fail(TEXT("BLUEPRINT_SHELL"), TEXT("asset or SCS is null"));
	}
	UBlueprintGeneratedClass* GeneratedClass =
		Cast<UBlueprintGeneratedClass>(Blueprint->GeneratedClass);
	const bool bClassExact = Blueprint->ParentClass
		== ADesignatedScoutCharacter::StaticClass()
		&& GeneratedClass != nullptr
		&& GeneratedClass->GetSuperClass()
			== ADesignatedScoutCharacter::StaticClass();
	int32 InvokerCount = 0;
	for (USCS_Node* Node : Blueprint->SimpleConstructionScript->GetAllNodes())
	{
		InvokerCount += Node != nullptr
			&& Node->ComponentClass == UNavigationInvokerComponent::StaticClass()
			? 1 : 0;
	}
	ADesignatedScoutCharacter* CDO = GeneratedClass
		? GeneratedClass->GetDefaultObject<ADesignatedScoutCharacter>() : nullptr;
	USkeletalMeshComponent* Mesh = CDO ? CDO->GetMesh() : nullptr;
	const bool bVisible = Mesh != nullptr
		&& Mesh->GetSkeletalMeshAsset() != nullptr
		&& Mesh->GetAnimClass() != nullptr && Mesh->IsVisible()
		&& !Mesh->bHiddenInGame
		&& CDO->ActorHasTag(TEXT("WalkableGroundDesignatedScout"));
	const int32 GraphNodes = CountGraphNodes(Blueprint);
	const bool bBaselineEmpty = InvokerCount == 0 && GraphNodes == 0;
	const bool bPass = bClassExact && Blueprint->Status == BS_UpToDate
		&& bBaselineEmpty && bVisible;
	return FString::Printf(TEXT(
		"%s baseline_empty=%d class_exact=%d compile_exact=%d component_count=%d "
		"graph_nodes=%d visible=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bBaselineEmpty ? 1 : 0,
		bClassExact ? 1 : 0,
		Blueprint->Status == BS_UpToDate ? 1 : 0,
		InvokerCount, GraphNodes, bVisible ? 1 : 0);
}
