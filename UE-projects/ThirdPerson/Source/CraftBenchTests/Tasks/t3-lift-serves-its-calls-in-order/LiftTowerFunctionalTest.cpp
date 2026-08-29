// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.

#include "LiftTowerFunctionalTest.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// ------------------------------------------------------------ DISCLOSED numbers.
	// Every one of these appears in the prompt in plain words.
	constexpr double kLevelToleranceUu = 5.0;   // "within five centimetres"
	constexpr double kSpeedBand = 0.20;         // "within a fifth of that number"
	constexpr double kSignSettleS = 0.5;        // "half a second to catch up"

	// ------------------------------- UNDISCLOSED: clocking, staging and forgiveness.
	// Each of these can only ever forgive a correct answer, never fail one.
	// kOpenEps IS LOAD-BEARING AND IT IS NOT COSMETIC SLACK. The supplied door mechanism
	// asks each leaf for the exact end position, and USceneComponent drops a relative
	// move smaller than UE_KINDA_SMALL_NUMBER (SceneComponent.cpp:3315) -- so the last
	// sliver of the ramp is silently discarded and the leaves settle ~6e-5 uu short of
	// both ends. Measured 2026-08-19: separation 319.99988 rather than 320 at the open
	// end and 140.00011 rather than 140 at the shut end, i.e. a raw fraction of 0.9999993
	// and 5.9e-7. This fixture reads fully open / shut through this epsilon and is
	// therefore right either way; the SCAFFOLD now snaps in GetDoorOpenFraction, which is
	// the only reason `>= 1.0f` is a legal thing for a submission to write. Never narrow
	// this below that residual.
	constexpr double kOpenEps = 1.0e-3;         // fully open / shut, with float slack
	constexpr double kHoldSlackS = 0.15;
	constexpr double kMovedUu = 1.0;            // 3.3 uu is one frame of real travel
	constexpr double kSillJitterUu = 0.05;
	constexpr double kMinSegmentUu = 40.0;      // shorter than this is a correction
	constexpr double kSegmentGapS = 0.5;
	constexpr double kProgressUu = 30.0;
	constexpr double kProgressWindowS = 3.0;
	constexpr double kDistantCallUu = 20.0;
	constexpr double kRiderFeetUu = 60.0;
	constexpr double kRiderMarginUu = 30.0;
	constexpr double kSignLevelBandUu = 12.0;
	constexpr double kNearestMarginUu = 120.0;
	constexpr double kSignGraceS = 2.0;
	constexpr double kLampGraceS = 0.5;
	constexpr double kLampOutWindowS = 2.0;
	constexpr double kPadShrinkUu = 15.0;
	constexpr double kPadFeetUu = 80.0;
	constexpr double kWaypointUu = 70.0;
	constexpr double kStayPutUu = 2.0;

	// Staging. Landing 2 is put at these two fractions of the shaft, so the fixture
	// re-derives itself if the tower is ever rebuilt taller.
	constexpr double kStagedTwoFractionA = 0.6944;   // 1250 uu in the shipped 1800 shaft
	constexpr double kStagedTwoFractionB = 0.25;     //  450 uu
	constexpr double kMinShaftUu = 1200.0;
	constexpr double kMinStagedSpreadUu = 400.0;
	constexpr double kMinEvenSpacingGapUu = 100.0;
	constexpr double kRestageClearUu = 250.0;

	constexpr double kSentinelS = 240.0;
	constexpr int32 kSentinelIndex = 50;

	// EARLY CALIB, DELIBERATELY *NOT* CHECKPOINTS. Cost paid on 2026-08-19: the first
	// checkpoint is at 4.0 s, a run failed at t=3.37 s, and it produced a verdict and
	// NOT ONE diagnostic line -- the whole opening sequence had to be reconstructed by
	// hand. The drive's tightest moment is in the first four seconds, so log through it.
	//
	// These are emitted straight from Tick rather than added to the schedule ON PURPOSE:
	// the checkpoint INDEX is a public key (cameras.json's pie_timeline binds shots to
	// it, and kSentinelIndex is the last index), so inserting seven points at the front
	// would silently re-aim every camera shot and re-number the sentinel. A log line
	// owes nothing to either.
	constexpr double kEarlyCalibS[] = { 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5 };
	constexpr int32 kEarlyCalibCount = 7;

	// THE COLLECTIVE ANSWER to the seven presses this drive makes, given that every
	// press landed inside its stated window (each window is enforced as a named graded
	// FAIL, so this array is a constant and not a guess):
	//   leg 1 -- called 1, then 3 and 2 from inside while standing at landing 1, so up
	//            from landing 1 stopping at everything on the way: 1, 2, 3;
	//   leg 2 -- called 3, then 1 from inside, then 3 again with the car already below
	//            landing 3, then 2 with the car still above landing 2: down from
	//            landing 3 stopping at everything on the way, then round again: 3, 2, 1, 3.
	const int32 kExpectedOpenings[] = { 1, 2, 3, 3, 2, 1, 3 };
	constexpr int32 kExpectedOpeningCount = 7;

	bool ReadFloatProp(const AActor* Actor, const TCHAR* Name, float& Out)
	{
		const FFloatProperty* const P =
			FindFProperty<FFloatProperty>(Actor->GetClass(), Name);
		if (P == nullptr)
		{
			return false;
		}
		Out = P->GetPropertyValue_InContainer(Actor);
		return true;
	}

	bool ReadIntProp(const AActor* Actor, const TCHAR* Name, int32& Out)
	{
		const FIntProperty* const P =
			FindFProperty<FIntProperty>(Actor->GetClass(), Name);
		if (P == nullptr)
		{
			return false;
		}
		Out = P->GetPropertyValue_InContainer(Actor);
		return true;
	}
}

ALiftTowerFunctionalTest::ALiftTowerFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	// The shaft has to be put together BEFORE anybody's BeginPlay runs, or a submission
	// that reads the landing heights once at play would be reading the map's decoy and
	// the whole "ask the landing where its floor is" requirement would be a trap rather
	// than a requirement. OnWorldInitializedActors fires after PostInitializeComponents
	// and before placed-actor BeginPlay (the same seam SanityFunctionalTest uses).
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ALiftTowerFunctionalTest::OnWorldActorsInitialized);
}

// =====================================================================================
// staging
// =====================================================================================

void ALiftTowerFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bStaged || !StagingFault.IsEmpty() || Params.World != GetWorld())
	{
		return;
	}
	if (ResolveAndStage())
	{
		bStaged = true;
	}
}

bool ALiftTowerFunctionalTest::ResolveCar(AActor* Actor, FString& OutWhy)
{
	Car.Actor = Actor;
	UPrimitiveComponent* const Root = Cast<UPrimitiveComponent>(Actor->GetRootComponent());
	if (Root == nullptr)
	{
		OutWhy = TEXT("the car's root is not a primitive, so it has no floor to stand on");
		return false;
	}
	Car.Platform = Root;

	TArray<USceneComponent*> Scenes;
	Actor->GetComponents<USceneComponent>(Scenes);
	for (USceneComponent* const C : Scenes)
	{
		if (C == nullptr)
		{
			continue;
		}
		const FString N = C->GetName();
		if (N == TEXT("DoorLeftLeaf")) { Car.LeafLeft = Cast<UPrimitiveComponent>(C); }
		else if (N == TEXT("DoorRightLeaf")) { Car.LeafRight = Cast<UPrimitiveComponent>(C); }
		else if (N == TEXT("Pad1")) { Car.Pads[0] = Cast<UPrimitiveComponent>(C); }
		else if (N == TEXT("Pad2")) { Car.Pads[1] = Cast<UPrimitiveComponent>(C); }
		else if (N == TEXT("Pad3")) { Car.Pads[2] = Cast<UPrimitiveComponent>(C); }
		else if (N == TEXT("PadLamp1")) { Car.Lamps[0] = Cast<UPointLightComponent>(C); }
		else if (N == TEXT("PadLamp2")) { Car.Lamps[1] = Cast<UPointLightComponent>(C); }
		else if (N == TEXT("PadLamp3")) { Car.Lamps[2] = Cast<UPointLightComponent>(C); }
	}

	if (!ReadFloatProp(Actor, TEXT("TravelSpeedUuPerSecond"), Car.Speed)
		|| !ReadFloatProp(Actor, TEXT("DoorTravelSeconds"), Car.DoorTravel)
		|| !ReadFloatProp(Actor, TEXT("DoorHoldSeconds"), Car.DoorHold)
		|| !ReadFloatProp(Actor, TEXT("DoorShutSeparationUu"), Car.ShutSep)
		|| !ReadFloatProp(Actor, TEXT("DoorOpenSeparationUu"), Car.OpenSep))
	{
		OutWhy = TEXT("the car no longer carries its five readable numbers");
		return false;
	}
	// THE 0.5 s FLOOR IS THE STEP-OUT FLOOR, and it lives here so it lives in one
	// place. Car.DoorHold is the threshold BOTH TheDoorsHoldOpenLongEnoughToGetOut and
	// TheCarStandsStillLongEnoughToStepOut are measured against, so a tower built with a
	// hold shorter than half a second would be a tower nobody can get out of -- and this
	// refusal, not a constant buried in a gate, is what makes that impossible.
	if (Car.Speed < 20.0f || Car.DoorTravel < 0.2f || Car.DoorHold < 0.5f
		|| FMath::Abs(Car.OpenSep - Car.ShutSep) < 20.0f)
	{
		OutWhy = FString::Printf(
			TEXT("the car's numbers are unusable: %.1f uu/s, doors %.2f s, hold %.2f s, ")
			TEXT("leaves %.0f shut / %.0f open"),
			Car.Speed, Car.DoorTravel, Car.DoorHold, Car.ShutSep, Car.OpenSep);
		return false;
	}

	const FVector Loc = Actor->GetActorLocation();
	Car.StagedX = Loc.X;
	Car.StagedY = Loc.Y;
	return true;
}

