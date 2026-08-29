// Copyright CraftBench. All Rights Reserved.

#include "SpikeContactRespawnFunctionalTest.h"

#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr float kFullHealth = 100.0f;
	constexpr float kCostPerTouch = 25.0f;
	constexpr double kRespawnWithinS = 1.0;      // "within 1 second it reappears"
	constexpr double kHealthBackWithinS = 0.5;   // "within a further half second"
	constexpr double kOnPadCm = 120.0;           // "within 120 cm of that pad's centre"
	constexpr double kSlabSpeedCmS = 300.0;      // "a steady 300 cm per second"
	constexpr double kRailLengthCm = 600.0;      // "600 cm apart"

	// UNDISCLOSED: fixture geometry and clocking.
	constexpr double kCapsuleRadiusCm = 34.0;
	constexpr double kCapsuleHalfHeightCm = 88.0;
	constexpr double kRailBandCm = 90.0;         // how far off the rail line is "off it"
	constexpr double kWaypointReachedCm = 60.0;
	constexpr double kFreedomProbeCm = 400.0;
	/** How far the bystander must actually have walked by the end. A control that
	 *  stood still would make BystanderHealthStaysFull vacuous -- it would only
	 *  say that a submission did not damage a stationary object. */
	constexpr double kTwinMustWalkCm = 3000.0;
	constexpr double kReadoutTolerance = 1.0;

	const FVector kStartMarkAt(300.0, 0.0, 0.0);
	const FVector kPad1At(1100.0, -300.0, 0.0);
	const FVector kPad2At(1900.0, -300.0, 0.0);
	const FVector kHoldAt(2700.0, 0.0, 0.0);
	const FVector kLane1At(1100.0, 0.0, 0.0);
	const FVector kLane2At(1900.0, 0.0, 0.0);

	int32 FirstDigitRun(const FString& In)
	{
		FString Digits;
		for (const TCHAR C : In)
		{
			if (FChar::IsDigit(C))
			{
				Digits.AppendChar(C);
			}
			else if (!Digits.IsEmpty())
			{
				break;
			}
		}
		return Digits.IsEmpty() ? -1 : FCString::Atoi(*Digits);
	}
}

ASpikeContactRespawnFunctionalTest::ASpikeContactRespawnFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

AActor* ASpikeContactRespawnFunctionalTest::FindDriven() const
{
	// Re-resolved every frame: a destroy-and-respawn implementation is legal, so the
	// driven character is "the LaneCharacter that is not the ControlTwin" rather than
	// a pointer captured once.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("LaneCharacter")), Found);
	for (AActor* A : Found)
	{
		if (A != nullptr && !A->ActorHasTag(FName(TEXT("ControlTwin"))))
		{
			return A;
		}
	}
	return nullptr;
}

AActor* ASpikeContactRespawnFunctionalTest::FindTwin() const
{
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("LaneCharacter")), Found);
	for (AActor* A : Found)
	{
		if (A != nullptr && A->ActorHasTag(FName(TEXT("ControlTwin"))))
		{
			return A;
		}
	}
	return nullptr;
}

float ASpikeContactRespawnFunctionalTest::ReadHealth(AActor* Character) const
{
	if (Character == nullptr)
	{
		return -1.0f;
	}
	// By PROPERTY NAME on the supplied surface, so a subclass still answers.
	if (const FFloatProperty* P =
			FindFProperty<FFloatProperty>(Character->GetClass(), TEXT("Health")))
	{
		return P->GetPropertyValue_InContainer(Character);
	}
	return -1.0f;
}

int32 ASpikeContactRespawnFunctionalTest::ReadCurrentPadOrder() const
{
	AActor* const C = Course.Get();
	if (C == nullptr)
	{
		return -1;
	}
	if (const FIntProperty* P =
			FindFProperty<FIntProperty>(C->GetClass(), TEXT("CurrentPadOrder")))
	{
		return P->GetPropertyValue_InContainer(C);
	}
	return -1;
}

bool ASpikeContactRespawnFunctionalTest::ReadPadMarked(AActor* Pad) const
{
	if (Pad == nullptr)
	{
		return false;
	}
	if (const FBoolProperty* P =
			FindFProperty<FBoolProperty>(Pad->GetClass(), TEXT("bMarkedCurrent")))
	{
		return P->GetPropertyValue_InContainer(Pad);
	}
	return false;
}

