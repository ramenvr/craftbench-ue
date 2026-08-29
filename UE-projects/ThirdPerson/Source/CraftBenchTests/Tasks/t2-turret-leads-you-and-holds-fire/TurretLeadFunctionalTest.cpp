// Copyright CraftBench. All Rights Reserved.

#include "TurretLeadFunctionalTest.h"

#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED IN THE PROMPT ------------------------------------------------
	constexpr double kHitToleranceUu = 120.0;   // "within 120 cm of the middle"

	// ---- FORGIVING BANDS. Every one of these can only ever EXCUSE a submission ---
	// Range. The prompt says "inside that turret's own engagement distance" without
	// saying whether that is measured from the turret or from the muzzle, and the
	// muzzle sits up to 230 uu out along the bore. 1.25x covers that ambiguity on the
	// SHORTEST reach in the yard (1500) with room over.
	constexpr double kRangeBandX = 1.25;
	// No-interception. The exact condition for the quadratic having no positive root
	// is [across-sight > s] OR [|V| > s AND opening]; these are strict subsets of it.
	constexpr double kNoSolveAcrossX = 1.25;
	constexpr double kNoSolveSpeedX = 1.25;
	constexpr double kNoSolveOpenX = 0.25;
	// The mirror margin on the other side: the yard only DEMANDS a shot where the
	// solution is comfortable, so a submission is never charged with silence for
	// declining an absurd shot.
	constexpr double kWindowAcrossX = 0.8;
	constexpr double kWindowMaxFlightS = 8.0;

	// ---- MEASUREMENT ------------------------------------------------------------
	constexpr double kMovingFloorUu = 200.0;    // below this the character is "stopped"
	constexpr double kSteadyS = 1.0;            // straight-line settle before grading
	constexpr double kSteadySpeedFrac = 0.05;
	constexpr double kSteadyDirDeg = 3.0;
	// The shot must land while the character is still walking the straight leg. The
	// drive stops applying input 70 uu short of a waypoint, i.e. 0.27 s before nominal
	// arrival at 260 uu/s, so 0.8 s of margin keeps every graded impact inside the
	// constant-velocity stretch the intercept solve assumed. Narrowing gradeability
	// can only ever forgive.
	constexpr double kFlightMarginS = 0.8;
	constexpr double kJudgeAfterS = 1.5;        // settle before reading closest approach
	constexpr double kMuzzleWindowUu = 150.0;   // a shot appears at a muzzle
	constexpr double kBarrelConeDeg = 6.0;      // launch dir vs barrel forward
	constexpr double kStraightFrac = 0.03;      // path vs analytic, fraction of speed
	constexpr double kStraightMinUu = 25.0;
	constexpr double kSlewSlackX = 3.0;         // frames of legal slew between samples
	constexpr double kSlewSlackDeg = 1.5;
	constexpr double kBoltedRotDeg = 0.5;
	constexpr double kBoltedLocUu = 2.0;
	constexpr double kReloadForgive = 0.85;
	constexpr double kRetuneBlurS = 0.5;        // shots too near a re-tune to speed-check
	constexpr int32 kMaxLiveShots = 400;

	// ---- DRIVE ------------------------------------------------------------------
	constexpr double kDwellS = 5.0;
	constexpr double kArriveUu = 70.0;
	constexpr double kRetuneAfterDwellS = 1.5;
	constexpr double kDrainS = 6.0;             // let the last shots land before totals
	constexpr double kSentinelS = 300.0;
	constexpr int32 kSentinelIndex = 22;

	// ---- FAIRNESS PRECONDITIONS -------------------------------------------------
	constexpr double kMinStandoffUu = 400.0;    // never crowd a solid turret base
	constexpr double kBoundaryFrac = 0.08;      // no stop this near a reach boundary
	constexpr double kBearingFrac = 0.6;        // barrel must out-slew the aim point
	constexpr double kWindowReloadX = 3.3;      // a demanded window is this many reloads
	constexpr double kMinGradeablePerTurretS = 2.0;
	constexpr double kMinNoSolutionS = 2.5;
	constexpr double kMinSpeedSpreadUu = 500.0;
	constexpr double kMinReachSpreadUu = 1000.0;

	// The three sets of four numbers, and which turret wears which in each phase.
	// The map's authored values match PHASE 1 on purpose: a submission that reads the
	// numbers once in BeginPlay is exactly right until the first re-tune.
	struct FSetLiteral { const TCHAR* Name; double S, R, T, L; };
	const FSetLiteral kSetL = { TEXT("SET-L"), 460.0, 4200.0, 40.0, 1.5 };
	const FSetLiteral kSetS = { TEXT("SET-S"), 1350.0, 1500.0, 130.0, 0.9 };
	const FSetLiteral kSetM = { TEXT("SET-M"), 750.0, 2600.0, 70.0, 1.2 };

	// Route shape. Every factor multiplies the REACH of the set that owns the leg, so
	// the route re-derives itself around each re-tune and nothing is a bare constant.
	constexpr double kLaneA_Along = 0.62;   // x SET-L reach
	constexpr double kLaneA_Side = 0.52;
	constexpr double kLaneB_Along = 2.00;   // x SET-S reach
	constexpr double kLaneB_Side = 0.55;
	constexpr double kRadialIn = 0.18;      // x SET-L reach
	constexpr double kRadialOut = 0.90;
	constexpr double kChargeOffset = 0.030; // x SET-L reach
	constexpr double kChargeStop = 0.20;
	constexpr double kLaneE_Along = 0.68;   // x SET-M reach
	constexpr double kLaneE_Side = 0.55;

	// Walking, sprinting away, charging. The charge is deliberately FASTER than the
	// long gun's shot (520 vs 460) and slower than the yard's own no-solution margin
	// (575), so "the target is faster than my shot, hold" is wrong there and provably
	// so; the run-away leg at 620 is past that margin and is genuinely unsolvable.
	const double kLegSpeed[9] = { 260.0, 260.0, 260.0, 260.0, 620.0, 620.0, 520.0,
		260.0, 260.0 };

	FVector2D RotateXY(const FVector2D& V, double Radians)
	{
		const double C = FMath::Cos(Radians);
		const double S = FMath::Sin(Radians);
		return FVector2D(V.X * C - V.Y * S, V.X * S + V.Y * C);
	}
}

