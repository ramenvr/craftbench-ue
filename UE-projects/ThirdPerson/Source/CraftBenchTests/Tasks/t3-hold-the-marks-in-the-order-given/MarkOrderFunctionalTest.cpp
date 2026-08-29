// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.

#include "MarkOrderFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// =============================== DISCLOSED numbers ===============================
	// Every one of these appears in the agent-visible prompt in plain words. Nothing
	// below this block is ever enforced against a submission without also being
	// forgiving in the direction that cannot mask a wrong answer.
	constexpr double kRingRadiusUu = 150.0;      // "a circle of radius 150 cm"
	constexpr double kMinSeparationUu = 500.0;   // "No two marks are within 500 cm"
	constexpr double kFaceLagS = 0.25;           // "a quarter of a second behind"
	constexpr double kLampLitFloor = 5000.0;     // "at least 5000 bright"
	constexpr double kLampDarkCeil = 1.0;        // "dark -- brightness 0"

	// ==================== UNDISCLOSED: clocking and forgiveness ======================
	// kSuppressS is 1.5x the half second the prompt promises the hall to catch up, so
	// the contract is never judged on its own boundary.
	constexpr double kSuppressS = 0.75;
	constexpr double kStagingSettleS = 0.75;
	// At 20 Hz a ~500 uu/s walk moves 25 cm per frame against a 300 cm ring, so at most
	// one frame is genuinely ambiguous. The route enters and leaves every ring head-on
	// and never grazes one tangentially, so a one-frame difference shifts an edge TIME
	// and never an edge COUNT.
	constexpr double kCrossSuppressS = 0.35;
	constexpr double kEdgeBandFrames = 1.5;

	// The comparison tolerance on a face's banked half is kFaceLagS plus that mark's
	// own accumulated one-frame sampling ambiguity (one frame per ring crossing in the
	// current attempt, zeroed whenever the bank is). THE CAP IS LOAD-BEARING ARITHMETIC:
	// the tightest pairwise separation any staged set carries is 0.7 s, and the named
	// wrong answers all miss by >= 1.0 s, so 0.25 + 0.25 = 0.50 s catches every one of
	// them with room to spare. Measured against the drive: the busiest mark takes three
	// crossings in one attempt, i.e. 0.15 s at 20 Hz, so the cap has 66% headroom and
	// never binds on a correct answer.
	constexpr double kUncertaintyCapS = 0.25;
	// The required half is an ECHO of a number the mark itself carries, so it is
	// compared tightly -- one decimal of rounding is +/-0.05.
	constexpr double kRequiredEps = 0.06;

	// Windows, all measured from the model event that arms them.
	constexpr double kWrongStepFromS = 0.75;
	constexpr double kWrongStepToS = 2.0;
	constexpr double kOutOfTurnFromS = 2.0;
	constexpr double kListChangeFromS = 0.75;
	constexpr double kListChangeToS = 2.5;
	constexpr double kReEntryWindowS = 0.5;
	constexpr double kAwayArmS = 0.75;
	constexpr double kAwayDriftS = 0.25;
	constexpr double kCompletionCheckS = 0.75;
	constexpr double kCompletionWindowS = 1.0;
	/** A bank below this is not "worth preserving": the pause/resume gates only arm on
	 *  a stand that actually banked something, so a step off a mark that banked nothing
	 *  (a poisoned stand, a finished mark) does not manufacture a vacuous window. */
	constexpr double kBankWorthS = 0.9;

	// Staging preconditions -- attributed, never scored.
	constexpr double kMinSecondsS = 1.0;
	constexpr double kMinSecondsGapS = 0.5;
	constexpr double kMinListLength = 2;

	// Route.
	constexpr double kNonTargetClearUu = 120.0;
	constexpr double kParkClearUu = 300.0;
	constexpr double kParkBackOffUu = 1000.0;
	constexpr double kWaypointUu = 70.0;
	constexpr double kHoldDeadbandUu = 45.0;
	constexpr double kHoldScale = 0.35;
	constexpr double kCrossOutUu = 700.0;    // past the crossed mark's centre, eastward
	constexpr double kCrossBackUu = 500.0;   // past the crossed mark's centre, westward
	constexpr double kCrossUpUu = 600.0;     // past the crossed mark's centre, northward
	constexpr double kRowAlignUu = 5.0;
	constexpr double kMovedUu = 2.0;

	// ============================ THE STAGED TABLES ==================================
	// CANONICAL ORDER -- Marks is re-ordered into it in ResolveHall, so a canonical
	// index and a Marks index are the same number and nothing has to be looked up twice.
	// These numbers are the FIXTURE's; a submission can only ever read them off the
	// actors, and they are re-written under it four times.
	const TCHAR* const kCanonNames[5] =
	{
		TEXT("Ash"), TEXT("Birch"), TEXT("Cedar"), TEXT("Dune"), TEXT("Elm")
	};
	constexpr int32 kAsh = 0, kBirch = 1, kCedar = 2, kDune = 3, kElm = 4;

	// Round 1. Pairwise separation of {2.5, 3.5, 5.0, 6.5, 8.0} is 1.0 s at its
	// tightest. The ORDER matches no orderable property of the hall -- not alphabetical
	// or its reverse, not ascending or descending X, not distance from the parking spot,
	// not ascending or descending required seconds (checked against all eight in
	// notes.md).
	constexpr double kRound1Seconds[5] = { 3.5, 5.0, 6.5, 2.5, 8.0 };
	constexpr int32 kRound1List[4] = { kDune, kBirch, kCedar, kAsh };

	// Round 2, staged AT THE SHIFT CHANGE, in one frame, while the character is standing
	// on Dune -- which the new list names at position 2. Three names, a different
	// subset, and Birch demoted to unlisted. {3.0, 4.5, 6.0, 7.0, 8.0}, tightest gap
	// 1.0 s.
	constexpr double kRound2Seconds[5] = { 4.5, 7.0, 3.0, 6.0, 8.0 };
	constexpr int32 kRound2List[3] = { kCedar, kDune, kAsh };

	// ROUND 3 -- THE SAME-LENGTH REORDER, staged while the character is parked clear of
	// every ring, after round 2 has been shown finished.
	//
	// THREE names again, THE SAME three names, THE SAME first name, and every mark's
	// seconds left exactly where they already stood: {Cedar, Dune, Ash} becomes
	// {Cedar, Ash, Dune}. Only the ORDER moves. A change detector that compares the
	// LENGTH of the list, or its FIRST name, or the SET of names it carries, sees
	// nothing here -- and every one of those is a locally reasonable reading of "the
	// board's list can be changed at any time". Round 1 -> round 2 goes 4 -> 3 names,
	// so a length comparison fires there and the two staged replacements together are
	// what make the difference between the two detectors observable.
	//
	// THE SECONDS ARE THE LIVE ONES, DELIBERATELY. Round 2 staged {4.5, 7.0, 3.0, 6.0,
	// 8.0}, the mid-stand raise put Cedar at 5.2, and the round-2 away drop put Dune at
	// 1.5 -- so this table is what the hall is ALREADY carrying, and StageRound refuses
	// to write it if that is ever untrue. Two reasons: (a) if a number moved here the
	// gate could fail on the required ECHO rather than on the order, which would make
	// the discrimination say something other than what it claims; and (b) at this
	// moment three marks are FINISHED, and whether a finished mark comes undone when
	// its own number is raised above its bank afterwards is a corner no prompt sentence
	// settles (task.md, Hidden invariants) -- so no finished mark's number may move.
	constexpr double kRound3Seconds[5] = { 4.5, 7.0, 5.2, 1.5, 8.0 };
	constexpr int32 kRound3List[3] = { kCedar, kAsh, kDune };

	// The four mid-stand rewrites. Each fires only while the character is standing on
	// the mark in question, and each is checked against the bank the FIXTURE's model
	// holds, never against anything the submission shows.
	constexpr double kDuneBank40pc = 1.0;        // 40% of the 2.5 round 1 stages
	constexpr double kDuneRaiseAtBank = 1.8;
	constexpr double kDuneRaisedTo = 4.2;        // the stand has to get LONGER
	constexpr double kBirchDropAtBank = 3.6;
	constexpr double kBirchDroppedTo = 2.0;      // BELOW the bank: finishes at once
	constexpr double kCedarBank45pc = 1.35;      // 45% of the 3.0 round 2 stages
	constexpr double kCedarRaiseAtBank = 2.4;
	constexpr double kCedarRaisedTo = 5.2;
	constexpr double kDunePartWayBank = 2.0;

	// THE TWO DROPS THAT LAND WITH NOBODY IN ANY RING. The character banks the mark
	// whose turn it is part way, walks all the way out to the parking spot, and only
	// then does the fixture drop that mark's number below what it has already banked.
	// The mark has to finish AT ONCE, with nobody standing anywhere -- which a finish
	// test nested inside "somebody is standing here and banking" can never do. Both
	// resulting sets keep the 0.5 s pairwise separation: round 1 becomes
	// {1.2, 2.0, 3.5, 4.2, 8.0} and round 2 becomes {1.5, 4.5, 5.2, 7.0, 8.0}.
	constexpr double kCedarBankBeforeAway = 3.0;
	constexpr double kCedarDroppedTo = 1.2;
	constexpr double kDuneBankBeforeAway = 2.5;
	constexpr double kDuneDroppedTo = 1.5;

	// Dwells the drive holds. Every one is a MINIMUM the windowed gates need, never a
	// tolerance: making them longer can only give a gate more frames to be right on.
	constexpr double kOutOfTurnStandS = 6.5;
	constexpr double kShortOutOfTurnStandS = 2.8;
	/** The two SKIP-AHEAD stands. Gate 2 judges from 0.75 s to 2.0 s and gate 3 from
	 *  2.0 s to the step off, so 4.0 s leaves gate 3 two full seconds of judged
	 *  frames -- forty at 20 Hz. Shorter than the other out-of-turn stands only
	 *  because each of these costs a re-bank of what the wipe destroyed. */
	constexpr double kSkipAheadStandS = 4.0;
	constexpr double kAwayWaitS = 6.5;
	/** How long the drive holds after a drop that landed with nobody in a ring. Gate
	 *  8's deferred check reads the lamp and the tally 0.75 s after the modelled
	 *  completion; 3.0 s is four times the half second the prompt promises. */
	constexpr double kAwayDropHoldS = 3.0;
	constexpr double kBaselineS = 1.5;
	constexpr double kShiftChangeHoldS = 3.2;
	/** How long the drive holds after the same-length reorder. Gate 4's window closes
	 *  at 2.5 s. */
	constexpr double kReorderHoldS = 3.2;

	// The schedule. The base class ends the test the moment the last scheduled
	// checkpoint is sampled, so the last entry is a SENTINEL far past the drive and the
	// run-level gate is evaluated at drive completion OR there, whichever comes first.
	// The drive models ~285 s (158 s of walking, measured off the layout by
	// authoring/author_map.py, plus ~98 s of standing and ~10% for the acceleration
	// ramps); 400 s of world time is a MEASURED anchor on this
	// substrate (t1-touched-crate-lights-up ships 420 s and holds a certificate).
	//
	// 58 CALIBRATION POINTS, NOT 50 (348 s of coverage against the old 300 s). The
	// drive grew by five phases on 2026-08-19 and a calib log that stops before the
	// drive does is a diagnostics hole. Points are only ever APPENDED: the checkpoint
	// INDEX is a public key (cameras.json's pie_timeline binds shots to it), so
	// inserting one at the front would silently re-aim every camera shot, while adding
	// one at the back moves nothing but kSentinelIndex. cameras.json's highest bound
	// index is 36, so nothing there moves.
	constexpr double kCheckpointEveryS = 6.0;
	constexpr int32 kGradedCheckpoints = 58;
	constexpr double kSentinelS = 400.0;
	constexpr int32 kSentinelIndex = 58;

	// EARLY CALIB, DELIBERATELY *NOT* CHECKPOINTS. The checkpoint INDEX is a public key
	// (cameras.json's pie_timeline binds shots to it, and kSentinelIndex is the last
	// index), so inserting points at the front would silently re-aim every camera shot.
	// A log line owes nothing to either, and the opening baseline is exactly where a
	// blank hall dies.
	constexpr double kEarlyCalibS[] = { 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0 };
	constexpr int32 kEarlyCalibCount = 7;
}

AMarkOrderFunctionalTest::AMarkOrderFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// =====================================================================================
// reflection helpers
// =====================================================================================

double AMarkOrderFunctionalTest::ReadFloat(const AActor* A, const TCHAR* PropName,
	bool& bOk) const
{
	if (A != nullptr)
	{
		if (const FFloatProperty* const P = FindFProperty<FFloatProperty>(A->GetClass(), PropName))
		{
			bOk = true;
			return double(P->GetPropertyValue_InContainer(A));
		}
		// A submission may not change these, but reading both widths costs nothing and
		// a missed read would look like a missing property, i.e. a harness fault.
		if (const FDoubleProperty* const P = FindFProperty<FDoubleProperty>(A->GetClass(), PropName))
		{
			bOk = true;
			return P->GetPropertyValue_InContainer(A);
		}
	}
	bOk = false;
	return 0.0;
}

int32 AMarkOrderFunctionalTest::ReadInt(const AActor* A, const TCHAR* PropName,
	bool& bOk) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), PropName) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0;
}

FName AMarkOrderFunctionalTest::ReadName(const AActor* A, const TCHAR* PropName,
	bool& bOk) const
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), PropName) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return NAME_None;
}

