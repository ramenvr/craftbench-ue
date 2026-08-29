// Copyright CraftBench. All Rights Reserved.

#include "ReplicatedDoorAssetAuthoring.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "K2Node_CallFunction.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Tasks/t3-every-player-sees-the-same-door-state/ReplicatedDoorTypes.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogReplicatedDoorAuthoring, Log, All);

namespace
{
	constexpr TCHAR TaskId[] = TEXT("t3-every-player-sees-the-same-door-state");
	constexpr TCHAR FinalPackage[] =
		TEXT("/Game/Tasks/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState");
	constexpr TCHAR FinalObject[] =
		TEXT("/Game/Tasks/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState.BP_ReplicatedDoorState");
	constexpr TCHAR FinalClass[] =
		TEXT("/Game/Tasks/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState.BP_ReplicatedDoorState_C");
	constexpr TCHAR AdmissionPackage[] =
		TEXT("/Game/__CraftBenchAdmission/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState_Admission");
	constexpr TCHAR AdmissionObject[] =
		TEXT("/Game/__CraftBenchAdmission/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState_Admission.BP_ReplicatedDoorState_Admission");
	constexpr TCHAR AdmissionClass[] =
		TEXT("/Game/__CraftBenchAdmission/t3-every-player-sees-the-same-door-state/BP_ReplicatedDoorState_Admission.BP_ReplicatedDoorState_Admission_C");
	constexpr TCHAR FinalMap[] =
		TEXT("/Game/Maps/t3-every-player-sees-the-same-door-state/L_ReplicatedDoorState");
	constexpr TCHAR AdmissionMap[] =
		TEXT("/Game/__CraftBenchAdmission/t3-every-player-sees-the-same-door-state/L_ReplicatedDoorStateAdmission");
	constexpr TCHAR StockGameMode[] =
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C");
	const FName FinalName(TEXT("BP_ReplicatedDoorState"));
	const FName AdmissionName(TEXT("BP_ReplicatedDoorState_Admission"));
	const FName DoorRevisionName(TEXT("DoorRevision"));
	const FName RequestToggleName(TEXT("RequestToggle"));
	const FName OnRepName(TEXT("OnRep_DoorRevision"));
	const FName AddIntName(TEXT("Add_IntInt"));
	const FName ApplyRevisionName(TEXT("ApplyReplicatedRevision"));

	FString Fail(const TCHAR* Gate, const FString& Detail)
	{
		const FString Result = FString::Printf(
			TEXT("FAIL %s %s"), Gate, *Detail);
		UE_LOG(LogReplicatedDoorAuthoring, Error,
			TEXT("REPLICATED-DOOR-AUTHORING %s"), *Result);
		return Result;
	}

