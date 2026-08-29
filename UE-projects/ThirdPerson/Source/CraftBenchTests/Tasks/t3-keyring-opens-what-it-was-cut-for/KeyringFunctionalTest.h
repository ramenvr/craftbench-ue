// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-keyring-opens-what-it-was-cut-for.
//
// Six key stands, seven door bays and one board. Every key is cut for one category and
// every bay is painted with the category (or, on exactly one bay, the two categories) it
// opens for. The yard RE-CUTS all six category names before any actor's BeginPlay, from
// a logged seed, so no canned string and no remembered ordering can pass; the PROP
// POSITIONS never move, so travel times and therefore the discrimination stops are the
// same run to run.
//
// Part way through, the fixture blanks the board and retires the body the drive is
// steering, and a fresh one takes over at the gate. The ring belongs to the shift, so a
// submission that hangs it off the character loses it, and a submission that cached the
// character in BeginPlay goes silently dead for the rest of the run.
//
// WHERE THE GATES LIVE, and why not on the checkpoint clock: dwells are 3.0 s with a
// 1.5 s settle floor, i.e. a gradeable window far shorter than any sane checkpoint
// period. Every gate therefore runs in Tick — the continuous ones every frame, the
// dwell ones on the first frame past the settle floor at their own stop. OnCheckpoint
// does two things only: it writes the calibration line, and at the SENTINEL (the last
// scheduled checkpoint, far past the drive, because ACraftBenchFunctionalTest declares
// SUCCESS the moment the last checkpoint is crossed) it evaluates the deferred
// whole-shift assertions.
//
// IDENTITY: props by ACTOR TAG, their readouts by COMPONENT TAG, their numbers by
// PROPERTY NAME. The prop classes live in the agent-writable module, so a rename, a
// retype or a stripped component tag is an AGENT action and grades as a named FAIL —
// never as a harness precondition, which would hand any submission a way out of the
// denominator. Only a prop MISSING FROM THE LEVEL is a staging fault.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "KeyringFunctionalTest.generated.h"

class ACharacter;
class APawn;
class APlayerStart;
class UPointLightComponent;
class USceneComponent;
class UTextRenderComponent;
struct FActorsInitializedParams;

