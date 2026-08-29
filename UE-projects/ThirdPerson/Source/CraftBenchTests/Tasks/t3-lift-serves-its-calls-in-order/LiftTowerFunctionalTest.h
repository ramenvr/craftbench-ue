// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-lift-serves-its-calls-in-order.
//
// A three-landing tower with one lift. The fixture STAGES the shaft (landing 2 is put at
// a height that exists nowhere the submission can read, and is MOVED again between the
// two legs), walks the character through both legs pressing seven pads, and grades what
// the lift does about it.
//
// FOUR THINGS THIS FIXTURE DOES DIFFERENTLY FROM THE REST OF THE REPO, ALL DELIBERATE:
//
//  1. PRESSES ARE THE FIXTURE'S OWN OBSERVATION, and arrival IS the press. A waypoint
//     that is a pad is "reached" when the character's capsule centre is inside that
//     pad's own world footprint (shrunk 15 uu so he is solidly on it), which is the same
//     test that records the press. The submission's bookkeeping is never consulted, and
//     a 70 uu arrival radius can no longer satisfy a waypoint from off the pad.
//
//  2. NOTHING THE SUBMISSION CAUSES ROUTES TO HARNESS-PRECONDITION. Only facts the
//     FIXTURE stages do: how many actors are tagged, the floor numbers, the two staged
//     floor-2 heights being far enough apart and not evenly spaced, the car and the
//     character being clear of landing 2 when it moves, and the walk not crossing a pad
//     it is not aimed at. A missed press window, a door that never opens, a door that
//     never shuts, a lift that stops short -- all of those are NAMED GRADED FAILS, so a
//     submission can never leave the denominator by failing.
//
//  3. THE SERVICE ORDER IS CHECKED AS A PREFIX, LIVE. The moment the doors reach fully
//     open at a floor the collective answer does not call for, the run ends at
//     TheLiftServesWhatIsOnTheWayBeforeItTurnsAround. Waiting until the end would have
//     let a press-order lift park itself somewhere the drive could not continue from and
//     die at a waiting deadline instead -- a wrong-reason FAIL for the single most
//     important discriminator in the task.
//
//  4. THE SIGN'S DIRECTION TRUTH IS READ OFF WHAT THE LIFT ACTUALLY DID NEXT, not off a
//     second implementation of the scheduler living in the fixture. For a frame at time
//     T the truth is: nothing outstanding (excluding the floor the car is standing at)
//     => no arrow; otherwise the direction of the next door-opening after T at a floor
//     more than 12 uu from where the car was at T. That cannot disagree with a correct
//     lift, because it IS the lift's own next stop -- and it still catches an arrow
//     driven from velocity, which reads "none" while the car stands at landing 1 with
//     landing 3 outstanding. It needs the future, so it is evaluated once at the end.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "LiftTowerFunctionalTest.generated.h"

class ACharacter;
class UPointLightComponent;
class UPrimitiveComponent;
class UTextRenderComponent;
struct FActorsInitializedParams;

/** What a drive step is waiting for. Plain C++ on purpose: nothing reflects on it, and
 *  a UENUM here would only give UHT something else to be strict about. */
enum class ELiftStepKind : uint8
{
	/** Walk to a point and stand there for a dwell. */
	GoTo,
	/** Walk onto a pad and stand there for a dwell. Arrival IS the press. */
	GoToPad,
	/** Stand still until the doors read fully open. */
	WaitDoorsOpen,
	/** Stand still until the doors leave fully open. */
	WaitDoorsClosing,
	/** Stand still until the car sill has dropped below a staged height. */
	WaitCarBelow,
	/** Stand still until N door-openings have happened and the car is level here. */
	WaitOpenings,
	/** The drive is over. */
	Done
};

/** Where a press has to land for the collective answer to be the one the fixture
 *  expects. Every one of these can only be missed by a lift that has already broken a
 *  sentence of the prompt -- see the spec's requirement map. */
