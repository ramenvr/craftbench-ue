// Copyright CraftBench. All Rights Reserved.
//
// L2 for t3-checkpoint-restores-the-world.
//
// The yard is walked once, on a twenty-stop script, and three lives end on hot floor
// along the way. What is graded at each of those three deaths is whether the yard came
// back to the way it was AT THE MOMENT THE CURRENT MARK WAS SET -- which is a different
// world at each of the three, and never the world the yard opened in except at the
// first.
//
// Every stop is computed from the props' LIVE trigger volumes; no coordinate appears in
// this file. The corridor the drive walks along is DERIVED too: it is the middle of the
// widest gap between the yard's occupied lanes, so it self-calibrates if the level is
// re-authored, and PrepareTest refuses to start if that gap is too narrow to walk.
//
// TWO THINGS ABOUT THE PREDICATES, because getting them backwards makes the task
// unwinnable for everyone including the reference:
//
//  (1) The props react to CAPSULE-versus-box overlaps, which begin about a capsule
//      radius of travel before the character's own origin reaches the box. Every
//      "X may only change within N seconds of standing on Y" window here is therefore
//      opened by (the prop's own overlap set) OR (that box grown by capsule radius +
//      half height + margin). That union is a strict superset of what the prop sees, so
//      the fixture's window opens EARLIER than the prop can fire and never later. A
//      door opening the instant its plate registers is always inside its window.
//  (2) The ledger of WHICH PAD was stood on uses the prop's overlap set and nothing
//      else -- ungrown. A grown pad box would let the fixture record a stand the pad's
//      own trigger never announced, and then grade the respawn against a mark the
//      submission was never told about.
//
// The death itself is taken from the hazard's own announcement, not from a sampled
// overlap: a correct submission moves the character off the hot floor inside the very
// frame the overlap fires, so an overlap sampled on the next tick can read empty. A
// sampled overlap is kept as a SECOND detector for a run where that announcement never
// arrives, and the two can never double-count.
//
// The fixture holds its own input for the whole judging window after each death. Without
// that it would still be walking the character at the hazard while measuring how far
// they are from the mark -- i.e. measuring its own drive.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "CheckpointRestoreFunctionalTest.generated.h"

class ABankCounterActor;
class ACharacter;
class ACheckpointStandActor;
class ACoinPickupActor;
class AHazardStripActor;
class ALatchDoorActor;
class UBoxComponent;

UCLASS()
class ACheckpointRestoreFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACheckpointRestoreFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

	/** Bound to every hazard. The ONLY reliable instant a death happened: a correct
	 *  submission has already moved the character by the time anything is sampled. */
	UFUNCTION()
	void OnHazardTouched(AActor* Victim);