bool AMarkOrderFunctionalTest::ReadBool(const AActor* A, const TCHAR* PropName,
	bool& bOk) const
{
	if (const FBoolProperty* const P = A
			? FindFProperty<FBoolProperty>(A->GetClass(), PropName) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return false;
}

bool AMarkOrderFunctionalTest::ReadNameArray(const AActor* A, const TCHAR* PropName,
	TArray<FName>& Out) const
{
	Out.Reset();
	const FArrayProperty* const P = A
		? FindFProperty<FArrayProperty>(A->GetClass(), PropName) : nullptr;
	if (P == nullptr)
	{
		return false;
	}
	const FNameProperty* const Inner = CastField<FNameProperty>(P->Inner);
	if (Inner == nullptr)
	{
		return false;
	}
	void* const Addr = P->ContainerPtrToValuePtr<void>(const_cast<AActor*>(A));
	FScriptArrayHelper Helper(P, Addr);
	Out.Reserve(Helper.Num());
	for (int32 Index = 0; Index < Helper.Num(); ++Index)
	{
		Out.Add(Inner->GetPropertyValue(Helper.GetElementPtr(Index)));
	}
	return true;
}

bool AMarkOrderFunctionalTest::WriteFloat(AActor* A, const TCHAR* PropName,
	double Value) const
{
	if (A == nullptr)
	{
		return false;
	}
	if (const FFloatProperty* const P = FindFProperty<FFloatProperty>(A->GetClass(), PropName))
	{
		P->SetPropertyValue_InContainer(A, float(Value));
		return true;
	}
	if (const FDoubleProperty* const P = FindFProperty<FDoubleProperty>(A->GetClass(), PropName))
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AMarkOrderFunctionalTest::WriteNameArray(AActor* A, const TCHAR* PropName,
	const TArray<FName>& Values) const
{
	const FArrayProperty* const P = A
		? FindFProperty<FArrayProperty>(A->GetClass(), PropName) : nullptr;
	if (P == nullptr)
	{
		return false;
	}
	const FNameProperty* const Inner = CastField<FNameProperty>(P->Inner);
	if (Inner == nullptr)
	{
		return false;
	}
	void* const Addr = P->ContainerPtrToValuePtr<void>(A);
	FScriptArrayHelper Helper(P, Addr);
	Helper.Resize(Values.Num());
	for (int32 Index = 0; Index < Values.Num(); ++Index)
	{
		Inner->SetPropertyValue(Helper.GetElementPtr(Index), Values[Index]);
	}
	return true;
}

double AMarkOrderFunctionalTest::LampIntensity(const FMark& M) const
{
	AActor* const A = M.Actor.Get();
	if (A == nullptr)
	{
		return -1.0;
	}
	TArray<UPointLightComponent*> Lights;
	A->GetComponents<UPointLightComponent>(Lights);
	bool bAny = false;
	double Best = 0.0;
	for (const UPointLightComponent* const L : Lights)
	{
		if (L == nullptr)
		{
			continue;
		}
		bAny = true;
		// A HIDDEN lamp is not a burning lamp. The claim is about what a person in the
		// hall sees, so visibility is part of the reading, not a detail beside it.
		Best = FMath::Max(Best, L->IsVisible() ? double(L->Intensity) : 0.0);
	}
	return bAny ? Best : -1.0;
}

// =====================================================================================
// the readouts -- the ONLY channel this fixture ever grades
// =====================================================================================

bool AMarkOrderFunctionalTest::ReadFace(const FMark& M, double& OutBanked,
	double& OutRequired) const
{
	OutBanked = -1.0;
	OutRequired = -1.0;
	const AActor* const A = M.Actor.Get();
	bool bOk = false;
	const bool bEver = ReadBool(A, TEXT("bFaceEverWritten"), bOk);
	if (!bOk || !bEver)
	{
		return false;
	}
	bool bB = false;
	bool bR = false;
	OutBanked = ReadFloat(A, TEXT("LastShownBankedSeconds"), bB);
	OutRequired = ReadFloat(A, TEXT("LastShownRequiredSeconds"), bR);
	return bB && bR;
}

bool AMarkOrderFunctionalTest::ReadTally(int32& OutFinished, int32& OutLength) const
{
	OutFinished = -1;
	OutLength = -1;
	const AActor* const B = Board.Get();
	bool bOk = false;
	const bool bEver = ReadBool(B, TEXT("bTallyEverWritten"), bOk);
	if (!bOk || !bEver)
	{
		return false;
	}
	bool bF = false;
	bool bL = false;
	OutFinished = ReadInt(B, TEXT("LastShownFinished"), bF);
	OutLength = ReadInt(B, TEXT("LastShownListLength"), bL);
	return bF && bL;
}

// =====================================================================================
// staging
// =====================================================================================

bool AMarkOrderFunctionalTest::ResolveHall()
{
	UWorld* const World = GetWorld();

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in the "
				 "hall, so there is nobody to walk the marks"));
		return false;
	}
	WalkZ = Hero->GetActorLocation().Z;
	if (const UCharacterMovementComponent* const Move = Hero->GetCharacterMovement())
	{
		// MEASURED, not assumed: every step deadline is derived from this.
		HeroSpeed = FMath::Max(double(Move->GetMaxSpeed()), 100.0);
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("DutyBoard")), Found);
	if (Found.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %d actor(s) tagged DutyBoard, expected exactly "
				 "one board"), Found.Num()));
		return false;
	}
	Board = Found[0];
	{
		TArray<FName> Probe;
		bool bF = false;
		bool bL = false;
		bool bE = false;
		ReadInt(Board.Get(), TEXT("LastShownFinished"), bF);
		ReadInt(Board.Get(), TEXT("LastShownListLength"), bL);
		ReadBool(Board.Get(), TEXT("bTallyEverWritten"), bE);
		if (!ReadNameArray(Board.Get(), TEXT("ListedMarkNames"), Probe) || !bF || !bL || !bE)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the board does not expose ListedMarkNames / "
					 "LastShownFinished / LastShownListLength / bTallyEverWritten "
					 "readably, so the fixture cannot read the round off it"));
			return false;
		}
	}

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("HallMark")), Found);
	if (Found.Num() != 5)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %d actor(s) tagged HallMark, expected exactly "
				 "five painted marks"), Found.Num()));
		return false;
	}

	// Re-ordered into the CANONICAL order, so a canonical index and a Marks index are
	// the same number. A hall that does not carry these five names is a re-authored
	// hall, and it fails LOUDLY rather than grading something else.
	Marks.Reset();
	Marks.SetNum(5);
	TArray<bool> Filled;
	Filled.Init(false, 5);
	for (AActor* const A : Found)
	{
		bool bN = false;
		bool bR = false;
		bool bD = false;
		const FName TheName = ReadName(A, TEXT("MarkName"), bN);
		const double TheRequired = ReadFloat(A, TEXT("RequiredSeconds"), bR);
		const double TheRadius = ReadFloat(A, TEXT("RingRadiusUu"), bD);
		if (!bN || !bR || !bD)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose MarkName / "
					 "RequiredSeconds / RingRadiusUu readably"), *A->GetName()));
			return false;
		}
		int32 Canon = INDEX_NONE;
		for (int32 c = 0; c < 5; ++c)
		{
			if (TheName == FName(kCanonNames[c]))
			{
				Canon = c;
				break;
			}
		}
		if (Canon == INDEX_NONE)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the hall carries a mark called '%s'; this "
					 "fixture stages Ash, Birch, Cedar, Dune and Elm"),
				*TheName.ToString()));
			return false;
		}
		if (Filled[Canon])
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: two marks are both called '%s'; a mark is "
					 "known by its name and by nothing else"), *TheName.ToString()));
			return false;
		}
		TArray<UPointLightComponent*> Lights;
		A->GetComponents<UPointLightComponent>(Lights);
		if (Lights.Num() == 0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the mark called '%s' has no lamp, so the "
					 "fixture cannot tell whether it is burning"), *TheName.ToString()));
			return false;
		}
		if (FMath::Abs(TheRadius - kRingRadiusUu) > 0.5)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the mark called '%s' carries a ring of "
					 "%.1f cm; the prompt discloses %.0f cm"),
				*TheName.ToString(), TheRadius, kRingRadiusUu));
			return false;
		}

		FMark& M = Marks[Canon];
		M.Actor = A;
		M.Name = TheName;
		M.Required = TheRequired;
		M.Radius = TheRadius;
		M.At = A->GetActorLocation();
		M.StagedName = TheName;
		M.StagedRequired = TheRequired;
		M.StagedRadius = TheRadius;
		M.StagedAt = M.At;
		M.PreviousRequired = TheRequired;
		M.Label = TheName.ToString();
		Filled[Canon] = true;

		double B = 0.0;
		double R = 0.0;
		ReadFace(M, B, R);
		bool bEver = false;
		ReadBool(A, TEXT("bFaceEverWritten"), bEver);
		if (!bEver)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the mark called '%s' does not expose "
					 "bFaceEverWritten, so the fixture cannot read its face"),
				*TheName.ToString()));
			return false;
		}
	}

	IdxAsh = kAsh;
	IdxBirch = kBirch;
	IdxCedar = kCedar;
	IdxDune = kDune;
	IdxControl = kElm;

	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		for (int32 j = i + 1; j < Marks.Num(); ++j)
		{
			const double D = FVector::Dist2D(Marks[i].At, Marks[j].At);
			if (D < kMinSeparationUu - 1.0)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: %s and %s stand %.0f cm apart and the "
						 "prompt promises at least %.0f, so the character could be on "
						 "two marks at once"),
					*Marks[i].Label, *Marks[j].Label, D, kMinSeparationUu));
				return false;
			}
		}
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-marks] hall resolved: %s; hero pace %.0f uu/s at z=%.0f"),
		*DescribeHall(), HeroSpeed, WalkZ);
	return true;
}

bool AMarkOrderFunctionalTest::ValidateStagedSet(const TCHAR* Which,
	const TArray<double>& Seconds, const TArray<FName>& List)
{
	if (Seconds.Num() != Marks.Num())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %s stages %d numbers for %d marks"),
			Which, Seconds.Num(), Marks.Num()));
		return false;
	}
	for (int32 i = 0; i < Seconds.Num(); ++i)
	{
		if (Seconds[i] < kMinSecondsS)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s stages %s at %.2f s; a mark nobody can "
					 "measurably stand on is not a mark"),
				Which, *Marks[i].Label, Seconds[i]));
			return false;
		}
		for (int32 j = i + 1; j < Seconds.Num(); ++j)
		{
			if (FMath::Abs(Seconds[i] - Seconds[j]) < kMinSecondsGapS)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: %s stages %s at %.2f and %s at %.2f, "
						 "which is inside the %.2f s the fixture needs to tell 'used "
						 "another mark's number' apart from a lagging face"),
					Which, *Marks[i].Label, Seconds[i], *Marks[j].Label, Seconds[j],
					kMinSecondsGapS));
				return false;
			}
		}
	}
	if (List.Num() < kMinListLength)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %s carries %d name(s); a round of fewer than "
				 "%d names cannot show an order at all"),
			Which, List.Num(), int32(kMinListLength)));
		return false;
	}
	for (int32 i = 0; i < List.Num(); ++i)
	{
		if (MarkIndexNamed(List[i]) == INDEX_NONE)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s names '%s' and no mark in the hall "
					 "carries that name"), Which, *List[i].ToString()));
			return false;
		}
		for (int32 j = i + 1; j < List.Num(); ++j)
		{
			if (List[i] == List[j])
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: %s names '%s' twice"),
					Which, *List[i].ToString()));
				return false;
			}
		}
		if (List[i] == Marks[IdxControl].Name)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s names '%s', which is the IN-SCENE "
					 "NEGATIVE CONTROL -- the one mark neither list may ever name"),
				Which, *List[i].ToString()));
			return false;
		}
	}
	return true;
}

void AMarkOrderFunctionalTest::StageRound(int32 Which, double Now)
{
	const double* Table = kRound1Seconds;
	TArray<FName> List;
	if (Which == 3)
	{
		Table = kRound3Seconds;
		for (int32 k = 0; k < 3; ++k)
		{
			List.Add(Marks[kRound3List[k]].Name);
		}
		// THE REORDER MOVES THE ORDER AND NOTHING ELSE. Three marks are finished at
		// this moment, and whether a finished mark comes undone when its own number
		// moves afterwards is a corner no prompt sentence settles and no gate can
		// judge. So the table has to be what the hall is already carrying, and a
		// table that has drifted out of step with the two rounds and the three
		// mid-run drops is a STAGING fault -- attributed here, never scored.
		for (int32 i = 0; i < Marks.Num(); ++i)
		{
			if (FMath::Abs(Marks[i].StagedRequired - kRound3Seconds[i]) > 0.001)
			{
				AttributeOverrun(Now, FString::Printf(
					TEXT("the same-length reorder would move %s from %.2f to %.2f, and "
						 "it may move no number at all: three marks are finished at "
						 "that instant and no gate settles what a finished mark does "
						 "when its own number moves under it"),
					*Marks[i].Label, Marks[i].StagedRequired, kRound3Seconds[i]));
				return;
			}
		}
	}
	else if (Which == 2)
	{
		Table = kRound2Seconds;
		for (int32 k = 0; k < 3; ++k)
		{
			List.Add(Marks[kRound2List[k]].Name);
		}
	}
	else
	{
		for (int32 k = 0; k < 4; ++k)
		{
			List.Add(Marks[kRound1List[k]].Name);
		}
	}

	// ONE FRAME. The pairwise-separation guarantee is stated per staged SET; writing
	// four numbers across four frames would manufacture transient sets nobody checked,
	// and any gate can be judged on one of them.
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		Marks[i].PreviousRequired = Marks[i].StagedRequired;
		Marks[i].StagedRequired = Table[i];
		WriteFloat(Marks[i].Actor.Get(), TEXT("RequiredSeconds"), Table[i]);
		Marks[i].RewrittenAt = Now;
	}
	WriteNameArray(Board.Get(), TEXT("ListedMarkNames"), List);
	StagedList = List;
	StagedRound = Which;
	StagingUntil = Now + kStagingSettleS;
	LastModelChangeAt = Now;

	FString Line;
	for (const FName& N : List)
	{
		Line += FString::Printf(TEXT("%s%s"), Line.IsEmpty() ? TEXT("") : TEXT(">"),
			*N.ToString());
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-marks] staged round %d at t=%.2f: list [%s], seconds %s"),
		Which, Now, *Line, *DescribeHall());
}

void AMarkOrderFunctionalTest::StageOneRequired(int32 MarkIndex, double NewRequired,
	double Now)
{
	if (!Marks.IsValidIndex(MarkIndex))
	{
		return;
	}
	FMark& M = Marks[MarkIndex];
	const double Was = M.StagedRequired;
	M.PreviousRequired = Was;
	M.StagedRequired = NewRequired;
	M.RewrittenAt = Now;
	WriteFloat(M.Actor.Get(), TEXT("RequiredSeconds"), NewRequired);
	StagingUntil = Now + kStagingSettleS;
	LastModelChangeAt = Now;

	// The moved number lands next to a neighbour by construction -- that is what a
	// mid-stand raise IS -- so this checks the resulting SET rather than trusting the
	// table, and attributes a mis-tuned table to staging instead of to the model.
	for (int32 j = 0; j < Marks.Num(); ++j)
	{
		if (j == MarkIndex)
		{
			continue;
		}
		if (FMath::Abs(Marks[j].StagedRequired - NewRequired) < kMinSecondsGapS)
		{
			AttributeOverrun(Now, FString::Printf(
				TEXT("the mid-stand rewrite put %s at %.2f, inside %.2f s of %s at "
					 "%.2f"), *M.Label, NewRequired, kMinSecondsGapS, *Marks[j].Label,
				Marks[j].StagedRequired));
			return;
		}
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-marks] mid-stand rewrite at t=%.2f: %s %.2f -> %.2f with %.2f banked"),
		Now, *M.Label, Was, NewRequired, M.Bank);
}

void AMarkOrderFunctionalTest::ReReadHall()
{
	for (FMark& M : Marks)
	{
		const AActor* const A = M.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		bool bN = false;
		bool bR = false;
		bool bD = false;
		M.Name = ReadName(A, TEXT("MarkName"), bN);
		M.Required = ReadFloat(A, TEXT("RequiredSeconds"), bR);
		M.Radius = ReadFloat(A, TEXT("RingRadiusUu"), bD);
		M.At = A->GetActorLocation();
	}
}

// =====================================================================================
// the model -- the same rule the prompt states, run on the fixture's own numbers
// =====================================================================================

int32 AMarkOrderFunctionalTest::MarkIndexNamed(FName InName) const
{
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		if (Marks[i].Name == InName)
		{
			return i;
		}
	}
	return INDEX_NONE;
}

int32 AMarkOrderFunctionalTest::IndexInModelList(FName InName) const
{
	return ModelList.IndexOfByKey(InName);
}

int32 AMarkOrderFunctionalTest::MarkUnderCharacter() const
{
	const ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		return INDEX_NONE;
	}
	const FVector Where = H->GetActorLocation();
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		// THE DISCLOSED PREDICATE, exactly: flat, mark centre to the character,
		// inclusive at the edge. The marks ship it as IsInsideRing; this is the same
		// arithmetic on the same two numbers, so a submission that calls theirs cannot
		// disagree with the fixture about which frame an entry happened on.
		const double DX = Where.X - Marks[i].At.X;
		const double DY = Where.Y - Marks[i].At.Y;
		if ((DX * DX + DY * DY) <= (Marks[i].Radius * Marks[i].Radius))
		{
			return i;
		}
	}
	return INDEX_NONE;
}

int32 AMarkOrderFunctionalTest::ModelFinishedCount() const
{
	return Turn;
}

void AMarkOrderFunctionalTest::StartRoundOver(double Now, const TCHAR* Why)
{
	for (FMark& M : Marks)
	{
		M.bHasBank = false;
		M.Bank = 0.0;
		M.Uncertainty = 0.0;
		M.CrossingsThisAttempt = 0;
		if (M.bFinished)
		{
			M.bFinished = false;
			M.FinishedChangedAt = Now;
		}
	}
	Turn = 0;
	LastModelChangeAt = Now;
	// WHATEVER the cause, and never cleared: gate 8's deferred check reads this to
	// know a completion was thrown away inside its own window.
	RoundStartedOverAt = Now;
	// A wait window measures a bank that is no longer there.
	AwaySinceAt = -1000.0;
	AwayMark = INDEX_NONE;
	bAwayArmed = false;
	bAwaySampled = false;
	// So does a resume window.
	ReEntryMark = INDEX_NONE;
	UE_LOG(LogTemp, Display, TEXT("[t3-marks] round starts over at t=%.2f: %s"),
		Now, Why);
}