bool ALiftTowerFunctionalTest::ResolveLanding(AActor* Actor, FLandingRef& Out, FString& OutWhy)
{
	Out.Actor = Actor;
	UPrimitiveComponent* const Root = Cast<UPrimitiveComponent>(Actor->GetRootComponent());
	if (Root == nullptr)
	{
		OutWhy = TEXT("a landing's root is not a primitive, so it has no deck");
		return false;
	}
	Out.Deck = Root;

	TArray<USceneComponent*> Scenes;
	Actor->GetComponents<USceneComponent>(Scenes);
	for (USceneComponent* const C : Scenes)
	{
		if (C == nullptr)
		{
			continue;
		}
		const FString N = C->GetName();
		if (N == TEXT("CallPad")) { Out.CallPad = Cast<UPrimitiveComponent>(C); }
		else if (N == TEXT("CallLamp")) { Out.CallLamp = Cast<UPointLightComponent>(C); }
		else if (N == TEXT("Readout")) { Out.Readout = Cast<UTextRenderComponent>(C); }
		else if (N == TEXT("Arrow")) { Out.Arrow = C; }
	}
	if (!ReadIntProp(Actor, TEXT("FloorNumber"), Out.Floor))
	{
		OutWhy = TEXT("a landing does not say which floor it is");
		return false;
	}
	Out.StagedAt = Actor->GetActorLocation();
	return true;
}

bool ALiftTowerFunctionalTest::ResolveAndStage()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		StagingFault = TEXT("no world");
		return false;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LiftCar")), Found);
	if (Found.Num() != 1)
	{
		StagingFault = FString::Printf(
			TEXT("%d actor(s) tagged LiftCar, expected exactly one"), Found.Num());
		return false;
	}
	FString Why;
	if (!ResolveCar(Found[0], Why))
	{
		StagingFault = Why;
		return false;
	}

	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LiftLanding")), Found);
	if (Found.Num() != 3)
	{
		StagingFault = FString::Printf(
			TEXT("%d actor(s) tagged LiftLanding, expected exactly three"), Found.Num());
		return false;
	}
	for (AActor* const A : Found)
	{
		FLandingRef L;
		if (!ResolveLanding(A, L, Why))
		{
			StagingFault = Why;
			return false;
		}
		Landings.Add(L);
	}
	Landings.Sort([](const FLandingRef& L, const FLandingRef& R)
	{
		return L.Floor < R.Floor;
	});
	for (int32 i = 0; i < Landings.Num(); ++i)
	{
		if (Landings[i].Floor != i + 1)
		{
			StagingFault = FString::Printf(
				TEXT("the three landings call themselves %d/%d/%d; the tower needs "
					 "1, 2 and 3"),
				Landings[0].Floor, Landings[1].Floor, Landings[2].Floor);
			return false;
		}
	}

	// The tower is authored axis-aligned, and the fixture's pad footprints and local
	// waypoints assume it. Say so rather than silently mis-aiming the walk.
	auto NearlyUnrotated = [](const AActor* A)
	{
		const FRotator R = A->GetActorRotation();
		return FMath::Abs(R.Pitch) < 1.0 && FMath::Abs(R.Yaw) < 1.0
			&& FMath::Abs(R.Roll) < 1.0;
	};
	if (!NearlyUnrotated(Car.Actor.Get()) || !NearlyUnrotated(Landings[0].Actor.Get())
		|| !NearlyUnrotated(Landings[1].Actor.Get())
		|| !NearlyUnrotated(Landings[2].Actor.Get()))
	{
		StagingFault = TEXT("the tower is not authored axis-aligned");
		return false;
	}

	const double S1 = LandingSill(0);
	const double S3 = LandingSill(2);
	const double Shaft = S3 - S1;
	if (Shaft < kMinShaftUu)
	{
		StagingFault = FString::Printf(
			TEXT("landing 1 is at %.0f and landing 3 at %.0f -- a %.0f uu shaft is too "
				 "short to measure a travel speed in"), S1, S3, Shaft);
		return false;
	}
	StagedSillTwoLegOne = static_cast<float>(S1 + Shaft * kStagedTwoFractionA);
	StagedSillTwoLegTwo = static_cast<float>(S1 + Shaft * kStagedTwoFractionB);

	// A staging that fails either of these makes a gate vacuous, so refuse to run.
	if (FMath::Abs(StagedSillTwoLegOne - StagedSillTwoLegTwo) < kMinStagedSpreadUu)
	{
		StagingFault = FString::Printf(
			TEXT("landing 2's two staged heights are %.0f and %.0f, only %.0f apart; a "
				 "lift that cached the height once would barely notice"),
			StagedSillTwoLegOne, StagedSillTwoLegTwo,
			FMath::Abs(StagedSillTwoLegOne - StagedSillTwoLegTwo));
		return false;
	}
	const double Mid = (S1 + S3) * 0.5;
	if (FMath::Abs(StagedSillTwoLegOne - Mid) < kMinEvenSpacingGapUu
		|| FMath::Abs(StagedSillTwoLegTwo - Mid) < kMinEvenSpacingGapUu)
	{
		StagingFault = FString::Printf(
			TEXT("a staged landing 2 (%.0f / %.0f) sits within %.0f uu of halfway "
				 "(%.0f); an evenly spaced shaft would let a lift guess the heights"),
			StagedSillTwoLegOne, StagedSillTwoLegTwo, kMinEvenSpacingGapUu, Mid);
		return false;
	}

	// THE MAP'S COMMITTED FLOOR-2 HEIGHT IS A DECOY. This is the write that makes it so,
	// and it lands before any BeginPlay, so a submission that reads the sill at play
	// reads the STAGED value -- the height is honest, and only CACHING it is punished
	// (by the mid-run move, which the prompt discloses).
	{
		AActor* const A = Landings[1].Actor.Get();
		const FVector L = A->GetActorLocation();
		A->SetActorLocation(
			FVector(L.X, L.Y, L.Z + (StagedSillTwoLegOne - LandingSill(1))),
			/*bSweep=*/false);
	}

	for (FLandingRef& L : Landings)
	{
		if (AActor* const A = L.Actor.Get())
		{
			L.StagedAt = A->GetActorLocation();
		}
	}
	for (int32 i = 0; i < Landings.Num(); ++i)
	{
		Landings[i].StagedSill = LandingSill(i);
	}
	return true;
}

// =====================================================================================
// measurements
// =====================================================================================

float ALiftTowerFunctionalTest::CarSill() const
{
	const UPrimitiveComponent* const P = Car.Platform.Get();
	return P != nullptr ? static_cast<float>(P->Bounds.GetBox().Max.Z) : 0.0f;
}

float ALiftTowerFunctionalTest::LandingSill(int32 Index) const
{
	if (!Landings.IsValidIndex(Index))
	{
		return 0.0f;
	}
	const UPrimitiveComponent* const D = Landings[Index].Deck.Get();
	return D != nullptr ? static_cast<float>(D->Bounds.GetBox().Max.Z) : 0.0f;
}

float ALiftTowerFunctionalTest::DoorFraction() const
{
	const UPrimitiveComponent* const L = Car.LeafLeft.Get();
	const UPrimitiveComponent* const R = Car.LeafRight.Get();
	if (L == nullptr || R == nullptr)
	{
		return 0.0f;
	}
	// MEASURED OFF THE LEAVES, not off a flag: the doors being open is where the doors
	// are. The two ends land on exactly 0 and exactly 1 for the supplied mechanism.
	const double Span = double(Car.OpenSep) - double(Car.ShutSep);
	if (FMath::Abs(Span) < 1.0)
	{
		return 0.0f;
	}
	const double Sep = FMath::Abs(R->GetRelativeLocation().Y - L->GetRelativeLocation().Y);
	return static_cast<float>(FMath::Clamp((Sep - double(Car.ShutSep)) / Span, 0.0, 1.0));
}

int32 ALiftTowerFunctionalTest::NearestLandingIndex(float Sill, float& OutBest,
	float& OutSecond) const
{
	int32 Best = INDEX_NONE;
	OutBest = TNumericLimits<float>::Max();
	OutSecond = TNumericLimits<float>::Max();
	for (int32 i = 0; i < Landings.Num(); ++i)
	{
		const float D = FMath::Abs(LandingSill(i) - Sill);
		if (D < OutBest)
		{
			OutSecond = OutBest;
			OutBest = D;
			Best = i;
		}
		else if (D < OutSecond)
		{
			OutSecond = D;
		}
	}
	return Best;
}

int32 ALiftTowerFunctionalTest::IndexOfFloor(int32 Floor) const
{
	for (int32 i = 0; i < Landings.Num(); ++i)
	{
		if (Landings[i].Floor == Floor)
		{
			return i;
		}
	}
	return INDEX_NONE;
}

