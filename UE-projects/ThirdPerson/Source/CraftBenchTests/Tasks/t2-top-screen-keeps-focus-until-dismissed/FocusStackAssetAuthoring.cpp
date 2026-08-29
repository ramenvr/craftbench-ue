// Copyright CraftBench. All Rights Reserved.
//
// AUTHORING-ONLY. See FocusStackAssetAuthoring.h.

#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/FocusStackAssetAuthoring.h"

#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/MenuFocusPolicy.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetTree.h"
#include "CommonActivatableWidget.h"
#include "Components/Button.h"
#include "Components/Overlay.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Factories/Factory.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_SwitchEnum.h"
#include "K2Node_VariableGet.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "Widgets/CommonActivatableWidgetContainer.h"

DEFINE_LOG_CATEGORY_STATIC(LogFocusStackAssetAuthoring, Log, All);

namespace
{
	const FString TaskPackageRoot =
		TEXT("/Game/Tasks/t2-top-screen-keeps-focus-until-dismissed");
	const FName RootAssetName(TEXT("WBP_MenuRoot"));
	const FName HomeAssetName(TEXT("WBP_HomeScreen"));
	const FName DetailAssetName(TEXT("WBP_DetailScreen"));
	const FName StackName(TEXT("ScreenStack"));
	const FName HomeButtonName(TEXT("Button_HomePrimary"));
	const FName DetailPrimaryName(TEXT("Button_DetailPrimary"));
	const FName DetailAlternateName(TEXT("Button_DetailAlternate"));
	const FName OpenDetailsName(TEXT("OpenDetails"));
	const FName DismissTopName(TEXT("DismissTop"));
	const FName CloseMenuName(TEXT("CloseMenu"));

	bool AuthoringFail(const TCHAR* Reason, const FString& Context)
	{
		UE_LOG(LogFocusStackAssetAuthoring, Error,
			TEXT("FOCUS-ASSET-AUTHORING FAILED reason=%s context=%s"),
			Reason, *Context);
		return false;
	}

	FString PackageNameFor(const FName AssetName)
	{
		return TaskPackageRoot + TEXT("/") + AssetName.ToString();
	}

	FString ObjectPathFor(const FName AssetName)
	{
		return FString::Printf(TEXT("%s/%s.%s"), *TaskPackageRoot,
			*AssetName.ToString(), *AssetName.ToString());
	}

	UBlueprint* LoadTaskBlueprint(const FName AssetName)
	{
		return LoadObject<UBlueprint>(nullptr, *ObjectPathFor(AssetName));
	}

	UWidgetTree* GetWidgetTree(UBlueprint* Blueprint)
	{
		return Blueprint != nullptr
			? FindObject<UWidgetTree>(Blueprint, TEXT("WidgetTree"))
			: nullptr;
	}

	FMapProperty* WidgetGuidMapProperty(UBlueprint* Blueprint)
	{
		FMapProperty* MapProperty = Blueprint != nullptr
			? FindFProperty<FMapProperty>(
				Blueprint->GetClass(), TEXT("WidgetVariableNameToGuidMap"))
			: nullptr;
		if (MapProperty == nullptr
			|| CastField<FNameProperty>(MapProperty->KeyProp) == nullptr)
		{
			return nullptr;
		}
		FStructProperty* GuidProperty = CastField<FStructProperty>(MapProperty->ValueProp);
		return GuidProperty != nullptr && GuidProperty->Struct != nullptr
			&& GuidProperty->Struct->GetFName() == TEXT("Guid")
			? MapProperty : nullptr;
	}

	bool RegisterWidgetGuid(UBlueprint* Blueprint, UWidget* Widget)
	{
		FMapProperty* MapProperty = WidgetGuidMapProperty(Blueprint);
		if (MapProperty == nullptr || Widget == nullptr)
		{
			return false;
		}
		void* MapAddress = MapProperty->ContainerPtrToValuePtr<void>(Blueprint);
		FScriptMapHelper MapHelper(MapProperty, MapAddress);
		const FName WidgetName = Widget->GetFName();
		if (const uint8* ExistingValue = MapHelper.FindValueFromHash(&WidgetName))
		{
			return reinterpret_cast<const FGuid*>(ExistingValue)->IsValid();
		}

		const FGuid StableGuid = FGuid::NewDeterministicGuid(Widget->GetPathName());
		if (!StableGuid.IsValid())
		{
			return false;
		}
		MapHelper.AddPair(&WidgetName, &StableGuid);
		const uint8* AddedValue = MapHelper.FindValueFromHash(&WidgetName);
		return AddedValue != nullptr
			&& *reinterpret_cast<const FGuid*>(AddedValue) == StableGuid;
	}

	bool RegisterAllWidgetGuids(UBlueprint* Blueprint)
	{
		UWidgetTree* Tree = GetWidgetTree(Blueprint);
		if (Tree == nullptr || WidgetGuidMapProperty(Blueprint) == nullptr)
		{
			return false;
		}
		bool bAllRegistered = true;
		Tree->ForEachWidget([Blueprint, &bAllRegistered](UWidget* Widget)
		{
			bAllRegistered = RegisterWidgetGuid(Blueprint, Widget) && bAllRegistered;
		});
		return bAllRegistered;
	}

