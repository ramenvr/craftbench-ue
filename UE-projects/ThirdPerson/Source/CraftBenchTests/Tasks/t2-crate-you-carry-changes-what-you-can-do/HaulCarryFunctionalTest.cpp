// Copyright CraftBench. All Rights Reserved.

#include "HaulCarryFunctionalTest.h"

#include "CollisionQueryParams.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED in the prompt. Not one of these is a private threshold. ----
	constexpr double kPickUpRadiusCm = 250.0;    // "within 250 cm of your middle"
	constexpr double kHoldMinCm = 290.0;         // "between 290 and 380 cm"
	constexpr double kHoldMaxCm = 380.0;
	constexpr double kClearFloorCm = 120.0;      // "at least 120 cm above the floor"
	constexpr double kWallFreeCm = 600.0;        // "more than 600 cm from a wall"
	constexpr double kInWallCm = 40.0;           // "no more than 40 cm inside a wall"
	constexpr double kOpenLiftCm = 250.0;        // "lifted at least 250 cm"
	constexpr double kShutLiftCm = 20.0;         // "back within 20 cm"
	constexpr double kDoorSettleS = 2.0;         // "within two seconds"
	constexpr double kFreeSpeedMin = 400.0;      // "400 to 600 units a second"
	constexpr double kFreeSpeedMax = 600.0;
	constexpr double kCarryFracMin = 0.35;       // "35% to 65%"
	constexpr double kCarryFracMax = 0.65;
	constexpr double kBackFracMin = 0.85;        // "85% to 115%"
	constexpr double kBackFracMax = 1.15;
	constexpr double kSetDownSettleS = 2.5;      // "within two and a half seconds"
	constexpr double kRestingWithinCm = 12.0;    // "within 12 cm of the surface"
	constexpr double kStaysWithinCm = 60.0;      // "stays where you left it"
	constexpr double kYardMoveCm = 2.0;          // "not yours to change"
	constexpr double kJumpWatchS = 1.5;          // "within a second and a half"
	constexpr double kJumpRiseCm = 40.0;         // "leaves the ground"

	// ---- UNDISCLOSED: this fixture's own clocking and staging. ----
	constexpr double kWaypointCm = 25.0;     // arrival tolerance on a fixed point
	constexpr double kAtCrateCm = 240.0;     // how far short of a crate the drive stops
	// A crate at rest sits ON the floor, so anything meaningfully above it is held.
	// Deliberately well under the 120 cm the carry gate requires, so this can never
	// stand in for that gate -- it only tells the DRIVE the crate has been taken.
	constexpr double kCarriedClearCm = 40.0;
	constexpr double kSpeedSmoothing = 0.15; // the shape validated on t1-mud
	constexpr double kMinSpeedToJudge = 30.0;
	// One window covers BOTH the acceleration ramp off a standstill and the turn at
	// the head of the leg. t1-mud measured a correct answer at 68% of its own speed
	// purely because a sample landed in a turn; this is that lesson carried over.
	constexpr double kLegSettleS = 1.8;
	constexpr int32 kMinSamples = 20;
	constexpr double kRideArmS = 0.5;        // "half a second after you pick it up"
	constexpr double kInWallForS = 0.5;      // a graze is not a burial
	constexpr double kEmptyBesideCrateS = 2.0;
	constexpr double kInAirCm = 40.0;        // above the 20 cm pads: on a pad is not "in the air"
	constexpr double kNearHeroCm = 500.0;    // beyond this, an airborne crate is abandoned
	constexpr double kJumpArmS = 0.8;        // stand still this long before pressing
	constexpr double kJumpPressS = 0.2;      // press/release pair, as the template binds
	constexpr double kOverReachCm = 320.0;   // a pick-up from further than this is the answer's fault
	constexpr double kMarginKg = 8.0;        // every staged comparison must clear by this
	constexpr double kLegSlackS = 12.0;      // per-leg deadline slack
	constexpr double kSentinelS = 480.0;

	// The two price lists. Round 1 makes a single hard-coded threshold wrong about
	// the high plate; round 2 makes a REMEMBERED number wrong about both plates at
	// once, with no crate moving at all.
	const float kMassRound1[3] = { 18.0f, 42.0f, 70.0f };   // west, middle, east
	const float kMassRound2[3] = { 24.0f, 52.0f, 48.0f };
	const float kHoldRound1[2] = { 30.0f, 55.0f };          // low-Y plate, high-Y plate
	const float kHoldRound2[2] = { 90.0f, 60.0f };

	FBox SolidBox(const AActor* A)
	{
		return A != nullptr ? A->GetComponentsBoundingBox(false) : FBox(ForceInit);
	}

	/** Shortest distance from a point to a segment, flat. */
	double DistPointToSeg2D(const FVector& P, const FVector& A, const FVector& B)
	{
		const FVector2D p(P.X, P.Y), a(A.X, A.Y), b(B.X, B.Y);
		const FVector2D ab = b - a;
		const double L2 = ab.X * ab.X + ab.Y * ab.Y;
		if (L2 < 1.0)
		{
			return FVector2D::Distance(p, a);
		}
		double t = ((p.X - a.X) * ab.X + (p.Y - a.Y) * ab.Y) / L2;
		t = FMath::Clamp(t, 0.0, 1.0);
		return FVector2D::Distance(p, a + ab * t);
	}

	/** Flat distance from a point to a box; 0 when inside it in XY. */
	double DistPointToBox2D(const FVector& P, const FBox& Box)
	{
		const double dx = FMath::Max3(Box.Min.X - P.X, 0.0, P.X - Box.Max.X);
		const double dy = FMath::Max3(Box.Min.Y - P.Y, 0.0, P.Y - Box.Max.Y);
		return FMath::Sqrt(dx * dx + dy * dy);
	}
}

AHaulCarryFunctionalTest::AHaulCarryFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

void AHaulCarryFunctionalTest::Fail(const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("%s: %s"), Gate, *Detail));
}

void AHaulCarryFunctionalTest::Precondition(const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Error,
		FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Detail));
}

float AHaulCarryFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	bool& bOK) const
{
	bOK = false;
	if (A == nullptr)
	{
		return 0.0f;
	}
	const FFloatProperty* const P = FindFProperty<FFloatProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return 0.0f;
	}
	bOK = true;
	return P->GetPropertyValue_InContainer(A);
}

void AHaulCarryFunctionalTest::WriteFloat(AActor* A, const TCHAR* Name, float Value)
{
	if (A == nullptr)
	{
		return;
	}
	if (const FFloatProperty* const P =
			FindFProperty<FFloatProperty>(A->GetClass(), Name))
	{
		P->SetPropertyValue_InContainer(A, Value);
	}
}

UStaticMeshComponent* AHaulCarryFunctionalTest::ResolvePanel(AActor* Door) const
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
		if (M != nullptr && M->GetName() == TEXT("Panel"))
		{
			return M;
		}
	}
	// 2. Else the largest by local bounds, ties by name, so the answer never
	//    depends on component enumeration order.
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

