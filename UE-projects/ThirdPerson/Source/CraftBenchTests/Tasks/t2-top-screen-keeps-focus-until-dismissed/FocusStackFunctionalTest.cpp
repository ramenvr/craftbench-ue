// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/FocusStackFunctionalTest.h"

#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/CommonUIFocusAdmissionFunctionalTest.h"
#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/MenuFocusPolicy.h"

#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetTree.h"
#include "CommonActivatableWidget.h"
#include "Components/Button.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Modules/ModuleManager.h"
#include "Widgets/CommonActivatableWidgetContainer.h"

namespace
{
	const FName HostTag(TEXT("MenuLifecycleHost"));
	const FName PolicyTag(TEXT("MenuFocusPolicy"));
	const FName StackName(TEXT("ScreenStack"));
	const FName HomeButtonName(TEXT("Button_HomePrimary"));
	const FName DetailPrimaryName(TEXT("Button_DetailPrimary"));
	const FName DetailAlternateName(TEXT("Button_DetailAlternate"));
	const FName OpenDetailsName(TEXT("OpenDetails"));
	const FName DismissTopName(TEXT("DismissTop"));
	const FName CloseMenuName(TEXT("CloseMenu"));
	const TCHAR* RootGeneratedClassPath =
		TEXT("/Game/Tasks/t2-top-screen-keeps-focus-until-dismissed/WBP_MenuRoot.WBP_MenuRoot_C");
}

AMenuLifecycleHost::AMenuLifecycleHost()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(HostTag);
}

bool AMenuLifecycleHost::CreateRoot(APlayerController* OwningController, FString& OutFailure)
{
	RemoveRoot();
	if (OwningController == nullptr)
	{
		OutFailure = TEXT("local player controller is null");
		return false;
	}

	UClass* RootClass = LoadClass<UCommonActivatableWidget>(nullptr, RootGeneratedClassPath);
	if (RootClass == nullptr || !RootClass->IsChildOf(UCommonActivatableWidget::StaticClass()))
	{
		OutFailure = TEXT("WBP_MenuRoot generated class is missing or not activatable");
		return false;
	}

	Root = CreateWidget<UCommonActivatableWidget>(OwningController, RootClass);
	if (Root == nullptr)
	{
		OutFailure = TEXT("WBP_MenuRoot could not be instantiated");
		return false;
	}
	Root->AddToViewport(1000);
	return RefreshLivePointers(OutFailure);
}

bool AMenuLifecycleHost::ActivateRoot(FString& OutFailure)
{
	if (Root == nullptr)
	{
		OutFailure = TEXT("root instance is null");
		return false;
	}
	Root->ActivateWidget();
	return true;
}

bool AMenuLifecycleHost::InvokeRootCommand(FName CommandName, FString& OutFailure)
{
	if (Root == nullptr)
	{
		OutFailure = TEXT("root instance is null");
		return false;
	}
	UFunction* Function = Root->FindFunction(CommandName);
	if (Function == nullptr || Function->NumParms != 0)
	{
		OutFailure = FString::Printf(TEXT("required zero-argument command '%s' is unavailable"),
			*CommandName.ToString());
		return false;
	}
	Root->ProcessEvent(Function, nullptr);
	return true;
}

bool AMenuLifecycleHost::RefreshLivePointers(FString& OutFailure)
{
	Stack = nullptr;
	Home = nullptr;
	ActiveDetail = nullptr;
	HomePrimary = nullptr;
	DetailPrimary = nullptr;
	DetailAlternate = nullptr;

	if (Root == nullptr || Root->WidgetTree == nullptr)
	{
		OutFailure = TEXT("root has no live WidgetTree");
		return false;
	}
	Stack = Cast<UCommonActivatableWidgetStack>(Root->WidgetTree->FindWidget(StackName));
	if (Stack == nullptr)
	{
		OutFailure = TEXT("root has no activation stack named ScreenStack");
		return false;
	}

	Home = Stack->GetRootContent();
	if (Home == nullptr || Home->WidgetTree == nullptr)
	{
		OutFailure = TEXT("activation stack has no live Home root content");
		return false;
	}
	HomePrimary = Cast<UButton>(Home->WidgetTree->FindWidget(HomeButtonName));
	if (HomePrimary == nullptr)
	{
		OutFailure = TEXT("Home has no button named Button_HomePrimary");
		return false;
	}

	UCommonActivatableWidget* Top = Stack->GetActiveWidget();
	if (Top != nullptr && Top != Home)
	{
		ActiveDetail = Top;
		if (Top->WidgetTree == nullptr)
		{
			OutFailure = TEXT("active Detail has no live WidgetTree");
			return false;
		}
		DetailPrimary = Cast<UButton>(Top->WidgetTree->FindWidget(DetailPrimaryName));
		DetailAlternate = Cast<UButton>(Top->WidgetTree->FindWidget(DetailAlternateName));
		if (DetailPrimary == nullptr || DetailAlternate == nullptr)
		{
			OutFailure = TEXT("active Detail does not expose both declared action buttons");
			return false;
		}
	}
	return true;
}

