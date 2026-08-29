// Copyright CraftBench. All Rights Reserved.

#include "AlarmEscalationFunctionalTest.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kSettleS = 0.5;              // "half a second to catch up"

	// UNDISCLOSED: fixture clocking, staging and tolerances. Every one of these is a
	// widening of the disclosed contract, never a narrowing.
	constexpr double kSuppressAfterS = kSettleS * 1.5;   // 1.5x the disclosed settle
	constexpr double kSuppressBeforeForgetS = 0.4;
	constexpr double kMarginAngleDeg = 3.0;       // "too close to a cone edge to judge"
	constexpr double kMarginReachFrac = 0.06;
	constexpr double kSpeedTolFrac = 0.01;        // 1% on a pace the panel dictates
	constexpr double kGuardOnRoundUu = 60.0;      // how far off its own round is "off"
	constexpr double kPostMoveUu = 2.0;
	constexpr double kWaypointUu = 90.0;
	constexpr double kMinWindowS = 2.0;           // assertable time inside a sighting
	constexpr double kMinGapS = 2.0;              // and between two of them
	constexpr double kCheckpointEveryS = 8.0;
	constexpr int32 kGradedCheckpoints = 49;      // 8 s .. 392 s
	constexpr double kSentinelAtS = 400.0;
	/** Deliberate over-exposure in leg 2: the yard is stood in front of until this
	 *  many RAW sightings have happened while the remembered count sticks at the cap. */
	constexpr int32 kRawSightingsForCapProof = 8;

	/** Perpendicular offsets, as fractions of the guards' own cone limits. Derived, so
	 *  a re-authored level with different guards follows automatically. */
	constexpr double kSeenSpotFraction = 0.55;    // of the NARROWER guard's limit
}

AAlarmEscalationFunctionalTest::AAlarmEscalationFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Reflection. The yard's numbers are read by NAME, not through a cast: the fixture
// never needs to know the agent's class layout, and the same helpers write the two
// dials the sergeant re-sets at the watch change.
//
// NOTE (and it is a real limit, not a nicety): reflection here buys avoiding a cast
// and NOTHING MORE. The guards, lamps, posts and panel are placed instances in a
// committed .umap under a deny-listed path, so the agent can neither rename these
// classes nor subclass them usefully -- a fresh subclass would never be instantiated.
// ---------------------------------------------------------------------------

float AAlarmEscalationFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0.0f;
}

int32 AAlarmEscalationFunctionalTest::ReadInt(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0;
}

FName AAlarmEscalationFunctionalTest::ReadName(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return NAME_None;
}

bool AAlarmEscalationFunctionalTest::WriteFloat(AActor* A, const TCHAR* Name,
	float Value) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AAlarmEscalationFunctionalTest::WriteInt(AActor* A, const TCHAR* Name,
	int32 Value) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AAlarmEscalationFunctionalTest::WriteName(AActor* A, const TCHAR* Name,
	FName Value) const
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AAlarmEscalationFunctionalTest::ReadDials(FDials& Out) const
{
	AActor* const A = Alarm.Get();
	bool bOk = true, bThis = false;
	Out.RaiseWatch = ReadInt(A, TEXT("SightingsToRaiseWatch"), bThis); bOk &= bThis;
	Out.RaiseHunt = ReadInt(A, TEXT("SightingsToRaiseHunt"), bThis); bOk &= bThis;
	Out.DropWatch = ReadInt(A, TEXT("SightingsToDropWatch"), bThis); bOk &= bThis;
	Out.DropCalm = ReadInt(A, TEXT("SightingsToDropCalm"), bThis); bOk &= bThis;
	Out.Cap = ReadInt(A, TEXT("MaxSightingsRemembered"), bThis); bOk &= bThis;
	Out.QuietStep = ReadFloat(A, TEXT("QuietSecondsPerStepDown"), bThis); bOk &= bThis;
	Out.ScaleCalm = ReadFloat(A, TEXT("PatrolScaleWhenCalm"), bThis); bOk &= bThis;
	Out.ScaleWatching = ReadFloat(A, TEXT("PatrolScaleWhenWatching"), bThis); bOk &= bThis;
	Out.ScaleHunting = ReadFloat(A, TEXT("PatrolScaleWhenHunting"), bThis); bOk &= bThis;
	return bOk;
}

void AAlarmEscalationFunctionalTest::ReReadGuardNumbers()
{
	// EVERY FRAME. The guards trade rounds mid-run and the panel's dials change with
	// them; a fixture that cached these would be grading the first watch's yard.
	for (FGuard& G : Guards)
	{
		AActor* const A = G.Actor.Get();
		bool bOk = false;
		G.Reach = ReadFloat(A, TEXT("SightRangeUu"), bOk);
		G.HalfAngleDeg = ReadFloat(A, TEXT("SightHalfAngleDeg"), bOk);
		G.BaseSpeed = ReadFloat(A, TEXT("BasePatrolSpeedUu"), bOk);
		G.RoundTag = ReadName(A, TEXT("RoundTag"), bOk);
	}
	ReadDials(Dials);
}

bool AAlarmEscalationFunctionalTest::ReadLit(const AActor* Lamp) const
{
	// THE LIGHT, not a flag. The yard is asked to show its setting, and a burning
	// floodlight is what a reviewer sees; a bool saying so is not the thing -- and a
	// private bool is invisible to reflection anyway.
	if (Lamp == nullptr)
	{
		return false;
	}
	TArray<UPointLightComponent*> Glows;
	const_cast<AActor*>(Lamp)->GetComponents<UPointLightComponent>(Glows);
	for (const UPointLightComponent* L : Glows)
	{
		if (L == nullptr)
		{
			continue;
		}
		// Hidden and zero-intensity both read as dark: they look identical.
		if (!L->IsVisible() || L->bHiddenInGame)
		{
			return false;
		}
		return L->Intensity > 0.0f;
	}
	return false;
}

// ---------------------------------------------------------------------------
// The oracle: the same rule the yard is asked to implement, run against the same
// live transforms and the same live dials.
// ---------------------------------------------------------------------------

double AAlarmEscalationFunctionalTest::ScaleFor(int32 InStage) const
{
	if (InStage >= 2) { return Dials.ScaleHunting; }
	if (InStage == 1) { return Dials.ScaleWatching; }
	return Dials.ScaleCalm;
}

double AAlarmEscalationFunctionalTest::ReachAtStage(const FGuard& G, int32 InStage) const
{
	double Reach = G.Reach;
	for (const FLamp& L : Lamps)
	{
		// The floodlights that WOULD be burning at this setting -- the model never
		// asks the submission what it lit. A submission whose lamps are wrong computes
		// a different reach, counts different sightings, and diverges; that is the
		// interaction, and it is the reason the lamp loop is not just a readout.
		if (L.LitFromStage <= InStage && L.CoversRoundTag == G.RoundTag)
		{
			Reach += L.ReachBonusUu;
		}
	}
	return Reach;
}

bool AAlarmEscalationFunctionalTest::CanSee(const FGuard& G, const FVector& Point,
	int32 InStage, double& OutAngleDeg, double& OutDist, double& OutReach) const
{
	OutAngleDeg = 180.0;
	OutDist = 0.0;
	OutReach = 0.0;
	const AActor* const A = G.Actor.Get();
	if (A == nullptr)
	{
		return false;
	}
	const FVector Eye = A->GetActorLocation();
	// FLAT: the yard is level and the prompt says height plays no part.
	const FVector To(Point.X - Eye.X, Point.Y - Eye.Y, 0.0);
	OutDist = To.Size();
	OutReach = ReachAtStage(G, InStage);
	if (OutDist <= KINDA_SMALL_NUMBER)
	{
		OutAngleDeg = 0.0;
		return true;
	}
	const FVector Fwd = A->GetActorForwardVector();
	const FVector Facing = FVector(Fwd.X, Fwd.Y, 0.0).GetSafeNormal();
	OutAngleDeg = FMath::RadiansToDegrees(FMath::Acos(
		FMath::Clamp(FVector::DotProduct(Facing, To / OutDist), -1.0, 1.0)));
	// INCLUSIVE at both edges, exactly as the prompt states.
	return OutDist <= OutReach && OutAngleDeg <= G.HalfAngleDeg;
}

bool AAlarmEscalationFunctionalTest::AnyVerdictMarginal(const FVector& Point) const
{
	for (const FGuard& G : Guards)
	{
		double Ang = 0.0, Dist = 0.0, Reach = 0.0;
		CanSee(G, Point, StageForReach, Ang, Dist, Reach);
		if (Reach <= 0.0)
		{
			continue;
		}
		// BOTH HALVES, not either. A guard whose facing happens to sweep within a few
		// degrees of its own view width while the character is four times its reach
		// away is not marginal about anything -- and treating it as marginal would
		// suppress the gates for most of the quiet spot's dwell, which is where the
		// empty submission is supposed to die. A verdict is only marginal when the
		// boundary in question is the one deciding it.
		const bool bNearAngle = FMath::Abs(Ang - double(G.HalfAngleDeg)) < kMarginAngleDeg;
		const bool bNearRange = FMath::Abs(Dist - Reach) < Reach * kMarginReachFrac;
		if (bNearRange && Ang <= double(G.HalfAngleDeg) + kMarginAngleDeg)
		{
			return true;
		}
		if (bNearAngle && Dist <= Reach * (1.0 + kMarginReachFrac))
		{
			return true;
		}
	}
	return false;
}

