// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY editor authoring and read-only inspection helper.

#include "Tasks/t3-the-guard-resumes-patrol-after-the-chase/GuardPatrolChaseAssetAuthoring.h"

#include "Tasks/t3-the-guard-resumes-patrol-after-the-chase/GuardPatrolChaseFunctionalTest.h"
#include "Tasks/t3-the-guard-resumes-patrol-after-the-chase/GuardPatrolChaseTypes.h"

#include "AI/NavigationSystemBase.h"
#include "AI/NavigationSystemConfig.h"
#include "AssetCompilingManager.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BehaviorTreeTypes.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Bool.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Object.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/BTCompositeNode.h"
#include "BehaviorTree/BTDecorator.h"
#include "BehaviorTree/Composites/BTComposite_Selector.h"
#include "BehaviorTree/Composites/BTComposite_Sequence.h"
#include "BehaviorTree/Decorators/BTDecorator_Blackboard.h"
#include "BehaviorTree/Decorators/BTDecorator_BlackboardBase.h"
#include "BehaviorTree/Decorators/BTDecorator_Loop.h"
#include "BehaviorTree/Tasks/BTTask_BlackboardBase.h"
#include "BehaviorTree/Tasks/BTTask_MoveTo.h"
#include "BehaviorTreeGraph.h"
#include "BehaviorTreeGraphNode.h"
#include "BehaviorTreeGraphNode_Composite.h"
#include "BehaviorTreeGraphNode_Decorator.h"
#include "BehaviorTreeGraphNode_Root.h"
#include "BehaviorTreeGraphNode_Task.h"
#include "EdGraphSchema_BehaviorTree.h"
#include "EdGraph/EdGraphPin.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Misc/PackageName.h"
#include "NavigationSystem.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

