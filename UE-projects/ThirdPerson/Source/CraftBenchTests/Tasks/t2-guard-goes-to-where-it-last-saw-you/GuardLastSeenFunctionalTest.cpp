// Copyright CraftBench. All Rights Reserved.

#include "GuardLastSeenFunctionalTest.h"

#include "CollisionQueryParams.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED IN THE PROMPT. Every one of these appears in the text the agent
	// reads, as a number of metres or of seconds.
	constexpr double kCloseUu      = 500.0;   // "close to within five metres of them"
	constexpr double kArriveUu     = 400.0;   // "within four metres of that spot counts as arriving"
	constexpr double kHoldUu       = 700.0;   // "stays within seven metres of that spot"
	constexpr double kHoldS        = 6.0;     // "for six seconds"
	constexpr double kHomeUu       = 300.0;   // "within three metres of where it started"
	constexpr double kBlindFloorUu = 1200.0;  // "never within twelve metres of them"
	constexpr double kBlindGraceS  = 5.0;     // "once it has not been able to see them for five seconds"
	constexpr double kUnbrokenS    = 2.0;     // "unbroken sight for two seconds"
	constexpr double kAllowS       = 6.0;     // "plus six seconds"

	// ---- NOT disclosed: fixture clocking. Every one of them WIDENS a window rather
	// than narrowing it, so none can turn a correct answer into a FAIL.
	constexpr double kSlackS       = 2.0;     // on top of every disclosed deadline
	constexpr double kWalkWindowS  = 1.0;     // rolling window for "it only ever walked"
	constexpr double kWalkFactor   = 1.4;     // a watchman doing its own pace has 40% spare
	constexpr double kWalkSlackUu  = 60.0;    // plus this, for capsule depenetration
	constexpr double kHeroWindowUu = 820.0;   // a 500 uu/s hero over 1.0 s, x1.4, +120
	constexpr double kWaypointUu   = 70.0;
	constexpr double kWallClearUu  = 200.0;   // the drive never passes closer to a wall
	constexpr double kSentinelS    = 306.0;
	constexpr double kStandBackUu  = 1200.0;  // where the hero stands on the way back out
	constexpr int32  kSentinelIdx  = 50;      // schedule is 6..300 (indices 0..49), then 306
}

AGuardLastSeenFunctionalTest::AGuardLastSeenFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Resolution
// ---------------------------------------------------------------------------

bool AGuardLastSeenFunctionalTest::ResolveYard()
{
	UWorld* const World = GetWorld();

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in the "
				 "yard, so there is nobody for a watchman to see"));
		return false;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardWatchman")), Found);
	if (Found.Num() != 2)
	{
		// GRADED, not attributed: the yard places exactly two, and the only ways to end
		// up with a different number are a submission that re-labelled, destroyed or
		// duplicated one. A behaviour-caused fault must never buy a non-graded verdict.
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheWatchmenAreAsTheYardBuiltThem: the yard has %d actor(s) answering "
				 "to the watchman tag and it placed exactly 2. The two standing out "
				 "there are the two that must do this work"), Found.Num()));
		return false;
	}
	// A stable identity, so "watchman <name>" means the same one in every message.
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });

	for (AActor* A : Found)
	{
		ACharacter* const C = Cast<ACharacter>(A);
		if (C == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheWatchmenAreAsTheYardBuiltThem: a watchman is no longer a body "
					 "that can walk. The two out there are the yard's, not yours"));
			return false;
		}
		const FFloatProperty* const PaceProp =
			FindFProperty<FFloatProperty>(C->GetClass(), TEXT("WalkPaceUuPerSecond"));
		const FFloatProperty* const RangeProp =
			FindFProperty<FFloatProperty>(C->GetClass(), TEXT("SightRangeUu"));
		if (PaceProp == nullptr || RangeProp == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheWatchmenAreAsTheYardBuiltThem: a watchman no longer reports "
					 "its own walking pace and sight range as readable numbers, and "
					 "every allowance in this yard is measured from those two"));
			return false;
		}
		FWatch W;
		W.Actor = C;
		W.Name = C->GetName();
		W.Post = C->GetActorLocation();
		W.Pace = PaceProp->GetPropertyValue_InContainer(C);
		W.Range = RangeProp->GetPropertyValue_InContainer(C);
		if (W.Pace < 50.0f || W.Range < 200.0f)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheWatchmenAreAsTheYardBuiltThem: watchman %s reports a pace of "
					 "%.0f uu/s and a sight range of %.0f uu, which is not what the "
					 "yard set on it. Those two numbers are the yard's"),
				*W.Name, W.Pace, W.Range));
			return false;
		}
		Watch.Add(MoveTemp(W));
	}

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardWall")), Found);
	if (Found.Num() < 6)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %d wall(s) tagged YardWall, expected at least "
				 "the six that make the two alcoves"), Found.Num()));
		return false;
	}
	for (AActor* A : Found)
	{
		FWall Wall;
		Wall.Actor = A;
		Walls.Add(MoveTemp(Wall));
	}
	MeasureWalls();
	return true;
}

void AGuardLastSeenFunctionalTest::MeasureWalls()
{
	AlcoveBox[0] = FBox(ForceInit);
	AlcoveBox[1] = FBox(ForceInit);
	for (FWall& W : Walls)
	{
		AActor* const A = W.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		W.StagedAt = A->GetActorLocation();
		W.Bounds = A->GetComponentsBoundingBox(true);
		// The two alcoves are told apart by which side of the yard they stand on --
		// a fact read off the world, not a name the fixture invented.
		const int32 Side = (W.StagedAt.Y >= 0.0) ? 0 : 1;
		AlcoveBox[Side] += W.Bounds;
	}
}

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

