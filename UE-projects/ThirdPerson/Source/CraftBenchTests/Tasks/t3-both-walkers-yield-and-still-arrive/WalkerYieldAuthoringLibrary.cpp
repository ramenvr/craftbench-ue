// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-walkers-yield-and-still-arrive/WalkerYieldAuthoringLibrary.h"

#include "Tasks/t3-both-walkers-yield-and-still-arrive/BothWalkersYieldFunctionalTest.h"
#include "Tasks/t3-both-walkers-yield-and-still-arrive/WalkerYieldCharacter.h"

#include "AI/NavigationSystemBase.h"
#include "AI/NavigationSystemConfig.h"
#include "AssetCompilingManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "DetourCrowdAIController.h"
#include "EdGraph/EdGraph.h"
#include "Engine/Blueprint.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "NavigationSystem.h"
#include "NavigationData.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

namespace
{
	constexpr TCHAR StockCharacterClassPath[] =
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C");

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

	bool NearlyEqual(const float Left, const float Right)
	{
		return FMath::IsNearlyEqual(Left, Right, 0.01f);
	}

	FString ClassPath(const UClass* Class)
	{
		return Class ? Class->GetPathName() : TEXT("None");
	}

	double LateralSeparation(
		const FVector& Point, const FVector& LineStart,
		const FVector& LineDirection)
	{
		const FVector Delta = Point - LineStart;
		return FMath::Abs(
			static_cast<double>(Delta.X) * LineDirection.Y
			- static_cast<double>(Delta.Y) * LineDirection.X);
	}
}

FString UWalkerYieldAuthoringLibrary::ConfigureWalkerBlueprint(
	UBlueprint* Blueprint, const bool bEnableAvoidance,
	const float AvoidanceWeight, const float ConsiderationRadius)
{
	if (Blueprint == nullptr || AvoidanceWeight < 0.0f || AvoidanceWeight > 1.0f
		|| ConsiderationRadius < 100.0f)
	{
		return TEXT("FAIL WALKER_CONFIG_INPUT");
	}
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate || Blueprint->GeneratedClass == nullptr
		|| Blueprint->GeneratedClass->GetSuperClass()
			!= AWalkerYieldCharacter::StaticClass())
	{
		return FString::Printf(
			TEXT("FAIL WALKER_CONFIG_PARENT status=%d generated=%s parent=%s"),
			static_cast<int32>(Blueprint->Status),
			*GetPathNameSafe(Blueprint->GeneratedClass),
			*ClassPath(Blueprint->GeneratedClass
				? Blueprint->GeneratedClass->GetSuperClass() : nullptr));
	}

	AWalkerYieldCharacter* CDO =
		Blueprint->GeneratedClass->GetDefaultObject<AWalkerYieldCharacter>();
	UCharacterMovementComponent* Movement = CDO
		? CDO->GetCharacterMovement() : nullptr;
	USkeletalMeshComponent* Mesh = CDO ? CDO->GetMesh() : nullptr;
	UCapsuleComponent* Capsule = CDO ? CDO->GetCapsuleComponent() : nullptr;
	UClass* StockClass = LoadObject<UClass>(nullptr, StockCharacterClassPath);
	ACharacter* StockCDO = StockClass
		? StockClass->GetDefaultObject<ACharacter>() : nullptr;
	USkeletalMeshComponent* StockMesh = StockCDO
		? StockCDO->GetMesh() : nullptr;
	if (CDO == nullptr || Movement == nullptr || Mesh == nullptr
		|| Capsule == nullptr || StockMesh == nullptr
		|| StockMesh->GetSkeletalMeshAsset() == nullptr
		|| StockMesh->GetAnimClass() == nullptr)
	{
		return FString::Printf(
			TEXT("FAIL WALKER_CONFIG_CDO cdo=%s movement=%s mesh=%s capsule=%s stock=%s stock_mesh=%s"),
			*GetNameSafe(CDO), *GetNameSafe(Movement), *GetNameSafe(Mesh),
			*GetNameSafe(Capsule), *GetNameSafe(StockCDO), *GetNameSafe(StockMesh));
	}

	CDO->Modify();
	Movement->Modify();
	Mesh->Modify();
	Capsule->Modify();
	CDO->Tags.AddUnique(TEXT("WalkerYieldSubject"));
	// Keep CharacterMovement RVO disabled: Detour Crowd owns the one live
	// avoidance solution. Stacking both systems would make provenance ambiguous.
	Movement->bUseRVOAvoidance = false;
	Movement->AvoidanceWeight = AvoidanceWeight;
	Movement->AvoidanceConsiderationRadius = ConsiderationRadius;
	CDO->AIControllerClass = bEnableAvoidance
		? ADetourCrowdAIController::StaticClass()
		: AWalkerYieldAIController::StaticClass();
	Movement->bOrientRotationToMovement = true;
	Movement->bRequestedMoveUseAcceleration = false;
	Mesh->SetSkeletalMeshAsset(StockMesh->GetSkeletalMeshAsset());
	Mesh->SetAnimInstanceClass(StockMesh->GetAnimClass());
	Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	Mesh->SetRelativeTransform(StockMesh->GetRelativeTransform());
	Mesh->SetVisibility(true);
	Mesh->SetHiddenInGame(false);
	Capsule->SetCollisionProfileName(TEXT("Pawn"));
	const auto RemoveGraphNodes = [Blueprint](UEdGraph* Graph)
	{
		if (Graph == nullptr)
		{
			return;
		}
		Graph->Modify();
		TArray<UEdGraphNode*> NodesToRemove;
		NodesToRemove.Reserve(Graph->Nodes.Num());
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			NodesToRemove.Add(Node);
		}
		for (UEdGraphNode* Node : NodesToRemove)
		{
			FBlueprintEditorUtils::RemoveNode(
				Blueprint, Node, /*bDontRecompile=*/true);
		}
		Graph->NotifyGraphChanged();
	};
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		RemoveGraphNodes(Graph);
	}
	for (UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		RemoveGraphNodes(Graph);
	}
	for (UEdGraph* Graph : Blueprint->MacroGraphs)
	{
		RemoveGraphNodes(Graph);
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate || !SaveBlueprint(Blueprint))
	{
		return FString::Printf(
			TEXT("FAIL WALKER_CONFIG_SAVE status=%d asset=%s"),
			static_cast<int32>(Blueprint->Status), *GetPathNameSafe(Blueprint));
	}
	return InspectWalkerBlueprint(
		Blueprint, bEnableAvoidance, AvoidanceWeight,
		ConsiderationRadius);
}

