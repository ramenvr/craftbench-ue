// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/WorkerPlanAssetAuthoring.h"

#include "Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/WorkerPlanStateTreeTypes.h"

#include "AI/NavigationSystemBase.h"
#include "AI/NavigationSystemConfig.h"
#include "AssetCompilingManager.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/StateTreeAIComponentSchema.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/PackageName.h"
#include "NavigationSystem.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "StateTree.h"
#include "StateTreeCompilerLog.h"
#include "StateTreeEditingSubsystem.h"
#include "StateTreeEditorData.h"
#include "StateTreeFactory.h"
#include "StateTreeState.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

namespace
{
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
}

bool UWorkerPlanAssetAuthoring::AuthorStateTree(
	const FString& PackageName, FString& OutMessage)
{
	OutMessage.Reset();
	if (!FPackageName::IsValidLongPackageName(PackageName)
		|| FPackageName::DoesPackageExist(PackageName))
	{
		OutMessage = TEXT("FAIL AUTHOR_PATH_INVALID_OR_EXISTS path=") + PackageName;
		return false;
	}

	UPackage* Package = CreatePackage(*PackageName);
	UStateTreeFactory* Factory = NewObject<UStateTreeFactory>();
	Factory->SetSchemaClass(UStateTreeAIComponentSchema::StaticClass());
	UStateTree* Tree = Cast<UStateTree>(Factory->FactoryCreateNew(
		UStateTree::StaticClass(), Package, *FPackageName::GetLongPackageAssetName(PackageName),
		RF_Public | RF_Standalone, nullptr, GWarn));
	if (Tree == nullptr)
	{
		OutMessage = TEXT("FAIL FACTORY_CREATE path=") + PackageName;
		return false;
	}

	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(Tree->EditorData);
	if (EditorData == nullptr || EditorData->SubTrees.Num() != 1
		|| EditorData->SubTrees[0] == nullptr)
	{
		OutMessage = TEXT("FAIL EDITOR_DATA_ROOT");
		return false;
	}
	UStateTreeState& Root = *EditorData->SubTrees[0];
	Root.Name = TEXT("Root");
	UStateTreeState& Idle = Root.AddChildState(TEXT("Idle"));
	UStateTreeState& Active = Root.AddChildState(TEXT("Active"));
	FStateTreeTransition& Transition = Idle.AddTransition(
		EStateTreeTransitionTrigger::OnTick,
		EStateTreeTransitionType::GotoState, &Active);
	auto& SignalCondition =
		Transition.AddConditionWithOuter<FWorkerPlanSignalCondition>(&Idle);
	SignalCondition.SetNodeName(TEXT("SeparatePlanSignal"));
	auto& NavigationTask = Active.AddTask<FWorkerPlanNavigateTask>();
	NavigationTask.SetNodeName(TEXT("PersistentPlanNavigation"));

	FStateTreeCompilerLog CompileLog;
	if (!UStateTreeEditingSubsystem::CompileStateTree(Tree, CompileLog)
		|| !Tree->IsReadyToRun())
	{
		OutMessage = TEXT("FAIL COMPILE_NOT_READY");
		return false;
	}
	FAssetRegistryModule::AssetCreated(Tree);
	if (!SaveAsset(Tree))
	{
		OutMessage = TEXT("FAIL SAVE path=") + PackageName;
		return false;
	}
	FString Detail;
	if (!InspectStateTree(Tree, Detail))
	{
		OutMessage = TEXT("FAIL SAME_PROCESS_READBACK ") + Detail;
		return false;
	}
	OutMessage = TEXT("PASS SAVED ") + Detail;
	return true;
}

