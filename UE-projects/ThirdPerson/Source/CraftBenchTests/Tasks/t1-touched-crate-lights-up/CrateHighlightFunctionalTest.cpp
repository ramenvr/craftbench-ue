// Copyright CraftBench. All Rights Reserved.

#include "CrateHighlightFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kSettleS = 0.5;         // "within half a second of a change"

	// UNDISCLOSED: fixture clocking and staging.
	constexpr double kInsideFactor = 0.7;    // a stop this far in is plainly inside
	constexpr double kOutsideFactor = 1.5;   // and this far out is plainly outside
	constexpr double kFarFactor = 3.0;
	constexpr double kMinStandoffUu = 130.0; // so the character never shoves a crate
	constexpr double kWaypointUu = 70.0;
	constexpr double kDwellS = 2.5;
	constexpr int32 kSentinelIndex = 40;
}

ACrateHighlightFunctionalTest::ACrateHighlightFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool ACrateHighlightFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("HighlightCrate")), Found);
	if (Found.Num() < 3)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %d actor(s) tagged HighlightCrate, expected "
				 "at least 3. Two crates is one comparison, and a submission can be "
				 "right about both by accident"), Found.Num()));
		return false;
	}
	// A stable order, so "crate 1" means the same crate however the level reports it.
	Found.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetName() < R.GetName();
	});

	for (AActor* A : Found)
	{
		const FFloatProperty* const P =
			FindFProperty<FFloatProperty>(A->GetClass(), TEXT("NoticeRadiusUu"));
		if (P == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a crate does not expose NoticeRadiusUu as "
					 "a readable property, so the fixture cannot tell how far that "
					 "crate is supposed to notice from"));
			return false;
		}
		FCrate C;
		C.Actor = A;
		C.Reach = P->GetPropertyValue_InContainer(A);
		if (C.Reach < 50.0f)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a crate notices from %.0f uu, which is "
					 "inside its own body"), C.Reach));
			return false;
		}
		TArray<UPointLightComponent*> Lamps;
		A->GetComponents<UPointLightComponent>(Lamps);
		if (Lamps.Num() == 0)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a crate has no lamp, so the fixture cannot "
					 "tell whether it has lit up"));
			return false;
		}
		Crates.Add(C);
	}

	// NO TWO REACHES MAY MATCH. Two crates a submission can treat as one is a crate
	// that has stopped testing anything.
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		for (int32 j = i + 1; j < Crates.Num(); ++j)
		{
			if (FMath::Abs(Crates[i].Reach - Crates[j].Reach) < 100.0f)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: crates %d and %d notice from %.0f uu "
						 "and %.0f uu, only %.0f apart; a single reach would be right "
						 "about both and the task would measure less than it claims"),
					i + 1, j + 1, Crates[i].Reach, Crates[j].Reach,
					FMath::Abs(Crates[i].Reach - Crates[j].Reach)));
				return false;
			}
		}
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
	return true;
}

FString ACrateHighlightFunctionalTest::ReachList() const
{
	FString S;
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		S += FString::Printf(TEXT("%s%.0f"), i ? TEXT("/") : TEXT(""), Crates[i].Reach);
	}
	return S;
}

bool ACrateHighlightFunctionalTest::ReadLit(const AActor* Crate) const
{
	// THE LAMP, not a flag. The yard asks a crate to light up, and that is what a
	// reviewer sees; a bool saying so is not the thing.
	if (Crate == nullptr)
	{
		return false;
	}
	TArray<UPointLightComponent*> Lamps;
	const_cast<AActor*>(Crate)->GetComponents<UPointLightComponent>(Lamps);
	for (const UPointLightComponent* L : Lamps)
	{
		if (L != nullptr)
		{
			return L->IsVisible() && !L->bHiddenInGame && L->Intensity > 0.0f;
		}
	}
	return false;
}

void ACrateHighlightFunctionalTest::StageLeg(int32 LegIndex)
{
	bStaging = true;
	if (LegIndex > 0 && Crates.Num() >= 3)
	{
		// THE CRATES CHANGE PLACES -- a cyclic shift by two, not a swap. With five
		// crates a swap leaves three of them where they were; a shift moves every
		// single one, so a submission keyed to where a crate stands rather than to
		// which crate it is gets every crate wrong from here on.
		TArray<FVector> Was;
		for (const FCrate& C : Crates)
		{
			Was.Add(C.Actor.IsValid() ? C.Actor->GetActorLocation()
									  : FVector::ZeroVector);
		}
		const int32 Shift = 2;
		for (int32 i = 0; i < Crates.Num(); ++i)
		{
			if (Crates[i].Actor.IsValid())
			{
				Crates[i].Actor->SetActorLocation(
					Was[(i + Shift) % Was.Num()], /*bSweep=*/false);
			}
		}
	}
	for (FCrate& C : Crates)
	{
		if (C.Actor.IsValid())
		{
			C.StagedAt = C.Actor->GetActorLocation();
		}
	}
	BuildRoute();
	Waypoint = 0;
	DwellUntil = -1.0;
	bStaging = false;
}