void AMarkOrderFunctionalTest::StepModel(double Dt, double Now)
{
	// ---- 1. THE LIST, READ NOW. -------------------------------------------------
	TArray<FName> LiveList;
	ReadNameArray(Board.Get(), TEXT("ListedMarkNames"), LiveList);
	if (LiveList != ModelList)
	{
		ModelList = LiveList;
		StartRoundOver(Now, TEXT("the board is carrying a different list"));
		ListChangedAt = Now;
		++ListChangeCount;
		// A stand that was poisoned by an out-of-turn step is NOT forgiven here, and
		// no gate can distinguish the two answers: the drive never replaces the list
		// while somebody stands on a poisoned mark (task.md, Hidden invariants).
	}

	// ---- 2. WHERE THE CHARACTER IS, AND WHETHER THAT IS A STEP ONTO. ------------
	const int32 Occ = MarkUnderCharacter();
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		Marks[i].bInsideLast = Marks[i].bInside;
		Marks[i].bInside = (i == Occ);
	}
	if (Occ != OccupiedLast)
	{
		// It is the STEP ONTO that poisons a stand, so a stand that has ended cannot
		// stay poisoned.
		if (PoisonedMark != INDEX_NONE && PoisonedMark != Occ)
		{
			PoisonedMark = INDEX_NONE;
			// AND NEITHER OF THE TWO GATES THAT WATCH THAT STAND CAN OUTLIVE IT.
			// Gates 2 and 3 both claim something about the stand this step began --
			// "every clock is empty" and "this mark banks nothing for as long as they
			// stay on it" -- and both of them guard on OccupiedLast == OutOfTurnMark.
			// Left set, this made every LATER legitimate stand on the same mark look
			// like a continuation of the poisoned one: the drive walks back onto that
			// very mark four times, and on each of them a CORRECT submission's face
			// climbs exactly as it should and gate 3 read it as a bank that must have
			// stayed at zero. That is a graded FAIL on a right answer, and it is why
			// this is cleared HERE, in the one place that already knows the stand is
			// over, rather than by a guard bolted onto each gate.
			OutOfTurnMark = INDEX_NONE;
			OutOfTurnAt = -1000.0;
			bOutOfTurnAhead = false;
		}

		if (OccupiedLast != INDEX_NONE && Marks.IsValidIndex(OccupiedLast))
		{
			FMark& L = Marks[OccupiedLast];
			L.Uncertainty += FrameDt;
			++L.CrossingsThisAttempt;
			++L.CrossingsTotal;
			LastRingExitAt = Now;
			if (L.bHasBank && L.Bank >= kBankWorthS && !L.bFinished)
			{
				AwaySinceAt = Now;
				AwayMark = OccupiedLast;
				bAwayArmed = false;
				bAwaySampled = false;
				++AwayCount;
			}
			if (OccupiedLast == IdxControl && bControlWatchOpen)
			{
				ControlWatchClosesAt = Now + kSuppressS;
			}
		}
		if (Occ != INDEX_NONE && Marks.IsValidIndex(Occ))
		{
			FMark& E = Marks[Occ];
			E.Uncertainty += FrameDt;
			++E.CrossingsThisAttempt;
			++E.CrossingsTotal;
			const int32 Idx = IndexInModelList(E.Name);
			if (Idx != INDEX_NONE && Idx != Turn)
			{
				// A mark the board names, that is not the one whose turn it is --
				// later in the list, or already finished. The whole round starts over
				// AT THIS MOMENT and this stand banks nothing however long it lasts.
				//
				// WHICH HALF OF THE RULE THIS ONE IS, recorded before the wipe moves
				// Turn: Idx > Turn is a SKIP AHEAD onto a name that is not yet due and
				// has never been the current one, Idx < Turn is a name already
				// finished. The run-level gate demands two of each, because a
				// submission that only checks "have I finished this one already" is a
				// locally reasonable wrong answer that no backwards-only drive can
				// see.
				bOutOfTurnAhead = (Idx > Turn);
				if (bOutOfTurnAhead)
				{
					++SkipAheadCount;
				}
				else
				{
					++FinishedStepCount;
				}
				OutOfTurnDisplacedTurn = Turn;
				StartRoundOver(Now, bOutOfTurnAhead
					? TEXT("somebody stepped ahead onto a name that is not due yet")
					: TEXT("somebody stepped back onto a name already finished"));
				PoisonedMark = Occ;
				OutOfTurnAt = Now;
				OutOfTurnMark = Occ;
				++OutOfTurnCount;
			}
			else if (Idx != INDEX_NONE && Idx == Turn && E.bHasBank
				&& E.Bank >= kBankWorthS && !E.bFinished)
			{
				ReEntryAt = Now;
				ReEntryMark = Occ;
				ReEntryPreserved = E.Bank;
				++ReEntryCount;
			}
			if (Occ == IdxControl)
			{
				int32 F = 0;
				int32 L2 = 0;
				bControlWatchOpen = true;
				bControlWatchModelMoved = false;
				ControlWatchClosesAt = -1000.0;
				if (ReadTally(F, L2))
				{
					ControlWatchTally = F;
					ControlWatchLength = L2;
				}
				else
				{
					ControlWatchTally = -1;
					ControlWatchLength = -1;
				}
				++ControlCrossings;
			}
			// Entering ANY ring ends an off-mark wait.
			AwaySinceAt = -1000.0;
			AwayMark = INDEX_NONE;
			bAwayArmed = false;
			bAwaySampled = false;
		}
		OccupiedLast = Occ;
		LastCrossingAt = Now;
	}

	// ---- 3. BANK, SECOND FOR SECOND, AND ONLY WHERE IT IS ALLOWED. --------------
	// Stepping off pauses a bank; nothing here empties one, so stepping back on
	// carries on from the value it stopped at.
	int32 NowBanking = INDEX_NONE;
	if (Occ != INDEX_NONE && Occ != PoisonedMark
		&& IndexInModelList(Marks[Occ].Name) == Turn)
	{
		FMark& B = Marks[Occ];
		if (!B.bHasBank)
		{
			B.bHasBank = true;
			B.Bank = 0.0;
		}
		B.Bank += Dt;
		NowBanking = Occ;
	}
	if (NowBanking != BankingMark)
	{
		BankingMark = NowBanking;
		LastModelChangeAt = Now;
	}

	// ---- 4. IS THE MARK WHOSE TURN IT IS FINISHED? ------------------------------
	// Against ITS OWN number as that number reads AT THIS MOMENT -- which is why this
	// runs whether or not anybody is still standing there: a number dropped below what
	// is already banked finishes the mark at once, with nobody moving.
	for (int32 Guard = 0; Guard <= ModelList.Num(); ++Guard)
	{
		if (!ModelList.IsValidIndex(Turn))
		{
			break;
		}
		const int32 Mi = MarkIndexNamed(ModelList[Turn]);
		if (Mi == INDEX_NONE)
		{
			break;
		}
		FMark& C = Marks[Mi];
		if (!C.bHasBank)
		{
			break;
		}
		if (C.Bank + UE_KINDA_SMALL_NUMBER < C.Required)
		{
			break;
		}
		C.BankAtFinish = C.Bank;
		C.RequiredAtFinish = C.Required;
		// A finished mark stands at its own number until the round starts over.
		C.Bank = C.Required;
		C.bFinished = true;
		C.FinishedAt = Now;
		C.FinishedChangedAt = Now;
		C.Uncertainty = 0.0;
		++Turn;
		LastModelChangeAt = Now;
		if (bControlWatchOpen)
		{
			bControlWatchModelMoved = true;
		}
		if (ReEntryMark == Mi)
		{
			ReEntryMark = INDEX_NONE;
		}
		if (Mi == AwayMark)
		{
			// A bank that has just been FINISHED is no longer a PAUSED bank, and gate
			// 7's claim is only ever about a paused one. The fixture drops the current
			// mark's number below its bank twice while the character is parked, and
			// the face legitimately moves to the mark's new number on that frame --
			// which is gate 8's business, not gate 7's. Closing the wait window here
			// is what keeps the two from contradicting each other.
			AwaySinceAt = -1000.0;
			AwayMark = INDEX_NONE;
			bAwayArmed = false;
			bAwaySampled = false;
		}

		FCompletion Cp;
		Cp.Mark = Mi;
		Cp.At = Now;
		Cp.RequiredThen = C.RequiredAtFinish;
		Cp.FinishedAfter = Turn;
		// NOBODY IN ANY RING at the instant it finished. The whole point of the two
		// staged away drops: a finish test nested inside "somebody is standing here
		// and banking" cannot produce this completion at all, and every other
		// completion in the run happens under somebody's feet.
		Cp.bNobodyStanding = (Occ == INDEX_NONE);
		if (Cp.bNobodyStanding)
		{
			++AwayCompletionCount;
		}
		Completions.Add(Cp);
		UE_LOG(LogTemp, Display,
			TEXT("[t3-marks] %s finished at t=%.2f with %.2f banked against %.2f%s; "
				 "the model's tally is %d/%d"),
			*C.Label, Now, C.BankAtFinish, C.RequiredAtFinish,
			Cp.bNobodyStanding ? TEXT(" with nobody standing on any mark") : TEXT(""),
			Turn, ModelList.Num());
	}
}

// =====================================================================================
// suppression -- every one of these WIDENS the disclosed contract, never narrows it
// =====================================================================================

bool AMarkOrderFunctionalTest::SettleSuppressed(double Now) const
{
	return (Now - LastModelChangeAt) < kSuppressS;
}

bool AMarkOrderFunctionalTest::StagingSuppressed(double Now) const
{
	return Now < StagingUntil;
}

bool AMarkOrderFunctionalTest::EdgeSuppressed(double Now) const
{
	if ((Now - LastCrossingAt) < kCrossSuppressS)
	{
		return true;
	}
	const ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		return false;
	}
	// The BEFORE half of "either side of a crossing", which no look-back can supply:
	// a character within a frame and a half of travel of any ring's edge is a character
	// the two models could legitimately place on opposite sides of it.
	const double Band = FMath::Max(HeroSpeed * FrameDt * kEdgeBandFrames, 20.0);
	const FVector Where = H->GetActorLocation();
	for (const FMark& M : Marks)
	{
		const double D = FVector::Dist2D(Where, M.At);
		if (FMath::Abs(D - M.Radius) <= Band)
		{
			return true;
		}
	}
	return false;
}

double AMarkOrderFunctionalTest::FaceTolerance(const FMark& M) const
{
	return kFaceLagS + FMath::Min(M.Uncertainty, kUncertaintyCapS);
}

// =====================================================================================
// the gates
// =====================================================================================

void AMarkOrderFunctionalTest::FailGate(const FString& Message)
{
	FinishTest(EFunctionalTestResult::Failed, Message);
}