FBox ALiftTowerFunctionalTest::PadWorldBox(int32 Frame, int32 PadFloor) const
{
	const UPrimitiveComponent* C = nullptr;
	if (Frame == INDEX_NONE)
	{
		if (PadFloor >= 1 && PadFloor <= 3)
		{
			C = Car.Pads[PadFloor - 1].Get();
		}
	}
	else if (Landings.IsValidIndex(Frame))
	{
		C = Landings[Frame].CallPad.Get();
	}
	return C != nullptr ? C->Bounds.GetBox() : FBox(ForceInit);
}

FVector2D ALiftTowerFunctionalTest::StepWorldTarget(const FStep& Step) const
{
	if (Step.Kind == ELiftStepKind::GoToPad)
	{
		const FBox B = PadWorldBox(Step.Frame, Step.PadFloor);
		const FVector C = B.GetCenter();
		return FVector2D(C.X, C.Y);
	}
	FVector Origin = FVector::ZeroVector;
	if (Step.Frame == INDEX_NONE)
	{
		if (const AActor* const A = Car.Actor.Get())
		{
			Origin = A->GetActorLocation();
		}
	}
	else if (Landings.IsValidIndex(Step.Frame))
	{
		if (const AActor* const A = Landings[Step.Frame].Actor.Get())
		{
			Origin = A->GetActorLocation();
		}
	}
	return FVector2D(Origin.X + Step.Local.X, Origin.Y + Step.Local.Y);
}

bool ALiftTowerFunctionalTest::HeroOnPad(const FBox& Box, double Shrink) const
{
	const ACharacter* const H = Hero.Get();
	if (H == nullptr || !Box.IsValid)
	{
		return false;
	}
	const FVector At = H->GetActorLocation();
	if (At.X < Box.Min.X + Shrink || At.X > Box.Max.X - Shrink
		|| At.Y < Box.Min.Y + Shrink || At.Y > Box.Max.Y - Shrink)
	{
		return false;
	}
	const double Feet = At.Z - H->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	return FMath::Abs(Feet - Box.Max.Z) <= kPadFeetUu;
}

bool ALiftTowerFunctionalTest::LampLit(const UPointLightComponent* Lamp) const
{
	// THE LAMP, not a flag. A hidden lamp is dark whatever anybody set.
	return Lamp != nullptr && Lamp->IsVisible() && !Lamp->bHiddenInGame
		&& Lamp->Intensity > 0.0f;
}

int32 ALiftTowerFunctionalTest::FirstIntegerIn(const FString& Text)
{
	int32 Value = 0;
	bool bAny = false;
	for (int32 i = 0; i < Text.Len(); ++i)
	{
		const TCHAR Ch = Text[i];
		if (Ch >= TEXT('0') && Ch <= TEXT('9'))
		{
			Value = Value * 10 + static_cast<int32>(Ch - TEXT('0'));
			bAny = true;
		}
		else if (bAny)
		{
			break;
		}
	}
	return bAny ? Value : 0;
}

// =====================================================================================
// PrepareTest
// =====================================================================================

void ALiftTowerFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (!StagingFault.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the tower could not be staged -- %s"),
			*StagingFault));
		return;
	}
	if (!bStaged || Landings.Num() != 3 || !Car.Actor.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the tower was never staged, so the floor "
				 "heights the run depends on are the map's own"));
		return;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(GetWorld(), 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in the "
				 "tower"));
		return;
	}

	BuildSteps();
	if (!ValidateRoute())
	{
		return;   // ValidateRoute finished the test with its own reason
	}

	// The last entry is a SENTINEL, far past the drive, because the base class ends the
	// test the moment the last scheduled checkpoint is sampled -- and every deferred
	// gate lives past the end of the walk. The reference drive measures ~85 s; the worst
	// legal drive (a lift that holds its doors far longer than it must) plus one blown
	// step budget is ~200 s.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kSentinelIndex; ++k)
	{
		Schedule.Add(double(k) * 4.0);
	}
	Schedule.Add(kSentinelS);
	SetCheckpointSchedule(Schedule);

	StepIndex = 0;
	StepStartedAt = -1.0;
}

void ALiftTowerFunctionalTest::BuildSteps()
{
	const double DoorTravel = double(Car.DoorTravel);
	const double DoorHold = double(Car.DoorHold);
	const double Speed = FMath::Max(double(Car.Speed), 1.0);
	const double Shaft = double(LandingSill(2)) - double(LandingSill(0));

	// Ride budgets are DERIVED from the path the car has to cover and from the car's own
	// door numbers, not written down: two door cycles and 1800 uu on leg 1, three cycles
	// and 3600 uu on leg 2, times 2.5, plus 15 s.
	const double Cycle = 2.0 * DoorTravel + DoorHold;
	const double RideOne = 2.5 * (Shaft / Speed + 2.0 * Cycle) + 15.0;
	const double RideTwo = 2.5 * (2.0 * Shaft / Speed + 3.0 * Cycle) + 15.0;

	auto Go = [&](int32 Frame, double X, double Y, double Dwell, double Budget)
	{
		FStep S;
		S.Kind = ELiftStepKind::GoTo;
		S.Frame = Frame;
		S.Local = FVector2D(X, Y);
		S.Dwell = Dwell;
		S.Budget = Budget;
		Steps.Add(S);
	};
	auto Press = [&](int32 Frame, int32 PadFloor, double Dwell, double Budget,
		ELiftPressWindow Window)
	{
		FStep S;
		S.Kind = ELiftStepKind::GoToPad;
		S.Frame = Frame;
		S.PadFloor = PadFloor;
		S.Dwell = Dwell;
		S.Budget = Budget;
		S.Window = Window;
		Steps.Add(S);
	};
	auto Wait = [&](ELiftStepKind Kind, double Budget, double Amount = 0.0,
		int32 Count = 0, int32 Frame = INDEX_NONE)
	{
		FStep S;
		S.Kind = Kind;
		S.Budget = Budget;
		S.Amount = Amount;
		S.Count = Count;
		S.Frame = Frame;
		Steps.Add(S);
	};

	// Every walk inside the car runs THROUGH the middle of the floor, never diagonally
	// between two pads. The middle is 80 uu clear of every pad's capsule-wide footprint,
	// so crossing the car can never register a press nobody made -- which would rewrite
	// the collective answer the service order is compared against.
	//
	// THE ONE TIMING-SENSITIVE STEP IN THE WHOLE DRIVE is leg 1's mid-close press, and
	// the dwells around it are set for it. Walked out against the shipped tower, the
	// character at 500 uu/s with 2048 uu/s^2 of acceleration:
	//   press landing 1 at t ~= 0.95 (doors start opening) -> arrive t ~= 1.2, dwell 1.5
	//   -> step off, 253 uu, dwell 0.3, ends t ~= 3.3
	//   -> doors fully open at t ~= 2.95, so the WaitDoorsOpen step is already satisfied
	//   -> walk 400 uu into the car, dwell 0.2, ends t ~= 4.3
	//   -> the 3.0 s hold ends at t ~= 5.95, so WaitDoorsClosing waits ~1.6 s
	//   -> the walk to pad 3 is 145 uu ~= 0.4 s, so the press lands at fraction ~= 0.8
	// The window fails only below fraction 0.10, i.e. 1.8 s into a 2 s close, so the
	// slack is about 2.4 s, not the 1.6 s the wait suggests. If a real run ever lands
	// that press below 0.10 the fix is to shorten these two dwells further -- NOT to
	// widen the window, which is what makes `if (State != Idle) return;` fail.

	// ---------------------------------------------------------------------- LEG ONE
	Press(0, 0, 1.5, 30.0, ELiftPressWindow::None);                    // call landing 1
	Go(0, 280.0, 0.0, 0.3, 20.0);                                      // step off the pad
	Wait(ELiftStepKind::WaitDoorsOpen, 6.0 * DoorTravel + 12.0);
	Go(INDEX_NONE, 0.0, 0.0, 0.2, 20.0);                               // walk into the car
	Wait(ELiftStepKind::WaitDoorsClosing, 4.0 * (DoorHold + DoorTravel) + 20.0);
	Press(INDEX_NONE, 3, 1.5, 12.0, ELiftPressWindow::DoorsMidClose);  // 3, mid-close
	Go(INDEX_NONE, 0.0, 0.0, 0.1, 12.0);
	Press(INDEX_NONE, 2, 1.5, 12.0, ELiftPressWindow::BelowFloorTwo);  // then 2
	Go(INDEX_NONE, 0.0, 0.0, 0.3, 12.0);                               // stand and ride
	Wait(ELiftStepKind::WaitOpenings, RideOne, 0.0, 3, 2);
	Go(2, -150.0, 200.0, 2.5, 30.0);                                   // out onto landing 3

	// ---------------------------------------------------------------------- LEG TWO
	Press(2, 0, 1.5, 30.0, ELiftPressWindow::None);                    // call landing 3
	Go(2, 280.0, 0.0, 0.3, 20.0);
	Wait(ELiftStepKind::WaitDoorsOpen, 6.0 * DoorTravel + 12.0);
	Go(INDEX_NONE, 0.0, 0.0, 0.2, 20.0);
	Press(INDEX_NONE, 1, 1.5, 15.0, ELiftPressWindow::None);           // 1, from inside
	Go(INDEX_NONE, 0.0, 0.0, 0.1, 12.0);
	Wait(ELiftStepKind::WaitCarBelow, 4.0 * (DoorHold + 2.0 * DoorTravel) + 25.0, 60.0,
		0, 2);
	Press(INDEX_NONE, 3, 1.5, 10.0, ELiftPressWindow::HighInShaft);    // 3, behind us
	Go(INDEX_NONE, 0.0, 0.0, 0.1, 12.0);
	Press(INDEX_NONE, 2, 1.5, 10.0, ELiftPressWindow::AboveFloorTwo);  // 2, still ahead
	Go(INDEX_NONE, 0.0, 0.0, 0.3, 12.0);
	Wait(ELiftStepKind::WaitOpenings, RideTwo, 0.0, 7, 2);
	Go(2, -150.0, 200.0, 2.5, 30.0);
	Go(2, -150.0, -80.0, 5.0, 20.0);                                   // the idle tail

	FStep Done;
	Done.Kind = ELiftStepKind::Done;
	Steps.Add(Done);
}

