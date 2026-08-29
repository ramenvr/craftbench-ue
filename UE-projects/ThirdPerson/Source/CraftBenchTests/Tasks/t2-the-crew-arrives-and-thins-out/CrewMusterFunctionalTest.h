// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t2-the-crew-arrives-and-thins-out.
//
// A muster deck with two identical boards, only one of which is ever stepped on. The
// fixture runs the whole rule itself -- the same edge-triggered call, the same paced
// fill, the same lowest-free seating, the same first-unspent-code issue with a
// whole-run ledger, the same arrival-place removal -- against the boards' LIVE chalk,
// and grades the deck's VISIBLE state against it: which actors tagged CrewHand exist,
// where they stand, what their badges say, and which of the boards' point lights are
// burning. It never reads a single one of the submission's own variables.
//
// THREE THINGS DECIDE THE SHAPE OF THIS FILE.
//
//   1. THE ARRIVAL-ORDER-TO-SPOT MAP IS OBSERVED, NEVER ASSUMED. If the fixture
//      derived the expected stand-down from who it thinks SHOULD have arrived where,
//      a submission with a wrong seating rule would fail the removal gate as well and
//      the two subsystems would be indistinguishable in the verdict. Deriving the
//      expected cleared spots from the order the fixture actually WATCHED makes
//      TheRightHandsAreLeftStanding a statement about the removal rule alone.
//
//   2. THE CHALK IS RE-STAMPED TWICE. PrepareTest writes a pinned schedule over both
//      boards before the character has walked anywhere -- the committed .umap holds
//      DIFFERENT numbers on purpose -- and phase 7 re-stamps all eight values again.
//      So a value cached in BeginPlay (which fires before PrepareTest) is wrong from
//      the FIRST call, not the second, and a value cached at the first call is wrong
//      at the second.
//
//   3. NOTHING IS JUDGED NEAR AN EVENT. Every assertion is skipped within 0.75 s of a
//      change in the fixture's own model, within 0.75 s of any plate contact or
//      release, inside a guard band of max(0.75 s, 0.30 x gap) either side of an
//      expected arrival, and while the fixture is itself re-staging the deck. Every
//      one of those is a WIDENING of the half second the prompt promises, never a
//      narrowing. PrepareTest refuses to start below a 2.0 s staged gap, which is
//      what keeps the judged plateau between two bands at least half a second wide --
//      ten frames on the 20 Hz leg.
//
// Identity is by TAG and by PROPERTY NAME throughout; this file includes nothing from
// the agent-writable module, so a renamed or subclassed board still answers and a
// submission cannot break the fixture's compile.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "CrewMusterFunctionalTest.generated.h"

class ACharacter;
class UBoxComponent;