ATurretLeadFunctionalTest::ATurretLeadFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// =================================================================================
// Reflection: the four numbers, read and written by NAME so the fixture never
// depends on the agent's class layout, and by FNumericProperty so a float -> double
// refactor is still readable rather than silently invisible.
// =================================================================================

bool ATurretLeadFunctionalTest::ReadNumber(const AActor* A, const TCHAR* PropName,
	double& Out) const
{
	if (A == nullptr)
	{
		return false;
	}
	FNumericProperty* const P =
		FindFProperty<FNumericProperty>(A->GetClass(), PropName);
	if (P == nullptr || !P->IsFloatingPoint())
	{
		return false;
	}
	UObject* const Obj = const_cast<AActor*>(A);
	Out = P->GetFloatingPointPropertyValue(P->ContainerPtrToValuePtr<void>(Obj));
	return true;
}

bool ATurretLeadFunctionalTest::WriteNumber(AActor* A, const TCHAR* PropName,
	double Value)
{
	if (A == nullptr)
	{
		return false;
	}
	FNumericProperty* const P =
		FindFProperty<FNumericProperty>(A->GetClass(), PropName);
	if (P == nullptr || !P->IsFloatingPoint())
	{
		return false;
	}
	UObject* const Obj = A;
	P->SetFloatingPointPropertyValue(P->ContainerPtrToValuePtr<void>(Obj), Value);
	return true;
}

bool ATurretLeadFunctionalTest::RefreshLiveNumbers()
{
	static const TCHAR* const kNames[4] = { TEXT("ShotSpeedUu"), TEXT("EngageRangeUu"),
		TEXT("TraverseDegPerSec"), TEXT("ReloadSeconds") };
	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		FTurret& T = Turrets[i];
		AActor* const A = T.Actor.Get();
		double V[4] = { 0.0, 0.0, 0.0, 0.0 };
		for (int32 k = 0; k < 4; ++k)
		{
			if (A == nullptr || !ReadNumber(A, kNames[k], V[k]))
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheTurretsKeptTheirFourNumbers: turret %d no longer carries "
						 "a readable number called %s. The four numbers on a turret "
						 "are what the yard re-tunes and what a solution has to read; "
						 "renaming, retyping or removing one is not a solution"),
					i + 1, kNames[k]));
				return false;
			}
		}
		T.Speed = V[0];
		T.Reach = V[1];
		T.Traverse = V[2];
		T.Reload = V[3];
		T.MinReloadSince = FMath::Min(T.MinReloadSince, T.Reload);
	}
	return true;
}

// =================================================================================
// Geometry. The fixture's OWN answer, from the same quantities a submission has.
// =================================================================================

bool ATurretLeadFunctionalTest::SolveIntercept(const FVector& D, const FVector& V,
	double ShotSpeed, double& OutFlightSeconds)
{
	const double A = V.SizeSquared() - ShotSpeed * ShotSpeed;
	const double B = 2.0 * FVector::DotProduct(D, V);
	const double C = D.SizeSquared();
	if (C <= UE_KINDA_SMALL_NUMBER)
	{
		OutFlightSeconds = 0.0;
		return true;
	}
	if (ShotSpeed <= UE_KINDA_SMALL_NUMBER)
	{
		return false;
	}
	if (FMath::Abs(A) < 1.0e-4)
	{
		if (FMath::Abs(B) < 1.0e-6)
		{
			return false;
		}
		const double T = -C / B;
		if (T <= 1.0e-4)
		{
			return false;
		}
		OutFlightSeconds = T;
		return true;
	}
	const double Disc = B * B - 4.0 * A * C;
	if (Disc < 0.0)
	{
		return false;
	}
	const double Root = FMath::Sqrt(Disc);
	const double Lo = FMath::Min((-B - Root) / (2.0 * A), (-B + Root) / (2.0 * A));
	const double Hi = FMath::Max((-B - Root) / (2.0 * A), (-B + Root) / (2.0 * A));
	if (Lo > 1.0e-4)
	{
		OutFlightSeconds = Lo;
		return true;
	}
	if (Hi > 1.0e-4)
	{
		OutFlightSeconds = Hi;
		return true;
	}
	return false;
}

void ATurretLeadFunctionalTest::SightSplit(const FVector& D, const FVector& V,
	double& OutAcross, double& OutAlong)
{
	const double Len = D.Size();
	if (Len <= UE_KINDA_SMALL_NUMBER)
	{
		OutAcross = V.Size();
		OutAlong = 0.0;
		return;
	}
	const FVector Dh = D / Len;
	OutAlong = FVector::DotProduct(V, Dh);          // positive = opening the range
	OutAcross = (V - Dh * OutAlong).Size();
}

bool ATurretLeadFunctionalTest::WindowOpenFor(const FTurret& T, const FVector& HeroAt,
	const FVector& HeroVel, double& OutFlight)
{
	if (HeroVel.Size() < kMovingFloorUu)
	{
		return false;   // standing still: no duty, so a dwell can never carry a window
	}
	if (FVector::Dist(HeroAt, T.StagedLoc) > T.Reach)
	{
		return false;
	}
	const FVector D = HeroAt - T.StagedBarrelLoc;
	double Across = 0.0;
	double Along = 0.0;
	SightSplit(D, HeroVel, Across, Along);
	if (Across > kWindowAcrossX * T.Speed)
	{
		return false;
	}
	if (!SolveIntercept(D, HeroVel, T.Speed, OutFlight))
	{
		return false;
	}
	return OutFlight <= kWindowMaxFlightS;
}

bool ATurretLeadFunctionalTest::OutOfReachFor(const FTurret& T, const FVector& HeroAt)
{
	return FVector::Dist(HeroAt, T.StagedLoc) > kRangeBandX * T.Reach;
}

bool ATurretLeadFunctionalTest::NoSolutionFor(const FTurret& T, const FVector& HeroAt,
	const FVector& HeroVel)
{
	const FVector D = HeroAt - T.StagedBarrelLoc;
	double Across = 0.0;
	double Along = 0.0;
	SightSplit(D, HeroVel, Across, Along);
	if (Across > kNoSolveAcrossX * T.Speed)
	{
		return true;
	}
	const double Sp = HeroVel.Size();
	return Sp > kNoSolveSpeedX * T.Speed && Along > kNoSolveOpenX * Sp;
}