bool ALiftTowerFunctionalTest::ValidateRoute()
{
	// A pad the walk crosses but is not aimed at records a press nobody made, and the
	// whole expected service order falls over. Check it rather than assert it.
	TArray<FBox> Boxes;
	TArray<FString> Names;
	for (int32 f = 1; f <= 3; ++f)
	{
		Boxes.Add(PadWorldBox(INDEX_NONE, f));
		Names.Add(FString::Printf(TEXT("the in-car pad for floor %d"), f));
	}
	// All three landings share one XY, so one call-pad footprint stands for all three.
	Boxes.Add(PadWorldBox(0, 0));
	Names.Add(TEXT("a landing call pad"));

	for (FBox& B : Boxes)
	{
		if (!B.IsValid || (B.Max.X - B.Min.X) * 0.5 < 55.0 || (B.Max.Y - B.Min.Y) * 0.5 < 55.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSuppliedMachineryIsStillThere: a pad footprint measures %.0f x "
					 "%.0f uu. The pads, the lamps, the doors and the signs are supplied "
					 "and working, and the job is to decide when to use them, not to "
					 "shrink or remove them"),
				B.IsValid ? (B.Max.X - B.Min.X) : 0.0, B.IsValid ? (B.Max.Y - B.Min.Y) : 0.0));
			return false;
		}
		// WIDEN BY THE CAPSULE, not just the centre. The SUBMISSION sees an overlap the
		// moment the character's 42 uu capsule touches a pad; the fixture sees a press
		// only when his centre is inside it. A walk that brushes a pad it is not aimed
		// at would therefore hand the lift a call the fixture never recorded, and the
		// service order would be compared against the wrong answer. 50 uu = the capsule
		// radius plus 8 uu of margin.
		B = B.ExpandBy(FVector(50.0, 50.0, 0.0));
	}

	FVector2D At = FVector2D::ZeroVector;
	if (const ACharacter* const H = Hero.Get())
	{
		const FVector L = H->GetActorLocation();
		At = FVector2D(L.X, L.Y);
	}
	int32 OriginPad = INDEX_NONE;
	for (const FStep& S : Steps)
	{
		if (S.Kind != ELiftStepKind::GoTo && S.Kind != ELiftStepKind::GoToPad)
		{
			continue;
		}
		const FVector2D To = StepWorldTarget(S);
		int32 DestPad = INDEX_NONE;
		if (S.Kind == ELiftStepKind::GoToPad)
		{
			DestPad = (S.Frame == INDEX_NONE) ? (S.PadFloor - 1) : 3;
		}
		constexpr int32 kSamples = 48;
		for (int32 k = 0; k <= kSamples; ++k)
		{
			const FVector2D P = FMath::Lerp(At, To, double(k) / double(kSamples));
			for (int32 b = 0; b < Boxes.Num(); ++b)
			{
				if (b == DestPad || b == OriginPad)
				{
					continue;
				}
				const FBox& B = Boxes[b];
				if (P.X >= B.Min.X && P.X <= B.Max.X && P.Y >= B.Min.Y && P.Y <= B.Max.Y)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walk to (%.0f, %.0f) crosses %s "
							 "at (%.0f, %.0f), which would record a press nobody made"),
						To.X, To.Y, *Names[b], P.X, P.Y));
					return false;
				}
			}
		}
		At = To;
		OriginPad = DestPad;
	}
	return true;
}

// =====================================================================================
// continuous gates
// =====================================================================================

void ALiftTowerFunctionalTest::CheckSuppliedMachinery(double Now)
{
	const bool bCar = Car.Actor.IsValid() && Car.Platform.IsValid()
		&& Car.LeafLeft.IsValid() && Car.LeafRight.IsValid();
	bool bParts = bCar;
	for (int32 i = 0; i < 3 && bParts; ++i)
	{
		bParts = Car.Pads[i].IsValid() && Car.Lamps[i].IsValid();
	}
	for (const FLandingRef& L : Landings)
	{
		bParts = bParts && L.Actor.IsValid() && L.Deck.IsValid() && L.CallPad.IsValid()
			&& L.CallLamp.IsValid() && L.Readout.IsValid() && L.Arrow.IsValid();
	}
	if (!bParts)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheSuppliedMachineryIsStillThere: at t=%.2f s a supplied part of the "
				 "tower has gone -- the platform, a door leaf, a pad, a lamp, a readout "
				 "or an arrow. The job is to decide when to use them, not to remove "
				 "them"), Now));
	}
}

void ALiftTowerFunctionalTest::CheckPinnedNumbers(double Now)
{
	const AActor* const A = Car.Actor.Get();
	if (A == nullptr)
	{
		return;
	}
	float Speed = 0.0f, Travel = 0.0f, Hold = 0.0f, Shut = 0.0f, Open = 0.0f;
	const bool bRead = ReadFloatProp(A, TEXT("TravelSpeedUuPerSecond"), Speed)
		&& ReadFloatProp(A, TEXT("DoorTravelSeconds"), Travel)
		&& ReadFloatProp(A, TEXT("DoorHoldSeconds"), Hold)
		&& ReadFloatProp(A, TEXT("DoorShutSeparationUu"), Shut)
		&& ReadFloatProp(A, TEXT("DoorOpenSeparationUu"), Open);
	const bool bSame = bRead
		&& FMath::IsNearlyEqual(Speed, Car.Speed, 0.01f)
		&& FMath::IsNearlyEqual(Travel, Car.DoorTravel, 0.001f)
		&& FMath::IsNearlyEqual(Hold, Car.DoorHold, 0.001f)
		&& FMath::IsNearlyEqual(Shut, Car.ShutSep, 0.01f)
		&& FMath::IsNearlyEqual(Open, Car.OpenSep, 0.01f);
	if (!bSame)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheNumbersOnTheCarAreNotYoursToRewrite: at t=%.2f s the car reads "
				 "%.1f uu/s, doors %.2f s, hold %.2f s; the tower built it %.1f uu/s, "
				 "doors %.2f s, hold %.2f s. Read them, do not rewrite them"),
			Now, Speed, Travel, Hold, Car.Speed, Car.DoorTravel, Car.DoorHold));
		return;
	}
	for (int32 i = 0; i < Landings.Num(); ++i)
	{
		int32 Floor = 0;
		if (!ReadIntProp(Landings[i].Actor.Get(), TEXT("FloorNumber"), Floor)
			|| Floor != Landings[i].Floor)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheNumbersOnTheCarAreNotYoursToRewrite: at t=%.2f s a landing "
					 "calls itself floor %d and the tower placed it as floor %d"),
				Now, Floor, Landings[i].Floor));
			return;
		}
	}
}

void ALiftTowerFunctionalTest::CheckNothingWasMoved(double Now)
{
	for (int32 i = 0; i < Landings.Num(); ++i)
	{
		const AActor* const A = Landings[i].Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		if (!A->GetActorLocation().Equals(Landings[i].StagedAt, kStayPutUu))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheLandingsAndTheCarStayedWhereTheyWerePut: at t=%.2f s landing %d "
					 "is at %s and the tower put it at %s. Where the landings are is not "
					 "yours to change"),
				Now, Landings[i].Floor, *A->GetActorLocation().ToCompactString(),
				*Landings[i].StagedAt.ToCompactString()));
			return;
		}
	}
	const AActor* const C = Car.Actor.Get();
	if (C == nullptr)
	{
		return;
	}
	const FVector L = C->GetActorLocation();
	if (FMath::Abs(L.X - Car.StagedX) > kStayPutUu
		|| FMath::Abs(L.Y - Car.StagedY) > kStayPutUu)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheLandingsAndTheCarStayedWhereTheyWerePut: at t=%.2f s the car has "
				 "left its shaft -- it is at (%.0f, %.0f) and the shaft is at "
				 "(%.0f, %.0f). The car may only go up and down"),
			Now, L.X, L.Y, Car.StagedX, Car.StagedY));
		return;
	}
	const float Sill = CarSill();
	if (Sill < LandingSill(0) - 200.0f || Sill > LandingSill(2) + 200.0f)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheLandingsAndTheCarStayedWhereTheyWerePut: at t=%.2f s the car sill "
				 "is at %.0f, outside the shaft (%.0f to %.0f)"),
			Now, Sill, LandingSill(0), LandingSill(2)));
	}
}

