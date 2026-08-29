// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalIsolationAdmissionFunctionalTest.h"

#include "Blueprint/WidgetTree.h"
#include "CommonGameViewportClient.h"
#include "CommonInputSettings.h"
#include "Components/Button.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/VerticalBox.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/SkeletalMesh.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/InputDeviceLibrary.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Input/CommonUIActionRouterBase.h"
#include "Input/CommonUIInputTypes.h"
#include "InputAction.h"
#include "InputKeyEventArgs.h"
#include "InputMappingContext.h"
#include "Widgets/CommonActivatableWidgetContainer.h"
#include "GenericPlatform/GenericPlatformInputDeviceMapper.h"

namespace
{
	constexpr int32 PlayerCount = 2;
	constexpr int32 EpochCount = 2;
	const FKey EpochKeys[EpochCount] = { EKeys::E, EKeys::Q };
	const TCHAR* GateIndependentRouters = TEXT("EachPlayerOwnsIndependentActionRouter");
	const TCHAR* GateOwningAction = TEXT("TopModalConsumesOnlyOwningPlayersAction");
	const TCHAR* GateFocusRestore = TEXT("DismissRestoresOnlyThatPlayersFocus");
	const TCHAR* GateOtherUnchanged = TEXT("OtherPlayersStackNeverChanges");
}

ULocalPlayerModalAdmissionScreen::ULocalPlayerModalAdmissionScreen(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	bAutoRestoreFocus = true;
}

TSharedRef<SWidget> ULocalPlayerModalAdmissionScreen::RebuildWidget()
{
	if (WidgetTree == nullptr)
	{
		WidgetTree = NewObject<UWidgetTree>(this, TEXT("WidgetTree"));
	}
	if (PrimaryButton == nullptr || AlternateButton == nullptr)
	{
		UVerticalBox* Layout = WidgetTree->ConstructWidget<UVerticalBox>(
			UVerticalBox::StaticClass(), TEXT("AdmissionFocusLayout"));
		PrimaryButton = WidgetTree->ConstructWidget<UButton>(
			UButton::StaticClass(), TEXT("PrimaryFocusButton"));
		AlternateButton = WidgetTree->ConstructWidget<UButton>(
			UButton::StaticClass(), TEXT("AlternateFocusButton"));
		Layout->AddChildToVerticalBox(PrimaryButton);
		Layout->AddChildToVerticalBox(AlternateButton);
		WidgetTree->RootWidget = Layout;
	}
	return Super::RebuildWidget();
}

UWidget* ULocalPlayerModalAdmissionScreen::NativeGetDesiredFocusTarget() const
{
	return ResolveConfiguredFocusTarget();
}

void ULocalPlayerModalAdmissionScreen::NativeOnActivated()
{
	Super::NativeOnActivated();
	ApplyConfiguredMapping();
	RegisterConfiguredDismiss();
}

void ULocalPlayerModalAdmissionScreen::NativeOnDeactivated()
{
	RemoveConfiguredMapping();
	Super::NativeOnDeactivated();
}

void ULocalPlayerModalAdmissionScreen::OnConfiguredDismiss_Implementation()
{
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-ACTION owner=%d modal=%d count=%d"),
		GetOwnerIndex(), GetModalOrdinal(), GetObservedActionCount());
	CloseOnlyThisModal();
}

UCommonActivatableWidgetStack*
ULocalPlayerModalAdmissionRoot::ResolvePlayerModalStack_Implementation() const
{
	return Stack;
}

TSharedRef<SWidget> ULocalPlayerModalAdmissionRoot::RebuildWidget()
{
	if (WidgetTree == nullptr)
	{
		WidgetTree = NewObject<UWidgetTree>(this, TEXT("WidgetTree"));
	}
	if (Stack == nullptr)
	{
		Stack = WidgetTree->ConstructWidget<UCommonActivatableWidgetStack>(
			UCommonActivatableWidgetStack::StaticClass(), TEXT("PlayerModalStack"));
		Stack->SetTransitionDuration(0.0f);
		WidgetTree->RootWidget = Stack;
	}
	return Super::RebuildWidget();
}

ALocalPlayerModalIsolationAdmissionFunctionalTest::
	ALocalPlayerModalIsolationAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

TSubclassOf<ULocalPlayerModalRootBase>
ALocalPlayerModalIsolationAdmissionFunctionalTest::GetRootWidgetClass() const
{
	return ULocalPlayerModalAdmissionRoot::StaticClass();
}

TSubclassOf<ULocalPlayerModalScreenBase>
ALocalPlayerModalIsolationAdmissionFunctionalTest::GetScreenWidgetClass() const
{
	return ULocalPlayerModalAdmissionScreen::StaticClass();
}