bool AHaulCarryFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> FoundCrates, FoundPlates, FoundDoors, FoundBlockers;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("HaulCrate")), FoundCrates);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("WeightPlate")), FoundPlates);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LiftDoor")), FoundDoors);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardBlocker")), FoundBlockers);

	if (FoundCrates.Num() != 3 || FoundPlates.Num() != 2 || FoundDoors.Num() != 2
		|| FoundBlockers.Num() < 1)
	{
		Precondition(FString::Printf(
			TEXT("the yard is not staged as authored - found %d crates, %d plates, ")
			TEXT("%d doors and %d walls, expected 3, 2, 2 and at least 1"),
			FoundCrates.Num(), FoundPlates.Num(), FoundDoors.Num(),
			FoundBlockers.Num()));
		return false;
	}

	// West to east: the drive names crates by where they stand, so the same crate
	// is "the west crate" however the level reports them.
	FoundCrates.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetActorLocation().X < R.GetActorLocation().X;
	});
	for (AActor* C : FoundCrates)
	{
		Crates.Add(C);
	}
	// Low Y first.
	FoundPlates.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetActorLocation().Y < R.GetActorLocation().Y;
	});

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid())
	{
		Precondition(TEXT("no player character in the yard - the level places one and ")
					 TEXT("sets it to be possessed by player 0"));
		return false;
	}
	if (!Hero->ActorHasTag(FName(TEXT("HaulHero"))))
	{
		Precondition(FString::Printf(
			TEXT("the possessed pawn is %s, which is not the yard's HaulHero"),
			*Hero->GetClass()->GetName()));
		return false;
	}
	if (Hero->GetMesh() == nullptr || Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		Precondition(TEXT("the character has no visible body, so a reviewer watching ")
					 TEXT("the recording would see nothing"));
		return false;
	}
	HeroStart = Hero->GetActorLocation();

	// The floor. Taken from the crates, which the yard stands ON it, so every
	// height in this fixture is measured from the same surface a person sees.
	const FBox First = SolidBox(Crates[0].Get());
	if (First.IsValid == 0)
	{
		Precondition(TEXT("a crate has no solid body, so nothing about it can be measured"));
		return false;
	}
	FloorTopZ = First.Min.Z;

	for (AActor* B : FoundBlockers)
	{
		const FBox Box = SolidBox(B);
		if (Box.IsValid == 0)
		{
			Precondition(TEXT("a yard wall has no solid body"));
			return false;
		}
		Blockers.Add(B);
		BlockerBoxes.Add(Box);
		BlockerStagedLoc.Add(B->GetActorLocation());
	}

	for (AActor* D : FoundDoors)
	{
		FHaulDoorProbe Probe;
		Probe.Actor = D;
		Probe.Panel = ResolvePanel(D);
		if (!Probe.Panel.IsValid())
		{
			Precondition(TEXT("a door has no slab to lift"));
			return false;
		}
		Probe.StagedActorLoc = D->GetActorLocation();
		Probe.ShutPanelZ = Probe.Panel->GetComponentLocation().Z;
		Doors.Add(Probe);
	}

	for (AActor* P : FoundPlates)
	{
		FHaulPlateProbe Probe;
		Probe.Actor = P;
		Probe.StagedLoc = P->GetActorLocation();
		const FObjectProperty* const Link =
			FindFProperty<FObjectProperty>(P->GetClass(), TEXT("LinkedDoor"));
		AActor* const Linked = Link != nullptr
			? Cast<AActor>(Link->GetObjectPropertyValue_InContainer(P)) : nullptr;
		if (Linked == nullptr)
		{
			Precondition(FString::Printf(
				TEXT("plate %s does not say which door it belongs to - LinkedDoor is ")
				TEXT("unset or has been redeclared, and the level's own wiring is ")
				TEXT("what the grade reads"), *P->GetName()));
			return false;
		}
		for (int32 i = 0; i < Doors.Num(); ++i)
		{
			if (Doors[i].Actor.Get() == Linked)
			{
				Probe.DoorIndex = i;
			}
		}
		if (Probe.DoorIndex < 0)
		{
			Precondition(FString::Printf(
				TEXT("plate %s is wired to %s, which is not one of the yard's doors"),
				*P->GetName(), *Linked->GetName()));
			return false;
		}
		Plates.Add(Probe);
	}
	if (Plates.Num() == 2 && Plates[0].DoorIndex == Plates[1].DoorIndex)
	{
		Precondition(TEXT("both plates are wired to the same door, so 'its own door' ")
					 TEXT("could not be told from 'a door'"));
		return false;
	}

	// The pad half-width, read off the pad rather than written down, so the yard
	// can be re-authored at a different size and the drive follows.
	const FBox PadBox = SolidBox(Plates[0].Actor.Get());
	if (PadBox.IsValid == 0)
	{
		Precondition(TEXT("a plate has no pad, so nothing can rest on it"));
		return false;
	}
	PadHalfCm = FMath::Min(PadBox.Max.X - PadBox.Min.X, PadBox.Max.Y - PadBox.Min.Y) * 0.5;

	LandedAt.SetNum(Crates.Num());
	LandedWhen.SetNum(Crates.Num());
	bAirborne.SetNum(Crates.Num());
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		LandedAt[i] = Crates[i]->GetActorLocation();
		LandedWhen[i] = -1000.0;
		bAirborne[i] = 0;
	}
	return true;
}

bool AHaulCarryFunctionalTest::ReadNumbers()
{
	for (const TWeakObjectPtr<AActor>& C : Crates)
	{
		bool bOK = false;
		ReadFloat(C.Get(), TEXT("MassKg"), bOK);
		if (!bOK)
		{
			Precondition(TEXT("a crate does not expose MassKg as a readable number - ")
						 TEXT("the weight painted on the crates is what the plates ")
						 TEXT("weigh and what this test reads"));
			return false;
		}
	}
	for (const FHaulPlateProbe& P : Plates)
	{
		bool bOK = false;
		ReadFloat(P.Actor.Get(), TEXT("MinimumHoldKg"), bOK);
		if (!bOK)
		{
			Precondition(TEXT("a plate does not expose MinimumHoldKg as a readable ")
						 TEXT("number"));
			return false;
		}
	}
	return true;
}

void AHaulCarryFunctionalTest::PriceYard(int32 Round)
{
	const float* const Mass = (Round == 1) ? kMassRound1 : kMassRound2;
	const float* const Hold = (Round == 1) ? kHoldRound1 : kHoldRound2;
	for (int32 i = 0; i < Crates.Num() && i < 3; ++i)
	{
		WriteFloat(Crates[i].Get(), TEXT("MassKg"), Mass[i]);
	}
	for (int32 i = 0; i < Plates.Num() && i < 2; ++i)
	{
		WriteFloat(Plates[i].Actor.Get(), TEXT("MinimumHoldKg"), Hold[i]);
	}
	PriceRound = Round;
}

bool AHaulCarryFunctionalTest::ValidateMargins()
{
	// Every comparison the drive actually stages, in both price rounds, with the
	// side it must come down on. A margin under kMarginKg would let a correct answer
	// round the wrong way; equal masses or equal thresholds would let a gate be
	// satisfied by accident.
	struct FCase { double Load; double Hold; bool bOpen; const TCHAR* What; };
	const double a1 = kMassRound1[0], b1 = kMassRound1[1], c1 = kMassRound1[2];
	const double a2 = kMassRound2[0], b2 = kMassRound2[1], c2 = kMassRound2[2];
	const double L1 = kHoldRound1[0], H1 = kHoldRound1[1];
	const double L2 = kHoldRound2[0], H2 = kHoldRound2[1];
	const FCase Cases[] = {
		{ a1,      L1, false, TEXT("round 1: the west crate alone on the low plate") },
		{ 0.0,     H1, false, TEXT("round 1: a person alone on the high plate") },
		{ b1,      H1, false, TEXT("round 1: the middle crate alone on the high plate") },
		{ b1,      L1, true,  TEXT("round 1: one hard-coded threshold would open here") },
		{ b1 + c1, H1, true,  TEXT("round 1: two crates on the high plate") },
		{ c1,      H1, true,  TEXT("round 1: one of the two lifted off again") },
		{ a1 + b1, L1, true,  TEXT("round 1: two crates on the low plate") },
		{ a2 + b2, L2, false, TEXT("round 2: the same two crates, re-priced") },
		{ c2,      H2, false, TEXT("round 2: the same one crate, re-priced") },
		{ b2,      L2, false, TEXT("round 2: the middle crate alone on the low plate") },
		{ c2 + a2, H2, true,  TEXT("round 2: two crates on the high plate") },
		{ a2,      H2, false, TEXT("round 2: the west crate alone on the high plate") },
		{ b2 + c2, L2, true,  TEXT("round 2: two crates on the low plate") },
	};
	for (const FCase& C : Cases)
	{
		const double Margin = C.bOpen ? (C.Load - C.Hold) : (C.Hold - C.Load);
		if (Margin < kMarginKg)
		{
			Precondition(FString::Printf(
				TEXT("%s comes to %.0f kg against a threshold of %.0f kg, only %.0f kg ")
				TEXT("clear (this fixture refuses under %.0f kg, because a correct ")
				TEXT("answer could round either way)"),
				C.What, C.Load, C.Hold, Margin, kMarginKg));
			return false;
		}
	}
	// The whole point of the second price list is that it changes the answer.
	if ((a1 + b1 >= L1) == (a2 + b2 >= L2) && (c1 >= H1) == (c2 >= H2))
	{
		Precondition(TEXT("the second price list does not change either plate's ")
					 TEXT("verdict, so a remembered number would never be caught"));
		return false;
	}
	return true;
}

