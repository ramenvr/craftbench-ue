// Copyright CraftBench. All Rights Reserved.

#include "MudWadeFunctionalTest.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kCleanSpeedMin = 400.0;   // "400-600 units per second"
	constexpr double kCleanSpeedMax = 600.0;
	constexpr double kMudFractionMin = 0.30;   // "between 30% and 50%"
	constexpr double kMudFractionMax = 0.50;
	constexpr double kOffFractionMin = 0.85;   // "between 85% and 115%"
	constexpr double kOffFractionMax = 1.15;
	constexpr double kTwinFloorFraction = 0.70;
	constexpr double kSettleS = 0.5;           // "within half a second"
	const TCHAR* const kWadeName = TEXT("A_MudWade");

	// UNDISCLOSED: fixture geometry and clocking.
	constexpr double kWaypointReachedCm = 90.0;
	constexpr double kSpeedSmoothing = 0.15;
	constexpr double kMinSpeedToJudge = 30.0;  // do not judge a figure standing still
	constexpr double kSettleAfterStartS = 1.2; // skip the acceleration ramp
	// The control patrols, so it turns around; a turn is a real slowdown that the
	// FIXTURE caused, not the submission. Measured 2026-08-18: a correct answer
	// failed the control gate at 68% purely because the sample landed in a turn.
	constexpr double kAfterTurnGraceS = 1.5;
	// The prompt's half second is when the SPEED SETTING and the animation are back.
	// A measured ground speed also has to climb 200 -> 500 at the engine's own
	// acceleration (~0.15 s) and then work through this fixture's smoothing (~0.1 s).
	// Judging the measurement at 0.5 s failed a correct answer at 388 of 500 purely on
	// that lag (measured 2026-08-18). One-sided: a longer window can only let a
	// genuinely slow answer through, never fail a correct one.
	constexpr double kSpeedSettleS = 1.2;
	// ENTERING is judged at the half second the prompt states, and must be: at full
	// speed the figure clears a 400 cm patch in 0.8 s, so a 1.2 s window never lands
	// ON the patch at all and the substantive gate silently never runs -- the empty
	// submission then failed on a sentinel instead of on the thing it got wrong
	// (measured 2026-08-18). Entering is a deceleration (~0.15 s) plus this fixture's
	// smoothing (~0.1 s), so half a second is comfortable. Leaving is an
	// acceleration with no dwell limit, which is why it gets the longer window.
	constexpr double kEnterSettleS = 0.5;
}

AMudWadeFunctionalTest::AMudWadeFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool AMudWadeFunctionalTest::OnMud(ACharacter* Who) const
{
	AActor* const P = Patch.Get();
	if (P == nullptr || Who == nullptr)
	{
		return false;
	}
	TArray<UBoxComponent*> Boxes;
	P->GetComponents<UBoxComponent>(Boxes);
	const FVector Here = Who->GetActorLocation();
	for (UBoxComponent* B : Boxes)
	{
		if (B == nullptr)
		{
			continue;
		}
		const FVector Local = B->GetComponentTransform().InverseTransformPosition(Here);
		const FVector Ext = B->GetUnscaledBoxExtent();
		if (FMath::Abs(Local.X) <= Ext.X && FMath::Abs(Local.Y) <= Ext.Y)
		{
			return true;
		}
	}
	return false;
}

bool AMudWadeFunctionalTest::WadeDrivesPose(ACharacter* Who) const
{
	// Ask the MESH what is driving it, never the submission. Two legitimate routes
	// answer here: a single-node player pointed at the clip, and an animation
	// blueprint whose current asset is the clip.
	USkeletalMeshComponent* const Mesh = Who ? Who->GetMesh() : nullptr;
	if (Mesh == nullptr)
	{
		return false;
	}
	if (const UAnimSingleNodeInstance* const Single = Mesh->GetSingleNodeInstance())
	{
		const UAnimationAsset* const Asset = Single->GetAnimationAsset();
		if (Asset != nullptr && Asset->GetName().Contains(kWadeName))
		{
			return true;
		}
	}
	if (const UAnimInstance* const Anim = Mesh->GetAnimInstance())
	{
		if (const UAnimMontage* const Montage = Anim->GetCurrentActiveMontage())
		{
			if (Montage->GetName().Contains(kWadeName))
			{
				return true;
			}
		}
	}
	return false;
}