FString UWalkerYieldAuthoringLibrary::InspectWalkerBlueprint(
	UBlueprint* Blueprint, const bool bExpectAvoidance,
	const float ExpectedWeight, const float ExpectedConsiderationRadius)
{
	const bool bParent = Blueprint != nullptr
		&& Blueprint->GeneratedClass != nullptr
		&& Blueprint->GeneratedClass->GetSuperClass()
			== AWalkerYieldCharacter::StaticClass();
	AWalkerYieldCharacter* CDO = bParent
		? Blueprint->GeneratedClass->GetDefaultObject<AWalkerYieldCharacter>()
		: nullptr;
	UCharacterMovementComponent* Movement = CDO
		? CDO->GetCharacterMovement() : nullptr;
	USkeletalMeshComponent* Mesh = CDO ? CDO->GetMesh() : nullptr;
	UCapsuleComponent* Capsule = CDO ? CDO->GetCapsuleComponent() : nullptr;
	const UClass* ExpectedControllerClass = bExpectAvoidance
		? ADetourCrowdAIController::StaticClass()
		: AWalkerYieldAIController::StaticClass();
	const bool bAvoidance = Movement != nullptr
		&& !Movement->bUseRVOAvoidance
		&& CDO != nullptr && CDO->AIControllerClass == ExpectedControllerClass
		&& NearlyEqual(Movement->AvoidanceWeight, ExpectedWeight)
		&& NearlyEqual(
			Movement->AvoidanceConsiderationRadius,
			ExpectedConsiderationRadius);
	const bool bVisual = Mesh != nullptr
		&& Mesh->GetSkeletalMeshAsset() != nullptr
		&& Mesh->GetAnimClass() != nullptr && Mesh->IsVisible();
	const bool bCollision = Capsule != nullptr
		&& Capsule->GetCollisionProfileName() == TEXT("Pawn")
		&& Capsule->GetCollisionEnabled()
			== ECollisionEnabled::QueryAndPhysics
		&& Capsule->GetCollisionResponseToChannel(ECC_Pawn) == ECR_Block;
	const bool bRuntime = CDO != nullptr
		&& CDO->ActorHasTag(TEXT("WalkerYieldSubject"))
		&& CDO->AIControllerClass == ExpectedControllerClass
		&& CDO->AutoPossessAI == EAutoPossessAI::PlacedInWorldOrSpawned
		&& Movement != nullptr && Movement->bOrientRotationToMovement
		&& !Movement->bRequestedMoveUseAcceleration;
	int32 GraphNodes = 0;
	if (Blueprint != nullptr)
	{
		for (const UEdGraph* Graph : Blueprint->UbergraphPages)
		{
			GraphNodes += Graph ? Graph->Nodes.Num() : 0;
		}
		for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			GraphNodes += Graph ? Graph->Nodes.Num() : 0;
		}
		for (const UEdGraph* Graph : Blueprint->MacroGraphs)
		{
			GraphNodes += Graph ? Graph->Nodes.Num() : 0;
		}
	}
	const bool bPass = bParent && bAvoidance && bVisual && bCollision
		&& bRuntime && GraphNodes == 0;
	return FString::Printf(
		TEXT("%s asset=%s parent=%d parent_class=%s crowd=%d controller=%s rvo=%d weight=%.3f radius=%.3f visual=%d mesh=%s anim=%s collision=%d runtime=%d graph_nodes=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), *GetPathNameSafe(Blueprint),
		bParent ? 1 : 0,
		*ClassPath(Blueprint && Blueprint->GeneratedClass
			? Blueprint->GeneratedClass->GetSuperClass() : nullptr),
		bExpectAvoidance ? 1 : 0,
		*GetPathNameSafe(CDO ? CDO->AIControllerClass.Get() : nullptr),
		Movement && Movement->bUseRVOAvoidance ? 1 : 0,
		Movement ? Movement->AvoidanceWeight : -1.0f,
		Movement ? Movement->AvoidanceConsiderationRadius : -1.0f,
		bVisual ? 1 : 0,
		*GetPathNameSafe(Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr),
		*GetPathNameSafe(Mesh ? Mesh->GetAnimClass() : nullptr),
		bCollision ? 1 : 0, bRuntime ? 1 : 0, GraphNodes);
}