void AHaulCarryFunctionalTest::BuildRoute()
{
	const FVector PL = Plates[0].StagedLoc;
	const FVector PH = Plates[1].StagedLoc;
	const double Z = HeroStart.Z;
	const double Run = PadHalfCm * 10.0 / 3.0;   // 1500 for the yard's 450 cm half-pad

	auto Pt = [Z](double X, double Y) { return FVector(X, Y, Z); };
	auto Walk = [this](const FVector& T, double Dwell, const TCHAR* Label,
		int32 Measure = 0)
	{
		FHaulStop S;
		S.Target = T;
		S.Dwell = Dwell;
		S.Measure = Measure;
		S.Label = Label;
		Route.Add(S);
	};
	auto Jump = [this](int32 Which, const FVector& T, const TCHAR* Label)
	{
		FHaulStop S;
		S.Target = T;
		S.Dwell = kJumpArmS + kJumpPressS + kJumpWatchS + 0.6;
		S.JumpTest = Which;
		S.Label = Label;
		Route.Add(S);
	};
	auto AtCrate = [this](int32 Index, double Dwell, const TCHAR* Label)
	{
		FHaulStop S;
		S.CrateIndex = Index;
		S.Dwell = Dwell;
		S.Label = Label;
		Route.Add(S);
	};
	auto Push = [this](const FVector& T, const TCHAR* Label)
	{
		FHaulStop S;
		S.Target = T;
		S.Press = 3.0;
		S.Label = Label;
		Route.Add(S);
	};

	// The lane runs from where the character starts, toward the plates.
	const double LaneSign = (PL.X >= HeroStart.X) ? 1.0 : -1.0;
	const FVector LaneEnd = Pt(HeroStart.X + LaneSign * 2600.0, HeroStart.Y);
	const FVector WallMid = BlockerBoxes[0].GetCenter();
	const FVector WallLineUp = Pt(WallMid.X, HeroStart.Y);
	const FVector WallInto = Pt(WallMid.X, WallMid.Y);

	const double WestX = PL.X - Run;
	const double EastX = PL.X + Run;
	const double NorthY = PH.Y + Run;
	const double SouthY = PL.Y - Run;

	// ------------------------------ ROUND 1 ---------------------------------
	Walk(LaneEnd, 3.0, TEXT("walk the lane empty-handed"), 1);
	Jump(1, LaneEnd, TEXT("jump with empty hands"));
	AtCrate(0, 3.0, TEXT("pick up the west crate"));
	Walk(LaneEnd, 3.0, TEXT("walk the same lane carrying it"), 2);
	Jump(2, LaneEnd, TEXT("try to jump while carrying"));
	Walk(WallLineUp, 0.4, TEXT("line up on the wall"));
	Push(WallInto, TEXT("push the crate into the wall"));
	Walk(WallLineUp, 0.4, TEXT("back off the wall"));
	Walk(Pt(WestX, PL.Y), 0.4, TEXT("line up west of the low plate"));
	Walk(PL, 3.0, TEXT("set the west crate on the low plate"));
	Walk(PH, 3.5, TEXT("stand on the high plate with empty hands"), 3);
	Walk(Pt(PH.X, PH.Y - Run), 0.4, TEXT("step south off the high plate"));
	AtCrate(1, 3.0, TEXT("pick up the middle crate"));
	Walk(Pt(PH.X, PH.Y - Run), 0.4, TEXT("line up south of the high plate"));
	Walk(PH, 3.0, TEXT("set the middle crate on the high plate"));
	Walk(Pt(WestX, PH.Y), 0.4, TEXT("step west off the high plate"));
	AtCrate(2, 3.0, TEXT("pick up the east crate"));
	Walk(Pt(WestX, PH.Y), 0.4, TEXT("line up west of the high plate"));
	Walk(PH, 3.0, TEXT("set the east crate beside it"));
	Walk(Pt(WestX, PH.Y - Run), 0.4, TEXT("step clear of both crates"));
	Walk(Pt(PH.X, NorthY), 0.4, TEXT("round to the north of the high plate"));
	AtCrate(1, 3.0, TEXT("lift one of the two off again"));
	Walk(Pt(PH.X, NorthY), 0.4, TEXT("step back north"));
	Walk(Pt(WestX, NorthY), 0.4, TEXT("west along the top of the yard"));
	Walk(Pt(WestX, SouthY), 0.4, TEXT("south along the west of the yard"));
	Walk(Pt(PL.X, SouthY), 0.4, TEXT("line up south of the low plate"));
	Walk(PL, 3.0, TEXT("set it on the low plate as well"));
	Walk(Pt(PL.X, SouthY), 0.4, TEXT("step south off the low plate"));
	Walk(Pt(EastX, SouthY), 0.4, TEXT("east along the bottom of the yard"));
	Walk(Pt(EastX, PH.Y), 0.4, TEXT("north to the east of the high plate"));
	AtCrate(2, 3.0, TEXT("take the last crate off the high plate"));
	Walk(Pt(EastX, PH.Y), 0.4, TEXT("step back east"));
	Walk(Pt(PH.X, PH.Y - Run), 0.4, TEXT("line up south of the high plate again"));
	Walk(PH, 4.0, TEXT("put it back on the high plate"));
	{
		FHaulStop S;
		S.Target = Pt(WestX, PH.Y);
		S.Dwell = 5.0;
		S.bReprice = true;
		S.Label = TEXT("step west and wait while the yard is re-priced");
		Route.Add(S);
	}

	// ------------------------------ ROUND 2 ---------------------------------
	// Nothing moves at the re-price. Two doors that are standing open have to shut.
	Walk(Pt(EastX, PL.Y), 0.4, TEXT("round to the east of the low plate"));
	AtCrate(0, 3.0, TEXT("lift the west crate off the low plate"));
	Walk(Pt(EastX, PL.Y), 0.4, TEXT("step back east"));
	Walk(Pt(WestX, PH.Y), 0.4, TEXT("line up west of the high plate"));
	Walk(PH, 3.0, TEXT("add it to the high plate"));
	Walk(Pt(WestX, PH.Y - Run), 0.4, TEXT("step clear of both crates again"));
	Walk(Pt(PH.X, NorthY), 0.4, TEXT("round to the north of the high plate again"));
	AtCrate(2, 3.0, TEXT("take the other one off the high plate"));
	Walk(Pt(PH.X, NorthY), 0.4, TEXT("step back north again"));
	Walk(Pt(WestX, NorthY), 0.4, TEXT("west along the top of the yard again"));
	Walk(Pt(WestX, PL.Y), 0.4, TEXT("line up west of the low plate"));
	Walk(PL, 4.0, TEXT("set it on the low plate"));
	Walk(Pt(WestX, PL.Y), 4.0, TEXT("step clear and let the yard settle"));
}

