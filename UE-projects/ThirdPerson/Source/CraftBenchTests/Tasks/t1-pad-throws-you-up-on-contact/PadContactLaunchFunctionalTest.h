// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// APadContactLaunchFunctionalTest — L2 fixture for t1-pad-throws-you-up-on-contact.
// Runs in Content/Maps/t1-pad-throws-you-up-on-contact/L_PadLane.umap.
//
// WHY IT DERIVES ACraftBenchFunctionalTest AND NOT THE PAWN BASE. Do not "fix"
// this. ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn() resolves the graded
// body through ResolveAgentPawnClass(), which GetDerivedClasses() over
// ACraftBenchCharacter recursively and takes the first non-abstract native
// subclass in the loaded module. Every other task's committed pawn is in that
// same module. This task's deliverable is a pad, not a pawn, so it contributes
// no subclass of its own to be preferred — and a foreign task's pawn (a glider,
// a double-jumper) could become the graded body and change the arc. The subject
// here is instead whatever the map's game mode possesses at the PlayerStart,
// read with UGameplayStatics::GetPlayerCharacter(World, 0). The three motion
// reductions needed (rose-then-fell, air-interval extraction, second-rise
// detection) are re-implemented locally over this fixture's own dense series;
// the base's versions are keyed to its own Pawn member.
//
// THE CONTROL TWIN IS SPAWNED LOCALLY, ON PURPOSE. The base class has no API for
// a second subject and adding one belongs to the other machine (see
// the 2026-08-16 ownership note). The owner approved duplicating a local
// spawner per task rather than blocking on that change. Do not go looking for a
// shared helper.
//
// POSSESSION OF THE TWIN IS LOAD-BEARING, not tidiness. An unpossessed ACharacter
// is inert — MOVE_None, no gravity (Slice-0 spike) — so "the twin stayed on the
// ground" measured on an unpossessed twin measures nothing and would pass for any
// pad whatsoever. cp0 FAILs by name if the twin is not MOVE_Walking.
//
// Checkpoint contract (world game-time, -deterministic -FPS=60). Measured
// against the reference, not predicted:
//   0.6  both settled and grounded (x=-700, dz=0), no air interval yet;
//        drive +X, and release it the moment a throw opens
//   2.9  mid-flight: dz=358, peak=412, descending, one interval
//   6.6  throw #1 closed and compliant; then walk OFF the pad and stop clear
//   8.8  subject grounded and clear; walk back toward the pad from whichever
//        side it is on, releasing again on the throw
//   13.2 a second contact event exists and its throw meets the same floors
//
// TWO DRIVE BUGS, BOTH FOUND BY GRADING A CORRECT REFERENCE, BOTH RECORDED SO
// NOBODY PUTS THEM BACK:
//
// 1. The drive must RELEASE on each throw. The first cut kept pushing +X after
//    the launch: the subject landed, walked on to x=2343, ran off the end of the
//    3600 cm floor, and fell — and the off-pad guard correctly reported "thrown
//    while it was not on the pad" against a CORRECT answer. A fixture that keeps
//    holding the key manufactures the violation it is watching for.
//
// 2. The drive may not assume WHICH legal throw shape it is grading. The spec
//    declares two legal: one that carries the subject forward off the pad, and
//    one that is near-vertical and drops it back onto the plate. This reference
//    is the second (measured: it lands at x=-140, 9 cm up on the plate's own top
//    face). The second cut reversed AWAY at cp3 from a pad the subject was still
//    standing on, and marched it off the -1300 edge instead. So cp2 now walks
//    off the pad and stops clear, and cp3 approaches from whichever side the
//    subject actually ended up on. A forward-carrying reference is already clear
//    at cp2 and its walk-off stops on the same condition immediately.
//
// Two guards run EVERY FRAME from cp0 to the end, because a single-instant
// sample cannot catch a cheat that fires between checkpoints:
//   - off-pad guard: an air interval that OPENS while the subject is not on the
//     pad (and did not leave it within the previous 0.25 s) is an uncaused
//     throw. Keyed to CONTACT, never to an interval ordinal.
//   - control guard: the twin leaving its start height by more than 10 cm.
//
// Air-interval duration is measured GROUND-DEPARTURE TO GROUND-CONTACT, not
// last-airborne minus first-airborne. At 60 Hz the latter undercounts a real
// flight by up to one frame, so a genuine 1.000 s flight measures 0.983 s and
// misses the disclosed >= 1.0 s floor — a false FAIL on correct work.
//
// All FAIL text is ASCII-only (the cp1252 log read-back rule).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "PadContactLaunchFunctionalTest.generated.h"

class ACharacter;
class UTextRenderComponent;

/** One dense per-frame sample of a character. Plain struct on purpose: nothing
 *  here is reflected, so it costs UHT nothing. */
struct FPadSample
{
	double T = 0.0;
	double Z = 0.0;
	double VZ = 0.0;
	FVector Loc = FVector::ZeroVector;
	bool bGrounded = false;
};

/** One maximal run of not-grounded samples, bracketed by the grounded samples
 *  either side of it. */
struct FPadAirInterval
{
	/** Last grounded time before the interval; -1 if the run began airborne. */
	double DepartT = -1.0;
	/** First grounded time after the interval; -1 while still airborne. */
	double ContactT = -1.0;
	double PeakZ = -TNumericLimits<double>::Max();
	/** Was the subject on the pad at the sample the interval opened on. This is
	 *  what makes an interval a "contact event" rather than an uncaused throw. */
	bool bOnPadAtOpen = false;
	/** Monotone upward runs of more than 50 cm inside the interval. */
	int32 RiseCount = 0;
	bool bClosed = false;
};

UCLASS()
class CRAFTBENCHTESTS_API APadContactLaunchFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	APadContactLaunchFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool GuardSubjects(int32 CheckpointIndex);
	bool IsOnPad(const FVector& Loc) const;
	void RecordSample(double T);
	void UpdateReadouts();

	/** The air intervals of the SUBJECT, in the order they opened. */
	TArray<FPadAirInterval> Intervals;

	/** Evaluate one closed interval against the four disclosed floors. Returns
	 *  false after raising the named FAIL. */
	bool JudgeThrow(const FPadAirInterval& Interval, int32 CheckpointIndex,
	                const TCHAR* WhichThrow);

	TWeakObjectPtr<ACharacter> Subject;
	TWeakObjectPtr<ACharacter> Twin;
	TWeakObjectPtr<AActor> Pad;

	TObjectPtr<UTextRenderComponent> SubjectReadout;
	TObjectPtr<UTextRenderComponent> TwinReadout;

	TArray<FPadSample> Series;

	double SubjectBaseZ = 0.0;
	double TwinBaseZ = 0.0;
	double PadHalfXY = 200.0;
	FVector PadCentre = FVector::ZeroVector;

	/** World time the subject was last inside the pad region. */
	double LastOnPadT = -1000.0;

	FVector DriveDir = FVector::ZeroVector;
	bool bDriving = false;
	/** Release the drive as soon as the air-interval count passes this. A player
	 *  who gets launched stops pushing forward; a fixture that keeps pushing
	 *  walks the subject off the end of the floor and then blames the pad for
	 *  the fall. Measured: it reached X=2343 and the off-pad guard fired on a
	 *  CORRECT reference. */
	int32 ReleaseDriveAboveIntervals = -1;
	/** Drive until the subject is clear of the pad, then release. Used to walk
	 *  OFF the pad before walking back onto it, because a throw that keeps the
	 *  subject over the pad lands it right back on the plate. */
	bool bDriveUntilClearOfPad = false;
	bool bGuardsArmed = false;
};
