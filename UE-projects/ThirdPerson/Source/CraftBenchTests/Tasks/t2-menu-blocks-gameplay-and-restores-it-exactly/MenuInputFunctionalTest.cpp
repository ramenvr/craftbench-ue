// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputFunctionalTest.h"

#include "CommonGameViewportClient.h"
#include "CommonInputSettings.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/LocalPlayer.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/Character.h"
#include "GameFramework/InputDeviceLibrary.h"
#include "GameFramework/PlayerController.h"
#include "Input/CommonUIActionRouterBase.h"
#include "Input/CommonUIInputTypes.h"
#include "InputKeyEventArgs.h"
#include "InputMappingContext.h"
#include "Kismet/GameplayStatics.h"
#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputRuntime.h"
#include "Widgets/CommonActivatableWidgetContainer.h"

namespace
{
	const FName HostTag(TEXT("MenuInputHost"));
	const FName PolicyTag(TEXT("MenuInputPolicy"));
	const TCHAR* MenuClassPath =
		TEXT("/Game/Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/WBP_InputBlockingMenu.WBP_InputBlockingMenu_C");
	const TCHAR* StockContextPath = TEXT("/Game/Input/IMC_Default.IMC_Default");
	const TCHAR* SupportRoot =
		TEXT("/Game/Maps/t2-menu-blocks-gameplay-and-restores-it-exactly/Support/");

	constexpr int32 GameplayPriorities[2] = { 31, 47 };
	constexpr int32 MenuPriorities[2] = { 103, 151 };
	constexpr int32 UnrelatedPriorities[2] = { -17, 11 };
	const FKey SharedKeys[2] = { EKeys::E, EKeys::Q };

	FString SupportPath(const TCHAR* Name)
	{
		return FString(SupportRoot) + Name + TEXT(".") + Name;
	}
}

TOptional<FUIInputConfig> UMenuInputAdmissionScreen::GetDesiredInputConfig() const
{
	return FUIInputConfig(ECommonInputMode::Menu, EMouseCaptureMode::NoCapture);
}

void UMenuInputAdmissionScreen::NativeOnActivated()
{
	AppliedContext = GetMenuInputPolicy() != nullptr
		? GetMenuInputPolicy()->GetCurrentMenuContext()
		: nullptr;
	const int32 MenuContextPriority = GetMenuInputPolicy() != nullptr
		? GetMenuInputPolicy()->GetCurrentMenuPriority()
		: 0;
	Super::NativeOnActivated();
	if (AppliedContext != nullptr && GetMenuInputSubsystem() != nullptr)
	{
		FModifyContextOptions Options;
		Options.bForceImmediately = true;
		GetMenuInputSubsystem()->AddMappingContext(
			AppliedContext, MenuContextPriority, Options);
	}
}

void UMenuInputAdmissionScreen::NativeOnDeactivated()
{
	if (AppliedContext != nullptr && GetMenuInputSubsystem() != nullptr)
	{
		FModifyContextOptions Options;
		Options.bForceImmediately = true;
		GetMenuInputSubsystem()->RemoveMappingContext(AppliedContext, Options);
	}
	AppliedContext = nullptr;
	Super::NativeOnDeactivated();
}

AMenuInputFunctionalTestBase::AMenuInputFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

bool AMenuInputFunctionalTestBase::RequireHarness(bool bCondition, const FString& Detail)
{
	if (!bCondition)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Detail));
		return false;
	}
	return true;
}

bool AMenuInputFunctionalTestBase::FailGate(const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]: %s"), Gate, *Detail));
	return false;
}

bool AMenuInputFunctionalTestBase::RequireGate(
	bool bCondition, const TCHAR* Gate, const FString& Detail)

{
	return bCondition ? true : FailGate(Gate, Detail);
}