FString UWalkerYieldAuthoringLibrary::ConfigureGoalMarker(AActor* GoalActor)
{
	TArray<UStaticMeshComponent*> Meshes;
	if (GoalActor != nullptr)
	{
		GoalActor->GetComponents<UStaticMeshComponent>(Meshes);
	}
	UStaticMeshComponent* Mesh = Meshes.Num() == 1 ? Meshes[0] : nullptr;
	if (Mesh == nullptr)
	{
		return FString::Printf(
			TEXT("FAIL goal=%s static_meshes=%d"),
			*GetNameSafe(GoalActor), Meshes.Num());
	}
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
	const bool bPass = !Mesh->CanEverAffectNavigation()
		&& Mesh->GetCollisionEnabled() == ECollisionEnabled::NoCollision
		&& Mesh->GetCollisionProfileName()
			== UCollisionProfile::NoCollision_ProfileName;
	return FString::Printf(
		TEXT("%s goal=%s static_meshes=1 profile=%s collision=%d nav_affect=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), *GoalActor->GetPathName(),
		*Mesh->GetCollisionProfileName().ToString(),
		static_cast<int32>(Mesh->GetCollisionEnabled()),
		Mesh->CanEverAffectNavigation() ? 1 : 0);
}

FString UWalkerYieldAuthoringLibrary::BuildNavigation(
	UObject* WorldContextObject)
{
	const auto Fail = [](const FString& Message)
	{
		UE_LOG(LogTemp, Error, TEXT("WALKER-YIELD-NAVIGATION %s"), *Message);
		return Message;
	};
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr || World->WorldType != EWorldType::Editor
		|| !World->IsInitialized())
	{
		return Fail(TEXT("FAIL WORLD_CONTEXT"));
	}
	TArray<ANavMeshBoundsVolume*> BoundsVolumes;
	for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
	{
		BoundsVolumes.Add(*It);
	}
	const FBox Bounds = BoundsVolumes.Num() == 1
		? BoundsVolumes[0]->GetComponentsBoundingBox(true) : FBox(ForceInit);
	if (BoundsVolumes.Num() != 1
		|| !BoundsVolumes[0]->HasActorRegisteredAllComponents()
		|| !Bounds.IsValid)
	{
		return Fail(FString::Printf(
			TEXT("FAIL NAV_BOUNDS count=%d registered=%d valid=%d"),
			BoundsVolumes.Num(), BoundsVolumes.Num() == 1
				&& BoundsVolumes[0]->HasActorRegisteredAllComponents() ? 1 : 0,
			Bounds.IsValid ? 1 : 0));
	}
	AWorldSettings* Settings = World->GetWorldSettings();
	UNavigationSystemConfig* Config = Settings
		? Settings->GetNavigationSystemConfig() : nullptr;
	UClass* NavigationClass = Config
		? Config->NavigationSystemClass.ResolveClass() : nullptr;
	const bool bPersistent = Settings != nullptr
		&& Settings->GetNavigationSystemConfigOverride() == nullptr
		&& Config != nullptr && Config->GetOuter() == Settings
		&& !Config->HasAnyFlags(RF_Transient)
		&& Settings->IsNavigationSystemEnabled()
		&& NavigationClass == UNavigationSystemV1::StaticClass();
	if (!bPersistent)
	{
		return Fail(FString::Printf(
			TEXT("FAIL NAV_CONFIG config=%s outer=%s class=%s"),
			*GetPathNameSafe(Config),
			*GetPathNameSafe(Config ? Config->GetOuter() : nullptr),
			*GetPathNameSafe(NavigationClass)));
	}

	Settings->SetNavigationSystemConfigOverride(Config);
	FNavigationSystem::AddNavigationSystemToWorld(
		*World, FNavigationSystemRunMode::EditorMode, Config,
		true, true);
	UNavigationSystemV1* NavigationSystem =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	if (NavigationSystem == nullptr)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(TEXT("FAIL NAV_SYSTEM_CREATE"));
	}
	constexpr uint8 AsyncLoadLock =
		static_cast<uint8>(ENavigationBuildLock::AsyncLoadLock);
	constexpr uint8 OtherLocks = static_cast<uint8>(
		ENavigationBuildLock::NoUpdateInEditor
		| ENavigationBuildLock::NoUpdateInPIE
		| ENavigationBuildLock::InitialLock
		| ENavigationBuildLock::Custom);
	const bool bAsync = NavigationSystem->IsNavigationBuildingLocked(AsyncLoadLock);
	const bool bOther = NavigationSystem->IsNavigationBuildingLocked(OtherLocks);
	FAssetCompilingManager::Get().FinishAllCompilation();
	const int32 PendingAssets =
		FAssetCompilingManager::Get().GetNumRemainingAssets();
	if (!bAsync || bOther || PendingAssets != 0)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(FString::Printf(
			TEXT("FAIL NAV_LOCK async=%d other=%d compiles=%d"),
			bAsync ? 1 : 0, bOther ? 1 : 0, PendingAssets));
	}
	NavigationSystem->RemoveNavigationBuildLock(
		AsyncLoadLock,
		UNavigationSystemV1::ELockRemovalRebuildAction::NoRebuild);
	if (NavigationSystem->IsNavigationBuildingLocked())
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(TEXT("FAIL NAV_UNLOCK"));
	}
	NavigationSystem->OnNavigationBoundsUpdated(BoundsVolumes[0]);
	NavigationSystem->Build();
	TArray<ARecastNavMesh*> Recasts;
	for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
	{
		Recasts.Add(*It);
	}
	ARecastNavMesh* Recast = Recasts.Num() == 1 ? Recasts[0] : nullptr;
	const bool bDefault = Recast != nullptr
		&& NavigationSystem->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate) == Recast;
	const int32 Tiles = Recast ? Recast->GetNumActiveTiles() : 0;
	const bool bBuilding = NavigationSystem->IsNavigationBuildInProgress();
	const int32 Tasks = NavigationSystem->GetNumRemainingBuildTasks();
	if (!bDefault || Tiles <= 0 || bBuilding || Tasks != 0)
	{
		Settings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(FString::Printf(
			TEXT("FAIL NAV_BUILD recasts=%d default=%d tiles=%d building=%d tasks=%d"),
			Recasts.Num(), bDefault ? 1 : 0, Tiles,
			bBuilding ? 1 : 0, Tasks));
	}

	FEnumProperty* RuntimeGenerationProperty =
		FindFProperty<FEnumProperty>(
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
		return Fail(TEXT("FAIL NAV_RUNTIME_PROPERTY"));
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
	if (!bRuntimeDynamic)
	{
		return Fail(FString::Printf(
			TEXT("FAIL NAV_RUNTIME_MODE mode=%d supports=%d"),
			static_cast<int32>(Recast->GetRuntimeGenerationMode()),
			Recast->SupportsRuntimeGeneration() ? 1 : 0));
	}
	return FString::Printf(
		TEXT("PASS persistent=1 async_lock=1 other_lock=0 compiles=0 bounds=1 recast=1 default=1 runtime_dynamic=1 runtime_supported=1 active_tiles=%d building=0 tasks=0"),
		Tiles);
}