	bool HasValidWidgetGuid(UBlueprint* Blueprint, const FName WidgetName)
	{
		FMapProperty* MapProperty = WidgetGuidMapProperty(Blueprint);
		if (MapProperty == nullptr)
		{
			return false;
		}
		FScriptMapHelper MapHelper(
			MapProperty, MapProperty->ContainerPtrToValuePtr<void>(Blueprint));
		const uint8* Value = MapHelper.FindValueFromHash(&WidgetName);
		return Value != nullptr && reinterpret_cast<const FGuid*>(Value)->IsValid();
	}

	bool SetClassProperty(UObject* Object, const FName PropertyName, UClass* Value)
	{
		FClassProperty* Property = Object != nullptr
			? FindFProperty<FClassProperty>(Object->GetClass(), PropertyName)
			: nullptr;
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
			? FindFProperty<FBoolProperty>(Object->GetClass(), PropertyName)
			: nullptr;
		if (Property == nullptr)
		{
			return false;
		}
		Property->SetPropertyValue_InContainer(Object, bValue);
		return Property->GetPropertyValue_InContainer(Object) == bValue;
	}

	bool SaveBlueprint(UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return AuthoringFail(TEXT("NULL_BLUEPRINT"), TEXT("<none>"));
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
		if (Blueprint->Status != BS_UpToDate
			&& Blueprint->Status != BS_UpToDateWithWarnings)
		{
			return AuthoringFail(TEXT("COMPILE_NOT_CLEAN"),
				FString::Printf(TEXT("%s status=%d"), *Blueprint->GetPathName(),
					static_cast<int32>(Blueprint->Status)));
		}

		UPackage* Package = Blueprint->GetOutermost();
		if (Package == nullptr)
		{
			return AuthoringFail(TEXT("NO_PACKAGE"), Blueprint->GetPathName());
		}
		Package->MarkPackageDirty();
		const FString Filename = FPackageName::LongPackageNameToFilename(
			Package->GetName(), FPackageName::GetAssetPackageExtension());
		FSavePackageArgs Args;
		Args.TopLevelFlags = RF_Public | RF_Standalone;
		Args.SaveFlags = SAVE_NoError;
		Args.Error = GError;
		if (!UPackage::SavePackage(Package, Blueprint, *Filename, Args))
		{
			return AuthoringFail(TEXT("SAVE_FAILED"), Filename);
		}
		return true;
	}

	bool AddEmptyFunction(UBlueprint* Blueprint, const FName FunctionName)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		for (const UEdGraph* Existing : Blueprint->FunctionGraphs)
		{
			if (Existing != nullptr && Existing->GetFName() == FunctionName)
			{
				return false;
			}
		}
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(
			Blueprint, FunctionName, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
		if (Graph == nullptr)
		{
			return false;
		}
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(Blueprint, Graph, true, nullptr);
		return Blueprint->FunctionGraphs.Contains(Graph);
	}

	UBlueprint* CreateWidgetBlueprint(const FName AssetName)
	{
		const FString PackageName = PackageNameFor(AssetName);
		if (FindPackage(nullptr, *PackageName) != nullptr
			|| FPackageName::DoesPackageExist(PackageName))
		{
			AuthoringFail(TEXT("ASSET_ALREADY_EXISTS"), ObjectPathFor(AssetName));
			return nullptr;
		}

		if (FModuleManager::Get().LoadModule(FName(TEXT("UMGEditor"))) == nullptr)
		{
			AuthoringFail(TEXT("UMG_EDITOR_MODULE_UNAVAILABLE"), TEXT("UMGEditor"));
			return nullptr;
		}
		UClass* FactoryClass = LoadClass<UFactory>(
			nullptr, TEXT("/Script/UMGEditor.WidgetBlueprintFactory"));
		if (FactoryClass == nullptr)
		{
			AuthoringFail(TEXT("WIDGET_FACTORY_CLASS_UNAVAILABLE"), TEXT("UMGEditor"));
			return nullptr;
		}
		UFactory* Factory = NewObject<UFactory>(GetTransientPackage(), FactoryClass);
		if (Factory == nullptr
			|| !SetClassProperty(Factory, TEXT("ParentClass"), UCommonActivatableWidget::StaticClass()))
		{
			AuthoringFail(TEXT("WIDGET_FACTORY_CONFIGURATION_FAILED"), AssetName.ToString());
			return nullptr;
		}

		UPackage* Package = CreatePackage(*PackageName);
		if (Package == nullptr)
		{
			AuthoringFail(TEXT("PACKAGE_CREATE_FAILED"), PackageNameFor(AssetName));
			return nullptr;
		}
		UObject* Created = Factory->FactoryCreateNew(
			Factory->GetSupportedClass(), Package, AssetName,
			RF_Public | RF_Standalone | RF_Transactional, nullptr, GWarn);
		UBlueprint* Blueprint = Cast<UBlueprint>(Created);
		if (Blueprint == nullptr)
		{
			AuthoringFail(TEXT("WIDGET_BLUEPRINT_CREATE_FAILED"), AssetName.ToString());
			return nullptr;
		}
		FAssetRegistryModule::AssetCreated(Blueprint);
		return Blueprint;
	}