bool AMenuInputFunctionalTestBase::LoadProtectedSupport()
{
	GameplayAction = LoadObject<UInputAction>(nullptr, *SupportPath(TEXT("IA_GameplayProbe")));
	MenuAction = LoadObject<UInputAction>(nullptr, *SupportPath(TEXT("IA_MenuProbe")));
	UnrelatedAction = LoadObject<UInputAction>(nullptr, *SupportPath(TEXT("IA_UnrelatedProbe")));
	StockMovementContext = LoadObject<UInputMappingContext>(nullptr, StockContextPath);

	GameplayContexts = {
		LoadObject<UInputMappingContext>(nullptr, *SupportPath(TEXT("IMC_GameplayQuartz"))),
		LoadObject<UInputMappingContext>(nullptr, *SupportPath(TEXT("IMC_GameplayViolet"))) };
	MenuContexts = {
		LoadObject<UInputMappingContext>(nullptr, *SupportPath(TEXT("IMC_MenuQuartz"))),
		LoadObject<UInputMappingContext>(nullptr, *SupportPath(TEXT("IMC_MenuViolet"))) };
	UnrelatedContexts = {
		LoadObject<UInputMappingContext>(nullptr, *SupportPath(TEXT("IMC_UnrelatedQuartz"))),
		LoadObject<UInputMappingContext>(nullptr, *SupportPath(TEXT("IMC_UnrelatedViolet"))) };

	return RequireHarness(GameplayAction != nullptr && MenuAction != nullptr && UnrelatedAction != nullptr,
		TEXT("protected probe input actions are missing")) &&
		RequireHarness(StockMovementContext != nullptr, TEXT("stock IMC_Default is missing")) &&
		RequireHarness(GameplayContexts.Num() == 2 && MenuContexts.Num() == 2 &&
			UnrelatedContexts.Num() == 2 && GameplayContexts[0] != nullptr && GameplayContexts[1] != nullptr &&
			MenuContexts[0] != nullptr && MenuContexts[1] != nullptr &&
			UnrelatedContexts[0] != nullptr && UnrelatedContexts[1] != nullptr,
			TEXT("protected two-leg context inventory is incomplete"));
}

bool AMenuInputFunctionalTestBase::ResolveWorldSupport()
{
	TArray<AActor*> Hosts;
	TArray<AActor*> Policies;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), HostTag, Hosts);
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), PolicyTag, Policies);
	if (!RequireGate(Hosts.Num() == 1 && Cast<AMenuInputHost>(Hosts[0]) != nullptr,
		TEXT("PopRestoresExactPriorContexts"), TEXT("expected exactly one supplied lifecycle host")) ||
		!RequireGate(Policies.Num() == 1 && Cast<AMenuInputPolicy>(Policies[0]) != nullptr,
			TEXT("PopRestoresExactPriorContexts"), TEXT("expected exactly one supplied world policy")))
	{
		return false;
	}
	Host = Cast<AMenuInputHost>(Hosts[0]);
	Policy = Cast<AMenuInputPolicy>(Policies[0]);
	return true;
}

bool AMenuInputFunctionalTestBase::StageLeg(int32 LegIndex)
{
	if (LegIndex < 0 || LegIndex > 1 || !InputSubsystem.IsValid() || !Policy.IsValid())
	{
		return RequireHarness(false, TEXT("invalid leg staging state"));
	}
	FModifyContextOptions Options;
	Options.bForceImmediately = true;
	for (UInputMappingContext* Context : GameplayContexts)
	{
		InputSubsystem->RemoveMappingContext(Context, Options);
	}
	for (UInputMappingContext* Context : MenuContexts)
	{
		InputSubsystem->RemoveMappingContext(Context, Options);
	}
	for (UInputMappingContext* Context : UnrelatedContexts)
	{
		InputSubsystem->RemoveMappingContext(Context, Options);
	}

	if (LegIndex == 0)
	{
		InputSubsystem->AddMappingContext(UnrelatedContexts[0], UnrelatedPriorities[0], Options);
		InputSubsystem->AddMappingContext(GameplayContexts[0], GameplayPriorities[0], Options);
	}
	else
	{
		InputSubsystem->AddMappingContext(GameplayContexts[1], GameplayPriorities[1], Options);
		InputSubsystem->AddMappingContext(UnrelatedContexts[1], UnrelatedPriorities[1], Options);
	}
	Policy->SetCurrentAssignment(MenuContexts[LegIndex], MenuAction, MenuPriorities[LegIndex]);
	return true;
}