bool AMenuLifecycleHost::AttemptBuriedScreenFocusForTest(FString& OutFailure)
{
	if (!RefreshLivePointers(OutFailure))
	{
		return false;
	}
	if (Home == nullptr || ActiveDetail == nullptr || Stack->GetActiveWidget() != ActiveDetail)
	{
		OutFailure = TEXT("buried Home and active Detail are not simultaneously available");
		return false;
	}
	Home->RequestRefreshFocus();
	return true;
}

void AMenuLifecycleHost::RemoveRoot()
{
	if (Root != nullptr)
	{
		Root->DeactivateWidget();
		Root->RemoveFromParent();
	}
	Root = nullptr;
	Stack = nullptr;
	Home = nullptr;
	ActiveDetail = nullptr;
	HomePrimary = nullptr;
	DetailPrimary = nullptr;
	DetailAlternate = nullptr;
}

AFocusStackFunctionalTest::AFocusStackFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

bool AFocusStackFunctionalTest::RequireHarness(bool bCondition, const FString& Detail)
{
	if (!bCondition)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Detail));
		return false;
	}
	return true;
}

bool AFocusStackFunctionalTest::FailGate(const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]: %s"), Gate, *Detail));
	return false;
}

bool AFocusStackFunctionalTest::RequireGate(
	bool bCondition, const TCHAR* Gate, const FString& Detail)
{
	return bCondition ? true : FailGate(Gate, Detail);
}

void AFocusStackFunctionalTest::LogFocus(const TCHAR* Stage) const
{
	APlayerController* PC = Controller.Get();
	auto OwnsFocus = [PC](const UButton* Button)
	{
		return Button != nullptr && PC != nullptr && Button->HasUserFocus(PC);
	};
	UE_LOG(LogTemp, Display,
		TEXT("[focus-stack] stage=%s home=%d first_primary=%d first_alt=%d second_primary=%d second_alt=%d"),
		Stage,
		OwnsFocus(HomePrimary.Get()) ? 1 : 0,
		OwnsFocus(FirstDetailPrimary.Get()) ? 1 : 0,
		OwnsFocus(FirstDetailAlternate.Get()) ? 1 : 0,
		OwnsFocus(SecondDetailPrimary.Get()) ? 1 : 0,
		OwnsFocus(SecondDetailAlternate.Get()) ? 1 : 0);
}

bool AFocusStackFunctionalTest::RequireExactFocus(
	UButton* Expected,
	const TArray<UButton*>& MustNotOwnFocus,
	const TCHAR* Gate,
	const TCHAR* Stage)
{
	APlayerController* PC = Controller.Get();
	LogFocus(Stage);
	if (Expected == nullptr || PC == nullptr || !Expected->HasUserFocus(PC))
	{
		return FailGate(Gate, FString::Printf(TEXT("%s expected focus target does not own user-0 focus"), Stage));
	}
	for (UButton* Unexpected : MustNotOwnFocus)
	{
		if (Unexpected != nullptr && Unexpected->HasUserFocus(PC))
		{
			return FailGate(Gate, FString::Printf(TEXT("%s an unexpected menu action owns user-0 focus"), Stage));
		}
	}
	return true;
}