bool AHaulCarryFunctionalTest::ValidateRoute()
{
	// WHAT THIS CHECK IS ENTITLED TO ASSERT. It runs in PrepareTest, before a
	// single frame, so the only geometry it knows is the geometry the LEVEL put
	// there. Two things on this route are settled by the SUBMISSION instead, and
	// asserting on either refuses a correct answer rather than protecting the
	// grade - which is exactly what it did to this yard as authored:
	//   - where a crate is once the drive has FETCHED it. The brief lets the crate
	//     ride anywhere from 290 to 380 cm ahead and be set down from there.
	//   - where the character finishes a PRESS leg. That leg is the one leg meant
	//     not to arrive, and where the wall stops it depends on whether the
	//     carried crate stays solid to its carrier: the reference has the two
	//     ignore each other and jams the capsule 42 cm off the wall face, while a
	//     crate left solid jams it at 122. Neither clears the 150 cm floor below,
	//     so there is no honest constant to reach for here - only a start point
	//     this fixture is not entitled to name.
	// So a crate is checked up to the leg that fetches it and not after, and a
	// press leg chains from the one point on its corridor the level does fix: its
	// own start. Measured on the staged yard, that leaves 30 crate clearances and
	// 47 wall clearances still asserted over all 48 legs, none refused, the
	// tightest 700 cm against the 290 cm floor (leg 12) and 1885 cm against the
	// 150 cm floor (leg 24) - and a leg re-aimed into the wall, a leg walked past
	// an untouched crate, or a push lined up from inside the wall are all still
	// refused by name.
	FVector From = HeroStart;
	// Crates the drive has already picked up. A crate stops being where the level
	// put it at that leg, so this check stops speaking about it there.
	TArray<uint8> bFetched;
	bFetched.SetNumZeroed(Crates.Num());
	for (int32 i = 0; i < Route.Num(); ++i)
	{
		const FHaulStop& S = Route[i];
		const FVector To = (S.CrateIndex >= 0)
			? Crates[S.CrateIndex]->GetActorLocation() : S.Target;

		// The crates the character is NOT going for have to stay outside its reach,
		// or the drive picks up something the script is not tracking. The carried
		// crate rides along the same line, so this clears both.
		//
		// A crate the drive has already fetched is skipped, and bFetched subsumes
		// the old "the crate picked up on the previous leg" exemption. Its staged
		// spot is not a weaker claim about where it is, it is a FALSE one: legs 21
		// and 22 measure 256 cm from crate 2's STAGED spot, which is under the
		// 290 cm floor, while the live crate 2 is sitting on the high plate ~658 cm
		// off those legs. Predicting where the crate went instead would make this
		// precondition depend on the submission's own hold distance, which is how a
		// task becomes unwinnable. The LIVE guards carry it from there, and they
		// read the world rather than the staging: a crate that comes off the ground
		// from further than kOverReachCm - measured against LandedAt, where it
		// actually settled - is a named FAIL, two airborne crates at once is a named
		// FAIL, and any pick-up the script did not schedule desynchronises the drive
		// into its own leg deadline.
		for (int32 c = 0; c < Crates.Num(); ++c)
		{
			if (c == S.CrateIndex || bFetched[c] != 0)
			{
				continue;
			}
			const double D = DistPointToSeg2D(Crates[c]->GetActorLocation(), From, To);
			if (D < kPickUpRadiusCm + 40.0)
			{
				Precondition(FString::Printf(
					TEXT("leg %d (%s) passes %.0f cm from a crate it is not going for, ")
					TEXT("and anything inside %.0f cm gets picked up"),
					i, *S.Label, D, kPickUpRadiusCm));
				return false;
			}
		}
		// And no leg but the wall push may run into a wall.
		if (S.Press <= 0.0)
		{
			for (int32 b = 0; b < BlockerBoxes.Num(); ++b)
			{
				const FBox& Box = BlockerBoxes[b];
				const FVector Mid = Box.GetCenter();
				const double D = DistPointToSeg2D(Mid, From, To)
					- FMath::Max(Box.Max.X - Mid.X, Box.Max.Y - Mid.Y);
				if (D < 150.0)
				{
					Precondition(FString::Printf(
						TEXT("leg %d (%s) runs into a yard wall (%.0f cm clear); only ")
						TEXT("the push leg is meant to"), i, *S.Label, D));
					return false;
				}
			}
		}
		if (S.CrateIndex >= 0)
		{
			bFetched[S.CrateIndex] = 1;
		}
		// A PRESS LEG NEVER ARRIVES, so the chain must not walk on as though it
		// had. From stays at the corridor's mouth - the last point on that corridor
		// the level fixes - so the next leg is still checked over every metre of new
		// ground it breaks, and the only stretch left unchecked is the press
		// corridor itself: the one stretch of this yard the route is allowed to
		// drive into a wall, and the stretch the press leg has just walked. Chaining
		// through the press leg's TARGET instead started leg 7 at the wall's own
		// CENTRE and reported that leg 400 cm inside the wall it was walking away
		// from: 0 cm to the centre, less the wall's 400 cm half-depth along the push
		// axis, which is the 800 cm depth author_map.py solves for so the no-clip
		// gate can contain a teleported crate. The wall is right; the chain was not.
		if (S.Press <= 0.0)
		{
			From = To;
		}
	}
	return true;
}

void AHaulCarryFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		Precondition(TEXT("no world"));
		return;
	}
	if (!ResolveStaging() || !ReadNumbers() || !ValidateMargins())
	{
		return;
	}
	PriceYard(1);
	BuildRoute();
	if (!ValidateRoute())
	{
		return;
	}

	LegStartedAt = 0.0;
	LegStartedFrom = HeroStart;
	LegLengthCm = FVector::Dist2D(HeroStart, Route[0].Target);

	TArray<double> Schedule;
	for (int32 i = 1; i * 10 <= 470; ++i)
	{
		Schedule.Add(static_cast<double>(i * 10));
	}
	// THE SENTINEL. The base class declares success the instant the last scheduled
	// checkpoint is sampled, so every gate that needs the whole haul to have
	// happened is evaluated here and nowhere earlier. The drive measures ~370 s.
	Schedule.Add(kSentinelS);
	TimeLimitMargin = 8.0f;
	SetCheckpointSchedule(Schedule);
}

// ---------------------------------------------------------------------------
//  MEASUREMENT
// ---------------------------------------------------------------------------

bool AHaulCarryFunctionalTest::CrateIsInAir(int32 i) const
{
	const FBox Box = SolidBox(Crates[i].Get());
	return Box.IsValid != 0 && (Box.Min.Z - FloorTopZ) > kInAirCm;
}

int32 AHaulCarryFunctionalTest::RidingCrateIndex() const
{
	if (!Hero.IsValid())
	{
		return -1;
	}
	const FVector Here = Hero->GetActorLocation();
	int32 Best = -1;
	double BestD = kNearHeroCm;
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		if (!CrateIsInAir(i))
		{
			continue;
		}
		const double D = FVector::Dist2D(Here, Crates[i]->GetActorLocation());
		if (D <= BestD)
		{
			BestD = D;
			Best = i;
		}
	}
	return Best;
}

