// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ACraftBenchFunctionalTest — abstract base for every CraftBench L2 fixture.
//
// Runs fixtures in a real PIE world (not Editor World). The engine ticks the
// AFunctionalTest actor every frame; fixtures observe state at a schedule of
// checkpoints and never call World->Tick / Actor->Tick (which is re-entrant
// inside PIE and trips FTickTaskSequencer::StartFrame — TickTaskManager.cpp).
// See docs/pie-verification-playbook.md (the PIE fixture-pattern recipes).
//
// This base owns:
//   (a) the PIE lever — IsEditorOnlyLoadedInPIE() override (routes map-based
//       tests into a real PIE world; BeginPlay auto-fires; FTimerManager ticks);
//   (b) fixed-timestep determinism — FApp::SetUseFixedTimeStep/FixedDeltaTime,
//       snapshotted in PrepareTest and restored in EndPlay (no leak across the
//       multi-test editor session);
//   (c) a checkpoint clock — Tick reads the world game-time (GetTimeSeconds,
//       seconds since the PIE world began play — the clock the agent's BeginPlay
//       timers / gravity use) and invokes OnCheckpoint() as each scheduled time
//       is crossed, then FinishTest()s. SetCheckpointSchedule() also sets a
//       TimeLimit so a stuck test FAILS instead of hanging.
//   (d) opt-in advisory capture — when the editor was launched with
//       -CraftBenchCapture AND a real RHI is up, each crossed checkpoint
//       fire-and-forgets a PIE screenshot into Saved/CraftBench/. Assert-free,
//       advisory-only; the default (headless -nullrhi, no switch) path is a
//       no-op and behaves byte-identically to before.
//
// A per-fixture author writes only: tagged-actor resolution in PrepareTest, a
// SetCheckpointSchedule() call, and an OnCheckpoint() body that samples state.

#pragma once

#include "CoreMinimal.h"
#include "FunctionalTest.h"
#include "CraftBenchFunctionalTest.generated.h"


UCLASS(Abstract)
class CRAFTBENCHTESTS_API ACraftBenchFunctionalTest : public AFunctionalTest
{
	GENERATED_BODY()

public:
	ACraftBenchFunctionalTest(const FObjectInitializer& ObjectInitializer);

	/** Snapshots editor globals AFTER AFunctionalTest::PrepareTest, then sets
	 *  fixed timestep for the run. Subclasses call Super::PrepareTest() first,
	 *  then resolve their tagged actor + SetCheckpointSchedule(). */
	virtual void PrepareTest() override;

	/** Resets the checkpoint cursor; chains Super (zeroes TotalTime). */
	virtual void StartTest() override;

	/** Reads TotalTime and fires OnCheckpoint() per crossed checkpoint, then
	 *  finishes. Never advances the world — the PIE engine ticks this actor. */
	virtual void Tick(float DeltaSeconds) override;

	/** Restores editor globals BEFORE chaining Super::EndPlay. */
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	/** The lever that routes map-based tests into a real PIE world
	 *  (ClientFuncTestPerforming.cpp:233 predicate). Base default = true so no
	 *  fixture can forget it. */
	virtual bool IsEditorOnlyLoadedInPIE() const override { return true; }

	/** Author sets the ascending checkpoint schedule, in seconds of WORLD
	 *  game-time (GetTimeSeconds, since the PIE world began play) — NOT since
	 *  StartTest. That is the clock the agent's BeginPlay timers/gravity/spawns
	 *  are anchored to; see the Tick implementation for why TotalTime would be
	 *  offset by the IsReady->StartTest warmup and break tight tolerances.
	 *  Also sets TimeLimit = last + margin so a hung test FAILS, not hangs. */
	void SetCheckpointSchedule(const TArray<double>& InCheckpoints);

	/** Per-crossed-checkpoint hook (TimeSeconds = world game-time at the crossing).
	 *  Sample state here; call FinishTest(Failed) to fail early, or do nothing to
	 *  pass. Default no-op. */
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) {}

	/** Seconds added past the last checkpoint for the failure TimeLimit. */
	float TimeLimitMargin = 2.0f;

private:
	bool bSnapshotTaken = false;
	bool bPriorUseFixedTimeStep = false;
	double PriorFixedDeltaTime = 0.0;

	TArray<double> Checkpoints;
	int32 NextCheckpointIndex = 0;
	bool bStarted = false;

	/** STALE-INSTANCE GUARD (2026-08-04). True once StartTest has run on THIS
	 *  actor instance. A second StartTest on the same instance means the test
	 *  is being re-run inside a REUSED world (an alive PIE session under the
	 *  editor's Automation tab) — the world clock is far past the schedule, so
	 *  every checkpoint fires in one frame against the un-reset members of the
	 *  previous run, and the stale flags + zero-velocity samples can satisfy
	 *  every gate: a green Success that means nothing. Reproduced live
	 *  2026-08-04 (user session; all five glide gates fooled). StartTest
	 *  hard-FAILs on reuse instead.
	 *
	 *  Deliberately an INSTANCE flag, not a clock check: schedules are world-
	 *  time-anchored on purpose (see SetCheckpointSchedule) and legitimately
	 *  start "late" — t0-sanity's whole schedule ({0.1}) sits before the
	 *  ~0.3 s IsReady warmup, so ANY at-start time guard would false-fail a
	 *  passing reference. The certified headless lane runs a fresh world and
	 *  fresh instance per test and can never trip this. */
	bool bInstanceHasRun = false;

	/** True only when the editor was launched with -CraftBenchCapture AND a real
	 *  RHI is up (resolved once in PrepareTest). Default false — the headless
	 *  -nullrhi path never captures. */
	bool bCaptureEnabled = false;

	void SnapshotGlobals();
	void RestoreGlobals();

	/** Turns motion blur off for a CAPTURE run only, restoring it in EndPlay.
	 *  A checkpoint screenshot is grabbed on one frame with no regard for what
	 *  moved into it; motion blur smears that frame for no benefit to a reviewer.
	 *  No-op unless bCaptureEnabled, which already requires a real RHI — a graded
	 *  -nullrhi run never reaches it and cannot be affected. */
	void SuppressMotionBlurForCapture();
	void RestoreMotionBlur();
	/** -1 = nothing to restore. */
	int32 PriorMotionBlurQuality = -1;

	/** ADVISORY: logs one greppable line when this level cannot be driven by
	 *  hand. Never fails a test — the input lane is substrate we ship, and four
	 *  established maps were already in that state when this was added, so a hard
	 *  gate here would turn passing tasks red for something no agent authored.
	 *  Reads by PROPERTY NAME, so this one file works verbatim on both substrates
	 *  without naming either one's character classes, and stays SILENT on a
	 *  substrate whose pawns do not use the template's input pattern at all. */
	void ReportBrokenPlayerInput() const;

	/** Fire-and-forget advisory screenshot for a crossed checkpoint. Assert-free
	 *  by design: the request fulfils async on a later rendered frame and is
	 *  never checked (the last checkpoint's shot may miss shutdown — acceptable,
	 *  advisory-only). No-op unless bCaptureEnabled; can never flip PASS/FAIL. */
	void MaybeCaptureCheckpoint(int32 CheckpointIndex);

};
