// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalAssetAuthoring.h"

#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalRuntime.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Button.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Dom/JsonObject.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Factories/Factory.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"
#include "Widgets/CommonActivatableWidgetContainer.h"

DEFINE_LOG_CATEGORY_STATIC(LogLocalPlayerModalAuthoring, Log, All);

namespace
{
	const FString TaskRoot =
		TEXT("/Game/Tasks/t3-each-local-player-owns-its-top-modal");
	const FName RootName(TEXT("WBP_LocalPlayerModalRoot"));
	const FName ScreenName(TEXT("WBP_LocalPlayerModalScreen"));
	const FName StackName(TEXT("PlayerModalStack"));
	const FName PrimaryName(TEXT("PrimaryFocusButton"));
	const FName AlternateName(TEXT("AlternateFocusButton"));

	bool Fail(const TCHAR* Reason, const FString& Detail)
	{
		UE_LOG(LogLocalPlayerModalAuthoring, Error,
			TEXT("LOCAL-PLAYER-MODAL-AUTHORING-FAILED reason=%s detail=%s"),
			Reason, *Detail);
		return false;
	}

	FString PackagePath(const FName Name)
	{
		return TaskRoot + TEXT("/") + Name.ToString();
	}

	FString ObjectPath(const FName Name)
	{
		return FString::Printf(TEXT("%s/%s.%s"), *TaskRoot,
			*Name.ToString(), *Name.ToString());
	}

	UBlueprint* LoadBlueprint(const FName Name)
	{
		return LoadObject<UBlueprint>(nullptr, *ObjectPath(Name));
	}

	UWidgetTree* WidgetTree(UBlueprint* Blueprint)
	{
		return Blueprint != nullptr
			? FindObject<UWidgetTree>(Blueprint, TEXT("WidgetTree")) : nullptr;
	}

	bool SetClassProperty(UObject* Object, const FName PropertyName, UClass* Value)
	{
		FClassProperty* Property = Object != nullptr
			? FindFProperty<FClassProperty>(Object->GetClass(), PropertyName) : nullptr;
		if (Property == nullptr)
		{
			return false;
		}
		Property->SetObjectPropertyValue_InContainer(Object, Value);
		return Property->GetObjectPropertyValue_InContainer(Object) == Value;
	}

	bool SetBoolProperty(UObject* Object, const FName PropertyName, bool bValue)
	{
		FBoolProperty* Property = Object != nullptr
			? FindFProperty<FBoolProperty>(Object->GetClass(), PropertyName) : nullptr;
		if (Property == nullptr)
		{
			return false;
		}
		Property->SetPropertyValue_InContainer(Object, bValue);
		return Property->GetPropertyValue_InContainer(Object) == bValue;
	}

	FMapProperty* WidgetGuidMapProperty(UBlueprint* Blueprint)
	{
		FMapProperty* Property = Blueprint != nullptr
			? FindFProperty<FMapProperty>(
				Blueprint->GetClass(), TEXT("WidgetVariableNameToGuidMap")) : nullptr;
		return Property != nullptr && CastField<FNameProperty>(Property->KeyProp) != nullptr
			&& CastField<FStructProperty>(Property->ValueProp) != nullptr
			? Property : nullptr;
	}

	bool RegisterWidgetGuids(UBlueprint* Blueprint)
	{
		UWidgetTree* Tree = WidgetTree(Blueprint);
		FMapProperty* Property = WidgetGuidMapProperty(Blueprint);
		if (Tree == nullptr || Property == nullptr)
		{
			return false;
		}
		bool bOkay = true;
		Tree->ForEachWidget([Blueprint, Property, &bOkay](UWidget* Widget)
		{
			if (Widget == nullptr)
			{
				bOkay = false;
				return;
			}
			FScriptMapHelper Helper(
				Property, Property->ContainerPtrToValuePtr<void>(Blueprint));
			const FName Name = Widget->GetFName();
			if (Helper.FindValueFromHash(&Name) == nullptr)
			{
				const FGuid Guid = FGuid::NewDeterministicGuid(Widget->GetPathName());
				Helper.AddPair(&Name, &Guid);
			}
			bOkay = Helper.FindValueFromHash(&Name) != nullptr && bOkay;
		});
		return bOkay;
	}

