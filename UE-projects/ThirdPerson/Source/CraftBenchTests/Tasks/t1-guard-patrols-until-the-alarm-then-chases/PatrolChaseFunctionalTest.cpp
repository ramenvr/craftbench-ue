// Copyright CraftBench. All Rights Reserved.

#include "PatrolChaseFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kQuietLineBandUu = 450.0;   // "stays on its line"
	constexpr double kQuietGapFloorUu = 900.0;   // "leaves the target alone"
	constexpr double kChaseClosesTo = 0.55;      // "more than halves the gap"

	// UNDISCLOSED: fixture clocking and tolerances.
	constexpr double kAlarmSettleS = 1.2;
	// Long enough that a guard which chased right up to the character has time to
	// WALK back to its line at patrol speed before the quiet rule is applied to it.
	// Measured on the reference: from where a chase leaves it, the guard is ~1136 uu
	// off its line, and it walks back toward a POST rather than straight at the line,
	// so it is still 490 uu out after 5 s and inside the band after 8. A settle that
	// expires while a correct guard is still legitimately walking home fails it for
	// being slow rather than wrong.
	constexpr double kQuietSettleS = 8.0;
	constexpr double kWaypointReachedCm = 110.0;
	constexpr double kDwellS = 10.0;
	/** How long the panel and the plate may disagree before that IS the verdict. */
	constexpr double kMismatchGraceS = 1.0;
	constexpr double kFacingToleranceDeg = 40.0;
	constexpr double kFacingFraction = 0.7;
	constexpr double kMinChaseSpellS = 4.0;
	constexpr double kDecoySlackUu = 300.0;
	constexpr double kPlateHalfUu = 120.0;
	// Deterministic, not random: a fixed nudge per post keeps the run reproducible
	// while making a submission that hard-codes where the posts stand read a stale
	// number.
	constexpr double kPostJitterCm = 80.0;
}

APatrolChaseFunctionalTest::APatrolChaseFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool APatrolChaseFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Guards, PostActors, Panels, Decoys;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("PatrolGuard")), Guards);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("PatrolPost")), PostActors);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("AlarmPanel")), Panels);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("DecoyFigure")), Decoys);

	if (Guards.Num() != 1 || PostActors.Num() != 2 || Panels.Num() != 1
		|| Decoys.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - "
				 "%d guard(s), %d post(s), %d panel(s), %d decoy(s); expected 1/2/1/1"),
			Guards.Num(), PostActors.Num(), Panels.Num(), Decoys.Num()));
		return false;
	}
	Guard = Guards[0];
	Panel = Panels[0];
	Decoy = Decoys[0];

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in "
				 "the yard"));
		return false;
	}
	// The alarm has to be READABLE THE WAY A REVIEWER READS IT, or nothing downstream
	// means anything. The panel's occupancy count is a plain private int with no
	// UPROPERTY, so reflection cannot see it -- and a fixture that silently read false
	// forever would fail every correct answer.
	{
		TArray<UPointLightComponent*> Lamps;
		Panel->GetComponents<UPointLightComponent>(Lamps);
		bool bFound = false;
		for (UPointLightComponent* L : Lamps)
		{
			if (L != nullptr && L->GetName() == TEXT("Lamp")) { bFound = true; }
		}
		if (!bFound)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the alarm panel has no Lamp component, so "
					 "the fixture cannot tell when it is sounding"));
			return false;
		}
	}

	// JITTER the posts. The prompt withholds their coordinates, so a submission keyed
	// on where they stand rather than on finding them reads a stale number.
	for (int32 i = 0; i < PostActors.Num(); ++i)
	{
		const double Sign = (i == 0) ? 1.0 : -1.0;
		PostActors[i]->SetActorLocation(PostActors[i]->GetActorLocation()
			+ FVector(Sign * kPostJitterCm * 0.5, Sign * kPostJitterCm, 0.0));
		Posts.Add(PostActors[i]);
		PostReached.Add(false);
	}
	PatrolLineX = (Posts[0]->GetActorLocation().X + Posts[1]->GetActorLocation().X)
		* 0.5;
	return true;
}

void APatrolChaseFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}

	const FVector Hero0 = Hero->GetActorLocation();
	// The plate is a component of the panel, so its world position is read off the
	// panel's transform rather than assumed from the panel's own location.
	const FVector PanelAt = Panel->GetActorLocation();
	const FVector PanelFacing = Panel->GetActorForwardVector().GetSafeNormal2D();
	PlateStand = PanelAt + PanelFacing * 300.0;
	PlateStand.Z = Hero0.Z;
	// Far enough from the patrol line that a guard obeying the quiet rule cannot be
	// anywhere near it, and outside the alert range the guard is configured with.
	// Lined up with the PLATE, not with the board the plate hangs off. The board is
	// deliberately off to one side; the walk has to run through the trigger.
	WaitSpot = FVector(PatrolLineX + 3000.0, PlateStand.Y, Hero0.Z);

	Route = {WaitSpot, PlateStand, WaitSpot, PlateStand, WaitSpot};
	StartDecoyGap = FVector::Dist2D(Guard->GetActorLocation(),
		Decoy->GetActorLocation());

	// The last entry is a SENTINEL, far past the end of the drive. Without it the base
	// class ends the test the moment the last real checkpoint is sampled, and a gate
	// that hangs off the second alarm would never be reached.
	SetCheckpointSchedule({2.0, 5.0, 8.0, 11.0, 14.0, 17.0, 20.0, 23.0, 26.0, 29.0,
		32.0, 35.0, 38.0, 41.0, 44.0, 47.0, 50.0, 53.0, 56.0, 59.0, 62.0, 150.0});
}

bool APatrolChaseFunctionalTest::HeroOnPlate() const
{
	if (!Hero.IsValid())
	{
		return false;
	}
	const FVector H = Hero->GetActorLocation();
	return FMath::Abs(H.X - PlateStand.X) <= kPlateHalfUu
		&& FMath::Abs(H.Y - PlateStand.Y) <= kPlateHalfUu;
}

bool APatrolChaseFunctionalTest::ReadRinging() const
{
	// THE LAMP, not a flag. The yard asks the panel to go red, and that is what a
	// reviewer sees; a counter saying so is not the thing -- and this panel's counter
	// has no UPROPERTY, so reflection would read nothing at all.
	if (!Panel.IsValid())
	{
		return false;
	}
	TArray<UPointLightComponent*> Lamps;
	Panel->GetComponents<UPointLightComponent>(Lamps);
	for (UPointLightComponent* L : Lamps)
	{
		if (L != nullptr && L->GetName() == TEXT("Lamp"))
		{
			return L->IsVisible() && !L->bHiddenInGame && L->Intensity > 0.0f;
		}
	}
	return false;
}

double APatrolChaseFunctionalTest::GapToHero() const
{
	return (Guard.IsValid() && Hero.IsValid())
		? FVector::Dist2D(Guard->GetActorLocation(), Hero->GetActorLocation())
		: 0.0;
}

void APatrolChaseFunctionalTest::DriveHero(double Now)
{
	if (!Route.IsValidIndex(Waypoint) || !Hero.IsValid())
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Route[Waypoint];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointReachedCm)
	{
		// STAND here. The alarm is a state, not an event: the guard needs long enough
		// to actually close the gap, and the quiet rule needs long enough to be more
		// than the tail of a chase.
		if (DwellUntil < 0.0) { DwellUntil = Now + kDwellS; }
		else if (Now >= DwellUntil) { ++Waypoint; DwellUntil = -1.0; }
	}
	else
	{
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
	}
}

void APatrolChaseFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || !Guard.IsValid() || !Panel.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	// THE ALARM, read from the panel that a reviewer watches. Its ground truth is
	// whether the character is standing on the plate, computed here.
	const bool bRinging = ReadRinging();
	const bool bShouldRing = HeroOnPlate();

	if (!bWasRinging && bRinging)
	{
		FAlarm A;
		A.StartedAt = Now;
		A.StartGap = GapToHero();
		A.BestGap = A.StartGap;
		Alarms.Add(A);
	}
	else if (bWasRinging && !bRinging)
	{
		if (Alarms.Num() > 0) { Alarms.Last().EndedAt = Now; }
		QuietSince = Now;
	}
	bWasRinging = bRinging;

	// The alarm must be the SUPPLIED alarm. A submission that drives the panel from
	// its own sensing has replaced the trigger the task is about. Judged on how long
	// they disagree, never on one frame: the plate's overlap and the fixture's own box
	// test flip on adjacent frames at the boundary, and one of those is not a verdict.
	if (bRinging != bShouldRing)
	{
		if (MismatchSince < 0.0) { MismatchSince = Now; }
		else if (Now - MismatchSince > kMismatchGraceS)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("AlarmMatchesThePlate: the panel said %s for %.1f s while the "
					 "character was %s the plate; the alarm is the supplied plate, "
					 "not something a submission drives"),
				bRinging ? TEXT("ringing") : TEXT("quiet"), Now - MismatchSince,
				bShouldRing ? TEXT("on") : TEXT("off")));
			return;
		}
	}
	else
	{
		MismatchSince = -1.0;
	}

	const FVector G = Guard->GetActorLocation();
	const double Gap = GapToHero();

	// Reaching a post, at any time. Which posts and WHEN both matter.
	for (int32 i = 0; i < Posts.Num(); ++i)
	{
		if (Posts[i].IsValid()
			&& FVector::Dist2D(G, Posts[i]->GetActorLocation()) <= 220.0)
		{
			PostReached[i] = true;
			if (Alarms.Num() == 0) { bReachedAPostBeforeFirstAlarm = true; }
			else if (Alarms[0].EndedAt > 0.0) { bReachedAPostAfterFirstAlarm = true; }
		}
	}

	// THE DECOY. It is parked outside the guard's alert range and is never a target;
	// a guard that drifts toward it is chasing whatever is nearest rather than what
	// the alarm is about.
	if (Decoy.IsValid())
	{
		const double DecoyGap = FVector::Dist2D(G, Decoy->GetActorLocation());
		if (DecoyGap < StartDecoyGap - kDecoySlackUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NeverApproachesTheOtherFigure: the guard closed on the second "
					 "figure (%.0f uu, from %.0f at the start); it is parked outside "
					 "the guard's alert range and is never the target"),
				DecoyGap, StartDecoyGap));
			return;
		}
	}

	if (bRinging)
	{
		FAlarm& A = Alarms.Last();
		if (Now - A.StartedAt >= kAlarmSettleS)
		{
			A.BestGap = FMath::Min(A.BestGap, Gap);
			++A.Samples;
			const FVector ToHero =
				(Hero->GetActorLocation() - G).GetSafeNormal2D();
			const FVector Facing = Guard->GetActorForwardVector().GetSafeNormal2D();
			const double AngleDeg = FMath::RadiansToDegrees(FMath::Acos(
				FMath::Clamp(FVector::DotProduct(Facing, ToHero), -1.0, 1.0)));
			if (AngleDeg <= kFacingToleranceDeg) { ++A.Facing; }
		}
	}
	else if (Now - QuietSince >= kQuietSettleS)
	{
		// THE RESTORED GATE. With the alarm quiet the guard belongs on its line and
		// nowhere near the target. This is the assertion a guard that charges from
		// frame one fails, and the whole reason the alarm is measurable at all.
		const double OffLine = FMath::Abs(G.X - PatrolLineX);
		if (OffLine > kQuietLineBandUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("StaysOnPatrolWhileTargetFar: with the alarm quiet the guard was "
					 "%.0f uu off its line (allowed %.0f); it is supposed to be "
					 "pacing between the posts"),
				OffLine, kQuietLineBandUu));
			return;
		}
		if (Gap < kQuietGapFloorUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("StaysOnPatrolWhileTargetFar: with the alarm quiet the guard "
					 "came within %.0f uu of the character (floor %.0f); nothing has "
					 "called it, so it must leave the target alone"),
				Gap, kQuietGapFloorUu));
			return;
		}
	}

	DriveHero(Now);
}

void APatrolChaseFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector G = Guard.IsValid() ? Guard->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t1-patrol calib] cp%d t=%.2f ring=%d offline=%.0f gap=%.0f "
			 "alarms=%d posts=%d/%d wp=%d"),
		Index, Now, bWasRinging ? 1 : 0, FMath::Abs(G.X - PatrolLineX), GapToHero(),
		Alarms.Num(),
		(PostReached.Num() > 0 && PostReached[0] ? 1 : 0)
			+ (PostReached.Num() > 1 && PostReached[1] ? 1 : 0),
		PostReached.Num(), Waypoint);
}

void APatrolChaseFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	// Everything below is judged once, at the sentinel, when the whole drive is done.
	if (CheckpointIndex + 1 < 22)
	{
		return;
	}

	int32 Qualified = 0;
	for (int32 i = 0; i < Alarms.Num(); ++i)
	{
		const FAlarm& A = Alarms[i];
		const double Lasted = (A.EndedAt > 0.0 ? A.EndedAt : TimeSeconds) - A.StartedAt;
		if (Lasted < kMinChaseSpellS)
		{
			continue;   // too short to be a fair test of anything
		}
		if (A.BestGap > A.StartGap * kChaseClosesTo)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ChasesWhileTheAlarmRings: alarm %d rang for %.1f s and the "
					 "guard only got from %.0f uu to %.0f uu of the character "
					 "(needed %.0f); it is supposed to abandon the route and go "
					 "after them"),
				i + 1, Lasted, A.StartGap, A.BestGap, A.StartGap * kChaseClosesTo));
			return;
		}
		if (A.Samples > 0
			&& double(A.Facing) < double(A.Samples) * kFacingFraction)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ChasesWhileTheAlarmRings: during alarm %d the guard faced the "
					 "character on only %d of %d sampled frames; closing the distance "
					 "sideways or backwards is not going after somebody"),
				i + 1, A.Facing, A.Samples));
			return;
		}
		++Qualified;
	}

	if (Qualified < 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ChasesEveryTimeTheAlarmRings: %d of %d alarm(s) produced a chase; "
				 "the yard sounds the alarm twice and both must send the guard after "
				 "the character"),
			Qualified, Alarms.Num()));
		return;
	}
	if (!PostReached.Contains(true) || PostReached.Contains(false))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("PatrolsBetweenThePosts: the guard reached %d of %d posts; pacing "
				 "between them means visiting both"),
			(PostReached.Num() > 0 && PostReached[0] ? 1 : 0)
				+ (PostReached.Num() > 1 && PostReached[1] ? 1 : 0),
			PostReached.Num()));
		return;
	}
	if (!bReachedAPostBeforeFirstAlarm)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("PatrolsBetweenThePosts: the guard never reached a post before the "
				 "first alarm; it is supposed to be pacing the route already"));
		return;
	}
	if (!bReachedAPostAfterFirstAlarm)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("ResumesPatrolWhenTheAlarmClears: the guard never reached a post "
				 "again after the first alarm ended; going back to pacing the posts "
				 "is a separate claim from having paced them at the start"));
		return;
	}
	if (Waypoint + 1 < Route.Num())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRouteWasWalked: the character only reached %d of %d stops, so "
				 "the yard never finished sounding both alarms"),
			Waypoint, Route.Num()));
		return;
	}
}