FVector AGuardLastSeenFunctionalTest::HeroEyePoint() const
{
	const ACharacter* const H = Hero.Get();
	return (H != nullptr) ? H->GetPawnViewLocation() : FVector::ZeroVector;
}

bool AGuardLastSeenFunctionalTest::FixtureCanSee(const FWatch& W, const FVector& HeroEye) const
{
	const ACharacter* const C = W.Actor.Get();
	const UWorld* const World = GetWorld();
	if (C == nullptr || World == nullptr)
	{
		return false;
	}
	const FVector From = C->GetPawnViewLocation();
	if (FVector::Dist(From, HeroEye) > double(W.Range))
	{
		return false;
	}
	FCollisionQueryParams Params(FName(TEXT("YardFixtureSight")), /*bTraceComplex=*/false, C);
	Params.AddIgnoredActor(Hero.Get());
	return !World->LineTraceTestByChannel(From, HeroEye, ECC_Visibility, Params);
}

bool AGuardLastSeenFunctionalTest::SegmentHitsAnyWall(const FVector& A, const FVector& B) const
{
	const UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return true;
	}
	FCollisionQueryParams Params(FName(TEXT("YardClearance")), /*bTraceComplex=*/false);
	Params.AddIgnoredActor(Hero.Get());
	for (const FWatch& W : Watch)
	{
		Params.AddIgnoredActor(W.Actor.Get());
	}
	return World->LineTraceTestByChannel(A, B, ECC_Visibility, Params);
}

double AGuardLastSeenFunctionalTest::ClearanceToWalls(const FVector& P) const
{
	double Best = 1.0e9;
	for (const FWall& W : Walls)
	{
		if (!W.Actor.IsValid())
		{
			continue;
		}
		// 2D distance from P to the wall's footprint; zero inside it.
		const FBox& B = W.Bounds;
		const double DX = FMath::Max3(B.Min.X - P.X, 0.0, P.X - B.Max.X);
		const double DY = FMath::Max3(B.Min.Y - P.Y, 0.0, P.Y - B.Max.Y);
		Best = FMath::Min(Best, FMath::Sqrt(DX * DX + DY * DY));
	}
	return Best;
}

// ---------------------------------------------------------------------------
// Staging
// ---------------------------------------------------------------------------

void AGuardLastSeenFunctionalTest::StageLeg(int32 LegIndex)
{
	bStaging = true;

	const int32 Side = (LegIndex == 0) ? 0 : 1;
	if (!FMath::IsNearlyZero(JitterAlcove[Side]))
	{
		const double Shift = JitterAlcove[Side];
		for (FWall& W : Walls)
		{
			AActor* const A = W.Actor.Get();
			if (A == nullptr)
			{
				continue;
			}
			if (((A->GetActorLocation().Y >= 0.0) ? 0 : 1) == Side)
			{
				A->SetActorLocation(A->GetActorLocation() + FVector(Shift, 0.0, 0.0),
					/*bSweep=*/false);
			}
		}
		JitterAlcove[Side] = 0.0;   // applied once
		MeasureWalls();             // and re-latched, so "nobody moved the walls" means AFTER this
	}

	for (FWatch& W : Watch)
	{
		W.bEverSawThisLeg = false;
		W.MinDistToSpot = 1.0e9;
		W.bReachedSpot = false;
		W.ReachedAt = -1.0;
		W.HoldRun = 0.0;
		W.HoldBest = 0.0;
		W.bHoldSatisfied = false;
		W.HoldDeadline = -1.0;
		W.HomeDeadline = -1.0;
		W.bHomeSatisfied = false;
		W.ArriveDeadline = -1.0;
		W.bChaseArmed = false;
		W.bChaseSatisfied = false;
		W.TrailT.Reset();
		W.TrailP.Reset();
	}
	Alert = FAlert();
	bFirstSightChecked = false;
	bLegHadSighting = false;

	BuildRoute();
	Waypoint = 0;
	DwellUntil = -1.0;
	bHeroStanding = false;

	// STAGING ONLY. Every measured metre of the character's motion is AddMovementInput.
	if (ACharacter* const H = Hero.Get())
	{
		H->SetActorLocation(Route[0], /*bSweep=*/false);
		if (UCharacterMovementComponent* const Move = H->GetCharacterMovement())
		{
			Move->StopMovementImmediately();
		}
	}
	HeroTrailT.Reset();
	HeroTrailP.Reset();
	bStaging = false;
}

void AGuardLastSeenFunctionalTest::BuildRoute()
{
	Route.Reset();
	RouteDwell.Reset();

	const ACharacter* const H = Hero.Get();
	const double Z = (H != nullptr) ? H->GetActorLocation().Z : 100.0;
	const int32 Side = (Leg == 0) ? 0 : 1;
	const double Sgn = (Leg == 0) ? 1.0 : -1.0;
	const double Lane = (Leg == 0) ? LaneY : -LaneY;
	const FBox& B = AlcoveBox[Side];

	// Everything below is read off the LIVE walls; no coordinate is written down, so
	// the same code produces leg 2's route after the yard has moved that alcove.
	// The alcove's mouth faces AWAY from the lane, so the character runs past it while
	// still receding from the watchman, comes round the far side, and drops in from
	// behind -- which is why nothing on the lane side can see into it afterwards.
	const double MidX = 0.5 * (B.Min.X + B.Max.X);
	const double TurnX = (Sgn > 0.0) ? (B.Max.X + 500.0) : (B.Min.X - 500.0);
	const double TopY = (Sgn > 0.0) ? (B.Max.Y + 500.0) : (B.Min.Y - 500.0);
	const double HideY = (Sgn > 0.0) ? (B.Max.Y - 550.0) : (B.Min.Y + 550.0);
	const double StartX = -2600.0 * Sgn;

	Route.Add(FVector(StartX, Lane, Z));   RouteDwell.Add(3.0);
	Route.Add(FVector(TurnX, Lane, Z));    RouteDwell.Add(0.4);
	Route.Add(FVector(TurnX, TopY, Z));    RouteDwell.Add(0.4);
	Route.Add(FVector(MidX, TopY, Z));     RouteDwell.Add(0.4);
	Route.Add(FVector(MidX, HideY, Z));    RouteDwell.Add(-1.0);
}