FString ALocalPlayerModalIsolationAdmissionFunctionalTest::GetSuccessMarker() const
{
	return TEXT("LOCAL-PLAYER-MODAL-ADMISSION-PASS");
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::RequireHarness(
	bool bCondition, const FString& Detail)
{
	if (!bCondition)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Detail));
		return false;
	}
	return true;
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::FailGate(
	const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]: %s"), Gate, *Detail));
	return false;
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::RequireGate(
	bool bCondition, const TCHAR* Gate, const FString& Detail)
{
	return bCondition ? true : FailGate(Gate, Detail);
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::ResolveTwoLocalPlayers()
{
	UWorld* World = GetWorld();
	GameInstance = World != nullptr ? World->GetGameInstance() : nullptr;
	ViewportClient = World != nullptr ? World->GetGameViewport() : nullptr;
	if (!RequireHarness(GameInstance.IsValid(), TEXT("PIE GameInstance is unavailable")) ||
		!RequireHarness(ViewportClient.IsValid() &&
			ViewportClient->IsA<UCommonGameViewportClient>(),
			TEXT("task overlay did not create CommonGameViewportClient")))
	{
		return false;
	}

	if (GameInstance->GetNumLocalPlayers() == 1)
	{
		GameInstance->DebugCreatePlayer(1);
		bCreatedSecondLocalPlayer = true;
	}
	if (!RequireHarness(GameInstance->GetNumLocalPlayers() == PlayerCount,
		FString::Printf(TEXT("expected exact two LocalPlayers; found %d"),
			GameInstance->GetNumLocalPlayers())))
	{
		return false;
	}

	// DebugCreatePlayer only maps controller 1's compatibility device when the
	// device has no existing owner. A connected physical XInput pad can already
	// own device 1 on user 0, leaving the newly-created user 1 without a primary
	// device. Provision the engine mapping deterministically for this verifier
	// fixture and restore the prior owner in EndPlay.
	ULocalPlayer* SecondLocalPlayer = GameInstance->GetLocalPlayerByIndex(1);
	if (!RequireHarness(SecondLocalPlayer != nullptr,
		TEXT("second LocalPlayer is unavailable before input-device provisioning")))
	{
		return false;
	}
	IPlatformInputDeviceMapper& DeviceMapper = IPlatformInputDeviceMapper::Get();
	FPlatformUserId SecondPlatformUser = SecondLocalPlayer->GetPlatformUserId();
	FInputDeviceId SecondControllerDevice = INPUTDEVICEID_NONE;
	const bool bResolvedControllerDevice =
		DeviceMapper.RemapControllerIdToPlatformUserAndDevice(
			SecondLocalPlayer->GetControllerId(),
			SecondPlatformUser,
			SecondControllerDevice);
	if (!RequireHarness(bResolvedControllerDevice && SecondControllerDevice.IsValid() &&
		SecondPlatformUser == SecondLocalPlayer->GetPlatformUserId(),
		FString::Printf(
			TEXT("controller/device mapping for player 1 is invalid controller=%d user=%d device=%d"),
			SecondLocalPlayer->GetControllerId(),
			SecondPlatformUser.GetInternalId(),
			SecondControllerDevice.GetId())))
	{
		return false;
	}

	const FPlatformUserId ExistingDeviceOwner =
		DeviceMapper.GetUserForInputDevice(SecondControllerDevice);
	if (ExistingDeviceOwner != SecondPlatformUser)
	{
		const bool bMapped = ExistingDeviceOwner.IsValid()
			? DeviceMapper.Internal_ChangeInputDeviceUserMapping(
				SecondControllerDevice, SecondPlatformUser, ExistingDeviceOwner)
			: DeviceMapper.Internal_MapInputDeviceToUser(
				SecondControllerDevice, SecondPlatformUser,
				EInputDeviceConnectionState::Connected);
		if (!RequireHarness(bMapped,
			FString::Printf(
				TEXT("could not provision device %d from user %d to user %d"),
				SecondControllerDevice.GetId(),
				ExistingDeviceOwner.GetInternalId(),
				SecondPlatformUser.GetInternalId())))
		{
			return false;
		}
		bReassignedSecondInputDevice = true;
		ReassignedSecondInputDevice = SecondControllerDevice;
		PreviousSecondInputDeviceOwner = ExistingDeviceOwner;
	}
	if (!RequireHarness(
		DeviceMapper.GetPrimaryInputDeviceForUser(SecondPlatformUser).IsValid() &&
		DeviceMapper.GetUserForInputDevice(SecondControllerDevice) == SecondPlatformUser,
		FString::Printf(
			TEXT("player 1 input-device provisioning did not stick user=%d device=%d prior_owner=%d"),
			SecondPlatformUser.GetInternalId(), SecondControllerDevice.GetId(),
			ExistingDeviceOwner.GetInternalId())))
	{
		return false;
	}
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-DEVICE-PROVISION user=%d device=%d prior_owner=%d reassigned=%d"),
		SecondPlatformUser.GetInternalId(), SecondControllerDevice.GetId(),
		ExistingDeviceOwner.GetInternalId(),
		bReassignedSecondInputDevice ? 1 : 0);

	LocalPlayers.SetNum(PlayerCount);
	Controllers.SetNum(PlayerCount);
	ActionRouters.SetNum(PlayerCount);
	InputSubsystems.SetNum(PlayerCount);
	for (int32 PlayerIndex = 0; PlayerIndex < PlayerCount; ++PlayerIndex)
	{
		ULocalPlayer* LocalPlayer = GameInstance->GetLocalPlayerByIndex(PlayerIndex);
		APlayerController* Controller = LocalPlayer != nullptr
			? LocalPlayer->GetPlayerController(World)
			: nullptr;
		UCommonUIActionRouterBase* Router = LocalPlayer != nullptr
			? LocalPlayer->GetSubsystem<UCommonUIActionRouterBase>()
			: nullptr;
		UEnhancedInputLocalPlayerSubsystem* InputSubsystem = LocalPlayer != nullptr
			? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>()
			: nullptr;
		ACharacter* Character = Controller != nullptr
			? Cast<ACharacter>(Controller->GetPawn())
			: nullptr;
		UEnhancedInputComponent* PawnInput = Character != nullptr
			? Cast<UEnhancedInputComponent>(Character->InputComponent)
			: nullptr;
		if (!RequireHarness(LocalPlayer != nullptr && Controller != nullptr,
			FString::Printf(TEXT("local player/controller %d is unavailable"), PlayerIndex)) ||
			!RequireHarness(Character != nullptr && Character->GetMesh() != nullptr &&
				Character->GetMesh()->GetSkeletalMeshAsset() != nullptr &&
				Character->GetMesh()->GetAnimClass() != nullptr,
				FString::Printf(TEXT("local player %d is not visibly represented"), PlayerIndex)) ||
			!RequireHarness(PawnInput != nullptr &&
				PawnInput->GetActionEventBindings().Num() > 0,
				FString::Printf(TEXT("local player %d pawn is not playable through Enhanced Input"),
					PlayerIndex)) ||
			!RequireHarness(Router != nullptr && InputSubsystem != nullptr,
			FString::Printf(TEXT("router/input subsystem %d is unavailable"), PlayerIndex)))
		{
			return false;
		}
		const FInputDeviceId Device =
			UInputDeviceLibrary::GetPrimaryInputDeviceForUser(LocalPlayer->GetPlatformUserId());
		if (!RequireHarness(Device.IsValid(),
			FString::Printf(TEXT("primary input device %d is invalid"), PlayerIndex)))
		{
			return false;
		}
		// DebugCreatePlayer establishes the LocalPlayer/controller/device mapping,
		// but unattended off-screen PIE does not receive a physical input event
		// that would normally make Slate lazily register the second user. Send one
		// harmless, unbound key through Slate's public event-processing seam before
		// requiring the engine-owned LocalPlayer -> controller -> SlateUser mapping.
		const int32 ExpectedSlateUserIndex =
			LocalPlayer->GetPlatformUserId().GetInternalId();
		const FKeyEvent ProvisioningEvent(
			EKeys::ScrollLock,
			FModifierKeysState(),
			Device,
			false,
			0,
			0,
			ExpectedSlateUserIndex);
		FSlateApplication::Get().ProcessKeyDownEvent(ProvisioningEvent);
		FSlateApplication::Get().ProcessKeyUpEvent(ProvisioningEvent);
		const TSharedPtr<FSlateUser> ProvisionedSlateUser =
			FSlateApplication::Get().GetUser(ProvisioningEvent);
		const TSharedPtr<FSlateUser> LocalPlayerSlateUser = LocalPlayer->GetSlateUser();
		if (!RequireHarness(ExpectedSlateUserIndex >= 0 &&
			ProvisionedSlateUser.IsValid() && LocalPlayerSlateUser.IsValid() &&
			LocalPlayerSlateUser.Get() == ProvisionedSlateUser.Get(),
			FString::Printf(
				TEXT("Slate user %d was not provisioned through its primary device"),
				PlayerIndex)))
		{
			return false;
		}
		const TSharedPtr<SWidget> GameViewportWidget =
			ViewportClient->GetGameViewportWidget();
		const bool bViewportFocusEstablished = GameViewportWidget.IsValid() &&
			FSlateApplication::Get().SetUserFocus(
				ExpectedSlateUserIndex, GameViewportWidget, EFocusCause::SetDirectly);
		if (!RequireHarness(bViewportFocusEstablished &&
			LocalPlayerSlateUser->IsWidgetInFocusPath(GameViewportWidget),
			FString::Printf(
				TEXT("game viewport is not in Slate user %d's focus path"),
				PlayerIndex)))
		{
			return false;
		}
		LocalPlayers[PlayerIndex] = LocalPlayer;
		Controllers[PlayerIndex] = Controller;
		ActionRouters[PlayerIndex] = Router;
		InputSubsystems[PlayerIndex] = InputSubsystem;
	}

	const int32 SlateUser0 = LocalPlayers[0]->GetSlateUser()->GetUserIndex();
	const int32 SlateUser1 = LocalPlayers[1]->GetSlateUser()->GetUserIndex();
	const FInputDeviceId Device0 = UInputDeviceLibrary::GetPrimaryInputDeviceForUser(
		LocalPlayers[0]->GetPlatformUserId());
	const FInputDeviceId Device1 = UInputDeviceLibrary::GetPrimaryInputDeviceForUser(
		LocalPlayers[1]->GetPlatformUserId());
	const bool bDistinct = LocalPlayers[0].Get() != LocalPlayers[1].Get() &&
		Controllers[0].Get() != Controllers[1].Get() &&
		ActionRouters[0].Get() != ActionRouters[1].Get() &&
		LocalPlayers[0]->GetPlatformUserId() != LocalPlayers[1]->GetPlatformUserId() &&
		Device0 != Device1 && SlateUser0 != SlateUser1;
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-IDENTITY players=2 lp=(%p,%p) pc=(%p,%p) router=(%p,%p) user=(%d,%d) device=(%d,%d) slate=(%d,%d) distinct=%d"),
		LocalPlayers[0].Get(), LocalPlayers[1].Get(),
		Controllers[0].Get(), Controllers[1].Get(),
		ActionRouters[0].Get(), ActionRouters[1].Get(),
		LocalPlayers[0]->GetPlatformUserId().GetInternalId(),
		LocalPlayers[1]->GetPlatformUserId().GetInternalId(),
		Device0.GetId(), Device1.GetId(), SlateUser0, SlateUser1,
		bDistinct ? 1 : 0);
	return RequireGate(bDistinct,
		GateIndependentRouters,
		FString::Printf(
			TEXT("identity collapse lp=%d pc=%d router=%d user=(%d,%d) device=(%d,%d) slate=(%d,%d)"),
			LocalPlayers[0].Get() == LocalPlayers[1].Get() ? 1 : 0,
			Controllers[0].Get() == Controllers[1].Get() ? 1 : 0,
			ActionRouters[0].Get() == ActionRouters[1].Get() ? 1 : 0,
			LocalPlayers[0]->GetPlatformUserId().GetInternalId(),
			LocalPlayers[1]->GetPlatformUserId().GetInternalId(),
			Device0.GetId(), Device1.GetId(), SlateUser0, SlateUser1));
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::BuildHomeStacks(int32 Epoch)
{
	RemoveAdmissionUI();
	EpochContexts.Reset();
	ContextOwners.Reset();
	ContextPriorities.Reset();
	ContextScreens.Reset();
	Roots.SetNum(PlayerCount);
	Homes.SetNum(PlayerCount);
	ActionTargets.SetNum(PlayerCount);
	TopsAfterPop.SetNum(PlayerCount);
	InitialStackCounts.Init(0, PlayerCount);

	for (int32 PlayerIndex = 0; PlayerIndex < PlayerCount; ++PlayerIndex)
	{
		APlayerController* Controller = Controllers[PlayerIndex].Get();
		ULocalPlayerModalRootBase* Root =
			CreateWidget<ULocalPlayerModalRootBase>(Controller, GetRootWidgetClass());
		if (!RequireHarness(Root != nullptr,
			FString::Printf(TEXT("could not create root for player %d"), PlayerIndex)) ||
			!RequireHarness(Root->AddToPlayerScreen(1000 + PlayerIndex),
			FString::Printf(TEXT("could not add root to player screen %d"), PlayerIndex)))
		{
			return false;
		}
		Root->ActivateWidget();
		UCommonActivatableWidgetStack* Stack = Root->ResolvePlayerModalStack();
		if (!RequireGate(Stack != nullptr, GateIndependentRouters,
			FString::Printf(TEXT("root %d did not return its authored player-owned stack"),
				PlayerIndex)))
		{
			return false;
		}
		ULocalPlayerModalScreenBase* Home =
			Stack->AddWidget<ULocalPlayerModalScreenBase>(
				GetScreenWidgetClass(),
				[Epoch, PlayerIndex](ULocalPlayerModalScreenBase& Screen)
				{
					Screen.ConfigurePolicy(nullptr, nullptr, 0, PlayerIndex, INDEX_NONE,
						false, ((Epoch + PlayerIndex) & 1) != 0);
				});
		if (!RequireGate(Home != nullptr, GateIndependentRouters,
			FString::Printf(TEXT("could not create authored Home for player %d"), PlayerIndex)))
		{
			return false;
		}
		Roots[PlayerIndex] = Root;
		Homes[PlayerIndex] = Home;
	}
	return true;
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::BeginEpoch(int32 Epoch)
{
	if (Epoch < 0 || Epoch >= EpochCount)
	{
		return RequireHarness(false, TEXT("invalid admission epoch"));
	}
	CurrentEpoch = Epoch;
	CurrentSharedKey = EpochKeys[Epoch];
	FirstOwner = Epoch == 0 ? 0 : 1;
	SecondOwner = 1 - FirstOwner;
	const int32 ModalDepths[PlayerCount] = {
		Epoch == 0 ? 2 : 1,
		Epoch == 0 ? 1 : 2 };

	for (int32 PlayerIndex = 0; PlayerIndex < PlayerCount; ++PlayerIndex)
	{
		UCommonActivatableWidgetStack* Stack = Roots[PlayerIndex].IsValid()
			? Roots[PlayerIndex]->ResolvePlayerModalStack()
			: nullptr;
		if (!RequireHarness(Stack != nullptr, TEXT("stack disappeared before epoch push")))
		{
			return false;
		}
		ULocalPlayerModalScreenBase* Prior = Homes[PlayerIndex].Get();
		for (int32 ModalOrdinal = 0; ModalOrdinal < ModalDepths[PlayerIndex]; ++ModalOrdinal)
		{
			UInputMappingContext* Context = NewObject<UInputMappingContext>(this,
				*FString::Printf(TEXT("AdmissionContext_E%d_P%d_M%d"),
					Epoch, PlayerIndex, ModalOrdinal));
			Context->MapKey(SharedAction, CurrentSharedKey);
			const int32 Priority = 100 + Epoch * 20 + PlayerIndex * 4 + ModalOrdinal;
			ULocalPlayerModalScreenBase* Screen =
				Stack->AddWidget<ULocalPlayerModalScreenBase>(
					GetScreenWidgetClass(),
					[this, Context, Priority, PlayerIndex, ModalOrdinal, Epoch](
						ULocalPlayerModalScreenBase& NewScreen)
					{
						NewScreen.ConfigurePolicy(SharedAction, Context, Priority,
							PlayerIndex, ModalOrdinal, true,
							((Epoch + PlayerIndex + ModalOrdinal) & 1) != 0);
					});
			if (!RequireHarness(Screen != nullptr,
				FString::Printf(TEXT("could not push epoch=%d player=%d modal=%d"),
					Epoch, PlayerIndex, ModalOrdinal)))
			{
				return false;
			}
			EpochContexts.Add(Context);
			ContextOwners.Add(PlayerIndex);
			ContextPriorities.Add(Priority);
			ContextScreens.Add(Screen);
			Prior = Screen;
			if (ModalOrdinal == ModalDepths[PlayerIndex] - 2)
			{
				TopsAfterPop[PlayerIndex] = Screen;
			}
		}
		ActionTargets[PlayerIndex] = Prior;
		if (!TopsAfterPop[PlayerIndex].IsValid())
		{
			TopsAfterPop[PlayerIndex] = Homes[PlayerIndex];
		}
		InitialStackCounts[PlayerIndex] = ModalDepths[PlayerIndex] + 1;
	}

	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-POLICY epoch=%d first_owner=%d second_owner=%d key=%s depths=(%d,%d)"),
		Epoch, FirstOwner, SecondOwner, *CurrentSharedKey.ToString(),
		InitialStackCounts[0] - 1, InitialStackCounts[1] - 1);
	return true;
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::VerifyFocus(
	int32 PlayerIndex, UButton* Expected, const TCHAR* Gate, const TCHAR* Stage)
{
	if (!Expected || !Controllers.IsValidIndex(PlayerIndex) ||
		!LocalPlayers.IsValidIndex(PlayerIndex))
	{
		return RequireHarness(false, TEXT("focus verifier received invalid state"));
	}
	APlayerController* Controller = Controllers[PlayerIndex].Get();
	APlayerController* OtherController = Controllers[1 - PlayerIndex].Get();
	TSharedPtr<const FSlateUser> SlateUser = LocalPlayers[PlayerIndex]->GetSlateUser();
	TSharedPtr<SWidget> ExpectedSlate = Expected->GetCachedWidget();
	const int32 SlateUserIndex = SlateUser.IsValid() ? SlateUser->GetUserIndex() : INDEX_NONE;
	const TSharedPtr<SWidget> ActualSlate = SlateUserIndex != INDEX_NONE
		? FSlateApplication::Get().GetUserFocusedWidget(SlateUserIndex)
		: nullptr;
	const bool bOwnUMGFocus = Expected->HasUserFocus(Controller);
	const bool bForeignUMGFocus = Expected->HasUserFocus(OtherController);
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-FOCUS stage=%s player=%d slate_user=%d expected=%s actual=%s own=%d foreign=%d"),
		Stage, PlayerIndex, SlateUserIndex, *GetNameSafe(Expected),
		ActualSlate.IsValid() ? *ActualSlate->ToString() : TEXT("None"),
		bOwnUMGFocus ? 1 : 0, bForeignUMGFocus ? 1 : 0);
	return RequireGate(SlateUserIndex != INDEX_NONE && ExpectedSlate.IsValid() &&
		ActualSlate == ExpectedSlate && bOwnUMGFocus && !bForeignUMGFocus,
		Gate,
		FString::Printf(TEXT("%s player=%d did not hold exact independent Slate/UMG focus"),
			Stage, PlayerIndex));
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::VerifyContextMatrix(
	int32 PlayerIndex, ULocalPlayerModalScreenBase* ExpectedTop,
	const TCHAR* Stage)
{
	UEnhancedInputLocalPlayerSubsystem* Subsystem = InputSubsystems[PlayerIndex].Get();
	if (!RequireHarness(Subsystem != nullptr &&
		EpochContexts.Num() == ContextOwners.Num() &&
		EpochContexts.Num() == ContextPriorities.Num() &&
		EpochContexts.Num() == ContextScreens.Num(),
		TEXT("context matrix shape is invalid")))
	{
		return false;
	}
	int32 PresentCount = 0;
	for (int32 Index = 0; Index < EpochContexts.Num(); ++Index)
	{
		int32 ActualPriority = MIN_int32;
		const bool bPresent = Subsystem->HasMappingContext(
			EpochContexts[Index], ActualPriority);
		const bool bExpected = ContextOwners[Index] == PlayerIndex &&
			ContextScreens[Index].Get() == ExpectedTop && ExpectedTop != nullptr &&
			ExpectedTop->IsConfiguredModal();
		if (bPresent)
		{
			++PresentCount;
		}
		UE_LOG(LogTemp, Display,
			TEXT("LOCAL-PLAYER-MODAL-CONTEXT-ENTRY stage=%s player=%d index=%d context=%p owner=%d expected=%d actual=%d priority=%d/%d"),
			Stage, PlayerIndex, Index, EpochContexts[Index].Get(),
			ContextOwners[Index], bExpected ? 1 : 0, bPresent ? 1 : 0,
			ContextPriorities[Index], ActualPriority);
		if (!RequireGate(bPresent == bExpected &&
			(!bPresent || ActualPriority == ContextPriorities[Index]),
			GateOtherUnchanged,
			FString::Printf(
				TEXT("%s player=%d context=%d owner=%d expected=%d actual=%d priority=%d/%d"),
				Stage, PlayerIndex, Index, ContextOwners[Index], bExpected ? 1 : 0,
				bPresent ? 1 : 0, ContextPriorities[Index], ActualPriority)))
		{
			return false;
		}
	}
	const int32 ExpectedCount = ExpectedTop != nullptr &&
		ExpectedTop->IsConfiguredModal() ? 1 : 0;
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-CONTEXT stage=%s player=%d present=%d expected=%d"),
		Stage, PlayerIndex, PresentCount, ExpectedCount);
	return RequireGate(PresentCount == ExpectedCount, GateOtherUnchanged,
		FString::Printf(TEXT("%s player=%d context cardinality=%d expected=%d"),
			Stage, PlayerIndex, PresentCount, ExpectedCount));
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::VerifyPlayerState(
	int32 PlayerIndex,
	ULocalPlayerModalScreenBase* ExpectedTop,
	int32 ExpectedStackCount,
	const TCHAR* Stage)
{
	ULocalPlayerModalRootBase* Root = Roots[PlayerIndex].Get();
	UCommonActivatableWidgetStack* Stack = Root != nullptr
		? Root->ResolvePlayerModalStack() : nullptr;
	UCommonUIActionRouterBase* Router = ActionRouters[PlayerIndex].Get();
	const ECommonInputMode ExpectedMode = ExpectedTop != nullptr &&
		ExpectedTop->IsConfiguredModal() ? ECommonInputMode::Menu : ECommonInputMode::All;
	const bool bExpectedNormalGameInput = ExpectedMode == ECommonInputMode::All;
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-STATE stage=%s player=%d root=%p stack=%p count=%d expected_count=%d top=%p expected_top=%p router=%p leaf=%p mode=%d expected_mode=%d normal=%d"),
		Stage, PlayerIndex, Root, Stack,
		Stack != nullptr ? Stack->GetNumWidgets() : -1, ExpectedStackCount,
		Stack != nullptr ? Stack->GetActiveWidget() : nullptr, ExpectedTop,
		Router, Router != nullptr ? Router->GetLeafmostActivatableWidget() : nullptr,
		Router != nullptr
			? static_cast<int32>(Router->GetActiveInputMode(ECommonInputMode::All)) : -1,
		static_cast<int32>(ExpectedMode),
		Router != nullptr && Router->CanProcessNormalGameInput() ? 1 : 0);
	if (!RequireGate(Root != nullptr && Stack != nullptr && Router != nullptr &&
		ExpectedTop != nullptr && Stack->GetNumWidgets() == ExpectedStackCount &&
		Stack->GetActiveWidget() == ExpectedTop && ExpectedTop->IsActivated() &&
		Router->GetLeafmostActivatableWidget() == ExpectedTop &&
		Router->GetActiveInputMode(ECommonInputMode::All) == ExpectedMode &&
		Router->CanProcessNormalGameInput() == bExpectedNormalGameInput,
		GateIndependentRouters,
		FString::Printf(
			TEXT("%s player=%d stack/top/router mismatch count=%d expected=%d top=%s router_leaf=%s mode=%d normal=%d"),
			Stage, PlayerIndex, Stack != nullptr ? Stack->GetNumWidgets() : -1,
			ExpectedStackCount,
			Stack != nullptr ? *GetNameSafe(Stack->GetActiveWidget()) : TEXT("None"),
			Router != nullptr ? *GetNameSafe(Router->GetLeafmostActivatableWidget()) : TEXT("None"),
			Router != nullptr ? static_cast<int32>(Router->GetActiveInputMode(ECommonInputMode::All)) : -1,
			Router != nullptr && Router->CanProcessNormalGameInput() ? 1 : 0)))
	{
		return false;
	}
	return VerifyFocus(PlayerIndex, ExpectedTop->ResolveConfiguredFocusTarget(),
		GateFocusRestore, Stage) &&
		VerifyContextMatrix(PlayerIndex, ExpectedTop, Stage);
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::InjectSharedKey(
	int32 PlayerIndex, EInputEvent Event)
{
	if (!ViewportClient.IsValid() || !LocalPlayers.IsValidIndex(PlayerIndex) ||
		!Controllers.IsValidIndex(PlayerIndex))
	{
		return RequireHarness(false, TEXT("input injection state disappeared"));
	}
	ULocalPlayer* LocalPlayer = LocalPlayers[PlayerIndex].Get();
	const FInputDeviceId Device = UInputDeviceLibrary::GetPrimaryInputDeviceForUser(
		LocalPlayer->GetPlatformUserId());
	if (!RequireHarness(Device.IsValid(), TEXT("input injection device is invalid")))
	{
		return false;
	}
	const float Amount = Event == IE_Released ? 0.0f : 1.0f;
	FInputKeyEventArgs Args = FInputKeyEventArgs::CreateSimulated(
		CurrentSharedKey, Event, Amount, -1, Device, false,
		ViewportClient->GetGameViewport());
	Args.ControllerId = LocalPlayer->GetControllerId();
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-INJECT epoch=%d player=%d user=%d device=%d controller=%d key=%s event=%d"),
		CurrentEpoch, PlayerIndex, LocalPlayer->GetPlatformUserId().GetInternalId(),
		Device.GetId(), Args.ControllerId, *CurrentSharedKey.ToString(),
		static_cast<int32>(Event));
	ViewportClient->InputKey(Args);
	return true;
}

