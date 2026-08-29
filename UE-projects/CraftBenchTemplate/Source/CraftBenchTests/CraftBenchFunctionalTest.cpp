// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ACraftBenchFunctionalTest implementation. See the header + the pattern guide
// (docs/pie-verification-playbook.md) for the PIE model.

#include "CraftBenchFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "GameFramework/GameModeBase.h"
#include "HAL/IConsoleManager.h"
#include "Misc/Paths.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "RHI.h"           // GUsingNullRHI
#include "UObject/UnrealType.h"
#include "UnrealClient.h"  // FScreenshotRequest

ACraftBenchFunctionalTest::ACraftBenchFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

void ACraftBenchFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	SnapshotGlobals();
	// Belt-and-suspenders: ensure fixed-step ticking is on (the runner also
	// passes -deterministic -FPS=<rate>, which OWNS the per-frame dt). We do
	// NOT set FApp::FixedDeltaTime here so the runner's -FPS controls the rate
	// (e.g. -FPS=20 for the Timer 20Hz framerate-independence leg). Restored
	// in EndPlay.
	FApp::SetUseFixedTimeStep(true);
	// Advisory-capture switch (opt-in): resolved once per test. Only the runner's
	// -CraftBenchCapture editor switch enables it, and only with a real RHI — a
	// -nullrhi run has nothing to render, so the default headless path stays a
	// no-op (byte-equivalent in behavior).
	bCaptureEnabled = FParse::Param(FCommandLine::Get(), TEXT("CraftBenchCapture")) && !GUsingNullRHI;
	if (bCaptureEnabled)
	{
		SuppressMotionBlurForCapture();
	}
	// Advisory, every run: say so if a human could not drive this level.
	ReportBrokenPlayerInput();
}

void ACraftBenchFunctionalTest::StartTest()
{
	// Super::StartTest() zeroes AFunctionalTest::TotalTime (the checkpoint clock).
	Super::StartTest();
	NextCheckpointIndex = 0;
	bStarted = true;

	// STALE-INSTANCE GUARD — see the bInstanceHasRun declaration for the full
	// account. A re-run on this instance means a reused world: the schedule is
	// entirely in the past and the members above still hold the previous run's
	// values, which is the exact recipe for a meaningless green Success. FAIL
	// loudly with the operator fix instead. (After Super::StartTest() on
	// purpose: FinishTest requires a running test.)
	if (bInstanceHasRun)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"STALE WORLD: this fixture instance already ran in this world - the "
			"editor re-ran the test inside an alive PIE session, so every "
			"checkpoint would fire instantly against the previous run's state. "
			"Stop the running PIE session (Esc) and re-run; a fresh PIE world "
			"runs the schedule for real."));
		return;
	}
	bInstanceHasRun = true;
}

void ACraftBenchFunctionalTest::Tick(float DeltaSeconds)
{
	// CRITICAL: Super first — it does TotalTime += DeltaSeconds and runs the
	// IsReady()->StartTest() / timeout machinery. We never call World->Tick.
	Super::Tick(DeltaSeconds);

	if (!bStarted || !IsRunning())
	{
		return;
	}

	// Checkpoints are measured against WORLD game-time (GetTimeSeconds, seconds
	// since the PIE world began play), NOT TotalTime (since StartTest). The
	// agent's behavior — BeginPlay timers, gravity, spawns — is anchored at
	// world-start, so the world clock is what keeps the fixture aligned with it.
	// (TotalTime would be offset by the IsReady->StartTest warmup, breaking
	// tight tolerances like the Timer task's +/-0.05s window.)
	const UWorld* World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : static_cast<double>(TotalTime);

	// Fire every checkpoint crossed this frame (robust to a tick spanning more than one).
	while (NextCheckpointIndex < Checkpoints.Num()
		&& Now >= Checkpoints[NextCheckpointIndex])
	{
		const int32 Idx = NextCheckpointIndex++;
		// Advisory screenshot BEFORE the checkpoint's assertions: the shot shows
		// the world state the assertions are about to judge, and it still fires
		// when OnCheckpoint FinishTest()s (a fixture that finishes inside its
		// last checkpoint — e.g. the single-checkpoint Sanity test — would
		// otherwise never capture). Fire-and-forget; no-op by default.
		MaybeCaptureCheckpoint(Idx);
		// Generic per-checkpoint breadcrumb: the run-summary card parses
		// "[CB-CP] idx=<n> t=<s>" out of the graded L2 log (preferring it over
		// per-fixture "idx=" lines) — every fixture gets checkpoint times for
		// free, incl. programmatic schedules a static source parse cannot know.
		// Advisory-only: a log line can never affect the verdict.
		UE_LOG(LogTemp, Display, TEXT("[CB-CP] idx=%d t=%.2f"), Idx, Checkpoints[Idx]);
		OnCheckpoint(Idx, Checkpoints[Idx]);
		if (!IsRunning())
		{
			return;  // OnCheckpoint finished the test early (a failed assertion).
		}
	}

	if (Checkpoints.Num() > 0 && NextCheckpointIndex >= Checkpoints.Num())
	{
		FinishTest(EFunctionalTestResult::Succeeded, TEXT("All checkpoints sampled."));
	}
}

void ACraftBenchFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	RestoreMotionBlur();
	RestoreGlobals();
	Super::EndPlay(EndPlayReason);
}

void ACraftBenchFunctionalTest::SuppressMotionBlurForCapture()
{
	// Measured 2026-08-17 on the plate-door task: all seven checkpoint stills came
	// out illegible -- door panel, the "0 deg"/"90 deg" readouts and the floor
	// stripes all smeared into diagonal streaks -- while the run itself was a clean
	// Result={Success}. The files were 745 KB-1.2 MB and all seven md5s DIFFERED,
	// so every cheap file-level sanity check passed; only opening the images showed
	// it. Cause is the shot teleporting the camera, which reads as a huge camera
	// velocity for exactly the frame the capture grabs. Turning this off fixed it
	if (IConsoleVariable* const MotionBlur =
			IConsoleManager::Get().FindConsoleVariable(TEXT("r.MotionBlurQuality")))
	{
		if (PriorMotionBlurQuality < 0)
		{
			PriorMotionBlurQuality = FMath::Max(0, MotionBlur->GetInt());
			MotionBlur->Set(0, ECVF_SetByCode);
		}
	}
}

void ACraftBenchFunctionalTest::RestoreMotionBlur()
{
	if (PriorMotionBlurQuality < 0)
	{
		return;  // never suppressed (the ordinary graded path)
	}
	if (IConsoleVariable* const MotionBlur =
			IConsoleManager::Get().FindConsoleVariable(TEXT("r.MotionBlurQuality")))
	{
		MotionBlur->Set(PriorMotionBlurQuality, ECVF_SetByCode);
	}
	PriorMotionBlurQuality = -1;
}

