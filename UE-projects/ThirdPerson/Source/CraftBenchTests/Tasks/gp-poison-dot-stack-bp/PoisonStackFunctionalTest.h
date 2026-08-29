// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// APoisonStackFunctionalTest — L2 fixture for task gp-poison-dot-stack-bp on the
// ThirdPerson substrate (ported verbatim 2026-08-05 from the CraftBenchTemplate
// fixture of the same name; every checkpoint, threshold, and gate is
// byte-identical so the substrate migration changes NO behavioral gate — the
// 2026-08-06 Leg C/D redefinition landed in BOTH copies the same way).
// Presets Health, applies Ability.Poison by tag, and samples Health over time:
//   Checkpoint 0 (THE STAGE-1 GATE — 2026-08-05 health-first redefinition: the
//                    task is two stages the agent builds in order; stage 1 =
//                    build the health system, stage 2 = the poison DoT): the
//                    graded pawn derives from the ASC-only task base, its ASC
//                    carries Health, Health initialized to 100 (read BEFORE any
//                    fixture write), and a write-then-read probe at != 100.
//                    All named FAILs ("stage 1 not built/incomplete: ...").
//   Leg A (1 stack): Health drops in ~1/sec steps (periodic, not instant) and
//                    STOPS inside the ~5s acceptance band (~4-7s; the stop
//                    window opens PAST the band top, so a conforming ~6s
//                    duration passes and a permanent drain fails).
//   Leg C (refresh — GATED 2026-08-06): one application, RE-APPLIED mid-window
//                    (trigger+3.6). The drain must CONTINUE past the original
//                    expiry band (refresh extended it) AND still STOP by the
//                    refreshed expiry band. Both directions are named FAILs.
//   Leg B/D (4 applies): the drain rate must scale >= StackRatioMin x the
//                    1-stack rate (stacking works, Leg B) AND <= StackRatioMax
//                    (the cap of 3 holds — Leg D, GATED 2026-08-06; 4 uncapped
//                    applications read ~4x). Rate windows are CONGRUENT with
//                    Leg A's (both trigger+4.1s) so tick-count quantization
//                    cancels and the ratio is pinnable headless.
// Overrides PreferredAbilityTag()=Ability.Poison so the resolver picks the poison
// pawn, not another committed ACraftBenchCharacter subclass.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "PoisonStackFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API APoisonStackFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	APoisonStackFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual FGameplayTag PreferredAbilityTag() const override;

private:
	int32 LastCheckpointIndex = 0;

	// Leg A (single stack): t≈0.5 trigger, samples 1.6 / 3.1 / 4.6, then the
	// stop window 7.6 → 9.7 (trigger+7.1 → trigger+9.2).
	double A1 = -1.0, A2 = -1.0, A3 = -1.0, AStop = -1.0, ATail = -1.0;
	double AStartT = 0.0, A3T = 0.0;

	// Leg C (refresh): t≈10.7 trigger, mid 12.3 (log), re-apply 14.3
	// (= trigger+3.6), refresh window 17.9 → 19.4, refreshed-stop 21.4 → 23.5.
	double CMid = -1.0, CAtReapply = -1.0;
	double CPost1 = -1.0, CPost2 = -1.0, CStop1 = -1.0, CStop2 = -1.0;
	double CStartT = 0.0, CReapplyT = 0.0;

	// Leg B/D (4 applies → cap 3): t≈24.5 trigger, mid 26.1 (log), BEnd 28.6
	// (= trigger+4.1 — congruent with the Leg A rate window on purpose).
	double BStartT = 0.0, BEnd = -1.0, BEndT = 0.0;

	double HealthPreset = 100.0;
	// STAGE-1 gate (checkpoint 0, BEFORE the trigger). 2026-08-05 health-first
	// redefinition: stage 1 of the task is the AGENT building the health system
	// on the provided ASC-only base pawn (ACraftBenchBareCharacter), so this
	// gate's meaning flipped from anti-broken-submission defense to THE stage-1
	// verifier — same present/write-then-read mechanics (proven 2026-08-05 to
	// FAIL a no-attribute-set pawn by name), plus the derivation gate and the
	// init-to-100 read. The write probe uses a value != 100 on purpose: an
	// inert-write set that happens to initialize at 100 must not pass the
	// write-then-read vacuously. EPOCH NOTE: results before/after 2026-08-05
	// are not comparable (same convention as glide's 2026-08-04 redefinition).
	double BaselineEpsilon = 0.5;      // |read-back - expected| at idx 0 (pre-trigger, so no drain yet)
	double HealthInitExpected = 100.0; // stage-1 contract: Health initializes to 100 (read BEFORE any write)
	double WriteProbeValue = 37.0;     // != HealthInitExpected on purpose (see above)
	bool bBaselineOk = false;          // surfaced as baseline=ok in the [POISON] log line
	// Calibrated bands (2026-08-06 Leg C/D redefinition; measured values in
	// task.md §Verifier specification + discrimination/MATRIX.md).
	//
	// The ~5s ACCEPTANCE BAND, made deliberate 2026-08-06: the drain must still
	// be stepping at trigger+4.1 (the periodic gate's last sample) and be fully
	// over by trigger+7.1 (where the stop window opens) — i.e. durations of
	// roughly 4-7s pass, with one-period (~1s) enforcement granularity above the
	// top (tick observation cannot see an expiry between ticks). The retired
	// schedule's StopEpsilon=9.0 existed because its tail sample sat INSIDE the
	// band (trigger+7.0) and had to absorb legitimate expiry ticks — and still
	// mis-failed a conforming ~6s duration by two ticks. Both stop windows now
	// open PAST the band top, so StopEpsilon absorbs only jitter, never
	// legitimate ticks: 2.5 < 4.0 (= 2 x PeriodicMinStep, the smallest two-tick
	// drop a still-running conforming drain leaves in a >= 2.0s window, so a
	// permanent drain at the minimum lawful rate still fails) and > rounding
	// noise. Used by both the Leg A stop gate and the Leg C refreshed-stop gate.
	double StopEpsilon = 2.5;
	double PeriodicMinStep = 2.0;    // min Health drop between A samples (proves periodic)
	double RefreshMinStep = 2.0;     // min drop across the Leg C refresh window (same floor as PeriodicMinStep)
	double StackRatioMin = 2.0;      // GATE: 4-application rate must be >= this x the 1-stack rate
	// GATE (2026-08-06, was advisory): 4 applications must NOT drain more than
	// this x the 1-stack rate. Pinnable now because the Leg B rate window is
	// CONGRUENT with Leg A's (both (trigger, trigger+4.1]) — equal windows at
	// equal offsets cancel tick-count quantization, so the ratio reads the stack
	// multiplier directly for any conforming period/duration/on-application
	// config. Measured 2026-08-06 (-deterministic -FPS=60, congruent windows):
	// capped reference = 3.00x, uncapped probe (StackLimitCount=0) = 4.00x —
	// 3.5 sits midway with ~0.5x measured margin to both populations.
	double StackRatioMax = 3.5;
};