	UTextBlock* AddLabel(UWidgetTree* Tree, UButton* Button, const TCHAR* Name, const TCHAR* Text)
	{
		if (Tree == nullptr || Button == nullptr)
		{
			return nullptr;
		}
		UTextBlock* Label = Tree->ConstructWidget<UTextBlock>(
			UTextBlock::StaticClass(), FName(Name));
		if (Label != nullptr)
		{
			Label->SetText(FText::FromString(Text));
			Button->AddChild(Label);
		}
		return Label;
	}

	bool BuildRootBaseline(UBlueprint* Blueprint)
	{
		UWidgetTree* Tree = GetWidgetTree(Blueprint);
		if (Tree == nullptr)
		{
			return false;
		}
		UOverlay* Layout = Tree->ConstructWidget<UOverlay>(
			UOverlay::StaticClass(), TEXT("MenuRootLayer"));
		if (Layout == nullptr)
		{
			return false;
		}
		Tree->RootWidget = Layout;
		return AddEmptyFunction(Blueprint, OpenDetailsName)
			&& AddEmptyFunction(Blueprint, DismissTopName)
			&& AddEmptyFunction(Blueprint, CloseMenuName);
	}

	bool BuildHomeBaseline(UBlueprint* Blueprint)
	{
		UWidgetTree* Tree = GetWidgetTree(Blueprint);
		if (Tree == nullptr)
		{
			return false;
		}
		UVerticalBox* Layout = Tree->ConstructWidget<UVerticalBox>(
			UVerticalBox::StaticClass(), TEXT("HomeLayout"));
		UButton* Button = Tree->ConstructWidget<UButton>(
			UButton::StaticClass(), HomeButtonName);
		if (Layout == nullptr || Button == nullptr
			|| !SetBoolProperty(Button, TEXT("IsFocusable"), false)
			|| AddLabel(Tree, Button, TEXT("Label_HomePrimary"), TEXT("Home Primary")) == nullptr)
		{
			return false;
		}
		Button->bIsVariable = true;
		Layout->AddChildToVerticalBox(Button);
		Tree->RootWidget = Layout;
		return true;
	}

	bool BuildDetailBaseline(UBlueprint* Blueprint)
	{
		UWidgetTree* Tree = GetWidgetTree(Blueprint);
		if (Tree == nullptr)
		{
			return false;
		}
		UVerticalBox* Layout = Tree->ConstructWidget<UVerticalBox>(
			UVerticalBox::StaticClass(), TEXT("DetailLayout"));
		UButton* Primary = Tree->ConstructWidget<UButton>(
			UButton::StaticClass(), DetailPrimaryName);
		UButton* Alternate = Tree->ConstructWidget<UButton>(
			UButton::StaticClass(), DetailAlternateName);
		if (Layout == nullptr || Primary == nullptr || Alternate == nullptr
			|| !SetBoolProperty(Primary, TEXT("IsFocusable"), false)
			|| !SetBoolProperty(Alternate, TEXT("IsFocusable"), false)
			|| AddLabel(Tree, Primary, TEXT("Label_DetailPrimary"), TEXT("Detail Primary")) == nullptr
			|| AddLabel(Tree, Alternate, TEXT("Label_DetailAlternate"), TEXT("Detail Alternate")) == nullptr)
		{
			return false;
		}
		Primary->bIsVariable = true;
		Alternate->bIsVariable = true;
		Layout->AddChildToVerticalBox(Primary);
		Layout->AddChildToVerticalBox(Alternate);
		Tree->RootWidget = Layout;
		return true;
	}

	template <typename TNode>
	TNode* AddNode(UEdGraph* Graph, int32 X, int32 Y)
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