bool AMarkOrderFunctionalTest::GateHallNotRewired(double Now)
{
	if (Marks.Num() != 5 || !Board.IsValid())
	{
		FailGate(FString::Printf(
			TEXT("TheHallIsNotYoursToRewire: at t=%.2f s the hall holds %d mark(s) and "
				 "%s board. It was staged with five marks and one board, and the hall "
				 "is not yours to rearrange"),
			Now, Marks.Num(), Board.IsValid() ? TEXT("one") : TEXT("no")));
		return false;
	}
	for (const FMark& M : Marks)
	{
		if (!M.Actor.IsValid())
		{
			FailGate(FString::Printf(
				TEXT("TheHallIsNotYoursToRewire: the mark staged as %s is gone at "
					 "t=%.2f s"), *M.Label, Now));
			return false;
		}
		if (M.Name != M.StagedName)
		{
			FailGate(FString::Printf(
				TEXT("TheHallIsNotYoursToRewire: the mark staged as %s now calls itself "
					 "'%s' at t=%.2f s. A mark is known by its name; renaming one moves "
					 "the whole round"),
				*M.Label, *M.Name.ToString(), Now));
			return false;
		}
		const double ReqTol = FMath::Max(0.01, 0.001 * FMath::Abs(M.StagedRequired));
		if (FMath::Abs(M.Required - M.StagedRequired) > ReqTol)
		{
			FailGate(FString::Printf(
				TEXT("TheHallIsNotYoursToRewire: %s reads %.3f seconds at t=%.2f s and "
					 "the hall wrote %.3f. Do not change any number written on a mark"),
				*M.Label, M.Required, Now, M.StagedRequired));
			return false;
		}
		if (FMath::Abs(M.Radius - M.StagedRadius) > FMath::Max(0.01, 0.001 * M.StagedRadius))
		{
			FailGate(FString::Printf(
				TEXT("TheHallIsNotYoursToRewire: %s carries a %.2f cm ring at t=%.2f s "
					 "and the hall painted %.2f. The size of a ring is not yours"),
				*M.Label, M.Radius, Now, M.StagedRadius));
			return false;
		}
		if (FVector::Dist(M.At, M.StagedAt) > kMovedUu)
		{
			FailGate(FString::Printf(
				TEXT("TheHallIsNotYoursToRewire: %s has moved %.1f cm from where the "
					 "hall put it, by t=%.2f s. Do not move the marks"),
				*M.Label, FVector::Dist(M.At, M.StagedAt), Now));
			return false;
		}
	}
	TArray<FName> LiveList;
	if (!ReadNameArray(Board.Get(), TEXT("ListedMarkNames"), LiveList))
	{
		FailGate(FString::Printf(
			TEXT("TheHallIsNotYoursToRewire: the board's list cannot be read at "
				 "t=%.2f s"), Now));
		return false;
	}
	if (LiveList != StagedList)
	{
		FString Was;
		FString Is;
		for (const FName& N : StagedList)
		{
			Was += FString::Printf(TEXT("%s%s"), Was.IsEmpty() ? TEXT("") : TEXT(">"),
				*N.ToString());
		}
		for (const FName& N : LiveList)
		{
			Is += FString::Printf(TEXT("%s%s"), Is.IsEmpty() ? TEXT("") : TEXT(">"),
				*N.ToString());
		}
		FailGate(FString::Printf(
			TEXT("TheHallIsNotYoursToRewire: the board's list reads [%s] at t=%.2f s "
				 "and the hall wrote [%s]. The board's list is not yours to change"),
			*Is, Now, *Was));
		return false;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateWrongStepEmpties(double Now)
{
	if (OutOfTurnMark == INDEX_NONE || !Marks.IsValidIndex(OutOfTurnMark))
	{
		return true;
	}
	const double Since = Now - OutOfTurnAt;
	if (Since < kWrongStepFromS || Since > kWrongStepToS)
	{
		return true;
	}
	// THE CLAIM EXPIRES WHEN THE STAND DOES. While the character is standing on the
	// mark they stepped onto out of turn, nothing in the hall can legitimately bank --
	// so every bank must read zero. Once they step off, a legitimate bank may start
	// again and this window would false-FAIL a correct answer.
	if (OccupiedLast != OutOfTurnMark)
	{
		return true;
	}
	// DEFENCE IN DEPTH, and redundant by construction: OutOfTurnMark is cleared in the
	// same breath as PoisonedMark the moment the stand ends. It is written down because
	// when it was NOT redundant this gate stayed armed on the last mark anybody ever
	// stepped onto out of turn and fired on four separate LEGITIMATE stands, so the
	// reference could never pass. If the two ever disagree again, stand down rather
	// than fail.
	if (PoisonedMark != OutOfTurnMark)
	{
		return true;
	}
	if (StagingSuppressed(Now))
	{
		return true;
	}

	const FMark& Stepped = Marks[OutOfTurnMark];
	const FName WhoseTurn = StagedList.IsValidIndex(OutOfTurnDisplacedTurn)
		? StagedList[OutOfTurnDisplacedTurn] : NAME_None;
	const TCHAR* const Half = bOutOfTurnAhead
		? TEXT("a name the board carries LATER in its list, which has not been the "
			   "mark whose turn it is at any point in this round")
		: TEXT("a name the board has already seen finished in this round");

	FString Standing;
	for (const FMark& M : Marks)
	{
		if (IndexInModelList(M.Name) == INDEX_NONE)
		{
			continue;
		}
		double B = 0.0;
		double R = 0.0;
		if (!ReadFace(M, B, R))
		{
			FailGate(FString::Printf(
				TEXT("AWrongStepEmptiesEveryClock: %.2f s after somebody stepped onto "
					 "%s out of turn (it was %s's turn), %s's face has never been "
					 "written at all. A wrong step empties every named mark's bank to "
					 "zero, darkens every named lamp and puts the tally back to none of "
					 "%d -- and every one of those has to be SHOWN"),
				Since, *Stepped.Label, *WhoseTurn.ToString(), *M.Label,
				ModelList.Num()));
			return false;
		}
		if (FMath::Abs(B) > kFaceLagS)
		{
			Standing += FString::Printf(TEXT("%s%s=%.2f"),
				Standing.IsEmpty() ? TEXT("") : TEXT(", "), *M.Label, B);
		}
		if (FMath::Abs(R - M.Required) > kRequiredEps)
		{
			FailGate(FString::Printf(
				TEXT("AWrongStepEmptiesEveryClock: %.2f s after the wrong step onto %s, "
					 "%s's face reads its number as %.2f and the mark carries %.2f"),
				Since, *Stepped.Label, *M.Label, R, M.Required));
			return false;
		}
		const double I = LampIntensity(M);
		if (I >= kLampDarkCeil)
		{
			FailGate(FString::Printf(
				TEXT("AWrongStepEmptiesEveryClock: %.2f s after somebody stepped onto "
					 "%s out of turn (it was %s's turn), %s's lamp is still burning at "
					 "%.0f. Every named mark goes dark at that moment"),
				Since, *Stepped.Label, *WhoseTurn.ToString(), *M.Label, I));
			return false;
		}
	}
	if (!Standing.IsEmpty())
	{
		FailGate(FString::Printf(
			TEXT("AWrongStepEmptiesEveryClock: %.2f s after somebody stepped onto %s "
				 "out of turn (it was %s's turn, and %s is %s), these banks are still "
				 "standing: %s. A step onto any other mark the board names starts the "
				 "WHOLE round over at that moment -- every named mark's bank, not just "
				 "the one stepped on, and at the step, not at the end. BOTH kinds of "
				 "name do it: one that comes later in the list, and one already "
				 "finished"),
			Since, *Stepped.Label, *WhoseTurn.ToString(), *Stepped.Label, Half,
			*Standing));
		return false;
	}
	int32 F = 0;
	int32 L = 0;
	if (!ReadTally(F, L))
	{
		FailGate(FString::Printf(
			TEXT("AWrongStepEmptiesEveryClock: %.2f s after the wrong step onto %s the "
				 "board's tally face has never been written; it has to read none of %d"),
			Since, *Stepped.Label, ModelList.Num()));
		return false;
	}
	if (F != 0 || L != ModelList.Num())
	{
		FailGate(FString::Printf(
			TEXT("AWrongStepEmptiesEveryClock: %.2f s after somebody stepped onto %s "
				 "out of turn the board reads %d/%d; the round started over at that "
				 "moment, so it reads 0/%d"),
			Since, *Stepped.Label, F, L, ModelList.Num()));
		return false;
	}
	if (WrongStepJudged < OutOfTurnCount)
	{
		++WrongStepJudged;
	}
	// THE TWO HALVES ARE COUNTED SEPARATELY, and the run-level gate demands two of
	// each. A drive that only ever steps BACKWARDS onto a finished name leaves the
	// skip-ahead branch of the rule completely ungated, which is exactly the state this
	// task shipped in before 2026-08-19.
	if (bOutOfTurnAhead)
	{
		if (SkipAheadJudged < SkipAheadCount)
		{
			++SkipAheadJudged;
		}
	}
	else if (FinishedStepJudged < FinishedStepCount)
	{
		++FinishedStepJudged;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateOutOfTurnBanksNothing(double Now)
{
	if (OutOfTurnMark == INDEX_NONE || !Marks.IsValidIndex(OutOfTurnMark))
	{
		return true;
	}
	const double Since = Now - OutOfTurnAt;
	if (Since < kOutOfTurnFromS)
	{
		return true;
	}
	if (OccupiedLast != OutOfTurnMark)
	{
		return true;
	}
	// Redundant by construction, for the same reason as in the gate above: this claim
	// belongs to the POISONED stand and dies with it.
	if (PoisonedMark != OutOfTurnMark)
	{
		return true;
	}
	if (StagingSuppressed(Now))
	{
		return true;
	}
	const FMark& M = Marks[OutOfTurnMark];
	double B = 0.0;
	double R = 0.0;
	if (!ReadFace(M, B, R))
	{
		FailGate(FString::Printf(
			TEXT("StandingOutOfTurnBanksNothing: %.2f s of standing on %s after "
				 "stepping onto it out of turn, and its face has never been written"),
			Since, *M.Label));
		return false;
	}
	if (FMath::Abs(B) > kFaceLagS)
	{
		FailGate(FString::Printf(
			TEXT("StandingOutOfTurnBanksNothing: %s reads %.2f of %.2f after %.2f s of "
				 "standing on it. It was stepped onto OUT OF TURN, and a mark stepped "
				 "on out of turn banks nothing at all however long anybody stands on "
				 "it -- even though the round starting over has since made it the mark "
				 "whose turn it is"),
			*M.Label, B, R, Since));
		return false;
	}
	const double I = LampIntensity(M);
	if (I >= kLampDarkCeil)
	{
		FailGate(FString::Printf(
			TEXT("StandingOutOfTurnBanksNothing: %s's lamp is burning at %.0f after "
				 "%.2f s of standing on a mark that was stepped onto out of turn"),
			*M.Label, I, Since));
		return false;
	}
	int32 F = 0;
	int32 L = 0;
	if (ReadTally(F, L) && F != 0)
	{
		FailGate(FString::Printf(
			TEXT("StandingOutOfTurnBanksNothing: the board reads %d/%d after %.2f s of "
				 "standing on %s, which was stepped onto out of turn; nothing has been "
				 "finished since the round started over"),
			F, L, Since, *M.Label));
		return false;
	}
	if (OutOfTurnJudged < OutOfTurnCount)
	{
		++OutOfTurnJudged;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateListChangeRestarts(double Now)
{
	if (ListChangeCount == 0)
	{
		return true;
	}
	const double Since = Now - ListChangedAt;
	if (Since < kListChangeFromS || Since > kListChangeToS)
	{
		return true;
	}
	if (StagingSuppressed(Now))
	{
		return true;
	}
	for (const FMark& M : Marks)
	{
		double B = 0.0;
		double R = 0.0;
		if (!ReadFace(M, B, R))
		{
			FailGate(FString::Printf(
				TEXT("TheRoundStartsOverWhenTheListChanges: %.2f s after the board "
					 "started carrying a different list, %s's face has never been "
					 "written. When the list changes the round starts over: every bank "
					 "empties, every lamp goes dark, and the tally reads none of "
					 "however many names the NEW list carries (%d)"),
				Since, *M.Label, ModelList.Num()));
			return false;
		}
		if (FMath::Abs(B) > kFaceLagS)
		{
			FailGate(FString::Printf(
				TEXT("TheRoundStartsOverWhenTheListChanges: %.2f s after the board "
					 "started carrying a different list, %s still reads %.2f of %.2f. "
					 "A new list starts the round over -- every bank empties, including "
					 "the one somebody is standing in"),
				Since, *M.Label, B, R));
			return false;
		}
		if (FMath::Abs(R - M.Required) > kRequiredEps)
		{
			FailGate(FString::Printf(
				TEXT("TheRoundStartsOverWhenTheListChanges: %.2f s after the new list, "
					 "%s's face reads its number as %.2f and the mark now carries "
					 "%.2f. The numbers moved in the same breath as the list, and a "
					 "number read once and kept is wrong"),
				Since, *M.Label, R, M.Required));
			return false;
		}
		const double I = LampIntensity(M);
		if (I >= kLampDarkCeil)
		{
			FailGate(FString::Printf(
				TEXT("TheRoundStartsOverWhenTheListChanges: %.2f s after the new list, "
					 "%s's lamp is still burning at %.0f"), Since, *M.Label, I));
			return false;
		}
	}
	int32 F = 0;
	int32 L = 0;
	if (!ReadTally(F, L))
	{
		FailGate(FString::Printf(
			TEXT("TheRoundStartsOverWhenTheListChanges: %.2f s after the new list the "
				 "board's tally face has never been written; it has to read 0/%d"),
			Since, ModelList.Num()));
		return false;
	}
	if (F != 0 || L != ModelList.Num())
	{
		FailGate(FString::Printf(
			TEXT("TheRoundStartsOverWhenTheListChanges: %.2f s after the board started "
				 "carrying a list of %d names, its tally reads %d/%d. It has to read "
				 "0/%d -- the round starts over, and the right-hand number is however "
				 "many names the board is carrying NOW, not a constant"),
			Since, ModelList.Num(), F, L, ModelList.Num()));
		return false;
	}
	if (ListChangeJudged < ListChangeCount)
	{
		++ListChangeJudged;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateBankStillThere(double Now)
{
	if (ReEntryMark == INDEX_NONE || !Marks.IsValidIndex(ReEntryMark))
	{
		return true;
	}
	const double Since = Now - ReEntryAt;
	if (Since < 0.0 || Since > kReEntryWindowS)
	{
		return true;
	}
	if (OccupiedLast != ReEntryMark || StagingSuppressed(Now))
	{
		return true;
	}
	// DELIBERATELY EXEMPT FROM THE SETTLE AND CROSSING SUPPRESSION, because the event
	// that arms this gate IS a crossing and IS a model state change -- suppressing it
	// would leave the window empty. It is safe to do because the bound is ONE-SIDED: a
	// frame of staleness can only make the face read the value it held before the
	// re-entry, which is exactly the value this gate demands.
	const FMark& M = Marks[ReEntryMark];
	double B = 0.0;
	double R = 0.0;
	if (!ReadFace(M, B, R))
	{
		FailGate(FString::Printf(
			TEXT("TheBankIsStillThereWhenYouComeBack: %s was left with %.2f banked and "
				 "%.2f s after stepping back onto it its face has never been written"),
			*M.Label, ReEntryPreserved, Since));
		return false;
	}
	const double Floor = ReEntryPreserved - FaceTolerance(M);
	if (B < Floor)
	{
		FailGate(FString::Printf(
			TEXT("TheBankIsStillThereWhenYouComeBack: %s held %.2f banked when somebody "
				 "stepped off it, and %.2f s after they stepped back on its face reads "
				 "%.2f of %.2f. Stepping off PAUSES a bank; it does not empty it, and "
				 "stepping back on carries on from the value it stopped at"),
			*M.Label, ReEntryPreserved, Since, B, R));
		return false;
	}
	if (StillThereJudged < ReEntryCount)
	{
		++StillThereJudged;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateBankPicksUp(double Now)
{
	if (ReEntryMark == INDEX_NONE || !Marks.IsValidIndex(ReEntryMark))
	{
		return true;
	}
	const double Since = Now - ReEntryAt;
	if (Since <= kReEntryWindowS)
	{
		return true;
	}
	const FMark& M = Marks[ReEntryMark];
	if (M.bFinished || OccupiedLast != ReEntryMark)
	{
		return true;
	}
	if (StagingSuppressed(Now) || EdgeSuppressed(Now))
	{
		return true;
	}
	double B = 0.0;
	double R = 0.0;
	if (!ReadFace(M, B, R))
	{
		FailGate(FString::Printf(
			TEXT("TheBankPicksUpFromWhereItStopped: %s's face has never been written, "
				 "%.2f s into a stand that resumed from %.2f banked"),
			*M.Label, Since, ReEntryPreserved));
		return false;
	}
	const double Tol = FaceTolerance(M);
	if (FMath::Abs(B - M.Bank) > Tol)
	{
		FailGate(FString::Printf(
			TEXT("TheBankPicksUpFromWhereItStopped: %s was paused at %.2f, has been "
				 "stood on for %.2f s since, and its face reads %.2f where %.2f is "
				 "owed (tolerance %.2f). A resumed bank carries on from the value it "
				 "stopped at -- it does not restart from nothing, and it does not "
				 "count the time nobody was standing there"),
			*M.Label, ReEntryPreserved, Since, B, M.Bank, Tol));
		return false;
	}
	if (FMath::Abs(R - M.Required) > kRequiredEps)
	{
		FailGate(FString::Printf(
			TEXT("TheBankPicksUpFromWhereItStopped: %s's face reads its number as %.2f "
				 "and the mark carries %.2f, %.2f s into the resumed stand"),
			*M.Label, R, M.Required, Since));
		return false;
	}
	int32 F = 0;
	int32 L = 0;
	if (ReadTally(F, L) && (F != ModelFinishedCount() || L != ModelList.Num()))
	{
		FailGate(FString::Printf(
			TEXT("TheBankPicksUpFromWhereItStopped: the board reads %d/%d %.2f s into "
				 "the resumed stand on %s, and %d of %d have been finished. Nothing "
				 "finishes while a bank is still climbing"),
			F, L, Since, *M.Label, ModelFinishedCount(), ModelList.Num()));
		return false;
	}
	if (PicksUpJudged < ReEntryCount)
	{
		++PicksUpJudged;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateBankHoldsAway(double Now)
{
	if (AwayMark == INDEX_NONE || !Marks.IsValidIndex(AwayMark))
	{
		return true;
	}
	if ((Now - AwaySinceAt) < kAwayArmS || StagingSuppressed(Now))
	{
		return true;
	}
	if (!bAwaySampled)
	{
		AwaySampleFace.Init(-1.0, Marks.Num());
		for (int32 i = 0; i < Marks.Num(); ++i)
		{
			double B = 0.0;
			double R = 0.0;
			if (!ReadFace(Marks[i], B, R))
			{
				FailGate(FString::Printf(
					TEXT("TheBankHoldsWhileYouAreAway: %.2f s after somebody stepped "
						 "off %s with %.2f banked, %s's face has never been written"),
					Now - AwaySinceAt, *Marks[AwayMark].Label, Marks[AwayMark].Bank,
					*Marks[i].Label));
				return false;
			}
			AwaySampleFace[i] = B;
		}
		int32 F = 0;
		int32 L = 0;
		if (!ReadTally(F, L))
		{
			FailGate(FString::Printf(
				TEXT("TheBankHoldsWhileYouAreAway: %.2f s after somebody stepped off "
					 "%s the board's tally face has never been written"),
				Now - AwaySinceAt, *Marks[AwayMark].Label));
			return false;
		}
		// The control's own watch is gate 9's and is deliberately NOT touched here.
		bAwaySampled = true;
		bAwayArmed = true;
		if (AwayJudged < AwayCount)
		{
			++AwayJudged;
		}
		return true;
	}
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		if (IndexInModelList(Marks[i].Name) == INDEX_NONE)
		{
			continue;   // the control and any demoted mark are gate 9's and gate 10's
		}
		double B = 0.0;
		double R = 0.0;
		if (!ReadFace(Marks[i], B, R))
		{
			FailGate(FString::Printf(
				TEXT("TheBankHoldsWhileYouAreAway: %s's face stopped reading anything "
					 "while nobody was standing on any mark"), *Marks[i].Label));
			return false;
		}
		if (!AwaySampleFace.IsValidIndex(i))
		{
			continue;
		}
		const double Drift = B - AwaySampleFace[i];
		if (FMath::Abs(Drift) > kAwayDriftS)
		{
			if (i == AwayMark)
			{
				FailGate(FString::Printf(
					TEXT("TheBankHoldsWhileYouAreAway: %s read %.2f when the wait "
						 "began and reads %.2f now, %.2f s after somebody stepped off "
						 "it with nobody standing on any mark since. A paused bank does "
						 "not move"),
					*Marks[i].Label, AwaySampleFace[i], B, Now - AwaySinceAt));
			}
			else
			{
				FailGate(FString::Printf(
					TEXT("TheBankHoldsWhileYouAreAway: %s read %.2f when the wait began "
						 "and reads %.2f now, and nobody has been standing on it at "
						 "all. Only the mark whose turn it is banks anything, and only "
						 "while somebody is standing in it"),
					*Marks[i].Label, AwaySampleFace[i], B));
			}
			return false;
		}
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateWaitsForItsOwnNumber(double Now)
{
	// ---- (a) THE DEFERRED CHECK, one per modelled completion. --------------------
	for (FCompletion& C : Completions)
	{
		if (C.bChecked || Now < C.At + kCompletionCheckS
			|| !Marks.IsValidIndex(C.Mark))
		{
			continue;
		}
		C.bChecked = true;
		// RoundStartedOverAt, not OutOfTurnAt: the latter dies with the stand it
		// belongs to, so a character who stepped off before this check landed would
		// have made the wipe invisible here and a correct submission would have been
		// charged for a completion it was RIGHT to throw away.
		if (RoundStartedOverAt > C.At)
		{
			// The round started over inside the window. Nothing can be claimed about a
			// completion the hall was right to have thrown away.
			UE_LOG(LogTemp, Display,
				TEXT("[t3-marks] completion of %s at t=%.2f not judged: the round "
					 "started over inside its window"), *Marks[C.Mark].Label, C.At);
			continue;
		}
		const FMark& M = Marks[C.Mark];
		// NAMED IN THE MESSAGE, because it is the whole difference between the two
		// implementations this half of the gate separates: a finish test that runs
		// every frame, and one nested inside "somebody is standing here and banking".
		const TCHAR* const Alone = C.bNobodyStanding
			? TEXT(", with NOBODY standing on any mark at that moment -- its number was "
				   "dropped below what it had already banked while the character was "
				   "parked clear of every ring")
			: TEXT("");
		const double I = LampIntensity(M);
		if (I < kLampLitFloor)
		{
			FailGate(FString::Printf(
				TEXT("AMarkWaitsForItsOwnNumber: %s reached its own number of %.2f "
					 "seconds at t=%.2f%s (its number then was %.2f and it reads %.2f "
					 "now) and %.2f s later its lamp is at %.0f. A mark is finished the "
					 "moment its bank reaches whatever its number says AT THAT MOMENT, "
					 "and a finished mark burns at least %.0f"),
				*M.Label, C.RequiredThen, C.At, Alone, C.RequiredThen, M.Required,
				kCompletionCheckS, I, kLampLitFloor));
			return false;
		}
		int32 F = 0;
		int32 L = 0;
		if (!ReadTally(F, L))
		{
			FailGate(FString::Printf(
				TEXT("AMarkWaitsForItsOwnNumber: %s finished at t=%.2f against its own "
					 "number of %.2f and the board's tally face has never been written"),
				*M.Label, C.At, C.RequiredThen));
			return false;
		}
		if (F != ModelFinishedCount() || L != ModelList.Num())
		{
			FailGate(FString::Printf(
				TEXT("AMarkWaitsForItsOwnNumber: %s finished at t=%.2f%s against its "
					 "own number of %.2f (it now carries %.2f), and %.2f s later the "
					 "board reads %d/%d where %d/%d is owed. When a mark finishes the "
					 "turn moves on to the next name and the tally rises by exactly "
					 "one"),
				*M.Label, C.At, Alone, C.RequiredThen, M.Required, kCompletionCheckS, F,
				L, ModelFinishedCount(), ModelList.Num()));
			return false;
		}
		double B = 0.0;
		double R = 0.0;
		if (!ReadFace(M, B, R))
		{
			FailGate(FString::Printf(
				TEXT("AMarkWaitsForItsOwnNumber: %s finished at t=%.2f and its face has "
					 "never been written"), *M.Label, C.At));
			return false;
		}
		const double Tol = FaceTolerance(M);
		// A finished mark stands at its own number. A submission that does not clamp
		// the bank back to the number shows the value it over-ran to instead, which is
		// a real and defensible reading of the same instant, so BOTH are accepted --
		// and neither of them can be produced by any of the named wrong answers.
		if (FMath::Abs(B - M.RequiredAtFinish) > Tol
			&& FMath::Abs(B - M.BankAtFinish) > Tol)
		{
			FailGate(FString::Printf(
				TEXT("AMarkWaitsForItsOwnNumber: %s finished at t=%.2f against its own "
					 "number of %.2f with %.2f banked, and its face reads %.2f of %.2f "
					 "%.2f s later. A finished mark stands at its own number"),
				*M.Label, C.At, M.RequiredAtFinish, M.BankAtFinish, B, R,
				kCompletionCheckS));
			return false;
		}
		if (CompletionJudged < Completions.Num())
		{
			++CompletionJudged;
		}
		if (C.bNobodyStanding && AwayCompletionJudged < AwayCompletionCount)
		{
			++AwayCompletionJudged;
		}
	}

	// ---- (b) THE EARLY ARM: a number cached when the stand began. ----------------
	// The fixture RAISES a mark's number while somebody is standing on it. A submission
	// that read the number at the start of the stand finishes the mark when the bank
	// passes the OLD value, which is before the mark is finished at all.
	if (StagingSuppressed(Now) || !ModelList.IsValidIndex(Turn))
	{
		return true;
	}
	const int32 Mi = MarkIndexNamed(ModelList[Turn]);
	if (Mi == INDEX_NONE)
	{
		return true;
	}
	const FMark& M = Marks[Mi];
	if (M.bFinished || M.RewrittenAt < 0.0 || M.PreviousRequired >= M.Required
		|| !M.bHasBank || M.Bank < M.PreviousRequired - 0.10)
	{
		return true;
	}
	const double I = LampIntensity(M);
	int32 F = 0;
	int32 L = 0;
	const bool bTally = ReadTally(F, L);
	if (I >= kLampLitFloor || (bTally && F > ModelFinishedCount()))
	{
		FailGate(FString::Printf(
			TEXT("AMarkWaitsForItsOwnNumber: %s carried %.2f seconds when somebody "
				 "started standing on it and carries %.2f now, it has %.2f banked, and "
				 "at t=%.2f the hall already shows it finished (lamp %.0f, tally %d/%d "
				 "where %d/%d is owed). A mark is finished as soon as its bank reaches "
				 "whatever its number says AT THAT MOMENT, so a number raised mid-stand "
				 "means standing longer"),
			*M.Label, M.PreviousRequired, M.Required, M.Bank, Now, I,
			bTally ? F : -1, bTally ? L : -1, ModelFinishedCount(), ModelList.Num()));
		return false;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateUnnamedStaysCold(double Now)
{
	if (!Marks.IsValidIndex(IdxControl))
	{
		return true;
	}
	const FMark& C = Marks[IdxControl];
	double B = 0.0;
	double R = 0.0;
	if (!ReadFace(C, B, R))
	{
		FailGate(FString::Printf(
			TEXT("TheUnnamedMarkStaysCold: %s is the one mark the board never names, "
				 "and at t=%.2f s its face has never been written. A mark the board "
				 "does not name is still a mark: it reads none of its own %.2f seconds"),
			*C.Label, Now, C.Required));
		return false;
	}
	if (FMath::Abs(B) > kFaceLagS)
	{
		FailGate(FString::Printf(
			TEXT("TheUnnamedMarkStaysCold: %s reads %.2f of %.2f at t=%.2f s. Neither "
				 "list ever names it, the route has walked straight through its ring "
				 "%d time(s), and standing on a mark the board does not name banks "
				 "nothing, lights nothing and disturbs nothing"),
			*C.Label, B, R, Now, C.CrossingsTotal));
		return false;
	}
	if (!StagingSuppressed(Now) && FMath::Abs(R - C.Required) > kRequiredEps)
	{
		FailGate(FString::Printf(
			TEXT("TheUnnamedMarkStaysCold: %s's face reads its number as %.2f at "
				 "t=%.2f s and the mark carries %.2f"), *C.Label, R, Now, C.Required));
		return false;
	}
	const double I = LampIntensity(C);
	if (I >= kLampDarkCeil)
	{
		FailGate(FString::Printf(
			TEXT("TheUnnamedMarkStaysCold: %s's lamp is burning at %.0f at t=%.2f s and "
				 "the board has never named it. Only a finished mark burns"),
			*C.Label, I, Now));
		return false;
	}

	// THE CROSSING CLAIM. Walking through the unnamed mark's ring is the plausible
	// reading of "the order is the board's" that has to be wrong: an implementation
	// that treats every mark other than the current one as an out-of-turn step wipes
	// the hall here. Nothing in the model moves across a crossing, so the tally the
	// hall showed when the character entered has to be the tally it shows when they
	// leave. Every mark's OWN bank across the same window is gate 10's business.
	if (bControlWatchOpen && !bControlWatchModelMoved && ControlWatchTally >= 0)
	{
		int32 F = 0;
		int32 L = 0;
		if (ReadTally(F, L) && (F != ControlWatchTally || L != ControlWatchLength))
		{
			FailGate(FString::Printf(
				TEXT("TheUnnamedMarkStaysCold: the board read %d/%d when the character "
					 "walked into %s's ring and reads %d/%d now. %s is on neither list, "
					 "so crossing it leaves every other mark's bank exactly as it was "
					 "and never starts the round over"),
				ControlWatchTally, ControlWatchLength, *C.Label, F, L, *C.Label));
			return false;
		}
		if (ControlWatchClosesAt > 0.0 && Now >= ControlWatchClosesAt)
		{
			bControlWatchOpen = false;
		}
	}
	else if (bControlWatchOpen && ControlWatchClosesAt > 0.0 && Now >= ControlWatchClosesAt)
	{
		bControlWatchOpen = false;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateEveryFace(double Now)
{
	for (const FMark& M : Marks)
	{
		double B = 0.0;
		double R = 0.0;
		if (!ReadFace(M, B, R))
		{
			FailGate(FString::Printf(
				TEXT("EveryFaceReadsItsOwnBank: at t=%.2f s %s's face has never been "
					 "written at all. Every mark's face reads its own banked seconds "
					 "and its own number, one decimal each, from the start of a round "
					 "onward -- %s should read 0.0 of %.1f right now"),
				Now, *M.Label, *M.Label, M.Required));
			return false;
		}
		const double Tol = FaceTolerance(M);
		bool bOk = FMath::Abs(B - M.Bank) <= Tol;
		if (!bOk && M.bFinished)
		{
			bOk = FMath::Abs(B - M.BankAtFinish) <= Tol;
		}
		if (!bOk)
		{
			FailGate(FString::Printf(
				TEXT("EveryFaceReadsItsOwnBank: at t=%.2f s %s reads %.2f of %.2f and "
					 "%.2f is banked on it (tolerance %.2f; the mark is %s and the turn "
					 "is name %d of %d). %s"),
				Now, *M.Label, B, R, M.Bank, Tol,
				M.bFinished ? TEXT("finished") : TEXT("unfinished"),
				ModelFinishedCount() + 1, ModelList.Num(), *DescribeShownFaces()));
			return false;
		}
		if (!StagingSuppressed(Now) && FMath::Abs(R - M.Required) > kRequiredEps)
		{
			FailGate(FString::Printf(
				TEXT("EveryFaceReadsItsOwnBank: at t=%.2f s %s's face reads its number "
					 "as %.2f and the mark carries %.2f. Each mark's face reads ITS OWN "
					 "number as that number reads at that moment -- not a shared "
					 "constant and not the value it had when somebody arrived"),
				Now, *M.Label, R, M.Required));
			return false;
		}
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateBoardTally(double Now)
{
	int32 F = 0;
	int32 L = 0;
	if (!ReadTally(F, L))
	{
		FailGate(FString::Printf(
			TEXT("TheBoardShowsHowFarYouGot: at t=%.2f s the board's tally face has "
				 "never been written. It reads how many of the board's marks are "
				 "finished out of how many names the board is carrying, and a round "
				 "that has begun reads 0/%d"),
			Now, ModelList.Num()));
		return false;
	}
	if (F != ModelFinishedCount() || L != ModelList.Num())
	{
		FailGate(FString::Printf(
			TEXT("TheBoardShowsHowFarYouGot: at t=%.2f s the board reads %d/%d and "
				 "%d of %d are finished. The left-hand number is how many of the "
				 "board's marks are finished in this round and the right-hand number "
				 "is how many names the board is carrying NOW; it never reads the full "
				 "count before the last name has been finished in its turn. %s"),
			Now, F, L, ModelFinishedCount(), ModelList.Num(), *DescribeShownFaces()));
		return false;
	}
	return true;
}

bool AMarkOrderFunctionalTest::GateLamps(double Now)
{
	for (const FMark& M : Marks)
	{
		// A PER-MARK settle grace, not a whole-gate suppression: only the mark whose
		// finished-ness has just moved is excused, and only for as long as the prompt
		// promises the hall to catch up. Every other lamp is graded on this frame.
		if ((Now - M.FinishedChangedAt) < kSuppressS)
		{
			continue;
		}
		const double I = LampIntensity(M);
		if (I < 0.0)
		{
			FailGate(FString::Printf(
				TEXT("EveryLampBurnsOnlyForAFinishedMark: %s has no light on it at all "
					 "at t=%.2f s. Every mark ships a lamp on a mast and the job is to "
					 "decide when to throw it"), *M.Label, Now));
			return false;
		}
		if (M.bFinished && I < kLampLitFloor)
		{
			FailGate(FString::Printf(
				TEXT("EveryLampBurnsOnlyForAFinishedMark: %s has been finished since "
					 "t=%.2f and its lamp reads %.0f at t=%.2f s. A finished mark keeps "
					 "its lamp at least %.0f bright until the round starts over"),
				*M.Label, M.FinishedAt, I, Now, kLampLitFloor));
			return false;
		}
		if (!M.bFinished && I >= kLampDarkCeil)
		{
			FailGate(FString::Printf(
				TEXT("EveryLampBurnsOnlyForAFinishedMark: %s is not finished (%.2f "
					 "banked of %.2f, and it is name %d on a list of %d) and its lamp "
					 "reads %.0f at t=%.2f s. A lamp is dark until its own mark is "
					 "finished"),
				*M.Label, M.Bank, M.Required, IndexInModelList(M.Name) + 1,
				ModelList.Num(), I, Now));
			return false;
		}
	}
	return true;
}

bool AMarkOrderFunctionalTest::AnyWindowArmed(double Now) const
{
	// The SAME triple of conditions gates 2 and 3 arm on, including the poison guard.
	// Without it -- back when OutOfTurnMark outlived the stand -- this returned true
	// for the whole of every later legitimate stand on that mark, which switched off
	// the per-mark face channel and the tally on precisely the frames a mis-scoped wipe
	// or a stale denominator shows up. Suppression has to be exactly as wide as the
	// sharper gate that replaces it, and never wider.
	if (OutOfTurnMark != INDEX_NONE && OccupiedLast == OutOfTurnMark
		&& PoisonedMark == OutOfTurnMark
		&& (Now - OutOfTurnAt) >= kWrongStepFromS)
	{
		return true;
	}
	if (ListChangeCount > 0)
	{
		const double Since = Now - ListChangedAt;
		if (Since >= kListChangeFromS && Since <= kListChangeToS)
		{
			return true;
		}
	}
	if (ReEntryMark != INDEX_NONE && OccupiedLast == ReEntryMark
		&& Marks.IsValidIndex(ReEntryMark) && !Marks[ReEntryMark].bFinished)
	{
		return true;
	}
	if (AwayMark != INDEX_NONE && (Now - AwaySinceAt) >= kAwayArmS)
	{
		return true;
	}
	for (const FCompletion& C : Completions)
	{
		if (Now >= C.At - kCompletionWindowS && Now <= C.At + kCompletionWindowS)
		{
			return true;
		}
	}
	return false;
}

bool AMarkOrderFunctionalTest::RunLevelGate(double Now, bool bAtSentinel)
{
	bRunLevelDone = true;

	// THE HARNESS SELF-CHECK FIRST. Every window in this fixture arms on a MODEL event,
	// so a short count can only mean the DRIVE failed to produce the event -- never
	// that the submission did anything. It is attributed, not scored, and
	// AttributeOverrun re-checks gates 1, 9 and 12 before it writes anything off.
	// TWO OF EVERY TRIGGER, AND TWO OF EVERY BRANCH OF EVERY TRIGGER. The last three
	// counters exist because a rule whose drive only exercises one of its two branches
	// is an UNGATED rule however loudly the prompt states it, and this fixture shipped
	// with exactly three such branches: an out-of-turn step onto a name that is not due
	// yet (every out-of-turn step in the run landed on a name already finished, at list
	// index 0), a completion with nobody standing anywhere, and a list replacement that
	// keeps the length.
	if (WrongStepJudged < 2 || OutOfTurnJudged < 2 || StillThereJudged < 2
		|| PicksUpJudged < 2 || AwayJudged < 2 || CompletionJudged < 2
		|| ListChangeJudged < 2 || ControlCrossings < 2
		|| SkipAheadJudged < 2 || FinishedStepJudged < 2 || AwayCompletionJudged < 2)
	{
		AttributeOverrun(Now, FString::Printf(
			TEXT("the drive did not produce two of every trigger it is built to "
				 "produce: wrong-step %d, standing-out-of-turn %d, come-back %d, "
				 "picks-up %d, away %d, completion %d, list-change %d, control "
				 "crossings %d, stepped-ahead-of-the-turn %d, stepped-onto-a-finished-"
				 "name %d, finished-with-nobody-standing %d"),
			WrongStepJudged, OutOfTurnJudged, StillThereJudged, PicksUpJudged,
			AwayJudged, CompletionJudged, ListChangeJudged, ControlCrossings,
			SkipAheadJudged, FinishedStepJudged, AwayCompletionJudged));
		return false;
	}

	if (!bShownFullRoundOne)
	{
		FailGate(FString::Printf(
			TEXT("TheHallDidItTwice: by t=%.2f s the board has never read the full "
				 "count of the first list it was carrying. A round has to be able to be "
				 "finished, and then to happen again%s"),
			Now, bAtSentinel ? TEXT(" (reached at the sentinel)") : TEXT("")));
		return false;
	}
	if (!bShownZeroBetween)
	{
		FailGate(FString::Printf(
			TEXT("TheHallDidItTwice: the board reached %d/%d and never went back to "
				 "none by t=%.2f s. None of this is one-shot: a wrong step and a new "
				 "list each start the whole round over"),
			ShownFullLengthOne, ShownFullLengthOne, Now));
		return false;
	}
	if (!bShownFullRoundTwo)
	{
		FailGate(FString::Printf(
			TEXT("TheHallDidItTwice: the board reached %d/%d in the first round and "
				 "never reached the full count of the second list by t=%.2f s. A round "
				 "that has been finished has to be able to happen again, on a new list "
				 "of a different length"),
			ShownFullLengthOne, ShownFullLengthOne, Now));
		return false;
	}
	if (ShownFullLengthOne == ShownFullLengthTwo)
	{
		FailGate(FString::Printf(
			TEXT("TheHallDidItTwice: both full counts read out of %d. The board carried "
				 "%d names and then %d, so the right-hand number is not a constant"),
			ShownFullLengthOne, StagedList.Num(), ShownFullLengthTwo));
		return false;
	}

	FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
		TEXT("The hall held the marks in the order given: two full rounds on lists of "
			 "%d and %d names with the board back to none in between, %d out-of-turn "
			 "steps each emptying every clock (%d onto a name not due yet, %d onto a "
			 "name already finished), %d pause-and-resume pairs, %d completions judged "
			 "against the number the mark carried at that instant of which %d landed "
			 "with nobody standing on any mark, one list replaced mid-stand and one "
			 "replaced by the same names in a different order, and %d walks straight "
			 "through a mark the board never named that changed nothing at all "
			 "(%.0f s of world time)"),
		ShownFullLengthOne, ShownFullLengthTwo, OutOfTurnCount, SkipAheadCount,
		FinishedStepCount, ReEntryCount, CompletionJudged, AwayCompletionJudged,
		ControlCrossings, Now));
	return true;
}

void AMarkOrderFunctionalTest::AttributeOverrun(double Now, const FString& What)
{
	// A HARNESS EXIT CAN NEVER LAUNDER A FAIL. Every adaptive step in this drive ends
	// on a condition the FIXTURE'S OWN MODEL reaches, so a submission cannot stall it
	// -- but a submission CAN re-write the hall into a shape where a walk never
	// arrives, and that is a graded failure. These three are re-checked
	// unconditionally, before anything is written off as staging.
	if (!GateHallNotRewired(Now))
	{
		return;
	}
	if (!GateUnnamedStaysCold(Now))
	{
		return;
	}
	if (!GateLamps(Now))
	{
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: %s. Step %d (%s) at t=%.2f s; %s; hero at "
			 "(%.0f,%.0f); the model's tally is %d/%d"),
		*What, Step, *StepLabel, Now, *DescribeHall(),
		Hero.IsValid() ? Hero->GetActorLocation().X : 0.0,
		Hero.IsValid() ? Hero->GetActorLocation().Y : 0.0,
		ModelFinishedCount(), ModelList.Num()));
}

// =====================================================================================
// diagnostics
// =====================================================================================

FString AMarkOrderFunctionalTest::DescribeHall() const
{
	FString Out;
	for (const FMark& M : Marks)
	{
		Out += FString::Printf(TEXT("%s%s=%.2f@(%.0f,%.0f)"),
			Out.IsEmpty() ? TEXT("") : TEXT(" "), *M.Label, M.Required, M.At.X, M.At.Y);
	}
	return Out;
}

FString AMarkOrderFunctionalTest::DescribeShownFaces() const
{
	FString Out = TEXT("the hall shows");
	for (const FMark& M : Marks)
	{
		double B = 0.0;
		double R = 0.0;
		if (ReadFace(M, B, R))
		{
			Out += FString::Printf(TEXT(" %s=%.1f/%.1f%s"), *M.Label, B, R,
				LampIntensity(M) >= kLampLitFloor ? TEXT("*") : TEXT(""));
		}
		else
		{
			Out += FString::Printf(TEXT(" %s=blank"), *M.Label);
		}
	}
	int32 F = 0;
	int32 L = 0;
	if (ReadTally(F, L))
	{
		Out += FString::Printf(TEXT(", tally %d/%d"), F, L);
	}
	else
	{
		Out += TEXT(", tally blank");
	}
	return Out;
}

FString AMarkOrderFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	TArray<FString> Problems;

	// Half one: the pawn's own Enhanced Input actions, read BY PROPERTY NAME so a
	// renamed or subclassed pawn still answers.
	if (Hero.IsValid())
	{
		TArray<FString> Unbound;
		for (const TCHAR* Name : { TEXT("MoveAction"), TEXT("LookAction"),
								   TEXT("MouseLookAction"), TEXT("JumpAction") })
		{
			const FObjectProperty* const Prop =
				FindFProperty<FObjectProperty>(Hero->GetClass(), Name);
			if (Prop == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(Hero.Get()) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Problems.Add(FString::Printf(TEXT("the character (%s) has nothing bound to %s"),
				*Hero->GetClass()->GetName(), *FString::Join(Unbound, TEXT(", "))));
		}
	}

	// Half two: a mapping context has to be applied, or no key reaches any of those
	// actions even when all four are set.
	const AGameModeBase* const GameMode =
		(World != nullptr) ? World->GetAuthGameMode() : nullptr;
	const UClass* const PCClass =
		(GameMode != nullptr) ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the player "
						  "gets a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts =
				 FindFProperty<FArrayProperty>(PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
		FScriptArrayHelper Helper(Contexts,
			Contexts->ContainerPtrToValuePtr<void>(PCClass->GetDefaultObject()));
		int32 Applied = 0;
		for (int32 Index = 0; Element != nullptr && Index < Helper.Num(); ++Index)
		{
			if (Element->GetObjectPropertyValue(Helper.GetElementPtr(Index)) != nullptr)
			{
				++Applied;
			}
		}
		if (Applied == 0)
		{
			Problems.Add(FString::Printf(TEXT("%s applies no input mapping context"),
				*PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s exposes no DefaultMappingContexts, so this check cannot tell "
				 "whether a key reaches the character"), *PCClass->GetName()));
	}

	return FString::Join(Problems, TEXT("; "));
}

void AMarkOrderFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString Lamps;
	for (const FMark& M : Marks)
	{
		// CHARACTERS, not one-character string literals: FString::operator+= resolves a
		// TCHAR[2] through the contiguous-range overload, which appends the terminator.
		Lamps.AppendChar(LampIntensity(M) >= kLampLitFloor ? TEXT('*') : TEXT('.'));
	}
	FString Model;
	for (const FMark& M : Marks)
	{
		Model += FString::Printf(TEXT(" %s=%.2f%s"), *M.Label, M.Bank,
			M.bFinished ? TEXT("F") : TEXT(""));
	}
	const FVector At = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-marks calib] cp%d t=%.2f step=%d(%s) round=%d turn=%d/%d occ=%d "
			 "poison=%d model:%s lamps=%s %s hero=(%.0f,%.0f) judged w%d o%d s%d p%d "
			 "a%d c%d l%d x%d ahead%d behind%d alone%d"),
		Index, Now, Step, *StepLabel, StagedRound, ModelFinishedCount(),
		ModelList.Num(), OccupiedLast, PoisonedMark, *Model, *Lamps,
		*DescribeShownFaces(), At.X, At.Y, WrongStepJudged, OutOfTurnJudged,
		StillThereJudged, PicksUpJudged, AwayJudged, CompletionJudged,
		ListChangeJudged, ControlCrossings, SkipAheadJudged, FinishedStepJudged,
		AwayCompletionJudged);
}

// =====================================================================================
// the route
// =====================================================================================

FVector AMarkOrderFunctionalTest::Lane(double X) const
{
	return FVector(X, 0.0, WalkZ);
}

FVector AMarkOrderFunctionalTest::Centre(int32 MarkIndex) const
{
	if (!Marks.IsValidIndex(MarkIndex))
	{
		return Park;
	}
	return FVector(Marks[MarkIndex].StagedAt.X, Marks[MarkIndex].StagedAt.Y, WalkZ);
}

double AMarkOrderFunctionalTest::PathLength(const FVector& From,
	const TArray<FVector>& Way) const
{
	double Len = 0.0;
	FVector At = From;
	for (const FVector& P : Way)
	{
		Len += FVector::Dist2D(At, P);
		At = P;
	}
	return Len;
}

bool AMarkOrderFunctionalTest::PathIsClear(const FVector& From,
	const TArray<FVector>& Way, const TArray<int32>& Allowed, FString& OutWhy) const
{
	FVector At = From;
	for (const FVector& To : Way)
	{
		const int32 Samples = FMath::Max(8, int32(FVector::Dist2D(At, To) / 25.0));
		for (int32 k = 0; k <= Samples; ++k)
		{
			const FVector P = FMath::Lerp(At, To, double(k) / double(Samples));
			for (int32 i = 0; i < Marks.Num(); ++i)
			{
				if (Allowed.Contains(i))
				{
					continue;
				}
				const double D = FVector::Dist2D(P, Marks[i].StagedAt);
				if (D < Marks[i].StagedRadius + kNonTargetClearUu)
				{
					OutWhy = FString::Printf(
						TEXT("the walk to (%.0f, %.0f) passes %.0f cm from %s, whose "
							 "ring reaches %.0f -- it needs %.0f of clearance or it "
							 "would start the round over on a mark nobody aimed at"),
						To.X, To.Y, D, *Marks[i].Label, Marks[i].StagedRadius,
						Marks[i].StagedRadius + kNonTargetClearUu);
					return false;
				}
			}
		}
		At = To;
	}
	return true;
}

bool AMarkOrderFunctionalTest::BuildRoute()
{
	// The parking spot is DERIVED: one clear stretch west of the westmost mark, on the
	// lane, so a re-authored hall moves it instead of leaving it inside a ring.
	double MinX = Marks[0].At.X;
	double MaxX = Marks[0].At.X;
	for (const FMark& M : Marks)
	{
		MinX = FMath::Min(MinX, M.At.X);
		MaxX = FMath::Max(MaxX, M.At.X);
	}
	Park = Lane(MinX - kParkBackOffUu);
	for (const FMark& M : Marks)
	{
		const double D = FVector::Dist2D(Park, M.StagedAt);
		if (D < M.StagedRadius + kParkClearUu)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the parking spot at (%.0f, %.0f) is %.0f cm "
					 "from %s, whose ring reaches %.0f; the drive parks at least %.0f "
					 "clear of every ring"),
				Park.X, Park.Y, D, *M.Label, M.StagedRadius, kParkClearUu));
			return false;
		}
		// The highway runs along y = 0, so every ring has to sit clear of it.
		if (FMath::Abs(M.StagedAt.Y) < M.StagedRadius + kNonTargetClearUu)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s stands %.0f cm off the lane the drive "
					 "walks along and its ring reaches %.0f; every transit would clip "
					 "it"), *M.Label, FMath::Abs(M.StagedAt.Y), M.StagedRadius));
			return false;
		}
	}

	FString Why;
	TArray<int32> Nothing;
	TArray<FVector> Way;

	// The highway itself, clear of EVERYTHING.
	Way = { Lane(MaxX + kCrossOutUu) };
	if (!PathIsClear(Park, Way, Nothing, Why))
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the lane the drive walks along is not clear -- "
				 "%s"), *Why));
		return false;
	}

	// One column per mark, straight in from the lane through the centre: a head-on
	// entry and a head-on exit, which is what keeps a one-frame sampling difference
	// from ever changing an edge COUNT.
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		TArray<int32> Allowed;
		Allowed.Add(i);
		Way = { Centre(i) };
		if (!PathIsClear(Lane(Marks[i].StagedAt.X), Way, Allowed, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the walk in to %s is not clear -- %s"),
				*Marks[i].Label, *Why));
			return false;
		}
	}

	const FVector Dune = Centre(IdxDune);
	const FVector Birch = Centre(IdxBirch);
	const FVector Cedar = Centre(IdxCedar);
	const FVector Ash = Centre(IdxAsh);
	const FVector Elm = Centre(IdxControl);
	const FVector EastEnd(Elm.X + kCrossOutUu, Elm.Y, WalkZ);
	const FVector WestEnd(Birch.X - kCrossBackUu, Birch.Y, WalkZ);
	const FVector NorthEnd(Elm.X, Elm.Y + kCrossUpUu, WalkZ);

	// CROSSING ONE: out of the first name, straight along its row and through the
	// unnamed mark, out the far side. Head-on both times only if the two really do
	// share a row.
	if (FMath::Abs(Elm.Y - Dune.Y) > kRowAlignUu || Elm.X <= Dune.X)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %s is at (%.0f,%.0f) and %s at (%.0f,%.0f); the "
				 "drive crosses the unnamed mark head-on along their shared row, which "
				 "needs it east of %s on the same row"),
			*Marks[IdxDune].Label, Dune.X, Dune.Y, *Marks[IdxControl].Label, Elm.X,
			Elm.Y, *Marks[IdxDune].Label));
		return false;
	}
	{
		TArray<int32> Allowed = { IdxDune, IdxControl };
		Way = { EastEnd };
		if (!PathIsClear(Dune, Way, Allowed, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the crossing of the unnamed mark is not "
					 "clear -- %s"), *Why));
			return false;
		}
		Way = { Lane(EastEnd.X) };
		if (!PathIsClear(EastEnd, Way, Nothing, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the way back to the lane from the far side "
					 "of the unnamed mark is not clear -- %s"), *Why));
			return false;
		}
	}

	// CROSSING TWO: out of the round-2 first name, west along its row and through the
	// mark the second list demotes, out the far side.
	if (FMath::Abs(Birch.Y - Cedar.Y) > kRowAlignUu || Birch.X >= Cedar.X)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %s is at (%.0f,%.0f) and %s at (%.0f,%.0f); the "
				 "drive crosses the demoted mark head-on along their shared row"),
			*Marks[IdxCedar].Label, Cedar.X, Cedar.Y, *Marks[IdxBirch].Label, Birch.X,
			Birch.Y));
		return false;
	}
	{
		TArray<int32> Allowed = { IdxCedar, IdxBirch };
		Way = { WestEnd };
		if (!PathIsClear(Cedar, Way, Allowed, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the crossing of the demoted mark is not "
					 "clear -- %s"), *Why));
			return false;
		}
		Way = { Lane(WestEnd.X) };
		if (!PathIsClear(WestEnd, Way, Nothing, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the way back to the lane from the far side "
					 "of the demoted mark is not clear -- %s. %s also has to stay %.0f "
					 "clear"), *Why, *Marks[IdxAsh].Label, kNonTargetClearUu));
			return false;
		}
	}

	// CROSSING THREE: up the unnamed mark's own column, through its centre and out the
	// top, then west along the top and down into the first name.
	{
		TArray<int32> Allowed = { IdxControl };
		Way = { NorthEnd };
		if (!PathIsClear(Lane(Elm.X), Way, Allowed, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the second crossing of the unnamed mark is "
					 "not clear -- %s"), *Why));
			return false;
		}
		TArray<int32> AllowedDune = { IdxDune };
		Way = { FVector(Dune.X, NorthEnd.Y, WalkZ), Dune };
		if (!PathIsClear(NorthEnd, Way, AllowedDune, Why))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the way back down into %s from the top of "
					 "the hall is not clear -- %s"), *Marks[IdxDune].Label, *Why));
			return false;
		}
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-marks] route solved: park (%.0f,%.0f), lane y=0, east end %.0f, west "
			 "end %.0f, north end %.0f; %s at (%.0f,%.0f) is the control"),
		Park.X, Park.Y, EastEnd.X, WestEnd.X, NorthEnd.Y, *Marks[IdxControl].Label,
		Elm.X, Elm.Y);
	(void)Ash;
	return true;
}