int32 ATurretLeadFunctionalTest::ShotsRequired(double WindowSeconds, double Traverse,
	double Reload)
{
	// A turret may need to swing before it can shoot. A quarter-turn at its own rate
	// is taken off the front of every window before any duty is counted.
	const double Rem = WindowSeconds - 90.0 / FMath::Max(Traverse, 1.0);
	if (Rem >= 10.0)
	{
		return 3;
	}
	return Rem >= FMath::Max(2.5, 1.6 * Reload) ? 1 : 0;
}

// =================================================================================
// Staging
// =================================================================================

bool ATurretLeadFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LeadTurret")), Found);
	if (Found.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %d actor(s) tagged LeadTurret, expected 2"),
			Found.Num()));
		return false;
	}
	// A stable order: turret 1 is the one nearer the origin end of the yard, so
	// "turret 1" means the same gun in every message and after every re-tune.
	Found.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetActorLocation().X < R.GetActorLocation().X;
	});

	for (int32 i = 0; i < Found.Num(); ++i)
	{
		AActor* const A = Found[i];
		FTurret T;
		T.Actor = A;
		T.StagedLoc = A->GetActorLocation();
		T.StagedRot = A->GetActorQuat();

		auto FindTagged = [A](const TCHAR* Tag) -> USceneComponent*
		{
			const TArray<UActorComponent*> Comps =
				A->GetComponentsByTag(USceneComponent::StaticClass(), FName(Tag));
			return Comps.Num() > 0 ? Cast<USceneComponent>(Comps[0]) : nullptr;
		};
		T.Barrel = FindTagged(TEXT("TurretBarrel"));
		T.Muzzle = FindTagged(TEXT("TurretMuzzle"));
		T.BasePart = FindTagged(TEXT("TurretBase"));
		if (!T.Barrel.IsValid() || !T.Muzzle.IsValid() || !T.BasePart.IsValid())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheTurretsKeptTheirFourNumbers: turret %d no longer carries the "
					 "parts the yard identifies it by -- a base, a barrel and a "
					 "muzzle. Rename or subclass whatever you like, but the gun has "
					 "to still be a gun"), i + 1));
			return false;
		}
		T.StagedBarrelLoc = T.Barrel->GetComponentLocation();
		T.StagedBaseRot = T.BasePart->GetComponentQuat();
		Turrets.Add(T);
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr
		|| Hero->GetCharacterMovement() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in "
				 "the yard"));
		return false;
	}
	return true;
}

void ATurretLeadFunctionalTest::ApplyPhase(int32 PhaseIndex)
{
	const FSetLiteral* First = &kSetL;
	const FSetLiteral* Second = &kSetS;
	if (PhaseIndex == 1) { First = &kSetS; Second = &kSetL; }
	else if (PhaseIndex >= 2) { First = &kSetM; Second = &kSetS; }

	const FSetLiteral* const Sets[2] = { First, Second };
	for (int32 i = 0; i < Turrets.Num() && i < 2; ++i)
	{
		AActor* const A = Turrets[i].Actor.Get();
		WriteNumber(A, TEXT("ShotSpeedUu"), Sets[i]->S);
		WriteNumber(A, TEXT("EngageRangeUu"), Sets[i]->R);
		WriteNumber(A, TEXT("TraverseDegPerSec"), Sets[i]->T);
		WriteNumber(A, TEXT("ReloadSeconds"), Sets[i]->L);
	}
	Phase = PhaseIndex;
	UE_LOG(LogTemp, Display, TEXT("[t2-turret] phase %d staged: turret 1 = %s, "
		"turret 2 = %s"), PhaseIndex + 1, First->Name, Second->Name);
}

void ATurretLeadFunctionalTest::BuildRoute()
{
	Route.Reset();
	LegSpeed.Reset();
	if (Turrets.Num() < 2 || !Hero.IsValid())
	{
		return;
	}
	const double Z = Hero->GetActorLocation().Z;
	const FVector2D A(Turrets[0].StagedLoc.X, Turrets[0].StagedLoc.Y);
	const FVector2D B(Turrets[1].StagedLoc.X, Turrets[1].StagedLoc.Y);
	const FVector2D Along = (B - A).GetSafeNormal();
	const FVector2D Side(-Along.Y, Along.X);

	auto At = [Z](const FVector2D& P) { return FVector(P.X, P.Y, Z); };

	const double RL = kSetL.R;
	const double RS = kSetS.R;
	const double RM = kSetM.R;

	// PHASE 1 -- the long gun's crossing lane, then the short gun's crossing lane.
	const FVector2D W0 = A - Along * (kLaneA_Along * RL) - Side * (kLaneA_Side * RL);
	const FVector2D W1 = A + Along * (kLaneA_Along * RL) - Side * (kLaneA_Side * RL);
	const FVector2D W2 = B - Along * (kLaneB_Along * RS) - Side * (kLaneB_Side * RS);
	const FVector2D W3 = B + Along * (kLaneB_Along * RS) - Side * (kLaneB_Side * RS);

	// PHASE 2 -- in along turret 2's radial, out along it at a sprint, then a charge
	// back in on a chord that never quite reaches the closest-approach point.
	const FVector2D U = (W3 - B).GetSafeNormal();
	const FVector2D W4 = B + U * (kRadialIn * RL);
	const FVector2D W5 = B + U * (kRadialOut * RL);
	const double POff = kChargeOffset * RL;
	const double RStop = kChargeStop * RL;
	const double RStart = kRadialOut * RL;
	const double Delta = FMath::Acos(FMath::Clamp(POff / RStart, -1.0, 1.0))
		- FMath::Acos(FMath::Clamp(POff / RStop, -1.0, 1.0));
	const FVector2D CandA = B + RotateXY(U, Delta) * RStop;
	const FVector2D CandB = B + RotateXY(U, -Delta) * RStop;
	// The charge stays on the same side of the turret axis as the rest of the route.
	const FVector2D W6 = FVector2D::DotProduct(CandA - B, Side)
		<= FVector2D::DotProduct(CandB - B, Side) ? CandA : CandB;

	// PHASE 3 -- a third speed, a third lead angle, on the mid gun's crossing lane.
	const FVector2D W7 = A + Along * (kLaneE_Along * RM) - Side * (kLaneE_Side * RM);
	const FVector2D W8 = A - Along * (kLaneE_Along * RM) - Side * (kLaneE_Side * RM);

	const FVector2D Stops[9] = { W0, W1, W2, W3, W4, W5, W6, W7, W8 };
	for (int32 i = 0; i < 9; ++i)
	{
		Route.Add(At(Stops[i]));
		LegSpeed.Add(kLegSpeed[i]);
	}
}