double AHaulCarryFunctionalTest::LoadOnPlateKg(int32 p) const
{
	const AActor* const Plate = Plates[p].Actor.Get();
	const FBox Pad = SolidBox(Plate);
	if (Pad.IsValid == 0)
	{
		return 0.0;
	}
	double Total = 0.0;
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		const AActor* const C = Crates[i].Get();
		const FBox Box = SolidBox(C);
		if (C == nullptr || Box.IsValid == 0)
		{
			continue;
		}
		const FVector Middle = C->GetActorLocation();
		const bool bOverPad = Middle.X >= Pad.Min.X && Middle.X <= Pad.Max.X
			&& Middle.Y >= Pad.Min.Y && Middle.Y <= Pad.Max.Y;
		const bool bSittingOnIt = FMath::Abs(Box.Min.Z - Pad.Max.Z) <= kRestingWithinCm;
		if (bOverPad && bSittingOnIt)
		{
			bool bOK = false;
			Total += ReadFloat(C, TEXT("MassKg"), bOK);
		}
	}
	return Total;
}

double AHaulCarryFunctionalTest::DoorLiftCm(int32 d) const
{
	if (d < 0 || d >= Doors.Num() || !Doors[d].Panel.IsValid())
	{
		return 0.0;
	}
	return Doors[d].Panel->GetComponentLocation().Z - Doors[d].ShutPanelZ;
}

double AHaulCarryFunctionalTest::SurfaceUnderCrateZ(int32 i) const
{
	UWorld* const World = GetWorld();
	AActor* const C = Crates[i].Get();
	if (World == nullptr || C == nullptr)
	{
		return FloorTopZ;
	}
	FCollisionQueryParams Params(FName(TEXT("HaulSurfaceUnder")), false);
	Params.AddIgnoredActor(C);
	if (Hero.IsValid())
	{
		Params.AddIgnoredActor(Hero.Get());
	}
	FHitResult Hit;
	const FVector From = C->GetActorLocation();
	if (World->LineTraceSingleByChannel(Hit, From,
			From - FVector(0.0, 0.0, 4000.0), ECC_Visibility, Params))
	{
		return Hit.ImpactPoint.Z;
	}
	return FloorTopZ;
}

// ---------------------------------------------------------------------------
//  GATES
// ---------------------------------------------------------------------------

bool AHaulCarryFunctionalTest::GateRideAndWalls(double Now)
{
	const FVector Here = Hero->GetActorLocation();

	int32 Airborne = 0;
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		if (!CrateIsInAir(i))
		{
			continue;
		}
		++Airborne;
		const double D = FVector::Dist2D(Here, Crates[i]->GetActorLocation());
		if (D > kNearHeroCm)
		{
			const FBox Box = SolidBox(Crates[i].Get());
			Fail(TEXT("TheCrateYouPutDownComesToRest"), FString::Printf(
				TEXT("a crate is hanging %.0f cm off the floor with nobody within ")
				TEXT("%.0f cm of it (it is %.0f cm away); a crate you have set down ")
				TEXT("has to come to rest on the pad or the floor"),
				Box.Min.Z - FloorTopZ, kNearHeroCm, D));
			return false;
		}
	}
	if (Airborne > 1)
	{
		Fail(TEXT("TheCrateRidesInFrontOfYou"), FString::Printf(
			TEXT("%d crates are off the ground at once, and you carry one at a time"),
			Airborne));
		return false;
	}

	const int32 Riding = RidingCrateIndex();
	if (Riding != LastRiding)
	{
		RidingSince = (Riding >= 0) ? Now : -1.0;
		DeepInWallSince = -1.0;
		if (Riding >= 0)
		{
			++PickUps;
			// A pick-up from further away than the yard's reach is the answer
			// reaching too far, not the drive standing in the wrong place.
			const double Reach = FVector::Dist2D(HeroPrev, LandedAt[Riding]);
			if (bHavePrev && Reach > kOverReachCm)
			{
				Fail(TEXT("TheCrateRidesInFrontOfYou"), FString::Printf(
					TEXT("a crate came off the ground from %.0f cm away; you pick up ")
					TEXT("a crate within %.0f cm of your middle"),
					Reach, kPickUpRadiusCm));
				return false;
			}
		}
		LastRiding = Riding;
	}

	if (Riding < 0)
	{
		// THE PICK-UP ITSELF. Standing beside a crate with empty hands and nothing
		// happening is where an untouched submission fails, and it is the first
		// thing this drive asks for.
		double Nearest = TNumericLimits<double>::Max();
		for (int32 i = 0; i < Crates.Num(); ++i)
		{
			Nearest = FMath::Min(Nearest,
				FVector::Dist2D(Here, Crates[i]->GetActorLocation()));
		}
		if (Nearest <= kPickUpRadiusCm)
		{
			if (EmptyBesideCrateSince < 0.0)
			{
				EmptyBesideCrateSince = Now;
			}
			else if (Now - EmptyBesideCrateSince > kEmptyBesideCrateS)
			{
				Fail(TEXT("TheCrateRidesInFrontOfYou"), FString::Printf(
					TEXT("the character stood %.0f cm from a crate with empty hands ")
					TEXT("for %.1f s and nothing was riding in front of it (the reach ")
					TEXT("is %.0f cm)"), Nearest, Now - EmptyBesideCrateSince,
					kPickUpRadiusCm));
				return false;
			}
		}
		else
		{
			EmptyBesideCrateSince = -1.0;
		}
		return true;
	}
	EmptyBesideCrateSince = -1.0;

	const FBox Box = SolidBox(Crates[Riding].Get());
	const FVector CrateAt = Crates[Riding]->GetActorLocation();

	// THE WALLS. Judged everywhere, wall or no wall: the penetration is measured
	// per axis and only a burial on ALL THREE at once counts, so a crate that
	// merely grazes a corner can never trip it.
	bool bDeep = false;
	int32 WhichWall = -1;
	FVector Deepest = FVector::ZeroVector;
	for (int32 b = 0; b < BlockerBoxes.Num(); ++b)
	{
		const FBox Over = Box.Overlap(BlockerBoxes[b]);
		if (Over.IsValid == 0)
		{
			continue;
		}
		const FVector Ext = Over.Max - Over.Min;
		if (FMath::Min3(Ext.X, Ext.Y, Ext.Z) > kInWallCm)
		{
			bDeep = true;
			WhichWall = b;
			Deepest = Ext;
		}
	}
	if (bDeep)
	{
		if (DeepInWallSince < 0.0)
		{
			DeepInWallSince = Now;
		}
		else if (Now - DeepInWallSince > kInWallForS)
		{
			Fail(TEXT("TheCrateStaysOutOfTheWalls"), FString::Printf(
				TEXT("the crate you are carrying is %.0f x %.0f x %.0f cm inside wall ")
				TEXT("%d and has been for %.1f s; the yard allows %.0f cm, and a crate ")
				TEXT("moved with a sweep simply stops at the wall"),
				Deepest.X, Deepest.Y, Deepest.Z, WhichWall,
				Now - DeepInWallSince, kInWallCm));
			return false;
		}
	}
	else
	{
		DeepInWallSince = -1.0;
	}

	// THE RIDE BAND, suspended near a wall. A crate correctly stopped by a wall
	// cannot also be 290-380 cm in front of somebody standing at that wall; the
	// yard says so and this is where it is honoured.
	double WallClear = TNumericLimits<double>::Max();
	for (const FBox& B : BlockerBoxes)
	{
		WallClear = FMath::Min(WallClear, DistPointToBox2D(Here, B));
	}
	if (RidingSince < 0.0 || Now - RidingSince < kRideArmS || WallClear <= kWallFreeCm)
	{
		return true;
	}

	FVector Forward = Hero->GetActorForwardVector();
	Forward.Z = 0.0;
	Forward = Forward.GetSafeNormal();
	FVector ToCrate = CrateAt - Here;
	ToCrate.Z = 0.0;
	const double Flat = ToCrate.Size();
	const double Dot = FVector::DotProduct(Forward, ToCrate.GetSafeNormal());
	if (Dot <= 0.0)
	{
		Fail(TEXT("TheCrateRidesInFrontOfYou"), FString::Printf(
			TEXT("the crate is behind the character (%.0f cm away, %.2f along its ")
			TEXT("facing); it is meant to ride in front"), Flat, Dot));
		return false;
	}
	if (Flat < kHoldMinCm || Flat > kHoldMaxCm)
	{
		Fail(TEXT("TheCrateRidesInFrontOfYou"), FString::Printf(
			TEXT("the crate is %.0f cm from the character; it is meant to ride ")
			TEXT("between %.0f and %.0f cm in front"), Flat, kHoldMinCm, kHoldMaxCm));
		return false;
	}
	const double Under = Box.Min.Z - FloorTopZ;
	if (Under < kClearFloorCm)
	{
		Fail(TEXT("TheCrateRidesInFrontOfYou"), FString::Printf(
			TEXT("the carried crate's underside is %.0f cm above the yard floor; it ")
			TEXT("is meant to stay at least %.0f cm clear"), Under, kClearFloorCm));
		return false;
	}
	return true;
}