UCLASS()
class ACrewMusterFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACrewMusterFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ------------------------------------------------------------------ the deck

	/** The four numbers a board carries. Read live, every frame, by name. */
	struct FChalk
	{
		int32 Call = 0;
		double Gap = 0.0;
		TArray<int32> Roster;
		TArray<int32> Slate;
	};

	struct FBoard
	{
		TWeakObjectPtr<AActor> Actor;
		FName Tag = NAME_None;
		FVector StagedAt = FVector::ZeroVector;
		/** What the fixture stamped for the watch in progress. */
		FChalk Staged;
		/** What the committed .umap held before the fixture touched it. Kept only so
		 *  the disjointness precondition can prove a badge code names its source. */
		FChalk Baked;
		/** This board's standing-spot numbers, ascending. */
		TArray<int32> Spots;
	};

	struct FBerth
	{
		TWeakObjectPtr<AActor> Actor;
		FName BoardTag = NAME_None;
		int32 SpotNumber = 0;
		FVector StagedAt = FVector::ZeroVector;
	};

	struct FPlate
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<UBoxComponent> Volume;
		FName BoardTag = NAME_None;
		bool bIsCall = true;
		FVector StagedAt = FVector::ZeroVector;
		/** Whether the fixture saw the character inside this plate's own region on the
		 *  previous frame -- its OWN observation, never the plate's report. */
		bool bHeroInside = false;
	};

	struct FHand
	{
		TWeakObjectPtr<AActor> Actor;
		/** Whose board's standing spot it is on. NAME_None when it is on none. */
		FName BoardTag = NAME_None;
		int32 SpotNumber = 0;
		FVector FirstAt = FVector::ZeroVector;
		double FirstSeenAt = 0.0;
		/** Locked in on the first judged frame at which the badge reads non-zero. */
		int32 IssuedCode = 0;
		/** True once this hand's code has been entered in the night's issue ledger.
		 *  Per-hand, not per-code: that is what turns a re-issue into a FAIL rather
		 *  than a silent no-op. */
		bool bLedgered = false;
		/** Its place in the arrival order of the call that was running when it turned
		 *  up; 0 when no call was running, which is a failure in itself. */
		int32 ArrivalPlace = 0;
		/** Whether this actor still answers to the CrewHand tag. A hand that has
		 *  stopped answering but is still standing in the world has NOT been sent
		 *  ashore, so it stays tracked -- see ObserveDeck. */
		bool bAnswersTag = true;
	};

	// -------------------------------------------------------------- reflection

	int32 ReadInt(const AActor* A, const TCHAR* Name, bool& bOk) const;
	float ReadFloat(const AActor* A, const TCHAR* Name, bool& bOk) const;
	FName ReadName(const AActor* A, const TCHAR* Name, bool& bOk) const;
	bool ReadBool(const AActor* A, const TCHAR* Name, bool& bOk) const;
	bool ReadIntArray(const AActor* A, const TCHAR* Name, TArray<int32>& Out) const;
	bool WriteInt(AActor* A, const TCHAR* Name, int32 Value) const;
	bool WriteFloat(AActor* A, const TCHAR* Name, float Value) const;
	bool WriteIntArray(AActor* A, const TCHAR* Name, const TArray<int32>& Values) const;

	/** All four chalked values off one board, live. False when any is unreadable. */
	bool ReadChalk(const AActor* A, FChalk& Out) const;
	/** Stamps all four onto one board. False when any write fails. */
	bool StampChalk(AActor* A, const FChalk& In) const;

	// ------------------------------------------------------ reading the world

	/** The number on a hand's badge -- off the thing on screen, never off a field. */
	int32 BadgeCodeOf(const AActor* Hand) const;
	/** Locks in each newly-arrived hand's badge code. Judged frames only. */
	void LockInBadges(double Now);
	/** Is the lamp for standing spot k on this board burning? Read from the light's
	 *  own intensity. bOutFound is false when the board has no such lamp at all. */
	bool LampLit(const AActor* Board, int32 Spot, bool& bOutFound) const;
	/** The standing spot a point is on, or 0. Fills OutBoardTag with whose it is. */
	int32 SpotAt(const FVector& Where, FName& OutBoardTag) const;
	/** Is the character inside this plate's own region, by the fixture's arithmetic? */
	bool HeroOnPlate(const FPlate& P) const;
	/** The live occupied standing spots on one board, ascending, de-duplicated. */
	TArray<int32> ObservedOccupied(FName BoardTag) const;
	/** How many living hands stand on one board's spots (duplicates counted). */
	int32 ObservedHandCount(FName BoardTag) const;

	// -------------------------------------------------------------- the model

	/** How many of the running call's hands should be aboard by now. */
	int32 ExpectedAboard(double Now) const;
	/** The spots that should be occupied on the working board after N arrivals of the
	 *  running call: whoever was held over, plus the N lowest-numbered spots that were
	 *  free when the plate was stepped on. */
	TArray<int32> ExpectedOccupiedAfter(int32 N) const;
	/** The guard band around each expected arrival of the running call. */
	double GuardBand() const;

	// -------------------------------------------------------------- the gates

	/** True on a frame no gate may judge. Every clause is a widening. */
	bool Suppressed(double Now) const;

	bool GateNotRearranged(double Now);
	bool GateQuietBoard(double Now);
	bool GateNobodyUncalled(double Now);
	bool GateCadence(double Now);
	bool GateFill(double Now);
	bool GateStandDown(double Now);
	bool GateNoShuffle(double Now);
	bool GateBadges(double Now);
	bool GateLamps(double Now);

	// -------------------------------------------------------------- the drive

	bool ResolveStaging();
	/** Fills PortWatch[]/TwinWatch[] with the pinned schedule. */
	void BuildSchedule();
	bool ValidateSchedule();
	bool ValidateGeometry();
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	void StageWatch(int32 InWatchIndex, double Now);
	void ObserveDeck(double Now);
	void ObservePlates(double Now);
	void BeginCall(double Now);
	void DoStandDown(double Now);

	void BeginPhase(int32 NewPhase, double Now);
	void SteerPhase(double Now);
	void DriveHero(double Now);
	void AdvancePhases(double Now);
	bool FinishRunLevel(double Now, const TCHAR* Where);
	void LogCalib(int32 Index, double Now) const;

	static FString DescribeSpots(const TArray<int32>& Spots);
	FString DescribeArrivalMap() const;
	FString DescribeBadges() const;
	/** The codes of the working board's live roster already spent tonight, in written
	 *  order, and the first one that has not been. */
	int32 FirstUnspentRosterCode(TArray<int32>& OutSpent) const;
	/** A sentence appended to an occupancy gate's message when one or more tracked
	 *  hands have stopped answering to the CrewHand tag while still standing on the
	 *  deck -- otherwise the message reads as if the fixture had lost track of them. */
	FString UntaggedNote() const;

	// ------------------------------------------------------------------ state

	TWeakObjectPtr<ACharacter> Hero;
	double CapsuleRadius = 42.0;
	double CapsuleHalfHeight = 96.0;
	double HeroSpeed = 500.0;

	FBoard Working;
	FBoard Twin;
	TArray<FBerth> Berths;
	TArray<FPlate> Plates;

	/** THE PINNED SCHEDULE, [watch]. The committed .umap deliberately holds different
	 *  numbers, and all eight of these are stamped over it before the character has
	 *  walked anywhere, then stamped again at the watch change. */
	FChalk PortWatch[2];
	FChalk TwinWatch[2];
	int32 WatchIndex = 0;

	/** Every hand the fixture can currently see, and the whole night's issue ledger. */
	TArray<FHand> Live;
	/** How many of Live stopped answering to the CrewHand tag on the last observation
	 *  while still existing. Never a gate of its own: it only makes the occupancy
	 *  gates' messages honest about why a spot still reads as held. */
	int32 UntaggedStillAboard = 0;
	TSet<int32> IssuedEver;
	/** code -> the spot the hand that first wore it stood on, for the ledger message. */
	TMap<int32, int32> IssuedOnSpot;

	/** The call in progress. bCallActive stays true from the call plate's contact
	 *  until the next stand-down contact -- that is the whole "fill window". */
	bool bCallActive = false;
	double CallContactAt = -1000.0;
	double CallGap = 0.0;
	int32 CallSize = 0;
	TArray<int32> HeldOverSpots;   // ascending
	TArray<int32> FreeAtCall;      // ascending
	/** The observed arrival order of the watch just called: place k is Arrivals[k-1],
	 *  a standing-spot number. Reset at every call. */
	TArray<int32> Arrivals;
	int32 LastExpectedAboard = 0;

	/** The last stand-down, captured at its contact instant. */
	TArray<int32> StandDownSlate;
	TArray<int32> StandDownArrivals;
	TArray<int32> ExpectedClearedSpots;
	TArray<int32> ExpectedAfterStandDown;
	TArray<int32> OccupiedBeforeStandDown;
	bool bStandDownArmed = false;
	double StandDownAt = -1000.0;

	/** Bookkeeping for the run-level gate. */
	int32 FillsCompleted = 0;
	int32 ThinningsSeen = 0;
	int32 CallsMade = 0;
	bool bFillCounted = false;
	bool bStandDownCounted = false;
	/** Judged frames per [round 0/1] x [inside the fill window / after the stand-down].
	 *  A zero here is the DRIVE's fault and never the submission's: it means a whole
	 *  window went ungraded and the run proved less than it claims. */
	int32 JudgedFrames[4] = {0, 0, 0, 0};

	/** Clocks. */
	double LastModelChangeAt = -1000.0;
	double LastPlateEventAt = -1000.0;
	double StagingUntil = -1.0;
	int32 LastJudgedHandCount = 0;
	bool bHaveJudgedHandCount = false;

	/** The drive. */
	int32 Phase = 0;
	int32 Phase3Sub = -1;
	double PhaseStartedAt = 0.0;
	double PhaseDeadline = 0.0;
	double ArrivedAt = -1.0;
	double PlateContactAt = -1.0;
	bool bPlateContactSeen = false;
	TArray<FVector> Waypoints;
	int32 WaypointIndex = 0;

	FVector QuietSpot = FVector::ZeroVector;
	FVector CallPlateAt = FVector::ZeroVector;
	FVector StandDownPlateAt = FVector::ZeroVector;
	FVector OffPadSpot = FVector::ZeroVector;

	bool bPrepared = false;
	bool bDriveComplete = false;
	bool bFinished = false;
};