int32 ASpikeContactRespawnFunctionalTest::ReadPadOrder(AActor* Pad) const
{
	if (Pad == nullptr)
	{
		return -1;
	}
	if (const FIntProperty* P =
			FindFProperty<FIntProperty>(Pad->GetClass(), TEXT("PadOrder")))
	{
		return P->GetPropertyValue_InContainer(Pad);
	}
	return -1;
}

int32 ASpikeContactRespawnFunctionalTest::ReadFloatingNumber(AActor* Character) const
{
	if (Character == nullptr)
	{
		return -1;
	}
	TArray<UTextRenderComponent*> Texts;
	Character->GetComponents<UTextRenderComponent>(Texts);
	for (UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetName() == TEXT("HealthReadout"))
		{
			return FirstDigitRun(T->Text.ToString());
		}
	}
	return -1;
}

bool ASpikeContactRespawnFunctionalTest::TouchingSlab(AActor* Character) const
{
	AActor* const S = Slab.Get();
	if (S == nullptr || Character == nullptr)
	{
		return false;
	}
	FVector Origin, Extent;
	S->GetActorBounds(true, Origin, Extent);
	// The slab's world box grown by the capsule: a character whose capsule centre is
	// inside it is in contact with the slab's surface.
	// ONE-SIDED BY CONSTRUCTION: the extra 25 cm means this window opens a frame or
	// two BEFORE the engine's own overlap edge can fire. That direction is the safe
	// one -- the fixture's window is the upper bound the submission's health drop is
	// checked against, so a legitimate hit can never read as "lost health while
	// nothing was touching it". The fixture may notice early, never late.
	const FVector Grown = Extent
		+ FVector(kCapsuleRadiusCm + 25.0, kCapsuleRadiusCm + 25.0,
				  kCapsuleHalfHeightCm + 25.0);
	const FVector P = Character->GetActorLocation();
	return FMath::Abs(P.X - Origin.X) <= Grown.X
		&& FMath::Abs(P.Y - Origin.Y) <= Grown.Y
		&& FMath::Abs(P.Z - Origin.Z) <= Grown.Z;
}

bool ASpikeContactRespawnFunctionalTest::StandingOnPad(AActor* Character, AActor* Pad) const
{
	if (Character == nullptr || Pad == nullptr)
	{
		return false;
	}
	return FVector::Dist2D(Character->GetActorLocation(), Pad->GetActorLocation())
		<= kOnPadCm;
}

bool ASpikeContactRespawnFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	auto One = [&](const TCHAR* Tag, TWeakObjectPtr<AActor>& Out) -> bool
	{
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsWithTag(World, FName(Tag), Found);
		if (Found.Num() != 1 || Found[0] == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the contact-lane course is not staged as "
					 "authored - expected exactly one actor tagged %s, found %d"),
				Tag, Found.Num()));
			return false;
		}
		Out = Found[0];
		return true;
	};
	if (!One(TEXT("SpikeLane"), Course)) { return false; }
	if (!One(TEXT("SlidingSpikes"), Slab)) { return false; }
	if (!One(TEXT("StartMark"), StartMark)) { return false; }

	TArray<AActor*> Pads;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LanePad")), Pads);
	if (Pads.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the contact-lane course is not staged as "
				 "authored - expected two pads, found %d"), Pads.Num()));
		return false;
	}
	for (AActor* P : Pads)
	{
		const int32 Order = ReadPadOrder(P);
		if (Order == 1) { Pad1 = P; }
		else if (Order == 2) { Pad2 = P; }
	}
	if (!Pad1.IsValid() || !Pad2.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: a readable course surface is missing - the two "
				 "pads do not carry PadOrder 1 and 2"));
		return false;
	}

	TArray<AActor*> Posts;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RailPost")), Posts);
	if (Posts.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the contact-lane course is not staged as "
				 "authored - expected two rail posts, found %d"), Posts.Num()));
		return false;
	}
	RailA = Posts[0]->GetActorLocation();
	RailB = Posts[1]->GetActorLocation();

	AActor* const Driven = FindDriven();
	Twin = FindTwin();
	if (Driven == nullptr || !Twin.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the contact-lane course is not staged as "
				 "authored - expected two LaneCharacters, exactly one of them the "
				 "ControlTwin"));
		return false;
	}
	// Owner bar: an invisible run is unreviewable, and each subject gets its own
	// literal so the verdict says WHICH one.
	auto Visible = [](AActor* A) -> bool
	{
		ACharacter* const C = Cast<ACharacter>(A);
		return C != nullptr && C->GetMesh() != nullptr
			&& C->GetMesh()->GetSkeletalMeshAsset() != nullptr
			&& C->GetMesh()->IsVisible();
	};
	if (!Visible(Driven))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the driven character is not visibly "
				 "represented"));
		return false;
	}
	if (!Visible(Twin.Get()))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the bystander character is not visibly "
				 "represented"));
		return false;
	}
	if (ReadHealth(Driven) < 0.0f || ReadHealth(Twin.Get()) < 0.0f
		|| ReadCurrentPadOrder() < 0)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: a readable course surface is missing - Health "
				 "or CurrentPadOrder could not be read"));
		return false;
	}

	// The bystander is possessed on purpose: an unpossessed Character is inert, and
	// an inert bystander would prove nothing about staying put.
	if (ACharacter* const TwinChar = Cast<ACharacter>(Twin.Get()))
	{
		TwinChar->SpawnDefaultController();
	}
	TwinStart = Twin->GetActorLocation();
	TwinWasAt = TwinStart;
	// The far end of its lane: straight along the corridor, staying on its own Y.
	TwinPatrolTo = FVector(TwinStart.X + 5600.0, TwinStart.Y, TwinStart.Z);
	SlabStart = Slab->GetActorLocation();
	return true;
}

void ASpikeContactRespawnFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}
	if (!ResolveStaging())
	{
		return;
	}

	// Every leg returns to the LANE CENTRE LINE before travelling in X. A straight
	// line from pad 1 to the hold point passes 30.7 cm from pad 2's box corner, and
	// the capsule is 34 cm -- so the DRIVE itself would clip pad 2, a compliant
	// submission would set CurrentPadOrder = 2, and the respawn-target gate would
	// FAIL correct work. Routing via (1100, 0) keeps every leg >= 200 cm clear.
	//
	// Freedom probes are driven in +X, never -X: respawn #1 is the start mark at
	// x = 300 and the platform begins at x = 0, so a 400 cm probe backwards would
	// walk out of the world.
	// DEADLINES ARE MEASURED FROM THE PATH, not written down. The first version
	// carried constants sized for a 3,200 cm lane; the lane is now 7,200 and the pads
	// are 3,400 apart instead of 600, and every one of those constants became a
	// failure of a correct submission for being slow. A deadline that has to be
	// re-tuned whenever the level changes is a deadline that will be wrong.
	const double SecondsPer1000 = 2.5;   // stock walk speed, x2 margin
	// Waiting to be hit FOUR times (100 health, 25 a touch) while the slab sweeps
	// back and forth, and then to reappear. Widened only in the safe direction: a
	// longer deadline can only ever excuse a submission that is genuinely stuck,
	// never one that is wrong.
	const double DeathAllowance = 60.0;
	const double Floor = 12.0;
	FVector Cursor = FindDriven() ? FindDriven()->GetActorLocation()
								  : FVector::ZeroVector;
	auto Leg = [&](std::initializer_list<FVector> Pts, const TCHAR* Label,
				   bool bDie = false, double Hold = 0.0)
	{
		FPhase P;
		P.Waypoints = Pts;
		P.Label = Label;
		double Length = 0.0;
		for (const FVector& Pt : Pts)
		{
			Length += FVector::Dist2D(Cursor, Pt);
			Cursor = Pt;
		}
		P.Deadline = FMath::Max(Floor,
			Length / 1000.0 * SecondsPer1000 + Hold + (bDie ? DeathAllowance : 0.0));
		P.bWaitForDeath = bDie;
		P.HoldSeconds = Hold;
		Phases.Add(MoveTemp(P));
	};
	Leg({kHoldAt}, TEXT("walk to the slab"), true);
	Leg({kHoldAt + FVector(kFreedomProbeCm, 0.0, 0.0)}, TEXT("first freedom probe"),
		false, 1.0);
	Leg({kLane1At, kPad1At, kLane1At, kHoldAt}, TEXT("via pad 1 to the slab"), true);
	Leg({FVector(kFreedomProbeCm, 0.0, 0.0)}, TEXT("second freedom probe"),
		false, 1.0);
	Leg({kLane1At, kLane2At, kPad2At, kLane2At, kLane1At, kPad1At, kLane1At, kHoldAt},
		TEXT("via pad 2 then back over pad 1"), true);
	Leg({FVector(kFreedomProbeCm, 0.0, 0.0)}, TEXT("third freedom probe"),
		false, 1.0);

	LastHealth = ReadHealth(FindDriven());
	// 45 gauging instants 8 s apart, plus a SENTINEL far past any real grade. The
	// base declares success the moment the last scheduled checkpoint is crossed, so
	// without the sentinel a run whose phases are still going would report a green
	// pass having graded nothing (measured on the rail task, 2026-08-17).
	TArray<double> Schedule;
	for (int32 i = 0; i < 45; ++i)
	{
		Schedule.Add(2.0 + 8.0 * i);
	}
	Schedule.Add(600.0);
	TimeLimitMargin = 6.0f;
	SetCheckpointSchedule(Schedule);
	PhaseIndex = 0;
	PhaseStarted = 0.0;
}