private:
	/** Where a coin is. Three places, not two -- "taken" and "banked" are different
	 *  things and only one of them ever comes back. */
	enum class ECoinPlace : uint8 { OnStand, InHand, OverTheLine };

	/** Where a leaf is. Neither is a failure in itself: the leaf has two places. */
	enum class EDoorState : uint8 { Shut, Open, Neither };

	enum class EStopKind : uint8 { DoorPlate, CoinStand, Pad, Counter, Hazard, Clear };

	struct FStop
	{
		EStopKind Kind = EStopKind::Clear;
		int32 Index = 0;
	};

	struct FPadRec
	{
		TWeakObjectPtr<ACheckpointStandActor> Actor;
		int32 Order = 0;
		/** Rising edge of the pad's OWN overlap set. Ungrown, on purpose. */
		bool bTouching = false;
	};

	struct FDoorRec
	{
		TWeakObjectPtr<ALatchDoorActor> Actor;
		FName Id;
		FVector ShutAt = FVector::ZeroVector;
		FVector OpenAt = FVector::ZeroVector;
		EDoorState State = EDoorState::Shut;
		/** Last instant the plate window was open. */
		double PlateContactAt = -1000.0;
		bool bPlateWindow = false;
		/** Set when the plate window opens on a SHUT door: it has to be open by then. */
		bool bOwesOpen = false;
		double OwesOpenBy = -1.0;
	};

	struct FCoinRec
	{
		TWeakObjectPtr<ACoinPickupActor> Actor;
		FName Id;
		ECoinPlace Place = ECoinPlace::OnStand;
		bool bVisible = true;
		double ContactAt = -1000.0;
		bool bStandWindow = false;
		/** Set when the stand window opens on a coin that is ON its stand. */
		bool bOwesTake = false;
		double OwesTakeBy = -1.0;
		/** Where the coin was staged, so the mid-run move is a move and not a drift. */
		FVector StagedAt = FVector::ZeroVector;
	};

	// -- staging ------------------------------------------------------------
	bool ResolveStaging();
	bool DeriveCorridor();
	bool BuildScript();
	bool CheckRoute();

	// -- geometry -----------------------------------------------------------
	bool InVolume(const UBoxComponent* Box, const FVector& P, bool bGrow) const;
	bool Touching(const UBoxComponent* Box) const;
	bool InWindow(const UBoxComponent* Box) const;
	double DistToVolume(const UBoxComponent* Box, const FVector& P) const;
	const UBoxComponent* PropVolume(const FStop& S) const;
	FVector StopLocation(const FStop& S) const;
	FVector HeroAt() const;

	// -- reads, all of them visible consequences ----------------------------
	EDoorState ReadDoor(const FDoorRec& D) const;
	bool ReadCoinVisible(const FCoinRec& C) const;
	bool ReadPadLit(const FPadRec& P) const;
	int32 ReadCarriedFace() const;
	int32 ReadBankedFace() const;
	int32 CountInHand() const;
	FString HandList() const;

	// -- gates --------------------------------------------------------------
	void ObserveDoors(double Now);
	void ObserveCoins(double Now);
	void ObserveBanked(double Now);
	void ObserveOwed(double Now);
	void ObserveSettled(double Now);
	void JudgeDeath(double Now);
	void FinalGrade(double Now);

	// -- drive --------------------------------------------------------------
	void TakeSnapshot(double Now);
	void RegisterDeath(double Now);
	void ReleaseAfterDeath(double Now);
	void MoveTheCoins();
	void BuildTransits();
	void AdvanceStep(double Now);
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now) const;
	void Fail(const FString& Message);
	void Precondition(const FString& Message);

	// -- staging state ------------------------------------------------------
	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<ABankCounterActor> Counter;
	TArray<FPadRec> Pads;
	TArray<FDoorRec> Doors;
	TArray<FCoinRec> Coins;
	TArray<TWeakObjectPtr<AHazardStripActor>> Hazards;
	TArray<FVector> Entrances;
	FVector Entrance = FVector::ZeroVector;
	double CorridorY = 0.0;
	bool bStaged = false;
	bool bGraded = false;

	// -- the mark and its snapshot ------------------------------------------
	int32 MarkPad = INDEX_NONE;
	double LastArmAt = -1000.0;
	TArray<bool> SnapDoorOpen;
	TArray<ECoinPlace> SnapCoinPlace;

	// -- the ledger ---------------------------------------------------------
	int32 BankedSeen = 0;
	int32 OpeningBanked = 0;
	double LedgerChangedAt = -1000.0;
	double CounterContactAt = -1000.0;

	// -- deaths -------------------------------------------------------------
	bool bDeathSignalled = false;
	bool bInDeathWindow = false;
	bool bHoldingInput = false;
	bool bJudgedThisDeath = false;
	int32 DeathsRegistered = 0;
	int32 DeathsJudged = 0;
	double DeathAt = -1000.0;
	double DeathWindowEndedAt = -1000.0;
	int32 BankedBeforeDeath = 0;
	int32 MarkAtDeath = INDEX_NONE;
	/** Per death: did the character move under fixture input once released? */
	TArray<bool> MovedAfterDeath;
	double MobilityStartedAt = -1.0;
	double MobilitySoFar = 0.0;
	FVector MobilityLastAt = FVector::ZeroVector;

	// -- drive state --------------------------------------------------------
	TArray<FStop> Script;
	int32 StepIndex = 0;
	TArray<FVector> Transits;
	int32 TransitIndex = 0;
	double DwellUntil = -1.0;
	bool bCoinsMoved = false;
};