bool AGuardLastSeenFunctionalTest::CheckStagingPreconditions(FString& OutWhy)
{
	// (1) The posts stand on opposite sides of the yard and far enough apart that one
	//     lane cannot be inside both watchmen's range.
	const double PostGap = FVector::Dist2D(Watch[0].Post, Watch[1].Post);
	if (PostGap < 2000.0 || (Watch[0].Post.Y * Watch[1].Post.Y) >= 0.0)
	{
		OutWhy = FString::Printf(
			TEXT("HARNESS-PRECONDITION: the two posts are %.0f uu apart and on the "
				 "same side of the yard, so one lane would be inside both watchmen's "
				 "range and the radio would never be tested"), PostGap);
		return false;
	}

	// (2) Per leg: exactly one post reaches the lane with its own sight range, and it
	//     does so with margin. The second watchman is kept blind by DISTANCE, never by
	//     a wall -- a wall that hid the lane from it would also block its straight walk
	//     to the spot it gets told about.
	for (int32 L = 0; L < 2; ++L)
	{
		const double Lane = (L == 0) ? LaneY : -LaneY;
		const double Sgn = (L == 0) ? 1.0 : -1.0;
		int32 InRange = 0;
		for (const FWatch& W : Watch)
		{
			double Near = 1.0e9;
			for (int32 k = -30; k <= 30; ++k)
			{
				const FVector P(double(k) * 250.0 * Sgn, Lane, W.Post.Z);
				Near = FMath::Min(Near, FVector::Dist2D(P, W.Post));
			}
			if (Near < double(W.Range) - 200.0)
			{
				++InRange;
			}
			else if (Near < double(W.Range) + 200.0)
			{
				OutWhy = FString::Printf(
					TEXT("HARNESS-PRECONDITION: a post sits %.0f uu from lane %d and "
						 "sees %.0f uu; that is too near the edge of its own range for "
						 "the lane to be plainly inside it or plainly outside it"),
					Near, L + 1, W.Range);
				return false;
			}
		}
		if (InRange != 1)
		{
			OutWhy = FString::Printf(
				TEXT("HARNESS-PRECONDITION: %d of the 2 watchmen can reach lane %d with "
					 "their own sight range; exactly one must"), InRange, L + 1);
			return false;
		}
	}

	// (3) The drive never scrapes a wall, and the hiding place is genuinely hidden --
	//     from both posts and from a band around the lane wide enough to hold every
	//     spot a watchman could legitimately be searching. Sight is lost somewhere on
	//     the lane, and a searcher must stay within kHoldUu of that spot, so that band
	//     is exactly where a correct watchman will be standing.
	for (int32 L = 0; L < 2; ++L)
	{
		const int32 Side = (L == 0) ? 0 : 1;
		const double Sgn = (L == 0) ? 1.0 : -1.0;
		const double Lane = (L == 0) ? LaneY : -LaneY;
		FBox B = AlcoveBox[Side];
		if (!B.IsValid)
		{
			OutWhy = TEXT("HARNESS-PRECONDITION: one side of the yard has no walls, so "
				"it has no alcove and nothing would ever be out of sight");
			return false;
		}
		// The leg's own alcove has not been shifted yet when leg 1 is checked, so fold
		// the pending shift in here rather than checking geometry the run will not use.
		B = B.ShiftBy(FVector(JitterAlcove[Side], 0.0, 0.0));

		const double MidX = 0.5 * (B.Min.X + B.Max.X);
		const double TurnX = (Sgn > 0.0) ? (B.Max.X + 500.0) : (B.Min.X - 500.0);
		const double TopY = (Sgn > 0.0) ? (B.Max.Y + 500.0) : (B.Min.Y - 500.0);
		const double HideY = (Sgn > 0.0) ? (B.Max.Y - 550.0) : (B.Min.Y + 550.0);
		const double Z = Hero.IsValid() ? Hero->GetActorLocation().Z : 100.0;
		const FVector Hide(MidX, HideY, Z);
		const FVector HideEye = Hide + FVector(0.0, 0.0, 64.0);

		const FVector Legs[4][2] = {
			{ FVector(-2600.0 * Sgn, Lane, Z), FVector(TurnX, Lane, Z) },
			{ FVector(TurnX, Lane, Z),         FVector(TurnX, TopY, Z) },
			{ FVector(TurnX, TopY, Z),         FVector(MidX, TopY, Z) },
			{ FVector(MidX, TopY, Z),          Hide }
		};
		for (const FVector(&Seg)[2] : Legs)
		{
			for (int32 k = 0; k <= 40; ++k)
			{
				const FVector P = FMath::Lerp(Seg[0], Seg[1], double(k) / 40.0);
				const double Clear = ClearanceToWalls(P);
				if (Clear < kWallClearUu)
				{
					OutWhy = FString::Printf(
						TEXT("HARNESS-PRECONDITION: the drive passes %.0f uu from a "
							 "wall on leg %d and the character would scrape it"),
						Clear, L + 1);
					return false;
				}
			}
		}

		for (const FWatch& W : Watch)
		{
			const FVector PostEye = W.Post + FVector(0.0, 0.0, 64.0);
			if (FVector::Dist(PostEye, HideEye) <= double(W.Range)
				&& !SegmentHitsAnyWall(PostEye, HideEye))
			{
				OutWhy = FString::Printf(
					TEXT("HARNESS-PRECONDITION: the hiding place on leg %d is in plain "
						 "view of a post, so the watchman would never lose the "
						 "character and there would be nothing to search for"), L + 1);
				return false;
			}
		}
		for (int32 k = -28; k <= 28; ++k)
		{
			for (int32 j = -1; j <= 1; ++j)
			{
				const FVector Eye(double(k) * 250.0 * Sgn,
					Lane + double(j) * kHoldUu, Z + 64.0);
				if (ClearanceToWalls(Eye) < kWallClearUu)
				{
					continue;      // inside or against a wall: nobody can stand there,
					               // and a trace begun inside geometry answers nothing
				}
				if (FVector::Dist(Eye, HideEye) > double(FMath::Max(Watch[0].Range, Watch[1].Range)))
				{
					continue;      // out of range from there, so hidden anyway
				}
				if (!SegmentHitsAnyWall(Eye, HideEye))
				{
					OutWhy = FString::Printf(
						TEXT("HARNESS-PRECONDITION: on leg %d the hiding place can be "
							 "seen from (%.0f, %.0f), which is inside the band a "
							 "watchman searches; the search would turn straight back "
							 "into a chase and nothing would be measured"),
						L + 1, Eye.X, Eye.Y);
					return false;
				}
			}
		}
	}
	return true;
}

void AGuardLastSeenFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveYard())
	{
		return;
	}

	// STAGING OFFSETS, deterministic. An earlier version drew these from
	// FPlatformTime::Cycles(), which meant the same submission could be staged two
	// different ways and a FAIL could not be re-run -- and "reproducible from the log"
	// is forensics, not reproducibility. The seed is now fixed. The anti-hard-coding
	// value is unchanged, because what defeats a hard-coded coordinate is that the
	// fixture MOVES things away from where the map put them, not that the move is
	// unpredictable; the submission cannot read this fixture either way. Every draw is
	// still re-checked against the staging preconditions and halved until they hold:
	// staging may widen the yard's variety and may never manufacture a FAIL.
	const uint32 Seed = 0x5CB1A17Du;
	FRandomStream Rng{int32(Seed)};
	const double DrawA = double(Rng.FRandRange(-200.0f, 200.0f));
	const double DrawB = double(Rng.FRandRange(-200.0f, 200.0f));
	const double DrawLane = double(Rng.FRandRange(-40.0f, 40.0f));

	bool bStaged = false;
	FString Why;
	for (int32 Attempt = 0; Attempt < 5 && !bStaged; ++Attempt)
	{
		// Attempt 4 is the zero draw: the yard as it was authored. If even that fails a
		// precondition the level really is wrong, and the run is attributed rather than
		// scored against the submission.
		const double Scale = (Attempt < 4) ? FMath::Pow(0.5, double(Attempt)) : 0.0;
		JitterAlcove[0] = DrawA * Scale;
		JitterAlcove[1] = DrawB * Scale;
		LaneY = 600.0 + DrawLane * Scale;
		Why.Reset();
		bStaged = CheckStagingPreconditions(Why);
	}
	if (!bStaged)
	{
		FinishTest(EFunctionalTestResult::Error, Why);
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-lastseen stage] seed=%u alcoveShift=(%.0f,%.0f) laneY=%.0f pace=%.0f "
			 "range=%.0f posts=(%.0f,%.0f)/(%.0f,%.0f)"),
		Seed, JitterAlcove[0], JitterAlcove[1], LaneY, Watch[0].Pace, Watch[0].Range,
		Watch[0].Post.X, Watch[0].Post.Y, Watch[1].Post.X, Watch[1].Post.Y);

	StageLeg(0);

	TArray<double> Schedule;
	for (int32 k = 1; k <= 50; ++k)
	{
		Schedule.Add(double(k) * 6.0);
	}
	// THE SENTINEL, far past the ~190 s the two legs take, because the base class ends
	// the test the moment the last scheduled checkpoint is sampled.
	Schedule.Add(kSentinelS);
	SetCheckpointSchedule(Schedule);
}

// ---------------------------------------------------------------------------
// The drive
// ---------------------------------------------------------------------------

