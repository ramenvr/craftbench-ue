// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHaulCarryFunctionalTest - L2 fixture for
// t2-crate-you-carry-changes-what-you-can-do. Runs in
// Content/Maps/t2-crate-you-carry-changes-what-you-can-do/L_HaulYard.umap.
//
// THE YARD IS PRICED BY THIS FIXTURE, TWICE. MassKg and MinimumHoldKg are written
// here in PrepareTest and written again part way through the run, at the RE-PRICE.
// That is the whole answer to "a table of hard-coded thresholds passes": the second
// set of numbers makes two doors that are standing OPEN have to SHUT with not one
// crate moving. A submission that copied a number down at BeginPlay, or that read
// the map once and baked it, keeps them open and fails by name. The crates' painted
// labels are derived from the property every frame, so the picture follows the
// price and a reviewer sees the same numbers the grade sees.
//
// CARRIED IS DECIDED GEOMETRICALLY, NEVER ASKED. A crate whose underside is above
// kInAirZ is off the ground; if it is near the character it is being carried and
// the ride gates apply, and if it is not, it is a crate somebody left hanging in
// mid-air and TheCrateYouPutDownComesToRest says so. Nothing here calls into the
// submission, so any mechanism that produces the behaviour grades the same.
//
// THE RIDE BAND IS SUSPENDED NEAR A WALL, AND THAT IS DISCLOSED. A crate that is
// correctly stopped by a wall cannot also be 290-380 cm in front of a character who
// has walked up to that wall - the two are geometrically incompatible. So the band
// is judged only when the character is more than kWallFreeCm from every blocker,
// and the no-clipping gate is judged everywhere. Get that wrong and the fixture
// fails the only correct answer there is.
//
// PANEL, NOT THE ACTOR. The graded part of a door is the component named "Panel",
// else the largest by local bounds, ties by name - resolved ONCE in PrepareTest, so
// a decorative component added later cannot become the thing that is measured. The
// door ACTOR is separately held to its staged transform, because sliding the whole
// door up is not the slab lifting out of its frame.
//
// All FAIL text is ASCII-only (the cp1252 log read-back rule).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "HaulCarryFunctionalTest.generated.h"

class ACharacter;
class UStaticMeshComponent;

/** One scheduled stop of the drive. */
struct FHaulStop
{
	/** Fixed world point to walk to. Ignored when CrateIndex >= 0. */
	FVector Target = FVector::ZeroVector;
	/** >= 0: walk at THAT crate's live position and arrive kAtCrateCm short of it. */
	int32 CrateIndex = -1;
	/** Seconds to stand still after arriving. */
	double Dwell = 0.5;
	/** > 0: never "arrives" - push toward Target for this long, then advance. */
	double Press = 0.0;
	/** 1 free-handed baseline, 2 carrying, 3 after setting down. 0 = not measured. */
	int32 Measure = 0;
	/** 1 press jump empty-handed, 2 press jump carrying. 0 = no jump here. */
	int32 JumpTest = 0;
	/** Re-price the yard when this stop's dwell ends. */
	bool bReprice = false;
	FString Label;
};

/** What the fixture watches on one door. */
struct FHaulDoorProbe
{
	TWeakObjectPtr<AActor> Actor;
	TWeakObjectPtr<UStaticMeshComponent> Panel;
	FVector StagedActorLoc = FVector::ZeroVector;
	double ShutPanelZ = 0.0;
	/** Separate spells of being open, and whether it is open right now. */
	int32 OpenSpells = 0;
	bool bWasOpen = false;
	int32 Drops = 0;
};

/** What the fixture watches on one plate. */
struct FHaulPlateProbe
{
	TWeakObjectPtr<AActor> Actor;
	int32 DoorIndex = -1;
	FVector StagedLoc = FVector::ZeroVector;
	/** The load last seen, and when it last changed. The door is judged only after
	 *  the disclosed settle has passed since then. */
	double LastLoadKg = -1.0;
	double LoadChangedAt = -1000.0;
};

