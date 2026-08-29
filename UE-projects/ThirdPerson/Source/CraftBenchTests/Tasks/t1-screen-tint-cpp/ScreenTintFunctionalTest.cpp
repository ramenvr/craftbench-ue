// Copyright CraftBench. All Rights Reserved.

#include "ScreenTintFunctionalTest.h"

#include "Components/PostProcessComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kTolerance = 0.12;      // "within 0.12 of the right value"
	constexpr double kSettleS = 0.4;         // "within 0.4 seconds of a change"

	// UNDISCLOSED: fixture clocking and staging.
	// Light: enough to kill single-frame noise, not enough to LAG. A heavier
	// filter made the fixture and a correct submission measure two different
	// speeds through a deceleration -- the fixture read 463 uu/s while the
	// character's own velocity said 333, and a perfectly correct answer failed
	// by the difference.
	constexpr double kSmoothTau = 0.06;
	constexpr double kStableFraction = 0.05;
	constexpr double kStillFraction = 0.05;
	constexpr double kFlatOutFraction = 0.85;
	/** The second leg runs on a different top speed. Not a round ratio, so a
	 *  submission cannot land on it by accident. */
	constexpr double kSecondLegSpeedScale = 0.52;
	constexpr double kLegTwoStartsAt = 25.0;
	constexpr int32 kSentinelIndex = 12;
}

AScreenTintFunctionalTest::AScreenTintFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

float AScreenTintFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	float Fallback) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name)
			: nullptr)
	{
		return P->GetPropertyValue_InContainer(A);
	}
	return Fallback;
}

bool AScreenTintFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Tints;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("ScreenTint")), Tints);
	if (Tints.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: %d actor(s) tagged ScreenTint, expected 1"),
			Tints.Num()));
		return false;
	}
	Tint = Tints[0];

	// THE SURFACE SWAP, and the whole reason a -bp leg can exist for this task.
	// A C++ agent edits the class the map already places, so the placed instance IS
	// their answer and nothing below fires. A Blueprint agent cannot place anything --
	// Content/Maps/ is deny-write -- so their subclass would never be instantiated and
	// the task would be unwinnable on that surface. The same shape the only working
	// pair uses for its pawn (ACraftBenchPawnFunctionalTest::ResolveAgentPawnClass:
	// native first, then Blueprint via the asset registry) applied to a placed prop:
	// if a Blueprint under /Game/Tasks/ derives from what the map placed, spawn THAT at
	// the placed transform, carry the tag over, and take the placed one out of the
	// world. Additive by construction -- with no such Blueprint present the -cpp leg
	// runs byte-identically to before.
	if (AActor* const FromBlueprint = SwapForGradedBlueprint(Tint.Get()))
	{
		Tint = FromBlueprint;
	}

	// The three numbers the effect works to, read off the supplied actor rather than
	// copied in here, so the two cannot drift apart.
	for (const TCHAR* Name : {TEXT("RestVignette"), TEXT("FullVignette"),
			TEXT("SuppliedFringe")})
	{
		if (FindFProperty<FFloatProperty>(Tint->GetClass(), Name) == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the screen actor does not expose %s as a "
					 "readable property, so the fixture cannot tell what the effect "
					 "is supposed to read"), Name));
			return false;
		}
	}
	RestVignette = ReadFloat(Tint.Get(), TEXT("RestVignette"), 0.0f);
	FullVignette = ReadFloat(Tint.Get(), TEXT("FullVignette"), 0.9f);
	SuppliedFringe = ReadFloat(Tint.Get(), TEXT("SuppliedFringe"), 0.6f);
	if (FMath::Abs(FullVignette - RestVignette) < 0.3f)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: rest %.2f and full %.2f are only %.2f apart; "
				 "an effect that barely moves cannot be graded against a %.2f "
				 "tolerance"),
			RestVignette, FullVignette, FMath::Abs(FullVignette - RestVignette),
			kTolerance));
		return false;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetCharacterMovement() == nullptr
		|| Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented, movement-driven "
				 "player character on the track"));
		return false;
	}
	FirstLegTopSpeed = Hero->GetCharacterMovement()->MaxWalkSpeed;
	TopSpeedNow = FirstLegTopSpeed;
	if (FirstLegTopSpeed < 100.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the character's top speed is %.0f uu/s"),
			FirstLegTopSpeed));
		return false;
	}
	LastHeroAt = Hero->GetActorLocation();
	return true;
}

void AScreenTintFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	// The last entry is a SENTINEL, far past the drive, because the base class ends
	// the test the moment the last scheduled checkpoint is sampled -- and the gates
	// that need both legs can only be judged after both legs have happened.
	SetCheckpointSchedule({3.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0, 33.0, 37.0, 41.0,
		45.0, 49.0, 120.0});
}