void AGuardLastSeenFunctionalTest::DriveHero(double Now)
{
	ACharacter* const H = Hero.Get();
	if (H == nullptr || !Route.IsValidIndex(Waypoint))
	{
		return;
	}
	const FVector Here = H->GetActorLocation();
	const FVector Target = Route[Waypoint];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);

	if (Flat.Size2D() > kWaypointUu)
	{
		H->AddMovementInput(Flat.GetSafeNormal2D(), 1.0f);
		bHeroStanding = false;
		return;
	}

	// STAND. Every gate here is about a state that has settled, and a route that only
	// passes through a spot never gives anybody a chance to be judged at it.
	bHeroStanding = true;

	const double Dwell = RouteDwell[Waypoint];
	if (Dwell >= 0.0)
	{
		if (DwellUntil < 0.0)
		{
			DwellUntil = Now + Dwell;
		}
		else if (Now >= DwellUntil)
		{
			++Waypoint;
			DwellUntil = -1.0;
			bHeroStanding = false;
		}
		return;
	}

	// The hiding place. Leg 1 holds until both watchmen are home again. Leg 2 holds
	// until both have stood their six seconds, and then the character walks back out
	// into the open while they are still trudging home.
	const bool bRelease = (Leg == 0)
		? (Watch[0].bHomeSatisfied && Watch[1].bHomeSatisfied)
		: ((Watch[0].bHoldSatisfied && Watch[1].bHoldSatisfied)
			|| (LegTwoReleaseAt > 0.0 && Now > LegTwoReleaseAt));
	if (!bRelease)
	{
		return;
	}
	++Waypoint;
	DwellUntil = -1.0;
	bHeroStanding = false;

	if (Leg == 1 && Waypoint >= Route.Num())
	{
		// THE WAY BACK OUT, resolved NOW from the live last-seen spot and the live
		// posts, so the standing places are facts about this run rather than
		// coordinates in this file. The three of them sit along the line the watchman
		// that answered the radio has to walk home, spread far enough apart that one
		// of them lands while it is still walking -- and the last one is close enough
		// to its post that even a watchman already standing on it has the character in
		// plain sight, so this gate cannot go unarmed by bad luck.
		const FBox& B = AlcoveBox[1];
		const double Z = H->GetActorLocation().Z;
		const double MidX = 0.5 * (B.Min.X + B.Max.X);
		const double TurnX = B.Min.X - 500.0;
		const double TopY = B.Min.Y - 500.0;
		const double Lane = -LaneY;
		Route.Add(FVector(MidX, TopY, Z));    RouteDwell.Add(0.3);
		Route.Add(FVector(TurnX, TopY, Z));   RouteDwell.Add(0.3);
		Route.Add(FVector(TurnX, Lane, Z));   RouteDwell.Add(0.3);

		const int32 RespIdx = (Alert.Spotter == 0) ? 1 : 0;
		const FVector RespPost = Watch[RespIdx].Post;
		const FVector Back = FVector(RespPost.X - Alert.Spot.X,
			RespPost.Y - Alert.Spot.Y, 0.0).GetSafeNormal2D();
		const double Home = FVector::Dist2D(Alert.Spot, RespPost);
		const double Ds[3] = {
			kStandBackUu,
			FMath::Min(kStandBackUu * 2.2, FMath::Max(Home - 1500.0, kStandBackUu + 600.0)),
			FMath::Max(Home - 900.0, kStandBackUu * 2.2 + 600.0)
		};
		const double Dwells[3] = { 14.0, 14.0, 16.0 };
		for (int32 k = 0; k < 3; ++k)
		{
			Route.Add(FVector(Alert.Spot.X + Back.X * Ds[k],
				Alert.Spot.Y + Back.Y * Ds[k], Z));
			RouteDwell.Add(Dwells[k]);
		}
	}
}

// ---------------------------------------------------------------------------
// Grading
// ---------------------------------------------------------------------------

void AGuardLastSeenFunctionalTest::OpenAlert(int32 SpotterIdx, const FVector& Spot, double Now)
{
	Alert.bLive = true;
	Alert.Spot = Spot;
	Alert.Time = Now;
	Alert.Spotter = SpotterIdx;

	for (FWatch& W : Watch)
	{
		const ACharacter* const C = W.Actor.Get();
		const FVector At = (C != nullptr) ? C->GetActorLocation() : W.Post;
		// THE DISCLOSED ALLOWANCE: the time its own pace needs to cover the distance in
		// a straight line, plus six seconds -- measured from where the watchman
		// actually is, which is the only reading fair to one the submission has
		// legitimately walked somewhere else.
		W.ArriveDeadline = Now + FVector::Dist2D(At, Spot) / double(W.Pace)
			+ kAllowS + kSlackS;
		W.MinDistToSpot = 1.0e9;
		W.bReachedSpot = false;
		W.ReachedAt = -1.0;
		W.HoldRun = 0.0;
		W.HoldBest = 0.0;
		W.bHoldSatisfied = false;
		W.HoldDeadline = -1.0;
		W.HomeDeadline = -1.0;
		W.bHomeSatisfied = false;
	}
	LegTwoReleaseAt = FMath::Max(Watch[0].ArriveDeadline, Watch[1].ArriveDeadline)
		+ kHoldS + kSlackS;
	UE_LOG(LogTemp, Display,
		TEXT("[t2-lastseen alert] leg=%d t=%.2f spot=(%.0f,%.0f) spotter=%s "
			 "firstSeen=(%.0f,%.0f) deadlines=%.1f/%.1f"),
		Leg + 1, Now, Spot.X, Spot.Y, *Watch[SpotterIdx].Name,
		Alert.HeroFirstSeenAt.X, Alert.HeroFirstSeenAt.Y,
		Watch[0].ArriveDeadline, Watch[1].ArriveDeadline);
}