bool UWorkerPlanAssetAuthoring::InspectStateTree(
	UStateTree* StateTree, FString& OutMessage)
{
	OutMessage.Reset();
	const UStateTreeEditorData* EditorData =
		StateTree ? Cast<UStateTreeEditorData>(StateTree->EditorData) : nullptr;
	const bool bBase = StateTree != nullptr && EditorData != nullptr
		&& StateTree->IsReadyToRun() && EditorData->Schema
		&& EditorData->Schema->IsA<UStateTreeAIComponentSchema>()
		&& EditorData->SubTrees.Num() == 1 && EditorData->SubTrees[0] != nullptr;
	const UStateTreeState* Root = bBase ? EditorData->SubTrees[0].Get() : nullptr;
	const bool bOwnership = Root != nullptr && Root->Name == TEXT("Root")
		&& Root->Children.Num() == 2 && Root->Children[0] != nullptr
		&& Root->Children[1] != nullptr
		&& Root->Children[0]->Name == TEXT("Idle")
		&& Root->Children[1]->Name == TEXT("Active");
	const UStateTreeState* Idle = bOwnership ? Root->Children[0].Get() : nullptr;
	const UStateTreeState* Active = bOwnership ? Root->Children[1].Get() : nullptr;
	bool bSignalTransition = false;
	if (Idle != nullptr && Idle->Transitions.Num() == 1)
	{
		const FStateTreeTransition& Transition = Idle->Transitions[0];
		bSignalTransition = Transition.Trigger == EStateTreeTransitionTrigger::OnTick
			&& Transition.State.Name == TEXT("Active")
			&& Transition.Conditions.Num() == 1
			&& Transition.Conditions[0].Node.GetScriptStruct()
				== FWorkerPlanSignalCondition::StaticStruct();
	}
	const bool bNavigationTask = Active != nullptr && Active->Tasks.Num() == 1
		&& Active->Tasks[0].Node.GetScriptStruct()
			== FWorkerPlanNavigateTask::StaticStruct();
	const bool bPass = bOwnership && bSignalTransition && bNavigationTask;
	OutMessage = FString::Printf(
		TEXT("%s ownership=%d signal_transition=%d navigation_task=%d tree=%s schema=%s"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bOwnership ? 1 : 0,
		bSignalTransition ? 1 : 0, bNavigationTask ? 1 : 0,
		*GetPathNameSafe(StateTree),
		*GetPathNameSafe(EditorData ? EditorData->Schema.Get() : nullptr));
	return bPass;
}

bool UWorkerPlanAssetAuthoring::AuthorStateTreeShell(
	const FString& PackageName, FString& OutMessage)
{
	OutMessage.Reset();
	if (!FPackageName::IsValidLongPackageName(PackageName)
		|| FPackageName::DoesPackageExist(PackageName))
	{
		OutMessage = TEXT("FAIL SHELL_PATH_INVALID_OR_EXISTS path=") + PackageName;
		return false;
	}

	UPackage* Package = CreatePackage(*PackageName);
	UStateTreeFactory* Factory = NewObject<UStateTreeFactory>();
	Factory->SetSchemaClass(UStateTreeAIComponentSchema::StaticClass());
	UStateTree* Tree = Cast<UStateTree>(Factory->FactoryCreateNew(
		UStateTree::StaticClass(), Package,
		*FPackageName::GetLongPackageAssetName(PackageName),
		RF_Public | RF_Standalone, nullptr, GWarn));
	if (Tree == nullptr)
	{
		OutMessage = TEXT("FAIL SHELL_FACTORY_CREATE path=") + PackageName;
		return false;
	}

	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(Tree->EditorData);
	if (EditorData == nullptr || EditorData->SubTrees.Num() != 1
		|| EditorData->SubTrees[0] == nullptr)
	{
		OutMessage = TEXT("FAIL SHELL_EDITOR_DATA_ROOT");
		return false;
	}
	UStateTreeState& Root = *EditorData->SubTrees[0];
	Root.Name = TEXT("Root");
	Root.AddChildState(TEXT("Idle"));
	Root.AddChildState(TEXT("Active"));

	FStateTreeCompilerLog CompileLog;
	if (!UStateTreeEditingSubsystem::CompileStateTree(Tree, CompileLog)
		|| !Tree->IsReadyToRun())
	{
		OutMessage = TEXT("FAIL SHELL_COMPILE_NOT_READY");
		return false;
	}
	FAssetRegistryModule::AssetCreated(Tree);
	if (!SaveAsset(Tree))
	{
		OutMessage = TEXT("FAIL SHELL_SAVE path=") + PackageName;
		return false;
	}
	FString Detail;
	if (!InspectStateTreeShell(Tree, Detail))
	{
		OutMessage = TEXT("FAIL SHELL_SAME_PROCESS_READBACK ") + Detail;
		return false;
	}
	OutMessage = TEXT("PASS SAVED ") + Detail;
	return true;
}

bool UWorkerPlanAssetAuthoring::InspectStateTreeShell(
	UStateTree* StateTree, FString& OutMessage)
{
	OutMessage.Reset();
	const UStateTreeEditorData* EditorData =
		StateTree ? Cast<UStateTreeEditorData>(StateTree->EditorData) : nullptr;
	const bool bBase = StateTree != nullptr && EditorData != nullptr
		&& StateTree->IsReadyToRun() && EditorData->Schema
		&& EditorData->Schema->IsA<UStateTreeAIComponentSchema>()
		&& EditorData->Evaluators.IsEmpty() && EditorData->GlobalTasks.IsEmpty()
		&& EditorData->SubTrees.Num() == 1 && EditorData->SubTrees[0] != nullptr;
	const UStateTreeState* Root = bBase ? EditorData->SubTrees[0].Get() : nullptr;
	const bool bOwnership = Root != nullptr && Root->Name == TEXT("Root")
		&& Root->Children.Num() == 2 && Root->Children[0] != nullptr
		&& Root->Children[1] != nullptr
		&& Root->Children[0]->Name == TEXT("Idle")
		&& Root->Children[1]->Name == TEXT("Active");
	const auto IsEmptyState = [](const UStateTreeState* State)
	{
		return State != nullptr && State->EnterConditions.IsEmpty()
			&& State->Tasks.IsEmpty() && State->Transitions.IsEmpty();
	};
	const bool bBaselineEmpty = bOwnership && IsEmptyState(Root)
		&& IsEmptyState(Root->Children[0]) && IsEmptyState(Root->Children[1])
		&& Root->Children[0]->Children.IsEmpty()
		&& Root->Children[1]->Children.IsEmpty();
	OutMessage = FString::Printf(
		TEXT("%s baseline_empty=%d ownership=%d signal_transition=0 navigation_task=0 tree=%s schema=%s"),
		bBaselineEmpty ? TEXT("PASS") : TEXT("FAIL"),
		bBaselineEmpty ? 1 : 0, bOwnership ? 1 : 0,
		*GetPathNameSafe(StateTree),
		*GetPathNameSafe(EditorData ? EditorData->Schema.Get() : nullptr));
	return bBaselineEmpty;
}

FString UWorkerPlanAssetAuthoring::BuildAdmissionNavigation(
	UObject* WorldContextObject)
{
	const auto Fail = [](FString Message)
	{
		UE_LOG(LogTemp, Error,
			TEXT("WORKER-PLAN-ADMISSION-NAVIGATION-NATIVE %s"), *Message);
		return Message;
	};
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr || World->WorldType != EWorldType::Editor
		|| !World->IsInitialized())
	{
		return Fail(FString::Printf(
			TEXT("FAIL WORLD_CONTEXT world=%s type=%d initialized=%d"),
			*GetPathNameSafe(World),
			World ? static_cast<int32>(World->WorldType.GetValue()) : -1,
			World && World->IsInitialized() ? 1 : 0));
	}

	TArray<ANavMeshBoundsVolume*> BoundsVolumes;
	for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
	{
		BoundsVolumes.Add(*It);
	}
	const FBox BoundsBox = BoundsVolumes.Num() == 1
		? BoundsVolumes[0]->GetComponentsBoundingBox(true)
		: FBox(ForceInit);
	const bool bBoundsRegistered = BoundsVolumes.Num() == 1
		&& BoundsVolumes[0]->HasActorRegisteredAllComponents();
	if (BoundsVolumes.Num() != 1 || !bBoundsRegistered || !BoundsBox.IsValid)
	{
		return Fail(FString::Printf(
			TEXT("FAIL NAV_BOUNDS bounds=%d registered=%d box_valid=%d"),
			BoundsVolumes.Num(), bBoundsRegistered ? 1 : 0,
			BoundsBox.IsValid ? 1 : 0));
	}

	AWorldSettings* WorldSettings = World->GetWorldSettings();
	UNavigationSystemConfig* NavigationConfig =
		WorldSettings ? WorldSettings->GetNavigationSystemConfig() : nullptr;
	const bool bPersistentConfig = WorldSettings != nullptr
		&& WorldSettings->GetNavigationSystemConfigOverride() == nullptr
		&& NavigationConfig != nullptr
		&& NavigationConfig->GetOuter() == WorldSettings
		&& !NavigationConfig->HasAnyFlags(RF_Transient)
		&& WorldSettings->IsNavigationSystemEnabled();
	const bool bSupportedConfigClass = NavigationConfig != nullptr
		&& (NavigationConfig->GetClass() == UNavigationSystemConfig::StaticClass()
			|| NavigationConfig->GetClass()
				== UNavigationSystemModuleConfig::StaticClass());
	UClass* ConfiguredNavigationClass = NavigationConfig
		? NavigationConfig->NavigationSystemClass.ResolveClass() : nullptr;
	const bool bExactNavigationClass = ConfiguredNavigationClass
		== UNavigationSystemV1::StaticClass();
	if (!bPersistentConfig || !bSupportedConfigClass || !bExactNavigationClass)
	{
		return Fail(FString::Printf(
			TEXT("FAIL NAV_CONFIG persistent=%d config=%s class=%s "
				 "class_supported=%d configured_nav_class=%s "
				 "configured_nav_class_exact=%d"),
			bPersistentConfig ? 1 : 0, *GetPathNameSafe(NavigationConfig),
			*GetPathNameSafe(NavigationConfig ? NavigationConfig->GetClass() : nullptr),
			bSupportedConfigClass ? 1 : 0,
			*GetPathNameSafe(ConfiguredNavigationClass),
			bExactNavigationClass ? 1 : 0));
	}

	// This is the public engine sequence used by ANavSystemConfigOverride.
	// The supplied config is the WorldSettings-owned instanced config, not a
	// transient author-only substitute, so the saved map remains self-contained.
	WorldSettings->SetNavigationSystemConfigOverride(NavigationConfig);
	FNavigationSystem::AddNavigationSystemToWorld(
		*World, FNavigationSystemRunMode::EditorMode, NavigationConfig,
		/*bInitializeForWorld=*/true, /*bOverridePreviousNavSys=*/true);
	UNavigationSystemV1* NavigationSystem =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	if (NavigationSystem == nullptr)
	{
		WorldSettings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(TEXT("FAIL NAV_SYSTEM_CREATE class=None"));
	}

	// EditorMode initialization deliberately takes AsyncLoadLock and normally
	// releases it from a delayed ticker after asset compilation reaches zero.
	// A one-shot commandlet does not advance that ticker before this helper.
	// Use the same public removal API as the engine, but only for that exact
	// lock and only after independently proving no asset compilation remains.
	constexpr uint8 AsyncLoadLock =
		static_cast<uint8>(ENavigationBuildLock::AsyncLoadLock);
	constexpr uint8 OtherBuildLocks = static_cast<uint8>(
		ENavigationBuildLock::NoUpdateInEditor
		| ENavigationBuildLock::NoUpdateInPIE
		| ENavigationBuildLock::InitialLock
		| ENavigationBuildLock::Custom);
	const bool bAsyncLoadLock =
		NavigationSystem->IsNavigationBuildingLocked(AsyncLoadLock);
	const bool bOtherBuildLock =
		NavigationSystem->IsNavigationBuildingLocked(OtherBuildLocks);
	const int32 AssetCompilesBeforeWait =
		FAssetCompilingManager::Get().GetNumRemainingAssets();
	if (AssetCompilesBeforeWait > 0)
	{
		FAssetCompilingManager::Get().FinishAllCompilation();
	}
	const int32 RemainingAssetCompiles =
		FAssetCompilingManager::Get().GetNumRemainingAssets();
	UE_LOG(LogTemp, Display,
		TEXT("WORKER-PLAN-AUTHOR-ASSET-COMPILE-WAIT before=%d after=%d"),
		AssetCompilesBeforeWait, RemainingAssetCompiles);
	if (!bAsyncLoadLock || bOtherBuildLock || RemainingAssetCompiles != 0)
	{
		WorldSettings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(FString::Printf(
			TEXT("FAIL NAV_BUILD_LOCK async_load_lock=%d other_lock=%d "
				 "asset_compiles=%d"),
			bAsyncLoadLock ? 1 : 0, bOtherBuildLock ? 1 : 0,
			RemainingAssetCompiles));
	}
	NavigationSystem->RemoveNavigationBuildLock(
		AsyncLoadLock,
		UNavigationSystemV1::ELockRemovalRebuildAction::NoRebuild);
	const bool bBuildLockReleased =
		!NavigationSystem->IsNavigationBuildingLocked();
	if (!bBuildLockReleased)
	{
		WorldSettings->SetNavigationSystemConfigOverride(nullptr);
		return Fail(FString::Printf(
			TEXT("FAIL NAV_BUILD_UNLOCK async_load_lock=1 other_lock=0 "
				 "asset_compiles=0 still_locked=1")));
	}

	NavigationSystem->OnNavigationBoundsUpdated(BoundsVolumes[0]);
	// Build() is public. In EditorMode it calls SpawnMissingNavigationData(),
	// registers the generated nav data, rebuilds it, and blocks through each
	// ANavigationData::EnsureBuildCompletion().
	NavigationSystem->Build();

	TArray<ARecastNavMesh*> RecastMeshes;
	for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
	{
		RecastMeshes.Add(*It);
	}
	ARecastNavMesh* Recast = RecastMeshes.Num() == 1
		? RecastMeshes[0] : nullptr;
	const bool bDefaultRecast = Recast != nullptr
		&& NavigationSystem->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate) == Recast;
	const int32 ActiveTiles = Recast ? Recast->GetNumActiveTiles() : 0;
	const bool bBuildInProgress = NavigationSystem->IsNavigationBuildInProgress();
	const int32 RemainingTasks = NavigationSystem->GetNumRemainingBuildTasks();
	// The override participates only in deterministic creation. Restore the
	// transient pointer before save; the original instanced config remains the
	// map's persistent WorldSettings configuration.
	WorldSettings->SetNavigationSystemConfigOverride(nullptr);
	if (Recast == nullptr || !bDefaultRecast || ActiveTiles <= 0
		|| bBuildInProgress || RemainingTasks != 0)
	{
		return Fail(FString::Printf(
			TEXT("FAIL NAV_BUILD recast=%d default_recast=%d active_tiles=%d build_in_progress=%d remaining_tasks=%d"),
			RecastMeshes.Num(), bDefaultRecast ? 1 : 0, ActiveTiles,
			bBuildInProgress ? 1 : 0, RemainingTasks));
	}

	return FString::Printf(
		TEXT("PASS world=Editor initialized=1 persistent_config=1 config=%s "
			 "config_class_supported=1 configured_nav_class=%s "
			 "configured_nav_class_exact=1 "
			 "async_load_lock=1 other_lock=0 asset_compiles=0 "
			 "build_lock_released=1 "
			 "nav_system=%s bounds=1 bounds_box_valid=1 recast=1 "
			 "default_recast=1 active_tiles=%d build_in_progress=0 "
			 "remaining_tasks=0 nav_data=%s"),
		*NavigationConfig->GetClass()->GetPathName(),
		*ConfiguredNavigationClass->GetPathName(),
		*NavigationSystem->GetClass()->GetPathName(), ActiveTiles,
		*Recast->GetClass()->GetPathName());
}
