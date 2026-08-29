// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// ACraftBenchPawnFunctionalTest — base for L2 fixtures that verify a Pawn's
// motion and/or GAS behavior. Ported verbatim from the CraftBenchTemplate
// substrate 2026-08-05 (owner decision: gameplay tasks run on the ThirdPerson
// substrate) — the resolved scaffold is the same-named ACraftBenchCharacter,
// now in the ThirdPerson runtime module. Sits on top of
// ACraftBenchFunctionalTest (PIE lever, fixed-dt, checkpoint clock) and owns
// three reusable machines so a per-task fixture stays thin (a trigger tag, a
// checkpoint schedule, asserts):
//
//   1. Pawn-class resolution — find the AGENT's ACraftBenchCharacter subclass
//      (native C++ or a Blueprint asset under /Game/Tasks) and fall back to
//      the base if the agent provided none. This is identity-by-derivation:
//      the task never dictates a class name.
//   2. Spawn + possess — spawn the resolved pawn and SpawnDefaultController() it.
//      Possession is MANDATORY: the Slice-0 spike proved an unpossessed Character
//      is inert (MOVE_None, no gravity, ignores LaunchCharacter); a possessed one
//      integrates a clean ballistic arc. No input injection.
//   3. Trajectory sampler + GAS runtime probe — record (t, loc, vel, mode) at the
//      checkpoint schedule and expose shape invariants (ApexDeltaZ / RoseThenFell /
//      ReachedMovementMode), plus deterministic ASC introspection (granted ability
//      count by tag, tag-trigger). All plain API — no LLM, FR-020d-clean.
//   4. GameplayEffect application + dual attribute read (V1.1/V1.4, 2026-08-08;
//      the g2 verifier-extensions spec §5) — apply a verifier-owned
//      UGameplayEffect (CraftBenchTestEffects.h) TO the pawn through the real
//      GAS path, count the ones still active by DEFINITION IDENTITY, and read an
//      attribute both post-aggregator and at its base. This is what lets a
//      fixture make the WORLD do something to the player; SetNumericAttributeBase
//      cannot be intercepted by any ability, effect or attribute-set hook, so
//      every gate built on it only ever tested the fixture's own arithmetic.
//      STRICTLY ADDITIVE: no existing member, gate or constant changed.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GameFramework/CharacterMovementComponent.h"
// FActiveGameplayEffectHandle (returned by value) and FGameplayAttribute (taken
// by reference but needed complete for callers) must be complete types here.
#include "ActiveGameplayEffectHandle.h"
#include "AttributeSet.h"
#include "CraftBenchPawnFunctionalTest.generated.h"

class ACraftBenchCharacter;
class UAbilitySystemComponent;
class UGameplayEffect;
struct FGameplayTag;

USTRUCT()
struct FCraftBenchTrajectorySample
{
	GENERATED_BODY()

	double T = 0.0;
	FVector Location = FVector::ZeroVector;
	FVector Velocity = FVector::ZeroVector;
	TEnumAsByte<EMovementMode> Mode = MOVE_None;
};


/** One monotonic run of vertical motion, extracted from the sample series. */
USTRUCT()
struct FCraftBenchMotionSegment
{
	GENERATED_BODY()

	double StartT = 0.0;
	double EndT = 0.0;
	double StartZ = 0.0;
	double EndZ = 0.0;
	bool bRising = false;

	double DeltaZ() const { return EndZ - StartZ; }
	double Duration() const { return EndT - StartT; }
};

UCLASS(Abstract)
class CRAFTBENCHTESTS_API ACraftBenchPawnFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACraftBenchPawnFunctionalTest(const FObjectInitializer& ObjectInitializer);

	/** Resolves + spawns + possesses the agent pawn, then chains the subclass's
	 *  own PrepareTest work. A subclass calls Super::PrepareTest() FIRST, then
	 *  SetCheckpointSchedule() + any per-task setup. */
	virtual void PrepareTest() override;

