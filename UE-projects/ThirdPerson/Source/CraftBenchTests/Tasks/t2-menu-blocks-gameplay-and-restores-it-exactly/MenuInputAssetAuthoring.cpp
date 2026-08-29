// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputAssetAuthoring.h"

#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputFunctionalTest.h"
#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputRuntime.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Dom/JsonObject.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "EnhancedInputSubsystems.h"
#include "Factories/Factory.h"
#include "FunctionalTest.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "K2Node.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_MakeStruct.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogMenuInputAssetAuthoring, Log, All);

namespace
{
	const FString TaskRoot =
		TEXT("/Game/Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly");
	const FString SupportRoot =
		TEXT("/Game/Maps/t2-menu-blocks-gameplay-and-restores-it-exactly/Support");
	const FName MenuAssetName(TEXT("WBP_InputBlockingMenu"));
	const FName StoredContextName(TEXT("AppliedMenuContext"));
	const TCHAR* AdmissionMapPackage =
		TEXT("/Game/Maps/t2-menu-blocks-gameplay-and-restores-it-exactly/L_MenuInputRouting");
	const TCHAR* StockGameModeClassPath =
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C");
	const TCHAR* StockPawnClassPath =
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C");
	const TCHAR* StockPlayerControllerClassPath =
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController.BP_ThirdPersonPlayerController_C");

	const FName GameplayActionName(TEXT("IA_GameplayProbe"));
	const FName MenuActionName(TEXT("IA_MenuProbe"));
	const FName UnrelatedActionName(TEXT("IA_UnrelatedProbe"));

	struct FContextRecipe
	{
		FName Name;
		FName ActionName;
		FKey Key;
	};

	const FContextRecipe ContextRecipes[] = {
		{ TEXT("IMC_GameplayQuartz"), GameplayActionName, EKeys::E },
		{ TEXT("IMC_MenuQuartz"), MenuActionName, EKeys::E },
		{ TEXT("IMC_UnrelatedQuartz"), UnrelatedActionName, EKeys::U },
		{ TEXT("IMC_GameplayViolet"), GameplayActionName, EKeys::Q },
		{ TEXT("IMC_MenuViolet"), MenuActionName, EKeys::Q },
		{ TEXT("IMC_UnrelatedViolet"), UnrelatedActionName, EKeys::U },
	};

	bool Fail(const TCHAR* Reason, const FString& Detail)
	{
		UE_LOG(LogMenuInputAssetAuthoring, Error,
			TEXT("MENU-INPUT-ASSET-AUTHORING FAILED reason=%s detail=%s"),
			Reason, *Detail);
		return false;
	}

	FString PackagePath(const FString& Root, const FName Name)
	{
		return Root + TEXT("/") + Name.ToString();
	}

	FString ObjectPath(const FString& Root, const FName Name)
	{
		return FString::Printf(TEXT("%s/%s.%s"), *Root,
			*Name.ToString(), *Name.ToString());
	}

	bool PackageExists(const FString& Root, const FName Name)
	{
		const FString Package = PackagePath(Root, Name);
		return FindPackage(nullptr, *Package) != nullptr ||
			FPackageName::DoesPackageExist(Package);
	}

	bool SaveAsset(UObject* Asset)
	{
		if (Asset == nullptr || Asset->GetOutermost() == nullptr)
		{
			return Fail(TEXT("NULL_ASSET"), GetNameSafe(Asset));
		}
		UPackage* Package = Asset->GetOutermost();
		Package->MarkPackageDirty();
		const FString Filename = FPackageName::LongPackageNameToFilename(
			Package->GetName(), FPackageName::GetAssetPackageExtension());
		FSavePackageArgs Args;
		Args.TopLevelFlags = RF_Public | RF_Standalone;
		Args.SaveFlags = SAVE_NoError;
		Args.Error = GError;
		if (!UPackage::SavePackage(Package, Asset, *Filename, Args))
		{
			return Fail(TEXT("SAVE_FAILED"), Filename);
		}
		return true;
	}