void ALiftTowerFunctionalTest::CheckDoorsAndMotion(double Now)
{
	const float Sill = CarSill();
	const float Frac = DoorFraction();

	if (bHavePrevFrame)
	{
		const double D = double(Sill) - double(PrevSill);

		// ------------------------------------------- the car never moves with its doors
		if (FMath::Abs(D) > kMovedUu && (Frac > kOpenEps || PrevFraction > kOpenEps))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheCarNeverMovesWithItsDoorsOpen: at t=%.2f s the car sill moved "
					 "%.1f uu in one frame with the doors reading %.2f open (%.2f the "
					 "frame before). Never move the car unless the doors are completely "
					 "shut"), Now, D, Frac, PrevFraction));
			return;
		}

		// ---------------------------------------------------------- travel segments
		if (FMath::Abs(D) > kSillJitterUu)
		{
			if (!bSegmentOpen)
			{
				bSegmentOpen = true;
				SegmentStartT = PrevTime;
				SegmentPathUu = 0.0;
			}
			SegmentPathUu += FMath::Abs(D);
			SegmentLastMoveT = Now;
		}
		else if (bSegmentOpen && Now - SegmentLastMoveT > kSegmentGapS)
		{
			bSegmentOpen = false;
			++SegmentIndex;
			const double Elapsed = SegmentLastMoveT - SegmentStartT;
			if (SegmentPathUu >= kMinSegmentUu && Elapsed > 1.0e-4)
			{
				const double Measured = SegmentPathUu / Elapsed;
				const double Want = double(Car.Speed);
				if (Measured < Want * (1.0 - kSpeedBand) || Measured > Want * (1.0 + kSpeedBand))
				{
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("TheCarTravelsAtTheSpeedWrittenOnIt: trip %d covered %.0f uu "
							 "in %.2f s of moving, which is %.0f uu/s. The number written "
							 "on this car is %.0f uu/s, and the same one whichever way it "
							 "is going and however far it has to go"),
						SegmentIndex, SegmentPathUu, Elapsed, Measured, Want));
					return;
				}
			}
		}

		// ------------------------------------------------- the doors hold open long
		if (Frac >= 1.0f - kOpenEps && PrevFraction < 1.0f - kOpenEps)
		{
			FullyOpenSince = Now;

			// ----------------------------------------- arrive level with the landing
			float Best = 0.0f, Second = 0.0f;
			const int32 Near = NearestLandingIndex(Sill, Best, Second);
			if (Near == INDEX_NONE)
			{
				return;
			}
			if (double(Best) > kLevelToleranceUu)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheCarStopsLevelWithTheLandingItServes: the doors opened all the "
						 "way at t=%.2f s with the car sill at %.0f and the nearest "
						 "landing (floor %d) at %.0f, which is %.0f uu out. Arrive level: "
						 "within five centimetres, so somebody can walk straight out"),
					Now, Sill, Landings[Near].Floor, LandingSill(Near), Best));
				return;
			}

			FOpening O;
			O.Floor = Landings[Near].Floor;
			O.At = Now;
			O.CarSill = Sill;
			O.LandingSill = LandingSill(Near);
			Openings.Add(O);

			// ------------------------- the order, checked as a PREFIX, the moment it goes
			const int32 Index = Openings.Num() - 1;
			if (Index >= kExpectedOpeningCount || O.Floor != kExpectedOpenings[Index])
			{
				FString Seen;
				for (const FOpening& E : Openings)
				{
					Seen += FString::Printf(TEXT("%s%d"), Seen.IsEmpty() ? TEXT("") : TEXT(","), E.Floor);
				}
				FString Want;
				for (int32 k = 0; k < kExpectedOpeningCount; ++k)
				{
					Want += FString::Printf(TEXT("%s%d"), k ? TEXT(",") : TEXT(""), kExpectedOpenings[k]);
				}
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheLiftServesWhatIsOnTheWayBeforeItTurnsAround: the doors opened "
						 "at floor %d at t=%.2f s. The floors served so far are [%s] and a "
						 "lift that keeps going the way it is going, stopping at "
						 "everything called on the way and only turning round when there "
						 "is nothing left ahead, would have served [%s]"),
					O.Floor, Now, *Seen, *Want));
				return;
			}

			for (FPress& P : Presses)
			{
				if (P.Floor == O.Floor && P.ServedAt < 0.0)
				{
					P.ServedAt = Now;
				}
			}

			// THE STOP BEGINS HERE. Armed on this edge and AFTER the level check above,
			// so a car that opened somewhere it was not level never starts a dwell it
			// could then be judged on -- it has already failed the level gate.
			DwellLandingIndex = Near;
			DwellFloor = O.Floor;
			DwellStartedAt = Now;
		}
		else if (Frac < 1.0f - kOpenEps && PrevFraction >= 1.0f - kOpenEps
			&& FullyOpenSince >= 0.0)
		{
			const double Held = Now - FullyOpenSince;
			const double Want = double(Car.DoorHold);
			FullyOpenSince = -1.0;
			if (Held < Want - kHoldSlackS)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheDoorsHoldOpenLongEnoughToGetOut: stop %d held all the way "
						 "open for %.2f s and the hold written on this car is %.2f s. "
						 "The hold starts when the doors are ALL the way open, not when "
						 "the car arrives"),
					Openings.Num(), Held, Want));
				return;
			}
		}

		// ------------------------------- the car STANDS at the floor it opened at
		// The gate above measures the DOOR. This one measures the CAR, and they are
		// different defects. TheCarNeverMovesWithItsDoorsOpen forgives a sill delta of
		// up to kMovedUu in one frame, which at this fixed step is 60 uu/s -- so a lift
		// that treats arrival as the start of its next journey and eases away while the
		// door animation finishes can drift ~180 uu out of the landing during a 3 s hold
		// and still pass every other gate in this file. Nobody can walk out of that, and
		// it is an entirely ordinary way to write a lift.
		//
		// Judged ONLY when the car actually leaves the landing. A car still standing
		// there when the run ends has rushed nobody, so there is deliberately nothing to
		// evaluate at the end and no way for this gate to false-FAIL a slow but correct
		// lift. The landing sill is re-read every frame rather than captured, so the
		// mid-run re-stage of landing 2 cannot make this gate disagree with the world.
		if (DwellLandingIndex != INDEX_NONE && Now > DwellStartedAt)
		{
			const double Off =
				FMath::Abs(double(Sill) - double(LandingSill(DwellLandingIndex)));
			const double Stood = Now - DwellStartedAt;
			const double Want = double(Car.DoorHold);
			if (Off > kLevelToleranceUu)
			{
				DwellLandingIndex = INDEX_NONE;
				if (Stood < Want - kHoldSlackS)
				{
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("TheCarStandsStillLongEnoughToStepOut: the doors reached all "
							 "the way open at floor %d at t=%.2f s, and %.2f s later the "
							 "car sill is already %.0f uu off that landing. A stop is a "
							 "stop: from the moment the doors are all the way open the "
							 "car stands still, level with that landing -- inside the "
							 "same five centimetres it arrived at -- for at least the "
							 "%.2f s hold written on it, so somebody can walk across the "
							 "sill and out. It does not begin to sink or climb toward its "
							 "next call while its doors are open"),
						DwellFloor, DwellStartedAt, Stood, Off, Want));
					return;
				}
			}
			else if (Stood >= Want - kHoldSlackS)
			{
				// It stood its ground for the whole hold. Nothing left to judge at this
				// stop; the next opening arms the next one.
				DwellLandingIndex = INDEX_NONE;
			}
		}
	}
}

void ALiftTowerFunctionalTest::CheckRiderAndProgress(double Now)
{
	const ACharacter* const H = Hero.Get();
	const UPrimitiveComponent* const P = Car.Platform.Get();
	if (H == nullptr || P == nullptr)
	{
		return;
	}
	const float Sill = CarSill();
	const float Frac = DoorFraction();

	// ------------------------------------------------------------------- (i) PROGRESS
	bool bDistantOutstanding = false;
	int32 WaitingFloor = 0;
	float WaitingSill = 0.0f;
	for (const FPress& Pr : Presses)
	{
		if (Pr.ServedAt >= 0.0)
		{
			continue;
		}
		const int32 Idx = IndexOfFloor(Pr.Floor);
		if (Idx == INDEX_NONE)
		{
			continue;
		}
		if (FMath::Abs(LandingSill(Idx) - Sill) > kDistantCallUu)
		{
			bDistantOutstanding = true;
			WaitingFloor = Pr.Floor;
			WaitingSill = LandingSill(Idx);
			break;
		}
	}
	if (Frac > kOpenEps || !bDistantOutstanding)
	{
		bProgressArmed = false;
	}
	else if (!bProgressArmed)
	{
		bProgressArmed = true;
		ProgressArmedAt = Now;
		ProgressArmedSill = Sill;
	}
	else if (FMath::Abs(Sill - ProgressArmedSill) >= kProgressUu)
	{
		ProgressArmedAt = Now;
		ProgressArmedSill = Sill;
	}
	else if (Now - ProgressArmedAt > kProgressWindowS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheCarActuallyTravelsAndTakesItsRiderWithIt: floor %d has been called "
				 "and is at %.0f, the car sill has sat at %.0f with its doors shut for "
				 "%.1f s, and it has not moved %.0f uu. The car must really travel"),
			WaitingFloor, WaitingSill, Sill, Now - ProgressArmedAt, kProgressUu));
		return;
	}

	// ---------------------------------------------------------------------- (ii) RIDER
	if (bHavePrevFrame && FMath::Abs(double(Sill) - double(PrevSill)) > kMovedUu)
	{
		const FBox Floorplate = P->Bounds.GetBox();
		const FVector At = H->GetActorLocation();
		const double Feet = At.Z - H->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		const bool bOver = At.X >= Floorplate.Min.X - kRiderMarginUu
			&& At.X <= Floorplate.Max.X + kRiderMarginUu
			&& At.Y >= Floorplate.Min.Y - kRiderMarginUu
			&& At.Y <= Floorplate.Max.Y + kRiderMarginUu;
		if (!bOver || FMath::Abs(Feet - double(Sill)) > kRiderFeetUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheCarActuallyTravelsAndTakesItsRiderWithIt: at t=%.2f s the car "
					 "sill is moving through %.0f and the rider is at (%.0f, %.0f) with "
					 "his feet at %.0f. Whoever is standing in the car has to be carried "
					 "the whole way"),
				Now, Sill, At.X, At.Y, Feet));
		}
	}
}