bool ATurretLeadFunctionalTest::ValidatePlan()
{
	// Which parameter set each turret wears while walking to each waypoint.
	const FSetLiteral* const PhaseSets[3][2] = {
		{ &kSetL, &kSetS }, { &kSetS, &kSetL }, { &kSetM, &kSetS } };
	auto PhaseOfLeg = [](int32 WaypointIdx)
	{
		return WaypointIdx <= 3 ? 0 : (WaypointIdx <= 6 ? 1 : 2);
	};

	// (1) No constant fits both turrets, in any phase.
	for (int32 p = 0; p < 3; ++p)
	{
		const double DS = FMath::Abs(PhaseSets[p][0]->S - PhaseSets[p][1]->S);
		const double DR = FMath::Abs(PhaseSets[p][0]->R - PhaseSets[p][1]->R);
		if (DS < kMinSpeedSpreadUu || DR < kMinReachSpreadUu)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: in phase %d the two turrets' shot speeds "
					 "are %.0f uu/s apart and their reaches %.0f uu apart; one "
					 "constant would fit both and the task would measure less than "
					 "it claims"), p + 1, DS, DR));
			return false;
		}
	}

	// A throwaway turret carrying a phase's numbers, so the plan is checked with the
	// same predicates that will grade it.
	auto Staged = [&](int32 TurretIdx, int32 PhaseIdx)
	{
		FTurret T;
		T.StagedLoc = Turrets[TurretIdx].StagedLoc;
		T.StagedBarrelLoc = Turrets[TurretIdx].StagedBarrelLoc;
		T.Speed = PhaseSets[PhaseIdx][TurretIdx]->S;
		T.Reach = PhaseSets[PhaseIdx][TurretIdx]->R;
		T.Traverse = PhaseSets[PhaseIdx][TurretIdx]->T;
		T.Reload = PhaseSets[PhaseIdx][TurretIdx]->L;
		return T;
	};

	// (2) Every stop clear of both bases, and clear of both reach boundaries in the
	//     phase it is visited in.
	for (int32 i = 0; i < Route.Num(); ++i)
	{
		for (int32 t = 0; t < 2; ++t)
		{
			const double D = FVector::Dist2D(Route[i], Turrets[t].StagedLoc);
			if (D < kMinStandoffUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: stop %d is %.0f uu from turret %d, "
						 "which is solid; the character would be pushing it"),
					i, D, t + 1));
				return false;
			}
			// Both the phase walked IN on and the phase walked OUT on: a re-tune
			// happens standing at a stop, so that stop is judged under two sets of
			// numbers and has to be clear of the boundary under both.
			const int32 PhIn = PhaseOfLeg(i);
			const int32 PhOut = PhaseOfLeg(FMath::Min(i + 1, Route.Num() - 1));
			const int32 BothPhases[2] = { PhIn, PhOut };
			for (int32 pi = 0; pi < 2; ++pi)
			{
				const int32 Ph = BothPhases[pi];
				const double Frac = D / PhaseSets[Ph][t]->R;
				if (FMath::Abs(Frac - 1.0) < kBoundaryFrac)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: stop %d sits %.1f%% from turret "
							 "%d's engagement boundary in phase %d, so a correct "
							 "answer could round either way"),
						i, FMath::Abs(Frac - 1.0) * 100.0, t + 1, Ph + 1));
					return false;
				}
			}
		}
	}

	// (3) Walk every leg and check the things a submission is entitled to.
	constexpr int32 kSamples = 240;
	double GradeableFor[2] = { 0.0, 0.0 };
	int32 DemandedWindows[2] = { 0, 0 };
	double LongestNoSolution = 0.0;
	double LongestOutOfReach = 0.0;

	for (int32 i = 1; i < Route.Num(); ++i)
	{
		const int32 Ph = PhaseOfLeg(i);
		const double Speed = LegSpeed[i];
		const double Len = FVector::Dist2D(Route[i - 1], Route[i]);
		const double Dur = Len / FMath::Max(Speed, 1.0);
		const FVector Dir = (Route[i] - Route[i - 1]).GetSafeNormal();
		const FVector Vel = Dir * Speed;

		for (int32 t = 0; t < 2; ++t)
		{
			const FTurret T = Staged(t, Ph);
			bool bOpen = false;
			double OpenStart = 0.0;
			double MaxBearing = 0.0;
			double PrevBearing = 0.0;
			bool bHavePrev = false;
			double NoSolRun = 0.0;
			double OutRun = 0.0;

			for (int32 k = 0; k <= kSamples; ++k)
			{
				const double F = double(k) / double(kSamples);
				const double Tm = F * Dur;
				const FVector P = FMath::Lerp(Route[i - 1], Route[i], F);
				const double Standoff = FVector::Dist2D(P, T.StagedLoc);
				if (Standoff < kMinStandoffUu)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walk to stop %d passes %.0f uu "
							 "from turret %d's base; the character would jam on it"),
						i, Standoff, t + 1));
					return false;
				}

				if (OutOfReachFor(T, P)) { OutRun += Dur / kSamples; }
				else { LongestOutOfReach = FMath::Max(LongestOutOfReach, OutRun);
					   OutRun = 0.0; }
				if (!OutOfReachFor(T, P) && NoSolutionFor(T, P, Vel))
				{
					NoSolRun += Dur / kSamples;
				}
				else
				{
					LongestNoSolution = FMath::Max(LongestNoSolution, NoSolRun);
					NoSolRun = 0.0;
				}

				double Flight = 0.0;
				const bool bNow = WindowOpenFor(T, P, Vel, Flight);
				if (bNow)
				{
					if (Tm >= kSteadyS && Flight + kFlightMarginS <= Dur - Tm)
					{
						GradeableFor[t] += Dur / kSamples;
					}
					const FVector Meet = P + Vel * Flight;
					const FVector Look = Meet - T.StagedBarrelLoc;
					const double Bear = FMath::Atan2(Look.Y, Look.X);
					if (bHavePrev)
					{
						double D = Bear - PrevBearing;
						while (D > UE_PI) { D -= 2.0 * UE_PI; }
						while (D < -UE_PI) { D += 2.0 * UE_PI; }
						MaxBearing = FMath::Max(MaxBearing,
							FMath::Abs(D) / (Dur / kSamples));
					}
					PrevBearing = Bear;
					bHavePrev = true;
				}
				else
				{
					bHavePrev = false;
				}

				if (bNow && !bOpen) { bOpen = true; OpenStart = Tm; MaxBearing = 0.0; }
				if ((!bNow || k == kSamples) && bOpen)
				{
					bOpen = false;
					const double Dw = Tm - OpenStart;
					const int32 Need = ShotsRequired(Dw, T.Traverse, T.Reload);
					if (Need > 0)
					{
						++DemandedWindows[t];
						if (Dw < kWindowReloadX * T.Reload)
						{
							FinishTest(EFunctionalTestResult::Error, FString::Printf(
								TEXT("HARNESS-PRECONDITION: the walk to stop %d asks "
									 "turret %d for a shot inside %.1f s and its "
									 "reload is %.1f s"), i, t + 1, Dw, T.Reload));
							return false;
						}
						if (FMath::RadiansToDegrees(MaxBearing)
							> kBearingFrac * T.Traverse)
						{
							FinishTest(EFunctionalTestResult::Error, FString::Printf(
								TEXT("HARNESS-PRECONDITION: on the walk to stop %d "
									 "turret %d's aim point swings at %.1f deg/s and "
									 "its barrel only turns at %.0f deg/s; the shot "
									 "the yard demands is one it could not take"),
								i, t + 1, FMath::RadiansToDegrees(MaxBearing),
								T.Traverse));
							return false;
						}
					}
				}
			}
			LongestNoSolution = FMath::Max(LongestNoSolution, NoSolRun);
			LongestOutOfReach = FMath::Max(LongestOutOfReach, OutRun);
		}
	}

	// (4) Neither the engage duty nor the accuracy gate may be vacuous.
	for (int32 t = 0; t < 2; ++t)
	{
		if (DemandedWindows[t] == 0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the route never asks turret %d for a "
					 "shot, so a turret that fires nothing would pass"), t + 1));
			return false;
		}
		if (GradeableFor[t] < kMinGradeablePerTurretS)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: turret %d gets only %.1f s of the route "
					 "in which a shot could be judged for accuracy at all"),
				t + 1, GradeableFor[t]));
			return false;
		}
	}
	// (5) And neither hold-fire gate may be vacuous either.
	if (LongestNoSolution < kMinNoSolutionS)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the route's longest stretch with a target in "
				 "reach but no interception is %.1f s; hold-fire would not be "
				 "measured"), LongestNoSolution));
		return false;
	}
	if (LongestOutOfReach < 5.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the route's longest stretch beyond a turret's "
				 "reach is %.1f s; the reach test would not be measured"),
			LongestOutOfReach));
		return false;
	}

	UE_LOG(LogTemp, Display, TEXT("[t2-turret] plan OK: demanded windows %d/%d, "
		"gradeable %.1f/%.1f s, longest no-interception %.1f s, longest out-of-reach "
		"%.1f s"), DemandedWindows[0], DemandedWindows[1], GradeableFor[0],
		GradeableFor[1], LongestNoSolution, LongestOutOfReach);
	return true;
}

void ATurretLeadFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	ApplyPhase(0);
	if (!RefreshLiveNumbers())
	{
		return;
	}
	BuildRoute();
	if (Route.Num() != 9)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the route did not build"));
		return;
	}
	if (!ValidatePlan())
	{
		return;
	}

	StagedTopSpeed = LegSpeed[0];
	Hero->GetCharacterMovement()->MaxWalkSpeed = float(StagedTopSpeed);
	HeroPrevAt = Hero->GetActorLocation();
	bHaveHeroPrev = true;

	// The last entry is a SENTINEL, far past the ~140 s route, because the base class
	// ends the test the moment the last scheduled checkpoint is sampled. A healthy run
	// finishes itself well before it; a run that stalled in phase 1 arrives here and
	// is failed for the legs it never walked.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kSentinelIndex; ++k)
	{
		Schedule.Add(double(k) * 10.0);
	}
	Schedule.Add(kSentinelS);
	SetCheckpointSchedule(Schedule);
}

// =================================================================================
// Per-frame
// =================================================================================

bool ATurretLeadFunctionalTest::HeroIsSteady(double Now) const
{
	if (HistT.Num() < 2)
	{
		return false;
	}
	const FVector VNow = HistV.Last();
	const double SpNow = VNow.Size();
	if (SpNow < kMovingFloorUu)
	{
		return false;
	}
	if (HistT[0] > Now - kSteadyS)
	{
		return false;   // not enough history to say it has been steady for a second
	}
	const FVector DirNow = VNow / SpNow;
	const double CosBar = FMath::Cos(FMath::DegreesToRadians(kSteadyDirDeg));
	for (int32 i = 0; i < HistT.Num(); ++i)
	{
		if (HistT[i] < Now - kSteadyS)
		{
			continue;
		}
		const double Sp = HistV[i].Size();
		if (FMath::Abs(Sp - SpNow) > kSteadySpeedFrac * SpNow)
		{
			return false;
		}
		if (Sp <= UE_KINDA_SMALL_NUMBER
			|| FVector::DotProduct(HistV[i] / Sp, DirNow) < CosBar)
		{
			return false;
		}
	}
	return true;
}