bool AHaulCarryFunctionalTest::GatePlatesAndDoors(double Now)
{
	for (int32 p = 0; p < Plates.Num(); ++p)
	{
		FHaulPlateProbe& Probe = Plates[p];
		const double Load = LoadOnPlateKg(p);
		if (FMath::Abs(Load - Probe.LastLoadKg) > 0.5)
		{
			Probe.LastLoadKg = Load;
			Probe.LoadChangedAt = Now;
		}
		const double Lift = DoorLiftCm(Probe.DoorIndex);

		// Separate spells of being open, so "it lifts again next time" is measured
		// rather than assumed. Counted whatever the load is doing.
		FHaulDoorProbe& Door = Doors[Probe.DoorIndex];
		if (!Door.bWasOpen && Lift >= kOpenLiftCm)
		{
			Door.bWasOpen = true;
			++Door.OpenSpells;
		}
		else if (Door.bWasOpen && Lift <= kShutLiftCm)
		{
			Door.bWasOpen = false;
			++Door.Drops;
		}

		const double SettledSince = FMath::Max(Probe.LoadChangedAt, RepricedAt);
		if (Now - SettledSince < kDoorSettleS)
		{
			continue;
		}
		bool bOK = false;
		const double Hold = ReadFloat(Probe.Actor.Get(), TEXT("MinimumHoldKg"), bOK);
		const bool bShouldBeOpen = Load >= Hold;
		if (bShouldBeOpen && Lift < kOpenLiftCm)
		{
			Fail(TEXT("EachPlateHoldsItsOwnDoorForItsOwnWeight"), FString::Printf(
				TEXT("plate %d is holding %.0f kg and holds from %.0f kg, and the door ")
				TEXT("it is wired to is only %.0f cm up %.1f s later (open is %.0f cm)"),
				p, Load, Hold, Lift, Now - SettledSince, kOpenLiftCm));
			return false;
		}
		if (!bShouldBeOpen && Lift > kShutLiftCm)
		{
			Fail(TEXT("TheDoorDropsWhenTheWeightComesOff"), FString::Printf(
				TEXT("plate %d is holding %.0f kg and holds from %.0f kg, and the door ")
				TEXT("it is wired to is still %.0f cm up %.1f s later (shut is within ")
				TEXT("%.0f cm)"), p, Load, Hold, Lift, Now - SettledSince, kShutLiftCm));
			return false;
		}
	}
	return true;
}

bool AHaulCarryFunctionalTest::GateYardStaysPut(double Now)
{
	for (int32 p = 0; p < Plates.Num(); ++p)
	{
		const AActor* const A = Plates[p].Actor.Get();
		if (A != nullptr && FVector::Dist(A->GetActorLocation(), Plates[p].StagedLoc)
			> kYardMoveCm)
		{
			Fail(TEXT("TheYardStaysWhereItIsPut"), FString::Printf(
				TEXT("plate %d has moved %.0f cm from where the yard put it"),
				p, FVector::Dist(A->GetActorLocation(), Plates[p].StagedLoc)));
			return false;
		}
	}
	for (int32 d = 0; d < Doors.Num(); ++d)
	{
		const AActor* const A = Doors[d].Actor.Get();
		if (A != nullptr && FVector::Dist(A->GetActorLocation(), Doors[d].StagedActorLoc)
			> kYardMoveCm)
		{
			Fail(TEXT("TheYardStaysWhereItIsPut"), FString::Printf(
				TEXT("door %d has moved %.0f cm from where the yard put it; the slab ")
				TEXT("lifts out of the frame, the frame does not travel"),
				d, FVector::Dist(A->GetActorLocation(), Doors[d].StagedActorLoc)));
			return false;
		}
	}
	for (int32 b = 0; b < Blockers.Num(); ++b)
	{
		const AActor* const A = Blockers[b].Get();
		if (A != nullptr && FVector::Dist(A->GetActorLocation(), BlockerStagedLoc[b])
			> kYardMoveCm)
		{
			Fail(TEXT("TheYardStaysWhereItIsPut"), FString::Printf(
				TEXT("wall %d has moved %.0f cm from where the yard put it"),
				b, FVector::Dist(A->GetActorLocation(), BlockerStagedLoc[b])));
			return false;
		}
	}

	// A crate that has been set down: it has to be at rest ON something, and it
	// has to stay where it was left until somebody picks it up again.
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		const bool bAir = CrateIsInAir(i);
		if (!bAir && bAirborne[i] != 0)
		{
			LandedAt[i] = Crates[i]->GetActorLocation();
			LandedWhen[i] = Now;
		}
		// LandedAt is NOT touched when a crate leaves the ground: it has to keep
		// naming where the crate was sitting, because that is what the over-reach
		// check in GateRideAndWalls measures the character's distance to.
		bAirborne[i] = bAir ? 1 : 0;

		if (bAir || Now - LandedWhen[i] < kSetDownSettleS)
		{
			continue;
		}
		const FBox Box = SolidBox(Crates[i].Get());
		const double Gap = Box.Min.Z - SurfaceUnderCrateZ(i);
		if (Gap > kRestingWithinCm)
		{
			Fail(TEXT("TheCrateYouPutDownComesToRest"), FString::Printf(
				TEXT("crate %d is sitting %.0f cm above whatever is beneath it %.1f s ")
				TEXT("after it was set down; the yard allows %.0f cm"),
				i, Gap, Now - LandedWhen[i], kRestingWithinCm));
			return false;
		}
		const double Drift = FVector::Dist2D(Crates[i]->GetActorLocation(), LandedAt[i]);
		if (Drift > kStaysWithinCm)
		{
			Fail(TEXT("TheYardStaysWhereItIsPut"), FString::Printf(
				TEXT("the crate set down at (%.0f, %.0f) is now %.0f cm away; a crate ")
				TEXT("stays where you left it until somebody picks it up"),
				LandedAt[i].X, LandedAt[i].Y, Drift));
			return false;
		}
	}
	return true;
}

