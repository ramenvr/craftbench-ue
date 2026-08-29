// Copyright CraftBench. All Rights Reserved.

#include "PlateDoorFunctionalTest.h"

#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// All disclosed in the prompt. None is a private threshold.
	constexpr double kOpenDeg      = 80.0;    // "at least 80 degrees from shut"
	constexpr double kOpenDeadlineS = 2.0;    // "within 2 seconds of stepping onto the plate"
	constexpr double kShutDeg      = 10.0;    // "within 10 degrees of shut"
	constexpr double kRepeatDeg    = 10.0;    // "the same open position, within 10 degrees"
	constexpr double kOnPlateCm    = 100.0;   // "within 100 cm of its centre"
	constexpr double kMaxDegPerSec = 720.0;   // "never faster than 720 degrees per second"
	constexpr double kMaxCmPerSec  = 3000.0;  // "or 3000 cm per second"

	// Measured consequences of the staged scene, not thresholds of their own.
	constexpr double kOffPlateCm   = 300.0;   // clear of the plate at a depart checkpoint
	constexpr double kStartClearCm = 400.0;   // where the hero starts / departs to
	constexpr double kControlKeepCm = 200.0;  // the hero never goes near the control plate
	// A real swing carries the panel over a metre because it is hinge-offset; this
	// floor only catches a panel that turned WITHOUT moving.
	constexpr double kTravelCm     = 50.0;
}

APlateDoorFunctionalTest::APlateDoorFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

UStaticMeshComponent* APlateDoorFunctionalTest::ResolvePanel(AActor* Door) const
{
	if (Door == nullptr)
	{
		return nullptr;
	}
	TArray<UStaticMeshComponent*> Meshes;
	Door->GetComponents<UStaticMeshComponent>(Meshes);
	if (Meshes.Num() == 0)
	{
		return nullptr;
	}

	// 1. The declared thing.
	for (UStaticMeshComponent* M : Meshes)
	{
		if (M && M->GetName() == TEXT("DoorPanel"))
		{
			return M;
		}
	}
	// 2. Else the largest by LOCAL bounds volume, ties by name ascending, so the
	//    result never depends on component enumeration order.
	Meshes.Sort([](const UStaticMeshComponent& A, const UStaticMeshComponent& B)
	{
		const FVector EA = A.Bounds.BoxExtent;
		const FVector EB = B.Bounds.BoxExtent;
		const double VA = EA.X * EA.Y * EA.Z;
		const double VB = EB.X * EB.Y * EB.Z;
		if (!FMath::IsNearlyEqual(VA, VB, 1.0))
		{
			return VA > VB;
		}
		return A.GetName() < B.GetName();
	});
	return Meshes[0];
}

bool APlateDoorFunctionalTest::InitProbe(FDoorProbe& Probe, AActor* Door,
	const TCHAR* Which)
{
	Probe.Actor = Door;
	Probe.Panel = ResolvePanel(Door);
	if (!Probe.Panel.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("PanelIsTheGradedPart: the %s door has no visible panel to swing"),
			Which));
		return false;
	}
	Probe.ClosedRot = Probe.Panel->GetComponentRotation();
	Probe.ClosedLoc = Probe.Panel->GetComponentLocation();
	Probe.LastAngle = 0.0;
	Probe.LastLoc = Probe.ClosedLoc;
	Probe.bSeeded = false;
	return true;
}

