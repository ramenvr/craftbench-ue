// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// AGlideStaminaFunctionalTest — L2 fixture for task gp-glide-stamina-bp on the
// ThirdPerson substrate (ported verbatim 2026-08-05 from the CraftBenchTemplate
// fixture of the same name; every checkpoint, threshold, and gate is
// byte-identical so the substrate migration changes NO behavioral gate). Spawn
// high, free-fall to establish a fast descent, fire Ability.Glide by tag, then
// verify the glide slows the descent and drains the Power resource (and, if
// Power exhausts in-window, that the slow-fall stops). Pawn resolved by
// derivation + spawned/possessed by the base.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "GlideStaminaFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AGlideStaminaFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	AGlideStaminaFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

	/** Prefer the pawn granting Ability.Glide so a foreign task's committed pawn
	 *  (e.g. the launch pawn) can't be resolved instead. */
	virtual FGameplayTag PreferredAbilityTag() const override;

private:
	int32 LastCheckpointIndex = 0;
	int32 TriggerCheckpoint = 2;  // free-fall first to build a fast descent, THEN glide
	bool bTriggered = false;
	double TriggerTime = 0.0;

	double FreeFallSpeed = 0.0;        // |vZ| at the pre-trigger free-fall sample
	double PowerAtTrigger = 0.0;       // Power right after the preset, at trigger
	double MinGlideSpeed = TNumericLimits<double>::Max();  // min |vZ| while gliding (Power>0 AND descending)
	/** Post-trigger samples with Power>0 that were NOT descending (vZ >= 0):
	 *  hovering, landed, or rising. Excluded from MinGlideSpeed — going up is
	 *  not a slow descent, and a hover scoring 0 used to satisfy gate (3) and
	 *  zero out gate (5)'s bar. Counted so a run that glides in name only can
	 *  say so instead of just reporting "no gliding samples". */
	int32 NonDescendingGlideSamples = 0;
	double LastSpeed = 0.0;            // |vZ| at the final sample
	double LastSampleTime = -1.0;      // TimeSeconds of that final sample (diagnostic)
	double MinPowerSeen = TNumericLimits<double>::Max();   // lowest Power observed post-trigger
	bool bPowerDrained = false;        // Power strictly decreased after trigger

	// Records WHEN Power first hit ~0 and what the descent was doing at that
	// instant, so a gate-(5) failure can be told apart from a MEASUREMENT-WINDOW
	// artifact without reconstructing it by hand from the [GLIDE] sample lines.
	// Was diagnostic-only; since 2026-08-06 the post-exhaustion OBSERVATION
	// WINDOW derived from ExhaustTime (LastSampleTime - ExhaustTime) is
	// gate-consumed: gate (5) may hard-FAIL only when it is >= ResumeWindowFloor
	// (below the floor it SKIPs — see that member). SpeedAtExhaust and the
	// mean-accel diagnostic line remain advisory-only.
	//
	// Why this exists (measured 2026-08-03, two independent opus-5 submissions):
	// both slowed the fall, drained Power to 0, and were visibly re-accelerating
	// at the last sample — yet failed gate (5) with final |vZ| = 182 and 291
	// against ResumeVZ = 350. The reference exhausts ~1.0 s after the trigger
	// and gets ~0.6 s of the schedule left to re-accelerate; a slower-but-
	// conforming drain exhausts near the last checkpoint and gets ~0.1 s. The
	// prompt never specifies a drain RATE, so gate (5) as written conflates
	// "the glide stopped" with "it drained fast enough to leave measuring room".
	// These fields make that visible in one log line.
	double ExhaustTime = -1.0;         // TimeSeconds of the FIRST sample with Power <= PowerEpsilon
	double SpeedAtExhaust = -1.0;      // |vZ| at that same sample (the resume baseline)

	// --- calibrated thresholds (pinned empirically from the reference run) ---
	double PowerPreset = 30.0;         // verifier presets Power to this at trigger
	double SlowFactor = 0.6;           // glide |vZ| must be <= SlowFactor * free-fall |vZ|
	double MinFreeFallSpeed = 100.0;   // baseline sanity: pawn was really falling
	double PowerEpsilon = 0.5;         // "Power reached ~0" tolerance
	double ResumeVZ = 350.0;           // post-exhaustion |vZ| that ends gate (5) outright

	// Gate (5) FALLBACK, added 2026-08-04. Four independent submissions failed
	// the absolute ResumeVZ at 182 / 291 / 300 / 346 while behaving correctly.
	// The per-sample telemetry settles it — reconstructing each run from its own
	// drain rate and one gravity predicts its final speed exactly:
	//
	//   reference  drains 30/s, empties at 2.60s, 0.50s of fall -> 182+980*0.50 = 672 (measured 672)
	//   opus-5 C   drains 20/s, empties at 3.00s, 0.10s of fall -> 150+980*0.10 = 248 (measured 300)
	//   opus-5 A   drains 20/s, empties at 3.10s, ~0.00s        -> ~150             (measured 182)
	//
	// Same physics in all three: the glide clamps |vZ|, and full gravity resumes
	// the instant Power hits 0. The ONLY difference is the drain rate — 30/s vs
	// 20/s — which the prompt never specifies ("steadily drains the Power
	// resource" is all it asks). ResumeVZ was therefore grading how fast the
	// stamina burned, and the gp-poison family's own law is that every gate must
	// be a RATIO, never an absolute magnitude.
	//
	// A mean-acceleration test does NOT work here and was tried first: the last
	// inter-sample gap is a MIXTURE of gliding and falling, so opus-5 C measures
	// (300-150)/0.4 = 375 cm/s^2 and would be failed by any threshold that still
	// rejects a partial-gravity fake. The ratio below compares two quantities the
	// same run actually produced, needs no timing model, and is unaffected by the
	// drain rate.
	double ResumeFactor = 1.5;         // final |vZ| must exceed the observed glide
	                                   // speed by this much once Power hits 0.
	                                   // reference 3.7x, the four false-failures
	                                   // 1.8-2.0x, a glide that never stops 1.0x.

	// Gate (5) WINDOW FLOOR, added 2026-08-06. The ratio fallback above is only
	// meaningful when there was ROOM to observe the resume. When a conforming-
	// but-slower-than-reference drain empties Power at exactly the last
	// checkpoint, the "final" sample IS the exhaust sample plus one partial
	// inter-sample gap, and the ratio reads 1.3-1.5x no matter what the glide
	// did — measured on 4 reps across BOTH substrates the week of 2026-08-06
	// (3 reps of bench-20260806-023946: window=0.00s, |vZ|=298 vs a 300 bar;
	// the build machine's glide-bp opus rep 2: 1.33x). Those are near-miss FAILs on correct
	// work — the unforgivable failure mode. So gate (5) may hard-FAIL only when
	// the post-exhaustion observation window is >= this floor; under it the
	// gate routes to the SAME skip semantics as "Power never emptied in-window"
	// ([GLIDE-RESUME-DIAG] ... SKIPPED, not failed). Gates (3)+(4) already
	// proved glide+drain, so a skipped (5) loses one bit of signal, never the
	// verdict's integrity — no static schedule can eliminate the boundary zone
	// where Power empties inside the final inter-sample gap; the floor closes
	// it honestly. 0.30 sits comfortably under the reference's MEASURED window
	// (2026-08-03 baseline: exhausted_at=2.70s, window=0.40s, re-accel
	// 980 cm/s^2 -> |vZ|=671), so the reference still hard-gates; the extended
	// schedule (see PrepareTest) shrinks the skip zone to drains that empty
	// inside the final 0.5s gap.
	double ResumeWindowFloor = 0.30;   // min post-exhaustion window (s) for
	                                   // gate (5) to be allowed to hard-FAIL;
	                                   // below it -> SKIPPED, not failed

	// --- FORCED EXHAUSTION (owner decision 2026-08-09) ---------------------
	// WHY. Everything above makes gate (5) honest about when it CAN measure a
	// resume; none of it makes it measure one. The skip paths are keyed on
	// whether Power emptied in-window — and the DRAIN RATE IS CHOSEN BY THE
	// SUBMISSION. So the model decides whether the hardest requirement in the
	// prompt ("when Power reaches zero, the slowed descent must end") is tested
	// at all. Measured 2026-08-09 over the six -cpp runs on disk: 1 of 4 PASSes
	// never asserted it (opus-5 rep 20260809-012802 — minpower=4.2, gate (5)
	// SKIPPED). A glide that ignores exhaustion entirely passes, provided it
	// drains slowly enough. That is a gaming surface, and it means two PASSes on
	// this task are not the same claim.
	//
	// WHAT. At ForceExhaustCheckpoint the verifier ZEROES Power itself, so the
	// resume is observed against a window IT chose instead of one the drain rate
	// handed out. This is not a new kind of intervention: the fixture already
	// WRITES this attribute (PowerPreset, at the trigger) and already activates
	// the ability by tag. It is the same lever, used a second time.
	//
	// STRICTLY MONOTONE — it fires ONLY when bPowerDrained is already true, i.e.
	// when the submission has itself demonstrated a drain. That is what makes
	// this safe to land without re-grading anything:
	//   * a submission that never drains is untouched (gate (4) fails it, as before);
	//   * a submission that exhausts naturally before this checkpoint is untouched
	//     (the REFERENCE drains 30/s and empties ~1.0s after the trigger, i.e. at
	//     t~2.5 — a full checkpoint earlier, so its path does not change at all);
	//   * the only behaviour that changes is the one this exists to catch: drained,
	//     still gliding, and previously never asked to stop.
	// Residual (accepted, and small): a drain so slow that bPowerDrained is still
	// false here keeps the old skip semantics. Closing that too would mean forcing
	// on a submission that has not shown a drain, which would credit our own write
	// as the model's.
	//
	// idx 6 (t=3.1) leaves 1.0s of schedule; the first zero-Power SAMPLE lands at
	// idx 7 (t=3.6), so the measured post-exhaustion window is 0.5s — comfortably
	// over ResumeWindowFloor, and enough runway for one gravity to carry any
	// conforming glide past ResumeFactor * MinGlideSpeed.
	int32 ForceExhaustCheckpoint = 6;
	bool bForcedExhaust = false;       // Power was zeroed BY THE VERIFIER, not the ability
};