void AAlarmEscalationFunctionalTest::StepModel(double Dt)
{
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	if (!Hero.IsValid())
	{
		return;
	}
	const FVector Target = Hero->GetActorLocation();

	// 1. Can anybody see him. The reach uses the setting the yard was SHOWING when the
	//    frame began -- the floodlights are thrown at the end of a frame, so what a
	//    guard can see during a frame is decided by the yard as it stood entering it.
	bool bSeen = false;
	for (const FGuard& G : Guards)
	{
		double Ang = 0.0, Dist = 0.0, Reach = 0.0;
		if (CanSee(G, Target, StageForReach, Ang, Dist, Reach))
		{
			bSeen = true;
			break;
		}
	}

	const int32 WasStage = Stage;
	const int32 WasCount = Sightings;
	const bool bSeenChanged = (bSeen != bSeenLastFrame);

	// 2. A sighting is the FALSE->TRUE edge, clamped at the panel's own cap. RawSightings
	//    is the fixture's own bookkeeping: it is how the drive knows it has over-exposed
	//    the yard far enough for the cap to be worth grading.
	if (bSeen && !bSeenLastFrame)
	{
		++RawSightings;
		Sightings = FMath::Min(Sightings + 1, Dials.Cap);
	}
	bSeenLastFrame = bSeen;

	// 3. The quiet clock: zeroed by being seen at all, otherwise forgetting one
	//    sighting per step, repeatedly.
	if (bSeen)
	{
		QuietFor = 0.0;
	}
	else
	{
		QuietFor += Dt;
		const double Step = FMath::Max(Dials.QuietStep, 0.01);
		while (QuietFor >= Step)
		{
			QuietFor -= Step;
			Sightings = FMath::Max(Sightings - 1, 0);
		}
	}

	// 4. The setting, which is a MEMORY: raise numbers and drop numbers are different,
	//    and between them nothing moves.
	while (Stage < 2
		&& Sightings >= (Stage == 0 ? Dials.RaiseWatch : Dials.RaiseHunt))
	{
		++Stage;
	}
	while (Stage > 0
		&& Sightings <= (Stage == 2 ? Dials.DropWatch : Dials.DropCalm))
	{
		--Stage;
	}

	// THE DISCRIMINATING SITUATION, RECORDED AS IT HAPPENS. A count strictly between a
	// drop number and its raise number is the only state in which a remembered setting
	// and a single threshold ladder are allowed to differ; everywhere else they agree
	// by construction. The drive is built to stand in both bands, and the run-level
	// gate refuses to report a pass unless they were both actually occupied -- so a
	// re-authored yard whose dials leave a band empty is caught as a staging fault
	// rather than quietly passing the one answer this task exists to reject.
	if (Sightings > Dials.DropCalm && Sightings < Dials.RaiseWatch)
	{
		bWasInWatchBand = true;
	}
	if (Sightings > Dials.DropWatch && Sightings < Dials.RaiseHunt)
	{
		bWasInHuntBand = true;
	}

	if (Sightings != WasCount)
	{
		// WHICH WAY the count is moving is the whole point: the same count means one
		// setting on the way up and another on the way down.
		bCountRising = (Sightings > WasCount);
	}
	if (Stage != WasStage || Sightings != WasCount || bSeenChanged)
	{
		LastModelChangeAt = Now;
	}
	if (WasStage == 0 && Stage > 0 && Leg >= 0 && Leg < 2)
	{
		++RisesInLeg[Leg];
	}
	if (Stage == 0 && RisesInLeg[0] > 0)
	{
		bReachedCalmAfterFirstRise = true;
	}
	StageForReach = Stage;
}

// ---------------------------------------------------------------------------
// Staging. Everything here ends the run as HARNESS-PRECONDITION rather than as a
// model failure: a yard that is not staged as authored is ours, never the agent's.
// ---------------------------------------------------------------------------

namespace
{
	/** Where a guard walking a straight round can see a stationary target standing
	 *  Offset uu to one side and Along uu beyond the round's own +U end. Coordinates
	 *  are the guard's position along the round, in [-HalfLen, +HalfLen]. */
	struct FSweepWindow
	{
		bool bEverVisible = false;
		double Lo = 0.0;
		double Hi = 0.0;
		double Width = 0.0;
		double AngleExit = 0.0;   // where the cone edge lets go of the target
	};

	FSweepWindow SweepWindow(double Reach, double HalfAngleDeg, double Offset,
		double Along, double HalfLen)
	{
		FSweepWindow W;
		const double Th = FMath::DegreesToRadians(FMath::Clamp(HalfAngleDeg, 0.1, 89.0));
		// The furthest to one side this guard can EVER hold a target: reach x sin(view
		// width). Derived from the cone predicate (the minimum along-track lead that
		// clears the half-angle is Offset/tan(theta), and the distance there is
		// Offset/sin(theta)); PrepareTest then re-checks it by simulating the round
		// rather than trusting the closed form.
		if (Offset >= Reach * FMath::Sin(Th))
		{
			return W;
		}
		W.AngleExit = Along - Offset / FMath::Tan(Th);
		const double RangeEntry = Along - FMath::Sqrt(FMath::Max(
			Reach * Reach - Offset * Offset, 0.0));
		W.Lo = FMath::Max(RangeEntry, -HalfLen);
		W.Hi = FMath::Min(W.AngleExit, HalfLen);
		W.Width = FMath::Max(W.Hi - W.Lo, 0.0);
		W.bEverVisible = W.Width > 0.0;
		return W;
	}
}

bool AAlarmEscalationFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;

	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("WatchGuard")), Found);
	if (Found.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - expected "
				 "two guards tagged WatchGuard, found %d"), Found.Num()));
		return false;
	}
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	for (AActor* A : Found)
	{
		FGuard G;
		G.Actor = A;
		Guards.Add(G);
	}

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardLamp")), Found);
	if (Found.Num() < 4)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - expected "
				 "at least four floodlights tagged YardLamp, found %d"), Found.Num()));
		return false;
	}
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	int32 LampIndex = 0;
	for (AActor* A : Found)
	{
		FLamp L;
		bool bOk = false;
		bool bAll = true;
		L.Actor = A;
		L.LitFromStage = ReadInt(A, TEXT("LitFromStage"), bOk); bAll = bAll && bOk;
		L.ReachBonusUu = ReadFloat(A, TEXT("ReachBonusUu"), bOk); bAll = bAll && bOk;
		L.CoversRoundTag = ReadName(A, TEXT("CoversRoundTag"), bOk); bAll = bAll && bOk;
		L.Label = FString::Printf(TEXT("lamp %d"), ++LampIndex);
		if (!bAll)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose LitFromStage / "
					 "ReachBonusUu / CoversRoundTag readably, so the fixture cannot "
					 "tell what the yard is supposed to be showing"), *L.Label));
			return false;
		}
		TArray<UPointLightComponent*> Glows;
		A->GetComponents<UPointLightComponent>(Glows);
		if (Glows.Num() == 0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s has no light, so the fixture cannot "
					 "tell whether it is burning"), *L.Label));
			return false;
		}
		Lamps.Add(L);
	}

	// THE FLOODLIGHTS MUST NOT BE IN ORDER. A yard whose lamps read 0,1,2,... in name
	// order is passed by "light the first N of them", and this task claims to measure
	// reading each light for itself.
	bool bMonotone = true;
	for (int32 i = 1; i < Lamps.Num(); ++i)
	{
		if (Lamps[i].LitFromStage < Lamps[i - 1].LitFromStage)
		{
			bMonotone = false;
			break;
		}
	}
	if (bMonotone)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the floodlights' settings run in order along "
				 "their names, so lighting the first N of them would pass and the "
				 "gate would measure nothing"));
		return false;
	}

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardAlarm")), Found);
	if (Found.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - expected "
				 "one panel tagged YardAlarm, found %d"), Found.Num()));
		return false;
	}
	Alarm = Found[0];
	if (!ReadDials(Dials))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the panel does not expose all nine dials "
				 "readably, so the fixture cannot tell what the yard is working to"));
		return false;
	}
	// The dials must describe a machine that can HOLD a setting: a raise number at or
	// below its own drop number is not hysteresis, it is a flapping ladder, and the
	// deadband gates would have nothing to stand on.
	if (!(Dials.DropCalm < Dials.RaiseWatch && Dials.DropWatch < Dials.RaiseHunt
		&& Dials.DropCalm <= Dials.DropWatch && Dials.RaiseWatch <= Dials.RaiseHunt
		&& Dials.RaiseHunt <= Dials.Cap && Dials.QuietStep > 0.5
		&& Dials.ScaleCalm > 0.0 && Dials.ScaleWatching > Dials.ScaleCalm * 1.1
		&& Dials.ScaleHunting > Dials.ScaleWatching * 1.1))
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the panel's dials do not describe a yard that "
				 "can hold a setting (raise %d/%d, drop %d/%d, cap %d, quiet %.1fs, "
				 "scales %.2f/%.2f/%.2f)"),
			Dials.RaiseWatch, Dials.RaiseHunt, Dials.DropWatch, Dials.DropCalm,
			Dials.Cap, Dials.QuietStep, Dials.ScaleCalm, Dials.ScaleWatching,
			Dials.ScaleHunting));
		return false;
	}

	ReReadGuardNumbers();
	for (const FGuard& G : Guards)
	{
		if (G.Reach <= 100.0f || G.HalfAngleDeg <= 1.0f || G.HalfAngleDeg >= 89.0f
			|| G.BaseSpeed <= 10.0f || G.RoundTag.IsNone())
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a guard's own numbers are unusable "
					 "(reach %.0f, view width %.1f deg, base pace %.0f, round '%s')"),
				G.Reach, G.HalfAngleDeg, G.BaseSpeed, *G.RoundTag.ToString()));
			return false;
		}
	}
	if (Guards[0].RoundTag == Guards[1].RoundTag)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: both guards are set to walk the same round, so "
				 "there is no watch to change"));
		return false;
	}
	if (FMath::Abs(Guards[0].BaseSpeed - Guards[1].BaseSpeed) < 20.0f)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the two guards' base paces are %.0f and %.0f; "
				 "one flat speed would fit both and the pace gate would measure "
				 "nothing"), Guards[0].BaseSpeed, Guards[1].BaseSpeed));
		return false;
	}

	WatchedRoundTag = Guards[0].RoundTag;
	FarRoundTag = Guards[1].RoundTag;
	const FName RoundTags[2] = { WatchedRoundTag, FarRoundTag };
	for (int32 t = 0; t < 2; ++t)
	{
		Found.Reset();
		UGameplayStatics::GetAllActorsWithTag(World, RoundTags[t], Found);
		if (Found.Num() != 2)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the round '%s' is marked by %d post(s), "
					 "expected exactly two"), *RoundTags[t].ToString(), Found.Num()));
			return false;
		}
		Found.Sort([](const AActor& L, const AActor& R)
		{
			return L.GetName() < R.GetName();
		});
		for (AActor* A : Found)
		{
			Posts.Add(A);
			StagedPostAt.Add(A->GetActorLocation());
		}
	}

	// At least one floodlight has to feed back into somebody's eyes, or the two halves
	// of this task never touch and it is two independent readouts of one number.
	bool bAnyBonus = false;
	for (const FLamp& L : Lamps)
	{
		if (L.ReachBonusUu > 0.0f
			&& (L.CoversRoundTag == WatchedRoundTag || L.CoversRoundTag == FarRoundTag))
		{
			bAnyBonus = true;
		}
	}
	if (!bAnyBonus)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no floodlight throws light down a round, so "
				 "the floodlights and the guards' eyes never touch and the task is "
				 "two independent readouts of one number"));
		return false;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in "
				 "the yard"));
		return false;
	}
	WalkZ = Hero->GetActorLocation().Z;
	if (const UCharacterMovementComponent* const Move = Hero->GetCharacterMovement())
	{
		// MEASURED, not assumed: every phase deadline is derived from this.
		HeroSpeed = FMath::Max(double(Move->GetMaxSpeed()), 100.0);
	}
	return true;
}