UCLASS()
class CRAFTBENCHTESTS_API AHaulCarryFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AHaulCarryFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ---- staging -------------------------------------------------------------
	bool ResolveStaging();
	bool ReadNumbers();
	void PriceYard(int32 Round);
	UStaticMeshComponent* ResolvePanel(AActor* Door) const;
	void BuildRoute();
	bool ValidateRoute();
	bool ValidateMargins();
	void Fail(const TCHAR* Gate, const FString& Detail);
	void Precondition(const FString& Detail);

	// ---- measurement ---------------------------------------------------------
	double LoadOnPlateKg(int32 PlateIndex) const;
	double DoorLiftCm(int32 DoorIndex) const;
	bool CrateIsInAir(int32 CrateIndex) const;
	int32 RidingCrateIndex() const;
	double SurfaceUnderCrateZ(int32 CrateIndex) const;
	float ReadFloat(const AActor* A, const TCHAR* Name, bool& bOK) const;
	void WriteFloat(AActor* A, const TCHAR* Name, float Value);

	// ---- per-frame gates -----------------------------------------------------
	bool GateSpeeds(double Now);
	bool GateJump(double Now);
	bool GateRideAndWalls(double Now);
	bool GatePlatesAndDoors(double Now);
	bool GateYardStaysPut(double Now);
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now) const;

	// ---- resolved yard -------------------------------------------------------
	TWeakObjectPtr<ACharacter> Hero;
	TArray<TWeakObjectPtr<AActor>> Crates;      // sorted west to east
	TArray<FHaulPlateProbe> Plates;             // sorted low Y first
	TArray<FHaulDoorProbe> Doors;
	TArray<FBox> BlockerBoxes;
	TArray<FVector> BlockerStagedLoc;
	TArray<TWeakObjectPtr<AActor>> Blockers;
	FVector HeroStart = FVector::ZeroVector;
	double FloorTopZ = 0.0;
	double PadHalfCm = 450.0;

	// ---- drive ---------------------------------------------------------------
	TArray<FHaulStop> Route;
	int32 Stop = 0;
	double ArrivedAt = -1.0;
	double LegStartedAt = 0.0;
	FVector LegStartedFrom = FVector::ZeroVector;
	double LegLengthCm = 0.0;
	/** Last frame's distance to the current stop. A submission that made the
	 *  character FASTER than the yard's own speed can step straight over a 25 cm
	 *  arrival window at 20 FPS and never "arrive"; that would FAIL the leg
	 *  deadline and read as a jam, when the fault is the speed. The latch below
	 *  catches the overshoot so the run reaches the speed gate that names it. */
	double LegPrevDist = -1.0;
	bool bRepricedThisStop = false;
	int32 PriceRound = 1;
	double RepricedAt = -1000.0;

	// ---- speed estimator (the already-validated mud shape) --------------------
	FVector HeroPrev = FVector::ZeroVector;
	bool bHavePrev = false;
	double HeroSpeed = 0.0;
	double FreeSpeed = 0.0;
	int32 FreeSamples = 0;
	double CarrySpeed = 0.0;
	int32 CarrySamples = 0;
	double BackSpeed = 0.0;
	int32 BackSamples = 0;

	// ---- jump probe ----------------------------------------------------------
	int32 JumpPhase = 0;             // 0 idle, 1 pressed, 2 watching
	double JumpStartedAt = -1.0;
	double JumpGroundZ = 0.0;
	double JumpRiseCm = 0.0;
	bool bJumpLeftGround = false;
	int32 JumpTestsDone = 0;

	// ---- ride / wall ---------------------------------------------------------
	int32 LastRiding = -1;
	double RidingSince = -1.0;
	double DeepInWallSince = -1.0;
	double EmptyBesideCrateSince = -1.0;
	int32 PickUps = 0;

	// ---- settled crates ------------------------------------------------------
	TArray<FVector> LandedAt;
	TArray<double> LandedWhen;
	TArray<uint8> bAirborne;
};