	bool SaveBlueprint(UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return Fail(TEXT("NULL_BLUEPRINT"), TEXT("WBP_InputBlockingMenu"));
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
		if (Blueprint->Status != BS_UpToDate && Blueprint->Status != BS_UpToDateWithWarnings)
		{
			return Fail(TEXT("BLUEPRINT_COMPILE_FAILED"),
				FString::Printf(TEXT("status=%d"), static_cast<int32>(Blueprint->Status)));
		}
		return SaveAsset(Blueprint);
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
		if (Graph == nullptr || OwnerClass == nullptr ||
			OwnerClass->FindFunctionByName(FunctionName) == nullptr)
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

	template <typename TVariableNode>
	TVariableNode* AddSelfVariable(
		UEdGraph* Graph, const FName VariableName, int32 X, int32 Y)
	{
		TVariableNode* Node = Graph != nullptr
			? NewObject<TVariableNode>(Graph) : nullptr;
		if (Node == nullptr)
		{
			return nullptr;
		}
		Node->VariableReference.SetSelfMember(VariableName);
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

	UEdGraphPin* StructPin(
		UEdGraphNode* Node, UScriptStruct* Struct, EEdGraphPinDirection Direction)
	{
		if (Node == nullptr || Struct == nullptr)
		{
			return nullptr;
		}
		for (UEdGraphPin* Candidate : Node->Pins)
		{
			if (Candidate != nullptr && Candidate->Direction == Direction &&
				Candidate->PinType.PinCategory == UEdGraphSchema_K2::PC_Struct &&
				Candidate->PinType.PinSubCategoryObject == Struct)
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

	bool BuildLifecycleGraph(UBlueprint* Blueprint)
	{
		UEdGraph* Graph = ResetEventGraph(Blueprint);
		const UEdGraphSchema_K2* Schema = Graph != nullptr
			? Cast<UEdGraphSchema_K2>(Graph->GetSchema()) : nullptr;
		int32 ActivatedY = 0;
		int32 DeactivatedY = 520;
		UK2Node_Event* Activated = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(
				Blueprint, Graph, TEXT("BP_OnActivated"),
				UCommonActivatableWidget::StaticClass(), ActivatedY)
			: nullptr;
		UK2Node_Event* Deactivated = Graph != nullptr
			? FKismetEditorUtilities::AddDefaultEventNode(
				Blueprint, Graph, TEXT("BP_OnDeactivated"),
				UCommonActivatableWidget::StaticClass(), DeactivatedY)
			: nullptr;

		UK2Node_CallFunction* PolicyForActivate = AddCall(
			Graph, UInputBlockingMenuBase::StaticClass(), TEXT("GetMenuInputPolicy"), 0, 110);
		UK2Node_CallFunction* CurrentContext = AddCall(
			Graph, AMenuInputPolicy::StaticClass(), TEXT("GetCurrentMenuContext"), 250, 110);
		UK2Node_CallFunction* CurrentPriority = AddCall(
			Graph, AMenuInputPolicy::StaticClass(), TEXT("GetCurrentMenuPriority"), 250, 240);
		UK2Node_VariableSet* StoreContext = AddSelfVariable<UK2Node_VariableSet>(
			Graph, StoredContextName, 520, 0);
		UK2Node_CallFunction* SubsystemForActivate = AddCall(
			Graph, UInputBlockingMenuBase::StaticClass(), TEXT("GetMenuInputSubsystem"), 520, 240);
		UK2Node_VariableGet* StoredForAdd = AddSelfVariable<UK2Node_VariableGet>(
			Graph, StoredContextName, 790, 170);
		UK2Node_CallFunction* AddContext = AddCall(
			Graph, UEnhancedInputLocalPlayerSubsystem::StaticClass(),
			TEXT("AddMappingContext"), 1040, 0);

		UK2Node_CallFunction* SubsystemForRemove = AddCall(
			Graph, UInputBlockingMenuBase::StaticClass(), TEXT("GetMenuInputSubsystem"), 300, 690);
		UK2Node_VariableGet* StoredForRemove = AddSelfVariable<UK2Node_VariableGet>(
			Graph, StoredContextName, 300, 820);
		UK2Node_CallFunction* RemoveContext = AddCall(
			Graph, UEnhancedInputLocalPlayerSubsystem::StaticClass(),
			TEXT("RemoveMappingContext"), 620, 520);

		if (Activated == nullptr || Deactivated == nullptr || Schema == nullptr ||
			PolicyForActivate == nullptr || CurrentContext == nullptr ||
			CurrentPriority == nullptr || StoreContext == nullptr ||
			SubsystemForActivate == nullptr || StoredForAdd == nullptr ||
			AddContext == nullptr || SubsystemForRemove == nullptr ||
			StoredForRemove == nullptr || RemoveContext == nullptr)
		{
			return false;
		}

		return
			Connect(Schema, Pin(Activated, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(StoreContext, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(StoreContext, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(AddContext, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(PolicyForActivate, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(CurrentContext, UEdGraphSchema_K2::PN_Self, EGPD_Input)) &&
			Connect(Schema, Pin(PolicyForActivate, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(CurrentPriority, UEdGraphSchema_K2::PN_Self, EGPD_Input)) &&
			Connect(Schema, Pin(CurrentContext, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(StoreContext, StoredContextName, EGPD_Input)) &&
			Connect(Schema, Pin(SubsystemForActivate, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(AddContext, UEdGraphSchema_K2::PN_Self, EGPD_Input)) &&
			Connect(Schema, Pin(StoredForAdd, StoredContextName, EGPD_Output),
				Pin(AddContext, TEXT("MappingContext"), EGPD_Input)) &&
			Connect(Schema, Pin(CurrentPriority, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(AddContext, TEXT("Priority"), EGPD_Input)) &&
			Connect(Schema, Pin(Deactivated, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(RemoveContext, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema, Pin(SubsystemForRemove, UEdGraphSchema_K2::PN_ReturnValue, EGPD_Output),
				Pin(RemoveContext, UEdGraphSchema_K2::PN_Self, EGPD_Input)) &&
			Connect(Schema, Pin(StoredForRemove, StoredContextName, EGPD_Output),
				Pin(RemoveContext, TEXT("MappingContext"), EGPD_Input));
	}

	bool BuildInputConfigOverride(UBlueprint* Blueprint)
	{
		const FName FunctionName(TEXT("BP_GetDesiredInputConfig"));
		if (Blueprint == nullptr || FindObject<UEdGraph>(Blueprint, *FunctionName.ToString()) != nullptr)
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
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(
			Blueprint, Graph, false, OverrideClass);
		UK2Node_FunctionEntry* Entry = nullptr;
		UK2Node_FunctionResult* Result = nullptr;
		for (UEdGraphNode* Existing : TArray<UEdGraphNode*>(Graph->Nodes))
		{
			if (UK2Node_FunctionEntry* EntryNode = Cast<UK2Node_FunctionEntry>(Existing))
			{
				Entry = EntryNode;
			}
			else if (UK2Node_FunctionResult* ResultNode = Cast<UK2Node_FunctionResult>(Existing))
			{
				Result = ResultNode;
			}
			else
			{
				Graph->RemoveNode(Existing);
			}
		}

		UK2Node_MakeStruct* MakeConfig = Graph != nullptr
			? NewObject<UK2Node_MakeStruct>(Graph) : nullptr;
		if (MakeConfig == nullptr)
		{
			return false;
		}
		MakeConfig->StructType = FUIInputConfig::StaticStruct();
		Graph->AddNode(MakeConfig, false, false);
		MakeConfig->CreateNewGuid();
		MakeConfig->PostPlacedNewNode();
		MakeConfig->AllocateDefaultPins();
		MakeConfig->NodePosX = 200;
		MakeConfig->NodePosY = 100;

		const UEdGraphSchema_K2* Schema = Cast<UEdGraphSchema_K2>(Graph->GetSchema());
		UEdGraphPin* ModePin = Pin(MakeConfig, TEXT("InputMode"), EGPD_Input);
		UEdGraphPin* CapturePin = Pin(MakeConfig, TEXT("MouseCaptureMode"), EGPD_Input);
		UEdGraphPin* LockPin = Pin(MakeConfig, TEXT("MouseLockMode"), EGPD_Input);
		if (Entry == nullptr || Result == nullptr || Schema == nullptr ||
			ModePin == nullptr || CapturePin == nullptr || LockPin == nullptr)
		{
			return false;
		}
		Schema->TrySetDefaultValue(*ModePin, TEXT("Menu"));
		Schema->TrySetDefaultValue(*CapturePin, TEXT("NoCapture"));
		Schema->TrySetDefaultValue(*LockPin, TEXT("DoNotLock"));
		return ModePin->DefaultValue == TEXT("Menu") &&
			CapturePin->DefaultValue == TEXT("NoCapture") &&
			LockPin->DefaultValue == TEXT("DoNotLock") &&
			Connect(Schema,
				Pin(Entry, UEdGraphSchema_K2::PN_Then, EGPD_Output),
				Pin(Result, UEdGraphSchema_K2::PN_Execute, EGPD_Input)) &&
			Connect(Schema,
				StructPin(MakeConfig, FUIInputConfig::StaticStruct(), EGPD_Output),
				StructPin(Result, FUIInputConfig::StaticStruct(), EGPD_Input));
	}

	bool ValidateEmptyBaselineEvent(
		const UK2Node_Event* Event, TSet<FName>& ObservedEvents, FString& OutDetail)
	{
		if (Event == nullptr)
		{
			OutDetail = TEXT("event is null");
			return false;
		}
		const FName EventName = Event->EventReference.GetMemberName();
		const TSet<FName> ExpectedEvents = {
			TEXT("PreConstruct"), TEXT("Construct"), TEXT("Tick")
		};
		UFunction* Signature = Event->FindEventSignatureFunction();
		if (!ExpectedEvents.Contains(EventName) || ObservedEvents.Contains(EventName) ||
			!Event->bOverrideFunction || !Event->CustomFunctionName.IsNone() ||
			Event->bInternalEvent || Signature == nullptr ||
			Signature->GetOwnerClass() != UUserWidget::StaticClass() ||
			Event->GetDesiredEnabledState() != ENodeEnabledState::Disabled ||
			Event->HasUserSetTheEnabledState())
		{
			OutDetail = FString::Printf(
				TEXT("name=%s duplicate=%d override=%d custom=%s internal=%d signature=%s enabled=%s user_enabled=%d"),
				*EventName.ToString(), ObservedEvents.Contains(EventName) ? 1 : 0,
				Event->bOverrideFunction ? 1 : 0, *Event->CustomFunctionName.ToString(),
				Event->bInternalEvent ? 1 : 0, *GetPathNameSafe(Signature),
				LexToString(Event->GetDesiredEnabledState()),
				Event->HasUserSetTheEnabledState() ? 1 : 0);
			return false;
		}
		for (const UEdGraphPin* EventPin : Event->Pins)
		{
			if (EventPin != nullptr && !EventPin->LinkedTo.IsEmpty())
			{
				OutDetail = FString::Printf(TEXT("name=%s linked_pin=%s links=%d"),
					*EventName.ToString(), *EventPin->PinName.ToString(),
					EventPin->LinkedTo.Num());
				return false;
			}
		}
		ObservedEvents.Add(EventName);
		return true;
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

	UInputAction* CreateAction(const FName Name)
	{
		UPackage* Package = CreatePackage(*PackagePath(SupportRoot, Name));
		UInputAction* Action = Package != nullptr
			? NewObject<UInputAction>(Package, Name,
				RF_Public | RF_Standalone | RF_Transactional)
			: nullptr;
		if (Action == nullptr)
		{
			Fail(TEXT("ACTION_CREATE_FAILED"), Name.ToString());
			return nullptr;
		}
		Action->ValueType = EInputActionValueType::Boolean;
		Action->bConsumeInput = true;
		FAssetRegistryModule::AssetCreated(Action);
		return SaveAsset(Action) ? Action : nullptr;
	}

	UInputMappingContext* CreateContext(
		const FContextRecipe& Recipe, const TMap<FName, UInputAction*>& Actions)
	{
		UInputAction* const* Action = Actions.Find(Recipe.ActionName);
		UPackage* Package = CreatePackage(*PackagePath(SupportRoot, Recipe.Name));
		UInputMappingContext* Context = Package != nullptr
			? NewObject<UInputMappingContext>(Package, Recipe.Name,
				RF_Public | RF_Standalone | RF_Transactional)
			: nullptr;
		if (Context == nullptr || Action == nullptr || *Action == nullptr)
		{
			Fail(TEXT("CONTEXT_CREATE_FAILED"), Recipe.Name.ToString());
			return nullptr;
		}
		Context->MapKey(*Action, Recipe.Key);
		FAssetRegistryModule::AssetCreated(Context);
		return SaveAsset(Context) ? Context : nullptr;
	}

	UWidgetTree* WidgetTree(UBlueprint* Blueprint)
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
		if (MapProperty == nullptr ||
			CastField<FNameProperty>(MapProperty->KeyProp) == nullptr)
		{
			return nullptr;
		}
		FStructProperty* GuidProperty = CastField<FStructProperty>(MapProperty->ValueProp);
		return GuidProperty != nullptr && GuidProperty->Struct != nullptr &&
			GuidProperty->Struct->GetFName() == TEXT("Guid")
			? MapProperty : nullptr;
	}

	bool RegisterAllWidgetGuids(UBlueprint* Blueprint)
	{
		UWidgetTree* Tree = WidgetTree(Blueprint);
		FMapProperty* MapProperty = WidgetGuidMapProperty(Blueprint);
		if (Tree == nullptr || MapProperty == nullptr)
		{
			return false;
		}
		bool bAllRegistered = true;
		Tree->ForEachWidget([Blueprint, MapProperty, &bAllRegistered](UWidget* Widget)
		{
			if (Widget == nullptr)
			{
				bAllRegistered = false;
				return;
			}
			FScriptMapHelper MapHelper(
				MapProperty, MapProperty->ContainerPtrToValuePtr<void>(Blueprint));
			const FName WidgetName = Widget->GetFName();
			if (const uint8* Existing = MapHelper.FindValueFromHash(&WidgetName))
			{
				bAllRegistered = reinterpret_cast<const FGuid*>(Existing)->IsValid() &&
					bAllRegistered;
				return;
			}
			const FGuid StableGuid = FGuid::NewDeterministicGuid(Widget->GetPathName());
			MapHelper.AddPair(&WidgetName, &StableGuid);
			const uint8* Added = MapHelper.FindValueFromHash(&WidgetName);
			bAllRegistered = Added != nullptr &&
				*reinterpret_cast<const FGuid*>(Added) == StableGuid && bAllRegistered;
		});
		return bAllRegistered;
	}

	UBlueprint* CreateBaselineMenu()
	{
		if (FModuleManager::Get().LoadModule(FName(TEXT("UMGEditor"))) == nullptr)
		{
			Fail(TEXT("UMG_EDITOR_UNAVAILABLE"), TEXT("UMGEditor"));
			return nullptr;
		}
		UClass* FactoryClass = LoadClass<UFactory>(
			nullptr, TEXT("/Script/UMGEditor.WidgetBlueprintFactory"));
		UFactory* Factory = FactoryClass != nullptr
			? NewObject<UFactory>(GetTransientPackage(), FactoryClass)
			: nullptr;
		if (Factory == nullptr || !SetClassProperty(
			Factory, TEXT("ParentClass"), UInputBlockingMenuBase::StaticClass()))
		{
			Fail(TEXT("WIDGET_FACTORY_FAILED"), MenuAssetName.ToString());
			return nullptr;
		}

		UPackage* Package = CreatePackage(*PackagePath(TaskRoot, MenuAssetName));
		UBlueprint* Blueprint = Package != nullptr
			? Cast<UBlueprint>(Factory->FactoryCreateNew(
				Factory->GetSupportedClass(), Package, MenuAssetName,
				RF_Public | RF_Standalone | RF_Transactional, nullptr, GWarn))
			: nullptr;
		if (Blueprint == nullptr)
		{
			Fail(TEXT("WIDGET_BLUEPRINT_CREATE_FAILED"), MenuAssetName.ToString());
			return nullptr;
		}
		FAssetRegistryModule::AssetCreated(Blueprint);

		FEdGraphPinType ContextType;
		ContextType.PinCategory = UEdGraphSchema_K2::PC_Object;
		ContextType.PinSubCategoryObject = UInputMappingContext::StaticClass();
		if (!FBlueprintEditorUtils::AddMemberVariable(
			Blueprint, StoredContextName, ContextType, FString()))
		{
			Fail(TEXT("STORED_CONTEXT_VARIABLE_FAILED"), StoredContextName.ToString());
			return nullptr;
		}

		UWidgetTree* Tree = WidgetTree(Blueprint);
		UVerticalBox* Layout = Tree != nullptr
			? Tree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("MenuPanel"))
			: nullptr;
		UTextBlock* Heading = Tree != nullptr
			? Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Text_MenuHeading"))
			: nullptr;
		UTextBlock* Help = Tree != nullptr
			? Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Text_MenuHelp"))
			: nullptr;
		UButton* Close = Tree != nullptr
			? Tree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("Button_CloseMenu"))
			: nullptr;
		UTextBlock* CloseLabel = Tree != nullptr
			? Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Text_CloseLabel"))
			: nullptr;
		if (Tree == nullptr || Layout == nullptr || Heading == nullptr || Help == nullptr ||
			Close == nullptr || CloseLabel == nullptr)
		{
			Fail(TEXT("WIDGET_TREE_CREATE_FAILED"), MenuAssetName.ToString());
			return nullptr;
		}
		Heading->SetText(FText::FromString(TEXT("INPUT ROUTING MENU")));
		Help->SetText(FText::FromString(
			TEXT("The shared action belongs to this top screen while it is open.")));
		CloseLabel->SetText(FText::FromString(TEXT("Close")));
		FBoolProperty* FocusableProperty = FindFProperty<FBoolProperty>(
			UButton::StaticClass(), TEXT("IsFocusable"));
		if (FocusableProperty == nullptr)
		{
			Fail(TEXT("BUTTON_FOCUSABLE_PROPERTY_MISSING"), Close->GetPathName());
			return nullptr;
		}
		FocusableProperty->SetPropertyValue_InContainer(Close, true);
		if (!Close->GetIsFocusable())
		{
			Fail(TEXT("BUTTON_FOCUSABLE_READBACK_FAILED"), Close->GetPathName());
			return nullptr;
		}
		Close->AddChild(CloseLabel);
		Layout->AddChild(Heading);
		Layout->AddChild(Help);
		Layout->AddChild(Close);
		Tree->RootWidget = Layout;
		if (!RegisterAllWidgetGuids(Blueprint))
		{
			Fail(TEXT("WIDGET_GUID_REGISTRATION_FAILED"), MenuAssetName.ToString());
			return nullptr;
		}
		return SaveBlueprint(Blueprint) ? Blueprint : nullptr;
	}

	UBlueprint* LoadMenuBlueprint()
	{
		return LoadObject<UBlueprint>(nullptr, *ObjectPath(TaskRoot, MenuAssetName));
	}

	UInputAction* LoadAction(const FName Name)
	{
		return LoadObject<UInputAction>(nullptr, *ObjectPath(SupportRoot, Name));
	}

	UInputMappingContext* LoadContext(const FName Name)
	{
		return LoadObject<UInputMappingContext>(nullptr, *ObjectPath(SupportRoot, Name));
	}

	bool HasStoredContextVariable(const UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
		{
			if (Variable.VarName == StoredContextName &&
				Variable.VarType.PinCategory == UEdGraphSchema_K2::PC_Object &&
				Variable.VarType.PinSubCategoryObject == UInputMappingContext::StaticClass())
			{
				return true;
			}
		}
		return false;
	}

	TSet<const UEdGraphNode*> ExecReachableFromEvent(
		const UBlueprint* Blueprint, const FName EventName)
	{
		TSet<const UEdGraphNode*> Reachable;
		TArray<const UEdGraphNode*> Queue;
		if (Blueprint == nullptr)
		{
			return Reachable;
		}
		TArray<UEdGraph*> Graphs;
		Blueprint->GetAllGraphs(Graphs);
		for (const UEdGraph* Graph : Graphs)
		{
			if (Graph == nullptr)
			{
				continue;
			}
			for (const UEdGraphNode* Node : Graph->Nodes)
			{
				const UK2Node_Event* Event = Cast<UK2Node_Event>(Node);
				if (Event != nullptr && Event->EventReference.GetMemberName() == EventName)
				{
					Reachable.Add(Event);
					Queue.Add(Event);
				}
			}
		}
		while (!Queue.IsEmpty())
		{
			const UEdGraphNode* Node = Queue.Pop(EAllowShrinking::No);
			for (const UEdGraphPin* Pin : Node->Pins)
			{
				if (Pin == nullptr || Pin->Direction != EGPD_Output ||
					Pin->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec)
				{
					continue;
				}
				for (const UEdGraphPin* Linked : Pin->LinkedTo)
				{
					const UEdGraphNode* Next = Linked != nullptr ? Linked->GetOwningNode() : nullptr;
					if (Next != nullptr && !Reachable.Contains(Next))
					{
						Reachable.Add(Next);
						Queue.Add(Next);
					}
				}
			}
		}
		return Reachable;
	}

	TSet<const UEdGraphNode*> IncludeInputDependencies(
		const TSet<const UEdGraphNode*>& ExecReachable)
	{
		TSet<const UEdGraphNode*> Result = ExecReachable;
		TArray<const UEdGraphNode*> Queue = Result.Array();
		while (!Queue.IsEmpty())
		{
			const UEdGraphNode* Node = Queue.Pop(EAllowShrinking::No);
			for (const UEdGraphPin* Pin : Node->Pins)
			{
				if (Pin == nullptr || Pin->Direction != EGPD_Input)
				{
					continue;
				}
				for (const UEdGraphPin* Linked : Pin->LinkedTo)
				{
					const UEdGraphNode* Dependency = Linked != nullptr
						? Linked->GetOwningNode() : nullptr;
					if (Dependency != nullptr && !Result.Contains(Dependency))
					{
						Result.Add(Dependency);
						Queue.Add(Dependency);
					}
				}
			}
		}
		return Result;
	}

	bool ReachableCall(const TSet<const UEdGraphNode*>& Nodes, const FName FunctionName)
	{
		for (const UEdGraphNode* Node : Nodes)
		{
			const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
			if (Call != nullptr && Call->FunctionReference.GetMemberName() == FunctionName)
			{
				return true;
			}
		}
		return false;
	}

	bool ReachableVariable(const TSet<const UEdGraphNode*>& Nodes,
		const FName VariableName, bool bSet)
	{
		for (const UEdGraphNode* Node : Nodes)
		{
			const UK2Node_Variable* Variable = Cast<UK2Node_Variable>(Node);
			if (Variable != nullptr && Variable->VariableReference.GetMemberName() == VariableName &&
				((bSet && Node->IsA<UK2Node_VariableSet>()) ||
				 (!bSet && Node->IsA<UK2Node_VariableGet>())))
			{
				return true;
			}
		}
		return false;
	}

	bool BlueprintContainsCall(const UBlueprint* Blueprint, TFunctionRef<bool(FName)> Predicate)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		TArray<UEdGraph*> Graphs;
		Blueprint->GetAllGraphs(Graphs);
		for (const UEdGraph* Graph : Graphs)
		{
			if (Graph == nullptr)
			{
				continue;
			}
			for (const UEdGraphNode* Node : Graph->Nodes)
			{
				const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
				if (Call != nullptr && Predicate(Call->FunctionReference.GetMemberName()))
				{
					return true;
				}
			}
		}
		return false;
	}

	bool HasSavedMenuConfigGraph(const UBlueprint* Blueprint)
	{
		if (Blueprint == nullptr)
		{
			return false;
		}
		for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph == nullptr || Graph->GetFName() != TEXT("BP_GetDesiredInputConfig"))
			{
				continue;
			}
			for (const UEdGraphNode* Node : Graph->Nodes)
			{
				const UK2Node_MakeStruct* MakeConfig = Cast<UK2Node_MakeStruct>(Node);
				if (MakeConfig != nullptr && MakeConfig->StructType == FUIInputConfig::StaticStruct())
				{
					const UEdGraphPin* ModePin = MakeConfig->FindPin(TEXT("InputMode"), EGPD_Input);
					return ModePin != nullptr && ModePin->DefaultValue == TEXT("Menu");
				}
			}
		}
		return false;
	}

	void SetCheck(TSharedRef<FJsonObject> Root, const TCHAR* Id, bool bPassed, const FString& Detail)
	{
		TSharedRef<FJsonObject> Item = MakeShared<FJsonObject>();
		Item->SetBoolField(TEXT("passed"), bPassed);
		Item->SetStringField(TEXT("detail"), Detail.Left(360));
		Root->SetObjectField(Id, Item);
	}
}

FString UMenuInputAssetAuthoring::InspectAdmissionMapContract(UWorld* World)
{
	if (World == nullptr)
	{
		return TEXT("FAIL MENU_INPUT_MAP_CONTRACT world=null");
	}

	int32 HostCount = 0;
	int32 PolicyCount = 0;
	int32 FinalFixtureCount = 0;
	int32 AdmissionFixtureCount = 0;
	int32 FunctionalFixtureCount = 0;
	int32 PlayerStartCount = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		const UClass* ActorClass = It->GetClass();
		HostCount += ActorClass == AMenuInputHost::StaticClass() ? 1 : 0;
		PolicyCount += ActorClass == AMenuInputPolicy::StaticClass() ? 1 : 0;
		FinalFixtureCount += ActorClass == AMenuInputFunctionalTest::StaticClass() ? 1 : 0;
		AdmissionFixtureCount +=
			ActorClass == AMenuInputAdmissionFunctionalTest::StaticClass() ? 1 : 0;
		FunctionalFixtureCount += It->IsA<AFunctionalTest>() ? 1 : 0;
		PlayerStartCount += ActorClass == APlayerStart::StaticClass() ? 1 : 0;
	}

	UClass* ExpectedGameModeClass = LoadClass<AGameModeBase>(
		nullptr, StockGameModeClassPath);
	UClass* ExpectedPawnClass = LoadClass<ACharacter>(nullptr, StockPawnClassPath);
	UClass* ExpectedPlayerControllerClass = LoadClass<APlayerController>(
		nullptr, StockPlayerControllerClassPath);
	const AWorldSettings* Settings = World->GetWorldSettings();
	const AGameModeBase* GameModeCDO = ExpectedGameModeClass != nullptr
		? ExpectedGameModeClass->GetDefaultObject<AGameModeBase>() : nullptr;
	const ACharacter* PawnCDO = ExpectedPawnClass != nullptr
		? ExpectedPawnClass->GetDefaultObject<ACharacter>() : nullptr;

	const bool bVisibleMesh = PawnCDO != nullptr && PawnCDO->GetMesh() != nullptr &&
		PawnCDO->GetMesh()->GetSkeletalMeshAsset() != nullptr;
	const bool bAnimClass = bVisibleMesh && PawnCDO->GetMesh()->GetAnimClass() != nullptr;
	int32 InputActionCount = 0;
	for (const FName PropertyName : {
		FName(TEXT("MoveAction")), FName(TEXT("LookAction")),
		FName(TEXT("MouseLookAction")), FName(TEXT("JumpAction")) })
	{
		const FObjectPropertyBase* Property = ExpectedPawnClass != nullptr
			? FindFProperty<FObjectPropertyBase>(ExpectedPawnClass, PropertyName)
			: nullptr;
		InputActionCount += Property != nullptr &&
			Property->PropertyClass->IsChildOf(UInputAction::StaticClass()) &&
			PawnCDO != nullptr &&
			Property->GetObjectPropertyValue_InContainer(PawnCDO) != nullptr ? 1 : 0;
	}

	const bool bValid = World->GetOutermost()->GetName() == AdmissionMapPackage &&
		HostCount == 1 && PolicyCount == 1 && FinalFixtureCount == 1 &&
		AdmissionFixtureCount == 1 && FunctionalFixtureCount == 2 &&
		PlayerStartCount == 1 && Settings != nullptr &&
		Settings->DefaultGameMode.Get() == ExpectedGameModeClass &&
		GameModeCDO != nullptr &&
		GameModeCDO->DefaultPawnClass.Get() == ExpectedPawnClass &&
		GameModeCDO->PlayerControllerClass.Get() == ExpectedPlayerControllerClass &&
		bVisibleMesh && bAnimClass && InputActionCount == 4;
	if (!bValid)
	{
		return FString::Printf(
			TEXT("FAIL MENU_INPUT_MAP_CONTRACT map=%s hosts=%d policies=%d final_fixtures=%d admission_fixtures=%d fixture_total=%d player_starts=%d game_mode=%s pawn=%s controller=%s visible_mesh=%d anim_class=%d input_actions=%d runtime_observed=0"),
			*World->GetOutermost()->GetName(), HostCount, PolicyCount,
			FinalFixtureCount, AdmissionFixtureCount, FunctionalFixtureCount,
			PlayerStartCount,
			*GetPathNameSafe(Settings ? Settings->DefaultGameMode.Get() : nullptr),
			*GetPathNameSafe(GameModeCDO ? GameModeCDO->DefaultPawnClass.Get() : nullptr),
			*GetPathNameSafe(GameModeCDO ? GameModeCDO->PlayerControllerClass.Get() : nullptr),
			bVisibleMesh ? 1 : 0, bAnimClass ? 1 : 0, InputActionCount);
	}

	return TEXT("PASS MENU_INPUT_MAP_CONTRACT map_exact=1 hosts=1 policies=1 final_fixtures=1 admission_fixtures=1 fixture_total=2 player_starts=1 game_mode_exact=1 pawn_exact=1 controller_exact=1 visible_mesh=1 anim_class=1 input_actions=4 runtime_observed=0");
}

bool UMenuInputAssetAuthoring::CreateAdmissionAssets()
{
	const FName ActionNames[] = { GameplayActionName, MenuActionName, UnrelatedActionName };
	if (PackageExists(TaskRoot, MenuAssetName))
	{
		return Fail(TEXT("EXACT_OUTPUT_EXISTS"), ObjectPath(TaskRoot, MenuAssetName));
	}
	for (const FName Name : ActionNames)
	{
		if (PackageExists(SupportRoot, Name))
		{
			return Fail(TEXT("EXACT_OUTPUT_EXISTS"), ObjectPath(SupportRoot, Name));
		}
	}
	for (const FContextRecipe& Recipe : ContextRecipes)
	{
		if (PackageExists(SupportRoot, Recipe.Name))
		{
			return Fail(TEXT("EXACT_OUTPUT_EXISTS"), ObjectPath(SupportRoot, Recipe.Name));
		}
	}

	TMap<FName, UInputAction*> Actions;
	for (const FName Name : ActionNames)
	{
		UInputAction* Action = CreateAction(Name);
		if (Action == nullptr)
		{
			return false;
		}
		Actions.Add(Name, Action);
	}
	for (const FContextRecipe& Recipe : ContextRecipes)
	{
		if (CreateContext(Recipe, Actions) == nullptr)
		{
			return false;
		}
	}
	if (CreateBaselineMenu() == nullptr || !ValidateAdmissionAssets())
	{
		return false;
	}
	UE_LOG(LogMenuInputAssetAuthoring, Display,
		TEXT("MENU-INPUT-ASSETS-SAVED baseline=1 actions=3 contexts=6"));
	return true;
}

bool UMenuInputAssetAuthoring::ValidateAdmissionAssets()
{
	UBlueprint* Blueprint = LoadMenuBlueprint();
	if (Blueprint == nullptr || Blueprint->ParentClass != UInputBlockingMenuBase::StaticClass() ||
		Blueprint->GeneratedClass == nullptr || !HasStoredContextVariable(Blueprint))
	{
		return Fail(TEXT("BASELINE_READBACK_FAILED"), GetNameSafe(Blueprint));
	}
	UWidgetTree* Tree = WidgetTree(Blueprint);
	if (Tree == nullptr || Tree->FindWidget(FName(TEXT("MenuPanel"))) == nullptr ||
		Tree->FindWidget(FName(TEXT("Button_CloseMenu"))) == nullptr)
	{
		return Fail(TEXT("BASELINE_WIDGET_TREE_FAILED"), Blueprint->GetPathName());
	}

	TMap<FName, UInputAction*> Actions;
	for (const FName Name : { GameplayActionName, MenuActionName, UnrelatedActionName })
	{
		UInputAction* Action = LoadAction(Name);
		if (Action == nullptr || Action->ValueType != EInputActionValueType::Boolean || !Action->bConsumeInput)
		{
			return Fail(TEXT("ACTION_READBACK_FAILED"), Name.ToString());
		}
		Actions.Add(Name, Action);
	}
	for (const FContextRecipe& Recipe : ContextRecipes)
	{
		UInputMappingContext* Context = LoadContext(Recipe.Name);
		UInputAction* const* ExpectedAction = Actions.Find(Recipe.ActionName);
		if (Context == nullptr || ExpectedAction == nullptr ||
			Context->GetMappings().Num() != 1 ||
			Context->GetMappings()[0].Action != *ExpectedAction ||
			Context->GetMappings()[0].Key != Recipe.Key)
		{
			return Fail(TEXT("CONTEXT_READBACK_FAILED"), Recipe.Name.ToString());
		}
	}
	UE_LOG(LogMenuInputAssetAuthoring, Display,
		TEXT("MENU-INPUT-ASSETS-READBACK baseline=1 actions=3 contexts=6 parent=%s"),
		*GetNameSafe(Blueprint->ParentClass.Get()));
	return true;
}

bool UMenuInputAssetAuthoring::BuildReferenceMenuGraph()
{
	UBlueprint* Blueprint = LoadMenuBlueprint();
	if (Blueprint == nullptr || Blueprint->ParentClass != UInputBlockingMenuBase::StaticClass() ||
		Blueprint->GeneratedClass == nullptr || !HasStoredContextVariable(Blueprint))
	{
		return Fail(TEXT("REFERENCE_BASELINE_INVALID"), GetNameSafe(Blueprint));
	}

	TArray<UEdGraph*> ExistingGraphs;
	Blueprint->GetAllGraphs(ExistingGraphs);
	TSet<FName> ObservedBaselineEvents;
	for (const UEdGraph* Graph : ExistingGraphs)
	{
		if (Graph == nullptr)
		{
			continue;
		}
		for (const UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node == nullptr)
			{
				continue;
			}
			for (const UEdGraphPin* NodePin : Node->Pins)
			{
				if (NodePin != nullptr && !NodePin->LinkedTo.IsEmpty())
				{
					return Fail(TEXT("REFERENCE_BASELINE_HAS_LINKS"),
						FString::Printf(TEXT("node=%s pin=%s links=%d"),
							*Node->GetPathName(), *NodePin->PinName.ToString(),
							NodePin->LinkedTo.Num()));
				}
			}
			if (const UK2Node_Event* Event = Cast<UK2Node_Event>(Node))
			{
				FString Detail;
				if (!ValidateEmptyBaselineEvent(Event, ObservedBaselineEvents, Detail))
				{
					return Fail(TEXT("REFERENCE_BASELINE_EVENT_INVALID"), Detail);
				}
			}
			else if (Node->IsA<UK2Node>())
			{
				return Fail(TEXT("REFERENCE_BASELINE_NOT_EMPTY"), Node->GetPathName());
			}
		}
	}
	const TSet<FName> ExpectedBaselineEvents = {
		TEXT("PreConstruct"), TEXT("Construct"), TEXT("Tick")
	};
	bool bExactBaselineEventSet =
		ObservedBaselineEvents.Num() == ExpectedBaselineEvents.Num();
	for (const FName ExpectedEvent : ExpectedBaselineEvents)
	{
		bExactBaselineEventSet = bExactBaselineEventSet &&
			ObservedBaselineEvents.Contains(ExpectedEvent);
	}
	if (!bExactBaselineEventSet)
	{
		return Fail(TEXT("REFERENCE_BASELINE_EVENT_SET_INVALID"),
			FString::Printf(TEXT("observed=%d expected=3"), ObservedBaselineEvents.Num()));
	}

	if (!BuildLifecycleGraph(Blueprint) || !BuildInputConfigOverride(Blueprint) ||
		!SaveBlueprint(Blueprint))
	{
		return Fail(TEXT("REFERENCE_GRAPH_BUILD_FAILED"), Blueprint->GetPathName());
	}

	const FString Inspection = InspectSubmissionAsset();
	TSharedPtr<FJsonObject> Parsed;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Inspection);
	if (!FJsonSerializer::Deserialize(Reader, Parsed) || !Parsed.IsValid())
	{
		return Fail(TEXT("REFERENCE_GRAPH_INSPECTION_INVALID"), Inspection);
	}
	const TCHAR* RequiredChecks[] = {
		TEXT("menu_is_real_activatable_screen"),
		TEXT("activation_adds_only_current_world_context"),
		TEXT("deactivation_removes_captured_context_without_global_clear"),
		TEXT("menu_declares_ui_routing_config"),
	};
	for (const TCHAR* CheckId : RequiredChecks)
	{
		const TSharedPtr<FJsonObject>* Item = nullptr;
		bool bPassed = false;
		if (!Parsed->TryGetObjectField(CheckId, Item) || Item == nullptr ||
			!(*Item)->TryGetBoolField(TEXT("passed"), bPassed) || !bPassed)
		{
			return Fail(TEXT("REFERENCE_GRAPH_INSPECTION_FAILED"), CheckId);
		}
	}

	UE_LOG(LogMenuInputAssetAuthoring, Display,
		TEXT("MENU-INPUT-REFERENCE-GRAPH-SAVED activation=1 deactivation=1 input_config=1 l2i=4"));
	return true;
}

FString UMenuInputAssetAuthoring::InspectSubmissionAsset()
{
	TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
	UBlueprint* Blueprint = LoadMenuBlueprint();
	if (Blueprint != nullptr)
	{
		FKismetEditorUtilities::CompileBlueprint(Blueprint);
	}

	const bool bExactParent = Blueprint != nullptr &&
		Blueprint->ParentClass == UInputBlockingMenuBase::StaticClass() &&
		Blueprint->GeneratedClass != nullptr &&
		(Blueprint->Status == BS_UpToDate || Blueprint->Status == BS_UpToDateWithWarnings);
	SetCheck(Result, TEXT("menu_is_real_activatable_screen"), bExactParent,
		FString::Printf(TEXT("asset=%s parent=%s status=%d"), *GetNameSafe(Blueprint),
			*GetNameSafe(Blueprint ? Blueprint->ParentClass.Get() : nullptr),
			Blueprint ? static_cast<int32>(Blueprint->Status) : -1));

	const TSet<const UEdGraphNode*> Activated = ExecReachableFromEvent(
		Blueprint, TEXT("BP_OnActivated"));
	const TSet<const UEdGraphNode*> Deactivated = ExecReachableFromEvent(
		Blueprint, TEXT("BP_OnDeactivated"));
	const TSet<const UEdGraphNode*> ActivatedWithData = IncludeInputDependencies(Activated);
	const TSet<const UEdGraphNode*> DeactivatedWithData = IncludeInputDependencies(Deactivated);
	const bool bReadsContext = ReachableCall(
		ActivatedWithData, TEXT("GetCurrentMenuContext"));
	const bool bReadsPriority = ReachableCall(
		ActivatedWithData, TEXT("GetCurrentMenuPriority"));
	const bool bAdd = ReachableCall(Activated, TEXT("AddMappingContext"));
	const bool bStore = ReachableVariable(Activated, StoredContextName, true);
	SetCheck(Result, TEXT("activation_adds_only_current_world_context"),
		bReadsContext && bReadsPriority && bAdd && bStore,
		FString::Printf(TEXT("reads_context=%d reads_priority=%d add=%d store=%d"),
			bReadsContext, bReadsPriority, bAdd, bStore));

	const bool bRemove = ReachableCall(Deactivated, TEXT("RemoveMappingContext"));
	const bool bReadStored = ReachableVariable(
		DeactivatedWithData, StoredContextName, false);
	const bool bForbidden = BlueprintContainsCall(Blueprint, [](FName Name)
	{
		const FString Text = Name.ToString();
		return Name == TEXT("ClearAllMappings") || Text.Contains(TEXT("SetInputMode_UIOnly"));
	});
	SetCheck(Result, TEXT("deactivation_removes_captured_context_without_global_clear"),
		bRemove && bReadStored && !bForbidden,
		FString::Printf(TEXT("remove=%d read_stored=%d forbidden=%d"),
			bRemove, bReadStored, bForbidden));

	const bool bSavedMenuConfigGraph = HasSavedMenuConfigGraph(Blueprint);
	bool bMenuConfig = false;
	if (bExactParent)
	{
		const UInputBlockingMenuBase* CDO = Cast<UInputBlockingMenuBase>(
			Blueprint->GeneratedClass->GetDefaultObject());
		const TOptional<FUIInputConfig> Config = CDO != nullptr
			? CDO->GetDesiredInputConfig() : TOptional<FUIInputConfig>();
		bMenuConfig = Config.IsSet() && Config.GetValue().GetInputMode() == ECommonInputMode::Menu;
	}
	SetCheck(Result, TEXT("menu_declares_ui_routing_config"),
		bSavedMenuConfigGraph && bMenuConfig,
		FString::Printf(TEXT("saved_graph=%d menu_input_config=%d"),
			bSavedMenuConfigGraph, bMenuConfig));

	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	FJsonSerializer::Serialize(Result, Writer);
	return Json;
}