// ---------------------------------------------------------------------------
// The geometry. Every place the drive stands is SOLVED from the round and the guards'
// own numbers, never written down -- so a re-authored yard with different guards moves
// the drive with it, and no stop can drift onto a boundary where a correct answer
// could round the wrong way.
// ---------------------------------------------------------------------------

double AAlarmEscalationFunctionalTest::ReachOnRound(const FGuard& G, int32 InStage,
	FName Tag) const
{
	double Reach = G.Reach;
	for (const FLamp& L : Lamps)
	{
		if (L.LitFromStage <= InStage && L.CoversRoundTag == Tag)
		{
			Reach += L.ReachBonusUu;
		}
	}
	return Reach;
}

double AAlarmEscalationFunctionalTest::LapSecondsFor(const FGuard& G, int32 InStage) const
{
	const double Speed = FMath::Max(double(G.BaseSpeed) * ScaleFor(InStage), 1.0);
	return 4.0 * RoundHalfLen / Speed;
}

double AAlarmEscalationFunctionalTest::QuietBetweenSightings(const FGuard& G,
	double Offset, double AlongPos, int32 InStage) const
{
	// AT THE OFFSET THE DRIVE PARKS AT, not the one it aims for. DriveHero stops
	// applying input the moment the character is within kWaypointUu of the waypoint, so
	// it can settle up to that far off; the component of that error that matters is the
	// one PERPENDICULAR to the round, because it is the only one that changes the
	// window (an along-track error slides both ends of the window together and leaves
	// its width alone). Further off means a shorter sighting and therefore a LONGER
	// quiet, so this is the conservative direction and the one the forget clock sees.
	const double R = ReachOnRound(G, InStage, WatchedRoundTag);
	const FSweepWindow W = SweepWindow(R, G.HalfAngleDeg, Offset + kWaypointUu,
		AlongPos, RoundHalfLen);
	// W.Width is 0 when the parked spot is out of the cone entirely, which yields a
	// whole lap of quiet -- correctly the worst answer this can return.
	const double Speed = FMath::Max(double(G.BaseSpeed) * ScaleFor(InStage), 1.0);
	return (4.0 * RoundHalfLen - W.Width) / Speed;
}

// Trailing return type on purpose: FGuard is a PRIVATE nested type, and a leading
// return type on an out-of-class definition is looked up in namespace scope, where it
// is inaccessible. After the declarator-id, class scope applies.
auto AAlarmEscalationFunctionalTest::CoveringGuard() const -> const FGuard*
{
	for (const FGuard& G : Guards)
	{
		if (G.RoundTag == WatchedRoundTag) { return &G; }
	}
	return nullptr;
}

auto AAlarmEscalationFunctionalTest::FarGuard() const -> const FGuard*
{
	for (const FGuard& G : Guards)
	{
		if (G.RoundTag != WatchedRoundTag) { return &G; }
	}
	return nullptr;
}