float AScreenTintFunctionalTest::ReadVignette() const
{
	if (!Tint.IsValid())
	{
		return 0.0f;
	}
	// Read the SETTING a viewer would see, off the component, not a flag on the actor.
	TArray<UPostProcessComponent*> Comps;
	const_cast<AActor*>(Tint.Get())->GetComponents<UPostProcessComponent>(Comps);
	for (const UPostProcessComponent* C : Comps)
	{
		if (C != nullptr)
		{
			return C->Settings.VignetteIntensity;
		}
	}
	return 0.0f;
}

float AScreenTintFunctionalTest::ReadFringe() const
{
	if (!Tint.IsValid())
	{
		return 0.0f;
	}
	TArray<UPostProcessComponent*> Comps;
	const_cast<AActor*>(Tint.Get())->GetComponents<UPostProcessComponent>(Comps);
	for (const UPostProcessComponent* C : Comps)
	{
		if (C != nullptr)
		{
			return C->Settings.SceneFringeIntensity;
		}
	}
	return 0.0f;
}

float AScreenTintFunctionalTest::Expected(double Fraction) const
{
	return RestVignette + float(FMath::Clamp(Fraction, 0.0, 1.0))
		* (FullVignette - RestVignette);
}

void AScreenTintFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || !Tint.IsValid() || DeltaSeconds <= 0.0f)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	// THE SECOND LEG RUNS ON A DIFFERENT TOP SPEED. This is the whole design: an
	// effect keyed to a constant tracks the first leg and is wrong by the ratio here.
	if (Leg == 0 && Now >= kLegTwoStartsAt)
	{
		Leg = 1;
		TopSpeedNow = FirstLegTopSpeed * kSecondLegSpeedScale;
		Hero->GetCharacterMovement()->MaxWalkSpeed = float(TopSpeedNow);
	}

	// HOW FAST IT IS ACTUALLY GOING. The character's own velocity -- which is derived
	// from real motion, so a submission cannot fake it by writing a number somewhere
	// -- and separately the distance it really covered, as a cross-check that the two
	// agree. Grading against the velocity is what lets the fixture and a correct
	// submission measure the SAME quantity; grading against a heavily smoothed
	// distance made them disagree through every deceleration.
	const FVector Here = Hero->GetActorLocation();
	const double Covered = FVector::Dist2D(Here, LastHeroAt) / DeltaSeconds;
	LastHeroAt = Here;
	const double Velocity = Hero->GetVelocity().Size2D();
	const double Alpha = FMath::Clamp(DeltaSeconds / kSmoothTau, 0.0, 1.0);
	SmoothedSpeed += (Velocity - SmoothedSpeed) * Alpha;
	// If the two ever disagree wildly the character is being teleported rather than
	// walked, and nothing downstream would mean anything.
	if (Velocity > 50.0 && Covered > 50.0
		&& FMath::Abs(Velocity - Covered) > 0.6 * Velocity)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the character reports %.0f uu/s but covered "
				 "%.0f uu/s of ground; it is not being walked"), Velocity, Covered));
		return;
	}
	const double Fraction = FMath::Clamp(SmoothedSpeed / TopSpeedNow, 0.0, 1.0);

	// Never judge during an acceleration ramp. The window is compared against the
	// fraction it OPENED at, not against the previous frame: under smooth
	// acceleration the per-frame change is a thousandth, so a frame-to-frame test
	// calls the entire ramp "stable" and grades an effect that is still legitimately
	// easing toward a speed the character has not reached yet.
	if (FMath::Abs(Fraction - FractionAtWindowStart) > kStableFraction)
	{
		StableSince = Now;
		FractionAtWindowStart = Fraction;
	}
	const bool bStable = (Now - StableSince) >= kSettleS;

	// Driven every frame, including the ones the gates skip: the walk is what the
	// gates are measuring, and pausing it while the speed settles would stop the
	// speed ever settling.
	DriveHero(Now);

	const float Vignette = ReadVignette();
	const float Fringe = ReadFringe();

	// THE CONTROL. The other setting is supplied and is not part of the task.
	if (FMath::Abs(Fringe - SuppliedFringe) > 0.02f)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheOtherSettingWasLeftAlone: the supplied colour-fringe setting "
				 "reads %.3f and was supplied at %.3f; only the vignette is yours to "
				 "drive"), Fringe, SuppliedFringe));
		return;
	}

	if (!bStable)
	{
		return;
	}

	const float Want = Expected(Fraction);
	if (FMath::Abs(Vignette - Want) > kTolerance)
	{
		// Diagnose the commonest wrong answer before failing it: an effect keyed to
		// the top speed the character had on the FIRST leg reads exactly this.
		FString Diagnosis;
		if (Leg > 0)
		{
			const double StaleFraction =
				FMath::Clamp(SmoothedSpeed / FirstLegTopSpeed, 0.0, 1.0);
			if (FMath::Abs(Vignette - Expected(StaleFraction)) <= kTolerance)
			{
				Diagnosis = FString::Printf(
					TEXT(" -- it reads exactly what it would if it were still "
						 "dividing by the %.0f uu/s top speed of the first leg, "
						 "rather than the %.0f uu/s it has now"),
					FirstLegTopSpeed, TopSpeedNow);
			}
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TintTracksHowFastYouAreMoving: on leg %d the character was moving "
				 "%.0f uu/s of a %.0f uu/s top speed (%.0f%%), so the effect should "
				 "read %.2f; it reads %.2f%s"),
			Leg + 1, SmoothedSpeed, TopSpeedNow, Fraction * 100.0, Want, Vignette,
			*Diagnosis));
		return;
	}

	if (Fraction >= kFlatOutFraction && Vignette >= FullVignette - kTolerance)
	{
		bLegSawFull[FMath::Clamp(Leg, 0, 1)] = true;
	}
	if (Fraction <= kStillFraction && Vignette <= RestVignette + kTolerance)
	{
		bLegSawStill[FMath::Clamp(Leg, 0, 1)] = true;
	}
}

