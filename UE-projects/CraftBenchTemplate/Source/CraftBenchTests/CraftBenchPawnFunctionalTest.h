// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// ACraftBenchPawnFunctionalTest — base for L2 fixtures that verify a Pawn's
// motion and/or GAS behavior. Sits on top of ACraftBenchFunctionalTest (PIE
// lever, fixed-dt, checkpoint clock) and owns three reusable machines so a
// per-task fixture stays thin (a trigger tag, a checkpoint schedule, asserts):
//
//   1. Pawn-class resolution — find the AGENT's ACraftBenchCharacter subclass
//      (a C++ subclass; Blueprint-asset resolution is a documented extension
//      point) and fall back to the base if the agent provided none. This is
//      identity-by-derivation: the task never dictates a class name.
//   2. Spawn + possess — spawn the resolved pawn and SpawnDefaultController() it.
//      Possession is MANDATORY: the Slice-0 spike proved an unpossessed Character
//      is inert (MOVE_None, no gravity, ignores LaunchCharacter); a possessed one
//      integrates a clean ballistic arc. No input injection.
//   3. Trajectory sampler + GAS runtime probe — record (t, loc, vel, mode) at the
//      checkpoint schedule and expose shape invariants (ApexDeltaZ / RoseThenFell /
//      ReachedMovementMode), plus deterministic ASC introspection (granted ability
//      count by tag, tag-trigger). All plain API — no LLM, FR-020d-clean.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "CraftBenchPawnFunctionalTest.generated.h"

class ACraftBenchCharacter;
class UAbilitySystemComponent;
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

	// --- spawn/resolve --------------------------------------------------------

	/** Spawn the resolved agent pawn at PawnSpawnLocation and possess it via
	 *  SpawnDefaultController(). Returns false (and FinishTest(Failed)) on failure. */
	bool SpawnAndPossessPawn();

	/** Resolve the agent's pawn class: a non-abstract C++ subclass of
	 *  ACraftBenchCharacter if present, else the base. (Blueprint-asset
	 *  resolution under /Game/Tasks/ is the documented extension for BP agents.)
	 *  When PreferredAbilityTag() is valid, a subclass that GRANTS an ability with
	 *  that tag is preferred — this disambiguates when more than one
	 *  ACraftBenchCharacter subclass is present (e.g. another task's committed pawn
	 *  carrying a different ability tag). */
	TSubclassOf<ACraftBenchCharacter> ResolveAgentPawnClass() const;

	/** A per-task ability tag the resolved pawn is expected to grant. Default is
	 *  invalid (resolve purely by derivation — legacy behavior). A GAS pawn fixture
	 *  overrides this to return its trigger tag so the resolver picks the pawn that
	 *  grants that tagged ability, never a foreign task's pawn. */
	virtual FGameplayTag PreferredAbilityTag() const;

	UPROPERTY()
	TArray<FCraftBenchTrajectorySample> Samples;
};