// =====================================================================================
// the drive
// =====================================================================================

void AMarkOrderFunctionalTest::BeginStep(int32 NewStep, double Now)
{
	Step = NewStep;
	StepStartedAt = Now;
	Waypoints.Reset();
	WaypointIndex = 0;
	MayCross.Reset();
	StandOn = INDEX_NONE;
	StandUntilBank = -1.0;
	bStandUntilFinished = false;
	StandUntilFinishedCount = -1;
	DwellS = -1.0;
	AwayForS = -1.0;
	OutOfTurnForS = -1.0;
	RewriteMark = INDEX_NONE;
	RewriteTo = 0.0;
	RewriteAtBank = -1.0;
	bRewriteFired = false;
	bRewriteWhileAway = false;
	bShiftChangeStep = false;
	bShiftChangeFired = false;
	bReorderStep = false;
	bReorderFired = false;
	EventFiredAt = -1000.0;
	HoldAfterEventS = -1.0;
	bBaselineStep = false;
	double StandBudget = 0.0;

	const FVector Dune = Centre(IdxDune);
	const FVector Birch = Centre(IdxBirch);
	const FVector Cedar = Centre(IdxCedar);
	const FVector Ash = Centre(IdxAsh);
	const FVector Elm = Centre(IdxControl);
	const FVector EastEnd(Elm.X + kCrossOutUu, Elm.Y, WalkZ);
	const FVector WestEnd(Birch.X - kCrossBackUu, Birch.Y, WalkZ);
	const FVector NorthEnd(Elm.X, Elm.Y + kCrossUpUu, WalkZ);

	switch (Step)
	{
	// ---- task.md phase 0: gates off; the character may spawn anywhere -------------
	case 0:
		StepLabel = TEXT("walk-to-the-parking-spot");
		Waypoints = { Park };
		break;

	// ---- task.md phase 1: THE BASELINE. The first graded frame in the run. --------
	case 1:
		StepLabel = TEXT("the-baseline");
		DwellS = kBaselineS;
		bBaselineStep = true;
		bGatesArmed = true;
		break;

	// ---- task.md phase 2: banking starts on the first name ------------------------
	case 2:
		StepLabel = TEXT("stand-on-the-first-name");
		Waypoints = { Lane(Dune.X), Dune };
		MayCross = { IdxDune };
		StandOn = IdxDune;
		StandUntilBank = kDuneBank40pc;
		StandBudget = kDuneBank40pc;
		break;

	// ---- task.md phase 3: THE SKIP AHEAD -- out of turn onto a name NOT DUE YET ---
	// The other half of the out-of-turn rule, and the half a submission is most likely
	// to get wrong, because it needs the realisation that a mark NOBODY HAS EVER
	// TOUCHED can still be an out-of-turn step. The first name is banked and mid-round;
	// the mark stepped onto is name 3 of 4, unfinished, and has not been the current
	// mark at any point. A submission that only treats an ALREADY FINISHED mark as out
	// of turn wipes nothing here, and the first name's bank is still standing 0.75 s
	// later, which is what gate 2 names.
	case 3:
		StepLabel = TEXT("step-ahead-onto-a-name-that-is-not-due-yet");
		Waypoints = { Lane(Dune.X), Lane(Cedar.X), Cedar };
		MayCross = { IdxDune, IdxCedar };
		StandOn = IdxCedar;
		OutOfTurnForS = kSkipAheadStandS;
		StandBudget = kSkipAheadStandS + 1.0;
		break;

	// The wipe took the first name's bank with it, so it has to be banked again before
	// the pause-and-resume pair can measure anything.
	case 4:
		StepLabel = TEXT("re-bank-the-first-name");
		Waypoints = { Lane(Cedar.X), Lane(Dune.X), Dune };
		MayCross = { IdxCedar, IdxDune };
		StandOn = IdxDune;
		StandUntilBank = kDuneBank40pc;
		StandBudget = kDuneBank40pc + 1.0;
		break;

	// ---- task.md phase 4: the first off-mark wait ---------------------------------
	case 5:
		StepLabel = TEXT("walk-out-and-wait");
		Waypoints = { Lane(Dune.X), Park };
		MayCross = { IdxDune };
		AwayForS = kAwayWaitS;
		StandBudget = kAwayWaitS + 1.0;
		break;

	// ---- task.md phase 5: come back, and the MID-STAND RAISE lands here -----------
	case 6:
		StepLabel = TEXT("walk-back-on-to-the-finish");
		Waypoints = { Lane(Dune.X), Dune };
		MayCross = { IdxDune };
		StandOn = IdxDune;
		bStandUntilFinished = true;
		RewriteMark = IdxDune;
		RewriteTo = kDuneRaisedTo;
		RewriteAtBank = kDuneRaiseAtBank;
		StandBudget = kDuneRaisedTo;
		break;

	// ---- task.md phase 6: crossing 1 of 2 through the unnamed mark ----------------
	case 7:
		StepLabel = TEXT("cross-the-unnamed-mark");
		Waypoints = { EastEnd };
		MayCross = { IdxDune, IdxControl };
		break;

	// ---- task.md phase 7: the MID-STAND DROP lands here; it must finish at once ---
	case 8:
		StepLabel = TEXT("stand-on-the-second-name");
		Waypoints = { Lane(EastEnd.X), Lane(Birch.X), Birch };
		MayCross = { IdxBirch };
		StandOn = IdxBirch;
		bStandUntilFinished = true;
		RewriteMark = IdxBirch;
		RewriteTo = kBirchDroppedTo;
		RewriteAtBank = kBirchDropAtBank;
		StandBudget = kBirchDropAtBank + 1.0;
		break;

	// ---- task.md phase 8: out of turn onto a name ALREADY FINISHED ----------------
	// The other half of the rule, and the first name is chosen deliberately: the wipe
	// makes it the mark whose turn it is again, which is exactly where "reset the round
	// and then re-evaluate where I am standing" starts banking and must not.
	case 9:
		StepLabel = TEXT("step-onto-a-finished-name-out-of-turn");
		Waypoints = { Lane(Birch.X), Lane(Dune.X), Dune };
		MayCross = { IdxBirch, IdxDune };
		StandOn = IdxDune;
		OutOfTurnForS = kOutOfTurnStandS;
		StandBudget = kOutOfTurnStandS + 1.0;
		break;

	// ---- task.md phase 9: walk off, then re-walk the whole list in order ----------
	case 10:
		StepLabel = TEXT("step-off-the-poisoned-mark");
		Waypoints = { Lane(Dune.X) };
		MayCross = { IdxDune };
		break;
	case 11:
		StepLabel = TEXT("re-walk-the-first-name");
		Waypoints = { Dune };
		MayCross = { IdxDune };
		StandOn = IdxDune;
		bStandUntilFinished = true;
		StandBudget = kDuneRaisedTo;
		break;
	case 12:
		StepLabel = TEXT("re-walk-the-second-name");
		Waypoints = { Lane(Dune.X), Lane(Birch.X), Birch };
		MayCross = { IdxDune, IdxBirch };
		StandOn = IdxBirch;
		bStandUntilFinished = true;
		StandBudget = kBirchDroppedTo;
		break;

	// ---- task.md phase 10: bank the third name PART WAY, then walk clear ----------
	// The completion this sets up is the one that has to fire with NOBODY STANDING
	// ANYWHERE, so the stand deliberately stops short of the number.
	case 13:
		StepLabel = TEXT("re-walk-the-third-name-part-way");
		Waypoints = { Lane(Birch.X), Lane(Cedar.X), Cedar };
		MayCross = { IdxBirch, IdxCedar };
		StandOn = IdxCedar;
		StandUntilBank = kCedarBankBeforeAway;
		StandBudget = kCedarBankBeforeAway + 1.0;
		break;

	// THE DROP THAT LANDS WITH NOBODY IN A RING. The character walks all the way out to
	// the parking spot, the off-mark wait is sampled, and only then does the fixture
	// drop the third name's number BELOW what it has already banked. It must finish at
	// once -- lamp lit, tally up by one, face at its own number -- with nobody moving.
	// A finish test nested inside "somebody is standing here and banking" cannot
	// produce this, and every other completion in the run happens under somebody's
	// feet, so this is the only place the two implementations differ.
	case 14:
		StepLabel = TEXT("walk-clear-while-the-third-name-is-still-owed");
		Waypoints = { Lane(Cedar.X), Park };
		MayCross = { IdxCedar };
		RewriteMark = IdxCedar;
		RewriteTo = kCedarDroppedTo;
		bRewriteWhileAway = true;
		HoldAfterEventS = kAwayDropHoldS;
		StandUntilFinishedCount = 3;
		StandBudget = kAwayWaitS + kAwayDropHoldS + 2.0;
		break;

	case 15:
		StepLabel = TEXT("re-walk-the-last-name");
		Waypoints = { Lane(Ash.X), Ash };
		MayCross = { IdxAsh };
		StandOn = IdxAsh;
		bStandUntilFinished = true;
		StandUntilFinishedCount = StagedList.Num();
		StandBudget = kRound1Seconds[kAsh];
		break;

	// ---- task.md phase 11: a finished mark keeps its lamp and its face ------------
	case 16:
		StepLabel = TEXT("hold-the-finished-round");
		Waypoints = { Lane(Ash.X) };
		MayCross = { IdxAsh };
		DwellS = 6.0;
		break;

	// ---- task.md phase 12: out of turn again, off, and back on -------------------
	case 17:
		StepLabel = TEXT("step-out-of-turn-again");
		Waypoints = { Lane(Dune.X), Dune };
		MayCross = { IdxDune };
		StandOn = IdxDune;
		OutOfTurnForS = kShortOutOfTurnStandS;
		StandBudget = kShortOutOfTurnStandS + 1.0;
		break;
	case 18:
		StepLabel = TEXT("step-off-again");
		Waypoints = { Lane(Dune.X) };
		MayCross = { IdxDune };
		DwellS = 3.0;
		break;
	case 19:
		StepLabel = TEXT("back-on-and-bank-a-little");
		Waypoints = { Dune };
		MayCross = { IdxDune };
		StandOn = IdxDune;
		StandUntilBank = kDunePartWayBank;
		StandBudget = kDunePartWayBank + 1.0;
		break;

	// ---- task.md phase 13: THE SHIFT CHANGE, mid-stand ---------------------------
	// The new list names the mark being stood on at position 2, so it must stop
	// banking and read none of its NEW number where they stand -- and NO wipe may
	// fire, because no step happened.
	case 20:
		StepLabel = TEXT("the-shift-change");
		StandOn = IdxDune;
		bShiftChangeStep = true;
		DwellS = kShiftChangeHoldS;
		break;

	// ---- task.md phase 14: round 2 begins ----------------------------------------
	case 21:
		StepLabel = TEXT("bank-the-new-first-name");
		Waypoints = { Lane(Dune.X), Lane(Cedar.X), Cedar };
		MayCross = { IdxDune, IdxCedar };
		StandOn = IdxCedar;
		StandUntilBank = kCedarBank45pc;
		StandBudget = kCedarBank45pc + 1.0;
		break;

	// ---- task.md phase 15: THE SECOND SKIP AHEAD, on the new list -----------------
	// Name 2 of 3, unfinished, never the current mark. The rule has to hold on a list
	// the submission was never handed at BeginPlay, and it has to hold twice.
	case 22:
		StepLabel = TEXT("step-ahead-onto-a-new-name-that-is-not-due-yet");
		Waypoints = { Lane(Cedar.X), Lane(Dune.X), Dune };
		MayCross = { IdxCedar, IdxDune };
		StandOn = IdxDune;
		OutOfTurnForS = kSkipAheadStandS;
		StandBudget = kSkipAheadStandS + 1.0;
		break;
	case 23:
		StepLabel = TEXT("re-bank-the-new-first-name");
		Waypoints = { Lane(Dune.X), Lane(Cedar.X), Cedar };
		MayCross = { IdxDune, IdxCedar };
		StandOn = IdxCedar;
		StandUntilBank = kCedarBank45pc;
		StandBudget = kCedarBank45pc + 1.0;
		break;

	// ---- task.md phase 16: the second off-mark wait ------------------------------
	case 24:
		StepLabel = TEXT("walk-out-and-wait-again");
		Waypoints = { Lane(Cedar.X), Park };
		MayCross = { IdxCedar };
		AwayForS = kAwayWaitS;
		StandBudget = kAwayWaitS + 1.0;
		break;

	// ---- task.md phase 17: come back; the second MID-STAND RAISE lands here ------
	case 25:
		StepLabel = TEXT("back-on-to-the-new-finish");
		Waypoints = { Lane(Cedar.X), Cedar };
		MayCross = { IdxCedar };
		StandOn = IdxCedar;
		bStandUntilFinished = true;
		RewriteMark = IdxCedar;
		RewriteTo = kCedarRaisedTo;
		RewriteAtBank = kCedarRaiseAtBank;
		StandBudget = kCedarRaisedTo;
		break;

	// ---- task.md phase 18: the demoted mark is now as inert as the control -------
	case 26:
		StepLabel = TEXT("cross-the-demoted-name");
		Waypoints = { WestEnd };
		MayCross = { IdxCedar, IdxBirch };
		break;
	case 27:
		StepLabel = TEXT("cross-the-unnamed-mark-again");
		Waypoints = { Lane(WestEnd.X), Lane(Elm.X), NorthEnd };
		MayCross = { IdxControl };
		break;

	// ---- task.md phase 19: bank part way, then step onto the new FIRST name ------
	case 28:
		StepLabel = TEXT("bank-the-new-second-name-part-way");
		Waypoints = { FVector(Dune.X, NorthEnd.Y, WalkZ), Dune };
		MayCross = { IdxDune };
		StandOn = IdxDune;
		StandUntilBank = kDunePartWayBank;
		StandBudget = kDunePartWayBank + 1.0;
		break;
	case 29:
		StepLabel = TEXT("step-onto-the-new-first-name-out-of-turn");
		Waypoints = { Lane(Dune.X), Lane(Cedar.X), Cedar };
		MayCross = { IdxDune, IdxCedar };
		StandOn = IdxCedar;
		OutOfTurnForS = kOutOfTurnStandS;
		StandBudget = kOutOfTurnStandS + 1.0;
		break;

	// ---- task.md phase 20: re-walk the whole new list in order -------------------
	case 30:
		StepLabel = TEXT("step-off-the-poisoned-mark-again");
		Waypoints = { Lane(Cedar.X) };
		MayCross = { IdxCedar };
		DwellS = 3.0;
		break;
	case 31:
		StepLabel = TEXT("re-walk-the-new-first-name");
		Waypoints = { Cedar };
		MayCross = { IdxCedar };
		StandOn = IdxCedar;
		bStandUntilFinished = true;
		StandBudget = kCedarRaisedTo;
		break;

	// ---- task.md phase 21: the SECOND completion with nobody standing ------------
	case 32:
		StepLabel = TEXT("re-walk-the-new-second-name-part-way");
		Waypoints = { Lane(Cedar.X), Lane(Dune.X), Dune };
		MayCross = { IdxCedar, IdxDune };
		StandOn = IdxDune;
		StandUntilBank = kDuneBankBeforeAway;
		StandBudget = kDuneBankBeforeAway + 1.0;
		break;
	case 33:
		StepLabel = TEXT("walk-clear-while-the-new-second-name-is-still-owed");
		Waypoints = { Lane(Dune.X), Park };
		MayCross = { IdxDune };
		RewriteMark = IdxDune;
		RewriteTo = kDuneDroppedTo;
		bRewriteWhileAway = true;
		HoldAfterEventS = kAwayDropHoldS;
		StandUntilFinishedCount = 2;
		StandBudget = kAwayWaitS + kAwayDropHoldS + 2.0;
		break;

	case 34:
		StepLabel = TEXT("re-walk-the-new-last-name");
		Waypoints = { Lane(Ash.X), Ash };
		MayCross = { IdxAsh };
		StandOn = IdxAsh;
		bStandUntilFinished = true;
		StandUntilFinishedCount = StagedList.Num();
		StandBudget = kRound2Seconds[kAsh];
		break;

	// ---- task.md phase 22: park, hold ---------------------------------------------
	case 35:
		StepLabel = TEXT("park-and-hold");
		Waypoints = { Lane(Ash.X), Park };
		MayCross = { IdxAsh };
		DwellS = 10.0;
		break;

	// ---- task.md phase 23: THE SAME-LENGTH REORDER --------------------------------
	// The board takes the SAME three names, the SAME first name and the SAME seconds,
	// in a different order, while the character is parked clear of every ring. The
	// round has to start over anyway. A change detector that compares the LENGTH of the
	// list, or its FIRST name, or the SET of names, sees nothing at all here -- and the
	// round-1-to-round-2 replacement (four names to three) is what makes each of those
	// look right the first time.
	case 36:
		StepLabel = TEXT("the-board-changes-its-mind");
		bReorderStep = true;
		HoldAfterEventS = kReorderHoldS;
		StandBudget = kReorderHoldS + 1.0;
		break;

	// ---- task.md phase 24: hold, then the run-level gate --------------------------
	case 37:
		StepLabel = TEXT("park-and-hold-again");
		DwellS = 3.0;
		break;

	default:
		StepLabel = TEXT("done");
		bDriveComplete = true;
		DriveCompletedAt = Now;
		UE_LOG(LogTemp, Display,
			TEXT("[t3-marks] the drive is complete at t=%.2f s; %s"), Now,
			*DescribeShownFaces());
		return;
	}

	// A SECOND NET on the route. BuildRoute already proved every primitive this
	// polyline is made of; this proves the polyline itself, from where the character
	// actually is, including the ring they are standing in as they set off.
	{
		TArray<int32> Allowed = MayCross;
		const int32 Under = MarkUnderCharacter();
		if (Under != INDEX_NONE)
		{
			Allowed.AddUnique(Under);
		}
		const FVector From = Hero.IsValid() ? Hero->GetActorLocation() : Park;
		FString Why;
		if (!PathIsClear(From, Waypoints, Allowed, Why))
		{
			AttributeOverrun(Now, FString::Printf(
				TEXT("drive step %d (%s) cannot be walked -- %s"), Step, *StepLabel,
				*Why));
			return;
		}
	}

	const FVector From = Hero.IsValid() ? Hero->GetActorLocation() : Park;
	const double Len = PathLength(From, Waypoints);
	// DERIVED, never written down: 2.5x the walk at the MEASURED pace, twice the
	// standing the step asks for, plus a flat 15 s. Generous on purpose -- the drive
	// must never manufacture a failure, and every step ends on a condition the
	// fixture's own model reaches, so a long budget costs nothing but wall clock.
	StepDeadline = Now + Len / HeroSpeed * 2.5 + StandBudget * 2.0 + 15.0;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-marks] step %d (%s) begins at t=%.2f: %d waypoint(s), %.0f uu, "
			 "budget %.0f s"),
		Step, *StepLabel, Now, Waypoints.Num(), Len, StepDeadline - Now);
}