void ALiftTowerFunctionalTest::SamplePresses(double Now)
{
	// Six pads: 0..2 are the in-car pads for floors 1..3, 3..5 are the landings' call
	// pads. A press is the fixture's OWN geometric observation; the submission's
	// bookkeeping is never consulted.
	//
	// THE TEST IS THE CAPSULE, NOT THE CENTRE, and that is load-bearing rather than
	// fussy. A submission bound to the pad's overlap event sees the press the moment the
	// 42 uu capsule TOUCHES the box; a fixture testing the centre would see it ~0.15 s
	// later. The sign gate compares what the signs show against what the fixture knows
	// is outstanding, so a fixture that learned about a press LATER than the submission
	// would fail a correct lift for lighting its arrow too early. Expanding by the
	// capsule radius makes the fixture's knowledge arrive first (a box expansion is
	// wider at the corners than the true capsule sweep), and the sign gate's half-second
	// settle absorbs the difference in the safe direction.
	const ACharacter* const H = Hero.Get();
	const double Radius = H != nullptr
		? H->GetCapsuleComponent()->GetScaledCapsuleRadius() : 42.0;
	for (int32 i = 0; i < 6; ++i)
	{
		const bool bCarPad = i < 3;
		const FBox Box = bCarPad ? PadWorldBox(INDEX_NONE, i + 1) : PadWorldBox(i - 3, 0);
		const bool bOn = HeroOnPad(Box, -Radius);
		if (bOn && !bPadOccupied[i])
		{
			FPress Pr;
			Pr.Floor = bCarPad ? (i + 1) : Landings[i - 3].Floor;
			Pr.bInCar = bCarPad;
			Pr.At = Now;
			Presses.Add(Pr);
		}
		bPadOccupied[i] = bOn;
	}
}

void ALiftTowerFunctionalTest::CheckLatchedLamps(double Now)
{
	for (FPress& Pr : Presses)
	{
		const UPointLightComponent* Lamp = nullptr;
		if (Pr.bInCar)
		{
			Lamp = Car.Lamps[Pr.Floor - 1].Get();
		}
		else
		{
			const int32 Idx = IndexOfFloor(Pr.Floor);
			Lamp = Landings.IsValidIndex(Idx) ? Landings[Idx].CallLamp.Get() : nullptr;
		}
		const bool bLit = LampLit(Lamp);

		// DIAGNOSTIC BOOKKEEPING, EVERY FRAME FROM THE SERVE ONWARDS -- not a gate.
		// Clause B below only looks inside [served+0.5, served+2.0]; without this the
		// two defects it can catch ("never went out" and "went out and came back") are
		// indistinguishable in the failure message, and a run gives you no way to tell
		// them apart afterwards. Recorded here, before the thresholds, so it covers the
		// blind half-second as well.
		if (Pr.ServedAt >= 0.0)
		{
			if (Pr.DarkAt < 0.0)
			{
				if (!bLit)
				{
					Pr.DarkAt = Now;
				}
			}
			else if (bLit && Pr.RelitAt < 0.0)
			{
				Pr.RelitAt = Now;
			}
		}

		if (Pr.ServedAt < 0.0)
		{
			if (Now - Pr.At >= kLampGraceS && !bLit)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("NoCallIsEverDropped: a pad was pressed for floor %d at t=%.2f s "
						 "and its light is out again at t=%.2f s, with the lift still not "
						 "having opened its doors there (the %s pad). That light comes on "
						 "when the pad is pressed and stays on until the lift has opened "
						 "its doors at that floor"),
					Pr.Floor, Pr.At, Now, Pr.bInCar ? TEXT("in-car") : TEXT("landing")));
				return;
			}
		}
		else if (Now - Pr.ServedAt >= kLampGraceS && Now - Pr.ServedAt <= kLampOutWindowS
			&& bLit)
		{
			// Same threshold as before, to the byte -- the sentence after it is the only
			// thing that changed, and it names WHICH defect this is.
			const FString Story = Pr.DarkAt < 0.0
				? FString(TEXT("it has not been out for a single frame since the doors "
							   "opened, so nothing ever cleared it"))
				: FString::Printf(
					TEXT("it went out at t=%.2f s and was lit again at t=%.2f s, so "
						 "something re-latched that floor after it was served"),
					Pr.DarkAt, Pr.RelitAt);
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NoCallIsEverDropped: a pad was served for floor %d at t=%.2f s and "
					 "its light is still on at t=%.2f s (the %s pad, pressed at "
					 "t=%.2f s). It goes out once the lift has opened its doors at that "
					 "floor -- %s"),
				Pr.Floor, Pr.ServedAt, Now, Pr.bInCar ? TEXT("in-car") : TEXT("landing"),
				Pr.At, *Story));
			return;
		}
	}
}

void ALiftTowerFunctionalTest::SampleSigns(double Now)
{
	FSignFrame F;
	F.T = Now;
	F.CarSill = CarSill();

	float Best = 0.0f, Second = 0.0f;
	const int32 Near = NearestLandingIndex(F.CarSill, Best, Second);
	F.NearestFloor = Landings.IsValidIndex(Near) ? Landings[Near].Floor : 0;
	F.bNearestAmbiguous = (Second - Best) < kNearestMarginUu;

	for (const FPress& Pr : Presses)
	{
		if (Pr.ServedAt >= 0.0)
		{
			continue;
		}
		const int32 Idx = IndexOfFloor(Pr.Floor);
		if (Idx != INDEX_NONE && FMath::Abs(LandingSill(Idx) - F.CarSill) > kSignLevelBandUu)
		{
			F.bAnythingOutstanding = true;
			break;
		}
	}

	for (int32 i = 0; i < Landings.Num() && i < 3; ++i)
	{
		const UTextRenderComponent* const R = Landings[i].Readout.Get();
		F.Shown[i] = R != nullptr ? FirstIntegerIn(R->Text.ToString()) : 0;
		const USceneComponent* const A = Landings[i].Arrow.Get();
		if (A == nullptr || !A->IsVisible())
		{
			F.Dir[i] = 0;
		}
		else
		{
			const double Up = A->GetUpVector().Z;
			F.Dir[i] = (Up > 0.5) ? 1 : ((Up < -0.5) ? -1 : 2);
		}
	}
	SignTrace.Add(F);
}

// =====================================================================================
// the drive
// =====================================================================================

void ALiftTowerFunctionalTest::DriveHeroTo(const FVector2D& Target)
{
	ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		return;
	}
	const FVector At = H->GetActorLocation();
	const FVector Flat(Target.X - At.X, Target.Y - At.Y, 0.0);
	if (Flat.SizeSquared() > 1.0)
	{
		H->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
	}
}

bool ALiftTowerFunctionalTest::PressWindowHolds(ELiftPressWindow Window, FString& OutWhy) const
{
	const float Sill = CarSill();
	const float Frac = DoorFraction();
	switch (Window)
	{
	case ELiftPressWindow::DoorsMidClose:
		if (Frac > 0.10f && Frac < 1.0f - kOpenEps)
		{
			return true;
		}
		OutWhy = FString::Printf(
			TEXT("the doors read %.2f open, and the press had to land while they were "
				 "still on their way shut"), Frac);
		return false;
	case ELiftPressWindow::BelowFloorTwo:
		if (double(Sill) < double(LandingSill(1)) - 100.0)
		{
			return true;
		}
		OutWhy = FString::Printf(
			TEXT("the car sill is %.0f and landing 2 is at %.0f, so floor 2 was no "
				 "longer ahead of the car"), Sill, LandingSill(1));
		return false;
	case ELiftPressWindow::HighInShaft:
	{
		const double Half = (double(LandingSill(2)) + double(LandingSill(1))) * 0.5;
		if (double(Sill) >= Half + 200.0 && double(Sill) <= double(LandingSill(2)) - 40.0)
		{
			return true;
		}
		OutWhy = FString::Printf(
			TEXT("the car sill is %.0f; the press had to land between %.0f and %.0f, "
				 "with the car under way and floor 3 still the nearer call"),
			Sill, Half + 200.0, double(LandingSill(2)) - 40.0);
		return false;
	}
	case ELiftPressWindow::AboveFloorTwo:
		if (double(Sill) > double(LandingSill(1)) + 100.0)
		{
			return true;
		}
		OutWhy = FString::Printf(
			TEXT("the car sill is %.0f and landing 2 is at %.0f, so floor 2 was no "
				 "longer ahead of the car"), Sill, LandingSill(1));
		return false;
	default:
		return true;
	}
}