bool AFocusStackFunctionalTest::ResolveProtectedActors()
{
	UWorld* World = GetWorld();
	TArray<AMenuLifecycleHost*> Hosts;
	TArray<AMenuFocusPolicy*> Policies;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor->ActorHasTag(HostTag))
		{
			if (AMenuLifecycleHost* Candidate = Cast<AMenuLifecycleHost>(Actor))
			{
				Hosts.Add(Candidate);
			}
			else
			{
				return RequireHarness(false, TEXT("MenuLifecycleHost tag is attached to the wrong verifier class"));
			}
		}
		if (Actor->ActorHasTag(PolicyTag))
		{
			if (AMenuFocusPolicy* Candidate = Cast<AMenuFocusPolicy>(Actor))
			{
				Policies.Add(Candidate);
			}
			else
			{
				return FailGate(TEXT("world_policy_changes_reactivated_focus"),
					TEXT("MenuFocusPolicy tag is attached to the wrong class"));
			}
		}
	}
	if (!RequireHarness(Hosts.Num() == 1, TEXT("map must contain exactly one verifier-owned MenuLifecycleHost")))
	{
		return false;
	}
	if (!RequireGate(Policies.Num() == 1, TEXT("world_policy_changes_reactivated_focus"),
		TEXT("expected exactly one world menu-policy actor")))
	{
		return false;
	}
	Host = Hosts[0];
	Policy = Policies[0];
	return true;
}

bool AFocusStackFunctionalTest::RefreshGeneratedState(const TCHAR* Gate, const TCHAR* Stage)
{
	if (!Host.IsValid())
	{
		return RequireHarness(false, TEXT("verifier lifecycle host disappeared"));
	}
	FString Failure;
	return RequireGate(Host->RefreshLivePointers(Failure), Gate,
		FString::Printf(TEXT("%s: %s"), Stage, *Failure));
}

void AFocusStackFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	UWorld* World = GetWorld();
	if (!RequireHarness(World != nullptr, TEXT("no PIE UWorld")))
	{
		return;
	}
	Controller = UGameplayStatics::GetPlayerController(World, 0);
	if (!RequireHarness(Controller.IsValid() && Controller->GetLocalPlayer() != nullptr,
		TEXT("local user 0 or PlayerController is unavailable")) ||
		!RequireHarness(FSlateApplication::IsInitialized(), TEXT("Slate is not initialized")) ||
		!RequireHarness(FModuleManager::Get().IsModuleLoaded(FName(TEXT("CommonUI"))),
			TEXT("CommonUI module is not loaded")) ||
		!RequireHarness(FModuleManager::Get().IsModuleLoaded(FName(TEXT("CommonInput"))),
			TEXT("CommonInput module is not loaded")))
	{
		return;
	}

	UCommonUIFocusProbeScreen* Probe = CreateWidget<UCommonUIFocusProbeScreen>(
		Controller.Get(), UCommonUIFocusProbeScreen::StaticClass());
	if (!RequireHarness(Probe != nullptr, TEXT("could not create verifier focus sentinel")))
	{
		return;
	}
	Sentinel = Probe;
	Probe->AddToViewport(2000);
	Probe->ActivateWidget();
	SentinelPrimary = Probe->GetPrimaryButton();
	SentinelAlternate = Probe->GetAlternateButton();
	if (!RequireHarness(SentinelPrimary.IsValid() && SentinelAlternate.IsValid(),
		TEXT("verifier focus sentinel buttons were not rebuilt")))
	{
		return;
	}
	SentinelPrimary->SetUserFocus(Controller.Get());

	const double Now = World->GetTimeSeconds();
	SetCheckpointSchedule({
		Now + 0.20, Now + 0.40, Now + 0.60, Now + 0.80,
		Now + 1.00, Now + 1.20, Now + 1.40, Now + 1.60,
		Now + 1.80, Now + 2.00, Now + 2.20, Now + 2.40 });
}

void AFocusStackFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	UE_LOG(LogTemp, Display, TEXT("[focus-stack] checkpoint=%d world_time=%.3f"),
		CheckpointIndex, TimeSeconds);
	APlayerController* PC = Controller.Get();
	if (!RequireHarness(PC != nullptr, TEXT("PlayerController disappeared")))
	{
		return;
	}

	if (CheckpointIndex == 0)
	{
		if (!RequireHarness(SentinelPrimary.IsValid() && SentinelPrimary->HasUserFocus(PC),
			TEXT("verifier direct-focus sentinel readback failed")))
		{
			return;
		}
		SentinelAlternate->SetUserFocus(PC);
		return;
	}

	if (CheckpointIndex == 1)
	{
		if (!RequireHarness(SentinelAlternate.IsValid() && SentinelAlternate->HasUserFocus(PC),
			TEXT("verifier alternate-focus sentinel readback failed")))
		{
			return;
		}
		Sentinel->RequestRefreshFocus();
		return;
	}

	if (CheckpointIndex == 2)
	{
		if (!RequireHarness(SentinelPrimary.IsValid() && SentinelPrimary->HasUserFocus(PC),
			TEXT("verifier active-leaf focus refresh failed")))
		{
			return;
		}
		Sentinel->DeactivateWidget();
		Sentinel->RemoveFromParent();
		if (!ResolveProtectedActors())
		{
			return;
		}
		Policy->PreferredDetailAction = EMenuFocusChoice::Primary;
		FString Failure;
		if (!RequireGate(Host->CreateRoot(PC, Failure), TEXT("root_and_screens_are_activatable"), Failure) ||
			!RequireGate(Host->ActivateRoot(Failure), TEXT("root_activation_focuses_home"), Failure))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 3)
	{
		if (!RefreshGeneratedState(TEXT("root_activation_focuses_home"), TEXT("root activation")))
		{
			return;
		}
		InitialHome = Host->GetHome();
		HomePrimary = Host->GetHomePrimary();
		if (!RequireGate(Host->GetRoot()->IsActivated() && Host->GetRoot()->IsInViewport() &&
			Host->GetStack()->GetActiveWidget() == InitialHome.Get() && InitialHome->IsActivated(),
			TEXT("root_activation_focuses_home"), TEXT("Home is not the exact active stack top")) ||
			!RequireExactFocus(HomePrimary.Get(), {}, TEXT("root_activation_focuses_home"), TEXT("home-first")))
		{
			return;
		}
		FString Failure;
		if (!RequireGate(Host->InvokeRootCommand(OpenDetailsName, Failure),
			TEXT("push_makes_detail_the_only_active_top"), Failure))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 4)
	{
		if (!RefreshGeneratedState(TEXT("push_makes_detail_the_only_active_top"), TEXT("first details push")))
		{
			return;
		}
		FirstDetail = Host->GetActiveDetail();
		FirstDetailPrimary = Host->GetDetailPrimary();
		FirstDetailAlternate = Host->GetDetailAlternate();
		if (!RequireGate(FirstDetail.IsValid() && Host->GetStack()->GetActiveWidget() == FirstDetail.Get() &&
			FirstDetail->IsActivated() && FirstDetail->IsVisible() &&
			!InitialHome->IsActivated(),
			TEXT("push_makes_detail_the_only_active_top"),
			TEXT("Detail is not the sole active visible stack top")) ||
			!RequireExactFocus(FirstDetailPrimary.Get(),
				{ HomePrimary.Get(), FirstDetailAlternate.Get() },
				TEXT("top_detail_owns_declared_focus"), TEXT("detail-primary")))
		{
			return;
		}
		FString Failure;
		if (!RequireHarness(Host->AttemptBuriedScreenFocusForTest(Failure),
			FString::Printf(TEXT("verifier buried-focus stimulus failed: %s"), *Failure)))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 5)
	{
		if (!RequireExactFocus(FirstDetailPrimary.Get(),
			{ HomePrimary.Get(), FirstDetailAlternate.Get() },
			TEXT("buried_screen_cannot_reclaim_focus"), TEXT("buried-home-request")))
		{
			return;
		}
		FString Failure;
		if (!RequireGate(Host->InvokeRootCommand(DismissTopName, Failure),
			TEXT("dismiss_restores_home_focus"), Failure))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 6)
	{
		if (!RefreshGeneratedState(TEXT("dismiss_restores_home_focus"), TEXT("first dismiss")) ||
			!RequireGate(Host->GetStack()->GetActiveWidget() == InitialHome.Get() && InitialHome->IsActivated(),
				TEXT("dismiss_restores_home_focus"), TEXT("dismiss did not restore the same Home instance")) ||
			!RequireExactFocus(HomePrimary.Get(),
				{ FirstDetailPrimary.Get(), FirstDetailAlternate.Get() },
				TEXT("dismiss_restores_home_focus"), TEXT("home-after-first-dismiss")))
		{
			return;
		}
		Policy->PreferredDetailAction = EMenuFocusChoice::Alternate;
		FString Failure;
		if (!RequireGate(Host->InvokeRootCommand(OpenDetailsName, Failure),
			TEXT("world_policy_changes_reactivated_focus"), Failure))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 7)
	{
		if (!RefreshGeneratedState(TEXT("world_policy_changes_reactivated_focus"), TEXT("second details push")))
		{
			return;
		}
		SecondDetail = Host->GetActiveDetail();
		SecondDetailPrimary = Host->GetDetailPrimary();
		SecondDetailAlternate = Host->GetDetailAlternate();
		if (!RequireGate(SecondDetail.IsValid() && Host->GetStack()->GetActiveWidget() == SecondDetail.Get() &&
			SecondDetail->IsActivated() && !InitialHome->IsActivated(),
			TEXT("world_policy_changes_reactivated_focus"),
			TEXT("reactivated Detail is not the only active stack top")) ||
			!RequireExactFocus(SecondDetailAlternate.Get(),
				{ HomePrimary.Get(), SecondDetailPrimary.Get() },
				TEXT("world_policy_changes_reactivated_focus"), TEXT("detail-alternate")))
		{
			return;
		}
		FString Failure;
		if (!RequireGate(Host->InvokeRootCommand(DismissTopName, Failure),
			TEXT("dismiss_restores_home_focus"), Failure))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 8)
	{
		if (!RefreshGeneratedState(TEXT("dismiss_restores_home_focus"), TEXT("second dismiss")) ||
			!RequireGate(Host->GetStack()->GetActiveWidget() == InitialHome.Get() && InitialHome->IsActivated(),
				TEXT("dismiss_restores_home_focus"), TEXT("second dismiss did not restore the same Home instance")) ||
			!RequireExactFocus(HomePrimary.Get(),
				{ SecondDetailPrimary.Get(), SecondDetailAlternate.Get() },
				TEXT("dismiss_restores_home_focus"), TEXT("home-after-second-dismiss")))
		{
			return;
		}
		FString Failure;
		if (!RequireGate(Host->InvokeRootCommand(CloseMenuName, Failure),
			TEXT("root_deactivation_releases_focus"), Failure))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 9)
	{
		UCommonActivatableWidget* Root = Host->GetRoot();
		UCommonActivatableWidgetStack* Stack = Host->GetStack();
		const bool bAnyMenuFocus =
			(HomePrimary.IsValid() && HomePrimary->HasUserFocus(PC)) ||
			(FirstDetailPrimary.IsValid() && FirstDetailPrimary->HasUserFocus(PC)) ||
			(FirstDetailAlternate.IsValid() && FirstDetailAlternate->HasUserFocus(PC)) ||
			(SecondDetailPrimary.IsValid() && SecondDetailPrimary->HasUserFocus(PC)) ||
			(SecondDetailAlternate.IsValid() && SecondDetailAlternate->HasUserFocus(PC));
		if (!RequireGate(Root != nullptr && !Root->IsActivated() && !Root->IsInViewport() &&
			Stack != nullptr && (Stack->GetActiveWidget() == nullptr || !Stack->GetActiveWidget()->IsActivated()) &&
			!bAnyMenuFocus,
			TEXT("root_deactivation_releases_focus"),
			TEXT("close left the root, an active child, or a menu action focused")))
		{
			return;
		}
		return;
	}

	// Checkpoints 10 and 11 are deliberate world-clock sentinels. They make a
	// deferred focus restore after close observable and prevent base-class early
	// success from hiding work scheduled after the final graded action.
	if (CheckpointIndex == 10)
	{
		const bool bDeferredFocus =
			(HomePrimary.IsValid() && HomePrimary->HasUserFocus(PC)) ||
			(FirstDetailPrimary.IsValid() && FirstDetailPrimary->HasUserFocus(PC)) ||
			(FirstDetailAlternate.IsValid() && FirstDetailAlternate->HasUserFocus(PC)) ||
			(SecondDetailPrimary.IsValid() && SecondDetailPrimary->HasUserFocus(PC)) ||
			(SecondDetailAlternate.IsValid() && SecondDetailAlternate->HasUserFocus(PC));
		if (!RequireGate(!bDeferredFocus, TEXT("root_deactivation_releases_focus"),
			TEXT("a deferred focus restore occurred after close")))
		{
			return;
		}
		return;
	}

	if (CheckpointIndex == 11)
	{
		FinishTest(EFunctionalTestResult::Succeeded,
			TEXT("All activation-stack and focus-lifecycle gates passed through the final sentinel."));
	}
}