namespace
{
const FName AlertKey(TEXT("AlertActive"));
const FName LiveTargetKey(TEXT("LiveTarget"));
const FName PatrolPointKey(TEXT("PatrolPoint"));

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

bool SetBlackboardSelector(UObject* Node, const FName KeyName)
{
	FStructProperty* Property = Node
		? FindFProperty<FStructProperty>(Node->GetClass(), TEXT("BlackboardKey"))
		: nullptr;
	if (Property == nullptr || Property->Struct != FBlackboardKeySelector::StaticStruct())
	{
		return false;
	}
	FBlackboardKeySelector* Selector =
		Property->ContainerPtrToValuePtr<FBlackboardKeySelector>(Node);
	Selector->SelectedKeyName = KeyName;
	Selector->InvalidateResolvedKey();
	Selector->SelectedKeyType = nullptr;
	return true;
}

bool SetByteProperty(UObject* Object, const FName PropertyName, const uint8 Value)
{
	FByteProperty* Property = Object
		? FindFProperty<FByteProperty>(Object->GetClass(), PropertyName) : nullptr;
	if (Property == nullptr)
	{
		return false;
	}
	Property->SetPropertyValue_InContainer(Object, Value);
	return true;
}

bool SetBoolProperty(UObject* Object, const FName PropertyName, const bool bValue)
{
	FBoolProperty* Property = Object
		? FindFProperty<FBoolProperty>(Object->GetClass(), PropertyName) : nullptr;
	if (Property == nullptr)
	{
		return false;
	}
	Property->SetPropertyValue_InContainer(Object, bValue);
	return true;
}

bool ReadBoolProperty(const UObject* Object, const FName PropertyName)
{
	const FBoolProperty* Property = Object
		? FindFProperty<FBoolProperty>(Object->GetClass(), PropertyName) : nullptr;
	return Property && Property->GetPropertyValue_InContainer(Object);
}

template <typename TGraphNode, typename TRuntimeNode>
TGraphNode* AddGraphNode(
	UBehaviorTreeGraph* Graph, UBehaviorTree* Tree, const int32 X, const int32 Y)
{
	FGraphNodeCreator<TGraphNode> Creator(*Graph);
	TGraphNode* GraphNode = Creator.CreateNode();
	GraphNode->NodePosX = X;
	GraphNode->NodePosY = Y;
	GraphNode->NodeInstance = NewObject<TRuntimeNode>(
		Tree, TRuntimeNode::StaticClass(), NAME_None, RF_Transactional);
	GraphNode->UpdateNodeClassData();
	Creator.Finalize();
	return GraphNode;
}

template <typename TRuntimeDecorator>
UBehaviorTreeGraphNode_Decorator* AddDecorator(
	UBehaviorTreeGraph* Graph, UBehaviorTree* Tree,
	UBehaviorTreeGraphNode* ParentNode)
{
	UBehaviorTreeGraphNode_Decorator* GraphNode =
		NewObject<UBehaviorTreeGraphNode_Decorator>(Graph);
	GraphNode->NodeInstance = NewObject<TRuntimeDecorator>(
		Tree, TRuntimeDecorator::StaticClass(), NAME_None, RF_Transactional);
	GraphNode->UpdateNodeClassData();
	ParentNode->AddSubNode(GraphNode, Graph);
	return GraphNode;
}

bool Connect(UEdGraphNode* Parent, UEdGraphNode* Child)
{
	UEdGraphPin* Output = Cast<UAIGraphNode>(Parent)
		? CastChecked<UAIGraphNode>(Parent)->GetOutputPin() : nullptr;
	UEdGraphPin* Input = Cast<UAIGraphNode>(Child)
		? CastChecked<UAIGraphNode>(Child)->GetInputPin() : nullptr;
	return Output && Input && Parent->GetGraph() &&
		Parent->GetGraph()->GetSchema()->TryCreateConnection(Output, Input);
}

FBlackboardEntry MakeBoolEntry(UBlackboardData* Owner, const FName Name)
{
	FBlackboardEntry Entry;
	Entry.EntryName = Name;
	Entry.KeyType = NewObject<UBlackboardKeyType_Bool>(Owner);
	return Entry;
}

FBlackboardEntry MakeActorEntry(UBlackboardData* Owner, const FName Name)
{
	FBlackboardEntry Entry;
	Entry.EntryName = Name;
	UBlackboardKeyType_Object* Type = NewObject<UBlackboardKeyType_Object>(Owner);
	Type->BaseClass = AActor::StaticClass();
	Entry.KeyType = Type;
	return Entry;
}

bool IsExactActorKey(const UBlackboardData* Blackboard, const FName Name)
{
	const FBlackboard::FKey KeyId = Blackboard
		? Blackboard->GetKeyID(Name) : FBlackboard::InvalidKey;
	const FBlackboardEntry* Entry = Blackboard && Blackboard->IsValidKey(KeyId)
		? Blackboard->GetKey(KeyId) : nullptr;
	const UBlackboardKeyType_Object* Type = Entry
		? Cast<UBlackboardKeyType_Object>(Entry->KeyType) : nullptr;
	return Type != nullptr && Type->BaseClass == AActor::StaticClass();
}

bool IsExactBoolKey(const UBlackboardData* Blackboard, const FName Name)
{
	const FBlackboard::FKey KeyId = Blackboard
		? Blackboard->GetKeyID(Name) : FBlackboard::InvalidKey;
	const FBlackboardEntry* Entry = Blackboard && Blackboard->IsValidKey(KeyId)
		? Blackboard->GetKey(KeyId) : nullptr;
	return Entry && Entry->KeyType &&
		Entry->KeyType->GetClass() == UBlackboardKeyType_Bool::StaticClass();
}

template <typename T>
int32 CountExact(UWorld* World)
{
	if (World == nullptr)
	{
		return 0;
	}
	int32 Count = 0;
	for (TActorIterator<T> It(World); It; ++It)
	{
		Count += It->GetClass() == T::StaticClass() ? 1 : 0;
	}
	return Count;
}
}

