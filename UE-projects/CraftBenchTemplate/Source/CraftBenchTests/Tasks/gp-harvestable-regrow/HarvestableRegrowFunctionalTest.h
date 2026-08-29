// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHarvestableRegrowFunctionalTest — L2 verifier fixture for task
// gp-harvestable-regrow (the g2-3 "Harvestable" port). Placed in
// L_HarvestableRegrow.umap alongside the HarvestableRoot-tagged host actor.
// PIE-native: the engine ticks the actor, BeginPlay auto-fires on the host
// (initializing it to the active state), and FTimerManager runs — so a timer-,
// timeline-, or tick-based regrow implementation is sampled correctly with no
// manual ticking.
//
// The verifier never injects player input. It induces the "walked into it"
// harvest by spawning a probe actor (with an overlapping collision sphere) AT the
// harvestable's location, which fires the harvestable's begin-overlap event.
//
// Checkpoint contract (seconds since the PIE world began play, fixed-step).
// Rewritten 2026-08-19 to close requirements-table rows 7, 9 and 11; the harvest
// lands at ~0.5s, so the 5-second regrow deadline is ~5.5s:
//   t=0.5s — host is ACTIVE (no "Regrowing" tag). Probe A is then spawned at the
//            host's location to induce harvest #1.
//   t=2.0s — host is REGROWING (tag present). Probe B is then spawned: a SECOND
//            walk-in, DURING the regrow window. A correct host ignores it; a host
//            with no re-entrancy guard re-harvests and restarts its 5s clock,
//            moving its deadline to ~7.0s. (row 7)
//   t=5.0s — host is STILL regrowing (0.5s short of its deadline). Tightens the
//            delay's LOWER bound, which only t=2.0 constrained before. Probes A
//            and B are then destroyed, so nothing is overlapping when the host
//            returns to active — otherwise a host that scans current overlaps
//            each tick would legitimately re-harvest itself the instant it woke,
//            and be failed for it.
//   t=6.0s — host is back ACTIVE (tag gone), 0.5s past its deadline and 1.0s
//            BEFORE the no-guard deadline: this one checkpoint carries both the
//            tightened upper bound and row 7's verdict. Probe C is then spawned
//            to induce harvest #2.
//   t=7.0s — host is REGROWING again: it really can be harvested a second time.
//            (row 11)
//
// The delay is therefore bounded to (4.5s, 5.5s] against a required 5.0s, down
// from (1.5s, 7.0]. Margins at both ends exceed one frame at BOTH declared frame
// rates, which is what makes the fps_legs run below safe rather than lucky.
//
// row 9 ("the 5-second delay must hold regardless of frame rate") is closed by the
// spec's `fps_legs: [60, 20]`, NOT by anything in this file: the whole fixture is
// replayed in a second PIE process at 20 FPS and both legs must pass, so a
// frame-counted regrow tuned for 60 Hz fails the 20 Hz leg.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "HarvestableRegrowFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AHarvestableRegrowFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AHarvestableRegrowFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Spawns a probe actor (with an overlap-enabled collision sphere) at the
	 *  harvestable's location to fire its begin-overlap event (the headless stand-in
	 *  for a player walking into it). Returns false if it could not spawn.
	 *
	 *  Each call spawns a FRESH probe on purpose: begin-overlap fires on the
	 *  transition, so re-using a probe already sitting inside the volume would
	 *  induce no second walk-in at all. */
	bool InduceHarvestOverlap();

	/** Destroys every probe spawned so far. Called before the host is expected to
	 *  return to active, so that "nothing is currently touching me" is true then. */
	void DestroyProbes();

	/** The harvestable host, resolved by tag in PrepareTest (never destroyed by
	 *  this fixture; cached so its tags can be sampled across checkpoints). */
	UPROPERTY()
	AActor* Harvestable = nullptr;

	/** The induced walk-in probes, so they can be cleared before the regrow
	 *  deadline. Weak: a probe destroyed by anything else must read as gone. */
	TArray<TWeakObjectPtr<AActor>> Probes;
};