bool AMenuInputFunctionalTestBase::RequireContext(
	const UInputMappingContext* Context,
	int32 ExpectedPriority,
	bool bExpectedPresent,
	const TCHAR* Gate,
	const TCHAR* Label)
{
	int32 FoundPriority = MIN_int32;
	const bool bPresent = InputSubsystem.IsValid() &&
		InputSubsystem->HasMappingContext(Context, FoundPriority);
	if (bPresent != bExpectedPresent || (bPresent && FoundPriority != ExpectedPriority))
	{
		return FailGate(Gate, FString::Printf(
			TEXT("%s expected present=%d priority=%d; found present=%d priority=%d"),
			Label, bExpectedPresent ? 1 : 0, ExpectedPriority,
			bPresent ? 1 : 0, FoundPriority));
	}
	return true;
}

bool AMenuInputFunctionalTestBase::RequirePriorState(
	int32 LegIndex, bool bMenuExpected, const TCHAR* Stage)
{
	if (!RequireContext(GameplayContexts[LegIndex], GameplayPriorities[LegIndex], true,
		TEXT("PopRestoresExactPriorContexts"), TEXT("current gameplay context")) ||
		!RequireContext(UnrelatedContexts[LegIndex], UnrelatedPriorities[LegIndex], true,
			TEXT("UnrelatedContextRemainsUntouched"), TEXT("current unrelated context")) ||
		!RequireContext(StockMovementContext, StockMovementPriority, true,
			TEXT("UnrelatedContextRemainsUntouched"), TEXT("stock movement context")) ||
		!RequireContext(MenuContexts[LegIndex], MenuPriorities[LegIndex], bMenuExpected,
			TEXT("PopRestoresExactPriorContexts"), TEXT("current menu context")) ||
		!RequireContext(MenuContexts[1 - LegIndex], MenuPriorities[1 - LegIndex], false,
			TEXT("PopRestoresExactPriorContexts"), TEXT("other menu context")))
	{
		return false;
	}
	UE_LOG(LogTemp, Display, TEXT("MENU-INPUT-CONTEXTS stage=%s leg=%d menu=%d"),
		Stage, LegIndex, bMenuExpected ? 1 : 0);
	return true;
}

bool AMenuInputFunctionalTestBase::RequireActiveMenu(
	UInputBlockingMenuBase* Expected, int32 LegIndex, const TCHAR* Stage)
{
	UCommonActivatableWidgetStack* Stack = Host.IsValid() ? Host->GetStack() : nullptr;
	return RequireGate(Expected != nullptr && Stack != nullptr &&
		Stack->GetActiveWidget() == Expected && Expected->IsActivated() &&
		ActionRouter.IsValid() && ActionRouter->GetLeafmostActivatableWidget() == Expected &&
		!ActionRouter->CanProcessNormalGameInput(),
		TEXT("TopMenuConsumesItsOwnAction"),
		FString::Printf(TEXT("%s leg=%d is not the exact active UI input leaf"), Stage, LegIndex));
}

