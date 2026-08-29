// Copyright CraftBench. All Rights Reserved.

#include "MarkedGroundDetourFunctionalTest.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kBudgetFactor = 1.30;      // "no more than 1.3x the straight line"
	constexpr double kTripSeconds = 70.0;       // "within 70 seconds"

	// UNDISCLOSED: fixture clocking and tolerances.
	constexpr double kArriveUu = 150.0;
	constexpr double kChestUu = 90.0;
	/** Ignore sub-millimetre jitter when accumulating distance travelled. */
	constexpr double kMinStepUu = 0.5;
	constexpr int32 kSentinelIndex = 16;
}

AMarkedGroundDetourFunctionalTest::AMarkedGroundDetourFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool AMarkedGroundDetourFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Walkers, Grounds, Starts, Goals;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("DetourWalker")), Walkers);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MarkedGround")), Grounds);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("DetourStart")), Starts);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("DetourGoal")), Goals);

	if (Walkers.Num() != 1 || Grounds.Num() != 2 || Starts.Num() != 1
		|| Goals.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - "
				 "%d walker(s), %d marked patch(es), %d start(s), %d goal(s); "
				 "expected 1/2/1/1"),
			Walkers.Num(), Grounds.Num(), Starts.Num(), Goals.Num()));
		return false;
	}
	Walker = Walkers[0];
	StartMark = Starts[0];
	GoalMark = Goals[0];

	// Sort the patches by X so "patch 0" means the near one whichever order the level
	// reports its actors in -- the run has to be reproducible.
	Grounds.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetActorLocation().X < R.GetActorLocation().X;
	});

	for (AActor* G : Grounds)
	{
		FPatch P;
		P.Actor = G;
		TArray<UStaticMeshComponent*> Meshes;
		G->GetComponents<UStaticMeshComponent>(Meshes);
		FBox Foot(ForceInit);
		for (UStaticMeshComponent* M : Meshes)
		{
			if (M == nullptr)
			{
				continue;
			}
			const FBox Box = M->Bounds.GetBox();
			P.Strokes.Add(Box);
			Foot += Box;
		}
		if (FindFProperty<FBoolProperty>(G->GetClass(), TEXT("bOutOfBounds"))
			== nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a marked patch does not expose "
					 "bOutOfBounds as a readable property, so the fixture cannot tell "
					 "which patch it marked - it would read false forever and fail "
					 "every correct answer"));
			return false;
		}
		if (P.Strokes.Num() < 3)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a marked patch has %d painted stroke(s), "
					 "expected at least 3"), P.Strokes.Num()));
			return false;
		}
		// The lane a straight line takes across this patch, at chest height. Paint
		// does not block, so this must be CLEAR now and stay clear.
		const FVector Centre = Foot.GetCenter();
		P.LaneFrom = FVector(Foot.Min.X - 300.0, Centre.Y, Foot.Max.Z + kChestUu);
		P.LaneTo = FVector(Foot.Max.X + 300.0, Centre.Y, Foot.Max.Z + kChestUu);
		P.bLaneWasClear = LaneIsClear(P);
		if (!P.bLaneWasClear)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a marked patch already blocks a straight "
					 "line across it before play; the patches are paint, and the "
					 "not-made-solid check would measure nothing"));
			return false;
		}
		Patches.Add(P);
	}

	// The walker's own height, not the marker's. Measured on this task: the start
	// marker is a disc at z=6, the walker's capsule centre belongs at z=95, and
	// teleporting it to the marker put its feet 84 uu under the floor. Its Tick ran,
	// it planned a route, and it moved zero distance for the whole run.
	// THE LEVEL MUST SHIP WITH EXACTLY ONE PATCH MARKED. The fixture re-marks them
	// for each trip, so it is the only thing that would ever notice -- and a level
	// that ships unmarked is inert when a human presses Play: two identical patches,
	// nothing to avoid, and a correct walker strolling straight through both.
	// Measured 2026-08-18 by the owner playing it.
	{
		int32 Marked = 0;
		for (const FPatch& P : Patches)
		{
			Marked += ReadOutOfBounds(P.Actor.Get()) ? 1 : 0;
		}
		if (Marked != 1)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the level ships with %d of 2 patches "
					 "marked out of bounds, expected exactly 1. With none it is inert "
					 "until this fixture runs, so nobody playing it sees anything to "
					 "avoid"), Marked));
			return false;
		}
	}

	StartAt = StartMark->GetActorLocation();
	StartAt.Z = Walker->GetActorLocation().Z;
	GoalAt = GoalMark->GetActorLocation();
	StraightLine = FVector::Dist2D(StartAt, GoalAt);
	if (StraightLine < 1000.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: start and goal are only %.0f uu apart"),
			StraightLine));
		return false;
	}
	return true;
}

