// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ACraftBenchFunctionalTest implementation. See the header + the pattern guide
// (docs/pie-verification-playbook.md) for the PIE model.

#include "CraftBenchFunctionalTest.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Engine/Blueprint.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
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

// ---- the SURFACE lane -----------------------------------------------------
// See the header for why a placed-prop task needs this at all.

UClass* ACraftBenchFunctionalTest::ResolveGradedBlueprintClass(UClass* PlacedClass)
{
	if (PlacedClass == nullptr)
	{
		return nullptr;
	}
	IAssetRegistry* const Registry = IAssetRegistry::Get();
	if (Registry == nullptr)
	{
		return nullptr;
	}
	// Blueprint-generated classes are not loaded until something references them,
	// and nothing in the map references a class the agent invented -- so the asset
	// REGISTRY is the only way to find one.
	FARFilter Filter;
	Filter.ClassPaths.Add(UBlueprint::StaticClass()->GetClassPathName());
	Filter.PackagePaths.Add(FName(TEXT("/Game/Tasks")));
	Filter.bRecursivePaths = true;
	TArray<FAssetData> Found;
	Registry->GetAssets(Filter, Found);

	UClass* Chosen = nullptr;
	for (const FAssetData& Asset : Found)
	{
		// GetAsset() is what LOADS it; a registry hit alone carries no
		// GeneratedClass. Same call ACraftBenchPawnFunctionalTest relies on, so no
		// new module dependency (EditorScriptingUtilities is not one of ours).
		const UBlueprint* const Blueprint = Cast<UBlueprint>(Asset.GetAsset());
		if (Blueprint == nullptr)
		{
			continue;
		}
		UClass* const Generated = Blueprint->GeneratedClass;
		if (Generated == nullptr || Generated == PlacedClass
			|| Generated->HasAnyClassFlags(CLASS_Abstract)
			|| !Generated->IsChildOf(PlacedClass))
		{
			continue;
		}
		if (Chosen != nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: two or more Blueprints under /Game/Tasks "
					 "derive from %s, so which one is the answer is ambiguous"),
				*PlacedClass->GetName()));
			return nullptr;
		}
		Chosen = Generated;
	}
	return Chosen;
}

AActor* ACraftBenchFunctionalTest::SwapForGradedBlueprint(AActor* Placed)
{
	UWorld* const World = GetWorld();
	if (World == nullptr || Placed == nullptr)
	{
		return nullptr;
	}
	UClass* const Chosen = ResolveGradedBlueprintClass(Placed->GetClass());
	if (Chosen == nullptr)
	{
		return nullptr;   // the C++ lane
	}
	AActor* const Spawned = SpawnStandInFor(Placed, Chosen);
	if (Spawned == nullptr)
	{
		return nullptr;
	}
	RepointReferencesTo(Placed, Spawned);
	FinishStandIn(Spawned);
	Placed->Destroy();
	return Spawned;
}