void ACraftBenchFunctionalTest::ReportBrokenPlayerInput() const
{
	UWorld* const World = GetWorld();
	const AGameModeBase* const GameMode = World ? World->GetAuthGameMode() : nullptr;
	const UClass* const PawnClass =
		GameMode != nullptr ? GameMode->DefaultPawnClass.Get() : nullptr;
	if (PawnClass == nullptr)
	{
		return;
	}

	// IDENTITY BY PROPERTY, NEVER BY CLASS. This file is shipped verbatim in both
	// substrates, so it cannot name either one's character types. A pawn that HAS
	// a MoveAction property is a template-style playable pawn, and then all four
	// actions must be set; a pawn without that property belongs to a substrate
	// that does not use the pattern, and this stays completely silent there.
	static const TCHAR* const kActionNames[] = {
		TEXT("MoveAction"), TEXT("LookAction"),
		TEXT("MouseLookAction"), TEXT("JumpAction")};
	if (FindFProperty<FObjectProperty>(PawnClass, kActionNames[0]) == nullptr)
	{
		// NO input properties at all. On a substrate that ships no input assets this
		// is simply how its pawns are, and saying anything would be noise on every
		// task. On a substrate that DOES ship them it is the loudest possible version
		// of the same defect: the pawn cannot be driven by any key at all.
		//
		// Found 2026-08-18: t1-spikes-hurt-you-and-you-respawn-at-your-marker derives
		// its character from ACraftBenchCharacter, which extends ACharacter directly
		// and has no SetupPlayerInputComponent anywhere -- and this check said nothing,
		// because it keyed on the pawn HAVING a MoveAction property. The substrate is
		// the discriminator, not the pawn.
		if (IFileManager::Get().FileSize(
				*(FPaths::ProjectContentDir() / TEXT("Input/Actions/IA_Move.uasset"))) > 0)
		{
			UE_LOG(LogTemp, Display,
				TEXT("[CB-PLAYLANE] this level cannot be played by hand — the pawn (%s) "
					 "declares no input actions at all, on a project that ships "
					 "Content/Input/Actions. Grading is unaffected; a human would get "
					 "a character that cannot move."),
				*PawnClass->GetName());
		}
		return;
	}

	TArray<FString> Problems;
	const UObject* const PawnCDO = PawnClass->GetDefaultObject();
	TArray<FString> Unbound;
	for (const TCHAR* const Name : kActionNames)
	{
		const FObjectProperty* const Prop =
			FindFProperty<FObjectProperty>(PawnClass, Name);
		if (Prop == nullptr || PawnCDO == nullptr
			|| Prop->GetObjectPropertyValue_InContainer(PawnCDO) == nullptr)
		{
			Unbound.Add(Name);
		}
	}
	if (Unbound.Num() > 0)
	{
		Problems.Add(FString::Printf(TEXT("the pawn (%s) has nothing bound to %s"),
			*PawnClass->GetName(), *FString::Join(Unbound, TEXT(", "))));
	}

	// The mapping context: without one, no key reaches any of those actions even
	// when all four are set.
	const UClass* const PCClass = GameMode->PlayerControllerClass.Get();
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the "
						  "player gets a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts =
				 FindFProperty<FArrayProperty>(PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
		FScriptArrayHelper Helper(Contexts, Contexts->ContainerPtrToValuePtr<void>(
											   PCClass->GetDefaultObject()));
		int32 Applied = 0;
		for (int32 Index = 0; Element != nullptr && Index < Helper.Num(); ++Index)
		{
			if (Element->GetObjectPropertyValue(Helper.GetElementPtr(Index)) != nullptr)
			{
				++Applied;
			}
		}
		if (Applied == 0)
		{
			Problems.Add(FString::Printf(
				TEXT("%s applies no input mapping context"), *PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s carries no DefaultMappingContexts, so nothing here can "
				 "confirm a key is mapped"), *PCClass->GetName()));
	}

	if (Problems.Num() == 0)
	{
		return;  // drivable: stay quiet rather than adding a line to 60+ logs
	}
	// ADVISORY ONLY — never FinishTest. Naming a task game mode replaces
	// GlobalDefaultGameMode, and both halves of Enhanced Input live on the
	// Blueprints it would have supplied, so a level can grade BYTE-IDENTICALLY to
	// a healthy one while being impossible to walk around. No fixture notices,
	// because they all drive the pawn through AddMovementInput. Four established
	// maps were already in this state when this was added (see
	// the 2026-08-17 unplayable-play-lane finding), so failing here
	// would turn passing tasks red for something no agent authored.
	UE_LOG(LogTemp, Display,
		TEXT("[CB-PLAYLANE] this level cannot be played by hand — %s. Grading is "
			 "unaffected; a human reviewer would see a standing, animated, "
			 "uncontrollable character."),
		*FString::Join(Problems, TEXT("; ")));
}

void ACraftBenchFunctionalTest::SetCheckpointSchedule(const TArray<double>& InCheckpoints)
{
	Checkpoints = InCheckpoints;
	Checkpoints.Sort();
	NextCheckpointIndex = 0;
	if (Checkpoints.Num() > 0)
	{
		// A stuck test FAILS at the deadline rather than hanging the editor.
		TimeLimit = static_cast<float>(Checkpoints.Last()) + TimeLimitMargin;
		TimesUpResult = EFunctionalTestResult::Failed;
	}
}

void ACraftBenchFunctionalTest::MaybeCaptureCheckpoint(int32 CheckpointIndex)
{
	if (!bCaptureEnabled)
	{
		return;
	}
	// Stock-UE PIE viewport screenshot (mirrors ARenderProbeFunctionalTest).
	// Async — it fulfils on a later rendered frame, so the last checkpoint's
	// shot may miss shutdown: acceptable, these are advisory-only artifacts.
	// NO assertions, NO file-existence checks — this can never flip a verdict.
	const FString Filename = FPaths::ProjectSavedDir() / TEXT("CraftBench")
		/ FString::Printf(TEXT("%s_cp%02d.png"), *GetName(), CheckpointIndex);
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), /*Tree=*/true);
	FScreenshotRequest::RequestScreenshot(Filename, /*bShowUI=*/false, /*bAddFilenameSuffix=*/false);
}





void ACraftBenchFunctionalTest::SnapshotGlobals()
{
	if (bSnapshotTaken)
	{
		return;
	}
	bPriorUseFixedTimeStep = FApp::UseFixedTimeStep();
	PriorFixedDeltaTime = FApp::GetFixedDeltaTime();
	bSnapshotTaken = true;
}

void ACraftBenchFunctionalTest::RestoreGlobals()
{
	if (!bSnapshotTaken)
	{
		return;
	}
	FApp::SetUseFixedTimeStep(bPriorUseFixedTimeStep);
	FApp::SetFixedDeltaTime(PriorFixedDeltaTime);
	bSnapshotTaken = false;
}
