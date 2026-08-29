// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/CommonUIFocusAdmissionFunctionalTest.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Button.h"
#include "Components/VerticalBox.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Modules/ModuleManager.h"
#include "Widgets/CommonActivatableWidgetContainer.h"

TSharedRef<SWidget> UCommonUIFocusProbeScreen::RebuildWidget()
{
	if (WidgetTree == nullptr)
	{
		WidgetTree = NewObject<UWidgetTree>(this, TEXT("WidgetTree"));
	}
	if (PrimaryButton == nullptr || AlternateButton == nullptr)
	{
		UVerticalBox* Layout = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("ProbeLayout"));
		PrimaryButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("ProbePrimary"));
		AlternateButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("ProbeAlternate"));
		Layout->AddChildToVerticalBox(PrimaryButton);
		Layout->AddChildToVerticalBox(AlternateButton);
		WidgetTree->RootWidget = Layout;
	}
	return Super::RebuildWidget();
}

UWidget* UCommonUIFocusProbeScreen::NativeGetDesiredFocusTarget() const
{
	return bPreferredAlternate ? AlternateButton.Get() : PrimaryButton.Get();
}

TSharedRef<SWidget> UCommonUIFocusProbeRoot::RebuildWidget()
{
	if (WidgetTree == nullptr)
	{
		WidgetTree = NewObject<UWidgetTree>(this, TEXT("WidgetTree"));
	}
	if (Stack == nullptr)
	{
		Stack = WidgetTree->ConstructWidget<UCommonActivatableWidgetStack>(
			UCommonActivatableWidgetStack::StaticClass(), TEXT("ProbeStack"));
		Stack->SetTransitionDuration(0.0f);
		WidgetTree->RootWidget = Stack;
	}
	return Super::RebuildWidget();
}

ACommonUIFocusAdmissionFunctionalTest::ACommonUIFocusAdmissionFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

bool ACommonUIFocusAdmissionFunctionalTest::Require(bool bCondition, const FString& FailureDetail)
{
	if (!bCondition)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("FOCUS-ADMISSION: %s"), *FailureDetail));
		return false;
	}
	return true;
}

bool ACommonUIFocusAdmissionFunctionalTest::RequireFocus(
	UButton* Expected,
	UButton* Unexpected,
	const TCHAR* Stage)
{
	APlayerController* PC = Controller.Get();
	const bool bExpectedFocused = Expected != nullptr && PC != nullptr && Expected->HasUserFocus(PC);
	const bool bUnexpectedFocused = Unexpected != nullptr && PC != nullptr && Unexpected->HasUserFocus(PC);
	UE_LOG(LogTemp, Display, TEXT("[focus-admission] stage=%s expected=%s unexpected=%s expected_focus=%s unexpected_focus=%s"),
		Stage, *GetNameSafe(Expected), *GetNameSafe(Unexpected),
		bExpectedFocused ? TEXT("true") : TEXT("false"),
		bUnexpectedFocused ? TEXT("true") : TEXT("false"));
	return Require(
		bExpectedFocused && !bUnexpectedFocused,
		FString::Printf(TEXT("%s expected exact user-0 focus on '%s'; unexpected '%s' focus=%s"),
			Stage, *GetNameSafe(Expected), *GetNameSafe(Unexpected),
			bUnexpectedFocused ? TEXT("true") : TEXT("false")));
}

void ACommonUIFocusAdmissionFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (!Require(World != nullptr, TEXT("no PIE UWorld")))
	{
		return;
	}
	Controller = UGameplayStatics::GetPlayerController(World, 0);
	if (!Require(Controller.IsValid() && Controller->GetLocalPlayer() != nullptr,
		TEXT("local user 0 or its PlayerController is unavailable")) ||
		!Require(FSlateApplication::IsInitialized(), TEXT("Slate is not initialized")) ||
		!Require(FModuleManager::Get().IsModuleLoaded(FName(TEXT("CommonUI"))), TEXT("CommonUI module is not loaded")) ||
		!Require(FModuleManager::Get().IsModuleLoaded(FName(TEXT("CommonInput"))), TEXT("CommonInput module is not loaded")))
	{
		return;
	}

	Sentinel = CreateWidget<UCommonUIFocusProbeScreen>(Controller.Get(), UCommonUIFocusProbeScreen::StaticClass());
	if (!Require(Sentinel.IsValid(), TEXT("could not create verifier-owned sentinel screen")))
	{
		return;
	}
	Sentinel->AddToViewport(2000);
	Sentinel->ActivateWidget();
	if (!Require(Sentinel->GetPrimaryButton() != nullptr, TEXT("sentinel focus button was not rebuilt")))
	{
		return;
	}
	Sentinel->GetPrimaryButton()->SetUserFocus(Controller.Get());

	const double Now = World->GetTimeSeconds();
	SetCheckpointSchedule({
		Now + 0.20, Now + 0.40, Now + 0.60,
		Now + 0.80, Now + 1.00, Now + 1.20,
		Now + 1.40, Now + 1.60, Now + 1.80 });
}

void ACommonUIFocusAdmissionFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	UE_LOG(LogTemp, Display, TEXT("[focus-admission] checkpoint=%d world_time=%.3f"), CheckpointIndex, TimeSeconds);
	APlayerController* PC = Controller.Get();
	if (!Require(PC != nullptr, TEXT("PlayerController disappeared during the probe")))
	{
		return;
	}

	if (CheckpointIndex == 0)
	{
		if (!RequireFocus(Sentinel.IsValid() ? Sentinel->GetPrimaryButton() : nullptr, nullptr, TEXT("sentinel")))
		{
			return;
		}
		Sentinel->DeactivateWidget();
		Sentinel->RemoveFromParent();

		Root = CreateWidget<UCommonUIFocusProbeRoot>(PC, UCommonUIFocusProbeRoot::StaticClass());
		if (!Require(Root.IsValid(), TEXT("could not create verifier-owned activatable root")))
		{
			return;
		}
		Root->AddToViewport(1000);
		Root->ActivateWidget();
		UCommonActivatableWidgetStack* Stack = Root->GetStack();
		if (!Require(Stack != nullptr, TEXT("root did not rebuild its activatable stack")))
		{
			return;
		}
		Home = Stack->AddWidget<UCommonUIFocusProbeScreen>(UCommonUIFocusProbeScreen::StaticClass());
		if (!Require(Home.IsValid(), TEXT("stack could not create Home")))
		{
			return;
		}
		HomePrimary = Home->GetPrimaryButton();
		return;
	}

	UCommonActivatableWidgetStack* Stack = Root.IsValid() ? Root->GetStack() : nullptr;
	if (!Require(Root.IsValid() && Stack != nullptr && Home.IsValid(),
		TEXT("root, stack, or Home disappeared")))
	{
		return;
	}

	if (CheckpointIndex == 1)
	{
		if (!Require(Stack->GetActiveWidget() == Home.Get() && Home->IsActivated(),
			TEXT("Home is not the exact active stack top")) ||
			!RequireFocus(HomePrimary.Get(), nullptr, TEXT("home-active")))
		{
			return;
		}
		Detail = Stack->AddWidget<UCommonUIFocusProbeScreen>(
			UCommonUIFocusProbeScreen::StaticClass(),
			[](UCommonUIFocusProbeScreen& Screen) { Screen.SetPreferredAlternate(false); });
		if (!Require(Detail.IsValid(), TEXT("stack could not push Detail")))
		{
			return;
		}
		DetailPrimary = Detail->GetPrimaryButton();
		DetailAlternate = Detail->GetAlternateButton();
		return;
	}

	if (CheckpointIndex == 2)
	{
		if (!Require(Stack->GetActiveWidget() == Detail.Get() && Detail->IsActivated() && !Home->IsActivated(),
			TEXT("Detail is not the only exact active stack top")) ||
			!RequireFocus(DetailPrimary.Get(), HomePrimary.Get(), TEXT("detail-primary")))
		{
			return;
		}
		DetailAlternate->SetUserFocus(PC);
		return;
	}

	if (CheckpointIndex == 3)
	{
		if (!RequireFocus(DetailAlternate.Get(), DetailPrimary.Get(), TEXT("visible-direct-focus")))
		{
			return;
		}
		Detail->RequestRefreshFocus();
		return;
	}

	if (CheckpointIndex == 4)
	{
		if (!RequireFocus(DetailPrimary.Get(), DetailAlternate.Get(), TEXT("active-refresh-focus")))
		{
			return;
		}
		Home->RequestRefreshFocus();
		return;
	}

	if (CheckpointIndex == 5)
	{
		if (!Require(Stack->GetActiveWidget() == Detail.Get() && !Home->IsActivated(),
			TEXT("buried Home request changed activation state")) ||
			!RequireFocus(DetailPrimary.Get(), HomePrimary.Get(), TEXT("buried-request-rejected")))
		{
			return;
		}
		Detail->DeactivateWidget();
		return;
	}

	if (CheckpointIndex == 6)
	{
		if (!Require(Stack->GetActiveWidget() == Home.Get() && Home->IsActivated(),
			TEXT("pop did not restore the same Home instance")) ||
			!RequireFocus(HomePrimary.Get(), DetailPrimary.Get(), TEXT("home-restored")))
		{
			return;
		}
		Detail = Stack->AddWidget<UCommonUIFocusProbeScreen>(
			UCommonUIFocusProbeScreen::StaticClass(),
			[](UCommonUIFocusProbeScreen& Screen) { Screen.SetPreferredAlternate(true); });
		if (!Require(Detail.IsValid(), TEXT("stack could not push Detail a second time")))
		{
			return;
		}
		DetailPrimary = Detail->GetPrimaryButton();
		DetailAlternate = Detail->GetAlternateButton();
		return;
	}

	if (CheckpointIndex == 7)
	{
		if (!Require(Stack->GetActiveWidget() == Detail.Get() && Detail->IsActivated() && !Home->IsActivated(),
			TEXT("reactivated Detail is not the exact active top")) ||
			!RequireFocus(DetailAlternate.Get(), DetailPrimary.Get(), TEXT("detail-alternate")))
		{
			return;
		}
		Stack->ClearWidgets();
		Root->DeactivateWidget();
		Root->RemoveFromParent();
		return;
	}

	if (CheckpointIndex == 8)
	{
		const bool bAnyMenuFocus =
			(HomePrimary.IsValid() && HomePrimary->HasUserFocus(PC)) ||
			(DetailPrimary.IsValid() && DetailPrimary->HasUserFocus(PC)) ||
			(DetailAlternate.IsValid() && DetailAlternate->HasUserFocus(PC));
		if (!Require(!Root->IsActivated() && Root->GetParent() == nullptr && !bAnyMenuFocus,
			TEXT("root close did not release activation and all menu focus")))
		{
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT("FOCUS-ADMISSION: all activation and focus telemetry passed"));
	}
}