bool ATurretLeadFunctionalTest::CheckIntegrity(double Dt)
{
	// THE CHARACTER IS THE YARD'S. Writing its top speed down would give every shot a
	// solution and make the whole hold-fire half of the task disappear.
	const double TopNow = Hero->GetCharacterMovement()->MaxWalkSpeed;
	if (FMath::Abs(TopNow - StagedTopSpeed) > 1.0)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheCharacterKeptTheSpeedTheYardSet: the yard set the character's top "
				 "speed to %.0f uu/s and it is now %.0f. How fast the character can "
				 "move is not yours to change"), StagedTopSpeed, TopNow));
		return false;
	}

	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		FTurret& T = Turrets[i];
		AActor* const A = T.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: turret %d stopped "
					 "existing mid-run"), i + 1));
			return false;
		}
		// BOLTED. The most natural first pass at "make the turret aim" is to rotate
		// the actor, which works mechanically -- the barrel is attached, so the shots
		// still connect -- and turns a base the yard says does not turn.
		const double RotOff = FMath::RadiansToDegrees(
			double(A->GetActorQuat().AngularDistance(T.StagedRot)));
		const double LocOff = FVector::Dist(A->GetActorLocation(), T.StagedLoc);
		if (RotOff > kBoltedRotDeg || LocOff > kBoltedLocUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: turret %d's body "
					 "has turned %.1f deg and moved %.1f uu from where the yard bolted "
					 "it. The base does not turn -- only the barrel moves"),
				i + 1, RotOff, LocOff));
			return false;
		}
		if (T.BasePart.IsValid())
		{
			const double BaseOff = FMath::RadiansToDegrees(
				double(T.BasePart->GetComponentQuat().AngularDistance(T.StagedBaseRot)));
			if (BaseOff > kBoltedRotDeg)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: turret %d's "
						 "base has turned %.1f deg. The base does not turn -- only "
						 "the barrel moves"), i + 1, BaseOff));
				return false;
			}
		}
		if (!T.Barrel.IsValid())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: turret %d has no "
					 "barrel any more"), i + 1));
			return false;
		}
		const double BarrelTravel =
			FVector::Dist(T.Barrel->GetComponentLocation(), T.StagedBarrelLoc);
		if (BarrelTravel > kBoltedLocUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: turret %d's barrel "
					 "has travelled %.1f uu from where it is mounted. It swings; it "
					 "does not move"), i + 1, BarrelTravel));
			return false;
		}

		// THE BARREL SWINGS; IT DOES NOT SNAP. The whole trigger-against-servo problem
		// disappears if a barrel can be pointed straight at the answer, so the rate is
		// measured rather than assumed. The allowance is three frames of legal slew
		// plus a degree and a half, which absorbs any tick-order jitter between this
		// fixture and the turret and still leaves a snap caught by an order of
		// magnitude.
		const FQuat BarrelNow = T.Barrel->GetComponentQuat();
		if (T.bHaveLastBarrel && FramesGraded > 2)
		{
			const double Swung = FMath::RadiansToDegrees(
				double(BarrelNow.AngularDistance(T.LastBarrel)));
			const double Allowed =
				T.Traverse * FMath::Max(Dt, 1.0 / 60.0) * kSlewSlackX + kSlewSlackDeg;
			if (Swung > Allowed)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheBarrelSwingsAtItsOwnRate: turret %d's barrel moved %.1f "
						 "deg in one frame and that turret swings at %.0f deg/s, which "
						 "is at most %.1f deg in that time. You point the barrel "
						 "somewhere and it swings there at its own rate"),
					i + 1, Swung, T.Traverse, Allowed));
				return false;
			}
		}
		T.LastBarrel = BarrelNow;
		T.bHaveLastBarrel = true;
	}
	return true;
}

