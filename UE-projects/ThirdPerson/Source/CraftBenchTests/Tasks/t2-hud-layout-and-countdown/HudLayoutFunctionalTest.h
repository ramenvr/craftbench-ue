// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHudLayoutFunctionalTest — L2 verifier fixture for task
// t2-hud-layout-and-countdown. Lives at Source/CraftBenchTests/Tasks/
// t2-hud-layout-and-countdown/. Placed in Content/Maps/
// t2-hud-layout-and-countdown/L_HudLayout.umap; the map's world settings
// select AHudGameMode (empty scaffold — the agent wires the HUD creation).
//
// PIE-native, PASSIVE OBSERVER: the fixture drives nothing. At cp0 it
// enumerates the LIVE user widgets actually on screen (IsInViewport), finds
// the one whose widget tree carries all four named widgets (the search
// recurses into nested user widgets, so composition cannot hide a name), and
// gates on presence, widget KIND (fill-bar vs text), and the countdown's
// starting value. At cp1 it re-reads the countdown text as an ADVISORY line
// only — whether the value decreased is logged, never graded (see the task
// notes for the descope rationale; it is deliberate, not an oversight).
//
// Checkpoint contract (seconds of world game-time, fixed-step):
//   t=0.7 — the HUD must already be on screen unaided: one viewport user
//           widget contains ALL of HealthBar/StaminaBar/ManaBar (fill-bar
//           widgets) + CountdownText (a text widget reading exactly 60).
//           0.7 sits AFTER BeginPlay creation (~frame 2) and BEFORE any
//           1-second countdown timer's first fire — checkpoints and world
//           timers share world game-time, so sampling later would read an
//           already-decremented value and fail timer-driven countdowns.
//   t=4.6 — persistence gate (the SAME widget still valid + in viewport;
//           "the HUD disappeared after appearing") + the advisory countdown
//           re-read (logged decreasing|static|unreadable, non-gating)
//           -> Succeeded
// Every checkpoint logs an ASCII "[t2-hud calib]" line for calibration.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "HudLayoutFunctionalTest.generated.h"

class UUserWidget;
class UWidget;

UCLASS()
class CRAFTBENCHTESTS_API AHudLayoutFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AHudLayoutFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Recursively collects every named widget in a user widget's tree,
	 *  descending into nested user widgets (composition must not hide a
	 *  required name). First name wins on duplicates. */
	static void CollectNamedWidgets(UUserWidget* Root, TMap<FName, UWidget*>& Out);

	/** The trimmed text of the CountdownText widget, or empty when the widget
	 *  is gone/not text. */
	FString ReadCountdownText() const;

	/** The HUD widget that satisfied cp0, kept for the advisory re-read. */
	TWeakObjectPtr<UUserWidget> Hud;
	/** The countdown widget inside it. */
	TWeakObjectPtr<UWidget> Countdown;
	/** cp0's countdown reading, for the advisory delta line. */
	FString CountdownAtCp0;
};