bool AHaulCarryFunctionalTest::GateJump(double Now)
{
	if (!Route.IsValidIndex(Stop))
	{
		return true;
	}
	const FHaulStop& S = Route[Stop];
	if (S.JumpTest == 0 || ArrivedAt < 0.0)
	{
		return true;
	}
	const double Since = Now - ArrivedAt;
	UCharacterMovementComponent* const Move = Hero->GetCharacterMovement();

	if (JumpPhase == 0 && Since >= kJumpArmS)
	{
		JumpPhase = 1;
		JumpStartedAt = Now;
		JumpGroundZ = Hero->GetActorLocation().Z;
		JumpRiseCm = 0.0;
		bJumpLeftGround = false;
		// The same press the template's Enhanced Input binding makes: IA_Jump
		// Started -> Jump(), Completed -> StopJumping().
		Hero->Jump();
	}
	else if (JumpPhase == 1)
	{
		JumpRiseCm = FMath::Max(JumpRiseCm, Hero->GetActorLocation().Z - JumpGroundZ);
		if (Move != nullptr && Move->IsFalling())
		{
			bJumpLeftGround = true;
		}
		if (Now - JumpStartedAt >= kJumpPressS)
		{
			Hero->StopJumping();
			JumpPhase = 2;
		}
	}
	else if (JumpPhase == 2)
	{
		JumpRiseCm = FMath::Max(JumpRiseCm, Hero->GetActorLocation().Z - JumpGroundZ);
		if (Move != nullptr && Move->IsFalling())
		{
			bJumpLeftGround = true;
		}
		if (Now - JumpStartedAt >= kJumpWatchS)
		{
			JumpPhase = 3;
			++JumpTestsDone;
			const bool bLeft = bJumpLeftGround || JumpRiseCm >= kJumpRiseCm;
			if (S.JumpTest == 1 && !bLeft)
			{
				Fail(TEXT("EmptyHandedYouJumpNormally"), FString::Printf(
					TEXT("with empty hands the character rose %.0f cm in %.1f s and ")
					TEXT("never left the ground; empty-handed it jumps as it always ")
					TEXT("did"), JumpRiseCm, kJumpWatchS));
				return false;
			}
			if (S.JumpTest == 2 && bLeft)
			{
				Fail(TEXT("CarryingStopsYouJumping"), FString::Printf(
					TEXT("carrying a crate the character left the ground and rose ")
					TEXT("%.0f cm; carrying, it cannot jump at all, whatever asks"),
					JumpRiseCm));
				return false;
			}
		}
	}
	return true;
}

bool AHaulCarryFunctionalTest::GateSpeeds(double Now)
{
	if (!Route.IsValidIndex(Stop))
	{
		return true;
	}
	const FHaulStop& S = Route[Stop];
	if (S.Measure == 0 || ArrivedAt >= 0.0)
	{
		return true;
	}
	if (Now - LegStartedAt < kLegSettleS || HeroSpeed < kMinSpeedToJudge)
	{
		return true;
	}
	if (S.Measure == 1)
	{
		FreeSpeed = (FreeSpeed * FreeSamples + HeroSpeed) / (FreeSamples + 1);
		++FreeSamples;
	}
	else if (S.Measure == 2)
	{
		CarrySpeed = (CarrySpeed * CarrySamples + HeroSpeed) / (CarrySamples + 1);
		++CarrySamples;
	}
	else if (S.Measure == 3)
	{
		BackSpeed = (BackSpeed * BackSamples + HeroSpeed) / (BackSamples + 1);
		++BackSamples;
	}
	return true;
}

// ---------------------------------------------------------------------------
//  DRIVE
// ---------------------------------------------------------------------------

void AHaulCarryFunctionalTest::DriveHero(double Now)
{
	if (!Route.IsValidIndex(Stop))
	{
		return;
	}
	const FHaulStop& S = Route[Stop];
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = (S.CrateIndex >= 0)
		? Crates[S.CrateIndex]->GetActorLocation() : S.Target;
	const double Arrive = (S.CrateIndex >= 0) ? kAtCrateCm : kWaypointCm;

	const double Eff = (FreeSamples >= kMinSamples) ? FreeSpeed : 500.0;
	const double Deadline = LegLengthCm / (0.25 * FMath::Max(Eff, 200.0))
		+ kLegSlackS + S.Dwell + S.Press;
	if (ArrivedAt < 0.0 && Now - LegStartedAt > Deadline)
	{
		Fail(TEXT("TheHaulRanBothRounds"), FString::Printf(
			TEXT("the run stopped at stop %d of %d (%s): the character covered %.0f cm ")
			TEXT("of a %.0f cm leg in %.0f s"), Stop, Route.Num(), *S.Label,
			FVector::Dist2D(LegStartedFrom, Here), LegLengthCm, Now - LegStartedAt));
		return;
	}

	if (S.Press > 0.0)
	{
		// The push leg never arrives: the wall is meant to stop it. It advances
		// once the character has been jammed for the disclosed while.
		FVector Dir = Target - Here;
		Dir.Z = 0.0;
		Hero->AddMovementInput(Dir.GetSafeNormal(), 1.0f);
		if (HeroSpeed < kMinSpeedToJudge)
		{
			if (ArrivedAt < 0.0)
			{
				ArrivedAt = Now;
			}
			else if (Now - ArrivedAt >= S.Press)
			{
				++Stop;
				ArrivedAt = -1.0;
				LegPrevDist = -1.0;
				LegStartedAt = Now;
				LegStartedFrom = Here;
				LegLengthCm = Route.IsValidIndex(Stop)
					? FVector::Dist2D(Here, Route[Stop].CrateIndex >= 0
						? Crates[Route[Stop].CrateIndex]->GetActorLocation()
						: Route[Stop].Target)
					: 0.0;
			}
		}
		else
		{
			ArrivedAt = -1.0;
		}
		return;
	}

	if (ArrivedAt < 0.0)
	{
		const double D = FVector::Dist2D(Here, Target);
		// Arrived, OR overshot: a character moving faster than the yard's own
		// 500 uu/s can step over a 25 cm window in one 20 FPS frame, and a leg
		// deadline would then read as a jam when the fault is the speed.
		const bool bOvershot = S.CrateIndex < 0 && LegPrevDist > 0.0
			&& D > LegPrevDist && D < Arrive + 125.0;
		// A CRATE STOP ALSO ARRIVES WHEN THE CRATE IS IN HAND, and without this the
		// drive can never reach one it is already carrying. The numbers say why: the
		// yard hands a crate over at 250 cm (PICKUP_CM), the drive calls it arrived at
		// 240 (kAtCrateCm), and a carried crate rides 330 cm ahead. So the crate is
		// taken one step BEFORE the arrival window opens and then stays outside it
		// forever -- the character walks after its own load and the leg times out
		// 12,761 cm from where it started. Measured 2026-08-20, and only once the
		// carry height was corrected: while the crate was riding 31 cm too low the
		// swept move jammed it against the character, D stayed small, and arrival
		// latched by accident. A correct carry is what exposed the drive.
		// "In hand" is read from the world, not from the submission: the crate's own
		// solid underside is clear of the floor by more than a crate can rest.
		bool bInHand = false;
		if (S.CrateIndex >= 0 && Crates.IsValidIndex(S.CrateIndex)
			&& Crates[S.CrateIndex].IsValid())
		{
			const FBox CrateBox = SolidBox(Crates[S.CrateIndex].Get());
			bInHand = CrateBox.IsValid != 0
				&& (CrateBox.Min.Z - FloorTopZ) > kCarriedClearCm;
		}
		if (D <= Arrive || bOvershot || bInHand)
		{
			ArrivedAt = Now;
			JumpPhase = 0;
		}
		else
		{
			FVector Dir = Target - Here;
			Dir.Z = 0.0;
			Hero->AddMovementInput(Dir.GetSafeNormal(), 1.0f);
		}
		LegPrevDist = D;
		return;
	}

	// STANDING. Advancing on arrival consumes waypoints instantly and nothing is
	// ever measured; every stop stands for its own dwell first.
	const bool bJumpBusy = S.JumpTest != 0 && JumpPhase < 3;
	if (!bJumpBusy && Now - ArrivedAt >= S.Dwell)
	{
		if (S.bReprice && !bRepricedThisStop)
		{
			PriceYard(2);
			RepricedAt = Now;
			bRepricedThisStop = true;
			return;   // let the new prices be read for a frame before moving on
		}
		++Stop;
		ArrivedAt = -1.0;
		LegPrevDist = -1.0;
		bRepricedThisStop = false;
		LegStartedAt = Now;
		LegStartedFrom = Here;
		LegLengthCm = Route.IsValidIndex(Stop)
			? FVector::Dist2D(Here, Route[Stop].CrateIndex >= 0
				? Crates[Route[Stop].CrateIndex]->GetActorLocation()
				: Route[Stop].Target)
			: 0.0;
	}
}

void AHaulCarryFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || Route.Num() == 0
		|| DeltaSeconds <= SMALL_NUMBER)
	{
		return;
	}
	for (const TWeakObjectPtr<AActor>& C : Crates)
	{
		if (!C.IsValid())
		{
			Precondition(TEXT("a crate went away mid-run"));
			return;
		}
	}
	const UWorld* const World = GetWorld();
	const double Now = World != nullptr
		? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	// MEASURED ground speed, smoothed so one hitching frame cannot decide anything.
	const FVector HeroAt = Hero->GetActorLocation();
	if (bHavePrev)
	{
		const double Raw = FVector::Dist2D(HeroAt, HeroPrev) / DeltaSeconds;
		HeroSpeed = HeroSpeed + (Raw - HeroSpeed) * kSpeedSmoothing;
	}

	if (!GateRideAndWalls(Now)) { HeroPrev = HeroAt; bHavePrev = true; return; }
	if (!GatePlatesAndDoors(Now)) { HeroPrev = HeroAt; bHavePrev = true; return; }
	if (!GateYardStaysPut(Now)) { HeroPrev = HeroAt; bHavePrev = true; return; }
	if (!GateJump(Now)) { HeroPrev = HeroAt; bHavePrev = true; return; }
	if (!GateSpeeds(Now)) { HeroPrev = HeroAt; bHavePrev = true; return; }
	DriveHero(Now);

	HeroPrev = HeroAt;
	bHavePrev = true;
}

void AHaulCarryFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const int32 Riding = RidingCrateIndex();
	UE_LOG(LogTemp, Display,
		TEXT("[t2-haul calib] cp%d t=%.1f stop=%d/%d riding=%d spd=%.0f free=%.0f ")
		TEXT("carry=%.0f back=%.0f round=%d picks=%d loadL=%.0f liftL=%.0f loadH=%.0f ")
		TEXT("liftH=%.0f spellsL=%d spellsH=%d"),
		Index, Now, Stop, Route.Num(), Riding, HeroSpeed, FreeSpeed, CarrySpeed,
		BackSpeed, PriceRound, PickUps,
		Plates.Num() > 0 ? LoadOnPlateKg(0) : 0.0,
		Plates.Num() > 0 ? DoorLiftCm(Plates[0].DoorIndex) : 0.0,
		Plates.Num() > 1 ? LoadOnPlateKg(1) : 0.0,
		Plates.Num() > 1 ? DoorLiftCm(Plates[1].DoorIndex) : 0.0,
		Doors.Num() > 0 ? Doors[0].OpenSpells : 0,
		Doors.Num() > 1 ? Doors[1].OpenSpells : 0);
}

void AHaulCarryFunctionalTest::OnCheckpoint(int32 Index, double TimeSeconds)
{
	if (!Hero.IsValid() || Route.Num() == 0)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World != nullptr
		? static_cast<double>(World->GetTimeSeconds()) : TimeSeconds;
	LogCalib(Index, Now);

	if (TimeSeconds < kSentinelS - 1.0)
	{
		return;
	}

	// ------------------------------ THE SENTINEL ------------------------------
	if (Stop < Route.Num())
	{
		Fail(TEXT("TheHaulRanBothRounds"), FString::Printf(
			TEXT("the run reached stop %d of %d (%s) in %.0f s, so most of what the ")
			TEXT("yard asks for was never measured"),
			Stop, Route.Num(), *Route[Stop].Label, Now));
		return;
	}
	if (PriceRound != 2)
	{
		Fail(TEXT("TheHaulRanBothRounds"),
			TEXT("the yard was never re-priced, so the second round never happened"));
		return;
	}
	if (FreeSamples < kMinSamples)
	{
		Fail(TEXT("WalksAtItsNormalTopSpeedEmptyHanded"), FString::Printf(
			TEXT("the character never walked a clean stretch empty-handed (%d samples ")
			TEXT("of %d), so nothing about its speed was measured"),
			FreeSamples, kMinSamples));
		return;
	}
	if (FreeSpeed < kFreeSpeedMin || FreeSpeed > kFreeSpeedMax)
	{
		Fail(TEXT("WalksAtItsNormalTopSpeedEmptyHanded"), FString::Printf(
			TEXT("empty-handed the character measured %.0f units a second, and the ")
			TEXT("yard asks for %.0f-%.0f"), FreeSpeed, kFreeSpeedMin, kFreeSpeedMax));
		return;
	}
	if (CarrySamples < kMinSamples)
	{
		Fail(TEXT("CarryingSlowsYouDown"), FString::Printf(
			TEXT("the character never walked a clean stretch carrying a crate (%d ")
			TEXT("samples of %d)"), CarrySamples, kMinSamples));
		return;
	}
	const double CarryFrac = CarrySpeed / FMath::Max(FreeSpeed, 1.0);
	if (CarryFrac < kCarryFracMin || CarryFrac > kCarryFracMax)
	{
		Fail(TEXT("CarryingSlowsYouDown"), FString::Printf(
			TEXT("carrying, the character measured %.0f units a second against %.0f ")
			TEXT("empty-handed - that is %.0f%%, and carrying is meant to cost you ")
			TEXT("(%.0f-%.0f%%)"), CarrySpeed, FreeSpeed, CarryFrac * 100.0,
			kCarryFracMin * 100.0, kCarryFracMax * 100.0));
		return;
	}
	if (BackSamples < kMinSamples)
	{
		Fail(TEXT("SettingItDownGivesYourSpeedBack"), FString::Printf(
			TEXT("the character never walked a clean stretch after setting a crate ")
			TEXT("down (%d samples of %d)"), BackSamples, kMinSamples));
		return;
	}
	const double BackFrac = BackSpeed / FMath::Max(FreeSpeed, 1.0);
	if (BackFrac < kBackFracMin || BackFrac > kBackFracMax)
	{
		Fail(TEXT("SettingItDownGivesYourSpeedBack"), FString::Printf(
			TEXT("after setting the crate down the character measured %.0f units a ")
			TEXT("second against %.0f empty-handed - that is %.0f%%, and the yard asks ")
			TEXT("for %.0f-%.0f%%"), BackSpeed, FreeSpeed, BackFrac * 100.0,
			kBackFracMin * 100.0, kBackFracMax * 100.0));
		return;
	}
	if (JumpTestsDone < 2)
	{
		Fail(TEXT("CarryingStopsYouJumping"), FString::Printf(
			TEXT("only %d of the 2 jump tries happened, so jumping was never ")
			TEXT("measured on both sides"), JumpTestsDone));
		return;
	}
	for (int32 d = 0; d < Doors.Num(); ++d)
	{
		if (Doors[d].OpenSpells < 2 || Doors[d].Drops < 1)
		{
			Fail(TEXT("EachDoorLiftsMoreThanOnce"), FString::Printf(
				TEXT("door %d lifted on %d separate occasions and dropped %d times; ")
				TEXT("each door is asked for twice, with a shut in between"),
				d, Doors[d].OpenSpells, Doors[d].Drops));
			return;
		}
	}
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("both rounds hauled: the crate rode in front, stayed out of the walls, ")
		TEXT("cost half the walking speed and all of the jumping and gave both back, ")
		TEXT("and each plate held its own door for its own weight through a re-price ")
		TEXT("that moved nothing"));
}