	bool SaveBlueprint(UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return Fail(TEXT("NULL_BLUEPRINT"), TEXT("None"));
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
		if (Blueprint->GeneratedClass == nullptr ||
			(Blueprint->Status != BS_UpToDate &&
			 Blueprint->Status != BS_UpToDateWithWarnings))
		{
			return Fail(TEXT("BLUEPRINT_COMPILE"),
				FString::Printf(TEXT("%s status=%d"), *Blueprint->GetPathName(),
					static_cast<int32>(Blueprint->Status)));
		}
		UPackage* Package = Blueprint->GetOutermost();
		Package->MarkPackageDirty();
		const FString Filename = FPackageName::LongPackageNameToFilename(
			Package->GetName(), FPackageName::GetAssetPackageExtension());
		FSavePackageArgs Args;
		Args.TopLevelFlags = RF_Public | RF_Standalone;
		Args.SaveFlags = SAVE_NoError;
		Args.Error = GError;
		return UPackage::SavePackage(Package, Blueprint, *Filename, Args) ||
			Fail(TEXT("BLUEPRINT_SAVE"), Filename);
	}

	UBlueprint* CreateWidgetBlueprint(const FName Name, UClass* ParentClass)
	{
		const FString Package = PackagePath(Name);
		if (FindPackage(nullptr, *Package) != nullptr ||
			FPackageName::DoesPackageExist(Package))
		{
			Fail(TEXT("ASSET_EXISTS"), ObjectPath(Name));
			return nullptr;
		}
		if (FModuleManager::Get().LoadModule(FName(TEXT("UMGEditor"))) == nullptr)
		{
			Fail(TEXT("UMG_EDITOR"), TEXT("module unavailable"));
			return nullptr;
		}
		UClass* FactoryClass = LoadClass<UFactory>(
			nullptr, TEXT("/Script/UMGEditor.WidgetBlueprintFactory"));
		UFactory* Factory = FactoryClass != nullptr
			? NewObject<UFactory>(GetTransientPackage(), FactoryClass) : nullptr;
		if (Factory == nullptr || !SetClassProperty(Factory, TEXT("ParentClass"), ParentClass))
		{
			Fail(TEXT("FACTORY_CONFIG"), GetNameSafe(ParentClass));
			return nullptr;
		}
		UPackage* NewPackage = CreatePackage(*Package);
		UObject* Created = NewPackage != nullptr
			? Factory->FactoryCreateNew(Factory->GetSupportedClass(), NewPackage, Name,
				RF_Public | RF_Standalone | RF_Transactional, nullptr, GWarn) : nullptr;
		UBlueprint* Blueprint = Cast<UBlueprint>(Created);
		if (Blueprint == nullptr)
		{
			Fail(TEXT("FACTORY_CREATE"), Name.ToString());
			return nullptr;
		}
		FAssetRegistryModule::AssetCreated(Blueprint);
		return Blueprint;
	}

	UEdGraphPin* Pin(UEdGraphNode* Node, const FName Name, EEdGraphPinDirection Direction)
	{
		return Node != nullptr ? Node->FindPin(Name, Direction) : nullptr;
	}

	UEdGraphPin* FirstDataPin(UEdGraphNode* Node, EEdGraphPinDirection Direction)
	{
		if (Node == nullptr)
		{
			return nullptr;
		}
		for (UEdGraphPin* Candidate : Node->Pins)
		{
			if (Candidate != nullptr && Candidate->Direction == Direction &&
				Candidate->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec &&
				Candidate->PinName != UEdGraphSchema_K2::PN_Self)
			{
				return Candidate;
			}
		}
		return nullptr;
	}

	bool Connect(const UEdGraphSchema_K2* Schema, UEdGraphPin* Output, UEdGraphPin* Input)
	{
		return Schema != nullptr && Output != nullptr && Input != nullptr &&
			Schema->TryCreateConnection(Output, Input);
	}