bool ALocalPlayerModalIsolationAdmissionFunctionalTest::VerifyAfterOwnedAction(
	int32 OwnerIndex, int32 OtherIndex, bool bOtherAlreadyPopped, const TCHAR* Stage)
{
	ULocalPlayerModalScreenBase* OwnerTarget = ActionTargets[OwnerIndex].Get();
	ULocalPlayerModalScreenBase* OwnerRestored = TopsAfterPop[OwnerIndex].Get();
	ULocalPlayerModalScreenBase* OtherActionTarget = ActionTargets[OtherIndex].Get();
	ULocalPlayerModalScreenBase* OtherExpectedTop = bOtherAlreadyPopped
		? TopsAfterPop[OtherIndex].Get()
		: OtherActionTarget;
	const int32 OtherExpectedActionCount = bOtherAlreadyPopped ? 1 : 0;
	const int32 OtherExpectedStackCount = InitialStackCounts[OtherIndex] -
		(bOtherAlreadyPopped ? 1 : 0);
	if (!RequireGate(OwnerTarget != nullptr && OwnerTarget->GetObservedActionCount() == 1,
		GateOwningAction,
		FString::Printf(TEXT("%s owner=%d target action count=%d expected=1"),
			Stage, OwnerIndex,
			OwnerTarget != nullptr ? OwnerTarget->GetObservedActionCount() : -1)) ||
		!RequireGate(OtherActionTarget != nullptr &&
			OtherActionTarget->GetObservedActionCount() == OtherExpectedActionCount,
			GateOwningAction,
			FString::Printf(TEXT("%s foreign player=%d action count=%d expected=%d"),
				Stage, OtherIndex,
				OtherActionTarget != nullptr
					? OtherActionTarget->GetObservedActionCount() : -1,
				OtherExpectedActionCount)) ||
		!VerifyPlayerState(OwnerIndex, OwnerRestored,
			InitialStackCounts[OwnerIndex] - 1, Stage) ||
		!VerifyPlayerState(OtherIndex, OtherExpectedTop,
			OtherExpectedStackCount, Stage))
	{
		return false;
	}
	return true;
}

void ALocalPlayerModalIsolationAdmissionFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	UWorld* World = GetWorld();
	if (!RequireHarness(World != nullptr, TEXT("no PIE UWorld")) ||
		!RequireHarness(FSlateApplication::IsInitialized(), TEXT("Slate is not initialized")) ||
		!RequireHarness(UCommonInputSettings::IsEnhancedInputSupportEnabled(),
			TEXT("task overlay did not enable CommonUI Enhanced Input support")) ||
		!ResolveTwoLocalPlayers())
	{
		return;
	}

	SharedAction = NewObject<UInputAction>(this, TEXT("AdmissionSharedModalAction"));
	SharedAction->ValueType = EInputActionValueType::Boolean;
	if (!RequireHarness(SharedAction != nullptr, TEXT("could not create shared transient input action")) ||
		!BuildHomeStacks(0))
	{
		return;
	}

	const double Now = World->GetTimeSeconds();
	SetCheckpointSchedule({
		Now + 0.25, Now + 0.50, Now + 0.75, Now + 1.00,
		Now + 1.25, Now + 1.50, Now + 1.75, Now + 2.00,
		Now + 2.25 });
}

void ALocalPlayerModalIsolationAdmissionFunctionalTest::OnCheckpoint(
	int32 CheckpointIndex, double TimeSeconds)
{
	UE_LOG(LogTemp, Display,
		TEXT("LOCAL-PLAYER-MODAL-CHECKPOINT index=%d world_time=%.3f epoch=%d"),
		CheckpointIndex, TimeSeconds, CurrentEpoch);

	if (CheckpointIndex == 0)
	{
		if (VerifyPlayerState(0, Homes[0].Get(), 1, TEXT("epoch0-home-p0")) &&
			VerifyPlayerState(1, Homes[1].Get(), 1, TEXT("epoch0-home-p1")))
		{
			BeginEpoch(0);
		}
		return;
	}
	if (CheckpointIndex == 1)
	{
		if (VerifyPlayerState(0, ActionTargets[0].Get(), InitialStackCounts[0],
				TEXT("epoch0-active-p0")) &&
			VerifyPlayerState(1, ActionTargets[1].Get(), InitialStackCounts[1],
				TEXT("epoch0-active-p1")))
		{
			InjectSharedKey(FirstOwner, IE_Pressed);
		}
		return;
	}
	if (CheckpointIndex == 2)
	{
		if (VerifyAfterOwnedAction(FirstOwner, SecondOwner, false,
			TEXT("epoch0-first-pop")))
		{
			InjectSharedKey(FirstOwner, IE_Released);
			InjectSharedKey(SecondOwner, IE_Pressed);
		}
		return;
	}
	if (CheckpointIndex == 3)
	{
		if (VerifyAfterOwnedAction(SecondOwner, FirstOwner, true,
			TEXT("epoch0-second-pop")))
		{
			InjectSharedKey(SecondOwner, IE_Released);
			BuildHomeStacks(1);
		}
		return;
	}
	if (CheckpointIndex == 4)
	{
		if (VerifyPlayerState(0, Homes[0].Get(), 1, TEXT("epoch1-home-p0")) &&
			VerifyPlayerState(1, Homes[1].Get(), 1, TEXT("epoch1-home-p1")))
		{
			BeginEpoch(1);
		}
		return;
	}
	if (CheckpointIndex == 5)
	{
		if (VerifyPlayerState(0, ActionTargets[0].Get(), InitialStackCounts[0],
				TEXT("epoch1-active-p0")) &&
			VerifyPlayerState(1, ActionTargets[1].Get(), InitialStackCounts[1],
				TEXT("epoch1-active-p1")))
		{
			InjectSharedKey(FirstOwner, IE_Pressed);
		}
		return;
	}
	if (CheckpointIndex == 6)
	{
		if (VerifyAfterOwnedAction(FirstOwner, SecondOwner, false,
			TEXT("epoch1-first-pop")))
		{
			InjectSharedKey(FirstOwner, IE_Released);
			InjectSharedKey(SecondOwner, IE_Pressed);
		}
		return;
	}
	if (CheckpointIndex == 7)
	{
		if (VerifyAfterOwnedAction(SecondOwner, FirstOwner, true,
			TEXT("epoch1-second-pop")))
		{
			InjectSharedKey(SecondOwner, IE_Released);
		}
		return;
	}
	if (CheckpointIndex == 8)
	{
		if (!RequireGate(GameInstance.IsValid() &&
			GameInstance->GetNumLocalPlayers() == PlayerCount &&
			ActionRouters[0].IsValid() && ActionRouters[1].IsValid() &&
			ActionRouters[0].Get() != ActionRouters[1].Get(),
			GateIndependentRouters,
			TEXT("final exact-two identity sentinel changed")))
		{
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded,
			FString::Printf(
				TEXT("%s players=2 epochs=2 EachPlayerOwnsIndependentActionRouter TopModalConsumesOnlyOwningPlayersAction DismissRestoresOnlyThatPlayersFocus OtherPlayersStackNeverChanges"),
				*GetSuccessMarker()));
	}
}

