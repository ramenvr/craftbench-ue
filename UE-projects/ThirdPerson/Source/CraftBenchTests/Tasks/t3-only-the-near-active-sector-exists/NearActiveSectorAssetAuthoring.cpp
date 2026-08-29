// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-only-the-near-active-sector-exists/NearActiveSectorAssetAuthoring.h"

#include "Tasks/t3-only-the-near-active-sector-exists/NearActiveSectorFunctionalTest.h"
#include "Tasks/t3-only-the-near-active-sector-exists/NearActiveSectorRuntime.h"

#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "DataLayer/DataLayerEditorSubsystem.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_GetArrayItem.h"
#include "K2Node_VariableGet.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "WorldPartition/DataLayer/DataLayerAsset.h"
#include "WorldPartition/DataLayer/DataLayerInstance.h"
#include "WorldPartition/DataLayer/DataLayerManager.h"
#include "WorldPartition/ActorDescContainerInstance.h"
#include "WorldPartition/WorldPartition.h"

DEFINE_LOG_CATEGORY_STATIC(LogNearActiveSectorAuthoring, Log, All);

namespace
{
	const FString TaskId(TEXT("t3-only-the-near-active-sector-exists"));
	const FString FinalControllerPackage =
		TEXT("/Game/Tasks/t3-only-the-near-active-sector-exists/BP_NearActiveSectorController");
	const FName ControllerName(TEXT("BP_NearActiveSectorController"));

	FString SupportRoot(const bool bAdmission)
	{
		return bAdmission
			? TEXT("/Game/__CraftBenchAdmission/t3-only-the-near-active-sector-exists")
			: TEXT("/Game/Maps/t3-only-the-near-active-sector-exists/Support");
	}

	FString LayerPath(const bool bAdmission, const TCHAR* Name)
	{
		return FString::Printf(TEXT("%s/%s.%s"), *SupportRoot(bAdmission), Name, Name);
	}

	FString Fail(const TCHAR* Gate, const FString& Detail)
	{
		const FString Result = FString::Printf(TEXT("FAIL %s %s"), Gate, *Detail);
		UE_LOG(LogNearActiveSectorAuthoring, Error,
			TEXT("NEAR-ACTIVE-SECTOR-AUTHORING %s"), *Result);
		return Result;
	}

	bool SaveObject(UObject* Object)
	{
		UPackage* Package = Object ? Object->GetOutermost() : nullptr;
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
		return UPackage::SavePackage(Package, Object, *Filename, Args);
	}

	UDataLayerAsset* CreateLayer(const FString& Root, const FName Name,
		const FColor Color)
	{
		const FString PackageName = Root + TEXT("/") + Name.ToString();
		if (FindPackage(nullptr, *PackageName) != nullptr
			|| FPackageName::DoesPackageExist(PackageName))
		{
			return nullptr;
		}
		UPackage* Package = CreatePackage(*PackageName);
		UDataLayerAsset* Asset = NewObject<UDataLayerAsset>(Package, Name,
			RF_Public | RF_Standalone | RF_Transactional);
		if (Asset == nullptr)
		{
			return nullptr;
		}
		Asset->OnCreated();
		Asset->SetType(EDataLayerType::Runtime);
		Asset->SetLoadFilter(EDataLayerLoadFilter::None);
		Asset->SetDebugColor(Color);
		Asset->PostEditChange();
		return SaveObject(Asset) ? Asset : nullptr;
	}

	template <typename TActor>
	TActor* Spawn(UWorld* World, const FVector& Location, const TCHAR* Label)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride =
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		TActor* Actor = World ? World->SpawnActor<TActor>(TActor::StaticClass(),
			FTransform(FRotator::ZeroRotator, Location), Params) : nullptr;
#if WITH_EDITOR
		if (Actor != nullptr)
		{
			Actor->SetActorLabel(Label);
		}
#endif
		return Actor;
	}

	AActor* SpawnClass(UWorld* World, UClass* Class, const FVector& Location,
		const TCHAR* Label)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride =
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AActor* Actor = World && Class ? World->SpawnActor<AActor>(Class,
			FTransform(FRotator::ZeroRotator, Location), Params) : nullptr;
#if WITH_EDITOR
		if (Actor != nullptr)
		{
			Actor->SetActorLabel(Label);
		}