double AMudWadeFunctionalTest::GroundSpeed(ACharacter* Who) const
{
	return (Who == Hero.Get()) ? HeroSpeed : TwinSpeed;
}

bool AMudWadeFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Heroes, Patches;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MudHero")), Heroes);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MudPatch")), Patches);
	if (Patches.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the mud lane is not staged as authored - "
				 "expected one MudPatch, found %d"), Patches.Num()));
		return false;
	}
	if (Heroes.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the mud lane is not staged as authored - "
				 "expected two figures, found %d"), Heroes.Num()));
		return false;
	}
	// THE SURFACE SWAP, with re-possession. Both figures carry the MudHero tag and
	// both are instances of the ONE class the agent extends, so both are replaced
	// or neither is -- a swapped driven figure beside an unswapped twin would grade
	// the Blueprint against a C++ control, which measures nothing. One of the two
	// is the pawn the game mode spawned and the player is driving, so the swap has
	// to hand the controller its stand-in: destroying a possessed pawn without
	// re-possessing leaves every AddMovementInput going nowhere, which would read
	// as a submission that simply never moves.
	SwapAllForGradedBlueprintRepossessing(Heroes);
	// Self-check rather than trusting the swap.
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MudHero")), Heroes);
	if (Heroes.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the surface swap left %d figure(s) tagged "
				 "MudHero, not the two the lane is authored with"), Heroes.Num()));
		return false;
	}

	Patch = Patches[0];
	for (AActor* A : Heroes)
	{
		ACharacter* const C = Cast<ACharacter>(A);
		if (C == nullptr)
		{
			continue;
		}
		if (A->ActorHasTag(FName(TEXT("CleanLaneTwin")))) { Twin = C; }
		else { Hero = C; }
	}
	if (!Hero.IsValid() || !Twin.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the mud lane is not staged as authored - the "
				 "two figures are not one graded and one CleanLaneTwin"));
		return false;
	}
	for (ACharacter* C : {Hero.Get(), Twin.Get()})
	{
		if (C->GetMesh() == nullptr || C->GetMesh()->GetSkeletalMeshAsset() == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a figure is not visibly represented, so a "
					 "reviewer would see nothing"));
			return false;
		}
	}
	// The bystander is possessed on purpose: an unpossessed Character is inert.
	Twin->SpawnDefaultController();
	return true;
}

void AMudWadeFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}

	// Down the lane past the patch, back, and down again: two crossings, and the
	// prompt says the second must wade the same way as the first.
	const FVector Start = Hero->GetActorLocation();
	const FVector Mud = Patch->GetActorLocation();
	const FVector Beyond(Mud.X + 900.0, Start.Y, Start.Z);
	const FVector Before(Start.X, Start.Y, Start.Z);
	Route = {Beyond, Before, Beyond};

	TwinFrom = Twin->GetActorLocation();
	TwinTo = FVector(Beyond.X, TwinFrom.Y, TwinFrom.Z);

	TArray<double> Schedule;
	for (int32 i = 0; i < 16; ++i)
	{
		Schedule.Add(1.0 + 2.0 * i);
	}
	// The SENTINEL: the base declares success the moment the last scheduled
	// checkpoint is crossed, and this fixture grades off measured crossings.
	Schedule.Add(90.0);
	TimeLimitMargin = 6.0f;
	SetCheckpointSchedule(Schedule);
}

void AMudWadeFunctionalTest::LogCalib(int32 Index, double Now) const
{
	UE_LOG(LogTemp, Display,
		TEXT("[t1-mud calib] cp%d t=%.2f heroSpd=%.0f twinSpd=%.0f clean=%.0f "
			 "onMud=%d wade=%d crossings=%d waded=%d slowed=%d wp=%d"),
		Index, Now, HeroSpeed, TwinSpeed, CleanGroundSpeed,
		OnMud(Hero.Get()) ? 1 : 0, WadeDrivesPose(Hero.Get()) ? 1 : 0,
		Crossings, CrossingsWithWade, CrossingsSlowed, Waypoint);
}

void AMudWadeFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || !Twin.IsValid() || !Patch.IsValid()
		|| DeltaSeconds <= SMALL_NUMBER)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	// ---- MEASURED ground speed, smoothed so one hitching frame cannot decide ----
	const FVector HeroAt = Hero->GetActorLocation();
	const FVector TwinAt = Twin->GetActorLocation();
	if (bHavePrev)
	{
		const double H = FVector::Dist2D(HeroAt, HeroPrev) / DeltaSeconds;
		const double T = FVector::Dist2D(TwinAt, TwinPrev) / DeltaSeconds;
		HeroSpeed = HeroSpeed + (H - HeroSpeed) * kSpeedSmoothing;
		TwinSpeed = TwinSpeed + (T - TwinSpeed) * kSpeedSmoothing;
	}
	HeroPrev = HeroAt;
	TwinPrev = TwinAt;
	bHavePrev = true;

	const bool bNowOnMud = OnMud(Hero.Get());
	const bool bWading = WadeDrivesPose(Hero.Get());

	// The clean-ground reference is MEASURED on this run, before any mud is touched,
	// so every fraction below is relative to what this figure actually does rather
	// than to a number the submission could have changed.
	// Sampled only AFTER the figure is up to speed. Including the acceleration ramp
	// off the start dragged the average to 467 where the level's own number is 500,
	// which shifts every fraction below by 7% for no reason to do with the answer
	// (measured 2026-08-18).
	if (!bNowOnMud && Crossings == 0 && Now > kSettleAfterStartS
		&& Now > HeroTurnedAt + kAfterTurnGraceS && HeroSpeed > kMinSpeedToJudge)
	{
		CleanGroundSpeed = (CleanGroundSpeed * CleanSamples + HeroSpeed)
			/ static_cast<double>(CleanSamples + 1);
		++CleanSamples;
	}

	// ---- CROSSING BOOKKEEPING ----
	if (bNowOnMud && !bWasOnMud)
	{
		EnteredMudAt = Now;
		bWadeSeenThisCrossing = false;
		++Crossings;
	}
	if (!bNowOnMud && bWasOnMud)
	{
		LeftMudAt = Now;
		if (bWadeSeenThisCrossing) { ++CrossingsWithWade; }
	}
	if (bNowOnMud && bWading) { bWadeSeenThisCrossing = true; }

	// ---- THE GRADED FIGURE ----
	// The graded figure turns around at its waypoints, and a turn is a real slowdown
	// this FIXTURE caused. Judging through one read 388 of 500 on a correct answer
	// (measured 2026-08-18) -- the same artifact as the control's patrol turns.
	const bool bHeroSteady = Now > HeroTurnedAt + kAfterTurnGraceS;
	if (CleanSamples > 20 && HeroSpeed > kMinSpeedToJudge && bHeroSteady)
	{
		if (bNowOnMud && Now > EnteredMudAt + kEnterSettleS)
		{
			const double Fraction = HeroSpeed / FMath::Max(CleanGroundSpeed, 1.0);
			if (Fraction < kMudFractionMin || Fraction > kMudFractionMax)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("WadesSlowlyThroughTheMud: on the patch the figure measured "
						 "%.0f units per second against %.0f on clean ground (%.0f%%, "
						 "and the level asks for 30-50%%)"),
					HeroSpeed, CleanGroundSpeed, Fraction * 100.0));
				return;
			}
			if (!bWading)
			{
				FinishTest(EFunctionalTestResult::Failed,
					TEXT("TheWadeMotionDrivesThePose: the figure slowed down on the "
						 "patch but the supplied wade was not driving its pose"));
				return;
			}
		}
		if (!bNowOnMud && LeftMudAt > 0.0 && Now > LeftMudAt + kSpeedSettleS)
		{
			const double Fraction = HeroSpeed / FMath::Max(CleanGroundSpeed, 1.0);
			if (Fraction < kOffFractionMin || Fraction > kOffFractionMax)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("FullSpeedReturnsOffThePatch: off the patch the figure "
						 "measured %.0f units per second against %.0f on clean ground "
						 "(%.0f%%, and the level asks for 85-115%%)"),
					HeroSpeed, CleanGroundSpeed, Fraction * 100.0));
				return;
			}
			if (bWading)
			{
				FinishTest(EFunctionalTestResult::Failed,
					TEXT("TheOrdinaryWalkReturnsOffThePatch: the supplied wade was "
						 "still driving the pose after the figure left the patch"));
				return;
			}
		}
	}

	// ---- THE CONTROL FIGURE ----
	if (WadeDrivesPose(Twin.Get()))
	{
		bTwinEverWaded = true;
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheCleanLaneFigureIsUntouched: the wade motion drove the pose of "
				 "the figure that never goes near the mud"));
		return;
	}
	if (CleanSamples > 20 && TwinSpeed > kMinSpeedToJudge
		&& Now > TwinTurnedAt + kAfterTurnGraceS)
	{
		const double Fraction = TwinSpeed / FMath::Max(CleanGroundSpeed, 1.0);
		TwinSlowestFraction = FMath::Min(TwinSlowestFraction, Fraction);
		if (Fraction < kTwinFloorFraction)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheCleanLaneFigureIsUntouched: the figure on the clean lane "
					 "dropped to %.0f%% of the graded figure's clean-ground speed "
					 "(the level's floor is 70%%)"), Fraction * 100.0));
			return;
		}
	}

	// ---- DRIVE ----
	if (Route.IsValidIndex(Waypoint))
	{
		const FVector Target = Route[Waypoint];
		const FVector Flat(Target.X - HeroAt.X, Target.Y - HeroAt.Y, 0.0);
		if (Flat.Size2D() <= kWaypointReachedCm)
		{
			++Waypoint;
			HeroTurnedAt = Now;
		}
		else { Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f); }
	}
	// The control patrols its own clean lane, so its speed is a real measurement.
	{
		const FVector Target = bTwinOutbound ? TwinTo : TwinFrom;
		const FVector Flat(Target.X - TwinAt.X, Target.Y - TwinAt.Y, 0.0);
		if (Flat.Size2D() <= kWaypointReachedCm)
		{
			bTwinOutbound = !bTwinOutbound;
			TwinTurnedAt = Now;
		}
		else { Twin->AddMovementInput(Flat.GetSafeNormal(), 1.0f); }
	}

	bWasOnMud = bNowOnMud;
}