void AMarkOrderFunctionalTest::DriveHero(double Now)
{
	ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		return;
	}
	const FVector Here = H->GetActorLocation();
	if (Waypoints.IsValidIndex(WaypointIndex))
	{
		const FVector Target = Waypoints[WaypointIndex];
		const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
		if (Flat.Size2D() <= kWaypointUu)
		{
			++WaypointIndex;
			return;
		}
		// THE SHIPPING PER-FRAME LOCOMOTION PATH, the same one a person drives with
		// WASD. There is not one key press anywhere in this task.
		H->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		return;
	}
	// The walk is done. Hold station on the mark this step stands on, with a deadband
	// so the correction cannot oscillate: a character that drifts out of a ring would
	// register an exit nobody asked for and pause a bank the drive means to be running.
	if (StandOn != INDEX_NONE)
	{
		const FVector C = Centre(StandOn);
		const FVector Flat(C.X - Here.X, C.Y - Here.Y, 0.0);
		if (Flat.Size2D() > kHoldDeadbandUu)
		{
			H->AddMovementInput(Flat.GetSafeNormal(), float(kHoldScale));
		}
	}
}

void AMarkOrderFunctionalTest::MaybeFireStagedRewrite(double Now)
{
	if (bShiftChangeStep && !bShiftChangeFired)
	{
		// MID-STAND, by construction: the character has to be standing in the ring the
		// new list will demote from current, or the phase measures nothing.
		if (StandOn != INDEX_NONE && OccupiedLast == StandOn)
		{
			StageRound(2, Now);
			bShiftChangeFired = true;
			EventFiredAt = Now;
		}
		return;
	}
	if (bReorderStep && !bReorderFired)
	{
		// PARKED, by construction: nobody in any ring and the walk finished. The
		// reorder wipes the round exactly as the shift change did, so a step edge
		// landing in the same window would make two events out of one and nobody could
		// say which the gate had judged.
		if (OccupiedLast == INDEX_NONE && WaypointIndex >= Waypoints.Num())
		{
			StageRound(3, Now);
			bReorderFired = true;
			EventFiredAt = Now;
		}
		return;
	}
	if (RewriteMark == INDEX_NONE || bRewriteFired || !Marks.IsValidIndex(RewriteMark))
	{
		return;
	}
	const FMark& M = Marks[RewriteMark];
	if (M.bFinished)
	{
		// The staged table is mis-tuned: the mark finished before the number could be
		// moved under it, so the live-read window this phase exists for would be empty.
		// Attributed, never scored.
		AttributeOverrun(Now, FString::Printf(
			TEXT("%s finished at %.2f banked before the staged rewrite to %.2f could "
				 "fire, so the live-read window would have been empty"),
			*M.Label, M.BankAtFinish, RewriteTo));
		return;
	}
	if (bRewriteWhileAway)
	{
		// THE DROP THAT MUST FINISH A MARK WITH NOBODY STANDING ANYWHERE. Three things
		// have to be true first, and every one of them is about the FIXTURE'S OWN state
		// rather than about anything the submission shows: the character is in no
		// ring, the walk to the parking spot is finished, and the off-mark wait has
		// already taken its "the bank did not move" sample -- so the ONLY thing that
		// can move that face afterwards is the completion this drop causes.
		const bool bWaitSettled = bAwaySampled
			|| (Now - LastRingExitAt) >= (kAwayArmS + 1.0);
		if (OccupiedLast != INDEX_NONE || WaypointIndex < Waypoints.Num()
			|| !bWaitSettled)
		{
			return;
		}
		if (!M.bHasBank || M.Bank <= RewriteTo + kMinSecondsGapS)
		{
			// Mis-tuned table: the drop is not clearly BELOW the standing bank, so
			// "it finishes at once" would rest on the tolerance rather than on the
			// rule. Attributed, never scored.
			AttributeOverrun(Now, FString::Printf(
				TEXT("the off-mark drop would put %s at %.2f against %.2f already "
					 "banked, which is not clear of the %.2f s the fixture needs to "
					 "call that a finish rather than a rounding"),
				*M.Label, RewriteTo, M.Bank, kMinSecondsGapS));
			return;
		}
	}
	else if (OccupiedLast != RewriteMark || !M.bHasBank || M.Bank < RewriteAtBank)
	{
		return;
	}
	StageOneRequired(RewriteMark, RewriteTo, Now);
	bRewriteFired = true;
	EventFiredAt = Now;
}