#endif
		return Actor;
	}

	void MakeExternalSpatial(AActor* Actor)
	{
		if (Actor != nullptr)
		{
			Actor->SetIsSpatiallyLoaded(true);
			if (!Actor->IsPackageExternal())
			{
				Actor->SetPackageExternal(true);
			}
		}
	}

	bool SetFixtureFacts(ANearActiveSectorFunctionalTestBase* Fixture,
		UDataLayerAsset* LayerA, UDataLayerAsset* LayerB,
		const FVector& LocationA, const FVector& LocationB, const float Radius)
	{
		if (Fixture == nullptr)
		{
			return false;
		}
		Fixture->LayerA = LayerA;
		Fixture->LayerB = LayerB;
		Fixture->SectorALocation = LocationA;
		Fixture->SectorBLocation = LocationB;
		Fixture->ExpectedSourceRadius = Radius;
		return true;
	}

	template <typename TNode>
	TNode* AddNode(UEdGraph* Graph, const int32 X, const int32 Y)
	{
		TNode* Node = Graph != nullptr ? NewObject<TNode>(Graph) : nullptr;
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

	UK2Node_CallFunction* AddCall(UEdGraph* Graph, UClass* Owner,
		const FName Function, const int32 X, const int32 Y)
	{
		if (Graph == nullptr || Owner == nullptr
			|| Owner->FindFunctionByName(Function) == nullptr)
		{
			return nullptr;
		}
		UK2Node_CallFunction* Node = NewObject<UK2Node_CallFunction>(Graph);
		Node->FunctionReference.SetExternalMember(Function, Owner);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UK2Node_VariableGet* AddExternalGet(UEdGraph* Graph, UClass* Owner,
		const FName Variable, const int32 X, const int32 Y)
	{
		if (Graph == nullptr || Owner == nullptr
			|| FindFProperty<FProperty>(Owner, Variable) == nullptr)
		{
			return nullptr;
		}
		UK2Node_VariableGet* Node = NewObject<UK2Node_VariableGet>(Graph);
		Node->VariableReference.SetExternalMember(Variable, Owner);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UEdGraphPin* Pin(UEdGraphNode* Node, const FName Name,
		const EEdGraphPinDirection Direction)
	{
		return Node != nullptr ? Node->FindPin(Name, Direction) : nullptr;
	}

	bool Connect(const UEdGraphSchema_K2* Schema, UEdGraphPin* Output,
		UEdGraphPin* Input)
	{
		return Schema != nullptr && Output != nullptr && Input != nullptr
			&& Schema->TryCreateConnection(Output, Input);
	}

	UEdGraph* ResetEventGraph(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
		if (Graph == nullptr && Blueprint != nullptr
			&& !Blueprint->UbergraphPages.IsEmpty())
		{
			Graph = Blueprint->UbergraphPages[0];
		}
		if (Graph != nullptr)
		{
			for (UEdGraphNode* Existing : TArray<UEdGraphNode*>(Graph->Nodes))
			{
				Graph->RemoveNode(Existing);
			}
		}
		return Graph;
	}
}

FString UNearActiveSectorAssetAuthoring::CreateDataLayerAssets(
	const bool bAdmission)
{
	const FString Root = SupportRoot(bAdmission);
	UDataLayerAsset* LayerA = CreateLayer(Root, TEXT("DL_SectorA"), FColor::Cyan);
	UDataLayerAsset* LayerB = CreateLayer(Root, TEXT("DL_SectorB"), FColor::Orange);
	if (LayerA == nullptr || LayerB == nullptr)
	{
		return Fail(TEXT("DATA_LAYER_CREATE"), Root);
	}
	const FString Result = FString::Printf(
		TEXT("PASS DATA_LAYERS mode=%s exact=2 runtime=2 a=%s b=%s"),
		bAdmission ? TEXT("admission") : TEXT("final"),
		*LayerA->GetPathName(), *LayerB->GetPathName());
	UE_LOG(LogNearActiveSectorAuthoring, Display,
		TEXT("NEAR-ACTIVE-SECTOR-DATA-LAYERS-SAVED %s"), *Result);
	return Result;
}

FString UNearActiveSectorAssetAuthoring::InspectDataLayerAssets(
	const bool bAdmission)
{
	UDataLayerAsset* LayerA = LoadObject<UDataLayerAsset>(nullptr,
		*LayerPath(bAdmission, TEXT("DL_SectorA")));
	UDataLayerAsset* LayerB = LoadObject<UDataLayerAsset>(nullptr,
		*LayerPath(bAdmission, TEXT("DL_SectorB")));
	if (LayerA == nullptr || LayerB == nullptr || LayerA == LayerB
		|| !LayerA->IsRuntime() || !LayerB->IsRuntime()
		|| LayerA->IsClientOnly() || LayerA->IsServerOnly()
		|| LayerB->IsClientOnly() || LayerB->IsServerOnly())
	{
		return Fail(TEXT("DATA_LAYER_READBACK"), FString::Printf(
			TEXT("a=%s b=%s runtime=%d/%d filter_none=%d/%d"),
			*GetPathNameSafe(LayerA), *GetPathNameSafe(LayerB),
			LayerA != nullptr && LayerA->IsRuntime() ? 1 : 0,
			LayerB != nullptr && LayerB->IsRuntime() ? 1 : 0,
			LayerA != nullptr && !LayerA->IsClientOnly()
				&& !LayerA->IsServerOnly() ? 1 : 0,
			LayerB != nullptr && !LayerB->IsClientOnly()
				&& !LayerB->IsServerOnly() ? 1 : 0));
	}
	const FString Result = FString::Printf(
		TEXT("PASS DATA_LAYER_READBACK mode=%s exact=2 runtime=2 filter_none=2 "
			 "a=%s b=%s"), bAdmission ? TEXT("admission") : TEXT("final"),
		*LayerA->GetPathName(), *LayerB->GetPathName());
	UE_LOG(LogNearActiveSectorAuthoring, Display,
		TEXT("NEAR-ACTIVE-SECTOR-DATA-LAYERS-READBACK %s"), *Result);
	return Result;
}

FString UNearActiveSectorAssetAuthoring::CreateBaselineController()
{
	if (FPackageName::DoesPackageExist(FinalControllerPackage))
	{
		return Fail(TEXT("BASELINE_EXISTS"), FinalControllerPackage);
	}
	UPackage* Package = CreatePackage(*FinalControllerPackage);
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(
		ANearActiveSectorControllerBase::StaticClass(), Package, ControllerName,
		BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass(),
		TEXT("NearActiveSectorBaseline"));
	if (Blueprint == nullptr)
	{
		return Fail(TEXT("BASELINE_CREATE"), FinalControllerPackage);
	}
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate || !SaveObject(Blueprint))
	{
		return Fail(TEXT("BASELINE_SAVE"), FinalControllerPackage);
	}
	const FString Result = FString::Printf(
		TEXT("PASS BASELINE asset=%s parent=%s graphs=%d"),
		*Blueprint->GetPathName(), *GetPathNameSafe(Blueprint->ParentClass.Get()),
		Blueprint->FunctionGraphs.Num());
	UE_LOG(LogNearActiveSectorAuthoring, Display,
		TEXT("NEAR-ACTIVE-SECTOR-BASELINE-SAVED %s"), *Result);
	return Result;
}

FString UNearActiveSectorAssetAuthoring::BuildReferenceControllerGraph()
{
	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr,
		*(FinalControllerPackage + TEXT(".") + ControllerName.ToString()));
	if (Blueprint == nullptr || !InspectController(false).StartsWith(TEXT("PASS ")))
	{
		return Fail(TEXT("REFERENCE_ENTRY"), GetPathNameSafe(Blueprint));
	}
	UEdGraph* Graph = ResetEventGraph(Blueprint);
	const UEdGraphSchema_K2* Schema = Graph != nullptr
		? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
	int32 EventY = 0;
	UK2Node_Event* Event = Graph != nullptr
		? FKismetEditorUtilities::AddDefaultEventNode(Blueprint, Graph,
			TEXT("ApplySectorRequest"),
			ANearActiveSectorControllerBase::StaticClass(), EventY)
		: nullptr;
	UK2Node_CallFunction* Manager = AddCall(Graph,
		ANearActiveSectorControllerBase::StaticClass(),
		TEXT("GetSectorDataLayerManager"), 0, 520);
	UK2Node_VariableGet* CandidateLayers = AddExternalGet(Graph,
		ANearActiveSectorRequest::StaticClass(), TEXT("CandidateLayers"), 0, 700);
	UK2Node_GetArrayItem* Layer0 = AddNode<UK2Node_GetArrayItem>(Graph, 300, 650);
	UK2Node_GetArrayItem* Layer1 = AddNode<UK2Node_GetArrayItem>(Graph, 300, 820);
	UK2Node_VariableGet* SelectedLayer = AddExternalGet(Graph,
		ANearActiveSectorRequest::StaticClass(), TEXT("SelectedLayer"), 600, 700);
	UK2Node_VariableGet* SourceActor = AddExternalGet(Graph,
		ANearActiveSectorRequest::StaticClass(), TEXT("StreamingSourceActor"),
		900, 700);
	UK2Node_VariableGet* Destination = AddExternalGet(Graph,
		ANearActiveSectorRequest::StaticClass(), TEXT("SelectedDestination"),
		900, 850);
	UK2Node_CallFunction* Unload0 = AddCall(Graph, UDataLayerManager::StaticClass(),
		TEXT("SetDataLayerRuntimeState"), 400, 0);
	UK2Node_CallFunction* Unload1 = AddCall(Graph, UDataLayerManager::StaticClass(),
		TEXT("SetDataLayerRuntimeState"), 720, 0);
	UK2Node_CallFunction* Activate = AddCall(Graph, UDataLayerManager::StaticClass(),
		TEXT("SetDataLayerRuntimeState"), 1040, 0);
	UK2Node_CallFunction* Move = AddCall(Graph, AActor::StaticClass(),
		TEXT("K2_SetActorLocation"), 1360, 0);
	if (Event == nullptr || Schema == nullptr || Manager == nullptr
		|| CandidateLayers == nullptr || Layer0 == nullptr || Layer1 == nullptr
		|| SelectedLayer == nullptr || SourceActor == nullptr
		|| Destination == nullptr || Unload0 == nullptr || Unload1 == nullptr
		|| Activate == nullptr || Move == nullptr)
	{
		return Fail(TEXT("REFERENCE_NODES"), FinalControllerPackage);
	}
	UEdGraphPin* RequestPin = Pin(Event, TEXT("Request"), EGPD_Output);
	UEdGraphPin* CandidateOutput = Pin(
		CandidateLayers, TEXT("CandidateLayers"), EGPD_Output);
	if (!Connect(Schema, RequestPin,
			Pin(CandidateLayers, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		|| !Connect(Schema, RequestPin,
			Pin(SelectedLayer, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		|| !Connect(Schema, RequestPin,
			Pin(SourceActor, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		|| !Connect(Schema, RequestPin,
			Pin(Destination, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		|| !Connect(Schema, CandidateOutput, Layer0->GetTargetArrayPin())
		|| !Connect(Schema, CandidateOutput, Layer1->GetTargetArrayPin()))
	{
		return Fail(TEXT("REFERENCE_DATA_LINKS"), FinalControllerPackage);
	}
	Schema->TrySetDefaultValue(*Layer0->GetIndexPin(), TEXT("0"));
	Schema->TrySetDefaultValue(*Layer1->GetIndexPin(), TEXT("1"));
	for (UK2Node_CallFunction* Call : {Unload0, Unload1})
	{
		Schema->TrySetDefaultValue(*Pin(Call, TEXT("InState"), EGPD_Input),
			TEXT("Unloaded"));
		Schema->TrySetDefaultValue(*Pin(Call, TEXT("bInIsRecursive"), EGPD_Input),
			TEXT("false"));
	}
	Schema->TrySetDefaultValue(*Pin(Activate, TEXT("InState"), EGPD_Input),
		TEXT("Activated"));
	Schema->TrySetDefaultValue(*Pin(Activate, TEXT("bInIsRecursive"), EGPD_Input),
		TEXT("false"));
	Schema->TrySetDefaultValue(*Pin(Move, TEXT("bSweep"), EGPD_Input), TEXT("false"));
	Schema->TrySetDefaultValue(*Pin(Move, TEXT("bTeleport"), EGPD_Input), TEXT("true"));
	const bool bConnected =
		Connect(Schema, Pin(Event, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Unload0, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(Unload0, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Unload1, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(Unload1, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Activate, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(Activate, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Move, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(Manager, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
			Pin(Unload0, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Pin(Manager, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
			Pin(Unload1, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Pin(Manager, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
			Pin(Activate, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Layer0->GetResultPin(),
			Pin(Unload0, TEXT("InDataLayerAsset"), EGPD_Input))
		&& Connect(Schema, Layer1->GetResultPin(),
			Pin(Unload1, TEXT("InDataLayerAsset"), EGPD_Input))
		&& Connect(Schema, Pin(SelectedLayer, TEXT("SelectedLayer"), EGPD_Output),
			Pin(Activate, TEXT("InDataLayerAsset"), EGPD_Input))
		&& Connect(Schema, Pin(SourceActor, TEXT("StreamingSourceActor"), EGPD_Output),
			Pin(Move, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Pin(Destination, TEXT("SelectedDestination"), EGPD_Output),
			Pin(Move, TEXT("NewLocation"), EGPD_Input));
	if (!bConnected)
	{
		return Fail(TEXT("REFERENCE_CONNECTIONS"), FinalControllerPackage);
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate || !SaveObject(Blueprint))
	{
		return Fail(TEXT("REFERENCE_COMPILE_SAVE"),
			FString::FromInt(static_cast<int32>(Blueprint->Status)));
	}
	const FString Inspection = InspectController(true);
	if (!Inspection.StartsWith(TEXT("PASS ")))
	{
		return Fail(TEXT("REFERENCE_READBACK"), Inspection);
	}
	UE_LOG(LogNearActiveSectorAuthoring, Display,
		TEXT("NEAR-ACTIVE-SECTOR-REFERENCE-SAVED %s"), *Inspection);
	return Inspection;
}

FString UNearActiveSectorAssetAuthoring::ConfigureMap(
	UWorld* World, const bool bAdmission)
{
	if (World == nullptr || World->GetWorldPartition() == nullptr
		|| World->PersistentLevel == nullptr
		|| !World->PersistentLevel->IsUsingExternalActors())
	{
		return Fail(TEXT("WORLD_PARTITION"), GetPathNameSafe(World));
	}
	UDataLayerAsset* LayerA = LoadObject<UDataLayerAsset>(nullptr,
		*LayerPath(bAdmission, TEXT("DL_SectorA")));
	UDataLayerAsset* LayerB = LoadObject<UDataLayerAsset>(nullptr,
		*LayerPath(bAdmission, TEXT("DL_SectorB")));
	UDataLayerEditorSubsystem* EditorLayers = UDataLayerEditorSubsystem::Get();
	if (LayerA == nullptr || LayerB == nullptr || EditorLayers == nullptr
		|| EditorLayers->GetDataLayerInstance(LayerA) != nullptr
		|| EditorLayers->GetDataLayerInstance(LayerB) != nullptr)
	{
		return Fail(TEXT("DATA_LAYER_ENTRY"), GetPathNameSafe(EditorLayers));
	}
	FDataLayerCreationParameters ParamsA;
	ParamsA.DataLayerAsset = LayerA;
	ParamsA.WorldDataLayers = World->GetWorldDataLayers();
	FDataLayerCreationParameters ParamsB;
	ParamsB.DataLayerAsset = LayerB;
	ParamsB.WorldDataLayers = World->GetWorldDataLayers();
	UDataLayerInstance* InstanceA = EditorLayers->CreateDataLayerInstance(ParamsA);
	UDataLayerInstance* InstanceB = EditorLayers->CreateDataLayerInstance(ParamsB);
	if (InstanceA == nullptr || InstanceB == nullptr)
	{
		return Fail(TEXT("DATA_LAYER_INSTANCE"), GetPathNameSafe(World));
	}
	EditorLayers->SetDataLayerInitialRuntimeState(
		InstanceA, EDataLayerRuntimeState::Unloaded);
	EditorLayers->SetDataLayerInitialRuntimeState(
		InstanceB, EDataLayerRuntimeState::Unloaded);

	// Keep both governed cells well outside the stock player's World Partition
	// streaming range. The verifier-owned source must be the only reason either
	// sector becomes resident; a player source near the persistent fixtures must
	// not silently keep the first cell alive after the governed source leaves.
	const FVector LocationA(-120000.0, 0.0, 250.0);
	const FVector LocationB(120000.0, 1500.0, 250.0);
	constexpr float Radius = 3200.0f;
	ANearActiveSectorStreamingSource* Source = Spawn<ANearActiveSectorStreamingSource>(
		World, FVector(0.0, -12000.0, 250.0), TEXT("NearActiveSectorSource"));
	ANearActiveSectorRequest* Request = Spawn<ANearActiveSectorRequest>(
		World, FVector(0.0, -11000.0, 150.0), TEXT("NearActiveSectorRequest"));
	UClass* ControllerClass = bAdmission
		? ANearActiveSectorAdmissionController::StaticClass()
		: LoadClass<AActor>(nullptr,
			TEXT("/Game/Tasks/t3-only-the-near-active-sector-exists/"
				 "BP_NearActiveSectorController.BP_NearActiveSectorController_C"));
	AActor* Controller = SpawnClass(World, ControllerClass,
		FVector(0.0, -10000.0, 150.0), TEXT("NearActiveSectorController"));
	if (Source == nullptr || Request == nullptr || Controller == nullptr)
	{
		return Fail(TEXT("STAGING_ACTORS"), GetPathNameSafe(World));
	}
	Source->Tags.AddUnique(TEXT("NearActiveSectorSource"));
	Request->Tags.AddUnique(TEXT("NearActiveSectorRequest"));
	Controller->Tags.AddUnique(TEXT("NearActiveSectorController"));
	FStreamingSourceShape Shape;
	Shape.bUseGridLoadingRange = false;
	Shape.Radius = Radius;
	Source->StreamingSource->Shapes = {Shape};
	Source->StreamingSource->EnableStreamingSource();
	Request->StreamingSourceActor = Source;
	Request->CandidateLayers = {LayerA, LayerB};

	TArray<AActor*> MarkersA;
	TArray<AActor*> MarkersB;
	for (int32 Index = 0; Index < 2; ++Index)
	{
		ANearActiveSectorMarker* MarkerA = Spawn<ANearActiveSectorMarker>(World,
			LocationA + FVector(0.0, Index == 0 ? -350.0 : 350.0, 0.0),
			Index == 0 ? TEXT("SectorA_Quartz") : TEXT("SectorA_Violet"));
		ANearActiveSectorMarker* MarkerB = Spawn<ANearActiveSectorMarker>(World,
			LocationB + FVector(0.0, Index == 0 ? -420.0 : 420.0, 0.0),
			Index == 0 ? TEXT("SectorB_Amber") : TEXT("SectorB_Cedar"));
		if (MarkerA == nullptr || MarkerB == nullptr)
		{
			return Fail(TEXT("MARKER_SPAWN"), FString::FromInt(Index));
		}
		MarkerA->SectorId = TEXT("SectorA");
		MarkerA->MarkerId = Index == 0 ? TEXT("A_Quartz") : TEXT("A_Violet");
		MarkerB->SectorId = TEXT("SectorB");
		MarkerB->MarkerId = Index == 0 ? TEXT("B_Amber") : TEXT("B_Cedar");
		MakeExternalSpatial(MarkerA);
		MakeExternalSpatial(MarkerB);
		MarkersA.Add(MarkerA);
		MarkersB.Add(MarkerB);
	}
	if (!EditorLayers->AddActorsToDataLayer(MarkersA, InstanceA)
		|| !EditorLayers->AddActorsToDataLayer(MarkersB, InstanceB))
	{
		return Fail(TEXT("MARKER_DATA_LAYERS"), GetPathNameSafe(World));
	}

	ANearActiveSectorFunctionalTestBase* FixtureA = nullptr;
	ANearActiveSectorFunctionalTestBase* FixtureB = nullptr;
	if (bAdmission)
	{
		FixtureA = Spawn<ANearActiveSectorAdmissionFunctionalTestA>(World,
			FVector(0.0, -9000.0, 150.0), TEXT("NearActiveSectorAdmissionA"));
		FixtureB = Spawn<ANearActiveSectorAdmissionFunctionalTestB>(World,
			FVector(0.0, -8500.0, 150.0), TEXT("NearActiveSectorAdmissionB"));
	}
	else
	{
		FixtureA = Spawn<ANearActiveSectorFunctionalTestA>(World,
			FVector(0.0, -9000.0, 150.0), TEXT("NearActiveSectorFunctionalTestA"));
		FixtureB = Spawn<ANearActiveSectorFunctionalTestB>(World,
			FVector(0.0, -8500.0, 150.0), TEXT("NearActiveSectorFunctionalTestB"));
	}
	if (!SetFixtureFacts(FixtureA, LayerA, LayerB, LocationA, LocationB, Radius)
		|| !SetFixtureFacts(FixtureB, LayerA, LayerB, LocationA, LocationB, Radius))
	{
		return Fail(TEXT("FIXTURE_FACTS"), GetPathNameSafe(World));
	}
	Spawn<APlayerStart>(World, FVector(0.0, -7500.0, 150.0), TEXT("PlayerStart"));
	UClass* StockMode = LoadClass<AGameModeBase>(nullptr,
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
			 "BP_ThirdPersonGameMode_C"));
	if (World->GetWorldSettings() == nullptr || StockMode == nullptr)
	{
		return Fail(TEXT("GAME_MODE"), GetPathNameSafe(World));
	}
	World->GetWorldSettings()->DefaultGameMode = StockMode;

	// Newly externalized actors assigned to an initially-unloaded runtime Data
	// Layer can leave live editor iteration before the unsaved World Partition
	// descriptor container has registered their descriptors.  Exact descriptor
	// cardinality is therefore checked by InspectMap only after the caller saves
	// the level, and again from a fresh process.  Every staging operation above
	// remains fail-closed here.
	const FString Inspection = FString::Printf(
		TEXT("PASS MAP mode=%s world_partition=1 ofpa=1 source=1 shape_radius=3200 "
			 "layers=2 markers=4 spatial=4 locations=far controller=1 request=1 fixtures=2"),
		bAdmission ? TEXT("admission") : TEXT("final"));
	UE_LOG(LogNearActiveSectorAuthoring, Display,
		TEXT("NEAR-ACTIVE-SECTOR-MAP-CONFIGURED %s"), *Inspection);
	return Inspection;
}

FString UNearActiveSectorAssetAuthoring::InspectMap(
	UWorld* World, const bool bAdmission)
{
	if (World == nullptr || World->GetWorldPartition() == nullptr
		|| World->PersistentLevel == nullptr
		|| !World->PersistentLevel->IsUsingExternalActors())
	{
		return Fail(TEXT("MAP_WORLD_PARTITION"), GetPathNameSafe(World));
	}
	int32 Sources = 0;
	int32 Requests = 0;
	int32 Controllers = 0;
	int32 FixturesA = 0;
	int32 FixturesB = 0;
	bool bSourceShape = false;
	bool bFixtureFacts = true;
	const FVector ExpectedA(-120000.0, 0.0, 250.0);
	const FVector ExpectedB(120000.0, 1500.0, 250.0);
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (const ANearActiveSectorStreamingSource* ExactSource =
			Cast<ANearActiveSectorStreamingSource>(Actor))
		{
			++Sources;
			bSourceShape = ExactSource->StreamingSource != nullptr
				&& ExactSource->StreamingSource->IsStreamingSourceEnabled()
				&& ExactSource->StreamingSource->Shapes.Num() == 1
				&& !ExactSource->StreamingSource->Shapes[0].bUseGridLoadingRange
				&& FMath::IsNearlyEqual(
					ExactSource->StreamingSource->Shapes[0].Radius, 3200.0f);
		}
		Requests += Actor->IsA<ANearActiveSectorRequest>() ? 1 : 0;
		Controllers += Actor->IsA<ANearActiveSectorControllerBase>() ? 1 : 0;
		FixturesA += Actor->IsA(bAdmission
			? ANearActiveSectorAdmissionFunctionalTestA::StaticClass()
			: ANearActiveSectorFunctionalTestA::StaticClass()) ? 1 : 0;
		FixturesB += Actor->IsA(bAdmission
			? ANearActiveSectorAdmissionFunctionalTestB::StaticClass()
			: ANearActiveSectorFunctionalTestB::StaticClass()) ? 1 : 0;
		if (const ANearActiveSectorFunctionalTestBase* Fixture =
			Cast<ANearActiveSectorFunctionalTestBase>(Actor))
		{
			bFixtureFacts = bFixtureFacts
				&& Fixture->SectorALocation.Equals(ExpectedA, 0.1)
				&& Fixture->SectorBLocation.Equals(ExpectedB, 0.1)
				&& FMath::IsNearlyEqual(Fixture->ExpectedSourceRadius, 3200.0f);
		}
	}
	int32 MarkerDescriptors = 0;
	int32 SpatialMarkerDescriptors = 0;
	int32 NearA = 0;
	int32 NearB = 0;
	UActorDescContainerInstance* DescContainer =
		World->GetWorldPartition()->GetActorDescContainerInstance();
	if (DescContainer != nullptr)
	{
		for (FActorDescInstanceList::TConstIterator<ANearActiveSectorMarker>
			It(DescContainer); It; ++It)
		{
			const FWorldPartitionActorDescInstance* Desc = *It;
			++MarkerDescriptors;
			SpatialMarkerDescriptors += Desc->GetIsSpatiallyLoaded() ? 1 : 0;
			const FVector Location = Desc->GetActorTransform().GetLocation();
			NearA += FVector::Dist2D(Location, ExpectedA) < 500.0 ? 1 : 0;
			NearB += FVector::Dist2D(Location, ExpectedB) < 500.0 ? 1 : 0;
		}
	}
	const bool bMarkerLocations = NearA == 2 && NearB == 2;
	UDataLayerAsset* LayerA = LoadObject<UDataLayerAsset>(nullptr,
		*LayerPath(bAdmission, TEXT("DL_SectorA")));
	UDataLayerAsset* LayerB = LoadObject<UDataLayerAsset>(nullptr,
		*LayerPath(bAdmission, TEXT("DL_SectorB")));
	UDataLayerManager* Manager = UDataLayerManager::GetDataLayerManager(World);
	const bool bLayers = LayerA != nullptr && LayerB != nullptr
		&& LayerA->IsRuntime() && LayerB->IsRuntime() && Manager != nullptr
		&& Manager->GetDataLayerInstanceFromAsset(LayerA) != nullptr
		&& Manager->GetDataLayerInstanceFromAsset(LayerB) != nullptr;
	if (Sources != 1 || Requests != 1 || Controllers != 1
		|| MarkerDescriptors != 4 || SpatialMarkerDescriptors != 4
		|| FixturesA != 1 || FixturesB != 1
		|| !bSourceShape || !bLayers || !bMarkerLocations || !bFixtureFacts)
	{
		return Fail(TEXT("MAP_CARDINALITY"), FString::Printf(
			TEXT("source=%d request=%d controller=%d markers=%d fixtures=%d/%d "
				 "spatial=%d shape=%d layers=%d locations=%d facts=%d"),
			Sources, Requests, Controllers, MarkerDescriptors, FixturesA, FixturesB,
			SpatialMarkerDescriptors, bSourceShape ? 1 : 0, bLayers ? 1 : 0,
			bMarkerLocations ? 1 : 0, bFixtureFacts ? 1 : 0));
	}
	return FString::Printf(
		TEXT("PASS MAP mode=%s world_partition=1 ofpa=1 source=1 shape_radius=3200 "
			 "layers=2 markers=4 spatial=4 locations=far controller=1 request=1 fixtures=2"),
		bAdmission ? TEXT("admission") : TEXT("final"));
}

FString UNearActiveSectorAssetAuthoring::InspectController(
	const bool bReferenceExpected)
{
	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr,
		*(FinalControllerPackage + TEXT(".") + ControllerName.ToString()));
	if (Blueprint == nullptr
		|| Blueprint->ParentClass != ANearActiveSectorControllerBase::StaticClass()
		|| Blueprint->GeneratedClass == nullptr)
	{
		return Fail(TEXT("CONTROLLER_IDENTITY"), GetPathNameSafe(Blueprint));
	}
	TArray<UEdGraph*> Graphs;
	Blueprint->GetAllGraphs(Graphs);
	int32 Nodes = 0;
	int32 Links = 0;
	int32 ApplyEvents = 0;
	int32 ManagerCalls = 0;
	int32 LayerCalls = 0;
	int32 MoveCalls = 0;
	int32 ArrayGets = 0;
	TSet<FName> RequestReads;
	for (const UEdGraph* Graph : Graphs)
	{
		Nodes += Graph ? Graph->Nodes.Num() : 0;
		if (Graph != nullptr)
		{
			for (const UEdGraphNode* Node : Graph->Nodes)
			{
				if (const UK2Node_Event* Event = Cast<UK2Node_Event>(Node))
				{
					ApplyEvents += Event->EventReference.GetMemberName()
						== TEXT("ApplySectorRequest") ? 1 : 0;
				}
				if (const UK2Node_CallFunction* Call =
					Cast<UK2Node_CallFunction>(Node))
				{
					const FName Function = Call->FunctionReference.GetMemberName();
					ManagerCalls += Function == TEXT("GetSectorDataLayerManager") ? 1 : 0;
					LayerCalls += Function == TEXT("SetDataLayerRuntimeState") ? 1 : 0;
					MoveCalls += Function == TEXT("K2_SetActorLocation") ? 1 : 0;
				}
				ArrayGets += Node->IsA<UK2Node_GetArrayItem>() ? 1 : 0;
				if (const UK2Node_VariableGet* Get = Cast<UK2Node_VariableGet>(Node))
				{
					const FName Variable = Get->VariableReference.GetMemberName();
					if (Variable == TEXT("CandidateLayers")
						|| Variable == TEXT("SelectedLayer")
						|| Variable == TEXT("StreamingSourceActor")
						|| Variable == TEXT("SelectedDestination"))
					{
						RequestReads.Add(Variable);
					}
				}
				for (const UEdGraphPin* Pin : Node->Pins)
				{
					Links += Pin ? Pin->LinkedTo.Num() : 0;
				}
			}
		}
	}
	const bool bExactReference = ApplyEvents == 1 && ManagerCalls == 1
		&& LayerCalls == 3 && MoveCalls == 1 && ArrayGets == 2
		&& RequestReads.Num() == 4 && Links >= 30;
	const bool bExactBaseline = ApplyEvents == 0 && ManagerCalls == 0
		&& LayerCalls == 0 && MoveCalls == 0 && ArrayGets == 0
		&& RequestReads.IsEmpty() && Links == 0;
	if ((bReferenceExpected && !bExactReference)
		|| (!bReferenceExpected && !bExactBaseline))
	{
		return Fail(TEXT("CONTROLLER_GRAPH"), FString::Printf(
			TEXT("expected=%d nodes=%d links=%d event=%d manager=%d layers=%d "
				 "move=%d array_get=%d reads=%d"), bReferenceExpected ? 1 : 0,
			Nodes, Links, ApplyEvents, ManagerCalls, LayerCalls, MoveCalls,
			ArrayGets, RequestReads.Num()));
	}
	return FString::Printf(
		TEXT("PASS CONTROLLER reference=%d nodes=%d links=%d event=%d manager=%d "
			 "layers=%d array_get=%d move=%d request_reads=%d"),
		bReferenceExpected ? 1 : 0, Nodes, Links, ApplyEvents, ManagerCalls,
		LayerCalls, ArrayGets, MoveCalls, RequestReads.Num());
}