void ALiftTowerFunctionalTest::FailWaitDeadline(const FStep& Step, double Now)
{
	// A wait that runs out is graded, never excused. WHICH gate it is comes from the
	// fixture's own record: an outstanding press means a call was dropped; no
	// outstanding press means the lift simply stopped doing anything.
	const FPress* Outstanding = nullptr;
	for (const FPress& Pr : Presses)
	{
		if (Pr.ServedAt < 0.0)
		{
			Outstanding = &Pr;
			break;
		}
	}
	const float Sill = CarSill();
	const float Frac = DoorFraction();
	if (Outstanding != nullptr)
	{
		const int32 Idx = IndexOfFloor(Outstanding->Floor);
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NoCallIsEverDropped: somebody stepped on the pad for floor %d at "
				 "t=%.2f s and %.1f s later the lift has still not opened its doors "
				 "there. The car sill is %.0f, that landing is at %.0f and the doors "
				 "read %.2f open. A call is never forgotten, whatever the lift was "
				 "doing when the pad was pressed"),
			Outstanding->Floor, Outstanding->At, Now - Outstanding->At, Sill,
			Landings.IsValidIndex(Idx) ? LandingSill(Idx) : 0.0f, Frac));
		return;
	}
	const TCHAR* What = TEXT("something to happen");
	switch (Step.Kind)
	{
	case ELiftStepKind::WaitDoorsOpen: What = TEXT("the doors to open all the way"); break;
	case ELiftStepKind::WaitDoorsClosing: What = TEXT("the doors to begin shutting again"); break;
	case ELiftStepKind::WaitCarBelow: What = TEXT("the car to get under way"); break;
	case ELiftStepKind::WaitOpenings: What = TEXT("the lift to finish serving its calls"); break;
	default: break;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheLiftKeptTheRiderWaiting: the rider stood for %.1f s waiting for %s and "
			 "it never happened. At t=%.2f s the car sill is %.0f, the doors read %.2f "
			 "open, and %d of %d stops have been made"),
		Now - StepStartedAt, What, Now, Sill, Frac, Openings.Num(), kExpectedOpeningCount));
}

void ALiftTowerFunctionalTest::AdvanceDrive(double Now)
{
	if (!Steps.IsValidIndex(StepIndex) || bDriveComplete)
	{
		return;
	}
	FStep& Step = Steps[StepIndex];
	if (StepStartedAt < 0.0)
	{
		StepStartedAt = Now;
		DwellUntil = -1.0;
	}

	auto Advance = [&]()
	{
		++StepIndex;
		StepStartedAt = -1.0;
		DwellUntil = -1.0;
		if (Steps.IsValidIndex(StepIndex) && Steps[StepIndex].Kind == ELiftStepKind::Done)
		{
			bDriveComplete = true;
			DriveCompletedAt = Now;
		}
	};

	switch (Step.Kind)
	{
	case ELiftStepKind::GoTo:
	{
		const FVector2D Target = StepWorldTarget(Step);
		const ACharacter* const H = Hero.Get();
		const FVector At = H ? H->GetActorLocation() : FVector::ZeroVector;
		if (FVector2D::Distance(FVector2D(At.X, At.Y), Target) <= kWaypointUu)
		{
			// STAND here. Everything this fixture measures is about a state that has
			// settled, and a walk that only passes through a spot measures nothing.
			if (DwellUntil < 0.0) { DwellUntil = Now + Step.Dwell; }
			else if (Now >= DwellUntil) { Advance(); }
		}
		else
		{
			DriveHeroTo(Target);
			if (Now - StepStartedAt > Step.Budget)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheRiderCouldNotGetWhereHeWasGoing: %.1f s of walking and the "
						 "rider is at (%.0f, %.0f, %.0f), still %.0f uu from (%.0f, "
						 "%.0f). The car sill is %.0f and the doors read %.2f open"),
					Now - StepStartedAt, At.X, At.Y, At.Z,
					FVector2D::Distance(FVector2D(At.X, At.Y), Target),
					Target.X, Target.Y, CarSill(), DoorFraction()));
			}
		}
		break;
	}
	case ELiftStepKind::GoToPad:
	{
		const FBox Box = PadWorldBox(Step.Frame, Step.PadFloor);
		if (HeroOnPad(Box, kPadShrinkUu))
		{
			if (DwellUntil < 0.0)
			{
				DwellUntil = Now + Step.Dwell;
				// The press has just been recorded by SamplePresses on this same frame
				// or the one before. Check its window HERE, where the world state that
				// the window is about is still the state at the press.
				FString Why;
				if (!PressWindowHolds(Step.Window, Why))
				{
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("TheCarKeptToItsOwnTimings: the rider reached the pad for "
							 "floor %d at t=%.2f s and by then %s. This car is written "
							 "with %.0f uu/s, %.2f s doors and a %.2f s hold, and a car "
							 "that beats its own numbers leaves its passenger unable to "
							 "reach a button"),
						Step.PadFloor > 0 ? Step.PadFloor
							: (Landings.IsValidIndex(Step.Frame) ? Landings[Step.Frame].Floor : 0),
						Now, *Why, Car.Speed, Car.DoorTravel, Car.DoorHold));
					return;
				}
			}
			else if (Now >= DwellUntil)
			{
				Advance();
			}
		}
		else
		{
			const FVector C = Box.GetCenter();
			DriveHeroTo(FVector2D(C.X, C.Y));
			if (Now - StepStartedAt > Step.Budget)
			{
				const ACharacter* const H = Hero.Get();
				const FVector At = H ? H->GetActorLocation() : FVector::ZeroVector;
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheRiderCouldNotGetWhereHeWasGoing: %.1f s of walking and the "
						 "rider is at (%.0f, %.0f, %.0f), still %.0f uu from (%.0f, "
						 "%.0f). The car sill is %.0f and the doors read %.2f open"),
					Now - StepStartedAt, At.X, At.Y, At.Z,
					FVector2D::Distance(FVector2D(At.X, At.Y), FVector2D(C.X, C.Y)),
					C.X, C.Y, CarSill(), DoorFraction()));
			}
		}
		break;
	}
	case ELiftStepKind::WaitDoorsOpen:
		if (DoorFraction() >= 1.0f - kOpenEps) { Advance(); }
		else if (Now - StepStartedAt > Step.Budget) { FailWaitDeadline(Step, Now); }
		break;
	case ELiftStepKind::WaitDoorsClosing:
		if (DoorFraction() < 1.0f - kOpenEps) { Advance(); }
		else if (Now - StepStartedAt > Step.Budget) { FailWaitDeadline(Step, Now); }
		break;
	case ELiftStepKind::WaitCarBelow:
		if (double(CarSill()) <= double(LandingSill(Step.Frame)) - Step.Amount) { Advance(); }
		else if (Now - StepStartedAt > Step.Budget) { FailWaitDeadline(Step, Now); }
		break;
	case ELiftStepKind::WaitOpenings:
	{
		const bool bLevel =
			FMath::Abs(CarSill() - LandingSill(Step.Frame)) <= kLevelToleranceUu;
		if (Openings.Num() >= Step.Count && bLevel && DoorFraction() >= 1.0f - kOpenEps)
		{
			Advance();
		}
		else if (Now - StepStartedAt > Step.Budget)
		{
			FailWaitDeadline(Step, Now);
		}
		break;
	}
	default:
		break;
	}

	// Between the two legs the tower moves landing 2, with nobody on it. Step 11 is the
	// first step of leg 2, so reaching it means leg 1 is over and the rider is standing
	// on landing 3 with the car parked there.
	if (!bRestaged && StepIndex >= 11 && IsRunning())
	{
		RestageForLegTwo(Now);
	}
}

void ALiftTowerFunctionalTest::RestageForLegTwo(double Now)
{
	bRestaged = true;
	AActor* const A = Landings[1].Actor.Get();
	const ACharacter* const H = Hero.Get();
	if (A == nullptr || H == nullptr)
	{
		return;
	}
	const double Old = double(LandingSill(1));
	const double New = double(StagedSillTwoLegTwo);
	const double Sill = double(CarSill());
	const double Feet = H->GetActorLocation().Z
		- H->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();

	// STAGED FACTS ONLY. Moving a landing out from under somebody, or through the car,
	// would be the fixture breaking the run -- so it refuses instead, and the refusal is
	// attributed to the harness rather than scored against the submission.
	if (FMath::Abs(Sill - Old) < kRestageClearUu || FMath::Abs(Sill - New) < kRestageClearUu
		|| FMath::Abs(Feet - Old) < kRestageClearUu || FMath::Abs(Feet - New) < kRestageClearUu)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: landing 2 cannot be moved from %.0f to %.0f at "
				 "t=%.2f s -- the car sill is at %.0f and the rider's feet at %.0f, and "
				 "one of them is inside %.0f uu of a floor that is about to move"),
			Old, New, Now, Sill, Feet, kRestageClearUu));
		return;
	}

	const FVector L = A->GetActorLocation();
	A->SetActorLocation(FVector(L.X, L.Y, L.Z + (New - Old)), /*bSweep=*/false);
	Landings[1].StagedAt = A->GetActorLocation();
	Landings[1].StagedSill = LandingSill(1);
	UE_LOG(LogTemp, Display,
		TEXT("[t3-lift stage] t=%.2f landing 2 moved from sill %.0f to sill %.0f"),
		Now, Old, double(LandingSill(1)));
}