protected:
	/** Where the pawn is spawned. A subclass may override before Super::PrepareTest. */
	FVector PawnSpawnLocation = FVector(0.0, 0.0, 200.0);

	/** The spawned+possessed agent pawn (valid after PrepareTest if spawn succeeded). */
	TWeakObjectPtr<ACraftBenchCharacter> Pawn;

	/** Pawn location captured at spawn (apex/displacement baseline). */
	FVector StartLocation = FVector::ZeroVector;

	// --- trajectory sampler ---------------------------------------------------

	/** Append a sample of the pawn's current motion. Call from OnCheckpoint. */
	void RecordSample(double T);

protected:
	//~ Dense sampling hook. Calls Super first so the base's checkpoint clock is
	//~ untouched, then appends one sample per tick when opted in.
	virtual void Tick(float DeltaSeconds) override;

public:

	/** Peak Z minus the first recorded sample's Z (0 if <1 sample). */
	double ApexDeltaZ() const;

	/** True if Z rose by >= MinRise from the first sample to a peak, then fell at
	 *  least FallMargin below that peak by the last sample. Catches teleport-up
	 *  (rises but never falls) and natural launch+gravity (rises then falls). */
	bool RoseThenFell(double MinRise, double FallMargin = 10.0) const;

	/** True if any recorded sample was in the given movement mode. */
	bool ReachedMovementMode(EMovementMode InMode) const;

	/** Vertical velocity of the most recent sample at or before time T (0 if none). */
	double VelocityZNear(double T) const;

	/** Max vertical velocity among samples strictly after time T (0 if none). A real
	 *  launch impulse shows a large +vZ; a position teleport leaves vZ at whatever
	 *  gravity produced (negative), so this separates a launch from a teleport. */
	double MaxVelocityZAfter(double T) const;

	// --- I1.4: DENSE SAMPLING + SEGMENTED MOTION (added 2026-08-10) ------------
	//
	// WHY THIS EXISTS. The five reductions above answer questions about the
	// series AS A WHOLE: ApexDeltaZ is first-sample-to-global-peak, and
	// RoseThenFell is one bool for the entire run (first -> global peak -> last).
	// Neither can answer "did it rise a SECOND time", which is the whole
	// observable of a double jump. Nor could they at the sampling rate they have
	// ever run at: RecordSample's only caller samples on a 9-point CHECKPOINT
	// schedule, and two jumps inside a couple of seconds alias away completely at
	// that rate.
	//
	// Both halves are therefore needed, and both are OPT-IN:
	//   * dense sampling, default OFF, so every existing fixture keeps its exact
	//     current behaviour and no committed verdict can move;
	//   * segment extraction, which answers shape questions the reductions cannot.
	//
	// HONESTY NOTE: the five reductions above have NEVER EXECUTED (zero callers
	// across both substrates as of 2026-08-10). Treat everything in this block as
	// unproven until a reference run prints DescribeSegments() and a human reads
	// the decomposition. That is why DescribeSegments exists and why the first
	// consumer must log it.

	/** Sample every tick instead of only where a fixture calls RecordSample.
	 *  Call from PrepareTest. DEFAULT OFF - enabling it changes nothing for any
	 *  fixture that does not ask, which is what keeps glide/poison byte-identical. */
	void SetDenseSampling(bool bEnable) { bDenseSampling = bEnable; }

	/** The sample series split into monotonic vertical runs. A run is emitted only
	 *  when it moves at least MinDeltaZ, so sensor noise and a settled pawn do not
	 *  manufacture segments. Direction flips shorter than that are absorbed into
	 *  the run they interrupt. */
	TArray<FCraftBenchMotionSegment> Segments(double MinDeltaZ) const;

	/** How many times the pawn rose by at least MinRiseZ AFTER having stopped
	 *  rising. THE double-jump observable: a single jump is 1, a double jump is 2,
	 *  and a pawn launched once that merely stutters on the way up is still 1
	 *  because sub-MinRiseZ flips are absorbed. */
	int32 NumRises(double MinRiseZ) const;

	/** Mean vertical rate over (FromT, ToT], or 0 when the window holds < 2
	 *  samples. Relative-gate helper: compare two windows of the SAME run. */
	double MeanVerticalRate(double FromT, double ToT) const;

	/** Human-readable decomposition for the diagnostic line. Print this from any
	 *  fixture that gates on segments - it is the only way a wrong decomposition
	 *  is visible instead of silently mis-gating. */
	FString DescribeSegments(double MinDeltaZ) const;

	// --- visible-character gate -----------------------------------------------

	/** True if the graded pawn carries a mesh component that a reviewer watching
	 *  the run would actually SEE: a non-null mesh asset, on a component that is
	 *  visible (not hidden in game) and not scaled to nothing.
	 *
	 *  HOISTED HERE 2026-08-11 because the predicate was copy-pasted into FIVE
	 *  fixtures (double-jump, heal-over-time, health-attribute-ops, poison,
	 *  glide) and every copy asserted only "some mesh component holds some
	 *  non-null asset". None checked that it renders — so `SetHiddenInGame(true)`
	 *  on a correctly-assigned mannequin passed the gate that exists precisely
	 *  BECAUSE 9 of 9 measured glide reps shipped pawns nobody could see. Fixing
	 *  it in one place is the point: five copies is five chances to fix four.
	 *
	 *  DELIBERATELY NOT ASSERTED (owner decision 2026-08-11):
	 *   - the `/Game/Characters/` mannequin pool the prompts name. The capability
	 *     under test is gameplay programming, not asset-path compliance, and a
	 *     visible character mesh from elsewhere serves a reviewer identically.
	 *     Enforcing the path would risk failing reasonable work to enforce a
	 *     detail nobody is being tested on.
	 *   - skeletal-vs-static. A visible static mesh is still visible.
	 *   - a minimum on-screen SIZE. A 1 cm cube technically passes; that is a
	 *     contrived cheat, whereas the meshless pawn is the one actually
	 *     measured in the wild. Adding a bounds floor would be inventing a
	 *     requirement rather than enforcing the stated one.
	 *
	 *  @param OutWhy  filled with the reason on failure, for the named FAIL. */
	bool PawnVisiblyRepresented(FString& OutWhy) const;

	// --- GAS runtime probe ----------------------------------------------------

	/** The pawn's ASC via IAbilitySystemInterface, or nullptr. */
	UAbilitySystemComponent* PawnASC() const;

	/** Number of activatable abilities on the pawn whose asset tags contain Tag.
	 *  0 for an un-granted / non-GAS pawn — the CMC-fake discriminator. */
	int32 NumGrantedAbilitiesWithTag(const FGameplayTag& Tag) const;

	/** TryActivateAbilitiesByTag on the pawn's ASC; true if an ability activated. */
	bool TriggerAbilityByTag(const FGameplayTag& Tag);

	/** Latches true once an ability with Tag has been observed activating. */
	bool bAbilityActivated = false;

	// --- GameplayEffect application (V1.1) ------------------------------------
	//
	// THE LAW FOR EVERY GATE BUILT ON THESE: assert on the VALUE the attribute
	// ends up at, never on "the effect applied" or "the effect count is N".
	// Against one externally-applied drain, an immunity implementation leaves
	// zero active effects, a PreAttributeChange clamp leaves one, and a competing
	// resistance modifier leaves one with a different magnitude — all three are
	// correct answers to the same behavior-only prompt. A count-keyed gate
	// blesses a single recipe and false-FAILs the rest.

	/** Apply a verifier-built effect to the pawn's own ASC and keep it alive for
	 *  the rest of the schedule.
	 *
	 *  FAILS THE TEST BY NAME, before applying anything, when the pawn's ability
	 *  system is not the network authority. GAS silently drops (or merely
	 *  predicts) a non-authority application, so without this check a harness
	 *  condition would present as "the submission's feature worked".
	 *
	 *  Does NOT fail on an invalid returned handle: an INSTANT effect always
	 *  returns one (it executed and was never added to the active container),
	 *  and a submission that legitimately blocked the application returns one
	 *  too. Read the attribute instead. */
	FActiveGameplayEffectHandle ApplyEffectToPawn(UGameplayEffect* Effect, float Level = 1.f);

	/** Remove a previously applied duration/infinite effect by handle. False if
	 *  there is no ASC, the handle is invalid, the ASC is not the authority (GAS
	 *  would log a Warning there, and a Warning inside the test window zeroes the
	 *  WHOLE fixture), or the effect was already gone. */
	bool RemoveEffectFromPawn(FActiveGameplayEffectHandle Handle);

	/** How many ACTIVE effects on the pawn were built from exactly this
	 *  definition object.
	 *
	 *  Matches on Spec.Def POINTER IDENTITY — the same identity GAS's own
	 *  stacking uses — and NOT on class. UAbilitySystemComponent::
	 *  GetGameplayEffectCount compares `SourceGameplayEffect == Spec.Def->GetClass()`,
	 *  and every runtime NewObject<UGameplayEffect> shares the class
	 *  UGameplayEffect, so the class-keyed count would return the SUM of every
	 *  verifier-dynamic effect on the pawn: drain, control and competing modifier
	 *  indistinguishable from one another.
	 *
	 *  Counts ENTRIES, not stacks: a 3-stack effect counts 1. (Stack depth is a
	 *  separate question and is deliberately not answered here — see the .cpp.) */
	int32 PawnEffectCount(const UGameplayEffect* Def) const;

	// --- attribute dual read (V1.4) -------------------------------------------
	//
	// Read BOTH or a clamp gate is vacuous. A PreAttributeChange-only clamp — the
	// most-documented recipe — writes CurrentValue only, so PawnAttribute() reads
	// exactly the cap (say 100) while PawnAttributeBase() sits at 117 and the
	// health system silently absorbs the next 17 damage. Conversely an Override
	// modifier moves only the current value, so a base-only read would false-FAIL
	// a conforming implementation.

	/** Post-aggregator CURRENT value of an attribute on the pawn's ASC. 0.0 when
	 *  there is no ASC or the ASC carries no attribute set exposing it. */
	double PawnAttribute(const FGameplayAttribute& Attribute) const;

	/** BASE value of an attribute on the pawn's ASC (before infinite/duration
	 *  modifiers aggregate). 0.0 under the same conditions as PawnAttribute. */
	double PawnAttributeBase(const FGameplayAttribute& Attribute) const;

	/** True if the pawn's ASC actually carries an attribute set exposing this
	 *  attribute. Both readers above return 0.0 for a missing attribute, which is
	 *  indistinguishable from a real zero — call this first if a gate needs to
	 *  tell "no health system" from "health is 0" and fail by the right name. */
	bool PawnHasAttribute(const FGameplayAttribute& Attribute) const;

	// --- spawn/resolve --------------------------------------------------------

	/** Spawn the resolved agent pawn at PawnSpawnLocation and possess it via
	 *  SpawnDefaultController(). Returns false (and FinishTest(Failed)) on failure. */
	bool SpawnAndPossessPawn();

	/** Resolve the agent's pawn class: a non-abstract C++ subclass of
	 *  ACraftBenchCharacter if present, else a Blueprint subclass found under
	 *  /Game/Tasks/, else the base. When PreferredAbilityTag() is valid, a
	 *  subclass that GRANTS an ability with that tag is preferred — this
	 *  disambiguates when more than one ACraftBenchCharacter subclass is present
	 *  (e.g. another task's committed pawn carrying a different ability tag). */
	TSubclassOf<ACraftBenchCharacter> ResolveAgentPawnClass() const;

	/** A per-task ability tag the resolved pawn is expected to grant. Default is
	 *  invalid (resolve purely by derivation — legacy behavior). A GAS pawn fixture
	 *  overrides this to return its trigger tag so the resolver picks the pawn that
	 *  grants that tagged ability, never a foreign task's pawn. */
	virtual FGameplayTag PreferredAbilityTag() const;

	UPROPERTY()
	TArray<FCraftBenchTrajectorySample> Samples;

	/** I1.4 dense sampling, OPT-IN. Default false so no existing fixture changes. */
	bool bDenseSampling = false;

	/** Every effect definition this fixture has handed to ApplyEffectToPawn.
	 *
	 *  GC ANCHOR, not bookkeeping. The factories in CraftBenchTestEffects.h
	 *  NewObject into the transient package with no other referencer; a
	 *  collection between two checkpoints would take a live periodic effect's
	 *  definition out from under it. A UPROPERTY on the fixture actor (which the
	 *  PIE world roots) is the cheapest correct anchor. */
	UPROPERTY()
	TArray<TObjectPtr<UGameplayEffect>> VerifierEffects;
};