void ASpikeContactRespawnFunctionalTest::AdvancePhase(double Now)
{
	++PhaseIndex;
	Waypoint = 0;
	PhaseStarted = Now;
	HoldUntil = -1.0;
	if (PhaseIndex >= Phases.Num())
	{
		FinalGrade();
	}
}

void ASpikeContactRespawnFunctionalTest::FinalGrade()
{
	// Every row below is VACUOUSLY TRUE if its leg never happened, so each carries an
	// explicit precondition-reached assert with its own substring. A run that quietly
	// skipped a segment must not read as a run that passed it.
	if (ContactWindows < 1)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("OneDeductionPerContact: no contact window ever opened, so per-touch "
				 "cost was never measured"));
		return;
	}
	if (ContactWindows < 2)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("SecondContactCostsAnother25: the slab only ever touched the "
				 "character once"));
		return;
	}
	if (SlabMovedAfterContactAt < 0.0 || !bSlabEverMoved)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("SpikesKeepSlidingAfterContact: the spiked slab stopped sliding "
				 "after it hurt someone"));
		return;
	}
	if (!bPad1Entered)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TouchingTheFirstPadMakesItCurrent: walking onto the first pad did "
				 "not make it current"));
		return;
	}
	if (!bPad2Entered)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheSecondPadTakesOver: the character never reached the second pad"));
		return;
	}
	if (!bWalkedBackOntoPad1)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("WalkingBackDoesNotRollBack: the character never walked back onto "
				 "the earlier pad"));
		return;
	}
	if (bRollBackSeen)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("WalkingBackDoesNotRollBack: walking back onto the earlier pad "
				 "rolled the current pad backwards"));
		return;
	}
	if (Deaths < 3)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ZeroHealthSendsYouBack: the character reached zero health and was "
				 "never sent back (%d death(s) completed of 3)"), Deaths));
		return;
	}
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("the slab slid its rail and cost 25 a touch, zero health sent the "
			 "character back to its latest pad each time, walking back never rolled "
			 "the pad progress backwards, and the bystander finished untouched"));
}

void ASpikeContactRespawnFunctionalTest::LogCalib(int32 Index, double Now) const
{
	AActor* const Driven = FindDriven();
	UE_LOG(LogTemp, Display,
		TEXT("[t1-spike calib] cp%d t=%.2f phase=%d hp=%.0f num=%d pad=%d "
			 "marks=%d%d windows=%d deaths=%d slabX=%.0f twinHp=%.0f"),
		Index, Now, PhaseIndex, ReadHealth(Driven), ReadFloatingNumber(Driven),
		ReadCurrentPadOrder(), ReadPadMarked(Pad1.Get()) ? 1 : 0,
		ReadPadMarked(Pad2.Get()) ? 1 : 0, ContactWindows, Deaths,
		Slab.IsValid() ? Slab->GetActorLocation().X : 0.0, ReadHealth(Twin.Get()));
}

void ASpikeContactRespawnFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base first: checkpoint clock + timeout machinery

	if (!IsRunning() || !Slab.IsValid() || !Course.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	AActor* const Driven = FindDriven();
	AActor* const TwinNow = Twin.Get();
	if (Driven == nullptr || TwinNow == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("CharactersStayResolvable: a graded character could no longer be "
				 "resolved in the level"));
		return;
	}

	// ---- SLAB ----
	const FVector SlabAt = Slab->GetActorLocation();
	if (!bSlabEverMoved && FVector::Dist(SlabAt, SlabStart) > 20.0)
	{
		bSlabEverMoved = true;
	}
	{
		// Distance from the rail segment: the slab may travel it, never leave it.
		const FVector AB = RailB - RailA;
		const double T = FMath::Clamp(
			FVector::DotProduct(SlabAt - RailA, AB) / FMath::Max(AB.SizeSquared(), 1.0),
			0.0, 1.0);
		const FVector Closest = RailA + AB * T;
		if (FVector::Dist2D(SlabAt, Closest) > kRailBandCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SpikesStayOnTheirRail: the spiked slab left its rail (%.0f cm "
					 "off the line between its posts)"),
				FVector::Dist2D(SlabAt, Closest)));
			return;
		}
	}

	// ---- DAMAGE ----
	const float Health = ReadHealth(Driven);
	const bool bTouching = TouchingSlab(Driven);
	if (bTouching && !bWasTouching)
	{
		++ContactWindows;
		HealthAtWindowOpen = Health;
		DeductionsThisWindow = 0;
		if (FirstContactAt < 0.0) { FirstContactAt = Now; }
	}
	if (!bTouching && bWasTouching && FirstContactAt >= 0.0)
	{
		// The slab must keep sliding after it hurts somebody.
		SlabMovedAfterContactAt = Now;
	}

	if (Health < LastHealth - 0.01f)
	{
		const float Lost = LastHealth - Health;
		if (!bTouching)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("HealthOnlyChangesOnContact: the character lost health while "
					 "nothing was touching it (%.0f gone with the slab clear)"), Lost));
			return;
		}
		++DeductionsThisWindow;
		if (!FMath::IsNearlyEqual(Lost, kCostPerTouch, 0.5f))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("FirstContactCostsExactly25: a touch of the slab did not cost "
					 "exactly 25 (it cost %.1f)"), Lost));
			return;
		}
		if (DeductionsThisWindow > 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("OneDeductionPerContact: a single touch of the slab cost more "
					 "than one 25 (%d deductions in one window)"),
				DeductionsThisWindow));
			return;
		}
	}
	if (Health > LastHealth + 0.01f && !bAwaitingRespawn && Deaths > 0
		&& Now > DeathAt + kRespawnWithinS + kHealthBackWithinS + 1.0)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("HealthOnlyChangesOnContact: the character gained health with no "
				 "death to explain it"));
		return;
	}
	if (ContactWindows == 0 && Health < kFullHealth - 0.01f)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("HealthFullUntilFirstContact: the character lost health before the "
				 "slab ever touched it (%.0f health, no contact yet)"), Health));
		return;
	}

	// WALK THE BYSTANDER. Up its lane and back, for as long as the run lasts, so it
	// is inside the hazard's stretch of corridor the whole time without ever being on
	// the rail.
	if (ACharacter* const TwinChar = Cast<ACharacter>(TwinNow))
	{
		const FVector Goal = bTwinOutbound ? TwinPatrolTo : TwinStart;
		const FVector Flat(Goal.X - TwinChar->GetActorLocation().X,
			Goal.Y - TwinChar->GetActorLocation().Y, 0.0);
		if (Flat.Size2D() <= 150.0)
		{
			bTwinOutbound = !bTwinOutbound;
		}
		else
		{
			TwinChar->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		}
	}

	// ---- CONTROL ----
	const float TwinHealth = ReadHealth(TwinNow);
	if (TwinHealth < kFullHealth - 0.01f && !TouchingSlab(TwinNow))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("BystanderHealthStaysFull: the bystander character lost health "
				 "without ever being touched (%.0f)"), TwinHealth));
		return;
	}
	// THE BYSTANDER HAS TO BE EXERCISED, not parked. A control that never moves
	// proves only that a submission did not damage a stationary object; this one
	// walks the length of the hazard on the lane beside it, so anything that hurts by
	// radius, by timer, or globally catches it. The gate that used to live here
	// required the opposite -- that it never move -- which is why it proved nothing.
	TwinTravelled += FVector::Dist2D(TwinNow->GetActorLocation(), TwinWasAt);
	TwinWasAt = TwinNow->GetActorLocation();

	// The bystander must stay off the rail: if it wandered into the slab's path the
	// control would be measuring a collision rather than the absence of one.
	if (TouchingSlab(TwinNow))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the bystander walked into the slab; its lane "
				 "is supposed to run clear of the rail, so the control is not "
				 "controlling anything"));
		return;
	}

	// ---- LEGIBILITY ----
	{
		const int32 Shown = ReadFloatingNumber(Driven);
		if (Shown >= 0 && FMath::Abs(static_cast<double>(Shown) - Health)
			> kCostPerTouch + kReadoutTolerance)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheFloatingNumberMatchesTheHealth: the number floating over the "
					 "driven character does not match its health (shows %d, health "
					 "%.0f)"), Shown, Health));
			return;
		}
		const int32 TwinShown = ReadFloatingNumber(TwinNow);
		if (TwinShown >= 0 && FMath::Abs(static_cast<double>(TwinShown) - TwinHealth) > 1.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheFloatingNumberMatchesTheHealth: the number floating over the "
					 "bystander character does not match its health (shows %d, health "
					 "%.0f)"), TwinShown, TwinHealth));
			return;
		}
	}

	// ---- PADS ----
	const int32 PadNow = ReadCurrentPadOrder();
	if (StandingOnPad(Driven, Pad1.Get()))
	{
		if (bPad2Entered) { bWalkedBackOntoPad1 = true; }
		else if (bPad1Entered) { bReTouchedCurrentPad = true; }
		bPad1Entered = true;
	}
	if (StandingOnPad(Driven, Pad2.Get()))
	{
		if (bPad2Entered) { bReTouchedCurrentPad = true; }
		bPad2Entered = true;
	}
	if (bPad2Entered && PadNow == 1)
	{
		bRollBackSeen = true;
	}
	if (PadNow >= 1)
	{
		const bool bMark1 = ReadPadMarked(Pad1.Get());
		const bool bMark2 = ReadPadMarked(Pad2.Get());
		if ((PadNow == 1 && (!bMark1 || bMark2)) || (PadNow == 2 && (!bMark2 || bMark1)))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheCurrentPadIsTheMarkedOne: the marked pad is not the one the "
					 "course says is current (course says %d, marks are %d%d)"),
				PadNow, bMark1 ? 1 : 0, bMark2 ? 1 : 0));
			return;
		}
	}

	// ---- DEATH AND RESPAWN ----
	if (Health <= 0.01f && !bAwaitingRespawn)
	{
		++Deaths;
		DeathAt = Now;
		bAwaitingRespawn = true;
		RespawnSeenAt = -1.0;
		if (PadNow == 2)
		{
			RespawnExpectedAt = Pad2->GetActorLocation();
			RespawnExpectedName = TEXT("the second pad");
		}
		else if (PadNow == 1)
		{
			RespawnExpectedAt = Pad1->GetActorLocation();
			RespawnExpectedName = TEXT("the first pad");
		}
		else
		{
			RespawnExpectedAt = StartMark->GetActorLocation();
			RespawnExpectedName = TEXT("the start mark");
		}
	}
	if (bAwaitingRespawn)
	{
		const double Since = Now - DeathAt;
		const bool bBack = FVector::Dist2D(Driven->GetActorLocation(),
			RespawnExpectedAt) <= kOnPadCm;
		if (bBack && RespawnSeenAt < 0.0)
		{
			RespawnSeenAt = Now;
			RespawnSeenLocation = Driven->GetActorLocation();
		}
		if (Since > kRespawnWithinS && RespawnSeenAt < 0.0)
		{
			// Where did it end up instead? Name the segment the answer got wrong.
			const TCHAR* const Gate =
				(Deaths == 1) ? TEXT("DeathBeforeAnyPadReturnsToTheStart")
				: (Deaths == 2 ? TEXT("DeathAfterTheFirstPadReturnsThere")
							   : TEXT("DeathAfterTheWalkBackReturnsToTheSecondPad"));
			const TCHAR* const What =
				(Deaths == 1) ? TEXT("first death did not return the character to the "
								     "start mark")
				: (Deaths == 2 ? TEXT("death after the first pad did not return the "
								      "character there")
							   : TEXT("death after walking back did not return the "
								      "character to the second pad"));
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("%s: the %s (expected %s, ended %.0f cm away)"),
				Gate, What, RespawnExpectedName,
				FVector::Dist2D(Driven->GetActorLocation(), RespawnExpectedAt)));
			return;
		}
		if (RespawnSeenAt >= 0.0
			&& Now > RespawnSeenAt + kHealthBackWithinS
			&& Health < kFullHealth - 0.01f)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("HealthIsFullAgainAfterRespawn: the character came back with the "
					 "wrong amount of health (%.0f)"), Health));
			return;
		}
		if (RespawnSeenAt >= 0.0 && Health >= kFullHealth - 0.01f)
		{
			bAwaitingRespawn = false;
			// The phase that was waiting for a death is now done.
			if (Phases.IsValidIndex(PhaseIndex) && Phases[PhaseIndex].bWaitForDeath)
			{
				AdvancePhase(Now);
			}
		}
	}

	// ---- DRIVE ----
	if (Phases.IsValidIndex(PhaseIndex))
	{
		FPhase& P = Phases[PhaseIndex];
		ACharacter* const DrivenChar = Cast<ACharacter>(Driven);
		const bool bWaypointsLeft = P.Waypoints.IsValidIndex(Waypoint);
		if (bWaypointsLeft && DrivenChar != nullptr && !bAwaitingRespawn)
		{
			FVector Target = P.Waypoints[Waypoint];
			if (P.Label != nullptr && FCString::Strstr(P.Label, TEXT("freedom")) != nullptr)
			{
				// Probes are relative to wherever the respawn put the character, and
				// always in +X so the walk cannot leave the platform.
				Target = RespawnSeenLocation + FVector(kFreedomProbeCm, 0.0, 0.0);
			}
			const FVector Here = DrivenChar->GetActorLocation();
			const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
			if (Flat.Size2D() <= kWaypointReachedCm)
			{
				++Waypoint;
				if (!P.Waypoints.IsValidIndex(Waypoint) && P.HoldSeconds > 0.0)
				{
					HoldUntil = Now + P.HoldSeconds;
				}
			}
			else
			{
				DrivenChar->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
			}
		}
		else if (!bWaypointsLeft && !P.bWaitForDeath)
		{
			if (HoldUntil < 0.0 || Now >= HoldUntil)
			{
				// A freedom probe just finished: nothing may have pulled the character
				// back to the pad it respawned on.
				if (P.Label != nullptr
					&& FCString::Strstr(P.Label, TEXT("freedom")) != nullptr)
				{
					const double Moved = FVector::Dist2D(Driven->GetActorLocation(),
						RespawnExpectedAt);
					if (Moved < kFreedomProbeCm * 0.5)
					{
						FinishTest(EFunctionalTestResult::Failed, FString::Printf(
							TEXT("FreeToWalkAwayAfterRespawn: the character kept being "
								 "pulled back to its pad (walked away and is still "
								 "%.0f cm from it)"), Moved));
						return;
					}
				}
				AdvancePhase(Now);
			}
		}
		if (Phases.IsValidIndex(PhaseIndex)
			&& Now > PhaseStarted + Phases[PhaseIndex].Deadline)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DriveReachedItsWaypoints: a drive phase ran out of time before "
					 "reaching its waypoint (%s, %.0f s)"),
				Phases[PhaseIndex].Label, Now - PhaseStarted));
			return;
		}
	}

	bWasTouching = bTouching;
	LastHealth = Health;
}