bool UGuardPatrolChaseAssetAuthoring::AuthorDecisionAssets(
	const FString& BlackboardPackageName,
	const FString& BehaviorTreePackageName,
	const bool bAuthorCompleteSolution,
	FString& OutMessage)
{
	OutMessage.Reset();
	if (!FPackageName::IsValidLongPackageName(BlackboardPackageName) ||
		!FPackageName::IsValidLongPackageName(BehaviorTreePackageName) ||
		BlackboardPackageName == BehaviorTreePackageName ||
		FPackageName::DoesPackageExist(BlackboardPackageName) ||
		FPackageName::DoesPackageExist(BehaviorTreePackageName))
	{
		OutMessage = TEXT("FAIL OUTPUT_PATH_INVALID_OR_EXISTS");
		return false;
	}

	UPackage* BlackboardPackage = CreatePackage(*BlackboardPackageName);
	UBlackboardData* Blackboard = NewObject<UBlackboardData>(
		BlackboardPackage, *FPackageName::GetLongPackageAssetName(BlackboardPackageName),
		RF_Public | RF_Standalone);
	Blackboard->Keys = {
		MakeActorEntry(Blackboard, FBlackboard::KeySelf),
		MakeBoolEntry(Blackboard, AlertKey),
		MakeActorEntry(Blackboard, LiveTargetKey),
		MakeActorEntry(Blackboard, PatrolPointKey)};

	UPackage* TreePackage = CreatePackage(*BehaviorTreePackageName);
	UBehaviorTree* Tree = NewObject<UBehaviorTree>(
		TreePackage, *FPackageName::GetLongPackageAssetName(BehaviorTreePackageName),
		RF_Public | RF_Standalone);
	Tree->BlackboardAsset = Blackboard;
	Tree->BTGraph = FBlueprintEditorUtils::CreateNewGraph(
		Tree, TEXT("BehaviorTreeGraph"), UBehaviorTreeGraph::StaticClass(),
		UEdGraphSchema_BehaviorTree::StaticClass());
	UBehaviorTreeGraph* Graph = Cast<UBehaviorTreeGraph>(Tree->BTGraph);
	if (Graph == nullptr)
	{
		OutMessage = TEXT("FAIL GRAPH_CREATE");
		return false;
	}
	Graph->GetSchema()->CreateDefaultNodesForGraph(*Graph);
	Graph->OnCreated();
	Graph->Initialize();

	UBehaviorTreeGraphNode_Root* EditorRoot = nullptr;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (UBehaviorTreeGraphNode_Root* Candidate =
			Cast<UBehaviorTreeGraphNode_Root>(Node))
		{
			EditorRoot = Candidate;
			break;
		}
	}
	if (EditorRoot == nullptr)
	{
		OutMessage = TEXT("FAIL GRAPH_ROOT");
		return false;
	}
	EditorRoot->BlackboardAsset = Blackboard;
	EditorRoot->UpdateBlackboard();

	if (bAuthorCompleteSolution)
	{
		Graph->LockUpdates();
		UBehaviorTreeGraphNode_Composite* Selector =
			AddGraphNode<UBehaviorTreeGraphNode_Composite, UBTComposite_Selector>(
				Graph, Tree, 0, 180);
		UBehaviorTreeGraphNode_Composite* Chase =
			AddGraphNode<UBehaviorTreeGraphNode_Composite, UBTComposite_Sequence>(
				Graph, Tree, -360, 430);
		UBehaviorTreeGraphNode_Composite* Patrol =
			AddGraphNode<UBehaviorTreeGraphNode_Composite, UBTComposite_Sequence>(
				Graph, Tree, 360, 430);
		UBehaviorTreeGraphNode_Task* ChaseMove =
			AddGraphNode<UBehaviorTreeGraphNode_Task, UBTTask_MoveTo>(
				Graph, Tree, -360, 690);
		UBehaviorTreeGraphNode_Task* SelectPoint =
			AddGraphNode<UBehaviorTreeGraphNode_Task, UGuardBTTask_SelectNextPatrolPoint>(
				Graph, Tree, 210, 690);
		UBehaviorTreeGraphNode_Task* PatrolMove =
			AddGraphNode<UBehaviorTreeGraphNode_Task, UBTTask_MoveTo>(
				Graph, Tree, 510, 690);

		UBehaviorTreeGraphNode_Decorator* AlertDecorator =
			AddDecorator<UBTDecorator_Blackboard>(Graph, Tree, Chase);
		UBehaviorTreeGraphNode_Decorator* LoopDecorator =
			AddDecorator<UBTDecorator_Loop>(Graph, Tree, Patrol);
		const bool bProperties =
			SetBlackboardSelector(AlertDecorator->NodeInstance, AlertKey) &&
			SetByteProperty(AlertDecorator->NodeInstance, TEXT("BasicOperation"),
				static_cast<uint8>(EBasicKeyOperation::Set)) &&
			SetByteProperty(AlertDecorator->NodeInstance, TEXT("FlowAbortMode"),
				static_cast<uint8>(EBTFlowAbortMode::Both)) &&
			SetBoolProperty(LoopDecorator->NodeInstance, TEXT("bInfiniteLoop"), true) &&
			SetBlackboardSelector(ChaseMove->NodeInstance, LiveTargetKey) &&
			SetBlackboardSelector(SelectPoint->NodeInstance, PatrolPointKey) &&
			SetBlackboardSelector(PatrolMove->NodeInstance, PatrolPointKey);
		const bool bConnections = Connect(EditorRoot, Selector) &&
			Connect(Selector, Chase) && Connect(Selector, Patrol) &&
			Connect(Chase, ChaseMove) && Connect(Patrol, SelectPoint) &&
			Connect(Patrol, PatrolMove);
		Graph->UnlockUpdates();
		if (!bProperties || !bConnections)
		{
			OutMessage = FString::Printf(
				TEXT("FAIL GRAPH_AUTHOR properties=%d connections=%d"),
				bProperties ? 1 : 0, bConnections ? 1 : 0);
			return false;
		}
	}

	Graph->UpdateAsset(UBehaviorTreeGraph::ClearDebuggerFlags);
	Graph->OnSave();
	FAssetRegistryModule::AssetCreated(Blackboard);
	FAssetRegistryModule::AssetCreated(Tree);
	if (!SaveAsset(Blackboard) || !SaveAsset(Tree))
	{
		OutMessage = TEXT("FAIL SAVE");
		return false;
	}

	if (bAuthorCompleteSolution)
	{
		FString Detail;
		if (!InspectDecisionAssets(Tree, Blackboard, Detail))
		{
			OutMessage = TEXT("FAIL SAME_PROCESS_READBACK ") + Detail;
			return false;
		}
		OutMessage = TEXT("PASS SAVED ") + Detail;
	}
	else
	{
		FString Detail;
		if (!InspectBaselineAssets(Tree, Blackboard, Detail))
		{
			OutMessage = TEXT("FAIL SAME_PROCESS_BASELINE_READBACK ") + Detail;
			return false;
		}
		OutMessage = TEXT("PASS SAVED ") + Detail;
	}
	return true;
}