bool AMarkOrderFunctionalTest::StepComplete(double Now) const
{
	const bool bAtEnd = (Waypoints.Num() == 0) || (WaypointIndex >= Waypoints.Num());
	if (!bAtEnd)
	{
		return false;
	}
	if (DwellS >= 0.0 && (Now - StepStartedAt) < DwellS)
	{
		return false;
	}
	if (AwayForS >= 0.0 && (Now - LastRingExitAt) < AwayForS)
	{
		return false;
	}
	if (OutOfTurnForS >= 0.0
		&& (OutOfTurnMark == INDEX_NONE || (Now - OutOfTurnAt) < OutOfTurnForS))
	{
		return false;
	}
	if (bShiftChangeStep && !bShiftChangeFired)
	{
		return false;
	}
	if (bReorderStep && !bReorderFired)
	{
		return false;
	}
	if (RewriteMark != INDEX_NONE && !bRewriteFired)
	{
		return false;
	}
	// Measured from the EVENT, not from the step's start: these steps carry a long walk
	// first, and a dwell measured from the start would be a wall-clock guess about how
	// fast the character got there. EventFiredAt < StepStartedAt means it has not fired
	// on THIS step yet.
	if (HoldAfterEventS >= 0.0
		&& (EventFiredAt < StepStartedAt || (Now - EventFiredAt) < HoldAfterEventS))
	{
		return false;
	}
	if (StandOn != INDEX_NONE && Marks.IsValidIndex(StandOn))
	{
		const FMark& M = Marks[StandOn];
		if (bStandUntilFinished && !M.bFinished)
		{
			return false;
		}
		if (StandUntilBank >= 0.0 && M.Bank < StandUntilBank)
		{
			return false;
		}
	}
	if (StandUntilFinishedCount >= 0 && ModelFinishedCount() < StandUntilFinishedCount)
	{
		return false;
	}
	return true;
}