	UK2Node_CallFunction* AddCall(
		UEdGraph* Graph, UClass* Owner, const FName Function, int32 X, int32 Y)
	{
		if (Graph == nullptr || Owner == nullptr || Owner->FindFunctionByName(Function) == nullptr)
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

	UEdGraph* ResetEventGraph(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = Blueprint != nullptr
			? FBlueprintEditorUtils::FindEventGraph(Blueprint) : nullptr;
		if (Graph == nullptr && Blueprint != nullptr && !Blueprint->UbergraphPages.IsEmpty())
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

	bool BuildScreenLifecycle(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = ResetEventGraph(Blueprint);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		int32 ActivatedY = 0;
		int32 DeactivatedY = 420;
		int32 DismissY = 760;
		UK2Node_Event* Activated = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(Blueprint, Graph,
				TEXT("BP_OnActivated"), UCommonActivatableWidget::StaticClass(), ActivatedY)
			: nullptr;
		UK2Node_Event* Deactivated = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(Blueprint, Graph,
				TEXT("BP_OnDeactivated"), UCommonActivatableWidget::StaticClass(), DeactivatedY)
			: nullptr;
		UK2Node_Event* Dismiss = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(Blueprint, Graph,
				TEXT("OnConfiguredDismiss"), ULocalPlayerModalScreenBase::StaticClass(), DismissY)
			: nullptr;
		UK2Node_CallFunction* Apply = AddCall(Graph,
			ULocalPlayerModalScreenBase::StaticClass(), TEXT("ApplyConfiguredMapping"), 260, 0);
		UK2Node_CallFunction* Register = AddCall(Graph,
			ULocalPlayerModalScreenBase::StaticClass(), TEXT("RegisterConfiguredDismiss"), 560, 0);
		UK2Node_CallFunction* Remove = AddCall(Graph,
			ULocalPlayerModalScreenBase::StaticClass(), TEXT("RemoveConfiguredMapping"), 300, 420);
		UK2Node_CallFunction* Close = AddCall(Graph,
			ULocalPlayerModalScreenBase::StaticClass(), TEXT("CloseOnlyThisModal"), 300, 760);
		return Activated != nullptr && Deactivated != nullptr && Dismiss != nullptr &&
			Apply != nullptr && Register != nullptr && Remove != nullptr && Close != nullptr &&
			Connect(Schema, Pin(Activated, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Apply, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(Apply, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Register, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(Deactivated, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Remove, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(Dismiss, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Close, UEdGraphSchema_K2::PN_Execute, EGPD_Input));
	}

	bool BuildPureCallOverride(UBlueprint* Blueprint, const FName FunctionName,
		UClass* CallOwner, const FName CallFunction)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		UFunction* OverrideFunction = nullptr;
		UClass* OverrideClass = FBlueprintEditorUtils::GetOverrideFunctionClass(
			Blueprint, FunctionName, &OverrideFunction);
		if (OverrideClass == nullptr || OverrideFunction == nullptr)
		{
			return false;
		}
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(
			Blueprint, FunctionName, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(Blueprint, Graph, false, OverrideClass);
		UK2Node_FunctionEntry* Entry = nullptr;
		UK2Node_FunctionResult* Result = nullptr;
		for (UEdGraphNode* Node : TArray<UEdGraphNode*>(Graph->Nodes))
		{
			if (UK2Node_FunctionEntry* EntryNode = Cast<UK2Node_FunctionEntry>(Node))
			{
				Entry = EntryNode;
			}
			else if (UK2Node_FunctionResult* ResultNode = Cast<UK2Node_FunctionResult>(Node))
			{
				Result = ResultNode;
			}
			else
			{
				Graph->RemoveNode(Node);
			}
		}
		UK2Node_CallFunction* Call = AddCall(Graph, CallOwner, CallFunction, 260, 100);
		const UEdGraphSchema_K2* Schema = Cast<UEdGraphSchema_K2>(Graph->GetSchema());
		return Entry != nullptr && Result != nullptr && Call != nullptr &&
			Connect(Schema, Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Result, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, FirstDataPin(Call, EGPD_Output),
				FirstDataPin(Result, EGPD_Input));
	}

	bool BuildRootStackOverride(UBlueprint* Blueprint)
	{
		const FName FunctionName(TEXT("ResolvePlayerModalStack"));
		UFunction* OverrideFunction = nullptr;
		UClass* OverrideClass = FBlueprintEditorUtils::GetOverrideFunctionClass(
			Blueprint, FunctionName, &OverrideFunction);
		if (Blueprint == nullptr || OverrideClass == nullptr || OverrideFunction == nullptr)
		{
			return false;
		}
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(
			Blueprint, FunctionName, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(Blueprint, Graph, false, OverrideClass);
		UK2Node_FunctionEntry* Entry = nullptr;
		UK2Node_FunctionResult* Result = nullptr;
		for (UEdGraphNode* Node : TArray<UEdGraphNode*>(Graph->Nodes))
		{
			Entry = Entry != nullptr ? Entry : Cast<UK2Node_FunctionEntry>(Node);
			Result = Result != nullptr ? Result : Cast<UK2Node_FunctionResult>(Node);
		}
		UK2Node_VariableGet* Stack = NewObject<UK2Node_VariableGet>(Graph);
		Stack->VariableReference.SetSelfMember(StackName);
		Graph->AddNode(Stack, false, false);
		Stack->CreateNewGuid();
		Stack->PostPlacedNewNode();
		Stack->AllocateDefaultPins();
		Stack->NodePosX = 250;
		Stack->NodePosY = 100;
		const UEdGraphSchema_K2* Schema = Cast<UEdGraphSchema_K2>(Graph->GetSchema());
		return Entry != nullptr && Result != nullptr &&
			Connect(Schema, Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Result, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(Stack, StackName, EGPD_Output),
				FirstDataPin(Result, EGPD_Input));
	}

	bool GraphHasCall(const UBlueprint* Blueprint, const FName Function)
	{
		TArray<UEdGraph*> Graphs;
		if (Blueprint != nullptr)
		{
			Blueprint->GetAllGraphs(Graphs);
		}
		for (const UEdGraph* Graph : Graphs)
		{
			for (const UEdGraphNode* Node : Graph != nullptr
				? Graph->Nodes : TArray<TObjectPtr<UEdGraphNode>>())
			{
				const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
				if (Call != nullptr && Call->FunctionReference.GetMemberName() == Function)
				{
					return true;
				}
			}
		}
		return false;
	}

	bool GraphHasFunction(const UBlueprint* Blueprint, const FName Function)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph != nullptr && Graph->GetFName() == Function && Graph->Nodes.Num() >= 3)
			{
				return true;
			}
		}
		return false;
	}

	bool GraphHasEvent(const UBlueprint* Blueprint, const FName Event)
	{
		UEdGraph* Graph = Blueprint != nullptr
			? FBlueprintEditorUtils::FindEventGraph(const_cast<UBlueprint*>(Blueprint)) : nullptr;
		if (Graph == nullptr)
		{
			return false;
		}
		for (const UEdGraphNode* Node : Graph->Nodes)
		{
			const UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node);
			if (EventNode != nullptr && EventNode->EventReference.GetMemberName() == Event)
			{
				return true;
			}
		}
		return false;
	}

	void SetCheck(const TSharedRef<FJsonObject>& Result, const TCHAR* Id,
		bool bPassed, const FString& Evidence)
	{
		TSharedRef<FJsonObject> Check = MakeShared<FJsonObject>();
		Check->SetBoolField(TEXT("passed"), bPassed);
		Check->SetStringField(TEXT("evidence"), Evidence);
		Result->SetObjectField(Id, Check);
	}
}

bool ULocalPlayerModalAssetAuthoring::CreateBaselineAssets()
{
	UBlueprint* Root = CreateWidgetBlueprint(RootName, ULocalPlayerModalRootBase::StaticClass());
	UBlueprint* Screen = CreateWidgetBlueprint(
		ScreenName, ULocalPlayerModalScreenBase::StaticClass());
	UWidgetTree* RootTree = WidgetTree(Root);
	UWidgetTree* ScreenTree = WidgetTree(Screen);
	UCommonActivatableWidgetStack* Stack = RootTree != nullptr
		? RootTree->ConstructWidget<UCommonActivatableWidgetStack>(
			UCommonActivatableWidgetStack::StaticClass(), StackName) : nullptr;
	UVerticalBox* Layout = ScreenTree != nullptr
		? ScreenTree->ConstructWidget<UVerticalBox>(
			UVerticalBox::StaticClass(), TEXT("ModalFocusLayout")) : nullptr;
	UButton* Primary = ScreenTree != nullptr
		? ScreenTree->ConstructWidget<UButton>(UButton::StaticClass(), PrimaryName) : nullptr;
	UButton* Alternate = ScreenTree != nullptr
		? ScreenTree->ConstructWidget<UButton>(UButton::StaticClass(), AlternateName) : nullptr;
	if (Root == nullptr || Screen == nullptr || Stack == nullptr || Layout == nullptr ||
		Primary == nullptr || Alternate == nullptr ||
		!SetBoolProperty(Primary, TEXT("IsFocusable"), true) ||
		!SetBoolProperty(Alternate, TEXT("IsFocusable"), true))
	{
		return Fail(TEXT("BASELINE_TREE"), TaskRoot);
	}
	Stack->bIsVariable = true;
	Stack->SetTransitionDuration(0.0f);
	RootTree->RootWidget = Stack;
	Layout->AddChildToVerticalBox(Primary);
	Layout->AddChildToVerticalBox(Alternate);
	ScreenTree->RootWidget = Layout;
	if (!RegisterWidgetGuids(Root) || !RegisterWidgetGuids(Screen) ||
		!SaveBlueprint(Root) || !SaveBlueprint(Screen))
	{
		return Fail(TEXT("BASELINE_SAVE"), TaskRoot);
	}
	UE_LOG(LogLocalPlayerModalAuthoring, Display,
		TEXT("LOCAL-PLAYER-MODAL-BASELINE-SAVED assets=2 root_stack=1 focus_buttons=2 behavior=0"));
	return true;
}

bool ULocalPlayerModalAssetAuthoring::ValidateBaselineAssets()
{
	UBlueprint* Root = LoadBlueprint(RootName);
	UBlueprint* Screen = LoadBlueprint(ScreenName);
	UCommonActivatableWidgetStack* Stack = Root != nullptr && WidgetTree(Root) != nullptr
		? Cast<UCommonActivatableWidgetStack>(WidgetTree(Root)->FindWidget(StackName)) : nullptr;
	UButton* Primary = Screen != nullptr && WidgetTree(Screen) != nullptr
		? Cast<UButton>(WidgetTree(Screen)->FindWidget(PrimaryName)) : nullptr;
	UButton* Alternate = Screen != nullptr && WidgetTree(Screen) != nullptr
		? Cast<UButton>(WidgetTree(Screen)->FindWidget(AlternateName)) : nullptr;
	const bool bValid = Root != nullptr && Screen != nullptr &&
		Root->ParentClass == ULocalPlayerModalRootBase::StaticClass() &&
		Screen->ParentClass == ULocalPlayerModalScreenBase::StaticClass() &&
		Stack != nullptr && Stack->bIsVariable && Primary != nullptr &&
		Alternate != nullptr && Primary->GetIsFocusable() && Alternate->GetIsFocusable() &&
		!GraphHasFunction(Root, TEXT("ResolvePlayerModalStack")) &&
		!GraphHasEvent(Screen, TEXT("BP_OnActivated")) &&
		!GraphHasEvent(Screen, TEXT("BP_OnDeactivated")) &&
		!GraphHasEvent(Screen, TEXT("OnConfiguredDismiss")) &&
		!GraphHasFunction(Screen, TEXT("BP_GetDesiredFocusTarget")) &&
		!GraphHasFunction(Screen, TEXT("BP_GetDesiredInputConfig")) &&
		!GraphHasCall(Screen, TEXT("ApplyConfiguredMapping")) &&
		!GraphHasCall(Screen, TEXT("RegisterConfiguredDismiss")) &&
		!GraphHasCall(Screen, TEXT("RemoveConfiguredMapping")) &&
		!GraphHasCall(Screen, TEXT("CloseOnlyThisModal"));
	if (!bValid)
	{
		return Fail(TEXT("BASELINE_READBACK"), TaskRoot);
	}
	UE_LOG(LogLocalPlayerModalAuthoring, Display,
		TEXT("LOCAL-PLAYER-MODAL-BASELINE-READBACK-PASS assets=2 root_stack=1 focus_buttons=2 behavior=0"));
	return true;
}

bool ULocalPlayerModalAssetAuthoring::BuildReferenceGraphs()
{
	UBlueprint* Root = LoadBlueprint(RootName);
	UBlueprint* Screen = LoadBlueprint(ScreenName);
	if (Root == nullptr || Screen == nullptr ||
		Root->ParentClass != ULocalPlayerModalRootBase::StaticClass() ||
		Screen->ParentClass != ULocalPlayerModalScreenBase::StaticClass() ||
		GraphHasFunction(Root, TEXT("ResolvePlayerModalStack")) ||
		GraphHasEvent(Screen, TEXT("BP_OnActivated")) ||
		GraphHasEvent(Screen, TEXT("BP_OnDeactivated")) ||
		GraphHasEvent(Screen, TEXT("OnConfiguredDismiss")))
	{
		return Fail(TEXT("REFERENCE_ENTRY"), TaskRoot);
	}
	if (!BuildRootStackOverride(Root) ||
		!BuildScreenLifecycle(Screen) ||
		!BuildPureCallOverride(Screen, TEXT("BP_GetDesiredFocusTarget"),
			ULocalPlayerModalScreenBase::StaticClass(), TEXT("ResolveConfiguredFocusTarget")) ||
		!BuildPureCallOverride(Screen, TEXT("BP_GetDesiredInputConfig"),
			ULocalPlayerModalScreenBase::StaticClass(), TEXT("ResolveConfiguredInputConfig")) ||
		!SaveBlueprint(Root) || !SaveBlueprint(Screen))
	{
		return Fail(TEXT("REFERENCE_BUILD"), TaskRoot);
	}
	const FString Inspection = InspectSubmissionAssets();
	TSharedPtr<FJsonObject> ParsedInspection;
	const TSharedRef<TJsonReader<>> InspectionReader =
		TJsonReaderFactory<>::Create(Inspection);
	const TArray<FString> ExpectedCheckIds = {
		TEXT("exact_two_player_owned_roots_and_stack_return"),
		TEXT("owning_player_modal_lifecycle_and_focus_return"),
		TEXT("exact_asset_inventory_without_global_substitute"),
	};
	bool bInspectionPassed =
		FJsonSerializer::Deserialize(InspectionReader, ParsedInspection) &&
		ParsedInspection.IsValid() &&
		ParsedInspection->Values.Num() == ExpectedCheckIds.Num();
	for (const FString& CheckId : ExpectedCheckIds)
	{
		const TSharedPtr<FJsonObject>* Check = nullptr;
		bool bPassed = false;
		bInspectionPassed = bInspectionPassed &&
			ParsedInspection->TryGetObjectField(CheckId, Check) &&
			Check != nullptr && Check->IsValid() &&
			(*Check)->TryGetBoolField(TEXT("passed"), bPassed) && bPassed;
	}
	if (!bInspectionPassed)
	{
		return Fail(TEXT("REFERENCE_READBACK"), Inspection);
	}
	UE_LOG(LogLocalPlayerModalAuthoring, Display,
		TEXT("LOCAL-PLAYER-MODAL-REFERENCE-SAVED assets=2 root_graph=1 lifecycle=3 focus=1 input_config=1 l2i=3"));
	return true;
}

FString ULocalPlayerModalAssetAuthoring::InspectSubmissionAssets()
{
	UBlueprint* Root = LoadBlueprint(RootName);
	UBlueprint* Screen = LoadBlueprint(ScreenName);
	if (Root != nullptr)
	{
		FKismetEditorUtilities::CompileBlueprint(Root);
	}
	if (Screen != nullptr)
	{
		FKismetEditorUtilities::CompileBlueprint(Screen);
	}
	TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
	UCommonActivatableWidgetStack* Stack = Root != nullptr && WidgetTree(Root) != nullptr
		? Cast<UCommonActivatableWidgetStack>(WidgetTree(Root)->FindWidget(StackName)) : nullptr;
	const bool bRoot = Root != nullptr &&
		Root->ParentClass == ULocalPlayerModalRootBase::StaticClass() && Stack != nullptr &&
		Stack->bIsVariable && GraphHasFunction(Root, TEXT("ResolvePlayerModalStack"));
	SetCheck(Result, TEXT("exact_two_player_owned_roots_and_stack_return"), bRoot,
		FString::Printf(TEXT("root=%s parent=%s stack=%d variable=%d return_graph=%d"),
			*GetNameSafe(Root), *GetNameSafe(Root ? Root->ParentClass.Get() : nullptr),
			Stack != nullptr, Stack != nullptr && Stack->bIsVariable,
			GraphHasFunction(Root, TEXT("ResolvePlayerModalStack"))));

	UButton* Primary = Screen != nullptr && WidgetTree(Screen) != nullptr
		? Cast<UButton>(WidgetTree(Screen)->FindWidget(PrimaryName)) : nullptr;
	UButton* Alternate = Screen != nullptr && WidgetTree(Screen) != nullptr
		? Cast<UButton>(WidgetTree(Screen)->FindWidget(AlternateName)) : nullptr;
	const bool bLifecycle = Screen != nullptr &&
		Screen->ParentClass == ULocalPlayerModalScreenBase::StaticClass() &&
		Primary != nullptr && Alternate != nullptr && Primary->GetIsFocusable() &&
		Alternate->GetIsFocusable() &&
		GraphHasEvent(Screen, TEXT("BP_OnActivated")) &&
		GraphHasEvent(Screen, TEXT("BP_OnDeactivated")) &&
		GraphHasEvent(Screen, TEXT("OnConfiguredDismiss")) &&
		GraphHasCall(Screen, TEXT("ApplyConfiguredMapping")) &&
		GraphHasCall(Screen, TEXT("RegisterConfiguredDismiss")) &&
		GraphHasCall(Screen, TEXT("RemoveConfiguredMapping")) &&
		GraphHasCall(Screen, TEXT("CloseOnlyThisModal")) &&
		GraphHasFunction(Screen, TEXT("BP_GetDesiredFocusTarget")) &&
		GraphHasFunction(Screen, TEXT("BP_GetDesiredInputConfig"));
	SetCheck(Result, TEXT("owning_player_modal_lifecycle_and_focus_return"), bLifecycle,
		FString::Printf(TEXT("screen=%s parent=%s buttons=%d events=%d/%d/%d calls=%d/%d/%d/%d focus=%d input=%d"),
			*GetNameSafe(Screen), *GetNameSafe(Screen ? Screen->ParentClass.Get() : nullptr),
			Primary != nullptr && Alternate != nullptr,
			GraphHasEvent(Screen, TEXT("BP_OnActivated")),
			GraphHasEvent(Screen, TEXT("BP_OnDeactivated")),
			GraphHasEvent(Screen, TEXT("OnConfiguredDismiss")),
			GraphHasCall(Screen, TEXT("ApplyConfiguredMapping")),
			GraphHasCall(Screen, TEXT("RegisterConfiguredDismiss")),
			GraphHasCall(Screen, TEXT("RemoveConfiguredMapping")),
			GraphHasCall(Screen, TEXT("CloseOnlyThisModal")),
			GraphHasFunction(Screen, TEXT("BP_GetDesiredFocusTarget")),
			GraphHasFunction(Screen, TEXT("BP_GetDesiredInputConfig"))));

	const bool bForbidden = GraphHasCall(Root, TEXT("AddToViewport")) ||
		GraphHasCall(Root, TEXT("AddToPlayerScreen")) ||
		GraphHasCall(Screen, TEXT("AddToViewport")) ||
		GraphHasCall(Screen, TEXT("AddToPlayerScreen")) ||
		GraphHasCall(Screen, TEXT("ClearAllMappings"));
	SetCheck(Result, TEXT("exact_asset_inventory_without_global_substitute"),
		Root != nullptr && Screen != nullptr && !bForbidden,
		FString::Printf(TEXT("root=%d screen=%d forbidden_global_calls=%d"),
			Root != nullptr, Screen != nullptr, bForbidden));

	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	FJsonSerializer::Serialize(Result, Writer);
	return Json;
}