void ACrateHighlightFunctionalTest::BuildRoute()
{
	Route.Reset();
	if (Crates.Num() < 3 || !Hero.IsValid())
	{
		return;
	}
	const double Z = Hero->GetActorLocation().Z;
	const FVector A = Crates[0].StagedAt;
	const FVector B = Crates.Last().StagedAt;
	// Everything is laid out along the line joining the two crates, and every stop is
	// expressed as a multiple of the radius of the crate it is about -- so the route
	// re-derives itself after the swap and no stop ever sits on a boundary.
	const FVector Along = (B - A).GetSafeNormal2D();
	// A LANE TO ONE SIDE. The crates are solid and they sit on the line joining them,
	// so a route that steps from one crate's reach to the other's along that line
	// walks straight into them -- measured: the character jammed against the first
	// crate and the run never reached its second leg. Every stop is offset
	// perpendicular instead, which changes nothing about the distances that matter.
	const FVector Perp(-Along.Y, Along.X, 0.0);
	const double MaxReach = FMath::Max(Crates[0].Reach, Crates[1].Reach);
	const double Lane = FMath::Max(MaxReach * 1.5, 400.0);

	auto Beside = [&](const FVector& Centre, double Out)
	{
		const FVector P = Centre + Perp * FMath::Max(Out, kMinStandoffUu);
		return FVector(P.X, P.Y, Z);
	};
	auto FarFrom = [&](const FVector& Centre, const FVector& Dir)
	{
		const FVector P = Centre + Dir * (MaxReach * kFarFactor) + Perp * Lane;
		return FVector(P.X, P.Y, Z);
	};

	// Nothing lit, then a stop inside EVERY crate's own reach in turn, then away,
	// then back to the first one -- so every crate is judged both ways and the first
	// is judged twice. The transit between two crates is outside both, because the
	// level refuses to place rings that touch, so "goes out again" is exercised by
	// the walk itself rather than needing a stop of its own.
	Route.Add(FarFrom(A, -Along));
	for (const FCrate& C : Crates)
	{
		Route.Add(Beside(C.StagedAt, C.Reach * kInsideFactor));
	}
	Route.Add(FarFrom(A, -Along));
	Route.Add(Beside(Crates[0].StagedAt, Crates[0].Reach * kInsideFactor));
	Route.Add(FarFrom(B, Along));
}

void ACrateHighlightFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	StageLeg(0);

	// THE ROUTE MUST NOT WALK THROUGH A CRATE. They are solid; a route that does jams
	// the character and the run simply stops, which reads as the submission's fault.
	for (int32 s = 0; s + 1 < Route.Num(); ++s)
	{
		constexpr int32 kSamples = 40;
		for (int32 k = 0; k <= kSamples; ++k)
		{
			const FVector P = FMath::Lerp(Route[s], Route[s + 1],
				double(k) / double(kSamples));
			for (const FCrate& C : Crates)
			{
				if (FVector::Dist2D(P, C.StagedAt) < kMinStandoffUu)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walk from stop %d to stop %d "
							 "passes %.0f uu from a crate's centre; the character "
							 "would jam against it"),
						s, s + 1, FVector::Dist2D(P, C.StagedAt)));
					return;
				}
			}
		}
	}

	// Every stop must be plainly inside or plainly outside every crate's reach, or a
	// correct answer could round the wrong way and be failed for it.
	for (const FVector& Stop : Route)
	{
		for (const FCrate& C : Crates)
		{
			const double D = FVector::Dist2D(Stop, C.StagedAt);
			const double Margin = FMath::Abs(D - C.Reach);
			if (Margin < C.Reach * 0.2)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: a stop sits %.0f uu from a crate that "
						 "notices from %.0f uu - only %.0f uu of margin, so a correct "
						 "answer could round either way"), D, C.Reach, Margin));
				return;
			}
			if (D < kMinStandoffUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: a stop is %.0f uu from a crate's "
						 "centre; the character would be pushing it"), D));
				return;
			}
		}
	}

	// The last entry is a SENTINEL, far past both legs, because the base class ends
	// the test the moment the last scheduled checkpoint is sampled.
	// Five crates and two legs is a long walk. The sentinel is far past it.
	TArray<double> Schedule;
	for (int32 k = 1; k <= 40; ++k)
	{
		Schedule.Add(double(k) * 6.0);
	}
	Schedule.Add(420.0);
	SetCheckpointSchedule(Schedule);
}