FString UWalkerYieldAuthoringLibrary::InspectWorld(
	UObject* WorldContextObject, const int32 ExpectedScenarios,
	const int32 ExpectedFixtures, const int32 ExpectedWalkers,
	const int32 ExpectedGoals)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL WORLD_MISSING");
	}
	int32 Scenarios = 0;
	int32 Fixtures = 0;
	int32 Walkers = 0;
	int32 Goals = 0;
	int32 NavBounds = 0;
	int32 Recasts = 0;
	ARecastNavMesh* ExactRecast = nullptr;
	TSet<FName> SpecificScenarioTags;
	TSet<FName> SpecificWalkerTags;
	TSet<FName> SpecificGoalTags;
	TSet<const UClass*> WalkerClasses;
	TArray<AWalkerYieldScenarioActor*> ScenarioActors;
	TMap<FName, AActor*> WalkerByTag;
	TMap<FName, AActor*> GoalByTag;
	TMap<FName, int32> WalkerTagCounts;
	TMap<FName, int32> GoalTagCounts;
	bool bCommonTags = true;
	bool bGoalMarkersNonNav = true;
	TArray<FString> GoalMarkerProblems;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Cast<AWalkerYieldScenarioActor>(Actor))
		{
			++Scenarios;
			ScenarioActors.Add(CastChecked<AWalkerYieldScenarioActor>(Actor));
			bCommonTags = bCommonTags
				&& Actor->ActorHasTag(TEXT("WalkerYieldScenario"));
			for (const FName Tag : Actor->Tags)
			{
				if (Tag.ToString().StartsWith(TEXT("WalkerYieldScenario.")))
				{
					SpecificScenarioTags.Add(Tag);
				}
			}
		}
		if (Cast<ABothWalkersYieldFunctionalTestBase>(Actor))
		{
			++Fixtures;
		}
		if (Cast<AWalkerYieldCharacter>(Actor))
		{
			++Walkers;
			WalkerClasses.Add(Actor->GetClass());
			bCommonTags = bCommonTags
				&& Actor->ActorHasTag(TEXT("WalkerYieldSubject"));
			for (const FName Tag : Actor->Tags)
			{
				if (Tag.ToString().StartsWith(TEXT("WalkerYieldSubject.")))
				{
					SpecificWalkerTags.Add(Tag);
					WalkerTagCounts.FindOrAdd(Tag) += 1;
					WalkerByTag.FindOrAdd(Tag) = Actor;
				}
			}
		}
		if (Actor->ActorHasTag(TEXT("WalkerYieldGoal")))
		{
			++Goals;
			TArray<UStaticMeshComponent*> GoalMeshes;
			Actor->GetComponents<UStaticMeshComponent>(GoalMeshes);
			const UStaticMeshComponent* GoalMesh =
				GoalMeshes.Num() == 1 ? GoalMeshes[0] : nullptr;
			const bool bGoalMarkerNonNav = GoalMesh != nullptr
				&& GoalMesh->GetCollisionProfileName()
					== UCollisionProfile::NoCollision_ProfileName
				&& GoalMesh->GetCollisionEnabled() == ECollisionEnabled::NoCollision
				&& !GoalMesh->CanEverAffectNavigation();
			if (!bGoalMarkerNonNav)
			{
				GoalMarkerProblems.Add(FString::Printf(
					TEXT("%s:meshes=%d:profile=%s:collision=%d:nav=%d"),
					*Actor->GetName(), GoalMeshes.Num(),
					GoalMesh ? *GoalMesh->GetCollisionProfileName().ToString()
						: TEXT("missing"),
					GoalMesh ? static_cast<int32>(GoalMesh->GetCollisionEnabled()) : -1,
					GoalMesh && GoalMesh->CanEverAffectNavigation() ? 1 : 0));
			}
			bGoalMarkersNonNav = bGoalMarkersNonNav && bGoalMarkerNonNav;
			for (const FName Tag : Actor->Tags)
			{
				if (Tag.ToString().StartsWith(TEXT("WalkerYieldGoal.")))
				{
					SpecificGoalTags.Add(Tag);
					GoalTagCounts.FindOrAdd(Tag) += 1;
					GoalByTag.FindOrAdd(Tag) = Actor;
				}
			}
		}
		NavBounds += Cast<ANavMeshBoundsVolume>(Actor) ? 1 : 0;
		if (ARecastNavMesh* Recast = Cast<ARecastNavMesh>(Actor))
		{
			++Recasts;
			ExactRecast = Recast;
		}
	}
	bool bScenarioFacts = ScenarioActors.Num() == ExpectedScenarios;
	TSet<FName> ScenarioIds;
	TSet<FString> FactSignatures;
	for (const AWalkerYieldScenarioActor* Scenario : ScenarioActors)
	{
		ScenarioIds.Add(Scenario->ScenarioId);
		FactSignatures.Add(FString::Printf(
			TEXT("%.1f:%.1f:%.1f:%.1f"), Scenario->PairASpeed,
			Scenario->PairBSpeed, Scenario->PairARadius,
			Scenario->PairBRadius));
		const TArray<FName> WalkerTags = {
			Scenario->PairATag, Scenario->PairBTag,
			Scenario->SoloATag, Scenario->SoloBTag};
		const TArray<FName> GoalTags = {
			Scenario->PairAGoalTag, Scenario->PairBGoalTag,
			Scenario->SoloAGoalTag, Scenario->SoloBGoalTag};
		TSet<FName> UniqueWalkerTags;
		TSet<FName> UniqueGoalTags;
		for (const FName Tag : WalkerTags)
		{
			UniqueWalkerTags.Add(Tag);
		}
		for (const FName Tag : GoalTags)
		{
			UniqueGoalTags.Add(Tag);
		}
		bScenarioFacts = bScenarioFacts && !Scenario->ScenarioId.IsNone()
			&& Scenario->ExpectedWalkerClass != nullptr
			&& Scenario->ExpectedWalkerClass->ClassGeneratedBy != nullptr
			&& Scenario->ExpectedWalkerClass->GetSuperClass()
				== AWalkerYieldCharacter::StaticClass()
			&& UniqueWalkerTags.Num() == 4 && UniqueGoalTags.Num() == 4
			&& !WalkerTags.Contains(NAME_None) && !GoalTags.Contains(NAME_None)
			&& Scenario->PairASpeed >= 200.0f
			&& Scenario->PairBSpeed >= 200.0f
			&& !NearlyEqual(Scenario->PairASpeed, Scenario->PairBSpeed)
			&& Scenario->PairARadius >= 30.0f
			&& Scenario->PairBRadius >= 30.0f
			&& !NearlyEqual(Scenario->PairARadius, Scenario->PairBRadius)
			&& Scenario->AcceptanceRadius >= 40.0f
			&& Scenario->AcceptanceRadius <= 90.0f;
		for (int32 Index = 0; Index < 4 && bScenarioFacts; ++Index)
		{
			bScenarioFacts = WalkerTagCounts.FindRef(WalkerTags[Index]) == 1
				&& GoalTagCounts.FindRef(GoalTags[Index]) == 1;
		}
		if (!bScenarioFacts)
		{
			continue;
		}
		const AActor* PairA = WalkerByTag.FindRef(Scenario->PairATag);
		const AActor* PairB = WalkerByTag.FindRef(Scenario->PairBTag);
		const AActor* SoloA = WalkerByTag.FindRef(Scenario->SoloATag);
		const AActor* SoloB = WalkerByTag.FindRef(Scenario->SoloBTag);
		const AActor* PairAGoal = GoalByTag.FindRef(Scenario->PairAGoalTag);
		const AActor* PairBGoal = GoalByTag.FindRef(Scenario->PairBGoalTag);
		const AActor* SoloAGoal = GoalByTag.FindRef(Scenario->SoloAGoalTag);
		const AActor* SoloBGoal = GoalByTag.FindRef(Scenario->SoloBGoalTag);
		bScenarioFacts = PairA->GetClass() == Scenario->ExpectedWalkerClass
			&& PairB->GetClass() == Scenario->ExpectedWalkerClass
			&& SoloA->GetClass() == Scenario->ExpectedWalkerClass
			&& SoloB->GetClass() == Scenario->ExpectedWalkerClass;
		if (!bScenarioFacts)
		{
			continue;
		}
		const FVector PairAPath = PairAGoal->GetActorLocation()
			- PairA->GetActorLocation();
		const FVector PairBPath = PairBGoal->GetActorLocation()
			- PairB->GetActorLocation();
		const FVector SoloAPath = SoloAGoal->GetActorLocation()
			- SoloA->GetActorLocation();
		const FVector SoloBPath = SoloBGoal->GetActorLocation()
			- SoloB->GetActorLocation();
		const FVector PairADirection = FVector(
			PairAPath.X, PairAPath.Y, 0.0f).GetSafeNormal();
		const FVector PairBDirection = FVector(
			PairBPath.X, PairBPath.Y, 0.0f).GetSafeNormal();
		const FVector SoloADirection = FVector(
			SoloAPath.X, SoloAPath.Y, 0.0f).GetSafeNormal();
		const FVector SoloBDirection = FVector(
			SoloBPath.X, SoloBPath.Y, 0.0f).GetSafeNormal();
		const FVector PairAMidpoint =
			(PairA->GetActorLocation() + PairAGoal->GetActorLocation()) * 0.5f;
		const FVector PairBMidpoint =
			(PairB->GetActorLocation() + PairBGoal->GetActorLocation()) * 0.5f;
		bScenarioFacts = PairAPath.Size2D() >= 1000.0f
			&& PairBPath.Size2D() >= 1000.0f
			&& FMath::Abs(FVector::DotProduct(
				PairADirection, PairBDirection)) <= 0.02f
			&& FVector::Dist2D(PairAMidpoint, PairBMidpoint) <= 5.0f
			&& FVector::DotProduct(PairADirection, SoloADirection) >= 0.999f
			&& FVector::DotProduct(PairBDirection, SoloBDirection) >= 0.999f
			&& FMath::Abs(PairAPath.Size2D() - SoloAPath.Size2D()) <= 5.0f
			&& FMath::Abs(PairBPath.Size2D() - SoloBPath.Size2D()) <= 5.0f
			&& LateralSeparation(SoloA->GetActorLocation(),
				PairA->GetActorLocation(), PairADirection) >= 900.0
			&& LateralSeparation(SoloB->GetActorLocation(),
				PairB->GetActorLocation(), PairBDirection) >= 900.0;
	}
	bScenarioFacts = bScenarioFacts
		&& ScenarioIds.Num() == ExpectedScenarios
		&& (ExpectedScenarios <= 1 || FactSignatures.Num() == ExpectedScenarios);
	const bool bPass = Scenarios == ExpectedScenarios
		&& Fixtures == ExpectedFixtures && Walkers == ExpectedWalkers
		&& Goals == ExpectedGoals && SpecificScenarioTags.Num() == ExpectedScenarios
		&& SpecificWalkerTags.Num() == ExpectedWalkers
		&& SpecificGoalTags.Num() == ExpectedGoals && WalkerClasses.Num() == 1
		&& bCommonTags && bScenarioFacts && bGoalMarkersNonNav
		&& NavBounds == 1 && Recasts == 1 && ExactRecast != nullptr
		&& ExactRecast->GetRuntimeGenerationMode()
			== ERuntimeGenerationType::Dynamic
		&& ExactRecast->SupportsRuntimeGeneration();
	return FString::Printf(
		TEXT("%s scenarios=%d fixtures=%d walkers=%d goals=%d scenario_tags=%d walker_tags=%d goal_tags=%d walker_classes=%d common_tags=%d scenario_facts=%d goal_markers_non_nav=%d goal_marker_problems=%s nav_bounds=%d recast=%d runtime_dynamic=%d runtime_supported=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), Scenarios, Fixtures,
		Walkers, Goals, SpecificScenarioTags.Num(), SpecificWalkerTags.Num(),
		SpecificGoalTags.Num(), WalkerClasses.Num(), bCommonTags ? 1 : 0,
		bScenarioFacts ? 1 : 0, bGoalMarkersNonNav ? 1 : 0,
		*FString::Join(GoalMarkerProblems, TEXT("|")),
		NavBounds, Recasts,
		ExactRecast && ExactRecast->GetRuntimeGenerationMode()
			== ERuntimeGenerationType::Dynamic ? 1 : 0,
		ExactRecast && ExactRecast->SupportsRuntimeGeneration() ? 1 : 0);
}