bool ATurretLeadFunctionalTest::TrackShots(double Now, const FVector& HeroPrev,
	const FVector& HeroAt)
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Live;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("TurretShot")), Live);
	if (Live.Num() > kMaxLiveShots)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NoTurretFiresFasterThanItsOwnReload: %d shots are in the air at "
				 "once. A turret fires as often as its own reload allows and no "
				 "faster"), Live.Num()));
		return false;
	}

	const FVector HeroVel = Hero->GetVelocity();
	const bool bSteady = HeroIsSteady(Now);
	const double LegLeft = Route.IsValidIndex(Waypoint) && HeroVel.Size() > 1.0
		? FVector::Dist2D(HeroAt, Route[Waypoint]) / HeroVel.Size()
		: 0.0;

	for (AActor* const A : Live)
	{
		bool bKnown = false;
		for (const FShot& S : Shots)
		{
			if (S.Actor.Get() == A) { bKnown = true; break; }
		}
		if (bKnown)
		{
			continue;
		}

		// --- a NEW shot. Its provenance is the fixture's, not the submission's. ---
		FShot S;
		S.Actor = A;
		S.T0 = Now;
		S.P0 = A->GetActorLocation();
		S.LastPos = S.P0;
		S.bSpeedAmbiguous = FMath::Abs(Now - LastRetuneAt) < kRetuneBlurS;

		if (FramesGraded <= 1)
		{
			// ADOPTED, NOT JUDGED. AFunctionalTest warms up for a few tenths of a
			// second before StartTest, and a turret is free to fire in that window.
			// The fixture did not see those shots leave, so it knows neither when nor
			// from what -- charging them against the reload, the reach or the
			// existence test would be inventing evidence. They are tracked only so
			// they are not re-discovered as new every frame.
			S.bSpeedAmbiguous = true;
			Shots.Add(S);
			continue;
		}

		int32 Best = -1;
		double BestD = 1.0e9;
		for (int32 i = 0; i < Turrets.Num(); ++i)
		{
			if (!Turrets[i].Muzzle.IsValid())
			{
				continue;
			}
			const double D =
				FVector::Dist(S.P0, Turrets[i].Muzzle->GetComponentLocation());
			if (D < BestD) { BestD = D; Best = i; }
		}
		if (Best < 0 || BestD > kMuzzleWindowUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: a shot appeared "
					 "%.0f uu from the nearest muzzle in the yard. A shot leaves the "
					 "gun that fired it, from its muzzle"), BestD));
			return false;
		}
		S.Turret = Best;
		FTurret& T = Turrets[Best];
		S.Speed = T.Speed;
		S.BarrelFwd0 = T.Barrel.IsValid() ? T.Barrel->GetForwardVector()
										  : FVector::ForwardVector;

		// RELOAD. The gap is measured against the SMALLEST reload this turret has
		// advertised since its last shot, so a re-tune can only ever forgive.
		if (T.LastShotAt > -1.0e5)
		{
			const double Gap = Now - T.LastShotAt;
			const double Need = kReloadForgive * T.MinReloadSince;
			if (Gap < Need)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("NoTurretFiresFasterThanItsOwnReload: turret %d fired %.2f s "
						 "after its previous shot and its reload is %.2f s. A turret "
						 "fires as often as its own reload allows and no faster"),
					Best + 1, Gap, T.MinReloadSince));
				return false;
			}
		}
		T.LastShotAt = Now;
		T.MinReloadSince = T.Reload;
		++T.TotalShots;

		// REACH. Measured from the turret, with a quarter forgiven either way.
		if (OutOfReachFor(T, HeroAt))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingIsFiredBeyondItsOwnReach: a turret fired at a character "
					 "standing outside its own engagement distance. Turret %d, "
					 "character %.0f uu away, that turret's reach %.0f uu"),
				Best + 1, FVector::Dist(HeroAt, T.StagedLoc), T.Reach));
			return false;
		}
		// EXISTENCE. Nothing a straight shot at this turret's own speed could catch.
		if (NoSolutionFor(T, HeroAt, HeroVel))
		{
			double Across = 0.0;
			double Along = 0.0;
			SightSplit(HeroAt - T.StagedBarrelLoc, HeroVel, Across, Along);
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingIsFiredWithNowhereToAim: a turret fired when no straight "
					 "shot leaving then at its own speed could ever have met the "
					 "character. Turret %d shoots at %.0f uu/s; the character is doing "
					 "%.0f uu/s, %.0f of it across the line of sight and %.0f of it "
					 "opening the range"),
				Best + 1, T.Speed, HeroVel.Size(), Across, Along));
			return false;
		}

		if (T.bWindowOpen)
		{
			++T.WindowShots;
		}
		// GRADEABLE FOR ACCURACY? Computed purely from the world and the route, so
		// nothing a submission does can widen or narrow it.
		double Flight = 0.0;
		const bool bWin = WindowOpenFor(T, HeroAt, HeroVel, Flight);
		if (bSteady && bWin && !S.bSpeedAmbiguous
			&& Flight + kFlightMarginS <= LegLeft)
		{
			S.bGradeable = true;
			S.SolveT = Flight;
			++T.GradeableShots;
		}
		Shots.Add(S);
	}

	// --- follow every shot already on the books ---------------------------------
	for (int32 i = Shots.Num() - 1; i >= 0; --i)
	{
		FShot& S = Shots[i];
		AActor* const A = S.Actor.Get();
		if (A == nullptr)
		{
			if (S.bGradeable && !S.bJudged)
			{
				S.bJudged = true;
				if (S.MinDistUu > kHitToleranceUu)
				{
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("ShotsFromTheOpenConnect: turret %d shot at a character "
							 "walking a straight line in the open and the shot's "
							 "closest approach was %.0f uu. A shot connects if it "
							 "passes within 120 cm of the middle of the character; "
							 "every shot taken in those conditions has to"),
						S.Turret + 1, S.MinDistUu));
					return false;
				}
			}
			Shots.RemoveAtSwap(i);
			continue;
		}

		const FVector P = A->GetActorLocation();
		// CLOSEST APPROACH, segment against segment, so frame discretisation
		// contributes nothing to the number the accuracy gate reads.
		FVector CA = FVector::ZeroVector;
		FVector CB = FVector::ZeroVector;
		FMath::SegmentDistToSegmentSafe(S.LastPos, P, HeroPrev, HeroAt, CA, CB);
		S.MinDistUu = FMath::Min(S.MinDistUu, FVector::Dist(CA, CB));

		const double Elapsed = Now - S.T0;
		if (!S.bHaveDir && Elapsed >= 0.20)
		{
			S.Dir = (P - S.P0).GetSafeNormal();
			S.bHaveDir = true;
			// ALONG THE BARREL. Six degrees, not a quarter of one: this fixture
			// samples once a frame and the fastest barrel in the yard legally swings
			// 2.2 deg between two samples, so a tighter bar would fail correct work on
			// tick order alone.
			const double Off = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
				FVector::DotProduct(S.Dir, S.BarrelFwd0.GetSafeNormal()), -1.0, 1.0)));
			if (Off > kBarrelConeDeg)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheBaseIsBoltedDownAndTheBarrelDoesTheAiming: turret %d's "
						 "shot left %.1f deg away from where its barrel was actually "
						 "pointing. The barrel is the gun -- a shot leaves along it, "
						 "not along whatever you worked out"), S.Turret + 1, Off));
				return false;
			}
		}
		if (S.bHaveDir && !S.bSpeedAmbiguous)
		{
			// STRAIGHT, AND AT THAT TURRET'S OWN SPEED. The reference path uses the
			// fixture's read of the firing turret's LIVE number, never anything the
			// shot carries, so re-stamping the shot buys nothing.
			const FVector Want = S.P0 + S.Dir * (S.Speed * Elapsed);
			const double Off = FVector::Dist(P, Want);
			const double Bar = FMath::Max(kStraightFrac * S.Speed, kStraightMinUu);
			if (Off > Bar)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("ShotsFlyStraightAtTheirOwnSpeed: turret %d's shot is %.0f uu "
						 "off the straight line it left on, %.2f s after it was fired. "
						 "A shot travels dead straight at that turret's own %.0f uu/s "
						 "and is never pulled down or steered"),
					S.Turret + 1, Off, Elapsed, S.Speed));
				return false;
			}
		}
		S.LastPos = P;

		if (S.bGradeable && !S.bJudged && Elapsed >= S.SolveT + kJudgeAfterS)
		{
			S.bJudged = true;
			if (S.MinDistUu > kHitToleranceUu)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("ShotsFromTheOpenConnect: turret %d shot at a character "
						 "walking a straight line in the open and the shot's closest "
						 "approach was %.0f uu. A shot connects if it passes within "
						 "120 cm of the middle of the character; every shot taken in "
						 "those conditions has to"), S.Turret + 1, S.MinDistUu));
				return false;
			}
		}
	}
	return true;
}

bool ATurretLeadFunctionalTest::CloseWindow(FTurret& T, int32 Index, double Now)
{
	if (!T.bWindowOpen)
	{
		return true;
	}
	T.bWindowOpen = false;
	const double Dur = Now - T.WindowStart;
	const int32 Need = ShotsRequired(Dur, T.Traverse, T.Reload);
	if (T.WindowShots < Need)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheTurretsActuallyEngage: a turret sat silent through a stretch "
				 "where the character was moving, inside that turret's own engagement "
				 "distance, and a straight shot at that turret's own speed would "
				 "genuinely have met them. Turret %d, %.1f s, %d shot(s) where %d "
				 "were required at a reload of %.1f s"),
			Index + 1, Dur, T.WindowShots, Need, T.Reload));
		return false;
	}
	T.WindowShots = 0;
	return true;
}