void AMudWadeFunctionalTest::OnCheckpoint(int32 Index, double TimeSeconds)
{
	if (!Hero.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : TimeSeconds;
	LogCalib(Index, Now);

	if (Index < 16)
	{
		return;
	}
	// The SENTINEL, and the gates that are vacuous unless their leg happened.
	if (CleanSamples < 20)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("WalksAtItsNormalTopSpeed: the figure never moved on clean ground, "
				 "so nothing about its speed was measured"));
		return;
	}
	if (CleanGroundSpeed < kCleanSpeedMin || CleanGroundSpeed > kCleanSpeedMax)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("WalksAtItsNormalTopSpeed: on clean ground the figure measured %.0f "
				 "units per second (the level asks for %.0f-%.0f)"),
			CleanGroundSpeed, kCleanSpeedMin, kCleanSpeedMax));
		return;
	}
	if (Crossings < 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("WadesAgainOnTheSecondCrossing: the figure crossed the patch %d "
				 "time(s), so wading twice was never measured"), Crossings));
		return;
	}
	if (CrossingsWithWade < 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("WadesAgainOnTheSecondCrossing: the wade drove the pose on %d of %d "
				 "crossings"), CrossingsWithWade, Crossings));
		return;
	}
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("the figure waded the patch at a measured 30-50 percent of its own "
			 "clean-ground speed with the supplied wade driving its pose, twice, and "
			 "came back to full speed and the ordinary walk each time"));
}