void AMarkOrderFunctionalTest::AdvanceSteps(double Now)
{
	if (bDriveComplete)
	{
		return;
	}
	if (Now > StepDeadline)
	{
		AttributeOverrun(Now, FString::Printf(
			TEXT("drive step %d (%s) overran its %.0f s budget with %d of %d waypoints "
				 "reached"),
			Step, *StepLabel, StepDeadline - StepStartedAt, WaypointIndex,
			Waypoints.Num()));
		return;
	}
	if (StepComplete(Now))
	{
		BeginStep(Step + 1, Now);
	}
}

// =====================================================================================
// lifecycle
// =====================================================================================

void AMarkOrderFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the hall has no world"));
		return;
	}
	if (!ResolveHall())
	{
		return;
	}
	if (const FString Unwired = DescribeBrokenPlayerInput(World); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. The "
				 "graded drive would still pass, so fix the substrate, not the task."),
			*Unwired));
		return;
	}

	// EVERY STAGED SET IS VALIDATED BEFORE ANY OF IT IS WRITTEN, including the two sets
	// the mid-stand rewrites produce -- a table whose separation does not come out is a
	// staging fault, and it has to be one BEFORE it can be mistaken for a model's.
	TArray<double> R1;
	TArray<double> R2;
	TArray<double> R3;
	for (int32 i = 0; i < 5; ++i)
	{
		R1.Add(kRound1Seconds[i]);
		R2.Add(kRound2Seconds[i]);
		R3.Add(kRound3Seconds[i]);
	}
	TArray<FName> L1;
	TArray<FName> L2;
	TArray<FName> L3;
	for (int32 k = 0; k < 4; ++k)
	{
		L1.Add(Marks[kRound1List[k]].Name);
	}
	for (int32 k = 0; k < 3; ++k)
	{
		L2.Add(Marks[kRound2List[k]].Name);
		L3.Add(Marks[kRound3List[k]].Name);
	}
	if (!ValidateStagedSet(TEXT("round 1"), R1, L1))
	{
		return;
	}
	if (!ValidateStagedSet(TEXT("round 2"), R2, L2))
	{
		return;
	}
	if (!ValidateStagedSet(TEXT("the same-length reorder"), R3, L3))
	{
		return;
	}
	{
		TArray<double> Raised = R1;
		Raised[kDune] = kDuneRaisedTo;
		if (!ValidateStagedSet(TEXT("round 1 after the mid-stand raise"), Raised, L1))
		{
			return;
		}
		TArray<double> Dropped = Raised;
		Dropped[kBirch] = kBirchDroppedTo;
		if (!ValidateStagedSet(TEXT("round 1 after the mid-stand drop"), Dropped, L1))
		{
			return;
		}
		TArray<double> DroppedAway = Dropped;
		DroppedAway[kCedar] = kCedarDroppedTo;
		if (!ValidateStagedSet(TEXT("round 1 after the off-mark drop"), DroppedAway, L1))
		{
			return;
		}
		TArray<double> Raised2 = R2;
		Raised2[kCedar] = kCedarRaisedTo;
		if (!ValidateStagedSet(TEXT("round 2 after the mid-stand raise"), Raised2, L2))
		{
			return;
		}
		TArray<double> DroppedAway2 = Raised2;
		DroppedAway2[kDune] = kDuneDroppedTo;
		if (!ValidateStagedSet(TEXT("round 2 after the off-mark drop"), DroppedAway2, L2))
		{
			return;
		}
		// THE REORDER MOVES NO NUMBER, and this is where that is proved rather than
		// asserted: kRound3Seconds has to BE the set the hall is carrying by then, or
		// StageRound(3) would move a number on a mark that is already finished -- a
		// corner no prompt sentence settles.
		if (DroppedAway2 != R3)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the same-length reorder stages seconds that "
					 "are not the ones the hall is carrying when it lands (round 2 "
					 "after its raise and its off-mark drop). The reorder must move the "
					 "ORDER and nothing else: three marks are finished at that instant "
					 "and no gate settles what a finished mark does when its own number "
					 "moves under it. %s"), *DescribeHall()));
			return;
		}
	}
	if (L1.Num() == L2.Num())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the first two staged lists carry %d names each. "
				 "The tally's right-hand number is one of the things this task grades, "
				 "so those two have to differ in LENGTH as well as in order"),
			L1.Num()));
		return;
	}
	if (L1 == L2)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the first two staged lists are the same list"));
		return;
	}
	// AND THE THIRD ONE HAS TO DIFFER IN ORDER *ONLY*. This is the whole point of it:
	// the first replacement (four names to three) is seen by a detector that compares
	// lengths, or first names, or the set of names, and each of those is a locally
	// reasonable reading of "the board's list can be changed at any time". The second
	// replacement is invisible to every one of them, so it is what separates them from
	// a real order-sensitive comparison. A reorder that quietly changed the length, the
	// first name or the set would test nothing that round 2 did not already test.
	if (L3.Num() != L2.Num())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the reorder carries %d names against the "
				 "previous list's %d. It has to keep the LENGTH, or a change detector "
				 "that compares lengths passes it"), L3.Num(), L2.Num()));
		return;
	}
	if (L3 == L2)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the reorder is the same list in the same order, "
				 "so nothing about it can be judged"));
		return;
	}
	if (L3.Num() > 0 && L3[0] != L2[0])
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the reorder starts with '%s' where the previous "
				 "list started with '%s'. It has to keep the FIRST NAME, or a change "
				 "detector that only watches the first name passes it"),
			*L3[0].ToString(), *L2[0].ToString()));
		return;
	}
	for (const FName& N : L2)
	{
		if (!L3.Contains(N))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the reorder drops '%s'. It has to carry the "
					 "same NAMES, or a change detector that compares the set of names "
					 "passes it"), *N.ToString()));
			return;
		}
	}
	if (!BuildRoute())
	{
		return;
	}

	const double Now = double(World->GetTimeSeconds());

	// ROUND 1 IS STAGED HERE, IN PrepareTest, WHICH RUNS AFTER EVERY BeginPlay. The
	// committed .umap carries a TWO-name decoy list and a different set of seconds, so
	// a submission that snapshots either at BeginPlay reads the wrong denominator at
	// the baseline checkpoint and is already wrong before the character has entered a
	// single ring.
	StageRound(1, Now);
	// The model is SEEDED with the round-1 list rather than adopting it as a change:
	// the opening staging is the baseline, not a graded list replacement. The one
	// graded replacements are the shift change, mid-stand, in step 20, and the
	// same-length reorder, parked, in step 36.
	ModelList = StagedList;
	Turn = 0;
	PoisonedMark = INDEX_NONE;
	// Kept in step with PoisonedMark HERE TOO, so the invariant "OutOfTurnMark is set
	// exactly when PoisonedMark is" holds from the very first frame and both gates and
	// AnyWindowArmed can lean on it.
	OutOfTurnMark = INDEX_NONE;
	OutOfTurnAt = -1000.0;
	bOutOfTurnAhead = false;
	OccupiedLast = INDEX_NONE;
	BankingMark = INDEX_NONE;
	for (FMark& M : Marks)
	{
		M.bHasBank = false;
		M.Bank = 0.0;
		M.bFinished = false;
		M.FinishedChangedAt = -1000.0;
		M.Uncertainty = 0.0;
		M.CrossingsThisAttempt = 0;
		M.CrossingsTotal = 0;
	}

	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelS);
	SetCheckpointSchedule(Schedule);

	BeginStep(0, Now);
	bPrepared = true;
}

void AMarkOrderFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !bPrepared || !Hero.IsValid() || !Board.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	FrameDt = FMath::Max(double(DeltaSeconds), 1.0 / 240.0);

	// BEFORE the gates, so a gate that finishes the test this frame still leaves the
	// state that led to it on the record. The tightest moment in the whole run is the
	// opening baseline, and it sits before the first scheduled checkpoint.
	while (NextEarlyCalib < kEarlyCalibCount && Now >= kEarlyCalibS[NextEarlyCalib])
	{
		LogCalib(-1 - NextEarlyCalib, Now);
		++NextEarlyCalib;
	}

	ReReadHall();

	// GATE 1 RUNS EVERY FRAME FROM THE FIRST, before the model steps: the model reads
	// the marks' LIVE numbers and the LIVE list, so without this a submission could
	// re-write the hall into a shape where every other window is unreachable.
	if (!GateHallNotRewired(Now))
	{
		return;
	}

	StepModel(double(DeltaSeconds), Now);
	MaybeFireStagedRewrite(Now);
	if (!IsRunning())
	{
		return;
	}

	// WHAT THE HALL SHOWED, for the run-level gate. Recorded from the readout, never
	// from the model, and recorded on every frame rather than only where a gate is
	// armed -- the claim is that the board REACHED these readings.
	{
		int32 F = 0;
		int32 L = 0;
		if (ReadTally(F, L))
		{
			if (StagedRound == 1 && F > 0 && F == L && L == StagedList.Num())
			{
				bShownFullRoundOne = true;
				ShownFullLengthOne = L;
			}
			if (bShownFullRoundOne && !bShownFullRoundTwo && F == 0)
			{
				bShownZeroBetween = true;
			}
			if (StagedRound == 2 && bShownZeroBetween && F > 0 && F == L
				&& L == StagedList.Num())
			{
				bShownFullRoundTwo = true;
				ShownFullLengthTwo = L;
			}
		}
	}

	if (bGatesArmed)
	{
		const bool bWindow = AnyWindowArmed(Now);

		// AT THE BASELINE THE BOARD SPEAKS FIRST. task.md's gate precedence table says
		// so in as many words, and it is the whole reason the empty submission is
		// charged with TheBoardShowsHowFarYouGot rather than with one of the two gates
		// that fail on the same frame for the same reason: the tally face ships blank
		// and a round that has begun reads none of four.
		if (bBaselineStep && !StagingSuppressed(Now) && !GateBoardTally(Now))
		{
			return;
		}

		if (!GateWrongStepEmpties(Now)) { return; }
		if (!GateOutOfTurnBanksNothing(Now)) { return; }
		if (!GateListChangeRestarts(Now)) { return; }
		if (!GateBankStillThere(Now)) { return; }
		if (!GateBankPicksUp(Now)) { return; }
		if (!GateBankHoldsAway(Now)) { return; }
		if (!GateWaitsForItsOwnNumber(Now)) { return; }

		// THE IN-SCENE NEGATIVE CONTROL IS NEVER SUPPRESSED. It is a genuinely separate
		// channel: without this, the one mark that must never move would be ungraded on
		// precisely the frames that matter most.
		if (!GateUnnamedStaysCold(Now)) { return; }

		if (!bWindow && !SettleSuppressed(Now) && !EdgeSuppressed(Now))
		{
			if (!GateEveryFace(Now)) { return; }
			if (!bBaselineStep && !GateBoardTally(Now)) { return; }
		}

		// THE LAMP ROW IS EVALUATED LAST, and only once whichever windowed gate was
		// armed has already agreed: a wrong bank is always named by the windowed gate,
		// and a right bank with wrong lamps is always named here.
		if (!GateLamps(Now)) { return; }
	}

	DriveHero(Now);
	AdvanceSteps(Now);
	if (!IsRunning())
	{
		return;
	}

	if (bDriveComplete && !bRunLevelDone && DriveCompletedAt >= 0.0
		&& Now >= DriveCompletedAt + 0.5)
	{
		RunLevelGate(Now, false);
	}
}

void AMarkOrderFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}
	// THE SENTINEL. Reached only when the drive never finished at all -- every step
	// carries its own derived deadline, so this is a backstop, not the normal path.
	if (!bRunLevelDone)
	{
		RunLevelGate(TimeSeconds, true);
	}
}
