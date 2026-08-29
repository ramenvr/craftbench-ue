// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalRuntime.h"

#include "Components/Button.h"
#include "Engine/LocalPlayer.h"
#include "EnhancedInputSubsystems.h"
#include "Input/CommonUIInputTypes.h"
#include "InputAction.h"
#include "InputMappingContext.h"

UCommonActivatableWidgetStack*
ULocalPlayerModalRootBase::ResolvePlayerModalStack_Implementation() const
{
	return nullptr;
}

TOptional<FUIInputConfig> ULocalPlayerModalRootBase::GetDesiredInputConfig() const
{
	return FUIInputConfig(ECommonInputMode::All, EMouseCaptureMode::NoCapture);
}

ULocalPlayerModalScreenBase::ULocalPlayerModalScreenBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	bAutoRestoreFocus = true;
}

void ULocalPlayerModalScreenBase::ConfigurePolicy(
	UInputAction* InAction,
	UInputMappingContext* InContext,
	int32 InPriority,
	int32 InOwnerIndex,
	int32 InModalOrdinal,
	bool bInModal,
	bool bInPreferAlternate)
{
	if (ActionBinding.IsValid())
	{
		ActionBinding.Unregister();
	}
	RemoveConfiguredMapping();
	ConfiguredAction = InAction;
	ConfiguredContext = InContext;
	ConfiguredPriority = InPriority;
	OwnerIndex = InOwnerIndex;
	ModalOrdinal = InModalOrdinal;
	ObservedActionCount = 0;
	bConfiguredModal = bInModal;
	bPreferAlternate = bInPreferAlternate;
	bIsModal = bInModal;
}

UEnhancedInputLocalPlayerSubsystem*
ULocalPlayerModalScreenBase::ResolveInputSubsystem() const
{
	if (ULocalPlayer* LocalPlayer = GetOwningLocalPlayer())
	{
		return LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>();
	}
	return nullptr;
}

void ULocalPlayerModalScreenBase::ApplyConfiguredMapping()
{
	if (!bConfiguredModal || ConfiguredContext == nullptr || bMappingApplied)
	{
		return;
	}
	if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ResolveInputSubsystem())
	{
		FModifyContextOptions Options;
		Options.bForceImmediately = true;
		Subsystem->AddMappingContext(ConfiguredContext, ConfiguredPriority, Options);
		bMappingApplied = Subsystem->HasMappingContext(ConfiguredContext);
	}
}

void ULocalPlayerModalScreenBase::RemoveConfiguredMapping()
{
	if (ConfiguredContext == nullptr || !bMappingApplied)
	{
		return;
	}
	if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ResolveInputSubsystem())
	{
		FModifyContextOptions Options;
		Options.bForceImmediately = true;
		Subsystem->RemoveMappingContext(ConfiguredContext, Options);
	}
	bMappingApplied = false;
}

void ULocalPlayerModalScreenBase::RegisterConfiguredDismiss()
{
	if (!bConfiguredModal || ConfiguredAction == nullptr || ActionBinding.IsValid())
	{
		return;
	}
	FBindUIActionArgs Args(
		ConfiguredAction,
		false,
		FSimpleDelegate::CreateUObject(
			this, &ULocalPlayerModalScreenBase::HandleConfiguredDismiss));
	Args.InputMode = ECommonInputMode::Menu;
	Args.KeyEvent = IE_Pressed;
	Args.bConsumeInput = true;
	ActionBinding = RegisterUIActionBinding(Args);
}

void ULocalPlayerModalScreenBase::CloseOnlyThisModal()
{
	DeactivateWidget();
}

UButton* ULocalPlayerModalScreenBase::ResolveConfiguredFocusTarget() const
{
	return Cast<UButton>(GetWidgetFromName(
		bPreferAlternate ? TEXT("AlternateFocusButton") : TEXT("PrimaryFocusButton")));
}

FUIInputConfig ULocalPlayerModalScreenBase::ResolveConfiguredInputConfig() const
{
	return bConfiguredModal
		? FUIInputConfig(ECommonInputMode::Menu, EMouseCaptureMode::NoCapture)
		: FUIInputConfig(ECommonInputMode::All, EMouseCaptureMode::NoCapture);
}

void ULocalPlayerModalScreenBase::OnConfiguredDismiss_Implementation()
{
}

void ULocalPlayerModalScreenBase::HandleConfiguredDismiss()
{
	++ObservedActionCount;
	OnConfiguredDismiss();
}

void ULocalPlayerModalScreenBase::NativeDestruct()
{
	if (ActionBinding.IsValid())
	{
		ActionBinding.Unregister();
	}
	RemoveConfiguredMapping();
	Super::NativeDestruct();
}
