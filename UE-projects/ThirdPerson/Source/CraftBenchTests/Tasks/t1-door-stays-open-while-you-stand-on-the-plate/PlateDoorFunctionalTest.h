// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// APlateDoorFunctionalTest — L2 fixture for
// t1-door-stays-open-while-you-stand-on-the-plate. Runs in
// Content/Maps/t1-door-stays-open-while-you-stand-on-the-plate/L_PlateDoorLane.umap.
//
// THE PANEL IS ONE COMPONENT, NOT THE MAX OVER ALL OF THEM. This is the whole
// soundness of the task, so do not "simplify" it. The agent owns
// SwingDoorActor.{h,cpp}. Under a max-over-static-meshes rule it could add a
// decorative component, rotate THAT smoothly 90 degrees and back, and satisfy
// every angle gate and the continuity guard while the panel a human watches
// never moves — a PASS that looks like a broken door on screen. So the graded
// part is resolved ONCE, in PrepareTest: the component named "DoorPanel" if
// present, else the largest local bounding-box volume, ties broken by name
// ascending. That is the same prefer-the-declared-thing-then-a-deterministic-
// rule idiom ResolveAgentPawnClass already uses, and it never falls back to
// enumeration order.
//
// AND THE PANEL HAS TO TRAVEL, not just turn. A panel spun about its own centre
// reads as 90 degrees of yaw while staying exactly where it was. Travel() is the
// distance from the recorded closed world location, and the hinge offset means a
// real swing carries it well over a metre.
//
// THE CONTINUITY GUARD MUST SEED FROM THE PREVIOUS SAMPLE, never from a
// default-constructed baseline. Zero-initialised LastLoc would make frame 1 read
// |Loc - LastLoc| = |(300, +/-150)| = 335 cm, which is over the 3000*dt budget at
// any framerate (50 cm at 60 fps, 150 cm at 20 fps) and would FAIL every
// submission including the reference, on the first frame, for a reason that has
// nothing to do with the door. On the first tick the guard records and returns.
//
// ONE LITERAL PER CHECKPOINT, index-suffixed. "The control broke while the graded
// door was open" and "the control was already broken at play start" have to be
// different strings, or a MATRIX row cannot tell which cycle failed.
//
// Checkpoint schedule (world game-time): 0.8 precondition · 4.8 open (cycle 1)
// · 6.4 still open · 9.4 shut again · 13.1 open (cycle 2) · 14.7 still open
// · 17.7 shut again -> PASS.
//
// All FAIL text is ASCII-only (the cp1252 log read-back rule).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "PlateDoorFunctionalTest.generated.h"

class ACharacter;
class UStaticMeshComponent;

/** What the fixture watches on one door. */
struct FDoorProbe
{
	TWeakObjectPtr<AActor> Actor;
	/** The graded part: named "DoorPanel", else largest by local bounds. */
	TWeakObjectPtr<UStaticMeshComponent> Panel;
	FRotator ClosedRot = FRotator::ZeroRotator;
	FVector ClosedLoc = FVector::ZeroVector;
	/** Previous SAMPLE, for the continuity guard. Never default-constructed. */
	double LastAngle = 0.0;
	FVector LastLoc = FVector::ZeroVector;
	bool bSeeded = false;
};

UENUM()
enum class EPlateDoorPhase : uint8
{
	Settle,
	Approach1,
	Stand1,
	Depart1,
	Approach2,
	Stand2,
	Depart2,
	Done,
};

UCLASS()
class CRAFTBENCHTESTS_API APlateDoorFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	APlateDoorFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/**
	 *  Empty when a human could pick up a controller and drive this level;
	 *  otherwise the reason they cannot. Nothing in the graded drive depends on
	 *  the keyboard lane, so without this the level is free to ship unplayable.
	 */
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	/** Named-then-largest, never enumeration order. */
	UStaticMeshComponent* ResolvePanel(AActor* Door) const;
	bool InitProbe(FDoorProbe& Probe, AActor* Door, const TCHAR* Which);

	double Angle(const FDoorProbe& Probe) const;
	double Travel(const FDoorProbe& Probe) const;
	double HeroDist2D(const AActor* Plate) const;
	bool OnPlate(const AActor* Plate) const;

	/** Runs at every checkpoint. Returns false after raising the named FAIL. */
	bool GaugeControl(int32 CheckpointIndex);

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> GradedPlate;
	TWeakObjectPtr<AActor> ControlPlate;
	FDoorProbe Graded;
	FDoorProbe Control;

	/** The open angle reached in cycle 1, so cycle 2 can be held to it. */
	double Open1 = 0.0;

	/** World time the hero first stood on the graded plate this cycle, and the
	 *  time the door first reached the open band after that. The DISCLOSED 2 s
	 *  deadline is measured between them.
	 *
	 *  This exists because it was MISSING and nothing noticed. cp1 samples at a
	 *  fixed t=4.80, which happens to be ~2.3 s after the hero arrives, so the
	 *  effective deadline was an accident of checkpoint spacing rather than the
	 *  2 s the prompt states. Measured 2026-08-17: the `frame-coupled` variant
	 *  takes 2.25 s to open at 20 Hz -- a real violation -- and PASSED. */
	double PlateEnteredT = -1.0;
	double ReachedOpenT = -1.0;

	EPlateDoorPhase Phase = EPlateDoorPhase::Settle;
};