void ATurretLeadFunctionalTest::DriveHero(double Now)
{
	if (!Route.IsValidIndex(Waypoint) || !Hero.IsValid())
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Route[Waypoint];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kArriveUu)
	{
		// STAND HERE. A drive that advances on arrival consumes its waypoints in a
		// handful of frames and nothing is ever measured; and the re-tunes need a
		// stationary character so no firing window ever spans one.
		if (!bDwelling)
		{
			bDwelling = true;
			DwellStart = Now;
		}
		else if (Now >= DwellStart + kDwellS)
		{
			bDwelling = false;
			++Waypoint;
			if (Route.IsValidIndex(Waypoint))
			{
				StagedTopSpeed = LegSpeed[Waypoint];
				Hero->GetCharacterMovement()->MaxWalkSpeed = float(StagedTopSpeed);
			}
		}
	}
	else
	{
		bDwelling = false;
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
	}
}

bool ATurretLeadFunctionalTest::FinishTotals(double Now)
{
	if (bTotalsDone)
	{
		return true;
	}
	bTotalsDone = true;
	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		if (!CloseWindow(Turrets[i], i, Now))
		{
			return false;
		}
	}
	int32 Total = 0;
	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		Total += Turrets[i].GradeableShots;
	}
	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		if (Turrets[i].GradeableShots < 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("EveryTurretTookAShotYouCanJudge: turret %d never once fired at a "
					 "character who was walking a straight line in the open inside its "
					 "reach with a shot plainly available, so nothing it did could be "
					 "judged for accuracy. It took %d shot(s) in all"),
				i + 1, Turrets[i].TotalShots));
			return false;
		}
	}
	if (Total < 4)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("EveryTurretTookAShotYouCanJudge: the yard offered both turrets many "
				 "chances at a character walking a straight line in the open and only "
				 "%d shot(s) in the whole run could be judged for accuracy"), Total));
		return false;
	}
	UE_LOG(LogTemp, Display, TEXT("[t2-turret] route complete at %.1f s: shots "
		"%d/%d, gradeable %d/%d, re-tunes %d"), Now, Turrets[0].TotalShots,
		Turrets[1].TotalShots, Turrets[0].GradeableShots, Turrets[1].GradeableShots,
		RetunesDone);
	FinishTest(EFunctionalTestResult::Succeeded, TEXT("t2-turret-leads-you-and-holds-"
		"fire: both turrets led a walking character, held fire where nothing could be "
		"caught, and did it through two re-tunings"));
	return true;
}

void ATurretLeadFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || Turrets.Num() != 2 || DeltaSeconds <= 0.0f)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	const double Dt = double(DeltaSeconds);
	const FVector HeroAt = Hero->GetActorLocation();
	const FVector HeroPrev = bHaveHeroPrev ? HeroPrevAt : HeroAt;
	const FVector HeroVel = Hero->GetVelocity();
	++FramesGraded;

	if (!RefreshLiveNumbers())
	{
		return;
	}
	if (!CheckIntegrity(Dt))
	{
		return;
	}

	HistT.Add(Now);
	HistV.Add(HeroVel);
	while (HistT.Num() > 0 && HistT[0] < Now - (kSteadyS + 0.3))
	{
		HistT.RemoveAt(0);
		HistV.RemoveAt(0);
	}

	// Firing windows, opened and closed from the world alone.
	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		FTurret& T = Turrets[i];
		double Flight = 0.0;
		const bool bOpen = WindowOpenFor(T, HeroAt, HeroVel, Flight);
		if (bOpen && !T.bWindowOpen)
		{
			T.bWindowOpen = true;
			T.WindowStart = Now;
			T.WindowShots = 0;
		}
		else if (!bOpen && T.bWindowOpen)
		{
			if (!CloseWindow(T, i, Now))
			{
				return;
			}
		}
	}

	if (!TrackShots(Now, HeroPrev, HeroAt))
	{
		return;
	}

	// THE RE-TUNES, a second and a half into the dwell so no window ever spans one.
	if (bDwelling && Now >= DwellStart + kRetuneAfterDwellS)
	{
		if (Waypoint == 3 && RetunesDone == 0)
		{
			for (int32 i = 0; i < Turrets.Num(); ++i)
			{
				if (!CloseWindow(Turrets[i], i, Now)) { return; }
			}
			ApplyPhase(1);
			RetunesDone = 1;
			LastRetuneAt = Now;
		}
		else if (Waypoint == 6 && RetunesDone == 1)
		{
			for (int32 i = 0; i < Turrets.Num(); ++i)
			{
				if (!CloseWindow(Turrets[i], i, Now)) { return; }
			}
			ApplyPhase(2);
			RetunesDone = 2;
			LastRetuneAt = Now;
		}
	}

	DriveHero(Now);
	HeroPrevAt = HeroAt;
	bHaveHeroPrev = true;

	if (Waypoint >= Route.Num())
	{
		// The route is walked; give the shots already in the air time to land before
		// the totals are taken, then finish. Every per-frame gate stays live for the
		// drain and nothing is evaluated twice.
		if (RouteDoneAt < 0.0)
		{
			RouteDoneAt = Now;
		}
		else if (Now >= RouteDoneAt + kDrainS)
		{
			FinishTotals(Now);
		}
	}
}

void ATurretLeadFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	const double Sp = Hero.IsValid() ? Hero->GetVelocity().Size() : 0.0;
	FString S;
	for (int32 i = 0; i < Turrets.Num(); ++i)
	{
		const FTurret& T = Turrets[i];
		S += FString::Printf(TEXT("t%d[s%.0f R%.0f tr%.0f rl%.1f d%.0f w%d n%d g%d] "),
			i + 1, T.Speed, T.Reach, T.Traverse, T.Reload,
			FVector::Dist(H, T.StagedLoc), T.bWindowOpen ? 1 : 0, T.TotalShots,
			T.GradeableShots);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-turret calib] cp%d t=%.2f ph%d wp=%d at=(%.0f,%.0f) v=%.0f %s"),
		Index, Now, Phase + 1, Waypoint, H.X, H.Y, Sp, *S);
}

void ATurretLeadFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}
	// THE SENTINEL. A healthy run has already finished itself in the drain after the
	// last leg; arriving here means the yard never got through the route, so the legs
	// it did walk cannot stand in for the ones it did not.
	if (Waypoint < Route.Num())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardWalkedTheWholeRoute: the run stopped at stop %d of %d with "
				 "%d of 2 re-tunings done. The legs that did run cannot answer for the "
				 "ones that did not"), Waypoint, Route.Num(), RetunesDone));
		return;
	}
	FinishTotals(TimeSeconds);
}
