// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputRuntime.h"

#include "Blueprint/WidgetTree.h"
#include "Engine/LocalPlayer.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "Input/CommonUIInputTypes.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "Widgets/CommonActivatableWidgetContainer.h"

namespace
{
	const FName PolicyTag(TEXT("MenuInputPolicy"));
	const FName HostTag(TEXT("MenuInputHost"));
}

AMenuInputPolicy::AMenuInputPolicy()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(PolicyTag);
}

void AMenuInputPolicy::SetCurrentAssignment(
	UInputMappingContext* InContext, UInputAction* InAction, int32 InPriority)
{
	CurrentMenuContext = InContext;
	CurrentMenuAction = InAction;
	CurrentMenuPriority = InPriority;
}

void UInputBlockingMenuBase::ConfigureFromPolicy(AMenuInputPolicy* InPolicy)
{
	if (MenuActionBinding.IsValid())
	{
		MenuActionBinding.Unregister();
	}
	MenuPolicy = InPolicy;
	ObservedMenuActionCount = 0;
	RegisterConfiguredMenuAction();
}

UEnhancedInputLocalPlayerSubsystem* UInputBlockingMenuBase::GetMenuInputSubsystem() const
{
	const ULocalPlayer* LocalPlayer = GetOwningLocalPlayer();
	return LocalPlayer != nullptr
		? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>()
		: nullptr;
}

void UInputBlockingMenuBase::NativeConstruct()
{
	Super::NativeConstruct();
	RegisterConfiguredMenuAction();
}

void UInputBlockingMenuBase::RegisterConfiguredMenuAction()
{
	if (MenuActionBinding.IsValid())
	{
		return;
	}
	if (MenuPolicy != nullptr && MenuPolicy->GetCurrentMenuAction() != nullptr)
	{
		FBindUIActionArgs Args(
			MenuPolicy->GetCurrentMenuAction(),
			false,
			FSimpleDelegate::CreateUObject(this, &UInputBlockingMenuBase::HandleMenuAction));
		Args.InputMode = ECommonInputMode::Menu;
		Args.bConsumeInput = true;
		MenuActionBinding = RegisterUIActionBinding(Args);
	}
}

void UInputBlockingMenuBase::NativeDestruct()
{
	if (MenuActionBinding.IsValid())
	{
		MenuActionBinding.Unregister();
	}
	MenuPolicy = nullptr;
	Super::NativeDestruct();
}

void UInputBlockingMenuBase::ActivateMappingContext()
{
	// The editable Blueprint owns the context lifecycle for this task.
}

void UInputBlockingMenuBase::DeactivateMappingContext()
{
	// The editable Blueprint owns the context lifecycle for this task.
}

void UInputBlockingMenuBase::HandleMenuAction()
{
	++ObservedMenuActionCount;
}

TOptional<FUIInputConfig> UMenuInputStackRoot::GetDesiredInputConfig() const
{
	// The permanent, empty stack root is infrastructure rather than a menu.
	// Leaving it on CommonUI's default Menu config blocks the gameplay probe
	// before a real screen is pushed. The active child screen still replaces
	// this with its own Menu config and therefore owns the blocking interval.
	return FUIInputConfig(ECommonInputMode::All, EMouseCaptureMode::NoCapture);
}

TSharedRef<SWidget> UMenuInputStackRoot::RebuildWidget()
{
	if (WidgetTree != nullptr && ScreenStack == nullptr)
	{
		ScreenStack = WidgetTree->ConstructWidget<UCommonActivatableWidgetStack>(
			UCommonActivatableWidgetStack::StaticClass(), TEXT("MenuScreenStack"));
		ScreenStack->SetTransitionDuration(0.0f);
		WidgetTree->RootWidget = ScreenStack;
	}
	return Super::RebuildWidget();
}

AMenuInputHost::AMenuInputHost()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(HostTag);
}

bool AMenuInputHost::InitializeForPlayer(APlayerController* InController, FString& OutFailure)
{
	RemoveMenuTree();
	if (InController == nullptr || InController->GetLocalPlayer() == nullptr)
	{
		OutFailure = TEXT("local player controller is unavailable");
		return false;
	}

	Root = CreateWidget<UMenuInputStackRoot>(InController, UMenuInputStackRoot::StaticClass());
	if (Root == nullptr)
	{
		OutFailure = TEXT("could not create the activatable menu root");
		return false;
	}
	Root->AddToViewport(1000);
	Root->ActivateWidget();
	if (Root->GetScreenStack() == nullptr)
	{
		OutFailure = TEXT("menu root did not build MenuScreenStack");
		return false;
	}
	return true;
}

UInputBlockingMenuBase* AMenuInputHost::PushMenu(
	TSubclassOf<UInputBlockingMenuBase> MenuClass,
	AMenuInputPolicy* Policy,
	FString& OutFailure)
{
	UCommonActivatableWidgetStack* Stack = GetStack();
	if (Stack == nullptr || MenuClass == nullptr || Policy == nullptr)
	{
		OutFailure = TEXT("stack, menu class, or policy is unavailable");
		return nullptr;
	}
	if (Stack->GetActiveWidget() != nullptr)
	{
		OutFailure = TEXT("a menu is already active");
		return nullptr;
	}

	ActiveMenu = Stack->AddWidget<UInputBlockingMenuBase>(
		MenuClass,
		[Policy](UInputBlockingMenuBase& Menu)
		{
			Menu.ConfigureFromPolicy(Policy);
		});
	if (ActiveMenu == nullptr)
	{
		OutFailure = TEXT("stack could not create the requested menu");
		return nullptr;
	}
	return ActiveMenu;
}

bool AMenuInputHost::PopMenu(FString& OutFailure)
{
	if (ActiveMenu == nullptr || GetStack() == nullptr || GetStack()->GetActiveWidget() != ActiveMenu)
	{
		OutFailure = TEXT("exact active menu is unavailable");
		return false;
	}
	ActiveMenu->DeactivateWidget();
	ActiveMenu = nullptr;
	return true;
}

void AMenuInputHost::RemoveMenuTree()
{
	if (ActiveMenu != nullptr)
	{
		ActiveMenu->DeactivateWidget();
	}
	ActiveMenu = nullptr;
	if (Root != nullptr)
	{
		Root->DeactivateWidget();
		Root->RemoveFromParent();
	}
	Root = nullptr;
}

UCommonActivatableWidgetStack* AMenuInputHost::GetStack() const
{
	return Root != nullptr ? Root->GetScreenStack() : nullptr;
}