bool AMenuInputFunctionalTestBase::InjectKey(
	const FKey& Key, EInputEvent Event, float Amount)
{
	if (!ViewportClient.IsValid() || !Controller.IsValid() || Controller->GetLocalPlayer() == nullptr)
	{
		return RequireHarness(false, TEXT("viewport or local player disappeared during input injection"));
	}
	const FPlatformUserId UserId = Controller->GetLocalPlayer()->GetPlatformUserId();
	const FInputDeviceId DeviceId = UInputDeviceLibrary::GetPrimaryInputDeviceForUser(UserId);
	if (!RequireHarness(DeviceId.IsValid(), TEXT("local player's primary input device is invalid")))
	{
		return false;
	}
	FInputKeyEventArgs Args = FInputKeyEventArgs::CreateSimulated(
		Key, Event, Amount, -1, DeviceId, false, ViewportClient->GetGameViewport());
	Args.ControllerId = 0;
	ViewportClient->InputKey(Args);
	return true;
}

void AMenuInputFunctionalTestBase::HandleGameplayAction(const FInputActionValue& Value)
{
	if (Value.Get<bool>())
	{
		++GameplayActionCount;
	}
}

void AMenuInputFunctionalTestBase::HandleUnrelatedAction(const FInputActionValue& Value)
{
	if (Value.Get<bool>())
	{
		++UnrelatedActionCount;
	}
}

void AMenuInputFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	UWorld* World = GetWorld();
	if (!RequireHarness(World != nullptr, TEXT("no PIE UWorld")) ||
		!RequireHarness(UCommonInputSettings::IsEnhancedInputSupportEnabled(),
			TEXT("task overlay did not enable Common UI Enhanced Input support")) ||
		!LoadProtectedSupport() || !ResolveWorldSupport())
	{
		return;
	}

	Controller = UGameplayStatics::GetPlayerController(World, 0);
	APawn* Pawn = Controller.IsValid() ? Controller->GetPawn() : nullptr;
	ACharacter* Character = Cast<ACharacter>(Pawn);
	ULocalPlayer* LocalPlayer = Controller.IsValid() ? Controller->GetLocalPlayer() : nullptr;
	InputSubsystem = LocalPlayer != nullptr
		? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>()
		: nullptr;
	ActionRouter = LocalPlayer != nullptr
		? LocalPlayer->GetSubsystem<UCommonUIActionRouterBase>()
		: nullptr;
	ViewportClient = World->GetGameViewport();
	PawnInputComponent = Pawn != nullptr
		? Cast<UEnhancedInputComponent>(Pawn->InputComponent)
		: nullptr;

	if (!RequireHarness(Controller.IsValid() && LocalPlayer != nullptr,
		TEXT("local player 0/controller is unavailable")) ||
		!RequireHarness(Character != nullptr && Character->GetMesh() != nullptr &&
			Character->GetMesh()->GetSkeletalMeshAsset() != nullptr &&
			Character->GetMesh()->GetAnimClass() != nullptr,
			TEXT("possessed Third Person character is not visibly represented")) ||
		!RequireHarness(PawnInputComponent != nullptr &&
			PawnInputComponent->GetActionEventBindings().Num() > 0,
			TEXT("possessed pawn is not drivable through Enhanced Input")) ||
		!RequireHarness(InputSubsystem.IsValid() && ActionRouter.IsValid(),
			TEXT("local input subsystem or Common UI action router is unavailable")) ||
		!RequireHarness(ViewportClient.IsValid() && ViewportClient->IsA<UCommonGameViewportClient>(),
			TEXT("task overlay did not create CommonGameViewportClient")))
	{
		return;
	}

	if (!RequireHarness(InputSubsystem->HasMappingContext(StockMovementContext, StockMovementPriority),
		TEXT("stock movement context is not active before grading")))
	{
		return;
	}
	PawnInputComponent->BindAction(GameplayAction, ETriggerEvent::Started,
		this, &AMenuInputFunctionalTestBase::HandleGameplayAction);
	PawnInputComponent->BindAction(UnrelatedAction, ETriggerEvent::Started,
		this, &AMenuInputFunctionalTestBase::HandleUnrelatedAction);

	FString Failure;
	if (!RequireHarness(Host->InitializeForPlayer(Controller.Get(), Failure),
		FString::Printf(TEXT("supplied menu host initialization failed: %s"), *Failure)))
	{
		return;
	}
	if (!RequireHarness(ActionRouter->CanProcessNormalGameInput(),
		TEXT("inactive menu stack root blocks normal gameplay input before grading")))
	{
		return;
	}

	const double Now = World->GetTimeSeconds();
	SetCheckpointSchedule({
		Now + 0.20, Now + 0.40, Now + 0.60, Now + 0.80, Now + 1.00,
		Now + 1.20, Now + 1.40, Now + 1.60, Now + 1.80, Now + 2.00,
		Now + 2.20, Now + 2.40, Now + 2.60, Now + 2.80, Now + 3.00 });
}

