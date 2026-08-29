// Copyright CraftBench. All Rights Reserved.

#include "HealthAttributeOpsFunctionalTest.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchBareCharacter.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"

AHealthAttributeOpsFunctionalTest::AHealthAttributeOpsFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

// PIN.md D3: Ability.Damage and Ability.Heal are the two NEW native tags this
// task lands in Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp} (same accessor
// shape as AbilityGlide/AbilityPoison -- CraftBenchGameplayTags.h:22-26,
// CraftBenchGameplayTags.cpp:10-22). Returning Ability.Damage here keeps this
// fixture's PreferredAbilityTag UNIQUE per GAS family, which is the whole point:
// ResolveAgentPawnClass prefers the candidate that GRANTS an ability with this
// tag (CraftBenchPawnFunctionalTest.cpp:134-144), so the glide pawn, the poison
// pawn and gp-heal-over-time's pawn can all be committed alongside this one
// without any of them winning resolution here by enumeration order.
FGameplayTag AHealthAttributeOpsFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityDamage();
}

void AHealthAttributeOpsFunctionalTest::PrepareTest()
{
	PawnSpawnLocation = FVector(0.0, 0.0, 200.0); // the pawn need not move; nothing here samples motion
	Super::PrepareTest();                          // resolve (by Ability.Damage) + spawn + possess

	// 5-checkpoint schedule (PIN.md section 2, verbatim):
	//   0.5 stage-1 ladder, preset Health to 60, trigger Ability.Damage
	//   1.2 read (drop1), trigger Ability.Damage again
	//   1.9 read (drop2), trigger Ability.Heal
	//   2.6 read (healDelta)
	//   3.3 read -- IDLE, nothing triggered (HO-11); final asserts
	//
	// The four inter-checkpoint windows are all 0.7 s. The three that feed a gate
	// -- (cp0,cp1], (cp1,cp2], (cp2,cp3] -- are therefore CONGRUENT, at equal
	// offsets from their own triggers. HO-9 and HO-10 are ratios of two such
	// windows, and only equal-length windows make a ratio pinnable: unequal ones
	// leave tick-count quantization in the numerator and denominator uncancelled,
	// which is exactly why the poison fixture's stack cap stayed ungateable until
	// its rate windows were made congruent (PoisonStackFunctionalTest.cpp:234-240).
	//
	// Literal braces on purpose: the film-strip describer statically parses the
	// braced schedule literal out of this source for per-frame time labels (a
	// variable-built TArray would demote every label to index-only).
	SetCheckpointSchedule({0.5, 1.2, 1.9, 2.6, 3.3});
	LastCheckpointIndex = 4;
}

void AHealthAttributeOpsFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Pawn.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn did not spawn/resolve"));
		return;
	}
	UAbilitySystemComponent* ASC = PawnASC(); // CraftBenchPawnFunctionalTest.h:113
	if (ASC == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn has no AbilitySystemComponent"));
		return;
	}

	// Read the POST-AGGREGATOR CURRENT value, not the base (the V1.4 law,
	// CraftBenchPawnFunctionalTest.h:170-185): a damage or heal implemented as a
	// duration/infinite modifier -- or as an Override -- never touches the base
	// value, so a base-only read would false-FAIL a conforming implementation and
	// report drop1 == 0. PawnAttribute() also returns 0.0 for a missing attribute
	// set, which is why HO-2 (PawnHasAttribute) runs first and by name.
	auto Health = [&]() -> double
	{
		return PawnAttribute(UCraftBenchAttributeSet::GetHealthAttribute());
	};
	// The write side has no base-class helper; SetNumericAttributeBase is the same
	// call the poison fixture uses (PoisonStackFunctionalTest.cpp:66-69).
	auto SetHealth = [&](double V)
	{
		ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetHealthAttribute(), static_cast<float>(V));
	};

	const FGameplayTag DamageTag = FCraftBenchGameplayTags::AbilityDamage();
	const FGameplayTag HealTag = FCraftBenchGameplayTags::AbilityHeal();

	// Record the REALIZED crossing time (world game-time -- the clock the base's
	// checkpoint loop reads, CraftBenchFunctionalTest.h:80-86). Evidence only; no
	// gate reads it. See the CrossingTimes comment in the header.
	CrossingTimes.Add(TimeSeconds);

	switch (CheckpointIndex)
	{
		case 0: // ---- the STAGE-1 LADDER (HO-1..HO-5), then preset + first damage ----
		{
			// The whole ladder is lifted from the poison fixture
			// (PoisonStackFunctionalTest.cpp:73-172); PIN.md section 1 row 1 makes
			// that reuse deliberate and constraint C1 in tasks/bp-g2/QUEUE.md
			// records the resulting correlation. Every rung FAILs by its own name
			// at cp0, so a missing stage 1 can never be misattributed to a stage-2
			// gate later in the leg.

			// HO-1 -- derivation. The graded pawn must derive from the provided
			// ASC-only task base. An empty submission resolves to the generic
			// scaffold pawn; a submission that subclasses the GENERIC pawn instead
			// of the task base inherits its PRE-BUILT health system and skips
			// stage 1 outright (AG-1). ACraftBenchBareCharacter is abstract, so it
			// can never itself win resolution (CraftBenchBareCharacter.h:21-29).
			if (!Pawn->IsA(ACraftBenchBareCharacter::StaticClass()))
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"stage 1 not built: the graded pawn (%s) does not derive from the provided task base "
					"pawn (CraftBenchBareCharacter). An empty submission resolves to the generic scaffold "
					"pawn; a submission subclassing the generic scaffold pawn inherits a pre-built health "
					"system and skips stage 1."),
					*GetNameSafe(Pawn->GetClass())));
				return;
			}
			// HO-2 -- presence. GetNumericAttribute on a missing attribute set
			// silently reads 0 and SetNumericAttributeBase silently no-ops, so
			// WITHOUT this gate a health-less submission would fail later as "the
			// damage operation did not lower Health" (misattributed) instead of by
			// name here (AG-1).
			if (!PawnHasAttribute(UCraftBenchAttributeSet::GetHealthAttribute())) // .h:191
			{
				FinishTest(EFunctionalTestResult::Failed, TEXT(
					"stage 1 not built: the pawn's health attribute system is absent - the ASC has no "
					"attribute set exposing Health, so reads return 0 and writes no-op. A pawn that never "
					"builds (or detaches) the contract attribute set looks exactly like this."));
				return;
			}
			// HO-3 -- initialization. Health must read 100 BEFORE any fixture write
			// (the AGENT initializes it; the fixture's own preset below would mask
			// an uninitialized attribute if this read came later). Absolute bar,
			// lawful because the prompt discloses it. The literal "100" in the
			// message is per PIN.md section 2 and must be kept in step with
			// HealthInitExpected if that member is ever re-pinned.
			InitRead = Health();
			if (FMath::Abs(InitRead - HealthInitExpected) > BaselineEpsilon)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"stage 1 incomplete: Health must initialize to 100 but read %.1f before any fixture "
					"write (|delta| %.2f > %.2f). An attribute set that is registered but never "
					"initialized reads 0 here."),
					InitRead, FMath::Abs(InitRead - HealthInitExpected), BaselineEpsilon));
				return;
			}
			// HO-4 -- writability. Write-then-read at a value != the init value: an
			// inert-write set that initializes at 100 would pass a 100-write
			// vacuously (AG-2). No ability has been triggered yet, so nothing else
			// can have moved Health inside this checkpoint.
			SetHealth(WriteProbeValue);
			WriteProbeRead = Health();
			if (FMath::Abs(WriteProbeRead - WriteProbeValue) > BaselineEpsilon)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"stage 1 incomplete: health attribute is inert, write-then-read failed (wrote %.1f, "
					"read back %.1f, |delta| %.2f > %.2f). An inert or shadowed attribute set accepts the "
					"write but keeps reading its own value."),
					WriteProbeValue, WriteProbeRead, FMath::Abs(WriteProbeRead - WriteProbeValue), BaselineEpsilon));
				return;
			}
			// HO-5 -- VISIBLE-CHARACTER gate (AG-5). The graded pawn must carry a
			// skeletal/static mesh component with a mesh actually assigned, so a
			// human reviewing the film strip can SEE the character. Structural and
			// deterministic; measured 2026-08-04 on the glide family, 9/9 matrix
			// reps shipped meshless pawns. Same shape as
			// PoisonStackFunctionalTest.cpp:143-172.
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

			// Stage 1 passed. Preset Health to 60 -- NOT 100 (PIN.md D4): two
			// damages of at most 25 plus one heal of at most 25 keep the entire leg
			// strictly inside (0, 100) for EVERY conforming magnitude, so neither a
			// floor clamp at 0 nor a MaxHealth ceiling can saturate an operation
			// mid-leg. A saturated heal or a clamped second damage would shrink
			// healDelta/drop2 and turn a conforming implementation into a
			// misattributed HO-9/HO-10 FAIL -- the anti-F3 discipline.
			SetHealth(PresetHealth);
			bBaselineOk = true;
			// H0 is read AFTER the preset and BEFORE the trigger: an instant damage
			// executes inside TryActivateAbilitiesByTag, so reading after the
			// trigger would blur the first application into the baseline and make
			// drop1 read 0.
			H0 = Health();
			++DamageTriggerAttempts;
			if (TriggerAbilityByTag(DamageTag)) { ++DamageActivations; } // .h:120
			break;
		}
		case 1: // drop1 closes; second damage opens drop2. Read BEFORE the trigger.
			H1 = Health();
			++DamageTriggerAttempts;
			if (TriggerAbilityByTag(DamageTag)) { ++DamageActivations; }
			break;
		case 2: // drop2 closes; the heal opens healDelta. Read BEFORE the trigger.
			H2 = Health();
			bHealActivated |= TriggerAbilityByTag(HealTag);
			break;
		case 3: // healDelta closes; the IDLE window opens (nothing is triggered here).
			H3 = Health();
			break;
		case 4: // idle window closes (HO-11).
			H4 = Health();
			break;
		default:
			break;
	}

	if (CheckpointIndex < LastCheckpointIndex)
	{
		return;
	}

	// ---- final assertions (HO-6..HO-11) ----

	const int32 GrantedDamage = NumGrantedAbilitiesWithTag(DamageTag); // .h:117
	const int32 GrantedHeal = NumGrantedAbilitiesWithTag(HealTag);

	const double Drop1 = H0 - H1;      // (cp0, cp1] -- 0.7 s
	const double Drop2 = H1 - H2;      // (cp1, cp2] -- 0.7 s, CONGRUENT with the above
	const double HealDelta = H3 - H2;  // (cp2, cp3] -- 0.7 s, CONGRUENT with both
	const double IdleDelta = H4 - H3;  // (cp3, cp4] -- nothing triggered

	// Both ratios share the SAME denominator (Drop1), and both are guarded below
	// by a named FAIL before either is gated. The 0.0 fallback here exists only so
	// the diagnostic line can always be emitted -- it is never gated on.
	const bool bDenominatorUsable = (Drop1 > DirectionEpsilon);
	const double RepeatRatio = bDenominatorUsable ? (Drop2 / Drop1) : 0.0;
	const double SymRatio = bDenominatorUsable ? (HealDelta / Drop1) : 0.0;

	// THE CALIBRATION INSTRUMENT. Every bar in PIN.md is PROPOSED - NOT YET
	// MEASURED, so this one line has to be enough to read the real population off
	// a single run: the raw ladder readings, all five Health samples, all three
	// deltas and both ratios. Emitted BEFORE the gates so it survives a FAIL.
	UE_LOG(LogTemp, Display,
		TEXT("[HEALTHOPS-FINAL] grantedDamage=%d grantedHeal=%d activatedDamage=%d activatedHeal=%d "
		     "init=%.1f writeProbe=%.1f h0=%.1f h1=%.1f h2=%.1f h3=%.1f h4=%.1f "
		     "drop1=%.2f drop2=%.2f heal=%.2f repeatRatio=%.2f symRatio=%.2f"),
		GrantedDamage, GrantedHeal, DamageActivations, bHealActivated ? 1 : 0,
		InitRead, WriteProbeRead, H0, H1, H2, H3, H4,
		Drop1, Drop2, HealDelta, RepeatRatio, SymRatio);
	// The realized window lengths, so the CONGRUENCE the two ratio gates rest on
	// is evidence in the log rather than an assumption in a comment. Guarded on
	// Num() because a fixture that FinishTest(Failed)s early never reaches here
	// with a full array.
	auto Window = [this](int32 A, int32 B) -> double
	{
		return (CrossingTimes.IsValidIndex(A) && CrossingTimes.IsValidIndex(B))
			? (CrossingTimes[B] - CrossingTimes[A]) : 0.0;
	};
	UE_LOG(LogTemp, Display,
		TEXT("[HEALTHOPS-FINAL] baseline=%s idleDelta=%.2f w1=%.3f w2=%.3f w3=%.3f w4=%.3f "
		     "(bars PROPOSED - NOT YET MEASURED: band %.1f-%.1f, repeatTol %.2f, symTol %.2f, "
		     "deltaEpsilon %.2f)"),
		bBaselineOk ? TEXT("ok") : TEXT("unchecked"), IdleDelta,
		Window(0, 1), Window(1, 2), Window(2, 3), Window(3, 4),
		MagnitudeMin, MagnitudeMax, RepeatTol, SymTol, DirectionEpsilon);

	// HO-6 -- both operations are ACTIVATABLE ABILITIES, granted on the pawn and
	// reachable by tag. This is the AG-3 defense: an implementation that pokes the
	// attribute from Tick or BeginPlay moves the numbers without ever being
	// activatable. Checked per tag so the FAIL names WHICH one is missing.
	if (GrantedDamage < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no activatable ability tagged Ability.Damage on the pawn (health operations not implemented "
			     "as activatable abilities). granted=%d"), GrantedDamage));
		return;
	}
	if (DamageActivations < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"an ability tagged Ability.Damage was granted but did NOT activate on TryActivateAbilitiesByTag"));
		return;
	}
	// HO-6c (added 2026-08-10 by adversarial review) -- EVERY damage activation
	// must have landed, and this must be said BY NAME.
	//
	// The fixture triggers Ability.Damage twice, 0.7s apart. UE 5.8 refuses
	// re-activation of an InstancedPerActor ability that is still running
	// (bRetriggerInstancedAbility defaults false), and of any ability whose
	// CommitAbility cooldown has not elapsed - in both cases
	// TryActivateAbilitiesByTag returns false having logged only at Verbose.
	// Those are idiomatic GAS shapes, not gaming. Before this gate existed the
	// second refusal surfaced as Drop2=0 -> RepeatRatio=0.00 -> HO-9 "your damage
	// is not a fixed amount", i.e. a conforming submission FAILed under a name
	// describing something it did not do. The prompt now discloses the cadence
	// ("activates the damage ability more than once, about 0.7 seconds apart");
	// this gate makes the corresponding failure legible.
	if (DamageActivations < DamageTriggerAttempts)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("an ability tagged Ability.Damage refused a later activation: %d of %d activations were "
			     "accepted. The verifier activates damage more than once, about %.1fs apart, and each "
			     "activation must land its full effect - an ability that is still running when the next "
			     "activation arrives, or that is on cooldown, is not counted."),
			DamageActivations, DamageTriggerAttempts, 0.7));
		return;
	}
	if (GrantedHeal < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no activatable ability tagged Ability.Heal on the pawn (health operations not implemented "
			     "as activatable abilities). granted=%d"), GrantedHeal));
		return;
	}
	if (!bHealActivated)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"an ability tagged Ability.Heal was granted but did NOT activate on TryActivateAbilitiesByTag"));
		return;
	}

	// HO-7 -- direction + noise floor: the first damage application must LOWER
	// Health by more than the noise floor.
	if (!(Drop1 > DirectionEpsilon))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the damage operation did not lower Health: Health went %.1f -> %.1f across the first "
			     "application (delta %.2f, need a drop > %.2f)."),
			H0, H1, Drop1, DirectionEpsilon));
		return;
	}

	// HO-8 -- the per-application magnitude sits inside the DISCLOSED 5-25 band.
	// Absolute bar, lawful only because the prompt states it. This gate exists
	// SPECIFICALLY so a non-conforming magnitude fails by its own name instead of
	// being misattributed to HO-9 or HO-10: an agent that picks 60 would otherwise
	// drive Health through the floor mid-leg and be told its damage "is not a
	// fixed amount", which is the F5 failure mode reproduced in a new task. The
	// band digits in the message are literal per PIN.md section 2 -- keep them in
	// step with MagnitudeMin/MagnitudeMax if either is ever re-pinned.
	if (Drop1 < MagnitudeMin || Drop1 > MagnitudeMax)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the per-application Health change is outside the stated %.0f-%.0f band: one damage moved Health "
			     "by %.1f. The prompt fixes a per-application amount between %.0f and %.0f."),
			MagnitudeMin, MagnitudeMax, Drop1, MagnitudeMin, MagnitudeMax));
		return;
	}

	// RATIO DENOMINATOR GUARD -- HO-9 and HO-10 both divide by Drop1. HO-7 and
	// HO-8 have already bounded it into [MagnitudeMin, MagnitudeMax], so this is
	// unreachable in practice; it is here so that a future reordering of the gates
	// can never reach a division by zero. It FAILS BY NAME rather than dividing.
	if (!bDenominatorUsable)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the repeatability and symmetry ratios have no usable denominator: the first damage "
			     "application moved Health by %.2f (need > %.2f). HO-9 and HO-10 are both ratios against "
			     "that first application and cannot be formed."),
			Drop1, DirectionEpsilon));
		return;
	}

	// HO-9 -- repeatability. drop2/drop1 over two CONGRUENT 0.7 s windows. This is
	// the AG-4 defense against "damage = set Health to a constant": that removes a
	// different amount the second time, so the ratio collapses.
	if (RepeatRatio < (1.0 - RepeatTol) || RepeatRatio > (1.0 + RepeatTol))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the damage operation is not a fixed amount: the first application removed %.1f and the "
			     "second removed %.1f (ratio %.2f, need %.2f-%.2f). A one-shot that sets Health to a "
			     "constant removes a different amount the second time."),
			Drop1, Drop2, RepeatRatio, 1.0 - RepeatTol, 1.0 + RepeatTol));
		return;
	}

	// HO-10 -- symmetry. healDelta/drop1, again over congruent 0.7 s windows. This
	// is the gate that catches the plausible-WRONG solve in PIN.md section 4:
	// "on activate, set Health = MaxHealth" passes HO-1..HO-7 and HO-11 and dies
	// here, by name, with ratio 6.00.
	if (SymRatio < (1.0 - SymTol) || SymRatio > (1.0 + SymTol))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("heal does not restore what damage removes: one damage removed %.1f but one heal restored "
			     "%.1f (ratio %.2f, need %.2f-%.2f). Restoring to full health, or healing a different "
			     "amount, fails here."),
			Drop1, HealDelta, SymRatio, 1.0 - SymTol, 1.0 + SymTol));
		return;
	}

	// HO-11 -- the operations are EVENT-DRIVEN, not a passive drift. Nothing was
	// triggered in (cp3, cp4], so Health must not move in either direction. This
	// is the AG-6 defense: a tick-driven regeneration loop that makes the heal
	// look like it worked keeps moving Health here.
	if (FMath::Abs(IdleDelta) > IdleEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("Health kept moving with no operation active: %.1f -> %.1f in the idle window "
			     "(|delta| %.2f > %.2f). Damage and heal must change Health only when activated."),
			H3, H4, FMath::Abs(IdleDelta), IdleEpsilon));
		return;
	}

	// All eleven deterministic gates passed -- the base finishes Succeeded after
	// the last checkpoint.
}