bool AAlarmEscalationFunctionalTest::BuildSpots()
{
	// The watched round is the pair of posts the first guard is set to walk; the other
	// pair is the far round. Both are read off the level, never assumed.
	const FVector A = StagedPostAt[0];
	const FVector B = StagedPostAt[1];
	const FVector FarCentre = (StagedPostAt[2] + StagedPostAt[3]) * 0.5;

	RoundCentre = FVector((A.X + B.X) * 0.5, (A.Y + B.Y) * 0.5, WalkZ);
	FVector Along(B.X - A.X, B.Y - A.Y, 0.0);
	RoundHalfLen = Along.Size() * 0.5;
	if (RoundHalfLen < 300.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the watched round is only %.0f uu long; there "
				 "is no room for a guard to sweep anybody"), RoundHalfLen * 2.0));
		return false;
	}
	// THE ROUND AND THE FORGET CLOCK HAVE TO FIT EACH OTHER, and this is the cheapest
	// place to say so because it needs nothing but the round, the paces and one dial.
	//
	// Every dwell spot the drive uses sits PAST the end of the round on purpose (see
	// the scan below), so a guard sights the character exactly ONCE per there-and-back:
	// on the return pass the target is behind it at more than ninety degrees. Between
	// two sightings there is therefore a stretch of unbroken quiet, and the panel
	// forgets one sighting per QuietStep of it. If that stretch is the longer of the
	// two, the count is knocked back down between every sighting, oscillates 0<->1 for
	// ever, and NOTHING the drive waits for -- the raise numbers, the cap -- can ever
	// happen. The drive would then simply run out its phase-3 deadline and report a
	// timeout, which says nothing about which number is wrong.
	//
	// The floor on that stretch is HALF A LAP: the widest sighting window physically
	// available is the whole outbound pass (2 x RoundHalfLen of travel), and the pace
	// that matters is the CALM one, because that is the setting the count has to start
	// climbing from and it is the slowest. So if half a lap at the calm pace is already
	// >= QuietStep, no offset, no along-track position and no re-routing can rescue it
	// -- the level's own numbers are the thing that has to move.
	//
	// Measured on the shipped yard 2026-08-19: half a lap is 1400/280 = 5.00 s (Slit)
	// and 1400/260 = 5.38 s (Wide), against a forget step that shipped at 5.00 s. That
	// is exactly the disagreement this fixture used to die of, 115 s into phase 3, with
	// nothing in the message pointing at the dial.
	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		const double HalfLapS = 2.0 * RoundHalfLen
			/ FMath::Max(double(Guards[i].BaseSpeed) * ScaleFor(0), 1.0);
		if (HalfLapS >= Dials.QuietStep)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: guard %d comes round its own %.0f uu of "
					 "round no more often than every %.2f s at its calm pace of %.0f "
					 "uu/s, and the panel forgets a sighting after %.2f s of quiet. A "
					 "spot past the end of the round is sighted once per lap, so the "
					 "count would be forgotten between every sighting and could never "
					 "reach the raise number %d, let alone the cap %d. The round, the "
					 "paces and the forget step do not fit each other"),
				i + 1, RoundHalfLen * 2.0, HalfLapS, double(Guards[i].BaseSpeed) * ScaleFor(0),
				Dials.QuietStep, Dials.RaiseWatch, Dials.Cap));
			return false;
		}
	}

	RoundU = Along.GetSafeNormal();
	const FVector Perp(-RoundU.Y, RoundU.X, 0.0);
	const FVector ToFar(FarCentre.X - RoundCentre.X, FarCentre.Y - RoundCentre.Y, 0.0);
	// The drive walks on the side AWAY from the far round, so the far guard is never
	// the reason anything happens and the two rounds cannot be confused.
	RoundV = (FVector::DotProduct(Perp, ToFar) > 0.0) ? -Perp : Perp;

	// How far to one side each guard can EVER hold somebody: unlit, and lit up as far
	// as the floodlights covering this round can take it.
	double UnlitLimit[2] = {0.0, 0.0};
	double LitLimit[2] = {0.0, 0.0};
	for (int32 i = 0; i < 2; ++i)
	{
		const double S = FMath::Sin(FMath::DegreesToRadians(Guards[i].HalfAngleDeg));
		UnlitLimit[i] = Guards[i].Reach * S;
		LitLimit[i] = ReachOnRound(Guards[i], 2, WatchedRoundTag) * S;
	}
	const int32 Narrow = (LitLimit[0] <= LitLimit[1]) ? 0 : 1;
	const int32 Wide = 1 - Narrow;
	// THE TWO GUARDS MUST NOT SEE ALIKE. If their reaches overlap, no spot means
	// opposite things to them and the whole watch change measures nothing.
	if (UnlitLimit[Wide] < LitLimit[Narrow] * 2.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the guards hold somebody out to %.0f uu and "
				 "%.0f uu off their round - less than 2x apart, so no spot means "
				 "opposite things to them and the watch change proves nothing"),
			LitLimit[Narrow], UnlitLimit[Wide]));
		return false;
	}

	OffsetSeen = kSeenSpotFraction * FMath::Min(UnlitLimit[0], UnlitLimit[1]);
	// The split spot: the geometric mean of "the narrow guard can never reach here,
	// even lit" and "the wide guard reaches comfortably past here". That puts it well
	// clear of both, and it moves with the level rather than being a written number.
	OffsetSplit = FMath::Sqrt(LitLimit[Narrow] * UnlitLimit[Wide]);
	if (OffsetSplit < LitLimit[Narrow] * 1.35 || OffsetSplit > UnlitLimit[Wide] * 0.75)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: no offset is both plainly beyond the narrow "
				 "guard (%.0f uu lit) and plainly inside the wide one (%.0f uu)"),
			LitLimit[Narrow], UnlitLimit[Wide]));
		return false;
	}

	// Score a candidate along-track position: the worst slack, over all three settings,
	// between the sighting window this guard would get and the two seconds the fixture
	// needs to be able to judge anything inside it. A candidate the count could never
	// climb at is not scored at all -- see QuietBetweenSightings.
	auto Score = [this](int32 GuardIdx, double Offset, double AlongPos, bool& bOk) -> double
	{
		const FGuard& G = Guards[GuardIdx];
		double Worst = 1.0e9;
		bOk = true;
		for (int32 S = 0; S <= 2; ++S)
		{
			const double R = ReachOnRound(G, S, WatchedRoundTag);
			const FSweepWindow W = SweepWindow(R, G.HalfAngleDeg, Offset, AlongPos,
				RoundHalfLen);
			if (!W.bEverVisible) { bOk = false; return 0.0; }
			// The cone edge must let go of the target either WELL inside the round (a
			// clean, transverse crossing) or not at all before the guard turns (a
			// clean 180-degree flip). Letting go a few uu short of the post is the one
			// shape where a frame of sampling order could add or drop an edge.
			if (W.AngleExit > RoundHalfLen - 80.0 && W.AngleExit < RoundHalfLen)
			{
				bOk = false;
				return 0.0;
			}
			// AND THE COUNT MUST BE ABLE TO CLIMB HERE. One sighting per lap is only
			// worth anything if the panel still remembers it when the next one lands.
			// Measured against the dial the panel is CURRENTLY carrying, so a
			// re-authored yard with a different forget step moves the search with it.
			if (QuietBetweenSightings(G, Offset, AlongPos, S) >= Dials.QuietStep)
			{
				bOk = false;
				return 0.0;
			}
			const double Speed = FMath::Max(double(G.BaseSpeed) * ScaleFor(S), 1.0);
			const double Lap = 4.0 * RoundHalfLen;
			Worst = FMath::Min(Worst, FMath::Min(W.Width / Speed - kMinWindowS,
				(Lap - W.Width) / Speed - kMinGapS));
		}
		return Worst;
	};

	double MaxReachAnywhere = 0.0;
	for (int32 i = 0; i < 2; ++i)
	{
		MaxReachAnywhere = FMath::Max(MaxReachAnywhere,
			FMath::Max(ReachOnRound(Guards[i], 2, WatchedRoundTag),
				ReachOnRound(Guards[i], 2, FarRoundTag)));
	}

	// Scan the lane beyond the round's own end for the two standing places. Beyond the
	// end is not decoration: with the target ahead of the round, the RETURN pass has it
	// behind the guard at more than 90 degrees, so a guard can only ever sight it on
	// the outbound pass -- one edge per lap, whatever its reach.
	double BestSeen = -1.0e9;
	double BestSplit = -1.0e9;
	for (double X = RoundHalfLen + 40.0; X < RoundHalfLen + 3.4 * MaxReachAnywhere;
		X += 20.0)
	{
		bool bOk0 = false, bOk1 = false;
		const double S0 = Score(0, OffsetSeen, X, bOk0);
		const double S1 = Score(1, OffsetSeen, X, bOk1);
		if (bOk0 && bOk1 && S0 > 0.0 && S1 > 0.0)
		{
			const double S = FMath::Min(S0, S1);
			if (S > BestSeen) { BestSeen = S; AlongSeen = X; }
		}
		bool bOkW = false;
		const double SW = Score(Wide, OffsetSplit, X, bOkW);
		if (bOkW && SW > 0.0 && SW > BestSplit) { BestSplit = SW; AlongSplit = X; }
	}
	if (BestSeen <= 0.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: nowhere on the lane gives BOTH guards a "
				 "sighting window long enough to judge AND a quiet stretch between "
				 "sightings shorter than the panel's %.2f s forget step - the round, "
				 "the reaches, the patrol scales and that dial do not fit together"),
			Dials.QuietStep));
		return false;
	}
	if (BestSplit <= 0.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: nowhere on the lane gives the wide guard a "
				 "sighting window long enough to judge, and a quiet stretch shorter "
				 "than the panel's %.2f s forget step, at the offset the narrow guard "
				 "can never reach"), Dials.QuietStep));
		return false;
	}

	SpotSeen = RoundCentre + RoundU * AlongSeen + RoundV * OffsetSeen;
	SpotSplit = RoundCentre + RoundU * AlongSplit + RoundV * OffsetSplit;
	SpotSeen.Z = WalkZ;
	SpotSplit.Z = WalkZ;
	// THE LANE. Every transit runs at the split spot's own offset, then turns in. In
	// the first watch the narrow guard cannot see ANY of that lane, so the walk to the
	// close-in spot crosses its cone once, head-on, at the very end -- never skimming
	// a boundary, which is the one way two honest counters could disagree.
	LaneOverSeen = RoundCentre + RoundU * AlongSeen + RoundV * OffsetSplit;
	LaneOverSeen.Z = WalkZ;

	// The quiet spot: far enough along the same lane that NEITHER guard reaches it
	// from EITHER round, with a quarter of its reach to spare.
	const FVector WatchA(StagedPostAt[0].X, StagedPostAt[0].Y, WalkZ);
	const FVector WatchB(StagedPostAt[1].X, StagedPostAt[1].Y, WalkZ);
	const FVector FarA(StagedPostAt[2].X, StagedPostAt[2].Y, WalkZ);
	const FVector FarB(StagedPostAt[3].X, StagedPostAt[3].Y, WalkZ);
	bool bFoundQuiet = false;
	for (double X = AlongSplit + 400.0; X < AlongSplit + 24000.0; X += 50.0)
	{
		const FVector P = RoundCentre + RoundU * X + RoundV * OffsetSplit;
		const double D = FMath::Min(
			double(FMath::PointDistToSegment(P, WatchA, WatchB)),
			double(FMath::PointDistToSegment(P, FarA, FarB)));
		if (D >= MaxReachAnywhere * 1.35)
		{
			SpotQuiet = FVector(P.X, P.Y, WalkZ);
			bFoundQuiet = true;
			break;
		}
	}
	if (!bFoundQuiet)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: there is nowhere on the lane that is out of "
				 "reach of both rounds by a quarter (largest reach %.0f uu)"),
			MaxReachAnywhere));
		return false;
	}
	return true;
}

bool AAlarmEscalationFunctionalTest::ValidateGeometry()
{
	// Re-run for the leg in progress against the dials as they NOW read: the sergeant
	// changes the hunting scale, and a faster guard means a shorter sighting window.
	const FGuard* const Cover = CoveringGuard();
	const FGuard* const Far = FarGuard();
	if (Cover == nullptr || Far == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no guard is set to walk the watched round"));
		return false;
	}
	const double Lap = 4.0 * RoundHalfLen;

	// WHICH WATCH THIS IS, decided from the covering guard's own eyes rather than from
	// a leg number: either it can never hold anybody at the split spot (the watch where
	// the yard must notice nothing there), or it holds them comfortably (the watch
	// where it must). Anything in between and the two watches would not disagree.
	double SplitLimitWorst = 1.0e9;
	double SplitLimitBest = 0.0;
	for (int32 S = 0; S <= 2; ++S)
	{
		const double L = ReachOnRound(*Cover, S, WatchedRoundTag)
			* FMath::Sin(FMath::DegreesToRadians(Cover->HalfAngleDeg));
		SplitLimitWorst = FMath::Min(SplitLimitWorst, L);
		SplitLimitBest = FMath::Max(SplitLimitBest, L);
	}
	const bool bCoverIsBlindAtSplit = (OffsetSplit >= SplitLimitBest * 1.35);
	const bool bCoverSeesSplit = (OffsetSplit <= SplitLimitWorst * 0.75);
	if (!bCoverIsBlindAtSplit && !bCoverSeesSplit)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the split spot is %.0f uu off the round and "
				 "the covering guard holds somebody out to between %.0f and %.0f uu "
				 "there; it is neither plainly blind to it nor plainly sighted on it, "
				 "so this watch proves nothing either way"),
			OffsetSplit, SplitLimitWorst, SplitLimitBest));
		return false;
	}

	// The spots this leg actually stands on, and what the covering guard must be able
	// to do at each. The close-in spot is only visited on the first watch.
	//
	// NOTE what this list IS: every place this leg stands where a sighting is meant to
	// happen, and therefore every place where the count is meant to CLIMB. The split
	// spot is added only on the watch where the covering guard can see it -- on the
	// other watch the drive stands there precisely to prove nothing is noticed, and
	// nothing below applies. So the climb check can ride along with the window check
	// without a second list to keep in step.
	struct FCase { double Offset; double Along; const TCHAR* What; };
	TArray<FCase> Cases;
	if (Leg == 0)
	{
		Cases.Add(FCase{ OffsetSeen, AlongSeen, TEXT("the close-in spot") });
	}
	if (bCoverSeesSplit)
	{
		Cases.Add(FCase{ OffsetSplit, AlongSplit, TEXT("the split spot") });
	}
	// WHAT THE WINDOW CHECK BELOW MEASURES, EXACTLY, because the difference has been
	// misread before: the sighting at the offset the drive AIMS for. The drive can
	// settle up to kWaypointUu further off the round, and the same sighting is shorter
	// there -- measured on this yard, the close-in spot's 3.91 / 2.79 / 2.53 s become
	// 2.47 / 1.77 / 1.75 s at the worst parked offset, i.e. under the kMinWindowS bar
	// at two of the three settings. That is deliberately NOT what this gate stands on,
	// and it is not a hole: a shorter window costs JUDGED FRAMES and never changes a
	// verdict, and 1.75 s is still more than twice the 0.75 s the fixture suppresses
	// after a change in its own model, so there is judging time inside every sighting
	// wherever the drive ends up. The thing a parked offset genuinely can break -- the
	// count no longer climbing, because the quiet between two sightings grows past the
	// panel's forget step -- IS measured at the parked offset, in the check that
	// follows this one. Tightening this one to the parked offset instead would fail
	// this yard's geometry outright rather than make it safer.
	for (const FCase& C : Cases)
	{
		for (int32 S = 0; S <= 2; ++S)
		{
			const double R = ReachOnRound(*Cover, S, WatchedRoundTag);
			const FSweepWindow W = SweepWindow(R, Cover->HalfAngleDeg, C.Offset,
				C.Along, RoundHalfLen);
			const double Speed = FMath::Max(double(Cover->BaseSpeed) * ScaleFor(S), 1.0);
			if (!W.bEverVisible || W.Width / Speed < kMinWindowS
				|| (Lap - W.Width) / Speed < kMinGapS)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: on watch %d, %s gives the covering "
						 "guard a %.2fs sighting and a %.2fs gap at setting %d (pace "
						 "%.0f uu/s, reach %.0f); the fixture needs %.1fs of each to "
						 "judge anything through its own settle window"),
					Leg + 1, C.What, W.Width / Speed, (Lap - W.Width) / Speed, S,
					Speed, R, kMinWindowS));
				return false;
			}
			// AND THE COUNT MUST BE ABLE TO CLIMB HERE. The window and the gap above
			// are about whether the fixture can JUDGE a sighting; this is about whether
			// a sighting is worth anything by the time the next one arrives. The drive
			// stands at every one of these spots waiting for a number it can only reach
			// by accumulating, so if the panel forgets faster than the guard comes
			// round, the phase never ends and the run dies as an unexplained timeout.
			// Measured at the PARKED offset, and against the dial the panel is
			// currently carrying -- both read from the world, so neither can drift out
			// of step with the level the way a written-down number would.
			const double QuietS = QuietBetweenSightings(*Cover, C.Offset, C.Along, S);
			if (QuietS >= Dials.QuietStep)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: on watch %d, %s leaves the covering "
						 "guard %.2fs of quiet between one sighting and the next at "
						 "setting %d (pace %.0f uu/s, reach %.0f), and the panel "
						 "forgets a sighting after %.2fs of quiet. The count would be "
						 "knocked back down between every sighting and could never "
						 "reach the raise number %d or the cap %d, so the drive would "
						 "wait for a setting that never comes"),
					Leg + 1, C.What, QuietS, S, Speed, R, Dials.QuietStep,
					Dials.RaiseWatch, Dials.Cap));
				return false;
			}
		}
	}

	// THE GUARD ON THE OTHER ROUND MUST BE IRRELEVANT. Everywhere the drive goes is on
	// the far side of the watched round, so the far guard should never reach any of it
	// -- otherwise a sighting the drive did not intend lands in the middle of a graded
	// window and both counters have to agree about something nobody designed.
	const FVector FarA(StagedPostAt[2].X, StagedPostAt[2].Y, WalkZ);
	const FVector FarB(StagedPostAt[3].X, StagedPostAt[3].Y, WalkZ);
	const FVector Route[4] = { SpotQuiet, SpotSplit, LaneOverSeen, SpotSeen };
	double FarReach = 0.0;
	for (int32 S = 0; S <= 2; ++S)
	{
		FarReach = FMath::Max(FarReach, ReachOnRound(*Far, S, FarRoundTag));
	}
	for (int32 i = 0; i + 1 < 4; ++i)
	{
		for (int32 k = 0; k <= 8; ++k)
		{
			const FVector P = FMath::Lerp(Route[i], Route[i + 1], double(k) / 8.0);
			const double D = FMath::PointDistToSegment(P, FarA, FarB);
			if (D < FarReach * 1.25)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: the route passes %.0f uu from the "
						 "other round and the guard on it reaches %.0f uu; the drive "
						 "would collect sightings nobody designed"), D, FarReach));
				return false;
			}
		}
	}
	return true;
}