UCLASS()
class AKeyringFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AKeyringFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	/** One key stand. */
	struct FStand
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<USceneComponent> KeyMesh;
		TWeakObjectPtr<UPointLightComponent> Lamp;
		FName Category;
		double MatRadius = 0.0;
		FVector StagedAt = FVector::ZeroVector;
		/** Inside its OWN mat at least once -- this is what the fixture's ring is
		 *  built from, and the order these fire in is the pickup order. */
		bool bStoodOnMat = false;
		/** Inside 1.5x its own mat at least once. Deliberately GENEROUS and used only
		 *  by the accusing half of a gate, so a submission whose reach is a little
		 *  wide is never failed for being early. */
		bool bNearMat = false;
		int32 Label = 0;
	};

	/** One door bay. */
	struct FBay
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<USceneComponent> Panel;
		FName Wants;
		FName AlsoWants;
		double MatRadius = 0.0;
		double Slide = 0.0;
		FVector StagedAt = FVector::ZeroVector;
		/** The panel's pose in the frame's own space, recorded BEFORE any BeginPlay.
		 *  "Open" is measured against this, never against a flag. */
		FVector PanelShutRel = FVector::ZeroVector;
		bool bNearMat = false;
		bool bEverOpen = false;
		double OpenedAt = -1.0;
		int32 Label = 0;
	};

	/** One point on the drive. Stop > 0 means "stand here and grade"; Stop == 0 is a
	 *  corner the drive turns at and nothing is measured. */
	struct FNode
	{
		FVector Loc = FVector::ZeroVector;
		int32 Stop = 0;
		double Dwell = 0.0;
	};

	// ---- staging, all of it before any actor's BeginPlay -------------------
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	bool CollectProps();
	bool ClassifyYard();
	bool RecutTheYard();
	bool CheckPropContract();

	// ---- reflection helpers (by NAME, never by linking the agent's class) --
	bool ReadName(AActor* A, const TCHAR* PropName, FName& Out) const;
	bool WriteName(AActor* A, const TCHAR* PropName, const FName& Value) const;
	bool ReadFloat(AActor* A, const TCHAR* PropName, double& Out) const;
	USceneComponent* FindTaggedScene(AActor* A, const TCHAR* ComponentTag) const;
	UTextRenderComponent* FindTaggedText(AActor* A, const TCHAR* ComponentTag) const;
	UPointLightComponent* FindLamp(AActor* A) const;

	// ---- readbacks: what a person watching the yard would see --------------
	bool ReadKeyTaken(const FStand& S) const;
	bool ReadBayOpen(const FBay& B) const;
	double ReadPanelTravel(const FBay& B) const;
	FString ReadBoard() const;
	/** The board's text split on commas and trimmed. "--" and "" both read empty. */
	void ParseBoard(TArray<FString>& OutTokens) const;

	// ---- the fixture's own truth -------------------------------------------
	FString RingText() const;
	bool RingHolds(const FName& Category) const;
	bool NearModelHolds(const FName& Category) const;
	FString BayDemandText(const FBay& B) const;

	// ---- route -------------------------------------------------------------
	void BuildRoute();
	void PushCorner(const FVector& Loc);
	void PushPlazaStop(const FVector& Stop, int32 Label, double Dwell);
	void PushAlcoveStop(const FVector& Stop, int32 Label, double Dwell);
	FVector BayStop(const FBay& B, bool bFromSouth) const;
	FVector StandStop(const FStand& S, bool bFromNorth) const;
	bool CheckRouteStaging();

	// ---- run ----------------------------------------------------------------
	void UpdateModels(const FVector& HeroAt, double Now);
	bool RunContinuousGates(double Now);
	bool CheckPropsIntact(double Now);
	void DriveAndGrade(double Now);
	void GradeStop(int32 Stop, double Now);
	void DoShiftChange(double Now);
	void LogCalib(int32 Index, double Now) const;

	// ---- gate bodies (each owns its own literals) ---------------------------
	void GateBoardShowsRing(int32 Stop, double Now);
	void GateBoardAfterShift(int32 Stop, double Now);
	void GateBoardForNewBody(int32 Stop, double Now);
	void GateStandGaveItsKey(int32 Stop, const FStand& S, double Now);
	void GateStandGaveItsKeyToNewBody(int32 Stop, const FStand& S, double Now);
	void GateBayShut(int32 Stop, const FBay& B, double Now);
	void GateBayOpen(int32 Stop, const FBay& B, double Now);
	void GateBaySecondOfItsKind(int32 Stop, const FBay& B, double Now);
	void GateBayOpenForNewBody(int32 Stop, const FBay& B, double Now);
	void GateFarBayOpen(int32 Stop, const FBay& B, double Now);
	void GateBayStillOpen(int32 Stop, const FBay& B, double Now);

	void FailStaging(const FString& Why);
	void FailBehaviour(const FString& Why);

	// ---- state --------------------------------------------------------------
	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Board;
	TWeakObjectPtr<UTextRenderComponent> Sign;
	TWeakObjectPtr<APlayerStart> Start;

	TArray<FStand> Stands;   // canonical order: southW, southE, alcove, far0..far2
	TArray<FBay> Bays;       // canonical order: row west->east (6), then the alcove bay

	/** Indices into Stands / Bays, filled by ClassifyYard. */
	int32 StandI = INDEX_NONE;      // the first key the shift takes  (category A)
	int32 StandII = INDEX_NONE;     // the second                     (category B)
	int32 StandIII = INDEX_NONE;    // taken by the FRESH body        (category C)
	int32 StandZ = INDEX_NONE;      // nobody ever goes there         (category Z)
	int32 BayA1 = INDEX_NONE;
	int32 BayA2 = INDEX_NONE;
	int32 BayZ = INDEX_NONE;
	int32 BayB1 = INDEX_NONE;
	int32 BayFar = INDEX_NONE;      // the one painted with TWO categories
	int32 BayWall = INDEX_NONE;     // the way into the walled corner
	int32 BayAlcove = INDEX_NONE;   // inside the walled corner

	/** Categories in the order the fixture saw the character stand on their mats. */
	TArray<int32> PickupOrder;
	/** When each of those happened, so which body fetched which key is decided by the
	 *  clock rather than by counting. */
	TArray<double> PickupTimes;

	TArray<FNode> Route;
	int32 NodeIndex = 0;
	double DwellStart = -1.0;
	bool bGradedThisNode = false;
	double SegmentStartedAt = 0.0;
	int32 LastStopReached = 0;

	/** Geometry derived from the LIVE yard in PrepareTest -- never written down. */
	double RowY = 0.0;
	double LaneY = 0.0;
	FVector AlcoveEntry = FVector::ZeroVector;
	FVector Muster = FVector::ZeroVector;
	double WalkSpeed = 500.0;
	double HeroHalfHeight = 96.0;
	double RouteLength = 0.0;
	double SentinelAt = 420.0;
	int32 SentinelIndex = 0;

	/** The shift change. */
	bool bShiftDone = false;
	bool bAwaitingBody = false;
	bool bFreshBodyConfirmed = false;
	double ShiftAt = -1.0;
	double AwaitUntil = -1.0;
	TWeakObjectPtr<APawn> RetiredBody;
	FName RetiredBodyName;

	int32 RecutSeed = 0;
	FDelegateHandle WorldInitHandle;
	bool bStaged = false;
	/** Set during the pre-BeginPlay pass, reported at PrepareTest (there is no test to
	 *  fail yet when it is found). Behaviour faults and staging faults are kept apart
	 *  on purpose: only the second is unscored. */
	FString PendingBehaviourFault;
	FString PendingStagingFault;
};