bool AGuardLastSeenFunctionalTest::GradePerFrame(double Now)
{
	ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the player character stopped existing mid-run"));
		return false;
	}
	const FVector HeroAt = H->GetActorLocation();
	const FVector HeroEye = HeroEyePoint();

	// ---- the yard is the yard's ------------------------------------------------
	for (const FWall& W : Walls)
	{
		const AActor* const A = W.Actor.Get();
		if (A == nullptr || !A->GetActorLocation().Equals(W.StagedAt, 2.0))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NobodyMovedWhatWasNotTheirsToMove: a wall is at %s and the yard "
					 "put it at %s. The walls, the posts and the character are the "
					 "yard's, not yours"),
				A != nullptr ? *A->GetActorLocation().ToCompactString() : TEXT("(gone)"),
				*W.StagedAt.ToCompactString()));
			return false;
		}
	}
	if (!bStaging)
	{
		HeroTrailT.Add(Now);
		HeroTrailP.Add(HeroAt);
		while (HeroTrailT.Num() > 1 && Now - HeroTrailT[0] > kWalkWindowS * 1.2)
		{
			HeroTrailT.RemoveAt(0, EAllowShrinking::No);
			HeroTrailP.RemoveAt(0, EAllowShrinking::No);
		}
		if (HeroTrailT.Num() > 1 && Now - HeroTrailT[0] >= kWalkWindowS * 0.9)
		{
			const double Moved = FVector::Dist2D(HeroTrailP[0], HeroAt);
			if (Moved > kHeroWindowUu)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("NobodyMovedWhatWasNotTheirsToMove: the character covered "
						 "%.0f uu in %.2f s, which is far more than it can walk. It is "
						 "the yard's to drive, not yours to place"),
					Moved, Now - HeroTrailT[0]));
				return false;
			}
		}
	}

	// ---- per watchman ----------------------------------------------------------
	// Snapshotted BEFORE this frame's sight update: a watchman that wandered off its
	// post and only then caught sight is still judged for having wandered.
	const bool bSawBefore[2] = { Watch[0].bEverSawThisLeg, Watch[1].bEverSawThisLeg };
	int32 SeeingNow = 0;
	for (int32 i = 0; i < Watch.Num(); ++i)
	{
		FWatch& W = Watch[i];
		ACharacter* const C = W.Actor.Get();
		if (C == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheWatchmenAreAsTheYardBuiltThem: a watchman stopped existing "
					 "mid-run. The two standing out there are the two that must do "
					 "this work"));
			return false;
		}
		const FVector At = C->GetActorLocation();

		// pace and range are the yard's, and BeginPlay runs before this fixture does,
		// so re-read them every frame rather than trusting one early sample.
		const FFloatProperty* const PaceProp =
			FindFProperty<FFloatProperty>(C->GetClass(), TEXT("WalkPaceUuPerSecond"));
		const FFloatProperty* const RangeProp =
			FindFProperty<FFloatProperty>(C->GetClass(), TEXT("SightRangeUu"));
		const float NowPace = (PaceProp != nullptr)
			? PaceProp->GetPropertyValue_InContainer(C) : -1.0f;
		const float NowRange = (RangeProp != nullptr)
			? RangeProp->GetPropertyValue_InContainer(C) : -1.0f;
		if (!FMath::IsNearlyEqual(NowPace, W.Pace, 0.5f)
			|| !FMath::IsNearlyEqual(NowRange, W.Range, 0.5f))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheWatchmenAreAsTheYardBuiltThem: watchman %s now walks at %.0f "
					 "uu/s and sees %.0f uu, and the yard set %.0f and %.0f. Those two "
					 "numbers are the yard's; read them, do not change them"),
				*W.Name, NowPace, NowRange, W.Pace, W.Range));
			return false;
		}

		// it only ever walked
		W.TrailT.Add(Now);
		W.TrailP.Add(At);
		while (W.TrailT.Num() > 1 && Now - W.TrailT[0] > kWalkWindowS * 1.2)
		{
			W.TrailT.RemoveAt(0, EAllowShrinking::No);
			W.TrailP.RemoveAt(0, EAllowShrinking::No);
		}
		if (W.TrailT.Num() > 1 && Now - W.TrailT[0] >= kWalkWindowS * 0.9)
		{
			const double Moved = FVector::Dist2D(W.TrailP[0], At);
			const double Budget = double(W.Pace) * (Now - W.TrailT[0]) * kWalkFactor
				+ kWalkSlackUu;
			if (Moved > Budget)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheWatchmenOnlyEverWalked: watchman %s covered %.0f uu in "
						 "%.2f s and it walks at %.0f uu/s. A watchman is never "
						 "anywhere it did not walk to"),
					*W.Name, Moved, Now - W.TrailT[0], W.Pace));
				return false;
			}
		}

		// the fixture's own eyes
		const bool bSee = FixtureCanSee(W, HeroEye);
		if (bSee)
		{
			++SeeingNow;
			W.bEverSawThisLeg = true;
			bLegHadSighting = true;
			W.SeenHeroAt = HeroAt;
			W.bHasSeenHeroAt = true;
			W.BlindSince = -1.0;
			if (W.SightedSince < 0.0)
			{
				W.SightedSince = Now;
			}
			if (!Alert.bLive && Alert.HeroFirstSeenAt.IsZero())
			{
				Alert.HeroFirstSeenAt = HeroAt;
			}
		}
		else
		{
			if (W.BlindSince < 0.0)
			{
				W.BlindSince = Now;
			}
			W.SightedSince = -1.0;
		}

		// the sight true->false EDGE raises the alert this fixture grades against
		if (W.bSaw && !bSee && W.bHasSeenHeroAt)
		{
			OpenAlert(i, W.SeenHeroAt, Now);
		}
		W.bSaw = bSee;
	}

	// Nobody has been alerted yet: a watchman that has not seen the character itself
	// has no business anywhere but its post. Judged before the sighting count below so
	// the message names the thing that went wrong first.
	if (!Alert.bLive)
	{
		for (int32 i = 0; i < Watch.Num(); ++i)
		{
			const FWatch& W = Watch[i];
			const ACharacter* const C = W.Actor.Get();
			if (C == nullptr || bSawBefore[i])
			{
				continue;
			}
			const double Off = FVector::Dist2D(C->GetActorLocation(), W.Post);
			if (Off > kHomeUu)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheOtherWatchmanStayedPutUntilItWasTold: watchman %s is "
						 "%.0f uu off its post on leg %d and it has neither seen the "
						 "character nor been told anything. The other watchman still "
						 "has them in view; it is told when sight is LOST, not when "
						 "the character is first spotted"), *W.Name, Off, Leg + 1));
				return false;
			}
		}
	}

	// Exactly one watchman may have the character in view the first time anybody does:
	// the yard is built so the other one cannot reach that lane with its own range.
	if (bLegHadSighting && !bFirstSightChecked)
	{
		bFirstSightChecked = true;
		if (SeeingNow != 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheWatchmenAreAsTheYardBuiltThem: %d watchmen had the character "
					 "in view the first moment anybody did, and this yard is built so "
					 "that exactly one can reach that lane with its own sight range"),
				SeeingNow));
			return false;
		}
	}

	if (!Alert.bLive)
	{
		return true;
	}

	// ---- everything below is judged against the alert in force -----------------
	for (int32 i = 0; i < Watch.Num(); ++i)
	{
		FWatch& W = Watch[i];
		const ACharacter* const C = W.Actor.Get();
		const FVector At = C->GetActorLocation();
		const double ToSpot = FVector::Dist2D(At, Alert.Spot);
		const double ToHero = FVector::Dist2D(At, HeroAt);
		const bool bSee = W.bSaw;

		W.MinDistToSpot = FMath::Min(W.MinDistToSpot, ToSpot);

		// went to where it last saw them / the radio carried the place
		if (!W.bReachedSpot && ToSpot <= kArriveUu)
		{
			W.bReachedSpot = true;
			W.ReachedAt = Now;
			W.HoldDeadline = Now + kHoldS + kSlackS + 2.0;
		}
		if (!W.bReachedSpot && Now > W.ArriveDeadline)
		{
			if (i == Alert.Spotter)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("WentToWhereItLastSawYou: the watchman that lost sight of the "
						 "character never went to the spot where it last saw them. "
						 "Last seen at (%.0f, %.0f); %s got no closer than %.0f uu "
						 "(four metres counts as arriving) by t=%.1fs. It first "
						 "spotted them at (%.0f, %.0f) and they are now at (%.0f, "
						 "%.0f) -- the spot is neither of those"),
					Alert.Spot.X, Alert.Spot.Y, *W.Name, W.MinDistToSpot,
					W.ArriveDeadline, Alert.HeroFirstSeenAt.X, Alert.HeroFirstSeenAt.Y,
					HeroAt.X, HeroAt.Y));
			}
			else
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheRadioCarriedThePlaceNotThePerson: the watchman that never "
						 "saw anything never reached the spot it was told about. "
						 "Reported spot (%.0f, %.0f); %s got no closer than %.0f uu by "
						 "t=%.1fs. The character is at (%.0f, %.0f) and the watchman "
						 "that called it in was at (%.0f, %.0f) -- it was told a "
						 "place, not a person and not a caller"),
					Alert.Spot.X, Alert.Spot.Y, *W.Name, W.MinDistToSpot,
					W.ArriveDeadline, HeroAt.X, HeroAt.Y,
					Watch[Alert.Spotter].Actor.IsValid()
						? Watch[Alert.Spotter].Actor->GetActorLocation().X : 0.0,
					Watch[Alert.Spotter].Actor.IsValid()
						? Watch[Alert.Spotter].Actor->GetActorLocation().Y : 0.0));
			}
			return false;
		}

		// searched, then went back to its post -- graded on leg 1, where nothing
		// interrupts it. Leg 2's search is cut short by a genuine re-acquisition,
		// which is what the prompt says should happen.
		if (W.bReachedSpot && !W.bHoldSatisfied)
		{
			if (ToSpot <= kHoldUu && !bSee)
			{
				W.HoldRun += GetWorld()->GetDeltaSeconds();
				W.HoldBest = FMath::Max(W.HoldBest, W.HoldRun);
			}
			else
			{
				W.HoldRun = 0.0;
			}
			if (W.HoldRun >= kHoldS)
			{
				W.bHoldSatisfied = true;
				W.HomeDeadline = Now + FVector::Dist2D(Alert.Spot, W.Post) / double(W.Pace)
					+ kAllowS + kSlackS;
			}
			else if (Leg == 0 && !bSee && Now > W.HoldDeadline)
			{
				// !bSee, because the prompt says sight ends a search -- a watchman that
				// has the character in front of it is not owed six seconds of standing.
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("SearchedThenWentBackToItsPost: watchman %s reached the "
						 "last-seen spot at t=%.1fs and then held within seven metres "
						 "of it for only %.1f s of the six it owes. A give-up clock "
						 "that starts when sight is lost has already run out by the "
						 "time the watchman gets there"),
					*W.Name, W.ReachedAt, W.HoldBest));
				return false;
			}
		}
		if (Leg == 0 && W.bHoldSatisfied && !W.bHomeSatisfied)
		{
			if (FVector::Dist2D(At, W.Post) <= kHomeUu)
			{
				W.bHomeSatisfied = true;
			}
			else if (Now > W.HomeDeadline)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("SearchedThenWentBackToItsPost: watchman %s searched the "
						 "last-seen spot and never went home. It is %.0f uu from its "
						 "post at t=%.1fs, and three metres is standing on it. A "
						 "watchman that arrives and simply stops is still standing "
						 "there when the yard closes"),
					*W.Name, FVector::Dist2D(At, W.Post), Now));
				return false;
			}
		}
		if (Leg == 1 && W.bHoldSatisfied && !W.bHomeSatisfied
			&& FVector::Dist2D(At, W.Post) <= kHomeUu)
		{
			W.bHomeSatisfied = true;
		}

		// nobody creeps up on what they cannot see
		if (!bSee && W.BlindSince >= 0.0 && (Now - W.BlindSince) >= kBlindGraceS
			&& ToSpot > kBlindFloorUu && ToHero < kBlindFloorUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NeverCreptUpOnWhatItCouldNotSee: watchman %s is %.0f uu from the "
					 "character and has not been able to see them for %.1f s. It is "
					 "%.0f uu from the spot it was told about, so it is not searching "
					 "it -- it is homing in on somebody it cannot see. The character "
					 "is at (%.0f, %.0f) and the spot is (%.0f, %.0f)"),
				*W.Name, ToHero, Now - W.BlindSince, ToSpot,
				HeroAt.X, HeroAt.Y, Alert.Spot.X, Alert.Spot.Y));
			return false;
		}

		// sight beats whatever it was doing
		const bool bLongStand = bHeroStanding && RouteDwell.IsValidIndex(Waypoint)
			&& RouteDwell[Waypoint] >= 10.0;
		if (bSee && bLongStand && W.SightedSince >= 0.0
			&& (Now - W.SightedSince) >= kUnbrokenS && !W.bChaseArmed
			&& !W.bChaseSatisfied)
		{
			W.bChaseArmed = true;
			W.bEverChaseArmed = true;
			W.ChaseGapAtArm = ToHero;
			W.ChaseBest = ToHero;
			W.ChaseDeadline = Now + ToHero / double(W.Pace) + kAllowS + kSlackS;
		}
		if (W.bChaseArmed)
		{
			W.ChaseBest = FMath::Min(W.ChaseBest, ToHero);
			if (W.ChaseBest <= kCloseUu)
			{
				W.bChaseArmed = false;
				W.bChaseSatisfied = true;
			}
			else if (!bSee || !bHeroStanding)
			{
				W.bChaseArmed = false;      // it lost them, or they moved off; not its fault
			}
			else if (Now > W.ChaseDeadline)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("SightWinsOverWhateverItWasDoing: watchman %s had the "
						 "character in unbroken sight, standing in the open %.0f uu "
						 "away, and by t=%.1fs had closed no further than %.0f uu. "
						 "Five metres, whatever it was in the middle of: standing its "
						 "post, walking somewhere, searching, or trudging home"),
					*W.Name, W.ChaseGapAtArm, W.ChaseDeadline, W.ChaseBest));
				return false;
			}
		}
	}
	return true;
}