FString APlateDoorFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	TArray<FString> Problems;

	// Half one: the pawn's own Enhanced Input actions. Read by property name so
	// a renamed or subclassed pawn still answers.
	if (Hero.IsValid())
	{
		TArray<FString> Unbound;
		for (const TCHAR* Name : { TEXT("MoveAction"), TEXT("LookAction"),
								   TEXT("MouseLookAction"), TEXT("JumpAction") })
		{
			const FObjectProperty* Prop =
				FindFProperty<FObjectProperty>(Hero->GetClass(), Name);
			if (Prop == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(Hero.Get()) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Problems.Add(FString::Printf(
				TEXT("the pawn (%s) has nothing bound to %s"),
				*Hero->GetClass()->GetName(), *FString::Join(Unbound, TEXT(", "))));
		}
	}

	// Half two: a mapping context has to be applied, or no key reaches any of
	// those actions even when all four are set.
	const AGameModeBase* GameMode = World->GetAuthGameMode();
	const UClass* PCClass =
		GameMode != nullptr ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the ")
					 TEXT("player gets a bare APlayerController"));
	}
	else if (const FArrayProperty* Contexts = FindFProperty<FArrayProperty>(
				 PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* Element = CastField<FObjectProperty>(Contexts->Inner);
		FScriptArrayHelper Helper(
			Contexts, Contexts->ContainerPtrToValuePtr<void>(
						  PCClass->GetDefaultObject()));
		int32 Applied = 0;
		for (int32 Index = 0; Element != nullptr && Index < Helper.Num(); ++Index)
		{
			if (Element->GetObjectPropertyValue(Helper.GetElementPtr(Index)) != nullptr)
			{
				++Applied;
			}
		}
		if (Applied == 0)
		{
			Problems.Add(FString::Printf(
				TEXT("%s applies no input mapping context"), *PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s carries no DefaultMappingContexts, so nothing here can ")
			TEXT("confirm a key is mapped"), *PCClass->GetName()));
	}

	return FString::Join(Problems, TEXT("; "));
}

void APlateDoorFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}

	// Identity by TAG, never by class: the agent may subclass or rename.
	TArray<AActor*> Heroes, Plates, Doors;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("PlateHero")), Heroes);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("ContactPlate")), Plates);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("SwingDoor")), Doors);

	if (Heroes.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected exactly one PlateHero, found %d"),
			Heroes.Num()));
		return;
	}
	if (Plates.Num() != 2 || Doors.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected two ContactPlate and two ")
			TEXT("SwingDoor actors, found %d and %d"), Plates.Num(), Doors.Num()));
		return;
	}

	Hero = Cast<ACharacter>(Heroes[0]);
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the PlateHero actor is not a character"));
		return;
	}
	if (Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the hero has no visible body, so a human ")
			TEXT("reviewing the recording would see nothing"));
		return;
	}

	// This fixture drives the hero through AddMovementInput and never presses a
	// key, so a level whose keyboard lane is dead grades exactly like a healthy
	// one -- which is how this map shipped authored, lit and certified while
	// being completely uncontrollable to play. Both halves are asserted, by
	// PROPERTY NAME rather than class, so a subclassed or renamed pawn still
	// answers. This is a HARNESS precondition: the input lane is substrate we
	// ship, never anything the agent was asked to write.
	if (const FString Unwired = DescribeBrokenPlayerInput(World); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. ")
			TEXT("The graded drive would still pass, so fix the substrate, not the ")
			TEXT("task."), *Unwired));
		return;
	}

	// Which plate is graded: the one nearer the hero's start. Its own LinkedDoor
	// says which door belongs to it, so the pairing is read from the level rather
	// than assumed from ordering.
	const FVector HeroAt = Hero->GetActorLocation();
	const bool bFirstIsNearer =
		FVector::Dist2D(HeroAt, Plates[0]->GetActorLocation())
		<= FVector::Dist2D(HeroAt, Plates[1]->GetActorLocation());
	GradedPlate = bFirstIsNearer ? Plates[0] : Plates[1];
	ControlPlate = bFirstIsNearer ? Plates[1] : Plates[0];

	AActor* GradedDoorActor = nullptr;
	AActor* ControlDoorActor = nullptr;
	for (AActor* P : Plates)
	{
		AActor* Linked = nullptr;
		for (TFieldIterator<FObjectProperty> It(P->GetClass()); It; ++It)
		{
			if (It->GetName() == TEXT("LinkedDoor"))
			{
				Linked = Cast<AActor>(It->GetObjectPropertyValue_InContainer(P));
				break;
			}
		}
		if (Linked == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: plate %s has no LinkedDoor set"),
				*P->GetName()));
			return;
		}
		if (P == GradedPlate.Get()) { GradedDoorActor = Linked; }
		else                        { ControlDoorActor = Linked; }
	}
	if (GradedDoorActor == nullptr || ControlDoorActor == nullptr
		|| GradedDoorActor == ControlDoorActor)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the two plates do not point at two ")
			TEXT("distinct doors"));
		return;
	}

	if (!InitProbe(Graded, GradedDoorActor, TEXT("graded"))) { return; }
	if (!InitProbe(Control, ControlDoorActor, TEXT("second"))) { return; }

	Phase = EPlateDoorPhase::Settle;
	SetCheckpointSchedule({ 0.8, 4.8, 6.4, 9.4, 13.1, 14.7, 17.7 });
}

