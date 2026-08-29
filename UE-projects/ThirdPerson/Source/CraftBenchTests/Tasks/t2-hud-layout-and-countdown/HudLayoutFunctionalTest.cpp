// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHudLayoutFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns the viewport-widget enumeration, the
// named-widget tree search, the kind gates, and the start-value gate. All
// FAIL message text is ASCII-only (the cp1252 log read-back rule).
//
// Spike provenance (2026-07-30, this box, -nullrhi -deterministic -FPS=60):
// CreateWidget/AddToViewport/IsInViewport and WidgetTree text reads all work
// headless; widget Tick does NOT fire. That last fact is why the countdown
// DECREASE is advisory-only here — see the task notes.

#include "HudLayoutFunctionalTest.h"

#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Blueprint/WidgetTree.h"
#include "Components/ProgressBar.h"
#include "Components/TextBlock.h"
#include "Engine/World.h"

namespace
{
	static const FName HealthBarName(TEXT("HealthBar"));
	static const FName StaminaBarName(TEXT("StaminaBar"));
	static const FName ManaBarName(TEXT("ManaBar"));
	static const FName CountdownTextName(TEXT("CountdownText"));

	// The disclosed starting value of the countdown readout.
	constexpr int32 KCountdownStart = 60;

	// The four required names, bars first (they share the fill-bar kind gate).
	const FName* RequiredNames[] = {
		&HealthBarName, &StaminaBarName, &ManaBarName, &CountdownTextName,
	};
}

AHudLayoutFunctionalTest::AHudLayoutFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void AHudLayoutFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	if (GetWorld() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// cp0 at 0.7s: after BeginPlay-time widget creation (on screen by frame
	// ~2) but BEFORE any 1-second countdown timer's first fire — checkpoints
	// and world timers share world game-time, so a later cp0 would read the
	// already-decremented value and punish exactly the timer-driven
	// implementations the descope protects (adversarial-review BLOCKER,
	// 2026-07-30). cp1 at 4.6s: persistence gate + the advisory re-read.
	SetCheckpointSchedule({ 0.7, 4.6 });
}

void AHudLayoutFunctionalTest::CollectNamedWidgets(UUserWidget* Root, TMap<FName, UWidget*>& Out)
{
	if (Root == nullptr || Root->WidgetTree == nullptr)
	{
		return;
	}
	TArray<UUserWidget*> Nested;
	Root->WidgetTree->ForEachWidget([&Out, &Nested](UWidget* Widget)
	{
		if (Widget == nullptr)
		{
			return;
		}
		if (!Out.Contains(Widget->GetFName()))
		{
			Out.Add(Widget->GetFName(), Widget);
		}
		if (UUserWidget* Nest = Cast<UUserWidget>(Widget))
		{
			Nested.Add(Nest);
		}
	});
	for (UUserWidget* Nest : Nested)
	{
		CollectNamedWidgets(Nest, Out);
	}
}

FString AHudLayoutFunctionalTest::ReadCountdownText() const
{
	const UTextBlock* Text = Cast<UTextBlock>(Countdown.Get());
	return Text ? Text->GetText().ToString().TrimStartAndEnd() : FString();
}

void AHudLayoutFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: OnCheckpoint: no UWorld available"));
		return;
	}

	if (CheckpointIndex == 0)
	{
		// Every live user widget, filtered to the ones actually ON SCREEN.
		// TopLevelOnly=false so a HUD wrapped in another user widget is still
		// seen; IsInViewport is what "reached the screen" means.
		TArray<UUserWidget*> AllWidgets;
		UWidgetBlueprintLibrary::GetAllWidgetsOfClass(
			World, AllWidgets, UUserWidget::StaticClass(), /*TopLevelOnly*/ false);
		TArray<UUserWidget*> OnScreen;
		for (UUserWidget* Widget : AllWidgets)
		{
			if (Widget && Widget->IsInViewport())
			{
				OnScreen.Add(Widget);
			}
		}
		UE_LOG(LogTemp, Display, TEXT("[t2-hud calib] cp0 t=%.2f live=%d onscreen=%d"),
			TimeSeconds, AllWidgets.Num(), OnScreen.Num());
		if (OnScreen.Num() == 0)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				TEXT("Expected the HUD unaided at play start; observed no HUD widget reached the screen at play start."));
			return;
		}

		// The qualifying HUD: the first on-screen widget whose tree carries all
		// four required names. Track the best miss so the named FAIL points at
		// the closest candidate's first missing widget.
		TMap<FName, UWidget*> Named;
		const FName* FirstMissing = nullptr;
		int32 BestFound = -1;
		for (UUserWidget* Candidate : OnScreen)
		{
			TMap<FName, UWidget*> CandidateNamed;
			CollectNamedWidgets(Candidate, CandidateNamed);
			int32 FoundCount = 0;
			const FName* Missing = nullptr;
			for (const FName* Required : RequiredNames)
			{
				if (CandidateNamed.Contains(*Required))
				{
					++FoundCount;
				}
				else if (Missing == nullptr)
				{
					Missing = Required;
				}
			}
			if (FoundCount == static_cast<int32>(UE_ARRAY_COUNT(RequiredNames)))
			{
				Hud = Candidate;
				Named = MoveTemp(CandidateNamed);
				break;
			}
			if (FoundCount > BestFound)
			{
				BestFound = FoundCount;
				FirstMissing = Missing;
			}
		}
		if (!Hud.IsValid())
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The HUD is missing a widget named '%s' (no on-screen widget carries all four required names)."),
					FirstMissing ? *FirstMissing->ToString() : TEXT("HealthBar")));
			return;
		}

		// Kind gates: the three bars must be fill-bar widgets; the countdown a
		// text widget. Names alone are not the contract.
		for (const FName* BarName : { &HealthBarName, &StaminaBarName, &ManaBarName })
		{
			if (Cast<UProgressBar>(Named.FindRef(*BarName)) == nullptr)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("Expected a fill-bar widget; observed %s is not a fill-bar widget."),
						*BarName->ToString()));
				return;
			}
		}
		Countdown = Named.FindRef(CountdownTextName);
		if (Cast<UTextBlock>(Countdown.Get()) == nullptr)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				TEXT("Expected a text readout; observed CountdownText is not a text widget."));
			return;
		}

		// Start-value gate: the disclosed contract is the whole number 60 the
		// moment the HUD appears.
		CountdownAtCp0 = ReadCountdownText();
		if (CountdownAtCp0 != FString::FromInt(KCountdownStart))
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the readout to show %d when the HUD appears; observed the countdown does not start at 60 (reads '%s')."),
					KCountdownStart, *CountdownAtCp0));
			return;
		}
		UE_LOG(LogTemp, Display, TEXT("[t2-hud calib] cp0 hud=%s countdown='%s'"),
			*GetNameSafe(Hud.Get()), *CountdownAtCp0);
	}
	else
	{
		// Persistence gate (GRADED, mechanism-free): the HUD that satisfied
		// cp0 must still be alive and on screen — appearing for one sample and
		// vanishing is not "a HUD". This never touches the countdown descope.
		if (!Hud.IsValid() || !Hud->IsInViewport())
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				TEXT("Expected the HUD to stay on screen; observed the HUD disappeared after appearing."));
			return;
		}

		// ADVISORY ONLY — never gates. Whether the countdown advanced between
		// cp0 (0.7s) and here (4.6s) is logged for human review; the graded
		// contract ends at the start value. See the task notes for why.
		// Non-numeric text is its own advisory word (Atoi("garbage") is 0 and
		// would masquerade as "decreasing").
		const FString Now = ReadCountdownText();
		const TCHAR* Verdict = TEXT("static");
		if (Now.IsEmpty() || !Now.IsNumeric())
		{
			Verdict = TEXT("unreadable");
		}
		else if (FCString::Atoi(*Now) < FCString::Atoi(*CountdownAtCp0))
		{
			Verdict = TEXT("decreasing");
		}
		UE_LOG(LogTemp, Display,
			TEXT("[t2-hud advisory] countdown cp0='%s' cp1='%s' -> %s (non-gating)"),
			*CountdownAtCp0, *Now, Verdict);
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
	}
}