bool AAlarmEscalationFunctionalTest::ValidateSightlines()
{
	// THE YARD PROMISES THERE IS NOTHING TO HIDE BEHIND, and the fixture's own model
	// never asks whether anything is in the way. A submission that DOES ask -- an
	// entirely ordinary thing to write for "a guard notices you" -- must get the same
	// answer, so nothing in the yard may block a sightline anywhere on the route.
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	TArray<FVector> Probe;
	const FVector Route[4] = { SpotQuiet, SpotSplit, LaneOverSeen, SpotSeen };
	for (int32 i = 0; i + 1 < 4; ++i)
	{
		for (int32 k = 0; k <= 4; ++k)
		{
			Probe.Add(FMath::Lerp(Route[i], Route[i + 1], double(k) / 4.0));
		}
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(AlarmYardSightline), true);
	Params.AddIgnoredActor(Hero.Get());
	for (const FGuard& G : Guards)
	{
		Params.AddIgnoredActor(G.Actor.Get());
	}
	for (FGuard& G : Guards)
	{
		AActor* const A = G.Actor.Get();
		if (A == nullptr) { continue; }
		const FTransform Was = A->GetActorTransform();
		const FVector EndA = (G.RoundTag == WatchedRoundTag)
			? FVector(StagedPostAt[0].X, StagedPostAt[0].Y, Was.GetLocation().Z)
			: FVector(StagedPostAt[2].X, StagedPostAt[2].Y, Was.GetLocation().Z);
		const FVector EndB = (G.RoundTag == WatchedRoundTag)
			? FVector(StagedPostAt[1].X, StagedPostAt[1].Y, Was.GetLocation().Z)
			: FVector(StagedPostAt[3].X, StagedPostAt[3].Y, Was.GetLocation().Z);
		for (int32 p = 0; p <= 8; ++p)
		{
			const FVector At = FMath::Lerp(EndA, EndB, double(p) / 8.0);
			A->SetActorLocation(At, /*bSweep=*/false);
			for (const FVector& Target : Probe)
			{
				FHitResult Hit;
				if (World->LineTraceSingleByChannel(Hit, At,
					FVector(Target.X, Target.Y, Was.GetLocation().Z),
					ECC_Visibility, Params))
				{
					const FString Blocker = Hit.GetActor()
						? Hit.GetActor()->GetName() : TEXT("<unknown>");
					A->SetActorTransform(Was);
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: %s blocks a guard's line to the "
							 "route, and the yard promises there is nothing to hide "
							 "behind; a submission that checks for cover would count "
							 "different sightings from the fixture"), *Blocker));
					return false;
				}
			}
		}
		A->SetActorTransform(Was);
	}
	return true;
}

// ---------------------------------------------------------------------------
// Staging a leg, and the watch change.
// ---------------------------------------------------------------------------

void AAlarmEscalationFunctionalTest::StageLeg(int32 LegIndex)
{
	UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	Leg = LegIndex;

	if (LegIndex == 1)
	{
		// THE WATCH CHANGES. The two guards trade rounds and the sergeant re-sets two
		// of the dials. Nothing announces it, and every number is read live by the
		// fixture from here on -- a submission that cached them at the start is now
		// working to last night's yard.
		AActor* const G0 = Guards[0].Actor.Get();
		AActor* const G1 = Guards[1].Actor.Get();
		const FName Was0 = Guards[0].RoundTag;
		const FName Was1 = Guards[1].RoundTag;
		if (G0 == nullptr || G1 == nullptr
			|| !WriteName(G0, TEXT("RoundTag"), Was1)
			|| !WriteName(G1, TEXT("RoundTag"), Was0))
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the guards' RoundTag could not be written, "
					 "so the watch cannot change and half the task is unreachable"));
			return;
		}
		// Put each guard on the near end of the round it has just been given.
		for (int32 i = 0; i < 2; ++i)
		{
			AActor* const A = Guards[i].Actor.Get();
			const FName NewTag = (i == 0) ? Was1 : Was0;
			const int32 Base = (NewTag == WatchedRoundTag) ? 0 : 2;
			const FVector NearEnd(StagedPostAt[Base].X, StagedPostAt[Base].Y,
				A->GetActorLocation().Z);
			A->SetActorLocation(NearEnd, /*bSweep=*/false);
		}
		AActor* const Panel = Alarm.Get();
		const int32 NewRaiseWatch = Dials.RaiseWatch + 1;
		const float NewHuntScale = float(Dials.ScaleHunting * 1.1667);
		if (!WriteInt(Panel, TEXT("SightingsToRaiseWatch"), NewRaiseWatch)
			|| !WriteFloat(Panel, TEXT("PatrolScaleWhenHunting"), NewHuntScale))
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the panel's dials could not be re-set, so "
					 "nothing tests whether they are read at the point of use"));
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("[t2-alarm] WATCH CHANGE at t=%.2f: '%s' <-> '%s', raise-watch "
				 "%d -> %d, hunting scale %.2f -> %.2f"),
			Now, *Was0.ToString(), *Was1.ToString(), Dials.RaiseWatch, NewRaiseWatch,
			Dials.ScaleHunting, NewHuntScale);
	}

	ReReadGuardNumbers();

	// Baseline everything the yard is not allowed to change, for THIS leg.
	for (FGuard& G : Guards)
	{
		G.StagedReach = G.Reach;
		G.StagedHalfAngleDeg = G.HalfAngleDeg;
		G.StagedBaseSpeed = G.BaseSpeed;
		G.StagedRoundTag = G.RoundTag;
		const int32 Base = (G.RoundTag == WatchedRoundTag) ? 0 : 2;
		G.RoundA = FVector(StagedPostAt[Base].X, StagedPostAt[Base].Y, WalkZ);
		G.RoundB = FVector(StagedPostAt[Base + 1].X, StagedPostAt[Base + 1].Y, WalkZ);
	}
	for (FLamp& L : Lamps)
	{
		AActor* const A = L.Actor.Get();
		bool bOk = false;
		L.LitFromStage = ReadInt(A, TEXT("LitFromStage"), bOk);
		L.ReachBonusUu = ReadFloat(A, TEXT("ReachBonusUu"), bOk);
		L.CoversRoundTag = ReadName(A, TEXT("CoversRoundTag"), bOk);
		L.StagedLitFromStage = L.LitFromStage;
		L.StagedReachBonusUu = L.ReachBonusUu;
		L.StagedCoversRoundTag = L.CoversRoundTag;
	}
	StagedDials = Dials;

	// Nothing is judged for a moment after a re-staging: the guards were teleported
	// and two dials moved, and neither is the submission's doing.
	StagingUntil = Now + 2.0;
}

// ---------------------------------------------------------------------------
// PrepareTest
// ---------------------------------------------------------------------------

void AAlarmEscalationFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	if (!BuildSpots())
	{
		return;
	}
	StageLeg(0);
	if (!ValidateGeometry())
	{
		return;
	}
	if (!ValidateSightlines())
	{
		return;
	}

	// The model starts where the yard starts: calm, nothing counted.
	Stage = 0;
	StageForReach = 0;
	Sightings = 0;
	RawSightings = 0;
	bSeenLastFrame = false;
	QuietFor = 0.0;
	LastModelChangeAt = -100.0;
	Phase = 0;
	PhaseStartedAt = 0.0;
	HoldSince = -1.0;
	Waypoints.Reset();
	Waypoints.Add(SpotQuiet);
	WaypointIndex = 0;
	// Phase 0 is the walk from wherever the level spawned the character to the quiet
	// spot. Its deadline comes off the MEASURED distance and the MEASURED hero pace,
	// like every other walk.
	PhaseDeadline = FVector::Dist2D(Hero->GetActorLocation(), SpotQuiet) / HeroSpeed
		* 2.5 + 20.0;

	UE_LOG(LogTemp, Display,
		TEXT("[t2-alarm] round '%s' half-length %.0f; offsets seen %.0f split %.0f; "
			 "along seen %.0f split %.0f; quiet at (%.0f,%.0f); hero pace %.0f uu/s"),
		*WatchedRoundTag.ToString(), RoundHalfLen, OffsetSeen, OffsetSplit,
		AlongSeen, AlongSplit, SpotQuiet.X, SpotQuiet.Y, HeroSpeed);

	// The last entry is a SENTINEL, far past the drive, because the base class ends the
	// test the moment the last scheduled checkpoint is sampled. The drive models about
	// 300 s of world time; the sentinel is a third again past that, and the fixture
	// finishes itself as soon as its last phase completes.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelAtS);
	SetCheckpointSchedule(Schedule);
	bPrepared = true;
}

// ---------------------------------------------------------------------------
// The drive. Every standing phase is "stay here until MY model says X", never "stay
// here for T seconds" -- which is what makes it immune to the feedback loop (raising
// the setting speeds the guards up, which changes how often their cones sweep anybody,
// which changes how fast the count climbs).
//
// EVERY TRANSIT GOES OUT THROUGH THE QUIET SPOT, along the lane, never spot to spot.
// In the first watch the covering guard cannot see any of that lane at all, so the
// only cone boundary the walk crosses is the one it crosses head-on at the very end.
// ---------------------------------------------------------------------------

void AAlarmEscalationFunctionalTest::BeginPhase(int32 NewPhase, double Now)
{
	Phase = NewPhase;
	PhaseStartedAt = Now;
	HoldSince = -1.0;
	RawAtPhaseStart = RawSightings;
	Waypoints.Reset();
	WaypointIndex = 0;

	const FGuard* const Cover = CoveringGuard();
	const double SlowLap = Cover ? LapSecondsFor(*Cover, 0) : 20.0;
	const double CoolS = double(Dials.Cap) * Dials.QuietStep;

	switch (Phase)
	{
	case 1:  PhaseDeadline = Now + 20.0; break;                        // settle, quiet
	case 2:  Waypoints.Add(LaneOverSeen); Waypoints.Add(SpotSeen); break;
	case 3:  PhaseDeadline = Now + double(Dials.Cap) * SlowLap * 1.8 + 25.0; break;
	case 4:  Waypoints.Add(LaneOverSeen); Waypoints.Add(SpotQuiet); break;
	case 5:  PhaseDeadline = Now + CoolS * 1.8 + 30.0; break;          // leg-1 cooldown
	case 6:  Waypoints.Add(SpotSplit); break;
	case 7:  PhaseDeadline = Now + 44.0; break;                        // the split spot
	case 8:  Waypoints.Add(SpotQuiet); break;
	case 9:  PhaseDeadline = Now + 18.0; break;
	case 10: PhaseDeadline = Now + 18.0; break;                        // watch change
	case 11: PhaseDeadline = Now + 24.0; break;
	case 12: Waypoints.Add(SpotSplit); break;
	case 13: PhaseDeadline =
		Now + double(kRawSightingsForCapProof) * SlowLap * 1.8 + 30.0; break;
	case 14: Waypoints.Add(SpotQuiet); break;
	case 15: PhaseDeadline = Now + CoolS * 1.8 + 35.0; break;          // leg-2 cooldown
	case 16: PhaseDeadline = Now + 22.0; break;
	default: PhaseDeadline = Now + 20.0; break;
	}

	if (Waypoints.Num() > 0)
	{
		// A walking deadline derived from the MEASURED walk and the MEASURED hero
		// pace, never from a written number of seconds: 2.5x the ideal plus ten, which
		// covers the acceleration ramp and a settle at each waypoint.
		double Length = 0.0;
		FVector From = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
		for (const FVector& P : Waypoints)
		{
			Length += FVector::Dist2D(From, P);
			From = P;
		}
		PhaseDeadline = Now + Length / HeroSpeed * 2.5 + 10.0;
	}
}

void AAlarmEscalationFunctionalTest::DriveHero(double Now)
{
	if (!Hero.IsValid() || !Waypoints.IsValidIndex(WaypointIndex))
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Waypoints[WaypointIndex];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointUu)
	{
		++WaypointIndex;
		return;
	}
	Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
}

void AAlarmEscalationFunctionalTest::AdvancePhases(double Now)
{
	const bool bAtEndOfWalk = Waypoints.Num() > 0 && WaypointIndex >= Waypoints.Num();
	const double Elapsed = Now - PhaseStartedAt;
	bool bDone = false;

	auto Held = [this, Now](bool bCondition, double Seconds) -> bool
	{
		if (!bCondition) { HoldSince = -1.0; return false; }
		if (HoldSince < 0.0) { HoldSince = Now; }
		return (Now - HoldSince) >= Seconds;
	};

	switch (Phase)
	{
	case 0:  bDone = bAtEndOfWalk; break;
	case 1:  bDone = Elapsed >= 8.0; break;
	case 2:  bDone = bAtEndOfWalk; break;
	case 3:  // LEAVE PROMPTLY once the cap is reached. Standing longer would let an
		// UNCLAMPED counter climb past the cap here, and then the leg-1 cooldown -
		// which the step-down and deadband gates own - would name the failure that
		// the cap gate in leg 2 exists to name. Measured against the covering
		// guard's hunting lap, which is more than three times this hold.
		bDone = Held(Sightings >= Dials.Cap, 1.5); break;
	case 4:  bDone = bAtEndOfWalk; break;
	case 5:  bDone = Held(Sightings <= 0 && Stage == 0, 8.0); break;
	case 6:  bDone = bAtEndOfWalk; break;
	case 7:  bDone = Elapsed >= 32.0; break;
	case 8:  bDone = bAtEndOfWalk; break;
	case 9:  bDone = Elapsed >= 6.0; break;
	case 10: bDone = Elapsed >= 4.0; break;
	case 11: bDone = Elapsed >= 10.0; break;
	case 12: bDone = bAtEndOfWalk; break;
	case 13: bDone = Held(RawSightings - RawAtPhaseStart >= kRawSightingsForCapProof
			&& Sightings >= Dials.Cap, 4.0); break;
	case 14: bDone = bAtEndOfWalk; break;
	case 15: bDone = Held(Sightings <= 0 && Stage == 0, 10.0); break;
	case 16: bDone = Elapsed >= 8.0; break;
	default: bDone = true; break;
	}

	if (!bDone)
	{
		if (Now > PhaseDeadline)
		{
			// A PHASE THAT OVERRAN. Before this is written off as a staging fault, the
			// two gates a submission could STALL the drive with are re-checked
			// unconditionally: the pace it writes decides how often a cone sweeps
			// anybody, so a mis-paced yard must never launder a FAIL into an
			// uncredited harness exit.
			if (!GateSpeeds(Now) || !GateNotRewired(Now))
			{
				return;
			}
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: phase %d of the drive ran past its derived "
					 "deadline (%.0fs) with the model at setting %d and %d sighting(s), "
					 "and the guards' paces and numbers are exactly as staged; the yard "
					 "cannot finish the drive, which is ours and not the submission's"),
				Phase, PhaseDeadline - PhaseStartedAt, Stage, Sightings));
		}
		return;
	}

	if (Phase == 13)
	{
		// Remember what the over-exposure delivered, for the cap gate's message.
		RawInOverexposure = RawSightings - RawAtPhaseStart;
	}
	if (Phase == 9)
	{
		BeginPhase(10, Now);
		StageLeg(1);
		if (!IsRunning()) { return; }
		ValidateGeometry();
		return;
	}
	if (Phase >= 16)
	{
		bDriveComplete = true;
		return;
	}
	BeginPhase(Phase + 1, Now);
}

// ---------------------------------------------------------------------------
// The gates.
//
// PRECEDENCE, in the order Tick evaluates them. At most ONE windowed gate is armed on
// any frame, so the named FAIL is never a race between two of them:
//
//   1  TheYardIsNotYoursToRewire     every frame, from the first
//   2  EachGuardSeesWithItsOwnEyes   phases 7 and 13 (the split spot, both watches)
//   3  TheAlarmStopsCountingAtTheCap phases 14-15 (the whole second-watch cooldown,
//                                    from the walk out of the yard onwards)
//   4  TheYardRemembersWhichWayItCame  whenever the count is strictly inside a
//                                      deadband and 2/3 are not armed
//   5  TheAlarmComesDownOneStepAtATime phases 4-5 (the first-watch cooldown, from the
//                                      walk out onwards), outside the deadbands
//   6  TheYardShowsTheRightStage     everywhere else -- exactly one of 2..6 runs
//   7  TheGuardsSpeedUpWithTheAlarm  every judged frame, ALWAYS LAST, and only once
//                                    whichever of 2..6 was armed has already agreed
//   8  TheAlarmRoseAgainOnTheNewWatch  once, when the drive completes or at the
//                                      sentinel, whichever comes first
//
// TheYardShowsTheRightStage is deliberately SUPPRESSED inside every windowed gate's
// window: it asserts the same fact from a different angle and would otherwise shadow
// every named message. The PACE gate is a genuinely separate channel, so suppressing
// it would leave the raised hunting scale on the second watch ungraded -- every frame
// the yard is hunting there falls inside another gate's window. Running it LAST, and
// only on a frame where the lamps have already been agreed, gets both: a wrong setting
// is always named by the windowed gate, and a right setting with a wrong pace is
// always named by this one.
// ---------------------------------------------------------------------------