AActor* ACraftBenchFunctionalTest::SpawnStandInFor(AActor* Placed, UClass* Chosen)
{
	// DEFERRED, and that is the whole trick. A stand-in spawned normally runs its
	// BeginPlay immediately -- before its per-instance values have been carried over
	// and before anything pointing AT the placed actor has been re-pointed. A
	// barrier's BeginPlay builds its pad and lamp lists by scanning the world for
	// "AnsweredBarrier == this", so a stand-in constructed too early comes up with
	// EMPTY lists and a CORRECT submission grades FAIL. Deferring lets the caller
	// finish the wiring first and only then let the actor begin.
	UWorld* const World = GetWorld();
	if (World == nullptr || Placed == nullptr || Chosen == nullptr)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.bDeferConstruction = true;
	AActor* const Spawned = World->SpawnActor<AActor>(
		Chosen, Placed->GetActorTransform(), Params);
	if (Spawned == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: a Blueprint answer was found but would not "
				 "spawn, so this run can say nothing about the submission"));
		return nullptr;
	}
	// CARRY THE INSTANCE'S OWN STATE. The stand-in is otherwise born from CLASS
	// DEFAULTS, which loses every value the map author set on this particular
	// actor -- the names a gate is cut for, a round's remaining time, a lamp's
	// slot. Measured consequence of not doing this: a fixture that reads a
	// world-time-anchored value off the swapped actor compares its class default
	// against the live expectation on the swap frame and fails a correct answer.
	// This is the same call the engine itself uses to move instance state onto a
	// recompiled Blueprint class, so it handles the reflection cases we would get
	// wrong by hand.
	UEngine::FCopyPropertiesForUnrelatedObjectsParams CopyParams;
	// bPreserveRootComponent STAYS TRUE (its default), and that is load-bearing: the
	// stand-in's own components are what the behaviour runs on -- the tint actor's
	// root IS its post-process component -- and letting the copy replace them with
	// the placed actor's leaves the stand-in wired to components that are about to
	// be destroyed. Measured 2026-08-20: setting it false took a -bp leg that
	// discriminated straight back to a graded FAIL of a correct answer. Only the
	// per-instance VALUES are wanted here, never the component objects.
	CopyParams.bNotifyObjectReplacement = true;

	// UNREGISTER BEFORE THE COPY, RE-REGISTER AFTER. Not optional and not tidiness:
	// CopyPropertiesForUnrelatedObjects opens with
	//     // Bad idea to write data to an actor while its components are registered
	//     for (UActorComponent* Component : NewActor->GetComponents())
	//         ensure(Component == nullptr || !Component->IsRegistered());
	// (UnrealEngine.cpp:18641-18648), and a deferred-construction spawn still comes
	// back with its components registered, so the copy tripped that ensure on every
	// swap. A HANDLED ensure logs `LogOutputDevice: Error:`, and the automation
	// harness fails a test on a logged Error -- which is why the -bp leg failed L2
	// while its behaviour was demonstrably right: measured 2026-08-20, all twelve
	// checkpoints read `want == got` with both legs' full/still gates satisfied, and
	// the run still came back FAIL. The verdict was the ensure, not the answer.
	//
	// This is the engine's OWN ordering for replacing an actor in place
	// (`KismetReinstanceUtilities.cpp:2582-2606`): capture whether it had registered
	// components, unregister, copy, then register again only if it had been
	// registered. Copied rather than invented, comment included, so the reason
	// survives the next person who reads three lines of ceremony around one call.
	//
	// Deliberately NOT done: the engine also unregisters the OLD actor's components
	// before spawning the replacement, to avoid copying sub-components a native
	// component generates for itself. `Placed` is still live here and other actors
	// are still pointing at it until RepointReferencesTo runs, so pulling its
	// registration early is a behavioural change this ensure does not require.
	const bool bStandInHadRegisteredComponents =
		Spawned->HasActorRegisteredAllComponents();
	Spawned->UnregisterAllComponents();
	UEngine::CopyPropertiesForUnrelatedObjects(Placed, Spawned, CopyParams);
	if (bStandInHadRegisteredComponents)
	{
		Spawned->RegisterAllComponents();
	}

	// The tags ride on the PLACED instance, so the stand-in has to inherit them or
	// every tag lookup after this point finds nothing. Done after the copy, since
	// the copy may have brought its own.
	for (const FName& Tag : Placed->Tags)
	{
		Spawned->Tags.AddUnique(Tag);
	}
	return Spawned;
}

void ACraftBenchFunctionalTest::RepointReferencesTo(AActor* Placed, AActor* StandIn)
{
	UWorld* const World = GetWorld();
	if (World == nullptr || Placed == nullptr || StandIn == nullptr)
	{
		return;
	}
	// Anything in the world holding an AActor*/UObject* to the placed actor would
	// otherwise be left pointing at a destroyed object. These references are how a
	// yard is wired instance-to-instance (a pad naming the barrier it answers for,
	// a lamp naming the gate it is bolted to), and they are set per instance in the
	// map, so nothing in the class can reconstruct them.
	int32 Repointed = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* const Holder = *It;
		if (Holder == nullptr || Holder == Placed || Holder == StandIn)
		{
			continue;
		}
		for (TFieldIterator<FObjectPropertyBase> Prop(Holder->GetClass()); Prop; ++Prop)
		{
			if (Prop->GetObjectPropertyValue_InContainer(Holder) == Placed)
			{
				Prop->SetObjectPropertyValue_InContainer(Holder, StandIn);
				++Repointed;
			}
		}
	}
	UE_LOG(LogTemp, Display,
		TEXT("[CB-surface] re-pointed %d reference(s) from %s to its stand-in"),
		Repointed, *Placed->GetName());
}