	bool SaveBlueprint(UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr || Blueprint->GetPackage() == nullptr)
		{
			return false;
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
		if (Blueprint->Status != BS_UpToDate || Blueprint->GeneratedClass == nullptr)
		{
			return false;
		}
		UPackage* Package = Blueprint->GetPackage();
		Package->MarkPackageDirty();
		const FString Filename = FPackageName::LongPackageNameToFilename(
			Package->GetName(), FPackageName::GetAssetPackageExtension());
		FSavePackageArgs Args;
		Args.TopLevelFlags = RF_Public | RF_Standalone;
		Args.SaveFlags = SAVE_NoError;
		return UPackage::SavePackage(Package, Blueprint, *Filename, Args);
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

	UK2Node_CustomEvent* AddCustomEvent(
		UEdGraph* Graph, const uint32 FunctionFlags)
	{
		UK2Node_CustomEvent* Node = Graph != nullptr
			? NewObject<UK2Node_CustomEvent>(Graph) : nullptr;
		if (Node == nullptr)
		{
			return nullptr;
		}
		Node->CustomFunctionName = RequestToggleName;
		Node->FunctionFlags = FunctionFlags;
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = -700;
		Node->NodePosY = 0;
		return Node;
	}

	UK2Node_CallFunction* AddCall(
		UEdGraph* Graph, UClass* Owner, const FName Function,
		const int32 X, const int32 Y)
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

	UK2Node_VariableGet* AddGet(UEdGraph* Graph, const int32 X, const int32 Y)
	{
		UK2Node_VariableGet* Node = AddNode<UK2Node_VariableGet>(Graph, X, Y);
		if (Node != nullptr)
		{
			Node->VariableReference.SetSelfMember(DoorRevisionName);
			Node->ReconstructNode();
		}
		return Node;
	}

	UK2Node_VariableSet* AddSet(UEdGraph* Graph, const int32 X, const int32 Y)
	{
		UK2Node_VariableSet* Node = AddNode<UK2Node_VariableSet>(Graph, X, Y);
		if (Node != nullptr)
		{
			Node->VariableReference.SetSelfMember(DoorRevisionName);
			Node->ReconstructNode();
		}
		return Node;
	}

	UEdGraphPin* Pin(
		const UEdGraphNode* Node, const FName Name,
		const EEdGraphPinDirection Direction)
	{
		return Node != nullptr
			? const_cast<UEdGraphNode*>(Node)->FindPin(Name, Direction)
			: nullptr;
	}

	bool Connect(
		const UEdGraphSchema_K2* Schema, UEdGraphPin* Output, UEdGraphPin* Input)
	{
		return Schema != nullptr && Output != nullptr && Input != nullptr
			&& (Output->LinkedTo.Contains(Input)
				|| Schema->TryCreateConnection(Output, Input));
	}

	bool OnlyLink(const UEdGraphPin* A, const UEdGraphPin* B)
	{
		return A != nullptr && B != nullptr && A->LinkedTo.Num() == 1
			&& B->LinkedTo.Num() == 1 && A->LinkedTo[0] == B
			&& B->LinkedTo[0] == A;
	}

	UEdGraph* ResetEventGraph(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = Blueprint != nullptr
			? FBlueprintEditorUtils::FindEventGraph(Blueprint) : nullptr;
		if (Graph == nullptr && Blueprint != nullptr
			&& !Blueprint->UbergraphPages.IsEmpty())
		{
			Graph = Blueprint->UbergraphPages[0];
		}
		if (Graph != nullptr)
		{
			for (UEdGraphNode* Node : TArray<UEdGraphNode*>(Graph->Nodes))
			{
				Graph->RemoveNode(Node);
			}
		}
		return Graph;
	}

	bool AddRepNotifyGraph(UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		for (const UEdGraph* Existing : Blueprint->FunctionGraphs)
		{
			if (Existing != nullptr && Existing->GetFName() == OnRepName)
			{
				return false;
			}
		}
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(
			Blueprint, OnRepName, UEdGraph::StaticClass(),
			UEdGraphSchema_K2::StaticClass());
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(
			Blueprint, Graph, true, nullptr);
		UK2Node_FunctionEntry* Entry = nullptr;
		UK2Node_FunctionResult* Result = nullptr;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			Entry = Entry != nullptr ? Entry : Cast<UK2Node_FunctionEntry>(Node);
			Result = Result != nullptr ? Result : Cast<UK2Node_FunctionResult>(Node);
		}
		UK2Node_CallFunction* Apply = AddCall(
			Graph, AReplicatedDoorStateBase::StaticClass(),
			ApplyRevisionName, 260, 0);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		if (Entry == nullptr || Apply == nullptr || Schema == nullptr
			|| !Connect(Schema,
				Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Apply, UEdGraphSchema_K2::PN_Execute, EGPD_Input)))
		{
			return false;
		}
		return Result == nullptr || Connect(Schema,
			Pin(Apply, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Result, UEdGraphSchema_K2::PN_Execute, EGPD_Input));
	}

	bool BuildSolvedGraph(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = ResetEventGraph(Blueprint);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		const uint32 RpcFlags = FUNC_BlueprintCallable | FUNC_BlueprintEvent
			| FUNC_Public | FUNC_Net | FUNC_NetServer | FUNC_NetReliable;
		UK2Node_CustomEvent* Request = AddCustomEvent(Graph, RpcFlags);
		UK2Node_VariableGet* GetRevision = AddGet(Graph, -460, 230);
		UK2Node_CallFunction* Add = AddCall(
			Graph, UKismetMathLibrary::StaticClass(), AddIntName, -160, 220);
		UK2Node_VariableSet* SetRevision = AddSet(Graph, 140, 0);
		UK2Node_CallFunction* Apply = AddCall(
			Graph, AReplicatedDoorStateBase::StaticClass(),
			ApplyRevisionName, 470, 0);
		UEdGraphPin* Increment = Pin(Add, TEXT("B"), EGPD_Input);
		if (Increment != nullptr)
		{
			Schema->TrySetDefaultValue(*Increment, TEXT("1"));
		}
		uint64* Flags = FBlueprintEditorUtils::GetBlueprintVariablePropertyFlags(
			Blueprint, DoorRevisionName);
		if (Graph == nullptr || Schema == nullptr || Request == nullptr
			|| GetRevision == nullptr || Add == nullptr || SetRevision == nullptr
			|| Apply == nullptr || Increment == nullptr || Flags == nullptr
			|| !Connect(Schema,
				Pin(Request, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(SetRevision, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			|| !Connect(Schema,
				Pin(SetRevision, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Apply, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			|| !Connect(Schema, Pin(GetRevision, DoorRevisionName, EGPD_Output),
				Pin(Add, TEXT("A"), EGPD_Input))
			|| !Connect(Schema,
				Pin(Add, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(SetRevision, DoorRevisionName, EGPD_Input)))
		{
			return false;
		}
		*Flags |= CPF_Net | CPF_RepNotify;
		FBlueprintEditorUtils::SetBlueprintVariableRepNotifyFunc(
			Blueprint, DoorRevisionName, OnRepName);
		return AddRepNotifyGraph(Blueprint);
	}

	UBlueprint* CreateBlueprint(const bool bAdmission, const bool bSolved)
	{
		const TCHAR* PackageName = bAdmission ? AdmissionPackage : FinalPackage;
		const FName AssetName = bAdmission ? AdmissionName : FinalName;
		if (FPackageName::DoesPackageExist(PackageName)
			|| FindPackage(nullptr, PackageName) != nullptr)
		{
			return nullptr;
		}
		UPackage* Package = CreatePackage(PackageName);
		UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(
			AReplicatedDoorStateBase::StaticClass(), Package, AssetName,
			BPTYPE_Normal, UBlueprint::StaticClass(),
			UBlueprintGeneratedClass::StaticClass(),
			TEXT("ReplicatedDoorAuthoring"));
		if (Blueprint == nullptr)
		{
			return nullptr;
		}
		FAssetRegistryModule::AssetCreated(Blueprint);
		FEdGraphPinType IntType;
		IntType.PinCategory = UEdGraphSchema_K2::PC_Int;
		if (!FBlueprintEditorUtils::AddMemberVariable(
			Blueprint, DoorRevisionName, IntType, TEXT("0")))
		{
			return nullptr;
		}
		UEdGraph* Graph = ResetEventGraph(Blueprint);
		const uint32 LocalFlags = FUNC_BlueprintCallable | FUNC_BlueprintEvent
			| FUNC_Public;
		if (AddCustomEvent(Graph, LocalFlags) == nullptr)
		{
			return nullptr;
		}
		if (bSolved && !BuildSolvedGraph(Blueprint))
		{
			return nullptr;
		}
		return SaveBlueprint(Blueprint) ? Blueprint : nullptr;
	}

	struct FDoorGraphFacts
	{
		UK2Node_CustomEvent* Request = nullptr;
		UK2Node_VariableGet* GetRevision = nullptr;
		UK2Node_CallFunction* Add = nullptr;
		UK2Node_VariableSet* SetRevision = nullptr;
		UK2Node_CallFunction* Apply = nullptr;
		int32 NodeCount = 0;
	};

	FDoorGraphFacts ReadEventFacts(UBlueprint* Blueprint)
	{
		FDoorGraphFacts Facts;
		UEdGraph* Graph = Blueprint != nullptr
			? FBlueprintEditorUtils::FindEventGraph(Blueprint) : nullptr;
		if (Graph == nullptr && Blueprint != nullptr
			&& !Blueprint->UbergraphPages.IsEmpty())
		{
			Graph = Blueprint->UbergraphPages[0];
		}
		Facts.NodeCount = Graph != nullptr ? Graph->Nodes.Num() : -1;
		for (UEdGraphNode* Node : Graph != nullptr
			? Graph->Nodes : TArray<TObjectPtr<UEdGraphNode>>())
		{
			if (UK2Node_CustomEvent* Event = Cast<UK2Node_CustomEvent>(Node))
			{
				if (Event->CustomFunctionName == RequestToggleName)
				{
					Facts.Request = Facts.Request == nullptr ? Event : nullptr;
				}
			}
			else if (UK2Node_VariableGet* Get = Cast<UK2Node_VariableGet>(Node))
			{
				if (Get->VariableReference.GetMemberName() == DoorRevisionName)
				{
					Facts.GetRevision = Get;
				}
			}
			else if (UK2Node_VariableSet* Set = Cast<UK2Node_VariableSet>(Node))
			{
				if (Set->VariableReference.GetMemberName() == DoorRevisionName)
				{
					Facts.SetRevision = Set;
				}
			}
			else if (UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
			{
				const FName Function = Call->FunctionReference.GetMemberName();
				if (Function == AddIntName)
				{
					Facts.Add = Call;
				}
				else if (Function == ApplyRevisionName)
				{
					Facts.Apply = Call;
				}
			}
		}
		return Facts;
	}

	bool ExactRepNotifyGraph(const UBlueprint* Blueprint)
	{
		const UEdGraph* Found = nullptr;
		for (const UEdGraph* Graph : Blueprint != nullptr
			? Blueprint->FunctionGraphs : TArray<TObjectPtr<UEdGraph>>())
		{
			if (Graph != nullptr && Graph->GetFName() == OnRepName)
			{
				if (Found != nullptr)
				{
					return false;
				}
				Found = Graph;
			}
		}
		if (Found == nullptr)
		{
			return false;
		}
		const UK2Node_FunctionEntry* Entry = nullptr;
		const UK2Node_FunctionResult* Result = nullptr;
		const UK2Node_CallFunction* Apply = nullptr;
		for (const UEdGraphNode* Node : Found->Nodes)
		{
			if (const UK2Node_FunctionEntry* EntryNode =
				Cast<UK2Node_FunctionEntry>(Node))
			{
				Entry = Entry == nullptr ? EntryNode : nullptr;
			}
			else if (const UK2Node_FunctionResult* ResultNode =
				Cast<UK2Node_FunctionResult>(Node))
			{
				Result = Result == nullptr ? ResultNode : nullptr;
			}
			else if (const UK2Node_CallFunction* Call =
				Cast<UK2Node_CallFunction>(Node))
			{
				if (Call->FunctionReference.GetMemberName() == ApplyRevisionName)
				{
					Apply = Apply == nullptr ? Call : nullptr;
				}
				else
				{
					return false;
				}
			}
			else
			{
				return false;
			}
		}
		return Entry != nullptr && Apply != nullptr
			&& OnlyLink(Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Apply, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			&& (Result == nullptr || OnlyLink(
				Pin(Apply, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Result, UEdGraphSchema_K2::PN_Execute, EGPD_Input)));
	}

	FString InspectBlueprintInternal(
		const bool bAdmission, const bool bExpectSolved)
	{
		const TCHAR* ObjectPath = bAdmission ? AdmissionObject : FinalObject;
		const TCHAR* ClassPath = bAdmission ? AdmissionClass : FinalClass;
		UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, ObjectPath);
		UClass* Generated = LoadClass<AReplicatedDoorStateBase>(nullptr, ClassPath);
		if (Blueprint == nullptr || Generated == nullptr
			|| Blueprint->GeneratedClass != Generated
			|| Blueprint->ParentClass != AReplicatedDoorStateBase::StaticClass()
			|| Generated->GetSuperClass() != AReplicatedDoorStateBase::StaticClass()
			|| Blueprint->Status != BS_UpToDate)
		{
			return Fail(TEXT("BLUEPRINT_IDENTITY"), ObjectPath);
		}
		FIntProperty* Revision = FindFProperty<FIntProperty>(
			Generated, DoorRevisionName);
		const FName RepNotify = FBlueprintEditorUtils::GetBlueprintVariableRepNotifyFunc(
			Blueprint, DoorRevisionName);
		const FDoorGraphFacts Facts = ReadEventFacts(Blueprint);
		UFunction* Request = Generated->FindFunctionByName(RequestToggleName);
		UFunction* OnRep = Generated->FindFunctionByName(OnRepName);
		AReplicatedDoorStateBase* CDO = Cast<AReplicatedDoorStateBase>(
			Generated->GetDefaultObject());
		if (Revision == nullptr || CDO == nullptr
			|| Revision->GetPropertyValue_InContainer(CDO) != 0
			|| Facts.Request == nullptr || Request == nullptr)
		{
			return Fail(TEXT("BLUEPRINT_SURFACE"), ObjectPath);
		}

		const bool bPropertySolved = Revision->HasAllPropertyFlags(
			CPF_Net | CPF_RepNotify) && RepNotify == OnRepName;
		const bool bRpcSolved = Request->HasAllFunctionFlags(
			FUNC_Net | FUNC_NetServer | FUNC_NetReliable)
			&& !Request->HasAnyFunctionFlags(FUNC_NetClient | FUNC_NetMulticast)
			&& (Facts.Request->FunctionFlags
				& (FUNC_Net | FUNC_NetServer | FUNC_NetReliable))
				== (FUNC_Net | FUNC_NetServer | FUNC_NetReliable);
		if (!bExpectSolved)
		{
			const bool bBaseline = Facts.NodeCount == 1
				&& !Revision->HasAnyPropertyFlags(CPF_Net | CPF_RepNotify)
				&& RepNotify.IsNone() && OnRep == nullptr
				&& !Request->HasAnyFunctionFlags(FUNC_NetFuncFlags)
				&& Facts.Request->Pins.ContainsByPredicate([](const UEdGraphPin* Value)
				{
					return Value != nullptr
						&& Value->PinName == UEdGraphSchema_K2::PN_Then
						&& Value->LinkedTo.IsEmpty();
				});
			if (!bBaseline)
			{
				return Fail(TEXT("BASELINE_NOT_EMPTY"), ObjectPath);
			}
			return FString::Printf(TEXT(
				"PASS DOOR_BLUEPRINT mode=%s solved=0 parent=direct variable=1 "
				"rpc=0 repnotify=0 nodes=1"),
				bAdmission ? TEXT("admission") : TEXT("final"));
		}

		const bool bGraphSolved = Facts.NodeCount == 5
			&& Facts.GetRevision != nullptr && Facts.Add != nullptr
			&& Facts.SetRevision != nullptr && Facts.Apply != nullptr
			&& OnlyLink(Pin(Facts.Request, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Facts.SetRevision, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			&& OnlyLink(Pin(Facts.SetRevision, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Facts.Apply, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			&& OnlyLink(Pin(Facts.GetRevision, DoorRevisionName, EGPD_Output),
				Pin(Facts.Add, TEXT("A"), EGPD_Input))
			&& OnlyLink(Pin(Facts.Add, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(Facts.SetRevision, DoorRevisionName, EGPD_Input));
		if (!bPropertySolved || !bRpcSolved || !bGraphSolved
			|| OnRep == nullptr || !ExactRepNotifyGraph(Blueprint))
		{
			return Fail(TEXT("SOLVED_GRAPH"), FString::Printf(
				TEXT("property=%d rpc=%d graph=%d onrep=%d"),
				bPropertySolved ? 1 : 0, bRpcSolved ? 1 : 0,
				bGraphSolved ? 1 : 0, OnRep != nullptr ? 1 : 0));
		}
		return FString::Printf(TEXT(
			"PASS DOOR_BLUEPRINT mode=%s solved=1 parent=direct variable=1 "
			"rpc=server_reliable repnotify=1 nodes=5 onrep_graph=1"),
			bAdmission ? TEXT("admission") : TEXT("final"));
	}
}

FString UReplicatedDoorAssetAuthoring::CreateBaselineDoorBlueprint()
{
	UBlueprint* Blueprint = CreateBlueprint(false, false);
	if (Blueprint == nullptr)
	{
		return Fail(TEXT("BASELINE_CREATE"), FinalPackage);
	}
	const FString Result = InspectBlueprintInternal(false, false);
	UE_LOG(LogReplicatedDoorAuthoring, Display,
		TEXT("REPLICATED-DOOR-BASELINE-SAVED %s"), *Result);
	return Result;
}

FString UReplicatedDoorAssetAuthoring::CreateAdmissionDoorBlueprint()
{
	UBlueprint* Blueprint = CreateBlueprint(true, true);
	if (Blueprint == nullptr)
	{
		return Fail(TEXT("ADMISSION_CREATE"), AdmissionPackage);
	}
	const FString Result = InspectBlueprintInternal(true, true);
	UE_LOG(LogReplicatedDoorAuthoring, Display,
		TEXT("REPLICATED-DOOR-ADMISSION-SAVED %s"), *Result);
	return Result;
}

FString UReplicatedDoorAssetAuthoring::BuildReferenceDoorGraph()
{
	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, FinalObject);
	if (Blueprint == nullptr
		|| !InspectBlueprintInternal(false, false).StartsWith(TEXT("PASS "))
		|| !BuildSolvedGraph(Blueprint) || !SaveBlueprint(Blueprint))
	{
		return Fail(TEXT("REFERENCE_BUILD"), FinalObject);
	}
	const FString Result = InspectBlueprintInternal(false, true);
	UE_LOG(LogReplicatedDoorAuthoring, Display,
		TEXT("REPLICATED-DOOR-REFERENCE-SAVED %s"), *Result);
	return Result;
}

FString UReplicatedDoorAssetAuthoring::InspectDoorBlueprint(
	const bool bAdmission, const bool bExpectSolved)
{
	const FString Result = InspectBlueprintInternal(bAdmission, bExpectSolved);
	if (Result.StartsWith(TEXT("PASS ")))
	{
		UE_LOG(LogReplicatedDoorAuthoring, Display,
			TEXT("REPLICATED-DOOR-BLUEPRINT-READBACK %s"), *Result);
	}
	else
	{
		UE_LOG(LogReplicatedDoorAuthoring, Error,
			TEXT("REPLICATED-DOOR-BLUEPRINT-READBACK %s"), *Result);
	}
	return Result;
}

FString UReplicatedDoorAssetAuthoring::InspectDoorMap(
	UWorld* World, const bool bAdmission)
{
	const TCHAR* ExpectedMap = bAdmission ? AdmissionMap : FinalMap;
	const TCHAR* ExpectedClassPath = bAdmission ? AdmissionClass : FinalClass;
	if (World == nullptr || World->GetPackage()->GetName() != ExpectedMap)
	{
		return Fail(TEXT("MAP_IDENTITY"), GetPathNameSafe(World));
	}
	UClass* ExpectedDoorClass = LoadClass<AReplicatedDoorStateBase>(
		nullptr, ExpectedClassPath);
	UClass* ExpectedGameMode = LoadClass<AGameModeBase>(nullptr, StockGameMode);
	AReplicatedDoorStateBase* Door = nullptr;
	AReplicatedDoorNetworkFunctionalTest* Fixture = nullptr;
	int32 DoorCount = 0;
	int32 FixtureCount = 0;
	int32 PlayerStartCount = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (AReplicatedDoorStateBase* Candidate =
			Cast<AReplicatedDoorStateBase>(*It))
		{
			++DoorCount;
			Door = Candidate;
		}
		if (AReplicatedDoorNetworkFunctionalTest* Candidate =
			Cast<AReplicatedDoorNetworkFunctionalTest>(*It))
		{
			++FixtureCount;
			Fixture = Candidate;
		}
		if (Cast<APlayerStart>(*It) != nullptr)
		{
			++PlayerStartCount;
		}
	}
	AWorldSettings* Settings = World->GetWorldSettings();
	if (ExpectedDoorClass == nullptr || ExpectedGameMode == nullptr
		|| DoorCount != 1 || FixtureCount != 1 || PlayerStartCount != 1
		|| Door == nullptr || Door->GetClass() != ExpectedDoorClass
		|| Fixture == nullptr || Fixture->Door != Door
		|| Door->GetDoorRevision() != 0 || !Door->HasFiniteDoorTransform()
		|| !Door->IsAtClosedTransform() || Door->IsAtOpenTransform()
		|| Settings == nullptr || Settings->DefaultGameMode != ExpectedGameMode)
	{
		return Fail(TEXT("MAP_CONTRACT"), FString::Printf(
			TEXT("doors=%d fixtures=%d starts=%d door=%s expected=%s bound=%d "
				"revision=%d closed=%d game_mode=%s"), DoorCount, FixtureCount,
			PlayerStartCount, *GetPathNameSafe(Door != nullptr ? Door->GetClass() : nullptr),
			*GetPathNameSafe(ExpectedDoorClass), Fixture != nullptr && Fixture->Door == Door,
			Door != nullptr ? Door->GetDoorRevision() : INDEX_NONE,
			Door != nullptr && Door->IsAtClosedTransform() ? 1 : 0,
			*GetPathNameSafe(Settings != nullptr ? Settings->DefaultGameMode.Get() : nullptr)));
	}
	const FString Result = FString::Printf(TEXT(
		"PASS DOOR_MAP mode=%s map_exact=1 doors=1 fixtures=1 player_starts=1 "
		"game_mode_exact=1 playable=1 fixture_bound=1 revision=0 closed=1"),
		bAdmission ? TEXT("admission") : TEXT("final"));
	UE_LOG(LogReplicatedDoorAuthoring, Display,
		TEXT("REPLICATED-DOOR-MAP-READBACK %s"), *Result);
	return Result;
}