enum class ELiftPressWindow : uint8
{
	None,
	/** The doors must still be on their way shut: 0.10 < fraction < 1.0. */
	DoorsMidClose,
	/** The car sill must still be below landing 2, by at least 100 uu. */
	BelowFloorTwo,
	/** The car must still be high in the shaft: above halfway between landings 3 and 2
	 *  by 200 uu, and already 40 uu below landing 3. */
	HighInShaft,
	/** The car sill must still be above landing 2, by at least 100 uu. */
	AboveFloorTwo
};

UCLASS()
class ALiftTowerFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ALiftTowerFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ------------------------------------------------------------------ staged world

	struct FLandingRef
	{
		TWeakObjectPtr<AActor> Actor;
		int32 Floor = 0;
		TWeakObjectPtr<UPrimitiveComponent> Deck;
		TWeakObjectPtr<UPrimitiveComponent> CallPad;
		TWeakObjectPtr<UPointLightComponent> CallLamp;
		TWeakObjectPtr<UTextRenderComponent> Readout;
		TWeakObjectPtr<USceneComponent> Arrow;
		/** Where the tower put this landing for the leg in progress. */
		FVector StagedAt = FVector::ZeroVector;
		float StagedSill = 0.0f;
	};

	struct FCarRef
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<UPrimitiveComponent> Platform;
		TWeakObjectPtr<UPrimitiveComponent> LeafLeft;
		TWeakObjectPtr<UPrimitiveComponent> LeafRight;
		TWeakObjectPtr<UPrimitiveComponent> Pads[3];
		TWeakObjectPtr<UPointLightComponent> Lamps[3];
		/** The five numbers, read BEFORE any BeginPlay could rewrite them. */
		float Speed = 0.0f;
		float DoorTravel = 0.0f;
		float DoorHold = 0.0f;
		float ShutSep = 0.0f;
		float OpenSep = 0.0f;
		/** The shaft is vertical; X and Y are the tower's, not the submission's. */
		double StagedX = 0.0;
		double StagedY = 0.0;
	};

	/** One pad press, as the fixture saw it happen. */
	struct FPress
	{
		int32 Floor = 0;
		/** true = an in-car pad, false = that landing's call pad. Only the lamp of the
		 *  pad that was ACTUALLY pressed is graded. */
		bool bInCar = false;
		double At = 0.0;
		double ServedAt = -1.0;

		// ---- DIAGNOSTIC ONLY. Nothing below here is read by any pass/fail condition;
		// they exist so that a clause-B failure says WHICH of the two very different
		// defects it is -- a lamp that never went out, or a lamp that went out and was
		// lit again -- instead of leaving that to be reconstructed by hand.
		/** First time the lamp was seen dark at or after ServedAt (-1 = never yet). */
		double DarkAt = -1.0;
		/** First time it was seen lit again after DarkAt (-1 = it stayed out). */
		double RelitAt = -1.0;
	};

	/** One door-opening: the frame the fraction first reached fully open. */
	struct FOpening
	{
		int32 Floor = 0;
		double At = 0.0;
		float CarSill = 0.0f;
		float LandingSill = 0.0f;
	};

	/** One frame of what the three signs were showing. The direction TRUTH needs the
	 *  future, so the whole trace is kept and judged once at the end. */
	struct FSignFrame
	{
		double T = 0.0;
		float CarSill = 0.0f;
		int32 NearestFloor = 0;
		bool bNearestAmbiguous = false;
		bool bAnythingOutstanding = false;
		/** Per landing: the first whole number in its readout (0 = none), and the arrow
		 *  as +1 up / -1 down / 0 hidden / 2 visible but pointing at neither. */
		int32 Shown[3] = { 0, 0, 0 };
		int32 Dir[3] = { 0, 0, 0 };
	};

	/** One step of the drive. */
	struct FStep
	{
		ELiftStepKind Kind = ELiftStepKind::GoTo;
		/** INDEX_NONE = the car's frame; otherwise the index into Landings. */
		int32 Frame = INDEX_NONE;
		/** GoTo: the target in that frame's local XY. */
		FVector2D Local = FVector2D::ZeroVector;
		/** GoToPad: 0 = that landing's call pad; 1..3 = the in-car pad for that floor. */
		int32 PadFloor = 0;
		double Dwell = 0.0;
		double Budget = 0.0;
		ELiftPressWindow Window = ELiftPressWindow::None;
		/** WaitCarBelow: how far below the reference landing's sill. */
		double Amount = 0.0;
		/** WaitOpenings: how many openings, and the landing the car must be level with. */
		int32 Count = 0;
	};

	// --------------------------------------------------------------------- lifecycle

	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	bool ResolveAndStage();
	bool ResolveCar(AActor* Actor, FString& OutWhy);
	bool ResolveLanding(AActor* Actor, FLandingRef& Out, FString& OutWhy);
	void BuildSteps();
	bool ValidateRoute();

	// ------------------------------------------------------------------- measurements

	float CarSill() const;
	float DoorFraction() const;
	float LandingSill(int32 Index) const;
	int32 NearestLandingIndex(float Sill, float& OutBest, float& OutSecond) const;
	int32 IndexOfFloor(int32 Floor) const;
	FVector2D StepWorldTarget(const FStep& Step) const;
	FBox PadWorldBox(int32 Frame, int32 PadFloor) const;
	bool HeroOnPad(const FBox& Box, double Shrink) const;
	bool LampLit(const UPointLightComponent* Lamp) const;
	static int32 FirstIntegerIn(const FString& Text);

	// ------------------------------------------------------------------------- gates

	void CheckSuppliedMachinery(double Now);
	void CheckPinnedNumbers(double Now);
	void CheckNothingWasMoved(double Now);
	void CheckDoorsAndMotion(double Now);
	void CheckRiderAndProgress(double Now);
	void SamplePresses(double Now);
	void CheckLatchedLamps(double Now);
	void SampleSigns(double Now);
	void EvaluateDeferredGates(double Now);

	// ------------------------------------------------------------------------- drive

	void AdvanceDrive(double Now);
	void DriveHeroTo(const FVector2D& Target);
	void FailWaitDeadline(const FStep& Step, double Now);
	bool PressWindowHolds(ELiftPressWindow Window, FString& OutWhy) const;
	void RestageForLegTwo(double Now);
	void LogCalib(int32 Index, double Now) const;

	// -------------------------------------------------------------------------- state

	TWeakObjectPtr<ACharacter> Hero;
	FCarRef Car;
	TArray<FLandingRef> Landings;

	FDelegateHandle WorldInitHandle;
	bool bStaged = false;
	FString StagingFault;

	/** The two heights landing 2 is staged to, derived from the shaft the map ships. */
	float StagedSillTwoLegOne = 0.0f;
	float StagedSillTwoLegTwo = 0.0f;
	bool bRestaged = false;

	/** How many of the pre-schedule calib lines have been printed. Diagnostic only --
	 *  the checkpoint schedule and its indices are untouched by it. */
	int32 NextEarlyCalib = 0;

	TArray<FStep> Steps;
	int32 StepIndex = 0;
	double StepStartedAt = -1.0;
	double DwellUntil = -1.0;
	bool bDriveComplete = false;
	double DriveCompletedAt = -1.0;

	TArray<FPress> Presses;
	TArray<FOpening> Openings;
	TArray<FSignFrame> SignTrace;
	/** Rising-edge memory, 0..2 = the in-car pads, 3..5 = the landings' call pads. */
	bool bPadOccupied[6] = { false, false, false, false, false, false };

	// per-frame carry-over
	bool bHavePrevFrame = false;
	double PrevTime = 0.0;
	float PrevSill = 0.0f;
	float PrevFraction = 0.0f;

	// travel segments
	bool bSegmentOpen = false;
	double SegmentStartT = 0.0;
	double SegmentLastMoveT = 0.0;
	double SegmentPathUu = 0.0;
	int32 SegmentIndex = 0;

	// door hold
	double FullyOpenSince = -1.0;

	// the stop dwell -- the car must STAND level with the landing it opened at.
	// INDEX_NONE = no stop is being measured right now.
	int32 DwellLandingIndex = INDEX_NONE;
	int32 DwellFloor = 0;
	double DwellStartedAt = -1.0;

	// progress watchdog
	bool bProgressArmed = false;
	double ProgressArmedAt = 0.0;
	float ProgressArmedSill = 0.0f;
};