void ACrateHighlightFunctionalTest::DriveHero(double Now)
{
	if (!Route.IsValidIndex(Waypoint) || !Hero.IsValid())
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Route[Waypoint];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointUu)
	{
		// STAND here. Every gate is about a state that has settled, and a route that
		// only passes through a spot never gives the crate a chance to be judged.
		if (DwellUntil < 0.0) { DwellUntil = Now + kDwellS; }
		else if (Now >= DwellUntil) { ++Waypoint; DwellUntil = -1.0; }
	}
	else
	{
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
	}
}

void ACrateHighlightFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || Crates.Num() < 3)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	const FVector HeroAt = Hero->GetActorLocation();

	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		FCrate& C = Crates[i];
		AActor* const A = C.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a crate stopped existing mid-run"));
			return;
		}
		// The crates are the yard's to place. A submission that moves one has changed
		// the question rather than answered it.
		if (!A->GetActorLocation().Equals(C.StagedAt, 2.0))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheCratesWereNotMoved: crate %d is at %s and the yard put it at "
					 "%s; where the crates stand is not yours to change"),
				i + 1, *A->GetActorLocation().ToCompactString(),
				*C.StagedAt.ToCompactString()));
			return;
		}

		// THE FIXTURE'S OWN ANSWER, from THIS crate's own reach.
		const double Distance = FVector::Dist2D(HeroAt, C.StagedAt);
		const bool bShould = Distance <= C.Reach;
		if (bShould != C.bLastTruth)
		{
			C.TruthChangedAt = Now;
			C.bLastTruth = bShould;
		}
		const bool bLit = ReadLit(A);
		if (bLit && !C.bWasLit)
		{
			++C.Spells;
		}
		C.bWasLit = bLit;

		if (Now - C.TruthChangedAt < kSettleS)
		{
			continue;   // it has half a second to catch up
		}
		if (bShould && !bLit)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("EachCrateLightsForItsOwnReach: crate %d notices from %.0f uu and "
					 "the character is %.0f uu away, and it is not lit. The %d crates "
					 "in this bay notice from %s - one reach does not fit them all"),
				i + 1, C.Reach, Distance, Crates.Num(), *ReachList()));
			return;
		}
		if (!bShould && bLit)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("EachCrateLightsForItsOwnReach: crate %d is lit with the "
					 "character %.0f uu away, and it only notices from %.0f uu. The "
					 "%d crates in this bay notice from %s - one reach does not fit "
					 "them all"),
				i + 1, Distance, C.Reach, Crates.Num(), *ReachList()));
			return;
		}
	}

	DriveHero(Now);

	// The route is walked once per leg; when it runs out, the yard swaps the crates
	// and walks it again.
	if (Waypoint >= Route.Num() && Leg == 0)
	{
		Leg = 1;
		StageLeg(1);
	}
}

void ACrateHighlightFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	FString S;
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		const double D = FVector::Dist2D(H, Crates[i].StagedAt);
		S += FString::Printf(TEXT("c%d[r%.0f d%.0f w%d l%d s%d] "),
			i + 1, Crates[i].Reach, D, D <= Crates[i].Reach ? 1 : 0,
			ReadLit(Crates[i].Actor.Get()) ? 1 : 0, Crates[i].Spells);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t1-crate calib] cp%d t=%.2f leg=%d wp=%d at=(%.0f,%.0f) %s"),
		Index, Now, Leg + 1, Waypoint, H.X, H.Y, *S);
}

void ACrateHighlightFunctionalTest::OnCheckpoint(int32 CheckpointIndex,
	double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}

	if (Leg < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardRanBothLegs: the run never reached the second leg (stop %d "
				 "of %d on leg 1), so the crates never swapped places and nothing was "
				 "proved about what a submission is keyed to"),
			Waypoint, Route.Num()));
		return;
	}
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		// Two legs, and crate 1 is walked up to twice per leg, so a crate that lights
		// once and stays lit -- or lights once and never again -- is caught here
		// rather than passing on the strength of its first spell.
		if (Crates[i].Spells < 2)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ACrateLightsUpAgainWhenYouComeBack: crate %d lit up %d time(s) "
					 "across both legs; the character walks away from it and comes "
					 "back, and it has to light again each time"),
				i + 1, Crates[i].Spells));
			return;
		}
	}
}