double APlateDoorFunctionalTest::Angle(const FDoorProbe& Probe) const
{
	if (!Probe.Panel.IsValid())
	{
		return 0.0;
	}
	// YAW — about the vertical axis, which is what the prompt discloses.
	return FMath::Abs(FMath::FindDeltaAngleDegrees(
		Probe.ClosedRot.Yaw, Probe.Panel->GetComponentRotation().Yaw));
}

double APlateDoorFunctionalTest::Travel(const FDoorProbe& Probe) const
{
	if (!Probe.Panel.IsValid())
	{
		return 0.0;
	}
	return FVector::Dist(Probe.Panel->GetComponentLocation(), Probe.ClosedLoc);
}

double APlateDoorFunctionalTest::HeroDist2D(const AActor* Plate) const
{
	if (!Hero.IsValid() || Plate == nullptr)
	{
		return TNumericLimits<double>::Max();
	}
	return FVector::Dist2D(Hero->GetActorLocation(), Plate->GetActorLocation());
}

bool APlateDoorFunctionalTest::OnPlate(const AActor* Plate) const
{
	if (!Hero.IsValid())
	{
		return false;
	}
	const UCharacterMovementComponent* const CMC = Hero->GetCharacterMovement();
	const bool bGrounded = CMC != nullptr && !CMC->IsFalling();
	return HeroDist2D(Plate) <= kOnPlateCm && bGrounded;
}

void APlateDoorFunctionalTest::Tick(float DeltaSeconds)
{
	// The continuity guard runs BEFORE the base clock so the frame that crosses
	// the final checkpoint is still covered.
	const double Budget = FMath::Max(DeltaSeconds, KINDA_SMALL_NUMBER);
	FDoorProbe* const Probes[2] = { &Graded, &Control };
	const TCHAR* const Names[2] = { TEXT("graded"), TEXT("second") };
	for (int32 i = 0; i < 2; ++i)
	{
		FDoorProbe& P = *Probes[i];
		if (!P.Panel.IsValid())
		{
			continue;
		}
		const double NowAngle = Angle(P);
		const FVector NowLoc = P.Panel->GetComponentLocation();
		if (!P.bSeeded)
		{
			// SEED from this sample. A default-constructed baseline would read
			// 335 cm of travel on frame 1 and FAIL everything, reference included.
			P.LastAngle = NowAngle;
			P.LastLoc = NowLoc;
			P.bSeeded = true;
			continue;
		}
		const double DegStep = FMath::Abs(NowAngle - P.LastAngle);
		const double CmStep = FVector::Dist(NowLoc, P.LastLoc);
		if (DegStep > kMaxDegPerSec * Budget || CmStep > kMaxCmPerSec * Budget)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorSwingsSmoothly: the %s door jumped %.1f degrees and ")
				TEXT("%.1f cm in one frame of %.4f s (the level allows %.0f ")
				TEXT("degrees and %.0f cm per second); the door has to travel, ")
				TEXT("not snap"),
				Names[i], DegStep, CmStep, Budget, kMaxDegPerSec, kMaxCmPerSec));
			return;
		}
		P.LastAngle = NowAngle;
		P.LastLoc = NowLoc;
	}

	Super::Tick(DeltaSeconds);

	if (!Hero.IsValid() || !GradedPlate.IsValid())
	{
		return;
	}

	// Track the DISCLOSED 2 s open deadline. Both edges are recorded per frame,
	// because a checkpoint sample cannot see when either happened.
	const bool bOn = OnPlate(GradedPlate.Get());
	if (bOn && PlateEnteredT < 0.0)
	{
		PlateEnteredT = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
		ReachedOpenT = -1.0;
	}
	else if (!bOn && PlateEnteredT >= 0.0 && Angle(Graded) <= kShutDeg)
	{
		PlateEnteredT = -1.0;          // cycle closed; arm for the next visit
	}
	if (PlateEnteredT >= 0.0 && ReachedOpenT < 0.0 && Angle(Graded) >= kOpenDeg)
	{
		ReachedOpenT = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	}

	// The walk drive. Movement input is consumed per frame, so it is re-applied
	// every tick; the world is NEVER ticked here.
	const FVector HeroAt = Hero->GetActorLocation();
	const FVector PlateAt = GradedPlate->GetActorLocation();

	if (Phase == EPlateDoorPhase::Approach1 || Phase == EPlateDoorPhase::Approach2)
	{
		if (HeroDist2D(GradedPlate.Get()) <= kOnPlateCm)
		{
			// Stop driving; braking settles the hero on the pad.
			Phase = (Phase == EPlateDoorPhase::Approach1)
				? EPlateDoorPhase::Stand1 : EPlateDoorPhase::Stand2;
		}
		else
		{
			FVector Dir = PlateAt - HeroAt;
			Dir.Z = 0.0;
			Hero->AddMovementInput(Dir.GetSafeNormal(), 1.0f);
		}
	}
	else if (Phase == EPlateDoorPhase::Depart1 || Phase == EPlateDoorPhase::Depart2)
	{
		if (HeroDist2D(GradedPlate.Get()) >= kStartClearCm)
		{
			Phase = EPlateDoorPhase::Done;
		}
		else
		{
			FVector Dir = HeroAt - PlateAt;
			Dir.Z = 0.0;
			Hero->AddMovementInput(Dir.GetSafeNormal(), 1.0f);
		}
	}
}