FString UGuardPatrolChaseAssetAuthoring::AuthorDecisionAssetsText(
	const FString& BlackboardPackageName,
	const FString& BehaviorTreePackageName,
	const bool bAuthorCompleteSolution)
{
	FString Detail;
	AuthorDecisionAssets(
		BlackboardPackageName,
		BehaviorTreePackageName,
		bAuthorCompleteSolution,
		Detail);
	return Detail;
}

bool UGuardPatrolChaseAssetAuthoring::InspectDecisionAssets(
	UBehaviorTree* BehaviorTree,
	UBlackboardData* Blackboard,
	FString& OutMessage)
{
	const bool bBlackboardContract = Blackboard != nullptr &&
		Blackboard->GetKeys().Num() == 4 &&
		IsExactActorKey(Blackboard, FBlackboard::KeySelf) &&
		IsExactBoolKey(Blackboard, AlertKey) &&
		IsExactActorKey(Blackboard, LiveTargetKey) &&
		IsExactActorKey(Blackboard, PatrolPointKey);
	const UBTComposite_Selector* Selector = BehaviorTree
		? Cast<UBTComposite_Selector>(BehaviorTree->RootNode) : nullptr;
	const bool bPriority = BehaviorTree != nullptr &&
		BehaviorTree->BlackboardAsset == Blackboard &&
		BehaviorTree->BTGraph != nullptr && Selector != nullptr &&
		Selector->Children.Num() == 2 &&
		Selector->Children[0].ChildComposite &&
		Selector->Children[0].ChildComposite->IsA<UBTComposite_Sequence>() &&
		Selector->Children[1].ChildComposite &&
		Selector->Children[1].ChildComposite->IsA<UBTComposite_Sequence>();

	const FBTCompositeChild* ChaseChild = bPriority ? &Selector->Children[0] : nullptr;
	const FBTCompositeChild* PatrolChild = bPriority ? &Selector->Children[1] : nullptr;
	const UBTCompositeNode* Chase = ChaseChild ? ChaseChild->ChildComposite : nullptr;
	const UBTCompositeNode* Patrol = PatrolChild ? PatrolChild->ChildComposite : nullptr;
	const UBTDecorator_Blackboard* AlertDecorator =
		ChaseChild && ChaseChild->Decorators.Num() == 1
			? Cast<UBTDecorator_Blackboard>(ChaseChild->Decorators[0]) : nullptr;
	const bool bObserverAbort = AlertDecorator != nullptr &&
		AlertDecorator->GetSelectedBlackboardKey() == AlertKey &&
		AlertDecorator->GetFlowAbortMode() == EBTFlowAbortMode::Both &&
		!AlertDecorator->IsInversed();

	const UBTTask_MoveTo* ChaseMove = Chase && Chase->Children.Num() == 1
		? Cast<UBTTask_MoveTo>(Chase->Children[0].ChildTask) : nullptr;
	const bool bChaseTarget = ChaseMove != nullptr &&
		ChaseMove->GetSelectedBlackboardKey() == LiveTargetKey;

	const UBTDecorator_Loop* Loop =
		PatrolChild && PatrolChild->Decorators.Num() == 1
			? Cast<UBTDecorator_Loop>(PatrolChild->Decorators[0]) : nullptr;
	const UGuardBTTask_SelectNextPatrolPoint* SelectPoint =
		Patrol && Patrol->Children.Num() == 2
			? Cast<UGuardBTTask_SelectNextPatrolPoint>(Patrol->Children[0].ChildTask)
			: nullptr;
	const UBTTask_MoveTo* PatrolMove = Patrol && Patrol->Children.Num() == 2
		? Cast<UBTTask_MoveTo>(Patrol->Children[1].ChildTask) : nullptr;
	const bool bPatrol = Loop != nullptr && ReadBoolProperty(Loop, TEXT("bInfiniteLoop")) &&
		SelectPoint != nullptr &&
		SelectPoint->GetSelectedBlackboardKey() == PatrolPointKey &&
		PatrolMove != nullptr &&
		PatrolMove->GetSelectedBlackboardKey() == PatrolPointKey;

	const bool bPass = bBlackboardContract && bPriority && bObserverAbort &&
		bChaseTarget && bPatrol;
	OutMessage = FString::Printf(
		TEXT("%s blackboard_contract=%d priority_selector=%d observer_abort=%d chase_target=%d patrol_loop=%d tree=%s blackboard=%s"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bBlackboardContract ? 1 : 0,
		bPriority ? 1 : 0, bObserverAbort ? 1 : 0,
		bChaseTarget ? 1 : 0, bPatrol ? 1 : 0,
		*GetPathNameSafe(BehaviorTree), *GetPathNameSafe(Blackboard));
	return bPass;
}

FString UGuardPatrolChaseAssetAuthoring::InspectDecisionAssetsText(
	UBehaviorTree* BehaviorTree,
	UBlackboardData* Blackboard)
{
	FString Detail;
	InspectDecisionAssets(BehaviorTree, Blackboard, Detail);
	return Detail;
}

bool UGuardPatrolChaseAssetAuthoring::InspectBaselineAssets(
	UBehaviorTree* BehaviorTree,
	UBlackboardData* Blackboard,
	FString& OutMessage)
{
	const bool bBlackboardContract = Blackboard != nullptr &&
		Blackboard->GetKeys().Num() == 4 &&
		IsExactActorKey(Blackboard, FBlackboard::KeySelf) &&
		IsExactBoolKey(Blackboard, AlertKey) &&
		IsExactActorKey(Blackboard, LiveTargetKey) &&
		IsExactActorKey(Blackboard, PatrolPointKey);
	const bool bEmptyEditable = BehaviorTree != nullptr &&
		BehaviorTree->BlackboardAsset == Blackboard &&
		BehaviorTree->BTGraph != nullptr && BehaviorTree->RootNode == nullptr;
	const bool bPass = bBlackboardContract && bEmptyEditable;
	OutMessage = FString::Printf(
		TEXT("%s baseline_empty=%d blackboard_contract=%d tree=%s blackboard=%s"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bEmptyEditable ? 1 : 0,
		bBlackboardContract ? 1 : 0, *GetPathNameSafe(BehaviorTree),
		*GetPathNameSafe(Blackboard));
	return bPass;
}

FString UGuardPatrolChaseAssetAuthoring::InspectBaselineAssetsText(
	UBehaviorTree* BehaviorTree,
	UBlackboardData* Blackboard)
{
	FString Detail;
	InspectBaselineAssets(BehaviorTree, Blackboard, Detail);
	return Detail;
}

bool UGuardPatrolChaseAssetAuthoring::InspectAuthoredMap(
	UObject* WorldContextObject,
	const bool bAdmissionMap,
	FString& OutMessage)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	const int32 Subjects = CountExact<AGuardPatrolCharacter>(World);
	const int32 Alerts = CountExact<AGuardAlertSource>(World);
	const int32 Targets = CountExact<AGuardChaseTarget>(World);
	const int32 Markers = CountExact<AGuardPatrolMarker>(World);
	const int32 AdmissionFixtures = CountExact<AGuardPatrolChaseAdmissionTest>(World);
	const int32 FinalFixtures = CountExact<AGuardPatrolChaseFunctionalTest>(World);
	const int32 PlayerStarts = CountExact<APlayerStart>(World);
	int32 Bounds = 0;
	for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
	{
		++Bounds;
	}
	const bool bFixture = bAdmissionMap
		? AdmissionFixtures == 1 && FinalFixtures == 0
		: AdmissionFixtures == 0 && FinalFixtures == 1;
	AGuardPatrolCharacter* Subject = nullptr;
	AGuardAlertSource* Alert = nullptr;
	AGuardChaseTarget* Target = nullptr;
	TArray<AGuardPatrolMarker*> MarkerActors;
	AGuardPatrolChaseFunctionalTest* Fixture = nullptr;
	for (TActorIterator<AGuardPatrolCharacter> It(World); It; ++It)
	{
		Subject = *It;
	}
	for (TActorIterator<AGuardAlertSource> It(World); It; ++It)
	{
		Alert = *It;
	}
	for (TActorIterator<AGuardChaseTarget> It(World); It; ++It)
	{
		Target = *It;
	}
	for (TActorIterator<AGuardPatrolMarker> It(World); It; ++It)
	{
		MarkerActors.Add(*It);
	}
	for (TActorIterator<AGuardPatrolChaseFunctionalTest> It(World); It; ++It)
	{
		if ((bAdmissionMap && It->GetClass() == AGuardPatrolChaseAdmissionTest::StaticClass()) ||
			(!bAdmissionMap && It->GetClass() == AGuardPatrolChaseFunctionalTest::StaticClass()))
		{
			Fixture = *It;
		}
	}
	const bool bTags = Subject && Subject->Tags.Num() == 1 &&
		Subject->ActorHasTag(TEXT("GuardPatrolSubject")) &&
		Alert && Alert->Tags.Num() == 1 &&
		Alert->ActorHasTag(TEXT("GuardAlertSource")) &&
		Target && Target->Tags.Num() == 1 &&
		Target->ActorHasTag(TEXT("GuardChaseTarget")) &&
		MarkerActors.Num() == 2 &&
		((MarkerActors[0]->Tags.Num() == 1 && MarkerActors[0]->ActorHasTag(TEXT("GuardPatrolMarker.A")) &&
		  MarkerActors[1]->Tags.Num() == 1 && MarkerActors[1]->ActorHasTag(TEXT("GuardPatrolMarker.B"))) ||
		 (MarkerActors[1]->Tags.Num() == 1 && MarkerActors[1]->ActorHasTag(TEXT("GuardPatrolMarker.A")) &&
		  MarkerActors[0]->Tags.Num() == 1 && MarkerActors[0]->ActorHasTag(TEXT("GuardPatrolMarker.B"))));
	const bool bDecisionReference = Subject && Subject->DecisionTree &&
		Subject->DecisionTree->BlackboardAsset;
	const bool bFixtureContract = Fixture && Subject &&
		Fixture->ExpectedBehaviorTree == Subject->DecisionTree &&
		Fixture->ExpectedBlackboard == Subject->DecisionTree->BlackboardAsset &&
		FMath::IsNearlyEqual(
			Fixture->TargetVelocity.Y, bAdmissionMap ? 135.0 : -155.0);
	UClass* ExpectedGameMode = LoadObject<UClass>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C"));
	UClass* ExpectedPawn = LoadObject<UClass>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C"));
	UClass* ExpectedController = LoadObject<UClass>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController.BP_ThirdPersonPlayerController_C"));
	const AWorldSettings* Settings = World ? World->GetWorldSettings() : nullptr;
	const AGameModeBase* GameModeCDO = Settings && Settings->DefaultGameMode
		? Settings->DefaultGameMode->GetDefaultObject<AGameModeBase>() : nullptr;
	const bool bGameMode = Settings && Settings->DefaultGameMode == ExpectedGameMode;
	const bool bPlayable = GameModeCDO &&
		GameModeCDO->DefaultPawnClass == ExpectedPawn &&
		GameModeCDO->PlayerControllerClass == ExpectedController;
	const bool bPass = World && Subjects == 1 && Alerts == 1 && Targets == 1 &&
		Markers == 2 && bFixture && PlayerStarts == 1 && Bounds == 1 &&
		bTags && bFixtureContract && bGameMode && bPlayable && bDecisionReference;
	OutMessage = FString::Printf(
		TEXT("%s admission=%d subject=%d alert=%d target=%d markers=%d admission_fixture=%d final_fixture=%d player_start=%d nav_bounds=%d tags=%d fixture_contract=%d game_mode=%d playable=%d decision_reference=%d runtime_observed=0 world=%s"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), bAdmissionMap ? 1 : 0,
		Subjects, Alerts, Targets, Markers, AdmissionFixtures, FinalFixtures,
		PlayerStarts, Bounds, bTags ? 1 : 0, bFixtureContract ? 1 : 0,
		bGameMode ? 1 : 0, bPlayable ? 1 : 0,
		bDecisionReference ? 1 : 0, *GetPathNameSafe(World));
	return bPass;
}

FString UGuardPatrolChaseAssetAuthoring::InspectAuthoredMapText(
	UObject* WorldContextObject,
	const bool bAdmissionMap)
{
	FString Detail;
	InspectAuthoredMap(WorldContextObject, bAdmissionMap, Detail);
	return Detail;
}

FString UGuardPatrolChaseAssetAuthoring::BuildAdmissionNavigation(
	UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr || World->WorldType != EWorldType::Editor ||
		!World->IsInitialized())
	{
		return TEXT("FAIL WORLD_NOT_INITIALIZED_EDITOR");
	}
	TArray<ANavMeshBoundsVolume*> BoundsVolumes;
	for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
	{
		BoundsVolumes.Add(*It);
	}
	if (BoundsVolumes.Num() != 1 ||
		!BoundsVolumes[0]->HasActorRegisteredAllComponents() ||
		!BoundsVolumes[0]->GetComponentsBoundingBox(true).IsValid)
	{
		return FString::Printf(
			TEXT("FAIL NAV_BOUNDS bounds=%d registered=%d box_valid=%d"),
			BoundsVolumes.Num(),
			BoundsVolumes.Num() == 1 &&
				BoundsVolumes[0]->HasActorRegisteredAllComponents() ? 1 : 0,
			BoundsVolumes.Num() == 1 &&
				BoundsVolumes[0]->GetComponentsBoundingBox(true).IsValid ? 1 : 0);
	}
	AWorldSettings* WorldSettings = World->GetWorldSettings();
	UNavigationSystemConfig* NavigationConfig =
		WorldSettings ? WorldSettings->GetNavigationSystemConfig() : nullptr;
	const bool bPersistentConfig = WorldSettings != nullptr &&
		WorldSettings->GetNavigationSystemConfigOverride() == nullptr &&
		NavigationConfig != nullptr && NavigationConfig->GetOuter() == WorldSettings &&
		!NavigationConfig->HasAnyFlags(RF_Transient) &&
		WorldSettings->IsNavigationSystemEnabled();
	const bool bSupportedConfigClass = NavigationConfig != nullptr &&
		(NavigationConfig->GetClass() == UNavigationSystemConfig::StaticClass() ||
		 NavigationConfig->GetClass() == UNavigationSystemModuleConfig::StaticClass());
	UClass* ConfiguredNavigationClass = NavigationConfig
		? NavigationConfig->NavigationSystemClass.ResolveClass() : nullptr;
	if (!bPersistentConfig || !bSupportedConfigClass ||
		ConfiguredNavigationClass != UNavigationSystemV1::StaticClass())
	{
		return FString::Printf(
			TEXT("FAIL NAV_CONFIG persistent=%d class_supported=%d configured_nav_class=%s"),
			bPersistentConfig ? 1 : 0, bSupportedConfigClass ? 1 : 0,
			*GetPathNameSafe(ConfiguredNavigationClass));
	}
	WorldSettings->SetNavigationSystemConfigOverride(NavigationConfig);
	FNavigationSystem::AddNavigationSystemToWorld(
		*World, FNavigationSystemRunMode::EditorMode, NavigationConfig,
		/*bInitializeForWorld=*/true, /*bOverridePreviousNavSys=*/true);
	UNavigationSystemV1* Navigation =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	if (Navigation == nullptr)
	{
		WorldSettings->SetNavigationSystemConfigOverride(nullptr);
		return TEXT("FAIL NAV_SYSTEM_MISSING");
	}
	FAssetCompilingManager::Get().FinishAllCompilation();
	constexpr uint8 AsyncLoadLock =
		static_cast<uint8>(ENavigationBuildLock::AsyncLoadLock);
	constexpr uint8 OtherBuildLocks = static_cast<uint8>(
		ENavigationBuildLock::NoUpdateInEditor |
		ENavigationBuildLock::NoUpdateInPIE |
		ENavigationBuildLock::InitialLock |
		ENavigationBuildLock::Custom);
	const bool bAsyncLoadLock =
		Navigation->IsNavigationBuildingLocked(AsyncLoadLock);
	const bool bOtherBuildLock =
		Navigation->IsNavigationBuildingLocked(OtherBuildLocks);
	const int32 RemainingAssetCompiles =
		FAssetCompilingManager::Get().GetNumRemainingAssets();
	if (!bAsyncLoadLock || bOtherBuildLock || RemainingAssetCompiles != 0)
	{
		WorldSettings->SetNavigationSystemConfigOverride(nullptr);
		return FString::Printf(
			TEXT("FAIL NAV_BUILD_LOCK async_load_lock=%d other_lock=%d asset_compiles=%d"),
			bAsyncLoadLock ? 1 : 0, bOtherBuildLock ? 1 : 0,
			RemainingAssetCompiles);
	}
	Navigation->RemoveNavigationBuildLock(
		AsyncLoadLock,
		UNavigationSystemV1::ELockRemovalRebuildAction::NoRebuild);
	if (Navigation->IsNavigationBuildingLocked())
	{
		WorldSettings->SetNavigationSystemConfigOverride(nullptr);
		return TEXT("FAIL NAV_BUILD_UNLOCK still_locked=1");
	}
	Navigation->OnNavigationBoundsUpdated(BoundsVolumes[0]);
	Navigation->Build();
	TArray<ARecastNavMesh*> Recast;
	for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
	{
		Recast.Add(*It);
	}
	ARecastNavMesh* RecastMesh = Recast.Num() == 1 ? Recast[0] : nullptr;
	const bool bDefault = RecastMesh != nullptr &&
		Navigation->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) == RecastMesh;
	int32 ActiveTiles = 0;
	if (RecastMesh != nullptr && RecastMesh->HasValidNavmesh())
	{
		TArray<FNavTileRef> TileRefs;
		RecastMesh->GetAllNavMeshTiles(TileRefs);
		for (const FNavTileRef TileRef : TileRefs)
		{
			TArray<FNavPoly> Polys;
			if (RecastMesh->GetPolysInTile(TileRef, Polys) && !Polys.IsEmpty())
			{
				++ActiveTiles;
			}
		}
	}
	const bool bPass = RecastMesh != nullptr && bDefault && ActiveTiles > 0 &&
		!Navigation->IsNavigationBuildInProgress() &&
		Navigation->GetNumRemainingBuildTasks() == 0;
	WorldSettings->SetNavigationSystemConfigOverride(nullptr);
	return FString::Printf(
		TEXT("%s recast=%d default=%d active_tiles=%d build_in_progress=%d remaining=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"), Recast.Num(),
		bDefault ? 1 : 0, ActiveTiles,
		Navigation->IsNavigationBuildInProgress() ? 1 : 0,
		Navigation->GetNumRemainingBuildTasks());
}