	UK2Node_CallFunction* AddCall(
		UEdGraph* Graph, UClass* OwnerClass, const FName FunctionName, int32 X, int32 Y)
	{
		if (Graph == nullptr || OwnerClass == nullptr
			|| OwnerClass->FindFunctionByName(FunctionName) == nullptr)
		{
			return nullptr;
		}
		UK2Node_CallFunction* Node = NewObject<UK2Node_CallFunction>(Graph);
		Node->FunctionReference.SetExternalMember(FunctionName, OwnerClass);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UK2Node_VariableGet* AddVariableGet(
		UEdGraph* Graph, const FName PropertyName, int32 X, int32 Y)
	{
		UK2Node_VariableGet* Node = Graph != nullptr
			? NewObject<UK2Node_VariableGet>(Graph) : nullptr;
		if (Node == nullptr)
		{
			return nullptr;
		}
		Node->VariableReference.SetSelfMember(PropertyName);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UK2Node_VariableGet* AddExternalVariableGet(
		UEdGraph* Graph, UClass* OwnerClass, const FName PropertyName, int32 X, int32 Y)
	{
		UK2Node_VariableGet* Node = Graph != nullptr
			? NewObject<UK2Node_VariableGet>(Graph) : nullptr;
		if (Node == nullptr || OwnerClass == nullptr
			|| OwnerClass->FindPropertyByName(PropertyName) == nullptr)
		{
			return nullptr;
		}
		Node->VariableReference.SetExternalMember(PropertyName, OwnerClass);
		Graph->AddNode(Node, false, false);
		Node->CreateNewGuid();
		Node->PostPlacedNewNode();
		Node->AllocateDefaultPins();
		Node->NodePosX = X;
		Node->NodePosY = Y;
		return Node;
	}

	UEdGraphPin* Pin(UEdGraphNode* Node, const FName Name, EEdGraphPinDirection Direction)
	{
		return Node != nullptr ? Node->FindPin(Name, Direction) : nullptr;
	}

	bool Connect(const UEdGraphSchema_K2* Schema, UEdGraphPin* A, UEdGraphPin* B)
	{
		return Schema != nullptr && A != nullptr && B != nullptr
			&& Schema->TryCreateConnection(A, B);
	}

	UEdGraph* FunctionGraph(UBlueprint* Blueprint, const FName Name)
	{
		if (Blueprint == nullptr)
		{
			return nullptr;
		}
		for (UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph != nullptr && Graph->GetFName() == Name)
			{
				return Graph;
			}
		}
		return nullptr;
	}

	UK2Node_FunctionEntry* ResetFunctionGraph(UEdGraph* Graph)
	{
		UK2Node_FunctionEntry* Entry = nullptr;
		if (Graph == nullptr)
		{
			return nullptr;
		}
		for (UEdGraphNode* Existing : TArray<UEdGraphNode*>(Graph->Nodes))
		{
			if (UK2Node_FunctionEntry* Candidate = Cast<UK2Node_FunctionEntry>(Existing))
			{
				Entry = Candidate;
			}
			else
			{
				Graph->RemoveNode(Existing);
			}
		}
		return Entry;
	}

	bool BuildOpenDetailsGraph(UBlueprint* Root, UClass* DetailClass)
	{
		UEdGraph* Graph = FunctionGraph(Root, OpenDetailsName);
		UK2Node_FunctionEntry* Entry = ResetFunctionGraph(Graph);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		UK2Node_VariableGet* Stack = AddVariableGet(Graph, StackName, 0, 120);
		UK2Node_CallFunction* Push = AddCall(Graph,
			UCommonActivatableWidgetContainerBase::StaticClass(), TEXT("BP_AddWidget"), 280, 0);
		UEdGraphPin* ClassPin = Pin(Push, TEXT("ActivatableWidgetClass"), EGPD_Input);
		if (Entry == nullptr || Schema == nullptr || Stack == nullptr || Push == nullptr
			|| ClassPin == nullptr || DetailClass == nullptr
			|| !Connect(Schema, Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Push, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			|| !Connect(Schema, Pin(Stack, StackName, EGPD_Output),
				Pin(Push, UEdGraphSchema_K2::PN_Self, EGPD_Input)))
		{
			return false;
		}
		Schema->TrySetDefaultObject(*ClassPin, DetailClass);
		return ClassPin->DefaultObject == DetailClass;
	}

	struct FActiveDeactivateNodes
	{
		UK2Node_VariableGet* Stack = nullptr;
		UK2Node_CallFunction* Active = nullptr;
		UK2Node_CallFunction* Deactivate = nullptr;
		UEdGraphPin* FirstExec = nullptr;
	};

	FActiveDeactivateNodes AddActiveDeactivate(
		UEdGraph* Graph, const UEdGraphSchema_K2* Schema, int32 X, int32 Y)
	{
		FActiveDeactivateNodes Nodes;
		Nodes.Stack = AddVariableGet(Graph, StackName, X, Y + 150);
		Nodes.Active = AddCall(Graph, UCommonActivatableWidgetContainerBase::StaticClass(),
			TEXT("GetActiveWidget"), X + 220, Y + 150);
		Nodes.Deactivate = AddCall(Graph, UCommonActivatableWidget::StaticClass(),
			TEXT("DeactivateWidget"), X + 470, Y);
		UEdGraphPin* ActiveExec = Pin(Nodes.Active, UEdGraphSchema_K2::PN_Execute, EGPD_Input);
		UEdGraphPin* ActiveThen = Pin(Nodes.Active, UEdGraphSchema_K2::PN_Then, EGPD_Output);
		UEdGraphPin* DeactivateExec = Pin(
			Nodes.Deactivate, UEdGraphSchema_K2::PN_Execute, EGPD_Input);
		if (Nodes.Stack == nullptr || Nodes.Active == nullptr || Nodes.Deactivate == nullptr
			|| DeactivateExec == nullptr || ((ActiveExec == nullptr) != (ActiveThen == nullptr))
			|| !Connect(Schema, Pin(Nodes.Stack, StackName, EGPD_Output),
				Pin(Nodes.Active, UEdGraphSchema_K2::PN_Self, EGPD_Input))
			|| !Connect(Schema, Pin(Nodes.Active, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(Nodes.Deactivate, UEdGraphSchema_K2::PN_Self, EGPD_Input))
			|| (ActiveThen != nullptr && !Connect(Schema, ActiveThen, DeactivateExec)))
		{
			return {};
		}
		Nodes.FirstExec = ActiveExec != nullptr ? ActiveExec : DeactivateExec;
		return Nodes;
	}

	bool BuildDismissGraph(UBlueprint* Root)
	{
		UEdGraph* Graph = FunctionGraph(Root, DismissTopName);
		UK2Node_FunctionEntry* Entry = ResetFunctionGraph(Graph);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		const FActiveDeactivateNodes Nodes = AddActiveDeactivate(Graph, Schema, 0, 0);
		return Entry != nullptr && Nodes.Deactivate != nullptr
			&& Connect(Schema, Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Nodes.FirstExec);
	}

	bool BuildCloseGraph(UBlueprint* Root)
	{
		UEdGraph* Graph = FunctionGraph(Root, CloseMenuName);
		UK2Node_FunctionEntry* Entry = ResetFunctionGraph(Graph);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		const FActiveDeactivateNodes Active = AddActiveDeactivate(Graph, Schema, 0, 0);
		UK2Node_CallFunction* DeactivateRoot = AddCall(
			Graph, UCommonActivatableWidget::StaticClass(), TEXT("DeactivateWidget"), 740, 0);
		UK2Node_CallFunction* RemoveRoot = AddCall(
			Graph, UWidget::StaticClass(), TEXT("RemoveFromParent"), 1010, 0);
		return Entry != nullptr && Active.Deactivate != nullptr
			&& DeactivateRoot != nullptr && RemoveRoot != nullptr
			&& Connect(Schema, Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Active.FirstExec)
			&& Connect(Schema, Pin(Active.Deactivate, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(DeactivateRoot, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			&& Connect(Schema, Pin(DeactivateRoot, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(RemoveRoot, UEdGraphSchema_K2::PN_Execute, EGPD_Input));
	}

	UEdGraph* ResetEventGraph(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
		if (Graph == nullptr && Blueprint != nullptr && !Blueprint->UbergraphPages.IsEmpty())
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

	bool BuildHomeFocusGraph(UBlueprint* Home)
	{
		UEdGraph* Graph = ResetEventGraph(Home);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		int32 EventY = 0;
		UK2Node_Event* Activated = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(Home, Graph,
				TEXT("BP_OnActivated"), UCommonActivatableWidget::StaticClass(), EventY)
			: nullptr;
		UK2Node_VariableGet* Button = AddVariableGet(Graph, HomeButtonName, 0, 150);
		UK2Node_CallFunction* SetDesired = AddCall(
			Graph, UUserWidget::StaticClass(), TEXT("SetDesiredFocusWidget"), 300, 0);
		return Activated != nullptr && Button != nullptr && SetDesired != nullptr
			&& Connect(Schema, Pin(Activated, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(SetDesired, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			&& Connect(Schema, Pin(Button, HomeButtonName, EGPD_Output),
				Pin(SetDesired, TEXT("Widget"), EGPD_Input));
	}

	UK2Node_SwitchEnum* AddChoiceSwitch(UEdGraph* Graph, int32 X, int32 Y)
	{
		UK2Node_SwitchEnum* SwitchNode = Graph != nullptr
			? NewObject<UK2Node_SwitchEnum>(Graph) : nullptr;
		if (SwitchNode == nullptr)
		{
			return nullptr;
		}
		SwitchNode->SetEnum(StaticEnum<EMenuFocusChoice>());
		Graph->AddNode(SwitchNode, false, false);
		SwitchNode->CreateNewGuid();
		SwitchNode->PostPlacedNewNode();
		SwitchNode->AllocateDefaultPins();
		SwitchNode->NodePosX = X;
		SwitchNode->NodePosY = Y;
		return SwitchNode;
	}

	bool BuildDetailFocusGraph(UBlueprint* Detail)
	{
		UEdGraph* Graph = ResetEventGraph(Detail);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		int32 EventY = 0;
		UK2Node_Event* Activated = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(Detail, Graph,
				TEXT("BP_OnActivated"), UCommonActivatableWidget::StaticClass(), EventY)
			: nullptr;
		UK2Node_CallFunction* GetPolicy = AddCall(
			Graph, UGameplayStatics::StaticClass(), TEXT("GetActorOfClass"), 10, 80);
		UK2Node_VariableGet* Choice = AddExternalVariableGet(Graph,
			AMenuFocusPolicy::StaticClass(), GET_MEMBER_NAME_CHECKED(
				AMenuFocusPolicy, PreferredDetailAction), 330, 190);
		UK2Node_SwitchEnum* ChoiceSwitch = AddChoiceSwitch(Graph, 590, 80);
		UK2Node_VariableGet* Primary = AddVariableGet(Graph, DetailPrimaryName, 820, -40);
		UK2Node_VariableGet* Alternate = AddVariableGet(Graph, DetailAlternateName, 820, 230);
		UK2Node_CallFunction* FocusPrimary = AddCall(
			Graph, UUserWidget::StaticClass(), TEXT("SetDesiredFocusWidget"), 1100, -80);
		UK2Node_CallFunction* FocusAlternate = AddCall(
			Graph, UUserWidget::StaticClass(), TEXT("SetDesiredFocusWidget"), 1100, 190);
		UEdGraphPin* ActorClassPin = Pin(GetPolicy, TEXT("ActorClass"), EGPD_Input);
		if (Activated == nullptr || Schema == nullptr || GetPolicy == nullptr
			|| Choice == nullptr || ChoiceSwitch == nullptr
			|| Primary == nullptr || Alternate == nullptr
			|| FocusPrimary == nullptr || FocusAlternate == nullptr
			|| ActorClassPin == nullptr)
		{
			return false;
		}
		Schema->TrySetDefaultObject(*ActorClassPin, AMenuFocusPolicy::StaticClass());
		if (ActorClassPin->DefaultObject != AMenuFocusPolicy::StaticClass()
			|| !Connect(Schema, Pin(Activated, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(GetPolicy, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			|| !Connect(Schema, Pin(GetPolicy, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				ChoiceSwitch->GetExecPin())
			|| !Connect(Schema, Pin(GetPolicy, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(Choice, UEdGraphSchema_K2::PN_Self, EGPD_Input))
			|| !Connect(Schema, Pin(Choice, GET_MEMBER_NAME_CHECKED(
					AMenuFocusPolicy, PreferredDetailAction), EGPD_Output),
				ChoiceSwitch->GetSelectionPin())
			|| !Connect(Schema, Pin(ChoiceSwitch, TEXT("Primary"), EGPD_Output),
				Pin(FocusPrimary, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			|| !Connect(Schema, Pin(ChoiceSwitch, TEXT("Alternate"), EGPD_Output),
				Pin(FocusAlternate, UEdGraphSchema_K2::PN_Execute, EGPD_Input))
			|| !Connect(Schema, Pin(Primary, DetailPrimaryName, EGPD_Output),
				Pin(FocusPrimary, TEXT("Widget"), EGPD_Input))
			|| !Connect(Schema, Pin(Alternate, DetailAlternateName, EGPD_Output),
				Pin(FocusAlternate, TEXT("Widget"), EGPD_Input)))
		{
			return false;
		}
		return true;
	}

	bool ValidateCommon(UBlueprint* Root, UBlueprint* Home, UBlueprint* Detail)
	{
		if (Root == nullptr || Home == nullptr || Detail == nullptr)
		{
			return AuthoringFail(TEXT("ASSET_MISSING"), TaskPackageRoot);
		}
		for (UBlueprint* Blueprint : {Root, Home, Detail})
		{
			if (Blueprint->ParentClass == nullptr
				|| !Blueprint->ParentClass->IsChildOf(UCommonActivatableWidget::StaticClass())
				|| GetWidgetTree(Blueprint) == nullptr)
			{
				return AuthoringFail(TEXT("WRONG_PARENT_OR_TREE"), Blueprint->GetPathName());
			}
		}
		UWidgetTree* HomeTree = GetWidgetTree(Home);
		UWidgetTree* DetailTree = GetWidgetTree(Detail);
		UButton* HomeButton = Cast<UButton>(HomeTree->FindWidget(HomeButtonName));
		UButton* DetailPrimary = Cast<UButton>(DetailTree->FindWidget(DetailPrimaryName));
		UButton* DetailAlternate = Cast<UButton>(DetailTree->FindWidget(DetailAlternateName));
		if (HomeButton == nullptr || DetailPrimary == nullptr || DetailAlternate == nullptr
			|| FunctionGraph(Root, OpenDetailsName) == nullptr
			|| FunctionGraph(Root, DismissTopName) == nullptr
			|| FunctionGraph(Root, CloseMenuName) == nullptr
			|| !HasValidWidgetGuid(Home, HomeButtonName)
			|| !HasValidWidgetGuid(Detail, DetailPrimaryName)
			|| !HasValidWidgetGuid(Detail, DetailAlternateName))
		{
			return AuthoringFail(TEXT("BASELINE_CONTRACT_MISSING"), TaskPackageRoot);
		}
		return true;
	}

	bool ValidateReference(UBlueprint* Root, UBlueprint* Home, UBlueprint* Detail)
	{
		if (!ValidateCommon(Root, Home, Detail))
		{
			return false;
		}
		UWidgetTree* RootTree = GetWidgetTree(Root);
		UWidgetTree* HomeTree = GetWidgetTree(Home);
		UWidgetTree* DetailTree = GetWidgetTree(Detail);
		UCommonActivatableWidgetStack* Stack = Cast<UCommonActivatableWidgetStack>(
			RootTree->FindWidget(StackName));
		UButton* HomeButton = Cast<UButton>(HomeTree->FindWidget(HomeButtonName));
		UButton* DetailPrimary = Cast<UButton>(DetailTree->FindWidget(DetailPrimaryName));
		UButton* DetailAlternate = Cast<UButton>(DetailTree->FindWidget(DetailAlternateName));
		FClassProperty* RootContent = Stack != nullptr
			? FindFProperty<FClassProperty>(Stack->GetClass(), TEXT("RootContentWidgetClass"))
			: nullptr;
		UClass* DeclaredHome = RootContent != nullptr
			? Cast<UClass>(RootContent->GetObjectPropertyValue_InContainer(Stack)) : nullptr;
		UEdGraph* OpenGraph = FunctionGraph(Root, OpenDetailsName);
		UEdGraph* DismissGraph = FunctionGraph(Root, DismissTopName);
		UEdGraph* CloseGraph = FunctionGraph(Root, CloseMenuName);
		UEdGraph* HomeEventGraph = FBlueprintEditorUtils::FindEventGraph(Home);
		UEdGraph* DetailEventGraph = FBlueprintEditorUtils::FindEventGraph(Detail);
		const bool bGraphsPopulated = OpenGraph != nullptr && DismissGraph != nullptr
			&& CloseGraph != nullptr && HomeEventGraph != nullptr && DetailEventGraph != nullptr
			&& OpenGraph->Nodes.Num() > 1 && DismissGraph->Nodes.Num() > 1
			&& CloseGraph->Nodes.Num() > 1 && HomeEventGraph->Nodes.Num() > 0
			&& DetailEventGraph->Nodes.Num() > 0;
		if (Stack == nullptr || RootContent == nullptr || DeclaredHome != Home->GeneratedClass
			|| !HasValidWidgetGuid(Root, StackName)
			|| HomeButton == nullptr || DetailPrimary == nullptr || DetailAlternate == nullptr
			|| !HomeButton->GetIsFocusable() || !DetailPrimary->GetIsFocusable()
			|| !DetailAlternate->GetIsFocusable() || !bGraphsPopulated)
		{
			return AuthoringFail(TEXT("REFERENCE_READBACK_FAILED"), TaskPackageRoot);
		}
		return true;
	}
}

bool UFocusStackAssetAuthoring::CreateBaselineAssets()
{
	UBlueprint* Root = CreateWidgetBlueprint(RootAssetName);
	UBlueprint* Home = CreateWidgetBlueprint(HomeAssetName);
	UBlueprint* Detail = CreateWidgetBlueprint(DetailAssetName);
	if (Root == nullptr || Home == nullptr || Detail == nullptr
		|| !BuildRootBaseline(Root) || !BuildHomeBaseline(Home) || !BuildDetailBaseline(Detail)
		|| !RegisterAllWidgetGuids(Root) || !RegisterAllWidgetGuids(Home)
		|| !RegisterAllWidgetGuids(Detail)
		|| !SaveBlueprint(Root) || !SaveBlueprint(Home) || !SaveBlueprint(Detail)
		|| !ValidateCommon(Root, Home, Detail))
	{
		return AuthoringFail(TEXT("BASELINE_BUILD_FAILED"), TaskPackageRoot);
	}
	UE_LOG(LogFocusStackAssetAuthoring, Display,
		TEXT("FOCUS-ASSET-AUTHORING BASELINE-DONE root=%s home=%s detail=%s"),
		*Root->GetPathName(), *Home->GetPathName(), *Detail->GetPathName());
	return true;
}

bool UFocusStackAssetAuthoring::BuildReferenceAssets()
{
	UBlueprint* Root = LoadTaskBlueprint(RootAssetName);
	UBlueprint* Home = LoadTaskBlueprint(HomeAssetName);
	UBlueprint* Detail = LoadTaskBlueprint(DetailAssetName);
	if (!ValidateCommon(Root, Home, Detail))
	{
		return false;
	}

	UWidgetTree* RootTree = GetWidgetTree(Root);
	UWidgetTree* HomeTree = GetWidgetTree(Home);
	UWidgetTree* DetailTree = GetWidgetTree(Detail);
	UOverlay* RootLayout = RootTree != nullptr ? Cast<UOverlay>(RootTree->RootWidget) : nullptr;
	UButton* HomeButton = HomeTree != nullptr
		? Cast<UButton>(HomeTree->FindWidget(HomeButtonName)) : nullptr;
	UButton* DetailPrimary = DetailTree != nullptr
		? Cast<UButton>(DetailTree->FindWidget(DetailPrimaryName)) : nullptr;
	UButton* DetailAlternate = DetailTree != nullptr
		? Cast<UButton>(DetailTree->FindWidget(DetailAlternateName)) : nullptr;
	UCommonActivatableWidgetStack* Stack = RootTree != nullptr
		? RootTree->ConstructWidget<UCommonActivatableWidgetStack>(
			UCommonActivatableWidgetStack::StaticClass(), StackName)
		: nullptr;
	if (RootLayout == nullptr || HomeButton == nullptr || DetailPrimary == nullptr
		|| DetailAlternate == nullptr || Stack == nullptr || Home->GeneratedClass == nullptr
		|| Detail->GeneratedClass == nullptr
		|| !SetBoolProperty(HomeButton, TEXT("IsFocusable"), true)
		|| !SetBoolProperty(DetailPrimary, TEXT("IsFocusable"), true)
		|| !SetBoolProperty(DetailAlternate, TEXT("IsFocusable"), true)
		|| !SetClassProperty(Stack, TEXT("RootContentWidgetClass"), Home->GeneratedClass))
	{
		return AuthoringFail(TEXT("REFERENCE_TREE_EDIT_FAILED"), TaskPackageRoot);
	}
	Stack->bIsVariable = true;
	Stack->SetTransitionDuration(0.0f);
	RootLayout->AddChildToOverlay(Stack);
	if (!RegisterAllWidgetGuids(Root)
		|| !RegisterAllWidgetGuids(Home)
		|| !RegisterAllWidgetGuids(Detail))
	{
		return AuthoringFail(TEXT("WIDGET_GUID_REGISTRATION_FAILED"), TaskPackageRoot);
	}

	// Compile the tree additions first so the generated ScreenStack/button
	// properties exist when the K2 variable nodes are allocated.
	if (!SaveBlueprint(Root) || !SaveBlueprint(Home) || !SaveBlueprint(Detail)
		|| !BuildHomeFocusGraph(Home)
		|| !BuildDetailFocusGraph(Detail)
		|| !SaveBlueprint(Home) || !SaveBlueprint(Detail)
		// Home/Detail compilation may reinstate their generated classes. Pin the
		// final class identities only after those compiles, then compile Root.
		|| !SetClassProperty(Stack, TEXT("RootContentWidgetClass"), Home->GeneratedClass)
		|| !BuildOpenDetailsGraph(Root, Detail->GeneratedClass)
		|| !BuildDismissGraph(Root)
		|| !BuildCloseGraph(Root)
		|| !SaveBlueprint(Root)
		|| !ValidateReference(Root, Home, Detail))
	{
		return AuthoringFail(TEXT("REFERENCE_BUILD_FAILED"), TaskPackageRoot);
	}
	UE_LOG(LogFocusStackAssetAuthoring, Display,
		TEXT("FOCUS-ASSET-AUTHORING REFERENCE-DONE root=%s home=%s detail=%s"),
		*Root->GetPathName(), *Home->GetPathName(), *Detail->GetPathName());
	return true;
}

bool UFocusStackAssetAuthoring::ValidateBaselineAssets()
{
	UBlueprint* Root = LoadTaskBlueprint(RootAssetName);
	UBlueprint* Home = LoadTaskBlueprint(HomeAssetName);
	UBlueprint* Detail = LoadTaskBlueprint(DetailAssetName);
	if (!ValidateCommon(Root, Home, Detail))
	{
		return false;
	}
	UButton* HomeButton = Cast<UButton>(GetWidgetTree(Home)->FindWidget(HomeButtonName));
	UButton* DetailPrimary = Cast<UButton>(GetWidgetTree(Detail)->FindWidget(DetailPrimaryName));
	UButton* DetailAlternate = Cast<UButton>(GetWidgetTree(Detail)->FindWidget(DetailAlternateName));
	const bool bUntouched = HomeButton != nullptr && DetailPrimary != nullptr
		&& DetailAlternate != nullptr && !HomeButton->GetIsFocusable()
		&& !DetailPrimary->GetIsFocusable() && !DetailAlternate->GetIsFocusable()
		&& GetWidgetTree(Root)->FindWidget(StackName) == nullptr
		&& FunctionGraph(Root, OpenDetailsName)->Nodes.Num() == 1
		&& FunctionGraph(Root, DismissTopName)->Nodes.Num() == 1
		&& FunctionGraph(Root, CloseMenuName)->Nodes.Num() == 1;
	if (!bUntouched)
	{
		return AuthoringFail(TEXT("BASELINE_READBACK_FAILED"), TaskPackageRoot);
	}
	UE_LOG(LogFocusStackAssetAuthoring, Display,
		TEXT("FOCUS-ASSET-AUTHORING BASELINE-READBACK-OK"));
	return true;
}

bool UFocusStackAssetAuthoring::ValidateReferenceAssets()
{
	const bool bValid = ValidateReference(
		LoadTaskBlueprint(RootAssetName),
		LoadTaskBlueprint(HomeAssetName),
		LoadTaskBlueprint(DetailAssetName));
	if (bValid)
	{
		UE_LOG(LogFocusStackAssetAuthoring, Display,
			TEXT("FOCUS-ASSET-AUTHORING REFERENCE-READBACK-OK"));
	}
	return bValid;
}