// =====================================================================================
// deferred gates
// =====================================================================================

void ALiftTowerFunctionalTest::EvaluateDeferredGates(double Now)
{
	// A trip still open at the end still gets measured.
	if (bSegmentOpen)
	{
		bSegmentOpen = false;
		++SegmentIndex;
		const double Elapsed = SegmentLastMoveT - SegmentStartT;
		if (SegmentPathUu >= kMinSegmentUu && Elapsed > 1.0e-4)
		{
			const double Measured = SegmentPathUu / Elapsed;
			const double Want = double(Car.Speed);
			if (Measured < Want * (1.0 - kSpeedBand) || Measured > Want * (1.0 + kSpeedBand))
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheCarTravelsAtTheSpeedWrittenOnIt: trip %d covered %.0f uu in "
						 "%.2f s of moving, which is %.0f uu/s. The number written on "
						 "this car is %.0f uu/s, and the same one whichever way it is "
						 "going and however far it has to go"),
					SegmentIndex, SegmentPathUu, Elapsed, Measured, Want));
				return;
			}
		}
	}

	// ---------------------------------------------------- every call was eventually served
	for (const FPress& Pr : Presses)
	{
		if (Pr.ServedAt < 0.0)
		{
			const int32 Idx = IndexOfFloor(Pr.Floor);
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NoCallIsEverDropped: somebody stepped on the pad for floor %d at "
					 "t=%.2f s and the run ended at t=%.2f s without the lift ever "
					 "opening its doors there. The car sill is %.0f and that landing is "
					 "at %.0f. A call is never forgotten"),
				Pr.Floor, Pr.At, Now, CarSill(),
				Landings.IsValidIndex(Idx) ? LandingSill(Idx) : 0.0f));
			return;
		}
	}
	if (Presses.Num() < 7)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the walk recorded %d pad presses and the drive "
				 "makes seven; the route did not put the rider on every pad"),
			Presses.Num()));
		return;
	}

	// -------------------------------------------------------------- the whole service order
	if (Openings.Num() != kExpectedOpeningCount)
	{
		FString Seen;
		for (const FOpening& E : Openings)
		{
			Seen += FString::Printf(TEXT("%s%d"), Seen.IsEmpty() ? TEXT("") : TEXT(","), E.Floor);
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheLiftServesWhatIsOnTheWayBeforeItTurnsAround: the lift opened its "
				 "doors at [%s] and seven calls were made. A lift that keeps going the "
				 "way it is going, stopping at everything called on the way and only "
				 "turning round when there is nothing left ahead, serves every one of "
				 "them"), *Seen));
		return;
	}

	// ------------------------------------------------------------------------ the signs
	// The direction truth is read off what the lift ACTUALLY did next, so it can never
	// disagree with a correct lift -- and it still catches an arrow driven from the
	// car's velocity, which shows nothing while the car stands at a floor with somewhere
	// left to go.
	int32 LastNearest = -1;
	int32 LastDir = -99;
	double LastChangeAt = -100.0;
	for (const FSignFrame& F : SignTrace)
	{
		int32 TruthDir = 0;
		if (F.bAnythingOutstanding)
		{
			for (const FOpening& O : Openings)
			{
				if (O.At <= F.T)
				{
					continue;
				}
				if (FMath::Abs(double(O.LandingSill) - double(F.CarSill)) <= kSignLevelBandUu)
				{
					continue;
				}
				TruthDir = (double(O.LandingSill) > double(F.CarSill)) ? 1 : -1;
				break;
			}
		}
		if (F.NearestFloor != LastNearest || TruthDir != LastDir)
		{
			LastNearest = F.NearestFloor;
			LastDir = TruthDir;
			LastChangeAt = F.T;
		}
		if (F.T < kSignGraceS || F.T - LastChangeAt < kSignSettleS || F.bNearestAmbiguous)
		{
			continue;
		}
		for (int32 i = 0; i < Landings.Num() && i < 3; ++i)
		{
			if (F.Shown[i] != F.NearestFloor || F.Dir[i] != TruthDir)
			{
				const TCHAR* const Want = TruthDir > 0 ? TEXT("up")
					: (TruthDir < 0 ? TEXT("down") : TEXT("no arrow"));
				const TCHAR* const Got = F.Dir[i] > 0 ? TEXT("up")
					: (F.Dir[i] < 0 ? TEXT("down")
						: (F.Dir[i] == 0 ? TEXT("no arrow") : TEXT("an arrow pointing sideways")));
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheSignSaysWhichFloorAndWhichWay: at t=%.2f s the sign on "
						 "landing %d reads %d and shows %s, with the car sill at %.0f. "
						 "It should read %d and show %s -- the floor the car is nearest "
						 "to, and the way the lift is about to go next, on all three "
						 "landings"),
					F.T, Landings[i].Floor, F.Shown[i], Got, F.CarSill,
					F.NearestFloor, Want));
				return;
			}
		}
	}

	FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
		TEXT("The lift served every call in lift order and arrived level every time: "
			 "seven presses, stops at [1,2,3,3,2,1,3], %d trips measured against "
			 "%.0f uu/s"), SegmentIndex, Car.Speed));
}

// =====================================================================================
// tick + checkpoints
// =====================================================================================

void ALiftTowerFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || Landings.Num() != 3 || !Car.Actor.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	// BEFORE the gates, so a gate that finishes the test this frame still leaves the
	// state that led to it on the record. Negative indices mark a pre-schedule calib
	// line; nothing but a human reads them.
	while (NextEarlyCalib < kEarlyCalibCount && Now >= kEarlyCalibS[NextEarlyCalib])
	{
		LogCalib(-1 - NextEarlyCalib, Now);
		++NextEarlyCalib;
	}

	CheckSuppliedMachinery(Now);        if (!IsRunning()) { return; }
	CheckPinnedNumbers(Now);            if (!IsRunning()) { return; }
	CheckNothingWasMoved(Now);          if (!IsRunning()) { return; }
	CheckDoorsAndMotion(Now);           if (!IsRunning()) { return; }
	CheckRiderAndProgress(Now);         if (!IsRunning()) { return; }
	SamplePresses(Now);
	CheckLatchedLamps(Now);             if (!IsRunning()) { return; }
	SampleSigns(Now);
	AdvanceDrive(Now);                  if (!IsRunning()) { return; }

	bHavePrevFrame = true;
	PrevTime = Now;
	PrevSill = CarSill();
	PrevFraction = DoorFraction();

	if (bDriveComplete && DriveCompletedAt >= 0.0 && Now >= DriveCompletedAt + 0.5)
	{
		EvaluateDeferredGates(Now);
	}
}

void ALiftTowerFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString Seen;
	for (const FOpening& O : Openings)
	{
		Seen += FString::Printf(TEXT("%s%d"), Seen.IsEmpty() ? TEXT("") : TEXT(","), O.Floor);
	}
	// The six lamps, as the gate reads them: in-car 1/2/3 then landing 1/2/3, '*' lit
	// and '.' dark. A lamp that disagrees with the lift is the one thing this fixture
	// grades that leaves no other trace, and a run that dies before its first calib
	// point used to leave none at all.
	// CHARACTERS, not one-character string literals: FString::operator+= resolves a
	// TCHAR[2] through the contiguous-range overload, which appends the terminator too.
	FString Lamps;
	for (int32 i = 0; i < 3; ++i)
	{
		Lamps.AppendChar(LampLit(Car.Lamps[i].Get()) ? TEXT('*') : TEXT('.'));
	}
	Lamps.AppendChar(TEXT('/'));
	for (int32 i = 0; i < Landings.Num() && i < 3; ++i)
	{
		Lamps.AppendChar(LampLit(Landings[i].CallLamp.Get()) ? TEXT('*') : TEXT('.'));
	}
	int32 Served = 0;
	for (const FPress& Pr : Presses)
	{
		Served += (Pr.ServedAt >= 0.0) ? 1 : 0;
	}
	const ACharacter* const H = Hero.Get();
	const FVector At = H ? H->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-lift calib] cp%d t=%.2f step=%d sill=%.0f frac=%.2f floors=%.0f/%.0f/%.0f "
			 "presses=%d served=%d lamps=%s opened=[%s] hero=(%.0f,%.0f,%.0f)"),
		Index, Now, StepIndex, CarSill(), DoorFraction(),
		LandingSill(0), LandingSill(1), LandingSill(2), Presses.Num(), Served, *Lamps,
		*Seen, At.X, At.Y, At.Z);
}

void ALiftTowerFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}
	// THE SENTINEL. Reached only when the drive never finished at all -- every step of
	// it carries its own derived deadline, so this is a backstop, not the normal path.
	if (!bDriveComplete)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheLiftKeptTheRiderWaiting: the run reached its sentinel at t=%.0f s "
				 "with the drive stuck on step %d of %d. The car sill is %.0f, the doors "
				 "read %.2f open, %d pads have been pressed and the lift has opened its "
				 "doors %d time(s)"),
			TimeSeconds, StepIndex, Steps.Num(), CarSill(), DoorFraction(),
			Presses.Num(), Openings.Num()));
		return;
	}
	EvaluateDeferredGates(TimeSeconds);
}