void AMenuInputFunctionalTestBase::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	UE_LOG(LogTemp, Display,
		TEXT("MENU-INPUT-CHECKPOINT mode=%s index=%d world_time=%.3f gameplay=%d unrelated=%d"),
		SuccessLabel(), CheckpointIndex, TimeSeconds, GameplayActionCount, UnrelatedActionCount);

	if (CheckpointIndex == 0)
	{
		if (StageLeg(0) && RequirePriorState(0, false, TEXT("leg-a-prior")))
		{
			InjectKey(SharedKeys[0], IE_Pressed, 1.0f);
		}
		return;
	}
	if (CheckpointIndex == 1)
	{
		if (!RequireGate(GameplayActionCount == 1, TEXT("PopRestoresExactPriorContexts"),
			TEXT("shared key did not reach gameplay before menu activation")))
		{
			return;
		}
		InjectKey(SharedKeys[0], IE_Released, 0.0f);
		InjectKey(EKeys::U, IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 2)
	{
		if (!RequireGate(UnrelatedActionCount == 1, TEXT("UnrelatedContextRemainsUntouched"),
			TEXT("unrelated action did not respond before menu activation")))
		{
			return;
		}
		InjectKey(EKeys::U, IE_Released, 0.0f);
		FString Failure;
		FirstMenu = Host->PushMenu(ResolveMenuClass(), Policy.Get(), Failure);
		RequireGate(FirstMenu.IsValid(), TEXT("TopMenuConsumesItsOwnAction"), Failure);
		return;
	}
	if (CheckpointIndex == 3)
	{
		if (!RequireActiveMenu(FirstMenu.Get(), 0, TEXT("leg-a-active")) ||
			!RequirePriorState(0, true, TEXT("leg-a-active")))
		{
			return;
		}
		InjectKey(SharedKeys[0], IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 4)
	{
		if (!RequireGate(FirstMenu.IsValid() && FirstMenu->GetObservedMenuActionCount() == 1,
			TEXT("TopMenuConsumesItsOwnAction"),
			TEXT("shared key did not invoke the exact active menu action once")) ||
			!RequireGate(GameplayActionCount == 1,
				TEXT("GameplayActionBlockedWhileMenuActive"),
				TEXT("gameplay action fired behind the first active menu")))
		{
			return;
		}
		InjectKey(SharedKeys[0], IE_Released, 0.0f);
		Policy->SetCurrentAssignment(MenuContexts[1], MenuAction, MenuPriorities[1]);
		FString Failure;
		RequireGate(Host->PopMenu(Failure), TEXT("PopRestoresExactPriorContexts"), Failure);
		return;
	}
	if (CheckpointIndex == 5)
	{
		if (!RequirePriorState(0, false, TEXT("leg-a-popped")) ||
			!RequireGate(ActionRouter->CanProcessNormalGameInput(),
				TEXT("PopRestoresExactPriorContexts"),
				TEXT("normal game input remained blocked after first pop")))
		{
			return;
		}
		InjectKey(SharedKeys[0], IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 6)
	{
		if (!RequireGate(GameplayActionCount == 2,
			TEXT("PopRestoresExactPriorContexts"),
			TEXT("gameplay action did not resume after first pop")))
		{
			return;
		}
		InjectKey(SharedKeys[0], IE_Released, 0.0f);
		InjectKey(EKeys::U, IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 7)
	{
		if (!RequireGate(UnrelatedActionCount == 2,
			TEXT("UnrelatedContextRemainsUntouched"),
			TEXT("unrelated action did not resume unchanged after first pop")))
		{
			return;
		}
		InjectKey(EKeys::U, IE_Released, 0.0f);
		if (!StageLeg(1) || !RequirePriorState(1, false, TEXT("leg-b-prior")))
		{
			return;
		}
		FString Failure;
		SecondMenu = Host->PushMenu(ResolveMenuClass(), Policy.Get(), Failure);
		RequireGate(SecondMenu.IsValid(), TEXT("TopMenuConsumesItsOwnAction"), Failure);
		return;
	}
	if (CheckpointIndex == 8)
	{
		if (!RequireActiveMenu(SecondMenu.Get(), 1, TEXT("leg-b-active")) ||
			!RequirePriorState(1, true, TEXT("leg-b-active")))
		{
			return;
		}
		InjectKey(SharedKeys[1], IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 9)
	{
		if (!RequireGate(SecondMenu.IsValid() && SecondMenu->GetObservedMenuActionCount() == 1,
			TEXT("TopMenuConsumesItsOwnAction"),
			TEXT("second world-assigned menu did not consume the shared key")) ||
			!RequireGate(GameplayActionCount == 2,
				TEXT("GameplayActionBlockedWhileMenuActive"),
				TEXT("gameplay action fired behind the second active menu")))
		{
			return;
		}
		InjectKey(SharedKeys[1], IE_Released, 0.0f);
		FString Failure;
		RequireGate(Host->PopMenu(Failure), TEXT("PopRestoresExactPriorContexts"), Failure);
		return;
	}
	if (CheckpointIndex == 10)
	{
		if (!RequirePriorState(1, false, TEXT("leg-b-popped")) ||
			!RequireGate(ActionRouter->CanProcessNormalGameInput(),
				TEXT("PopRestoresExactPriorContexts"),
				TEXT("normal game input remained blocked after second pop")))
		{
			return;
		}
		InjectKey(SharedKeys[1], IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 11)
	{
		if (!RequireGate(GameplayActionCount == 3,
			TEXT("PopRestoresExactPriorContexts"),
			TEXT("gameplay action did not resume after second pop")))
		{
			return;
		}
		InjectKey(SharedKeys[1], IE_Released, 0.0f);
		InjectKey(EKeys::U, IE_Pressed, 1.0f);
		return;
	}
	if (CheckpointIndex == 12)
	{
		if (!RequireGate(UnrelatedActionCount == 3,
			TEXT("UnrelatedContextRemainsUntouched"),
			TEXT("unrelated action did not remain usable after second pop")))
		{
			return;
		}
		InjectKey(EKeys::U, IE_Released, 0.0f);
		return;
	}
	if (CheckpointIndex == 13)
	{
		RequirePriorState(1, false, TEXT("final-stability"));
		return;
	}
	if (CheckpointIndex == 14)
	{
		if (!RequirePriorState(1, false, TEXT("final-sentinel")))
		{
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded,
			FString::Printf(TEXT("MENU-INPUT-%s-PASS GameplayActionBlockedWhileMenuActive TopMenuConsumesItsOwnAction PopRestoresExactPriorContexts UnrelatedContextRemainsUntouched gameplay=%d unrelated=%d"),
				SuccessLabel(), GameplayActionCount, UnrelatedActionCount));
	}
}

TSubclassOf<UInputBlockingMenuBase> AMenuInputFunctionalTest::ResolveMenuClass() const
{
	return LoadClass<UInputBlockingMenuBase>(nullptr, MenuClassPath);
}

TSubclassOf<UInputBlockingMenuBase> AMenuInputAdmissionFunctionalTest::ResolveMenuClass() const
{
	return UMenuInputAdmissionScreen::StaticClass();
}