bool APlateDoorFunctionalTest::GaugeControl(int32 i)
{
	// The control gauge runs at EVERY checkpoint, with the index in the literal so
	// "broke while the graded door was open" and "was already broken at play
	// start" are different strings.
	const double ControlAngle = Angle(Control);
	if (ControlAngle > kShutDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("SecondPairNeverMoves: expected the untouched door to stay shut ")
			TEXT("at cp%d, and it was %.1f degrees open (allowed %.0f); a plate ")
			TEXT("moves only its own door"),
			i, ControlAngle, kShutDeg));
		return false;
	}
	const double ControlDist = HeroDist2D(ControlPlate.Get());
	if (OnPlate(ControlPlate.Get()) || ControlDist < kControlKeepCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("SecondPairNeverMoves: expected nobody to go near the second ")
			TEXT("plate at cp%d, and the character was %.0f cm from it (the test ")
			TEXT("keeps it beyond %.0f)"),
			i, ControlDist, kControlKeepCm));
		return false;
	}
	return true;
}

void APlateDoorFunctionalTest::OnCheckpoint(int32 i, double T)
{
	if (!Hero.IsValid() || !Graded.Panel.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: a graded actor went away before cp%d"), i));
		return;
	}

	const double G = Angle(Graded);
	const double Tr = Travel(Graded);
	const double D = HeroDist2D(GradedPlate.Get());

	UE_LOG(LogTemp, Display,
		TEXT("[t1-plate-door calib] cp%d t=%.2f graded=%.1f travel=%.0f ")
		TEXT("control=%.1f heroDist=%.0f onPlate=%d phase=%d"),
		i, T, G, Tr, Angle(Control), D, OnPlate(GradedPlate.Get()) ? 1 : 0,
		(int32)Phase);

	if (!GaugeControl(i))
	{
		return;
	}

	switch (i)
	{
	case 0:
		// Precondition, fail-only: banks no credit, but it is the only scored
		// defence against a door that is simply open from the start.
		if (G > kShutDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorShutBeforeContact: expected the door to be shut before ")
				TEXT("anyone stood on a plate, and it was %.1f degrees open"), G));
			return;
		}
		Phase = EPlateDoorPhase::Approach1;
		break;

	case 1:
		if (!OnPlate(GradedPlate.Get()))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the test could not reach the plate on ")
				TEXT("the first approach (%.0f cm away at t=%.2f)"), D, T));
			return;
		}
		if (G < kOpenDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorOpensWhileOccupied: expected the door to be open while ")
				TEXT("the character stood on its plate (cycle 1), and it was ")
				TEXT("%.1f degrees from shut (the level asks for %.0f)"),
				G, kOpenDeg));
			return;
		}
		if (Tr < kTravelCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PanelIsTheGradedPart: expected the door's own panel to move, ")
				TEXT("not just turn in place; it is %.0f cm from where it started ")
				TEXT("(the level asks for %.0f)"), Tr, kTravelCm));
			return;
		}
		if (ReachedOpenT < 0.0 || PlateEnteredT < 0.0
			|| (ReachedOpenT - PlateEnteredT) > kOpenDeadlineS)
		{
			const double Took = (ReachedOpenT >= 0.0 && PlateEnteredT >= 0.0)
				? (ReachedOpenT - PlateEnteredT) : -1.0;
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorOpensWithinDeadline: expected the door to reach the open ")
				TEXT("band within %.1f s of the character stepping on, and it took ")
				TEXT("%.2f s (-1 means it never got there while they stood)"),
				kOpenDeadlineS, Took));
			return;
		}
		Open1 = G;
		break;

	case 2:
		if (G < kOpenDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorStaysOpenWhileOccupied: expected the door to stay open ")
				TEXT("for as long as the character kept standing (cycle 1), and it ")
				TEXT("was %.1f degrees from shut"), G));
			return;
		}
		Phase = EPlateDoorPhase::Depart1;
		break;

	case 3:
		if (G > kShutDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorShutsWhenVacated: expected the door to be shut again ")
				TEXT("after the character walked off (cycle 1), and it was %.1f ")
				TEXT("degrees open with the character %.0f cm away"), G, D));
			return;
		}
		if (Tr > kTravelCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PanelReturnsHome: expected the panel to come back to where ")
				TEXT("it started (cycle 1), and it is %.0f cm away"), Tr));
			return;
		}
		Phase = EPlateDoorPhase::Approach2;
		break;

	case 4:
		if (!OnPlate(GradedPlate.Get()))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the test could not reach the plate on ")
				TEXT("the second approach (%.0f cm away at t=%.2f)"), D, T));
			return;
		}
		if (G < kOpenDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorOpensEveryTime: expected the door to open again the ")
				TEXT("second time, and it was %.1f degrees from shut"), G));
			return;
		}
		if (Tr < kTravelCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PanelIsTheGradedPart: expected the door's own panel to move ")
				TEXT("again the second time; it is %.0f cm from where it started"),
				Tr));
			return;
		}
		if (ReachedOpenT < 0.0 || PlateEnteredT < 0.0
			|| (ReachedOpenT - PlateEnteredT) > kOpenDeadlineS)
		{
			const double Took = (ReachedOpenT >= 0.0 && PlateEnteredT >= 0.0)
				? (ReachedOpenT - PlateEnteredT) : -1.0;
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorOpensWithinDeadline: expected the door to reach the open ")
				TEXT("band within %.1f s of the character stepping on, and it took ")
				TEXT("%.2f s (-1 means it never got there while they stood)"),
				kOpenDeadlineS, Took));
			return;
		}
		if (FMath::Abs(G - Open1) > kRepeatDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorOpensEveryTime: expected the same open position as the ")
				TEXT("first time, and it differed by %.1f degrees (%.1f then, ")
				TEXT("%.1f now; the level allows %.0f)"),
				FMath::Abs(G - Open1), Open1, G, kRepeatDeg));
			return;
		}
		break;

	case 5:
		if (G < kOpenDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorStaysOpenWhileOccupied: expected the door to stay open ")
				TEXT("for as long as the character kept standing (cycle 2), and it ")
				TEXT("was %.1f degrees from shut"), G));
			return;
		}
		Phase = EPlateDoorPhase::Depart2;
		break;

	case 6:
		if (G > kShutDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("DoorShutsWhenVacated: expected the door to be shut again ")
				TEXT("after the character walked off (cycle 2), and it was %.1f ")
				TEXT("degrees open"), G));
			return;
		}
		if (Tr > kTravelCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PanelReturnsHome: expected the panel to come back to where ")
				TEXT("it started (cycle 2), and it is %.0f cm away"), Tr));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded,
			TEXT("door opened and shut on both visits; the second pair never moved"));
		break;

	default:
		break;
	}
}