bool AGuardLastSeenFunctionalTest::GradeFinalTallies(double Now, bool bAtSentinel)
{
	if (!bLegTwoDone)
	{
		if (!bAtSentinel)
		{
			return false;
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardRanBothLegs: the yard never finished its second leg (leg %d, "
				 "stop %d of %d at t=%.0fs). It runs the whole thing twice, with the "
				 "other watchman doing the seeing and the walls somewhere else, and "
				 "nothing has been proved until both have run"),
			Leg + 1, Waypoint, Route.Num(), Now));
		return false;
	}

	bool bAnyChase = false;
	for (const FWatch& W : Watch)
	{
		bAnyChase = bAnyChase || W.bEverChaseArmed;
	}
	if (!bAnyChase)
	{
		if (!bAtSentinel)
		{
			return false;
		}
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("SightWinsOverWhateverItWasDoing: the character walked back out of "
				 "hiding and stood still in the open, three times over, and neither "
				 "watchman ever had it in sight for two unbroken seconds. Both of them "
				 "were somewhere the yard never sent them"));
		return false;
	}
	return true;
}

void AGuardLastSeenFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	FString S;
	for (const FWatch& W : Watch)
	{
		const ACharacter* const C = W.Actor.Get();
		const FVector At = (C != nullptr) ? C->GetActorLocation() : FVector::ZeroVector;
		S += FString::Printf(TEXT("%s[at(%.0f,%.0f) see%d spot%.0f hold%.1f home%d] "),
			*W.Name, At.X, At.Y, W.bSaw ? 1 : 0, W.MinDistToSpot, W.HoldBest,
			W.bHomeSatisfied ? 1 : 0);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-lastseen calib] cp%d t=%.2f leg=%d wp=%d hero=(%.0f,%.0f) "
			 "alert=%d spot=(%.0f,%.0f) %s"),
		Index, Now, Leg + 1, Waypoint, H.X, H.Y, Alert.bLive ? 1 : 0,
		Alert.Spot.X, Alert.Spot.Y, *S);
}

void AGuardLastSeenFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bDone || !IsRunning() || !Hero.IsValid() || Watch.Num() != 2)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = (World != nullptr) ? double(World->GetTimeSeconds()) : 0.0;

	if (!GradePerFrame(Now))
	{
		return;
	}

	DriveHero(Now);

	if (Waypoint >= Route.Num())
	{
		if (Leg == 0)
		{
			Leg = 1;
			StageLeg(1);
		}
		else if (!bLegTwoDone)
		{
			bLegTwoDone = true;
		}
	}

	// The drive is over and every tally is in: end here rather than burning the wall
	// clock to the sentinel. The tallies are the SAME function the sentinel calls, so
	// nothing that would have been judged there is skipped.
	if (bLegTwoDone && GradeFinalTallies(Now, /*bAtSentinel=*/false))
	{
		bDone = true;
		FinishTest(EFunctionalTestResult::Succeeded,
			TEXT("Both legs ran: each watchman went to where it last saw the "
				 "character, searched it, went home, and the one that saw nothing "
				 "went to the place it was told about."));
	}
}

void AGuardLastSeenFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIdx)
	{
		return;
	}
	GradeFinalTallies(TimeSeconds, /*bAtSentinel=*/true);
}