namespace
{
	const TCHAR* StageName(int32 S)
	{
		return (S >= 2) ? TEXT("hunting") : (S == 1 ? TEXT("watching") : TEXT("calm"));
	}
}

bool AAlarmEscalationFunctionalTest::Suppressed(double Now) const
{
	if (Now < StagingUntil)
	{
		return true;   // the fixture itself moved something
	}
	if (Now - LastModelChangeAt < kSuppressAfterS)
	{
		return true;   // 1.5x the half-second the prompt promises
	}
	// The next forget tick is exactly predictable, so a submission that steps DOWN a
	// frame early is covered as well as one that lags.
	if (!bSeenLastFrame && Sightings > 0
		&& (Dials.QuietStep - QuietFor) < kSuppressBeforeForgetS)
	{
		return true;
	}
	return Hero.IsValid() && AnyVerdictMarginal(Hero->GetActorLocation());
}

bool AAlarmEscalationFunctionalTest::ShownStageMatches(int32 Expect) const
{
	for (const FLamp& L : Lamps)
	{
		if (ReadLit(L.Actor.Get()) != (L.LitFromStage <= Expect))
		{
			return false;
		}
	}
	return true;
}

FString AAlarmEscalationFunctionalTest::LitSetDescription(int32 InStage) const
{
	FString S;
	for (const FLamp& L : Lamps)
	{
		if (L.LitFromStage <= InStage)
		{
			S += FString::Printf(TEXT("%s%s(burns from %d)"),
				S.IsEmpty() ? TEXT("") : TEXT(", "), *L.Label, L.LitFromStage);
		}
	}
	return S.IsEmpty() ? FString(TEXT("none")) : S;
}

FString AAlarmEscalationFunctionalTest::ActualLitDescription() const
{
	FString S;
	for (const FLamp& L : Lamps)
	{
		if (ReadLit(L.Actor.Get()))
		{
			S += FString::Printf(TEXT("%s%s(burns from %d)"),
				S.IsEmpty() ? TEXT("") : TEXT(", "), *L.Label, L.LitFromStage);
		}
	}
	return S.IsEmpty() ? FString(TEXT("none")) : S;
}

bool AAlarmEscalationFunctionalTest::GateNotRewired(double Now)
{
	(void)Now;
	auto SameF = [](double A, double B) { return FMath::Abs(A - B) <= FMath::Abs(B) * 0.001 + 0.001; };

	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		const FGuard& G = Guards[i];
		AActor* const A = G.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a guard stopped existing mid-run"));
			return false;
		}
		if (!SameF(G.Reach, G.StagedReach) || !SameF(G.HalfAngleDeg, G.StagedHalfAngleDeg)
			|| !SameF(G.BaseSpeed, G.StagedBaseSpeed) || G.RoundTag != G.StagedRoundTag)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: a guard's own numbers were changed. "
					 "The yard set guard %d to reach %.0f uu, %.1f deg of view, a base "
					 "pace of %.0f uu/s on round '%s'; it now reads %.0f / %.1f / %.0f "
					 "/ '%s'. The pace you are meant to write is PatrolSpeedUuPerSec"),
				i + 1, G.StagedReach, G.StagedHalfAngleDeg, G.StagedBaseSpeed,
				*G.StagedRoundTag.ToString(), G.Reach, G.HalfAngleDeg, G.BaseSpeed,
				*G.RoundTag.ToString()));
			return false;
		}
		// ON ITS OWN ROUND. Guards legitimately move, so this is a comparison against
		// the SEGMENT rather than against a point -- but parking one on top of the
		// character, or anywhere else, is still moving a guard, and the brief forbids
		// it. Without this the fixture's own model would agree with a parked guard
		// that the yard should be at hunting, and the whole run would grade nothing.
		const FVector Flat(A->GetActorLocation().X, A->GetActorLocation().Y, WalkZ);
		const double Off = FMath::PointDistToSegment(Flat, G.RoundA, G.RoundB);
		if (Off > kGuardOnRoundUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: a guard was moved off its own round. "
					 "Guard %d is %.0f uu away from the line between its two posts, "
					 "and the yard allows %.0f. Where the guards walk is not yours to "
					 "change"), i + 1, Off, kGuardOnRoundUu));
			return false;
		}
	}

	for (const FLamp& L : Lamps)
	{
		if (L.LitFromStage != L.StagedLitFromStage
			|| !SameF(L.ReachBonusUu, L.StagedReachBonusUu)
			|| L.CoversRoundTag != L.StagedCoversRoundTag)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: a floodlight's own numbers were "
					 "changed. The yard set %s to burn from setting %d and add %.0f uu "
					 "over '%s'; it now reads %d / %.0f / '%s'. The switch is yours to "
					 "throw, the numbers on it are not"),
				*L.Label, L.StagedLitFromStage, L.StagedReachBonusUu,
				*L.StagedCoversRoundTag.ToString(), L.LitFromStage, L.ReachBonusUu,
				*L.CoversRoundTag.ToString()));
			return false;
		}
	}

	if (Dials.RaiseWatch != StagedDials.RaiseWatch
		|| Dials.RaiseHunt != StagedDials.RaiseHunt
		|| Dials.DropWatch != StagedDials.DropWatch
		|| Dials.DropCalm != StagedDials.DropCalm
		|| Dials.Cap != StagedDials.Cap
		|| !SameF(Dials.QuietStep, StagedDials.QuietStep)
		|| !SameF(Dials.ScaleCalm, StagedDials.ScaleCalm)
		|| !SameF(Dials.ScaleWatching, StagedDials.ScaleWatching)
		|| !SameF(Dials.ScaleHunting, StagedDials.ScaleHunting))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardIsNotYoursToRewire: a dial on the panel was changed. The yard "
				 "set raise %d/%d, drop %d/%d, cap %d, quiet %.1f s, scales "
				 "%.2f/%.2f/%.2f; the panel now reads raise %d/%d, drop %d/%d, cap %d, "
				 "quiet %.1f s, scales %.2f/%.2f/%.2f. Only the sergeant re-sets a "
				 "dial"),
			StagedDials.RaiseWatch, StagedDials.RaiseHunt, StagedDials.DropWatch,
			StagedDials.DropCalm, StagedDials.Cap, StagedDials.QuietStep,
			StagedDials.ScaleCalm, StagedDials.ScaleWatching, StagedDials.ScaleHunting,
			Dials.RaiseWatch, Dials.RaiseHunt, Dials.DropWatch, Dials.DropCalm,
			Dials.Cap, Dials.QuietStep, Dials.ScaleCalm, Dials.ScaleWatching,
			Dials.ScaleHunting));
		return false;
	}

	for (int32 i = 0; i < Posts.Num(); ++i)
	{
		const AActor* const P = Posts[i].Get();
		if (P == nullptr || !P->GetActorLocation().Equals(StagedPostAt[i], kPostMoveUu))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: a post that marks a round was moved. "
					 "The yard put post %d at %s and it is now at %s"),
				i + 1, *StagedPostAt[i].ToCompactString(),
				*(P ? P->GetActorLocation() : FVector::ZeroVector).ToCompactString()));
			return false;
		}
	}
	return true;
}

bool AAlarmEscalationFunctionalTest::GateSpeeds(double Now)
{
	(void)Now;
	const double Scale = ScaleFor(Stage);
	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		const FGuard& G = Guards[i];
		bool bOk = false;
		const double Actual = ReadFloat(G.Actor.Get(), TEXT("PatrolSpeedUuPerSec"), bOk);
		if (!bOk)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a guard no longer exposes "
					 "PatrolSpeedUuPerSec readably"));
			return false;
		}
		const double Want = double(G.StagedBaseSpeed) * Scale;
		if (FMath::Abs(Actual - Want) > FMath::Max(Want * kSpeedTolFrac, 1.0))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheGuardsSpeedUpWithTheAlarm: a guard is walking at the wrong "
					 "pace for the setting the yard is at. Guard %d has its own base "
					 "pace of %.0f uu/s and the panel currently multiplies by %.2f at "
					 "%s, so it should be walking at %.0f uu/s; it is walking at %.0f. "
					 "The two guards' base paces are not the same number"),
				i + 1, G.StagedBaseSpeed, Scale, StageName(Stage), Want, Actual));
			return false;
		}
	}
	return true;
}

bool AAlarmEscalationFunctionalTest::GateStageShown(double Now)
{
	(void)Now;
	if (ShownStageMatches(Stage))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheYardShowsTheRightStage: the floodlights are not showing the setting "
			 "the yard is at. The panel is %s with %d sighting(s) remembered, so "
			 "exactly the floodlights that burn from that setting or lower should be "
			 "lit. Should be burning: %s. Actually burning: %s"),
		StageName(Stage), Sightings, *LitSetDescription(Stage),
		*ActualLitDescription()));
	return false;
}

bool AAlarmEscalationFunctionalTest::GateOwnEyes(double Now)
{
	(void)Now;
	if (ShownStageMatches(Stage))
	{
		return true;
	}
	const FGuard* const Cover = CoveringGuard();
	const FGuard* const Far = FarGuard();
	if (Cover == nullptr || Far == nullptr)
	{
		return true;
	}
	const double CoverLimit = ReachOnRound(*Cover, Stage, WatchedRoundTag)
		* FMath::Sin(FMath::DegreesToRadians(Cover->HalfAngleDeg));
	const double FarLimit = ReachOnRound(*Far, Stage, WatchedRoundTag)
		* FMath::Sin(FMath::DegreesToRadians(Far->HalfAngleDeg));
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("EachGuardSeesWithItsOwnEyes: the yard is answering to the wrong pair of "
			 "eyes. The character is standing %.0f uu off the round, and the guard "
			 "walking it reaches %.0f uu through a %.1f deg view, which holds somebody "
			 "out to %.0f uu at most; the guard on the other round reaches %.0f uu "
			 "through %.1f deg, which would hold them out to %.0f uu. On this watch "
			 "the panel should be %s with %d sighting(s). Should be burning: %s. "
			 "Actually burning: %s"),
		OffsetSplit, Cover->Reach, Cover->HalfAngleDeg, CoverLimit,
		Far->Reach, Far->HalfAngleDeg, FarLimit, StageName(Stage), Sightings,
		*LitSetDescription(Stage), *ActualLitDescription()));
	return false;
}

