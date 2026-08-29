// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/DistrictStreamingReferenceAuthoring.h"

#include "Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/DistrictStreamingRuntime.h"

#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/LevelStreaming.h"
#include "Engine/LevelStreamingDynamic.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

#include <initializer_list>

DEFINE_LOG_CATEGORY_STATIC(LogDistrictReferenceAuthoring, Log, All);

namespace
{
	FString Fail(const TCHAR* Gate, const FString& Detail)
	{
		const FString Message = FString::Printf(
			TEXT("FAIL %s %s"), Gate, *Detail);
		UE_LOG(LogDistrictReferenceAuthoring, Error,
			TEXT("DISTRICT-REFERENCE-NATIVE %s"), *Message);
		return Message;
	}

	template <typename TNode>
	TNode* AddNode(UEdGraph* Graph, const int32 X, const int32 Y)
	{
		TNode* Node = Graph ? NewObject<TNode>(Graph) : nullptr;
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

	UK2Node_CallFunction* AddCall(
		UEdGraph* Graph, UClass* Owner, const FName Function, const int32 X,
		const int32 Y)
	{
		if (Owner == nullptr || Owner->FindFunctionByName(Function) == nullptr)
		{
			return nullptr;
		}
		UK2Node_CallFunction* Node = NewObject<UK2Node_CallFunction>(Graph);
		if (Node == nullptr)
		{
			return nullptr;
		}
		Node->FunctionReference.SetExternalMember(Function, Owner);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UK2Node_VariableGet* AddGet(
		UEdGraph* Graph, const FName Property, UClass* ExternalOwner,
		const int32 X, const int32 Y)
	{
		UK2Node_VariableGet* Node = NewObject<UK2Node_VariableGet>(Graph);
		if (Node == nullptr)
		{
			return nullptr;
		}
		if (ExternalOwner != nullptr)
		{
			Node->VariableReference.SetExternalMember(Property, ExternalOwner);
		}
		else
		{
			Node->VariableReference.SetSelfMember(Property);
		}
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UK2Node_VariableSet* AddSet(
		UEdGraph* Graph, const FName Property, const int32 X, const int32 Y)
	{
		UK2Node_VariableSet* Node = NewObject<UK2Node_VariableSet>(Graph);
		if (Node == nullptr)
		{
			return nullptr;
		}
		Node->VariableReference.SetSelfMember(Property);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UEdGraphPin* Pin(
		const UEdGraphNode* Node, const FName Name,
		const EEdGraphPinDirection Direction)
	{
		return Node ? const_cast<UEdGraphNode*>(Node)->FindPin(Name, Direction) : nullptr;
	}

	bool Connect(
		const UEdGraphSchema_K2* Schema, UEdGraphPin* Output, UEdGraphPin* Input)
	{
		return Schema != nullptr && Output != nullptr && Input != nullptr
			&& Schema->TryCreateConnection(Output, Input);
	}

	bool OnlyLink(const UEdGraphPin* A, const UEdGraphPin* B)
	{
		return A != nullptr && B != nullptr && A->LinkedTo.Num() == 1
			&& B->LinkedTo.Num() == 1 && A->LinkedTo[0] == B
			&& B->LinkedTo[0] == A;
	}

	bool ExactLinks(
		const UEdGraphPin* Source, std::initializer_list<const UEdGraphPin*> Targets)
	{
		if (Source == nullptr || Source->LinkedTo.Num() != static_cast<int32>(Targets.size()))
		{
			return false;
		}
		for (const UEdGraphPin* Target : Targets)
		{
			if (Target == nullptr || Target->LinkedTo.Num() != 1
				|| Target->LinkedTo[0] != Source
				|| !Source->LinkedTo.Contains(const_cast<UEdGraphPin*>(Target)))
			{
				return false;
			}
		}
		return true;
	}

	bool ExactBlueprintIdentity(const UBlueprint* Blueprint)
	{
		return Blueprint != nullptr
			&& Blueprint->ParentClass == ADistrictStreamLoaderBase::StaticClass()
			&& Blueprint->GeneratedClass != nullptr
			&& Blueprint->GeneratedClass->GetSuperClass()
				== ADistrictStreamLoaderBase::StaticClass()
			&& Blueprint->Status == BS_UpToDate;
	}

	bool SaveBlueprint(UBlueprint* Blueprint)
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
		if (Blueprint == nullptr || Blueprint->Status != BS_UpToDate)
		{
			return false;
		}
		UPackage* Package = Blueprint->GetOutermost();
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
		return UPackage::SavePackage(Package, nullptr, *Filename, Args);
	}

	template <typename TNode>
	TNode* UniqueNode(UEdGraph* Graph, TFunctionRef<bool(const TNode*)> Predicate)
	{
		TNode* Match = nullptr;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			TNode* Candidate = Cast<TNode>(Node);
			if (Candidate != nullptr && Predicate(Candidate))
			{
				if (Match != nullptr)
				{
					return nullptr;
				}
				Match = Candidate;
			}
		}
		return Match;
	}

	UK2Node_Event* UniqueEvent(UEdGraph* Graph, const FName EventName)
	{
		return UniqueNode<UK2Node_Event>(Graph,
			[EventName](const UK2Node_Event* Node)
			{
				return Node->EventReference.GetMemberName() == EventName;
			});
	}

	UK2Node_CallFunction* UniqueCall(UEdGraph* Graph, UFunction* Function)
	{
		return UniqueNode<UK2Node_CallFunction>(Graph,
			[Function](const UK2Node_CallFunction* Node)
			{
				return Node->GetTargetFunction() == Function;
			});
	}

	bool EventIdentity(const UK2Node_Event* Event, const FName Name)
	{
		UFunction* Signature = Event ? Event->FindEventSignatureFunction() : nullptr;
		return Event != nullptr && Event->EventReference.GetMemberName() == Name
			&& Event->bOverrideFunction && Event->CustomFunctionName.IsNone()
			&& !Event->bInternalEvent && Signature != nullptr
			&& Signature->GetOwnerClass() == ADistrictStreamLoaderBase::StaticClass();
	}
}

FString UDistrictStreamingReferenceAuthoring::InspectEmptyBaseline(
	UBlueprint* Blueprint)
{
	if (!ExactBlueprintIdentity(Blueprint))
	{
		return Fail(TEXT("BASELINE_IDENTITY"), FString::Printf(
			TEXT("asset=%s parent=%s generated=%s status=%d"),
			*GetPathNameSafe(Blueprint),
			*GetPathNameSafe(Blueprint ? Blueprint->ParentClass.Get() : nullptr),
			*GetPathNameSafe(Blueprint ? Blueprint->GeneratedClass : nullptr),
			Blueprint ? static_cast<int32>(Blueprint->Status) : -1));
	}
	TArray<UEdGraph*> Graphs;
	Blueprint->GetAllGraphs(Graphs);
	int32 Nodes = 0;
	int32 Links = 0;
	for (const UEdGraph* Graph : Graphs)
	{
		if (Graph == nullptr)
		{
			continue;
		}
		for (const UEdGraphNode* Node : Graph->Nodes)
		{
			++Nodes;
			if (!Node->IsA<UK2Node_Event>() && !Node->IsA<UK2Node_FunctionEntry>())
			{
				return Fail(TEXT("BASELINE_BEHAVIOR_NODE"), FString::Printf(
					TEXT("graph=%s node=%s class=%s"), *GetNameSafe(Graph),
					*GetNameSafe(Node), *Node->GetClass()->GetName()));
			}
			for (const UEdGraphPin* NodePin : Node->Pins)
			{
				Links += NodePin ? NodePin->LinkedTo.Num() : 0;
			}
		}
	}
	if (Links != 0)
	{
		return Fail(TEXT("BASELINE_LINKS"), FString::Printf(TEXT("links=%d"), Links));
	}
	const FString Result = FString::Printf(
		TEXT("PASS DISTRICT_EMPTY_BASELINE identity=1 behavior_nodes=0 "
			 "links=0 total_nodes=%d"), Nodes);
	UE_LOG(LogDistrictReferenceAuthoring, Display,
		TEXT("DISTRICT-REFERENCE-NATIVE %s"), *Result);
	return Result;
}

FString UDistrictStreamingReferenceAuthoring::InspectReferenceGraph(
	UBlueprint* Blueprint)
{
	if (!ExactBlueprintIdentity(Blueprint))
	{
		return Fail(TEXT("REFERENCE_IDENTITY"), *GetPathNameSafe(Blueprint));
	}
	UEdGraph* Graph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
	if (Graph == nullptr || Graph->Nodes.Num() != 10)
	{
		return Fail(TEXT("REFERENCE_NODE_COUNT"), FString::Printf(
			TEXT("graph=%s nodes=%d expected=10"), *GetNameSafe(Graph),
			Graph ? Graph->Nodes.Num() : -1));
	}

	UK2Node_Event* LoadEvent = UniqueEvent(Graph, TEXT("LoadRequestedDistrict"));
	UK2Node_Event* UnloadEvent = UniqueEvent(Graph, TEXT("UnloadRequestedDistrict"));
	UK2Node_CallFunction* Load = UniqueCall(Graph,
		ULevelStreamingDynamic::StaticClass()->FindFunctionByName(
			TEXT("LoadLevelInstanceBySoftObjectPtr")));
	UK2Node_CallFunction* SetVisible = UniqueCall(Graph,
		ULevelStreaming::StaticClass()->FindFunctionByName(TEXT("SetShouldBeVisible")));
	UK2Node_CallFunction* SetLoaded = UniqueCall(Graph,
		ULevelStreaming::StaticClass()->FindFunctionByName(TEXT("SetShouldBeLoaded")));
	UK2Node_CallFunction* SetRemoval = UniqueCall(Graph,
		ULevelStreaming::StaticClass()->FindFunctionByName(
			TEXT("SetIsRequestingUnloadAndRemoval")));
	UK2Node_VariableGet* Requested = UniqueNode<UK2Node_VariableGet>(Graph,
		[](const UK2Node_VariableGet* Node)
		{
			return Node->VariableReference.GetMemberName() == TEXT("RequestedDistrict")
				&& !Node->VariableReference.IsSelfContext()
				&& Node->VariableReference.GetMemberParentClass()
					== ADistrictStreamRequest::StaticClass();
		});
	UK2Node_VariableGet* Active = UniqueNode<UK2Node_VariableGet>(Graph,
		[](const UK2Node_VariableGet* Node)
		{
			return Node->VariableReference.GetMemberName()
					== TEXT("ActiveStreamingLevel")
				&& Node->VariableReference.IsSelfContext();
		});
	TArray<UK2Node_VariableSet*> ActiveSets;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		UK2Node_VariableSet* Set = Cast<UK2Node_VariableSet>(Node);
		if (Set != nullptr
			&& Set->VariableReference.GetMemberName() == TEXT("ActiveStreamingLevel")
			&& Set->VariableReference.IsSelfContext())
		{
			ActiveSets.Add(Set);
		}
	}
	if (!EventIdentity(LoadEvent, TEXT("LoadRequestedDistrict"))
		|| !EventIdentity(UnloadEvent, TEXT("UnloadRequestedDistrict"))
		|| Load == nullptr || SetVisible == nullptr || SetLoaded == nullptr
		|| SetRemoval == nullptr || Requested == nullptr || Active == nullptr
		|| ActiveSets.Num() != 2)
	{
		return Fail(TEXT("REFERENCE_EXACT_NODE_SET"), FString::Printf(
			TEXT("events=%d/%d calls=%d/%d/%d/%d request=%d active=%d sets=%d"),
			LoadEvent ? 1 : 0, UnloadEvent ? 1 : 0, Load ? 1 : 0,
			SetVisible ? 1 : 0, SetLoaded ? 1 : 0, SetRemoval ? 1 : 0,
			Requested ? 1 : 0, Active ? 1 : 0, ActiveSets.Num()));
	}

	UK2Node_VariableSet* StoreActive = nullptr;
	UK2Node_VariableSet* ClearActive = nullptr;
	for (UK2Node_VariableSet* Set : ActiveSets)
	{
		if (OnlyLink(Pin(Load, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Set, UEdGraphSchema_K2::PN_Execute, EGPD_Input)))
		{
			StoreActive = Set;
		}
		if (OnlyLink(Pin(SetRemoval, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Set, UEdGraphSchema_K2::PN_Execute, EGPD_Input)))
		{
			ClearActive = Set;
		}
	}
	const UEdGraphPin* RequestObject = Pin(LoadEvent, TEXT("Request"), EGPD_Output);
	const UEdGraphPin* RequestedTarget = Pin(
		Requested, UEdGraphSchema_K2::PN_Self, EGPD_Input);
	const UEdGraphPin* RequestedValue = Pin(Requested, TEXT("RequestedDistrict"), EGPD_Output);
	const UEdGraphPin* LevelInput = Pin(Load, TEXT("Level"), EGPD_Input);
	const UEdGraphPin* LevelOverride = Pin(
		Load, TEXT("OptionalLevelNameOverride"), EGPD_Input);
	const bool bLoadFlow = StoreActive != nullptr
		&& OnlyLink(Pin(LoadEvent, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Load, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& OnlyLink(RequestObject, RequestedTarget)
		&& OnlyLink(RequestedValue, LevelInput)
		&& OnlyLink(Pin(Load, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
			Pin(StoreActive, TEXT("ActiveStreamingLevel"), EGPD_Input))
		&& LevelInput->DefaultObject == nullptr && LevelInput->DefaultValue.IsEmpty()
		&& LevelOverride != nullptr && LevelOverride->LinkedTo.IsEmpty()
		&& LevelOverride->DefaultValue.IsEmpty();
	if (!bLoadFlow)
	{
		return Fail(TEXT("REFERENCE_LOAD_FLOW"), TEXT("request_soft_world_to_engine_stream=0"));
	}

	const UEdGraphPin* ActiveValue = Pin(Active, TEXT("ActiveStreamingLevel"), EGPD_Output);
	const UEdGraphPin* VisibleTarget = Pin(SetVisible, UEdGraphSchema_K2::PN_Self, EGPD_Input);
	const UEdGraphPin* LoadedTarget = Pin(SetLoaded, UEdGraphSchema_K2::PN_Self, EGPD_Input);
	const UEdGraphPin* RemovalTarget = Pin(SetRemoval, UEdGraphSchema_K2::PN_Self, EGPD_Input);
	const UEdGraphPin* VisibleValue = Pin(SetVisible, TEXT("bInShouldBeVisible"), EGPD_Input);
	const UEdGraphPin* LoadedValue = Pin(SetLoaded, TEXT("bInShouldBeLoaded"), EGPD_Input);
	const UEdGraphPin* RemovalValue = Pin(
		SetRemoval, TEXT("bInIsRequestingUnloadAndRemoval"), EGPD_Input);
	const UEdGraphPin* ClearValue = ClearActive
		? Pin(ClearActive, TEXT("ActiveStreamingLevel"), EGPD_Input) : nullptr;
	const bool bUnloadFlow = ClearActive != nullptr
		&& OnlyLink(Pin(UnloadEvent, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(SetVisible, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& OnlyLink(Pin(SetVisible, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(SetLoaded, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& OnlyLink(Pin(SetLoaded, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(SetRemoval, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& ExactLinks(ActiveValue, {VisibleTarget, LoadedTarget, RemovalTarget})
		&& VisibleValue != nullptr && VisibleValue->LinkedTo.IsEmpty()
		&& VisibleValue->DefaultValue == TEXT("false")
		&& LoadedValue != nullptr && LoadedValue->LinkedTo.IsEmpty()
		&& LoadedValue->DefaultValue == TEXT("false")
		&& RemovalValue != nullptr && RemovalValue->LinkedTo.IsEmpty()
		&& RemovalValue->DefaultValue == TEXT("true")
		&& ClearValue != nullptr && ClearValue->LinkedTo.IsEmpty()
		&& ClearValue->DefaultObject == nullptr;
	if (!bUnloadFlow)
	{
		return Fail(TEXT("REFERENCE_UNLOAD_FLOW"), TEXT("exact_active_stream_chain=0"));
	}

	const FString Result =
		TEXT("PASS DISTRICT_REFERENCE_GRAPH l2i=5 identity=1 nodes=10 "
			 "request_soft_world=1 engine_load_level_instance=1 active_store=1 "
			 "exact_active_unload=1 hardcoded_world=0");
	UE_LOG(LogDistrictReferenceAuthoring, Display,
		TEXT("DISTRICT-REFERENCE-NATIVE %s"), *Result);
	return Result;
}

FString UDistrictStreamingReferenceAuthoring::AuthorReferenceGraph(
	UBlueprint* Blueprint)
{
	const FString Empty = InspectEmptyBaseline(Blueprint);
	if (!Empty.StartsWith(TEXT("PASS DISTRICT_EMPTY_BASELINE ")))
	{
		return Fail(TEXT("AUTHOR_REQUIRES_EMPTY_BASELINE"), Empty);
	}
	UEdGraph* Graph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
	if (Graph == nullptr && !Blueprint->UbergraphPages.IsEmpty())
	{
		Graph = Blueprint->UbergraphPages[0];
	}
	const UEdGraphSchema_K2* Schema = Graph
		? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
	if (Graph == nullptr || Schema == nullptr)
	{
		return Fail(TEXT("AUTHOR_EVENT_GRAPH"), *GetPathNameSafe(Blueprint));
	}
	for (UEdGraphNode* Existing : TArray<UEdGraphNode*>(Graph->Nodes))
	{
		Graph->RemoveNode(Existing);
	}

	int32 EventY = 0;
	UK2Node_Event* LoadEvent = FKismetEditorUtilities::AddDefaultEventNode(
		Blueprint, Graph, TEXT("LoadRequestedDistrict"),
		ADistrictStreamLoaderBase::StaticClass(), EventY);
	UK2Node_VariableGet* Requested = AddGet(
		Graph, TEXT("RequestedDistrict"), ADistrictStreamRequest::StaticClass(),
		220, 130);
	UK2Node_CallFunction* Load = AddCall(
		Graph, ULevelStreamingDynamic::StaticClass(),
		TEXT("LoadLevelInstanceBySoftObjectPtr"), 520, 0);
	UK2Node_VariableSet* StoreActive = AddSet(
		Graph, TEXT("ActiveStreamingLevel"), 900, 0);

	EventY = 420;
	UK2Node_Event* UnloadEvent = FKismetEditorUtilities::AddDefaultEventNode(
		Blueprint, Graph, TEXT("UnloadRequestedDistrict"),
		ADistrictStreamLoaderBase::StaticClass(), EventY);
	UK2Node_VariableGet* Active = AddGet(
		Graph, TEXT("ActiveStreamingLevel"), nullptr, 200, 650);
	UK2Node_CallFunction* SetVisible = AddCall(
		Graph, ULevelStreaming::StaticClass(), TEXT("SetShouldBeVisible"), 380, 420);
	UK2Node_CallFunction* SetLoaded = AddCall(
		Graph, ULevelStreaming::StaticClass(), TEXT("SetShouldBeLoaded"), 650, 420);
	UK2Node_CallFunction* SetRemoval = AddCall(
		Graph, ULevelStreaming::StaticClass(),
		TEXT("SetIsRequestingUnloadAndRemoval"), 920, 420);
	UK2Node_VariableSet* ClearActive = AddSet(
		Graph, TEXT("ActiveStreamingLevel"), 1240, 420);
	if (LoadEvent == nullptr || Requested == nullptr || Load == nullptr
		|| StoreActive == nullptr || UnloadEvent == nullptr || Active == nullptr
		|| SetVisible == nullptr || SetLoaded == nullptr || SetRemoval == nullptr
		|| ClearActive == nullptr)
	{
		return Fail(TEXT("AUTHOR_NODE_CREATE"), *GetPathNameSafe(Blueprint));
	}

	const bool bWired =
		Connect(Schema, Pin(LoadEvent, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(Load, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(LoadEvent, TEXT("Request"), EGPD_Output),
			Pin(Requested, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Pin(Requested, TEXT("RequestedDistrict"), EGPD_Output),
			Pin(Load, TEXT("Level"), EGPD_Input))
		&& Connect(Schema, Pin(Load, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(StoreActive, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(Load, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
			Pin(StoreActive, TEXT("ActiveStreamingLevel"), EGPD_Input))
		&& Connect(Schema, Pin(UnloadEvent, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(SetVisible, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(SetVisible, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(SetLoaded, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(SetLoaded, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(SetRemoval, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(SetRemoval, UEdGraphSchema_K2::PN_Then, EGPD_Output),
			Pin(ClearActive, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
		&& Connect(Schema, Pin(Active, TEXT("ActiveStreamingLevel"), EGPD_Output),
			Pin(SetVisible, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Pin(Active, TEXT("ActiveStreamingLevel"), EGPD_Output),
			Pin(SetLoaded, UEdGraphSchema_K2::PN_Self, EGPD_Input))
		&& Connect(Schema, Pin(Active, TEXT("ActiveStreamingLevel"), EGPD_Output),
			Pin(SetRemoval, UEdGraphSchema_K2::PN_Self, EGPD_Input));
	UEdGraphPin* VisibleValue = Pin(SetVisible, TEXT("bInShouldBeVisible"), EGPD_Input);
	UEdGraphPin* LoadedValue = Pin(SetLoaded, TEXT("bInShouldBeLoaded"), EGPD_Input);
	UEdGraphPin* RemovalValue = Pin(
		SetRemoval, TEXT("bInIsRequestingUnloadAndRemoval"), EGPD_Input);
	if (!bWired || VisibleValue == nullptr || LoadedValue == nullptr
		|| RemovalValue == nullptr)
	{
		return Fail(TEXT("AUTHOR_WIRE"), *GetPathNameSafe(Blueprint));
	}
	Schema->TrySetDefaultValue(*VisibleValue, TEXT("false"));
	Schema->TrySetDefaultValue(*LoadedValue, TEXT("false"));
	Schema->TrySetDefaultValue(*RemovalValue, TEXT("true"));
	if (VisibleValue->DefaultValue != TEXT("false")
		|| LoadedValue->DefaultValue != TEXT("false")
		|| RemovalValue->DefaultValue != TEXT("true"))
	{
		return Fail(TEXT("AUTHOR_LITERAL"), FString::Printf(
			TEXT("visible=%s loaded=%s removal=%s"),
			*VisibleValue->DefaultValue, *LoadedValue->DefaultValue,
			*RemovalValue->DefaultValue));
	}
	if (!SaveBlueprint(Blueprint))
	{
		return Fail(TEXT("AUTHOR_COMPILE_SAVE"), *GetPathNameSafe(Blueprint));
	}
	const FString Inspection = InspectReferenceGraph(Blueprint);
	if (!Inspection.StartsWith(TEXT("PASS DISTRICT_REFERENCE_GRAPH ")))
	{
		return Fail(TEXT("AUTHOR_SAME_PROCESS_L2I"), Inspection);
	}
	const FString Result = TEXT("PASS DISTRICT_REFERENCE_AUTHORED ") + Inspection;
	UE_LOG(LogDistrictReferenceAuthoring, Display,
		TEXT("DISTRICT-REFERENCE-NATIVE %s"), *Result);
	return Result;
}