void AScreenTintFunctionalTest::DriveHero(double Now)
{
	if (!Hero.IsValid())
	{
		return;
	}
	// Still, half pace, flat out, still -- then the same again after the top speed
	// changes, walking back the way it came so no teleport is needed. (A teleport
	// between legs is how the detour task buried its walker under the floor.)
	struct FPhase { double Until; double Scale; double Dir; };
	static const FPhase kPhases[] = {
		{ 4.0, 0.0,  1.0},   // leg 1: stand
		{12.0, 0.5,  1.0},   // leg 1: half pace
		{20.0, 1.0,  1.0},   // leg 1: flat out
		{25.0, 0.0,  1.0},   // leg 1: stand
		{29.0, 0.0, -1.0},   // leg 2: stand, on the new top speed
		{37.0, 0.5, -1.0},   // leg 2: half pace, back the way it came
		{45.0, 1.0, -1.0},   // leg 2: flat out
		{50.0, 0.0, -1.0},   // leg 2: stand
	};
	for (const FPhase& P : kPhases)
	{
		if (Now < P.Until)
		{
			if (P.Scale > 0.0)
			{
				Hero->AddMovementInput(FVector(P.Dir, 0.0, 0.0), float(P.Scale));
			}
			return;
		}
	}
}

void AScreenTintFunctionalTest::LogCalib(int32 Index, double Now) const
{
	UE_LOG(LogTemp, Display,
		TEXT("[t1-tint calib] cp%d t=%.2f leg=%d top=%.0f speed=%.0f frac=%.2f "
			 "want=%.2f got=%.2f fringe=%.2f full=%d/%d still=%d/%d"),
		Index, Now, Leg + 1, TopSpeedNow, SmoothedSpeed,
		TopSpeedNow > 0.0 ? SmoothedSpeed / TopSpeedNow : 0.0,
		Expected(TopSpeedNow > 0.0 ? SmoothedSpeed / TopSpeedNow : 0.0),
		ReadVignette(), ReadFringe(),
		bLegSawFull[0] ? 1 : 0, bLegSawFull[1] ? 1 : 0,
		bLegSawStill[0] ? 1 : 0, bLegSawStill[1] ? 1 : 0);
}

void AScreenTintFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}

	for (int32 i = 0; i < 2; ++i)
	{
		if (!bLegSawStill[i])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TintIsOffWhenYouStandStill: on leg %d the effect never read its "
					 "rest value of %.2f while the character was standing still"),
				i + 1, RestVignette));
			return;
		}
		if (!bLegSawFull[i])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TintReachesFullWhenYouRunFlatOut: on leg %d the effect never "
					 "reached its full value of %.2f while the character was running "
					 "at its top speed of %.0f uu/s"),
				i + 1, FullVignette,
				i == 0 ? FirstLegTopSpeed : FirstLegTopSpeed * kSecondLegSpeedScale));
			return;
		}
	}
	if (Leg < 1)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheTrackRanBothLegs: the run never reached the second leg, so the "
				 "top speed was never changed and nothing was proved about what the "
				 "effect divides by"));
		return;
	}
}