bool AAlarmEscalationFunctionalTest::GateHysteresis(double Now)
{
	(void)Now;
	if (ShownStageMatches(Stage))
	{
		return true;
	}
	const bool bHuntBand = (Sightings > Dials.DropWatch && Sightings < Dials.RaiseHunt);
	const int32 Drop = bHuntBand ? Dials.DropWatch : Dials.DropCalm;
	const int32 Raise = bHuntBand ? Dials.RaiseHunt : Dials.RaiseWatch;
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheYardRemembersWhichWayItCame: the setting is not a function of the "
			 "count, and this count is inside the band where the panel does not move "
			 "at all. It reads %d sighting(s), between the drop number %d and the "
			 "raise number %d, and it got here on the way %s, so the panel should "
			 "still be %s. Should be burning: %s. Actually burning: %s"),
		Sightings, Drop, Raise, bCountRising ? TEXT("up") : TEXT("down"),
		StageName(Stage), *LitSetDescription(Stage), *ActualLitDescription()));
	return false;
}

bool AAlarmEscalationFunctionalTest::GateStepDown(double Now)
{
	if (ShownStageMatches(Stage))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheAlarmComesDownOneStepAtATime: the yard came down faster or slower "
			 "than the panel says. It forgets ONE sighting per quiet window, then "
			 "another, and the setting follows the count. After %.1f s of unbroken "
			 "quiet at %.1f s per step the count is %d, so the panel should be %s. "
			 "Should be burning: %s. Actually burning: %s"),
		Now - PhaseStartedAt, Dials.QuietStep, Sightings, StageName(Stage),
		*LitSetDescription(Stage), *ActualLitDescription()));
	return false;
}

bool AAlarmEscalationFunctionalTest::GateCap(double Now)
{
	if (ShownStageMatches(Stage))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheAlarmStopsCountingAtTheCap: the yard remembered more sightings than "
			 "its dial allows. It was stood in front of until it had been sighted %d "
			 "times on this watch while the panel only ever remembers %d, so after "
			 "%.1f s of quiet at %.1f s per step the count is %d and the panel should "
			 "be %s. Should be burning: %s. Actually burning: %s"),
		RawInOverexposure, Dials.Cap, Now - PhaseStartedAt, Dials.QuietStep, Sightings,
		StageName(Stage), *LitSetDescription(Stage), *ActualLitDescription()));
	return false;
}

// ---------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------

void AAlarmEscalationFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !bPrepared || !Hero.IsValid() || Guards.Num() != 2)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	// EVERY NUMBER, EVERY FRAME. Two of them change part way through the night.
	ReReadGuardNumbers();
	for (FLamp& L : Lamps)
	{
		AActor* const A = L.Actor.Get();
		bool bOk = false;
		L.LitFromStage = ReadInt(A, TEXT("LitFromStage"), bOk);
		L.ReachBonusUu = ReadFloat(A, TEXT("ReachBonusUu"), bOk);
		L.CoversRoundTag = ReadName(A, TEXT("CoversRoundTag"), bOk);
	}

	StepModel(double(DeltaSeconds));

	if (!GateNotRewired(Now))
	{
		return;
	}

	// Phase 0 is the walk from wherever the character spawned to the quiet spot;
	// nothing is judged until it is standing somewhere the fixture chose.
	if (Phase >= 1 && !Suppressed(Now))
	{
		bool bOk = true;
		const bool bHuntBand = (Sightings > Dials.DropWatch && Sightings < Dials.RaiseHunt);
		const bool bWatchBand = (Sightings > Dials.DropCalm && Sightings < Dials.RaiseWatch);
		if (Phase == 7 || Phase == 13)
		{
			bOk = GateOwnEyes(Now);
		}
		else if (Phase == 14 || Phase == 15)
		{
			bOk = GateCap(Now);
		}
		else if (bHuntBand || bWatchBand)
		{
			bOk = GateHysteresis(Now);
		}
		else if (Phase == 4 || Phase == 5)
		{
			bOk = GateStepDown(Now);
		}
		else
		{
			bOk = GateStageShown(Now);
		}
		// THE PACE IS A SEPARATE CHANNEL, so it is judged on every frame the others
		// are -- but ALWAYS LAST, and only once the setting the yard is showing has
		// already been agreed. A wrong setting makes both this and the windowed gate
		// above true at once; running this second means the windowed gate always owns
		// that failure, and this one can only ever fire when the lamps are right and
		// the pace is not. Without it the raised hunting scale on the second watch
		// would go ungraded, because every frame the yard is hunting there falls
		// inside another gate's window.
		if (bOk)
		{
			bOk = GateSpeeds(Now);
		}
		if (!bOk)
		{
			return;
		}
	}

	DriveHero(Now);
	AdvancePhases(Now);

	if (bDriveComplete && IsRunning())
	{
		if (RisesInLeg[0] < 1 || RisesInLeg[1] < 1 || !bReachedCalmAfterFirstRise)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheAlarmRoseAgainOnTheNewWatch: the yard has to be able to do the "
					 "whole thing again. It rose from calm %d time(s) on the first "
					 "watch and %d time(s) on the second, and it %s come all the way "
					 "back to calm in between. A yard that latches at its highest "
					 "setting, or a quiet clock that is only ever armed once, can only "
					 "manage this the first time"),
				RisesInLeg[0], RisesInLeg[1],
				bReachedCalmAfterFirstRise ? TEXT("did") : TEXT("never did")));
			return;
		}
		// AND THE DISCRIMINATING SITUATION HAS TO HAVE HAPPENED. Everything above is
		// about the submission; this is about the run. The whole defence against the
		// named wrong answer -- one threshold ladder for both directions -- is
		// TheYardRemembersWhichWayItCame arming while the count stands strictly inside
		// a deadband, so a run that never produced such a count proves nothing about
		// hysteresis whatever else it agreed on. That is a fault in the yard's dials
		// or in the drive, never in the submission, so it ends the run as ours.
		if (!bWasInWatchBand || !bWasInHuntBand)
		{
			const TCHAR* BandName = TEXT("hunting");
			if (!bWasInWatchBand)
			{
				BandName = bWasInHuntBand
					? TEXT("watching") : TEXT("watching or the hunting");
			}
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive finished without the count ever "
					 "standing strictly inside the %s deadband (drop/raise %d/%d for "
					 "watching and %d/%d for hunting, cap %d), so "
					 "TheYardRemembersWhichWayItCame was never armed and a plain "
					 "threshold ladder would have graded exactly like a remembered "
					 "setting; the yard's dials and the drive do not produce the "
					 "situation this task exists to measure"),
				BandName, Dials.DropCalm, Dials.RaiseWatch, Dials.DropWatch,
				Dials.RaiseHunt, Dials.Cap));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
			TEXT("Both watches ran: %d rise(s) then %d, %d raw sightings, cap %d; the "
				 "count stood inside both deadbands."),
			RisesInLeg[0], RisesInLeg[1], RawSightings, Dials.Cap));
	}
}

void AAlarmEscalationFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	FString GuardBits;
	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		double Ang = 0.0, Dist = 0.0, Reach = 0.0;
		const bool bSees = CanSee(Guards[i], H, StageForReach, Ang, Dist, Reach);
		bool bOk = false;
		const double Pace = ReadFloat(Guards[i].Actor.Get(),
			TEXT("PatrolSpeedUuPerSec"), bOk);
		GuardBits += FString::Printf(TEXT("g%d['%s' d%.0f/%.0f a%.1f/%.1f see%d "
			"pace%.0f] "), i + 1, *Guards[i].RoundTag.ToString(), Dist, Reach, Ang,
			Guards[i].HalfAngleDeg, bSees ? 1 : 0, Pace);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-alarm calib] cp%d t=%.2f leg=%d phase=%d at=(%.0f,%.0f) model=%s "
			 "n=%d raw=%d quiet=%.1f lit=[%s] want=[%s] %s"),
		Index, Now, Leg + 1, Phase, H.X, H.Y, StageName(Stage), Sightings,
		RawSightings, QuietFor, *ActualLitDescription(), *LitSetDescription(Stage),
		*GuardBits);
}

void AAlarmEscalationFunctionalTest::OnCheckpoint(int32 CheckpointIndex,
	double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kGradedCheckpoints)
	{
		return;
	}
	// THE SENTINEL. The base class ends the test the moment the last scheduled
	// checkpoint is sampled, so the run-level gate is evaluated here as well as when
	// the drive completes -- whichever comes first.
	if (bDriveComplete)
	{
		return;
	}
	// The drive did not finish. Before that is written off as a staging fault, the two
	// gates a submission could stall the drive with are re-checked unconditionally.
	if (!GateSpeeds(TimeSeconds) || !GateNotRewired(TimeSeconds))
	{
		return;
	}
	if (RisesInLeg[0] < 1 || RisesInLeg[1] < 1 || !bReachedCalmAfterFirstRise)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheAlarmRoseAgainOnTheNewWatch: the yard has to be able to do the "
				 "whole thing again. It rose from calm %d time(s) on the first watch "
				 "and %d time(s) on the second, and it %s come all the way back to "
				 "calm in between; the drive was still at phase %d when the run ran "
				 "out of time"),
			RisesInLeg[0], RisesInLeg[1],
			bReachedCalmAfterFirstRise ? TEXT("did") : TEXT("never did"), Phase));
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the drive was still at phase %d at the sentinel "
			 "with every continuous gate green and the guards paced exactly as the "
			 "panel dictates; the yard is staged so the drive cannot finish, which is "
			 "ours and not the submission's"), Phase));
}
