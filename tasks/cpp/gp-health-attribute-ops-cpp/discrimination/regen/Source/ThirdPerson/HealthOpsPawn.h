// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `regen/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-6 (PIN.md section 3): "a passive regeneration loop that
// makes the heal look like it worked."
//
// THE ONE DELTA: the reference PLUS the textbook passive Health regeneration
// loop driven from Tick ("while Health is below its maximum, creep back up").
// Stage 1, both abilities, both instant effects and the mesh are the reference
// verbatim. The `Health < MaxHealth` guard is what keeps the drift out of the
// stage-1 ladder -- see the long note in the .cpp; without it the variant dies
// at HO-3 instead, because the checkpoint clock is absolute world time and the
// pawn is spawned ~0.5s before checkpoint 0.
//
// EXPECTED: FAIL at the final checkpoint -- but at **HO-10, NOT HO-11**, on the
// named substring
//   "heal does not restore what damage removes: one damage removed"
// UNVALIDATED / NOT YET RUN.
//
// READ THIS BEFORE CHANGING THE RATE. HO-11's idle window CANNOT be reached by
// any constant-rate passive drift at the reference's per-application magnitude.
// A drift of R Health/s contributes R*W to every one of the four 0.7s windows,
// so with magnitude M = 10:
//   * it SHRINKS drop1 and drop2 equally (HO-9's ratio stays 1.00 -- untouched),
//   * it GROWS healDelta by the same amount it shrank drop1 by, so HO-10's ratio
//     is (M + R*W)/(M - R*W) and passes only while R <= M/(21*W) = 0.68 Health/s,
//   * it moves Health by R*W in the idle window, so HO-11 fires only once
//     R > DeltaEpsilon/W = 0.71 Health/s.
// Those two conditions do not overlap: 0.68 < 0.71. HO-10 is checked first, so
// every rate that trips HO-11 has already tripped HO-10. Pushing R higher only
// moves the verdict further away -- R > 7.14 trips HO-8 (drop1 falls out of the
// 5-25 band) and R > 13.6 trips HO-7 (drop1 goes negative). There is no rate
// that lands on HO-11. The general condition for one to exist is
// M > DeltaEpsilon * 21 / 1 = 10.5, i.e. the reference magnitude would have to
// exceed 10.5 -- see MATRIX.md "HO-11 IS NOT REACHABLE", which records this as a
// PIN calibration finding and the recommended fix (decouple the idle window
// length from the gated window length).
//
// The rate below is therefore chosen to make the variant land on HO-10 with the
// LARGEST margins on every neighbouring bar, not to chase HO-11.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "HealthOpsPawn.generated.h"

class UCraftBenchAttributeSet;

UCLASS()
class AHealthOpsPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	AHealthOpsPawn();

	/** THE DELTA. The reference does not override Tick at all. */
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;

	/** Passive regeneration, Health per second. PROPOSED - NOT YET MEASURED.
	 *
	 *  2.0 contributes 1.4 Health to each 0.7s window. Predicted leg with the
	 *  reference's magnitude 10 and preset 60:
	 *    H0 60.0 -> H1 51.4 -> H2 42.8 -> H3 54.2 -> H4 55.6
	 *    drop1 8.6, drop2 8.6  -> HO-9 ratio 1.00      (passes, dead centre)
	 *    drop1 8.6             -> HO-8 in [5, 25]      (passes, 3.6 of margin
	 *                                                   to the nearer edge)
	 *    healDelta 11.4        -> HO-10 ratio 1.326    (FAILS, 0.23 past 1.10)
	 *    idleDelta 1.4         -> HO-11 would fire too, but is never reached.
	 *  Every neighbouring bar is cleared by a wide margin and only HO-10 fires,
	 *  which is what makes the verdict attributable. */
	static constexpr float HealthOpsRegenRate = 2.0f;
};
