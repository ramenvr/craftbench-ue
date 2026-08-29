// Copyright CraftBench. All Rights Reserved.

#include "GlideStaminaFunctionalTest.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"

AGlideStaminaFunctionalTest::AGlideStaminaFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

FGameplayTag AGlideStaminaFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityGlide();
}

void AGlideStaminaFunctionalTest::PrepareTest()
{
	// Spawn very high so the pawn free-falls a long way (builds a fast descent
	// before the glide, and never lands within the schedule).
	PawnSpawnLocation = FVector(0.0, 0.0, 5000.0);
	Super::PrepareTest(); // resolve + spawn + SpawnDefaultController the agent pawn

	// Free-fall through idx 0..2 to build a fast descent, trigger glide at idx 2,
	// glide through idx 3..4 (Power>0); the reference exhausts ~2.7s and resumes
	// fall with ~1.4s of runway. idx 7..8 (3.6, 4.1) appended 2026-08-06: a
	// conforming-but-slower-than-reference drain that emptied Power at the old
	// 3.1s tail got a 0.00s post-exhaustion window (4 measured near-miss FAILs —
	// see ResumeWindowFloor in the header). The 0.5s spacing (a shade wider than
	// the 0.4s tail, bounding sim time) gives any drain that empties by ~3.6s a
	// >=0.5s window; later still and gate (5) skips via the window floor /
	// never-exhausted paths. SetCheckpointSchedule() auto-extends the failure
	// TimeLimit to last + TimeLimitMargin (verified in the base class:
	// 4.1 + 2.0 = 6.1s), so no separate time-limit change is needed.
	const TArray<double> Schedule = {0.5, 1.0, 1.5, 1.9, 2.3, 2.7, 3.1, 3.6, 4.1};
	LastCheckpointIndex = Schedule.Num() - 1;
	SetCheckpointSchedule(Schedule);
}

void AGlideStaminaFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Pawn.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn did not spawn/resolve"));
		return;
	}

	RecordSample(TimeSeconds);
	const double Speed = FMath::Abs(static_cast<double>(Pawn->GetVelocity().Z));
	LastSpeed = Speed;
	LastSampleTime = TimeSeconds;   // diagnostic pair for LastSpeed

	// Checkpoint 0 — VISIBLE-CHARACTER gate (2026-08-06, owner decision; applied
	// to the whole glide/poison family, both variants — this fixture is shared).
	// The graded pawn must carry a skeletal/static mesh component with a mesh
	// actually assigned, so a human reviewer watching the run (film strip /
	// preview) can SEE the character. Structural + deterministic — the
	// fixture-level twin of the -bp variant's L2I pawn_visibly_represented
	// check (measured 2026-08-04: all 9 matrix reps shipped meshless pawns and
	// the C++ task's film strips showed an empty scene). Named FAIL here at
	// checkpoint 0, never a misattributed later gate.
	if (CheckpointIndex == 0)
	{
		// Visible-character gate — hoisted to the base class 2026-08-11. The
		// inlined copy this replaces (in FIVE fixtures) asserted only "a mesh
		// asset is assigned somewhere", so a mesh hidden in game or scaled to
		// nothing passed the gate that exists BECAUSE reps shipped pawns nobody
		// could see. See ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented
		// for what is deliberately NOT asserted (asset path, mesh type, size).
		FString VisWhy;
		if (!PawnVisiblyRepresented(VisWhy))
		{
			FinishTest(EFunctionalTestResult::Failed, VisWhy);
			return;
		}
	}

	UAbilitySystemComponent* ASC = PawnASC();
	const double Power = (ASC != nullptr)
		? static_cast<double>(ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute()))
		: -1.0;

	// Checkpoint 1 — STARTING-POWER gate (owner decision 2026-08-09).
	// The prompt asks for a pawn "starting with some Power to spend" and NOTHING
	// verified it: this fixture reads Power at every checkpoint but branched on it
	// only from the trigger onward, and AT the trigger it OVERWRITES the value
	// (PowerPreset). A submission that seeded no Power at all passed — the same
	// shape as the gate-(5) hole closed above: the prompt asked, the verifier
	// did not check.
	//
	// Not a vacuous gate: UCraftBenchAttributeSet declares
	// `FGameplayAttributeData Power;` with NO initializer and ACraftBenchCharacter
	// never seeds it, so the scaffold pawn genuinely starts at 0. The reference
	// seeds 100 (GlidePawn.cpp).
	//
	// Checkpoint 1 (t=1.0), not 0: the base spawns+possesses in PrepareTest and
	// BeginPlay seeding lands well before t=0.5, but a whole extra checkpoint of
	// settling costs nothing and removes any argument about timing. The trigger is
	// checkpoint 2, so this still reads a PRE-glide value.
	//
	// PowerPreset STAYS: this gate is about the resource EXISTING, the preset is
	// about the drain measurement being comparable across submissions. Two
	// different questions — do not collapse them.
	//
	// The `ASC != nullptr` guard is load-bearing, not defensive noise: `Power` is
	// the sentinel -1.0 when there is no ASC, which is <= PowerEpsilon and would
	// fail HERE with a misleading message. A missing ASC is gate (1)'s business
	// ("no activatable ability tagged Ability.Glide ... GAS not implemented"), and
	// stealing that FAIL would regress the no-gas variant's named reason — the
	// matrix would still read FAIL while proving the wrong thing.
	if (CheckpointIndex == 1 && ASC != nullptr && Power <= PowerEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the pawn does not start with any Power to spend (Power=%.1f at t=%.2f, "
			     "before the glide) — the prompt asks for a pawn that starts with Power"),
			Power, TimeSeconds));
		return;
	}

	// Trigger: capture the free-fall baseline AT the trigger moment (the actual fast
	// descent the glide must slow), then preset Power and fire Ability.Glide by tag.
	if (CheckpointIndex == TriggerCheckpoint && !bTriggered)
	{
		FreeFallSpeed = Speed;  // pre-glide descent speed (compared against the gliding speed)
		if (ASC != nullptr)
		{
			ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), static_cast<float>(PowerPreset));
		}
		TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityGlide());
		bTriggered = true;
		TriggerTime = TimeSeconds;
		PowerAtTrigger = (ASC != nullptr)
			? static_cast<double>(ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute()))
			: -1.0;
	}

	// After the trigger settles: track the slowed descent + the Power drain.
	if (bTriggered && TimeSeconds > TriggerTime + 0.05)
	{
		MinPowerSeen = FMath::Min(MinPowerSeen, Power);
		// DESCENDING, not merely slow. `Speed` is |vZ| (an absolute value taken
		// at the top of this function), so without the sign test this counted
		// any small vertical speed as "a genuine gliding sample" — including
		// two shapes that are not descents at all:
		//
		//   * ASCENDING. A pawn rising at 300 cm/s scored 300 and satisfied
		//     gate (3) ("descends noticeably slower than an unaided fall").
		//     Going UP is not a slow descent.
		//   * HOVERING / LANDED. vZ == 0 scored 0, which passes gate (3)
		//     trivially AND drives gate (5)'s bar to ResumeFactor * 0 == 0, so
		//     `LastSpeed < 0` is never true. A permanent mid-air freeze — the
		//     exact "not a teleport" shape the prompt forbids — passed BOTH.
		//     One missing sign test, two holes.
		//
		// Conservative by construction: it only EXCLUDES samples, and every
		// sample of a real glide is descending, so MinGlideSpeed is unchanged
		// for conforming work (recorded runs sit at 256-406 cm/s of descent).
		// A submission that bobs upward mid-glide simply has those samples
		// ignored, which is what "minimum descent speed" should have meant.
		const double VelZ = static_cast<double>(Pawn->GetVelocity().Z);
		if (Power > PowerEpsilon && VelZ < 0.0)
		{
			MinGlideSpeed = FMath::Min(MinGlideSpeed, Speed); // a genuine "gliding" sample
		}
		else if (Power > PowerEpsilon)
		{
			// Not a descent. Recorded rather than silently dropped: a run whose
			// entire "glide" is non-descending will fail gate (3) for having no
			// gliding sample at all, and this line is what tells a reader why.
			NonDescendingGlideSamples++;
		}
		else if (ExhaustTime < 0.0)
		{
			// FIRST sample at ~0 Power. Diagnostic only — nothing branches on it.
			ExhaustTime = TimeSeconds;
			SpeedAtExhaust = Speed;
		}
		// Only the SUBMISSION's own drain may set this. After the verifier zeroes
		// Power (below), the attribute no longer reports the ability's behaviour,
		// and crediting our own write as the model's drain would turn gate (4)
		// into a formality.
		if (!bForcedExhaust && Power < PowerAtTrigger - PowerEpsilon)
		{
			bPowerDrained = true;
		}
	}

	// FORCED EXHAUSTION — make gate (5) unconditional (see the header).
	// Placed AFTER the bookkeeping above so this checkpoint's own sample is the
	// pre-write value, and fired ONLY when the submission has already proved it
	// drains: that is what keeps this monotone, i.e. incapable of changing any
	// outcome except the one it exists to catch (drained, still gliding, and
	// previously never asked to stop).
	if (bTriggered && !bForcedExhaust && bPowerDrained
		&& CheckpointIndex == ForceExhaustCheckpoint
		&& MinPowerSeen > PowerEpsilon    // it did not already empty on its own
		&& ASC != nullptr)
	{
		ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), 0.0f);
		bForcedExhaust = true;
		UE_LOG(LogTemp, Display, TEXT(
			"[GLIDE-FORCE] Power zeroed BY THE VERIFIER at t=%.2f (was %.1f; the drain was "
			"real but would not have emptied inside the schedule). The prompt requires the "
			"slowed descent to END when Power reaches zero — this makes that testable "
			"regardless of the drain rate the submission chose."),
			TimeSeconds, Power);
	}

	// `speed=` is the CACHED gate-consumed sample from the top of this
	// checkpoint; `vZnow=` is re-read at log time and legitimately differs at
	// the trigger checkpoint for an instant-clamp implementation (measured
	// 2026-08-04: opus rep2 logged vZ=-150 next to speed=1208.7 at idx=2 and
	// the mismatch cost a manual adjudication). Renamed from `vZ=` so nobody
	// reads the post-trigger value as the gate input again.
	UE_LOG(LogTemp, Display,
		TEXT("[GLIDE] idx=%d t=%.2f speed=%.1f vZnow=%.1f power=%.1f freefall=%.1f minglide=%.1f"),
		CheckpointIndex, TimeSeconds, Speed, Pawn->GetVelocity().Z, Power, FreeFallSpeed,
		(MinGlideSpeed == TNumericLimits<double>::Max() ? -1.0 : MinGlideSpeed));

	if (CheckpointIndex < LastCheckpointIndex)
	{
		return;
	}

	// ---- final assertions ----
	const FGameplayTag GlideTag = FCraftBenchGameplayTags::AbilityGlide();
	const int32 Granted = NumGrantedAbilitiesWithTag(GlideTag);
	const bool bExhausted = (MinPowerSeen <= PowerEpsilon);

	UE_LOG(LogTemp, Display,
		TEXT("[GLIDE-FINAL] granted=%d activated=%d freefall=%.1f minglide=%.1f minpower=%.1f drained=%d exhausted=%d forced=%d lastspeed=%.1f"),
		Granted, bAbilityActivated ? 1 : 0, FreeFallSpeed,
		(MinGlideSpeed == TNumericLimits<double>::Max() ? -1.0 : MinGlideSpeed),
		(MinPowerSeen == TNumericLimits<double>::Max() ? -1.0 : MinPowerSeen),
		bPowerDrained ? 1 : 0, bExhausted ? 1 : 0, bForcedExhaust ? 1 : 0, LastSpeed);

	// The measuring room gate (5) actually had. `window` is how much of the
	// schedule remained AFTER Power hit ~0, and `accel` is the mean
	// re-acceleration observed inside it. Since 2026-08-06 `window` is
	// GATE-CONSUMED — gate (5) may hard-FAIL only when window >=
	// ResumeWindowFloor, so a tiny-window run (a slow-but-conforming drain
	// running out of schedule, NOT a bad glide) now SKIPs instead of
	// near-miss failing; `accel` stays diagnostic-only. On a gate-(5) FAIL
	// read these two numbers FIRST: a large window with a near-zero accel is
	// a glide that really did ignore exhaustion. Deciding that from
	// `lastspeed` alone is impossible,
	// which is why two correct-looking 2026-08-03 submissions (final |vZ| 182
	// and 291 vs ResumeVZ 350) could not be adjudicated without re-deriving
	// this by hand from the per-sample [GLIDE] lines.
	if (bExhausted && ExhaustTime >= 0.0)
	{
		const double Window = LastSampleTime - ExhaustTime;
		const double Accel = (Window > KINDA_SMALL_NUMBER)
			? (LastSpeed - SpeedAtExhaust) / Window : -1.0;
		UE_LOG(LogTemp, Display,
			TEXT("[GLIDE-RESUME-DIAG] exhausted_at=%.2fs speed_then=%.1f "
			     "last_sample_at=%.2fs window=%.2fs speed_now=%.1f mean_accel=%.0f cm/s^2 "
			     "(gate needs |vZ| >= %.0f. MEASURED reference baseline 2026-08-03: "
			     "exhausted_at=2.70 window=0.40 accel=980 -> 671. accel ~980 is ONE gravity, "
			     "i.e. a correct resume; a short window with accel ~980 means the drain was "
			     "slower than the reference's, NOT that the glide ignored exhaustion.)"),
			ExhaustTime, SpeedAtExhaust, LastSampleTime, Window, LastSpeed, Accel, ResumeVZ);
	}
	else if (!bExhausted)
	{
		UE_LOG(LogTemp, Display, TEXT(
			"[GLIDE-RESUME-DIAG] Power never reached ~0 in-window (min=%.1f) — "
			"gate (5) is SKIPPED, not failed."),
			(MinPowerSeen == TNumericLimits<double>::Max() ? -1.0 : MinPowerSeen));
	}

	// (1) GAS implemented: an activatable ability carries the glide tag.
	if (Granted < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=%d"), Granted));
		return;
	}

	// (2) It activated on the tag-trigger.
	if (!bAbilityActivated)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"an ability tagged Ability.Glide was granted but did NOT activate on TryActivateAbilitiesByTag"));
		return;
	}

	// baseline sanity: the pawn really was free-falling fast before the trigger.
	if (FreeFallSpeed < MinFreeFallSpeed)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no free-fall baseline: pawn was not descending fast pre-trigger (|vZ|=%.0f < %.0f)"),
			FreeFallSpeed, MinFreeFallSpeed));
		return;
	}

	if (MinGlideSpeed == TNumericLimits<double>::Max())
	{
		// Two different failures reach here, and telling them apart is the
		// difference between "your ability did nothing" and "your ability held
		// the pawn up instead of slowing its fall" — the latter being the
		// hover/teleport shape the prompt explicitly forbids.
		if (NonDescendingGlideSamples > 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("the pawn was never DESCENDING while the ability was active: all %d "
				     "post-trigger samples with Power>0 had vZ >= 0 (hovering, rising or "
				     "already landed). The prompt asks for a slower DESCENT — holding the "
				     "character up, or moving it without falling, is not a glide."),
				NonDescendingGlideSamples));
			return;
		}
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"no gliding samples captured with Power>0 (ability never reduced descent before Power ran out)"));
		return;
	}

	// (3) Descent SLOWED — the load-bearing discriminator. A no-slow / teleport fake fails here.
	if (MinGlideSpeed > SlowFactor * FreeFallSpeed)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("descent was not slowed by the glide: min glide |vZ|=%.0f > %.2f * free-fall(%.0f) = %.0f"),
			MinGlideSpeed, SlowFactor, FreeFallSpeed, SlowFactor * FreeFallSpeed));
		return;
	}

	// (4) Power drained while gliding — catches a free (no-stamina-cost) glide.
	if (!bPowerDrained)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"the Power resource did not drain while gliding (the glide consumed no stamina)"));
		return;
	}

	// (5) CONDITIONAL gate: only assert stop-on-exhaustion if Power actually reached
	//     ~0 within the window. A correct-but-slow-draining glide (Power never empties
	//     in-window) skips this (advisory) rather than false-failing; a glide that
	//     exhausts Power but keeps slowing the fall forever FAILS here.
	//     WINDOW-HONEST since 2026-08-06: a hard FAIL additionally requires the
	//     post-exhaustion observation window to be >= ResumeWindowFloor. No static
	//     schedule can eliminate the boundary zone where Power empties inside the
	//     final inter-sample gap (window ~0), and there the ratio fallback reads
	//     1.3-1.5x on conforming work (4 measured near-miss FAILs, week of
	//     2026-08-06). Below the floor the gate routes to the SAME skip semantics
	//     as "never emptied in-window" — gates (3)+(4) already proved glide+drain,
	//     so a skipped (5) costs one bit of signal, while a wrong FAIL on
	//     conforming work is the unforgivable failure mode.
	if (bExhausted)
	{
		// THE ABSOLUTE FAST PATH IS GONE (2026-08-11). It used to read
		//     if (LastSpeed < ResumeVZ) { ...the real check... }
		// so any run ending at |vZ| >= 350 skipped gate (5) ENTIRELY on the
		// grounds that such a descent "has unambiguously resumed". It has not:
		// 350 is meaningful only against the speed THIS run glided at.
		//
		// MEASURED 2026-08-11 across all 13 recorded runs of this task: every
		// one ended at 1361-1836 cm/s, so every one took the fast path and
		// gate (5)'s ratio NEVER EXECUTED — not once, on either variant. The
		// gate that asserts "the glide stops when stamina runs out", the
		// task's whole point, had never run.
		//
		// The hole it left: a submission clamping anywhere in [350, 725] cm/s
		// passes gate (3) (clamp <= 0.6 x 1208.7 free-fall) AND gate (5)
		// (>= ResumeVZ) while NEVER RELEASING. One of the seven graded
		// submissions glides at 406.5 — inside that band. Had it never
		// released, this fixture could not have told the difference.
		//
		// It also contradicted this header's own law (.h:91-93): every gate
		// must be a RATIO, never an absolute magnitude. Restoring that is all
		// this change does — the ratio branch below is unchanged, and the
		// ResumeWindowFloor skip remains the single deliberate escape.
		//
		// SAFE FOR CONFORMING WORK, checked before changing anything rather
		// than after: run every recorded run through the ratio it now must
		// clear. Margins are 3.60x-6.26x against a 1.5x bar; the tightest is
		// 20260810-230658 (406.5 -> 1461.7). Nothing known-good moves.
		{
			const double ResumeWindow = (ExhaustTime >= 0.0) ? (LastSampleTime - ExhaustTime) : 0.0;
			if (ResumeWindow < ResumeWindowFloor)
			{
				// Too little measuring room to grade the resume at all: the final
				// sample IS (nearly) the exhaust sample. SKIP, not FAIL — the
				// same semantics as "Power never emptied in-window" above.
				UE_LOG(LogTemp, Display, TEXT(
					"[GLIDE-RESUME-DIAG] post-exhaustion window=%.2fs is below the %.2fs "
					"floor (Power emptied inside the schedule's final gap) — too little "
					"room to measure the resume, so gate (5) is SKIPPED, not failed. "
					"Gates (3)+(4) already proved glide+drain; the reference's measured "
					"window is 0.40s."),
					ResumeWindow, ResumeWindowFloor);
			}
			else
			{
				// Short of the absolute bar, which by itself only means the drain was
				// slower than the reference's. Ask the question the gate is actually
				// about — did the descent break out of the glide clamp? — as a RATIO
				// against the glide speed this same run produced. See ResumeFactor.
				const double Bar = ResumeFactor * MinGlideSpeed;
				if (LastSpeed < Bar)
				{
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("Power was exhausted (min=%.1f) but the descent did NOT speed back up "
						     "in a %.2fs observation window (>= the %.2fs floor): "
						     "final |vZ|=%.0f is only %.2fx the glide speed (%.0f) — need %.1fx "
						     "(=%.0f). The glide ignored stamina exhaustion."),
						MinPowerSeen, ResumeWindow, ResumeWindowFloor, LastSpeed,
						LastSpeed / FMath::Max(MinGlideSpeed, 1.0),
						MinGlideSpeed, ResumeFactor, Bar));
					return;
				}
				// Wording no longer claims "below ResumeVZ": since the fast path
				// was removed this line fires for EVERY pass, including the
				// 1361-1836 cm/s shapes that previously skipped the gate.
				UE_LOG(LogTemp, Display, TEXT(
					"[GLIDE-ADVISORY] gate (5) PASSED on the ratio: final |vZ|=%.0f is %.2fx the "
					"glide speed (%.0f), clearing the %.1fx bar (=%.0f) — the clamp released. "
					"(ResumeVZ=%.0f is no longer an exit: an absolute speed says nothing without "
					"the glide speed it is measured against.) A slower-than-reference drain "
					"empties Power later and simply has less runway before the last sample; the "
					"prompt does not specify a drain rate."),
					LastSpeed, LastSpeed / FMath::Max(MinGlideSpeed, 1.0), MinGlideSpeed,
					ResumeFactor, ResumeFactor * MinGlideSpeed, ResumeVZ);
			}
		}
	}
	else
	{
		// Since the 2026-08-09 forced-exhaustion change this branch is NARROW: a
		// submission that drained enough to set bPowerDrained gets Power zeroed
		// for it at ForceExhaustCheckpoint, so reaching here means the drain was
		// too small to register by then (< PowerEpsilon inside ~1.6s). Gate (4)
		// usually fails such a run outright; when it does not, this is the one
		// remaining shape that escapes gate (5) — say so explicitly rather than
		// letting a reader assume the requirement was asserted.
		UE_LOG(LogTemp, Display, TEXT(
			"[GLIDE-ADVISORY] Power did not reach ~0 within the schedule (min=%.1f) AND the "
			"drain was too slow to register by the forced-exhaustion checkpoint, so it was "
			"not zeroed for it; stop-on-exhaustion is NOT gated this run."), MinPowerSeen);
	}

	// All deterministic gates passed — base finishes Succeeded after the last checkpoint.
}