void ALocalPlayerModalIsolationAdmissionFunctionalTest::RemoveAdmissionUI()
{
	for (TWeakObjectPtr<ULocalPlayerModalRootBase>& RootPtr : Roots)
	{
		if (ULocalPlayerModalRootBase* Root = RootPtr.Get())
		{
			if (UCommonActivatableWidgetStack* Stack = Root->ResolvePlayerModalStack())
			{
				Stack->ClearWidgets();
			}
			Root->DeactivateWidget();
			Root->RemoveFromParent();
		}
	}
	Roots.Reset();
	Homes.Reset();
	ActionTargets.Reset();
	TopsAfterPop.Reset();
}

void ALocalPlayerModalIsolationAdmissionFunctionalTest::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	RemoveAdmissionUI();
	if (bReassignedSecondInputDevice && ReassignedSecondInputDevice.IsValid())
	{
		IPlatformInputDeviceMapper& DeviceMapper = IPlatformInputDeviceMapper::Get();
		const FPlatformUserId CurrentOwner =
			DeviceMapper.GetUserForInputDevice(ReassignedSecondInputDevice);
		if (PreviousSecondInputDeviceOwner.IsValid())
		{
			if (CurrentOwner.IsValid() && CurrentOwner != PreviousSecondInputDeviceOwner)
			{
				DeviceMapper.Internal_ChangeInputDeviceUserMapping(
					ReassignedSecondInputDevice,
					PreviousSecondInputDeviceOwner,
					CurrentOwner);
			}
			else if (!CurrentOwner.IsValid())
			{
				DeviceMapper.Internal_MapInputDeviceToUser(
					ReassignedSecondInputDevice,
					PreviousSecondInputDeviceOwner,
					EInputDeviceConnectionState::Connected);
			}
		}
		else
		{
			DeviceMapper.Internal_MapInputDeviceToUser(
				ReassignedSecondInputDevice,
				PLATFORMUSERID_NONE,
				EInputDeviceConnectionState::Disconnected);
		}
		bReassignedSecondInputDevice = false;
		ReassignedSecondInputDevice = INPUTDEVICEID_NONE;
		PreviousSecondInputDeviceOwner = PLATFORMUSERID_NONE;
	}
	if (bCreatedSecondLocalPlayer && GameInstance.IsValid() && LocalPlayers.Num() == PlayerCount)
	{
		if (ULocalPlayer* Second = LocalPlayers[1].Get();
			Second != nullptr && GameInstance->GetLocalPlayers().Contains(Second))
		{
			GameInstance->RemoveLocalPlayer(Second);
		}
	}
	Super::EndPlay(EndPlayReason);
}