bool AMarkedGroundDetourFunctionalTest::CoversPoint(const FPatch& Patch,
	const FVector& P) const
{
	// The fixture's OWN answer, from the bounds it measured before play. It never
	// asks the patch, whose class the submission may edit.
	for (const FBox& Box : Patch.Strokes)
	{
		if (P.X >= Box.Min.X && P.X <= Box.Max.X
			&& P.Y >= Box.Min.Y && P.Y <= Box.Max.Y)
		{
			return true;
		}
	}
	return false;
}

bool AMarkedGroundDetourFunctionalTest::LaneIsClear(const FPatch& Patch) const
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(MarkedGroundLane), true);
	Params.AddIgnoredActor(this);
	if (Walker.IsValid())
	{
		Params.AddIgnoredActor(Walker.Get());
	}
	FHitResult Hit;
	return !World->LineTraceSingleByChannel(
		Hit, Patch.LaneFrom, Patch.LaneTo, ECC_Visibility, Params);
}

bool AMarkedGroundDetourFunctionalTest::ReadOutOfBounds(const AActor* Patch) const
{
	// The patch's flag, by reflection. It IS a UPROPERTY on purpose: the walker has
	// to be able to read which patch is out of bounds, and the yard has to be able to
	// check that nobody changed the answer. PrepareTest refuses to start if it cannot
	// be found, rather than reading false forever and failing every correct answer.
	if (const FBoolProperty* const P = Patch
			? FindFProperty<FBoolProperty>(Patch->GetClass(), TEXT("bOutOfBounds"))
			: nullptr)
	{
		return P->GetPropertyValue_InContainer(Patch);
	}
	return false;
}

void AMarkedGroundDetourFunctionalTest::ApplyTripStaging(int32 TripIndex)
{
	bStaging = true;
	const int32 Forbidden = TripIndex % 2;
	for (int32 i = 0; i < Patches.Num(); ++i)
	{
		AActor* const A = Patches[i].Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		if (UFunction* const Fn = A->FindFunction(FName(TEXT("SetOutOfBounds"))))
		{
			struct { bool bValue; } Args{i == Forbidden};
			A->ProcessEvent(Fn, &Args);
		}
	}
	if (AActor* const W = Walker.Get())
	{
		W->SetActorLocation(StartAt, /*bSweep=*/false);
		W->SetActorRotation((GoalAt - StartAt).GetSafeNormal2D().Rotation());
	}
	FTrip T;
	T.OutOfBoundsIndex = Forbidden;
	T.StartedAt = GetWorld() ? double(GetWorld()->GetTimeSeconds()) : 0.0;
	Trips.Add(T);
	LastWalkerAt = StartAt;
	bStaging = false;
}

void AMarkedGroundDetourFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	ApplyTripStaging(0);

	// The last entry is a SENTINEL, far past the end of both trips. Without it the
	// base class ends the test the moment the last real checkpoint is sampled, and
	// every gate that can only be judged once both trips are done would be skipped.
	SetCheckpointSchedule({5.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0,
		105.0, 115.0, 125.0, 135.0, 145.0, 155.0, 260.0});
}

void AMarkedGroundDetourFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Walker.IsValid() || Patches.Num() != 2
		|| !Trips.IsValidIndex(Trip))
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	FTrip& T = Trips[Trip];
	if (T.bArrived)
	{
		return;
	}

	// The marking must still say what the yard set it to. A submission that repaints
	// the patch has changed the question rather than answered it.
	for (int32 i = 0; i < Patches.Num(); ++i)
	{
		const bool bWant = (i == T.OutOfBoundsIndex);
		if (ReadOutOfBounds(Patches[i].Actor.Get()) != bWant)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheMarkingWasNotChanged: patch %d reads %s on trip %d and the "
					 "yard set it %s; which ground is off limits is the yard's to "
					 "say"),
				i, bWant ? TEXT("free") : TEXT("shut"), Trip + 1,
				bWant ? TEXT("shut") : TEXT("free")));
			return;
		}
	}

	// The paint must still be paint. A submission that walks a clean route by turning
	// the marked ground into a wall has solved a different problem.
	for (int32 i = 0; i < Patches.Num(); ++i)
	{
		if (Patches[i].bLaneWasClear && !LaneIsClear(Patches[i]))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheMarkedGroundWasNotMadeSolid: a straight line across patch %d "
					 "was clear before play and is blocked now; the marked ground is "
					 "paint and must stay walkable"), i));
			return;
		}
	}

	const FVector Here = Walker->GetActorLocation();
	const double Step = FVector::Dist2D(Here, LastWalkerAt);
	if (!bStaging && Step >= kMinStepUu)
	{
		T.Travelled += Step;
	}
	LastWalkerAt = Here;

	// THE GATE THE TASK IS ABOUT.
	if (CoversPoint(Patches[T.OutOfBoundsIndex], Here))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NeverStepsOnTheGroundThatIsOutOfBounds: on trip %d the walker stood "
				 "at (%.0f, %.0f), which is on the patch the yard marked out of "
				 "bounds"),
			Trip + 1, Here.X, Here.Y));
		return;
	}
	if (CoversPoint(Patches[1 - T.OutOfBoundsIndex], Here))
	{
		T.bSteppedOnAllowed = true;
	}

	if (T.Travelled > StraightLine * kBudgetFactor)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("StaysWithinTheDistanceBudget: on trip %d the walker has covered "
				 "%.0f uu against a budget of %.0f (%.2fx the %.0f uu straight line); "
				 "going the long way round both patches costs more than this"),
			Trip + 1, T.Travelled, StraightLine * kBudgetFactor, kBudgetFactor,
			StraightLine));
		return;
	}

	if (FVector::Dist2D(Here, GoalAt) <= kArriveUu)
	{
		T.bArrived = true;
		T.ArrivedAt = Now;
		if (Trip + 1 < 2)
		{
			++Trip;
			ApplyTripStaging(Trip);
		}
	}
}

void AMarkedGroundDetourFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector W = Walker.IsValid() ? Walker->GetActorLocation()
									   : FVector::ZeroVector;
	const FTrip* T = Trips.IsValidIndex(Trip) ? &Trips[Trip] : nullptr;
	UE_LOG(LogTemp, Display,
		TEXT("[t1-detour calib] cp%d t=%.2f trip=%d oob=%d at=(%.0f,%.0f) "
			 "gone=%.0f/%.0f togoal=%.0f allowed=%d arrived=%d"),
		Index, Now, Trip + 1, T ? T->OutOfBoundsIndex : -1, W.X, W.Y,
		T ? T->Travelled : 0.0, StraightLine * kBudgetFactor,
		FVector::Dist2D(W, GoalAt), T && T->bSteppedOnAllowed ? 1 : 0,
		T && T->bArrived ? 1 : 0);
}

void AMarkedGroundDetourFunctionalTest::OnCheckpoint(int32 CheckpointIndex,
	double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	// A trip that has run out of time ends the test where it stands, so the failure
	// names the trip rather than arriving at the sentinel as a bare "did not finish".
	if (Trips.IsValidIndex(Trip) && !Trips[Trip].bArrived
		&& TimeSeconds - Trips[Trip].StartedAt > kTripSeconds)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ReachesTheGoalOnBothTrips: trip %d ran for %.0f s without reaching "
				 "the goal (still %.0f uu away, %.0f uu covered); a route that keeps "
				 "clear of BOTH patches does not exist inside the budget, so a walker "
				 "that will not cross the allowed one gets stuck here"),
			Trip + 1, TimeSeconds - Trips[Trip].StartedAt,
			FVector::Dist2D(Walker.IsValid() ? Walker->GetActorLocation()
											 : FVector::ZeroVector, GoalAt),
			Trips[Trip].Travelled));
		return;
	}

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}

	if (Trips.Num() < 2 || !Trips[0].bArrived || !Trips[1].bArrived)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ReachesTheGoalOnBothTrips: %d of 2 trips finished; the yard swaps "
				 "which patch is out of bounds between them, so a route decided once "
				 "and reused arrives on the first and not the second"),
			(Trips.Num() > 0 && Trips[0].bArrived ? 1 : 0)
				+ (Trips.Num() > 1 && Trips[1].bArrived ? 1 : 0)));
		return;
	}
	for (int32 i = 0; i < Trips.Num(); ++i)
	{
		if (!Trips[i].bSteppedOnAllowed)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("CrossesTheGroundThatIsAllowed: on trip %d the walker reached the "
					 "goal without once setting foot on the patch it could cross. "
					 "Keeping off BOTH painted patches is not the task - the yard "
					 "paints two and only one of them is off limits"),
				i + 1));
			return;
		}
	}
}