void ACraftBenchFunctionalTest::FinishStandIn(AActor* StandIn)
{
	// Now, and only now, is the actor allowed to begin: its own values are carried
	// and everything that names it points at it.
	if (StandIn != nullptr)
	{
		StandIn->FinishSpawning(FTransform::Identity, /*bIsDefaultTransform=*/true);
	}
}

int32 ACraftBenchFunctionalTest::SwapAllForGradedBlueprint(TArray<AActor*>& InOut)
{
	UWorld* const World = GetWorld();
	if (World == nullptr || InOut.Num() == 0)
	{
		return 0;
	}
	// Resolve ONCE off the first entry: every element is an instance of the same
	// supplied class, and re-resolving per element would walk the asset registry N
	// times and could report the two-candidate precondition N times over.
	UClass* PlacedClass = nullptr;
	for (const AActor* const A : InOut)
	{
		if (A != nullptr)
		{
			PlacedClass = A->GetClass();
			break;
		}
	}
	UClass* const Chosen = ResolveGradedBlueprintClass(PlacedClass);
	if (Chosen == nullptr)
	{
		return 0;   // the C++ lane: the placed instances are the answer
	}
	int32 Swapped = 0;
	TArray<AActor*> Pending;   // built + wired, not yet begun
	for (int32 i = 0; i < InOut.Num(); ++i)
	{
		AActor* const Placed = InOut[i];
		if (Placed == nullptr)
		{
			continue;
		}
		// A mixed array would grade one surface for some instances and the other for
		// the rest, which is not a verdict about either.
		if (Placed->GetClass() != PlacedClass)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the actors handed to the surface swap are "
					 "not all one class (%s vs %s), so a swap would grade a mix"),
				*PlacedClass->GetName(), *Placed->GetClass()->GetName()));
			return Swapped;
		}
		AActor* const Spawned = SpawnStandInFor(Placed, Chosen);
		if (Spawned == nullptr)
		{
			return Swapped;   // SpawnStandInFor already raised the precondition
		}
		// EVERY stand-in is built and wired BEFORE ANY of them begins. Finishing
		// them one at a time would let the first one's BeginPlay scan a world where
		// the later placed actors are still the ones being pointed at, so it would
		// wire itself to actors about to be destroyed. Two passes, not one.
		RepointReferencesTo(Placed, Spawned);
		Placed->Destroy();
		InOut[i] = Spawned;
		Pending.Add(Spawned);
		++Swapped;
	}
	for (AActor* const StandIn : Pending)
	{
		FinishStandIn(StandIn);
	}
	return Swapped;
}

int32 ACraftBenchFunctionalTest::SwapAllForGradedBlueprintRepossessing(
	TArray<AActor*>& InOut)
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return 0;
	}
	APlayerController* const PC = UGameplayStatics::GetPlayerController(World, 0);
	APawn* const WasDriving = (PC != nullptr) ? PC->GetPawn() : nullptr;
	// Which INDEX was the driven one, recorded before the swap: after it, the
	// pointer is dangling and the array holds stand-ins.
	int32 DrivenIndex = INDEX_NONE;
	for (int32 i = 0; i < InOut.Num(); ++i)
	{
		if (InOut[i] != nullptr && InOut[i] == WasDriving)
		{
			DrivenIndex = i;
			break;
		}
	}

	const int32 Swapped = SwapAllForGradedBlueprint(InOut);
	if (Swapped == 0 || DrivenIndex == INDEX_NONE || PC == nullptr)
	{
		return Swapped;   // nothing swapped, or the driven pawn was not among them
	}
	APawn* const NowDriving = Cast<APawn>(InOut[DrivenIndex]);
	if (NowDriving == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the Blueprint stand-in for the driven pawn "
				 "is not a pawn, so player 0 cannot be re-possessed and no drive "
				 "input would reach anything"));
		return Swapped;
	}
	PC->Possess(NowDriving);
	if (PC->GetPawn() != NowDriving)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: re-possessing the Blueprint stand-in did not "
				 "take, so the drive would push a pawn nobody is controlling"));
	}
	return Swapped;
}