void ASpikeContactRespawnFunctionalTest::OnCheckpoint(int32 Index, double TimeSeconds)
{
	if (!Course.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : TimeSeconds;
	LogCalib(Index, Now);

	// The slab has to be moving on its own from the start.
	if (Index >= 2 && !bSlabEverMoved)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("SpikesMoveOnTheirOwn: the spiked slab never moved on its own"));
		return;
	}

	// The SENTINEL. Reaching it means the phases never finished, and without it the
	// base would declare success the moment the last real checkpoint passed.
	if (Index < 45)   // the sentinel; the schedule now runs 45 gauging instants
	{
		return;
	}
	if (PhaseIndex < Phases.Num())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("DriveReachedItsWaypoints: the run never finished its legs (stopped "
				 "in phase %d of %d, %d death(s), %d contact window(s))"),
			PhaseIndex, Phases.Num(), Deaths, ContactWindows));
		return;
	}
	// THE CONTROL HAS TO HAVE BEEN EXERCISED. A bystander that stood still makes
	// BystanderHealthStaysFull vacuous -- it would say only that a submission did not
	// damage a stationary object, which the owner rightly called terrible design.
	if (TwinTravelled < kTwinMustWalkCm)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the bystander only walked %.0f cm of its lane "
				 "(needs %.0f), so the never-touched-never-hurt check proved nothing. "
				 "That is the yard's fault, not the submission's"),
			TwinTravelled, kTwinMustWalkCm));
		return;
	}
}
