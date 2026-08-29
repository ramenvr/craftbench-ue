// Copyright CraftBench. All Rights Reserved.

#include "CheckpointRestoreFunctionalTest.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerStart.h"
#include "Kismet/GameplayStatics.h"

// The yard's supplied props. Staging reads only -- ids, the authored slide, the trigger
// volumes, the hazards' announcement. Every GRADED read below is a visible consequence:
// a leaf's world position, a coin mesh's visibility, a lamp's intensity, the two faces
// on the counter, the character's own location.
#include "Tasks/t3-checkpoint-restores-the-world/CheckpointYardProps.h"

namespace
{
	// ---- VERIFIER SLACK: wider than the prompt, never tighter -------------
	// The prompt promises the character is back at the mark "within a second".
	constexpr double kJudgeAtS = 2.0;        // twice what was promised
	constexpr double kHazardClearS = 3.0;    // and clear of hot floor for this long
	constexpr double kDeathHoldS = 5.0;      // input off for the whole judging window
	constexpr double kChangeWindowS = 0.5;   // "within half a second of standing on it"
	constexpr double kSettleS = 1.0;
	constexpr double kReuseWithinS = 1.0;
	constexpr double kMarkTolUu = 200.0;
	constexpr double kEntranceTolUu = 300.0;
	constexpr double kLeafTolUu = 20.0;

	// ---- UNDISCLOSED: fixture clocking, geometry and staging --------------
	constexpr double kDwellS = 2.0;          // stand still at every stop, or nothing settles
	constexpr double kWaypointUu = 70.0;
	constexpr double kMobilityWindowS = 8.0;
	constexpr double kMobilityUu = 400.0;
	// Capsule radius 42 and half height 96 on this substrate's character
	// (ThirdPersonCharacter.cpp: InitCapsuleSize(42, 96)), plus 60 uu of margin. A box
	// grown by this is a STRICT SUPERSET of the region in which the engine's own
	// capsule-versus-box overlap can fire, which is the whole point: the fixture's
	// window may open early, never late. The margin is 60 rather than the arithmetic
	// minimum of 0 because the 20 FPS leg advances 25 uu a frame, and route clearance
	// is held at 220 uu, so a window reaching 102 uu still cannot open on a prop the
	// script is not aimed at.
	constexpr double kGrowXYUu = 102.0;
	constexpr double kGrowZUu = 156.0;

	constexpr int32 kMinPads = 3;
	constexpr int32 kMinDoors = 3;
	constexpr int32 kMinCoins = 5;
	constexpr int32 kMinHazards = 2;
	constexpr double kMinLeafSpreadUu = 300.0;
	constexpr double kMinRespawnToHazardUu = 1500.0;   // 3 s of walking at 500 uu/s
	constexpr double kMinRespawnToCounterUu = 1500.0;
	constexpr double kMinRespawnToCoinUu = 400.0;
	constexpr double kMinCorridorClearUu = 600.0;
	constexpr double kMinCrossClearUu = 220.0;
	constexpr double kMinTriggerHalfUu = 100.0;        // 200 uu deep: no tunnelling at 20 FPS
	constexpr double kCoinMoveClearUu = 500.0;

	constexpr double kSentinelS = 720.0;
	constexpr int32 kSentinelIndex = 60;

	/** The first run of digits in a string, or -1. The counter's faces are bare
	 *  numbers by construction; this is what a player reads off them. */
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

	const TCHAR* PlaceName(int32 Place)
	{
		switch (Place)
		{
			case 0: return TEXT("on its stand");
			case 1: return TEXT("in hand");
			default: return TEXT("over the line");
		}
	}
}

ACheckpointRestoreFunctionalTest::ACheckpointRestoreFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Failure helpers -- one place, so every message keeps its own literal.
// ---------------------------------------------------------------------------

void ACheckpointRestoreFunctionalTest::Fail(const FString& Message)
{
	if (bGraded)
	{
		return;
	}
	bGraded = true;
	FinishTest(EFunctionalTestResult::Failed, Message);
}

void ACheckpointRestoreFunctionalTest::Precondition(const FString& Message)
{
	if (bGraded)
	{
		return;
	}
	bGraded = true;
	FinishTest(EFunctionalTestResult::Error,
		FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Message));
}

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

FVector ACheckpointRestoreFunctionalTest::HeroAt() const
{
	return Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
}

bool ACheckpointRestoreFunctionalTest::InVolume(const UBoxComponent* Box,
	const FVector& P, bool bGrow) const
{
	if (Box == nullptr)
	{
		return false;
	}
	const FVector Rel = Box->GetComponentQuat().UnrotateVector(P - Box->GetComponentLocation());
	FVector E = Box->GetScaledBoxExtent();
	if (bGrow)
	{
		E += FVector(kGrowXYUu, kGrowXYUu, kGrowZUu);
	}
	return FMath::Abs(Rel.X) <= E.X && FMath::Abs(Rel.Y) <= E.Y && FMath::Abs(Rel.Z) <= E.Z;
}

bool ACheckpointRestoreFunctionalTest::Touching(const UBoxComponent* Box) const
{
	// EXACTLY what the prop's own trigger sees, and nothing more. Used where the
	// fixture must not know something the submission was never told.
	return Box != nullptr && Hero.IsValid() && Box->IsOverlappingActor(Hero.Get());
}

bool ACheckpointRestoreFunctionalTest::InWindow(const UBoxComponent* Box) const
{
	// ONE-SIDED BY CONSTRUCTION. The union of the prop's own overlap set and a box
	// grown past the capsule: it is true whenever the prop's trigger could have fired,
	// and true for about a capsule radius of travel BEFORE that. The direction matters
	// -- a window that opened late would score the prop's own instant reaction as an
	// unsanctioned change, on every submission ever made.
	return Touching(Box) || InVolume(Box, HeroAt(), /*bGrow=*/true);
}

double ACheckpointRestoreFunctionalTest::DistToVolume(const UBoxComponent* Box,
	const FVector& P) const
{
	if (Box == nullptr)
	{
		return TNumericLimits<double>::Max();
	}
	const FVector Rel = Box->GetComponentQuat().UnrotateVector(P - Box->GetComponentLocation());
	const FVector E = Box->GetScaledBoxExtent();
	// Flat distance: the yard is one storey and every rule that uses this is about
	// where somebody is standing, not how high they are.
	const double DX = FMath::Max(0.0, FMath::Abs(Rel.X) - E.X);
	const double DY = FMath::Max(0.0, FMath::Abs(Rel.Y) - E.Y);
	return FMath::Sqrt(DX * DX + DY * DY);
}

const UBoxComponent* ACheckpointRestoreFunctionalTest::PropVolume(const FStop& S) const
{
	switch (S.Kind)
	{
		case EStopKind::DoorPlate:
			return Doors.IsValidIndex(S.Index) && Doors[S.Index].Actor.IsValid()
				? Doors[S.Index].Actor->PlateTrigger : nullptr;
		case EStopKind::CoinStand:
			return Coins.IsValidIndex(S.Index) && Coins[S.Index].Actor.IsValid()
				? Coins[S.Index].Actor->Trigger : nullptr;
		case EStopKind::Pad:
			return Pads.IsValidIndex(S.Index) && Pads[S.Index].Actor.IsValid()
				? Pads[S.Index].Actor->Trigger : nullptr;
		case EStopKind::Counter:
			return Counter.IsValid() ? Counter->Trigger : nullptr;
		case EStopKind::Hazard:
			return Hazards.IsValidIndex(S.Index) && Hazards[S.Index].IsValid()
				? Hazards[S.Index]->Trigger : nullptr;
		default:
			return nullptr;
	}
}

FVector ACheckpointRestoreFunctionalTest::StopLocation(const FStop& S) const
{
	if (S.Kind == EStopKind::Clear)
	{
		// Off the last pad and out into the walking lane, so "can they still move"
		// is answered by them actually going somewhere.
		const FVector Pad = Pads.IsValidIndex(S.Index) && Pads[S.Index].Actor.IsValid()
			? Pads[S.Index].Actor->GetActorLocation() : Entrance;
		return FVector(Pad.X, CorridorY, Pad.Z);
	}
	if (const UBoxComponent* const Box = PropVolume(S))
	{
		return Box->GetComponentLocation();
	}
	return Entrance;
}

// ---------------------------------------------------------------------------
// Reads -- every one of them a visible consequence
// ---------------------------------------------------------------------------

ACheckpointRestoreFunctionalTest::EDoorState
ACheckpointRestoreFunctionalTest::ReadDoor(const FDoorRec& D) const
{
	if (!D.Actor.IsValid() || D.Actor->Leaf == nullptr)
	{
		return EDoorState::Neither;
	}
	const FVector At = D.Actor->Leaf->GetComponentLocation();
	if (FVector::Dist(At, D.ShutAt) <= kLeafTolUu)
	{
		return EDoorState::Shut;
	}
	if (FVector::Dist(At, D.OpenAt) <= kLeafTolUu)
	{
		return EDoorState::Open;
	}
	return EDoorState::Neither;
}

bool ACheckpointRestoreFunctionalTest::ReadCoinVisible(const FCoinRec& C) const
{
	if (!C.Actor.IsValid() || C.Actor->Coin == nullptr)
	{
		return false;
	}
	const UStaticMeshComponent* const M = C.Actor->Coin;
	return M->IsVisible() && !M->bHiddenInGame;
}

bool ACheckpointRestoreFunctionalTest::ReadPadLit(const FPadRec& P) const
{
	// THE LAMP, never a flag. A pad that says it is the mark without showing it tells
	// a player nothing.
	if (!P.Actor.IsValid() || P.Actor->Lamp == nullptr)
	{
		return false;
	}
	const UPointLightComponent* const L = P.Actor->Lamp;
	return L->IsVisible() && !L->bHiddenInGame && L->Intensity > 0.0f;
}

int32 ACheckpointRestoreFunctionalTest::ReadCarriedFace() const
{
	if (!Counter.IsValid() || Counter->CarriedText == nullptr)
	{
		return -1;
	}
	return FirstDigitRun(Counter->CarriedText->Text.ToString());
}

int32 ACheckpointRestoreFunctionalTest::ReadBankedFace() const
{
	if (!Counter.IsValid() || Counter->BankedText == nullptr)
	{
		return -1;
	}
	return FirstDigitRun(Counter->BankedText->Text.ToString());
}

int32 ACheckpointRestoreFunctionalTest::CountInHand() const
{
	int32 N = 0;
	for (const FCoinRec& C : Coins)
	{
		if (C.Place == ECoinPlace::InHand)
		{
			++N;
		}
	}
	return N;
}

FString ACheckpointRestoreFunctionalTest::HandList() const
{
	FString S;
	for (const FCoinRec& C : Coins)
	{
		if (C.Place == ECoinPlace::InHand)
		{
			S += FString::Printf(TEXT("%s%s"), S.IsEmpty() ? TEXT("") : TEXT("+"),
				*C.Id.ToString());
		}
	}
	return S.IsEmpty() ? FString(TEXT("nothing")) : S;
}

// ---------------------------------------------------------------------------
// Staging
// ---------------------------------------------------------------------------

bool ACheckpointRestoreFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();

	auto ByTag = [&](const TCHAR* Tag, TArray<AActor*>& Out)
	{
		UGameplayStatics::GetAllActorsWithTag(World, FName(Tag), Out);
		Out.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	};

	TArray<AActor*> Found;

	ByTag(TEXT("CheckpointStand"), Found);
	for (AActor* A : Found)
	{
		ACheckpointStandActor* const P = Cast<ACheckpointStandActor>(A);
		if (P == nullptr || P->Trigger == nullptr || P->Lamp == nullptr)
		{
			Precondition(TEXT("an actor tagged CheckpointStand is not a checkpoint pad "
				"with a volume and a lamp, so the fixture cannot tell where somebody "
				"stood or which pad is lit"));
			return false;
		}
		FPadRec R;
		R.Actor = P;
		R.Order = P->StandOrder;
		Pads.Add(R);
	}
	if (Pads.Num() < kMinPads)
	{
		Precondition(FString::Printf(TEXT("%d checkpoint pad(s) in the yard, expected at "
			"least %d; the mark has to be able to move backwards as well as forwards"),
			Pads.Num(), kMinPads));
		return false;
	}
	Pads.Sort([](const FPadRec& L, const FPadRec& R) { return L.Order < R.Order; });
	for (int32 i = 1; i < Pads.Num(); ++i)
	{
		if (Pads[i].Order == Pads[i - 1].Order)
		{
			Precondition(FString::Printf(TEXT("two pads both carry StandOrder %d; the "
				"pads have to be tellable apart by their numbering for the gate that "
				"says the numbering is NOT the answer to mean anything"), Pads[i].Order));
			return false;
		}
	}

	ByTag(TEXT("LatchDoor"), Found);
	for (AActor* A : Found)
	{
		ALatchDoorActor* const D = Cast<ALatchDoorActor>(A);
		if (D == nullptr || D->Leaf == nullptr || D->PlateTrigger == nullptr)
		{
			Precondition(TEXT("an actor tagged LatchDoor is not a door with a leaf and a "
				"plate volume, so the fixture cannot tell whether it is open"));
			return false;
		}
		FDoorRec R;
		R.Actor = D;
		R.Id = D->DoorId;
		// The two places the leaf lives, taken from where it ACTUALLY is at the start of
		// play plus the slide this door was authored with -- not from a number written
		// down here, and not from a function a submission could redefine.
		R.ShutAt = D->Leaf->GetComponentLocation();
		R.OpenAt = R.ShutAt + D->GetActorQuat().RotateVector(
			FVector(0.0, static_cast<double>(D->OpenSlideUu), 0.0));
		R.State = EDoorState::Shut;
		Doors.Add(R);
	}
	if (Doors.Num() < kMinDoors)
	{
		Precondition(FString::Printf(TEXT("%d door(s) in the yard, expected at least %d; "
			"a mark has to be set with some doors open and some shut"),
			Doors.Num(), kMinDoors));
		return false;
	}
	Doors.Sort([](const FDoorRec& L, const FDoorRec& R)
	{
		return L.Id.ToString() < R.Id.ToString();
	});
	for (const FDoorRec& D : Doors)
	{
		if (FVector::Dist(D.ShutAt, D.OpenAt) < kMinLeafSpreadUu)
		{
			Precondition(FString::Printf(TEXT("door %s slides only %.0f uu, and %.0f uu "
				"is the least this fixture can tell apart from a jitter"),
				*D.Id.ToString(), FVector::Dist(D.ShutAt, D.OpenAt), kMinLeafSpreadUu));
			return false;
		}
		if (D.Actor.IsValid() && D.Actor->IsOpen())
		{
			Precondition(FString::Printf(TEXT("door %s is already open when the yard "
				"opens; the first death is graded against the opening state and would "
				"measure nothing"), *D.Id.ToString()));
			return false;
		}
	}
	for (int32 i = 1; i < Doors.Num(); ++i)
	{
		if (Doors[i].Id == Doors[i - 1].Id)
		{
			Precondition(FString::Printf(TEXT("two doors both carry DoorId %s; a door "
				"that cannot be named cannot be judged"), *Doors[i].Id.ToString()));
			return false;
		}
	}

	ByTag(TEXT("CoinPickup"), Found);
	for (AActor* A : Found)
	{
		ACoinPickupActor* const C = Cast<ACoinPickupActor>(A);
		if (C == nullptr || C->Coin == nullptr || C->Trigger == nullptr)
		{
			Precondition(TEXT("an actor tagged CoinPickup is not a coin with a mesh and a "
				"volume, so the fixture cannot tell whether it has been taken"));
			return false;
		}
		FCoinRec R;
		R.Actor = C;
		R.Id = C->CoinId;
		R.Place = ECoinPlace::OnStand;
		R.bVisible = true;
		R.StagedAt = C->GetActorLocation();
		Coins.Add(R);
	}
	if (Coins.Num() < kMinCoins)
	{
		Precondition(FString::Printf(TEXT("%d coin(s) in the yard, expected at least %d; "
			"the script needs coins over the line, coins in hand and coins on their "
			"stands all at once"), Coins.Num(), kMinCoins));
		return false;
	}
	Coins.Sort([](const FCoinRec& L, const FCoinRec& R)
	{
		return L.Id.ToString() < R.Id.ToString();
	});
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (i > 0 && Coins[i].Id == Coins[i - 1].Id)
		{
			Precondition(FString::Printf(TEXT("two coins both carry CoinId %s; a coin "
				"that cannot be named cannot be ledgered"), *Coins[i].Id.ToString()));
			return false;
		}
		if (!ReadCoinVisible(Coins[i]))
		{
			Precondition(FString::Printf(TEXT("coin %s is already gone when the yard "
				"opens"), *Coins[i].Id.ToString()));
			return false;
		}
	}

	ByTag(TEXT("BankCounter"), Found);
	if (Found.Num() != 1)
	{
		Precondition(FString::Printf(TEXT("%d actor(s) tagged BankCounter, expected "
			"exactly one"), Found.Num()));
		return false;
	}
	Counter = Cast<ABankCounterActor>(Found[0]);
	if (!Counter.IsValid() || Counter->Trigger == nullptr
		|| Counter->CarriedText == nullptr || Counter->BankedText == nullptr)
	{
		Precondition(TEXT("the counter has no line volume or no readable faces, so the "
			"fixture cannot read the two numbers a player reads"));
		return false;
	}

	ByTag(TEXT("HazardStrip"), Found);
	for (AActor* A : Found)
	{
		AHazardStripActor* const H = Cast<AHazardStripActor>(A);
		if (H == nullptr || H->Trigger == nullptr)
		{
			Precondition(TEXT("an actor tagged HazardStrip is not hot floor with a "
				"volume"));
			return false;
		}
		Hazards.Add(H);
		H->OnLethalTouch.AddDynamic(this, &ACheckpointRestoreFunctionalTest::OnHazardTouched);
	}
	if (Hazards.Num() < kMinHazards)
	{
		Precondition(FString::Printf(TEXT("%d strip(s) of hot floor, expected at least "
			"%d; the script ends three lives and no two in a row on the same strip"),
			Hazards.Num(), kMinHazards));
		return false;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		Precondition(TEXT("no visibly represented player character in the yard"));
		return false;
	}
	Entrance = Hero->GetActorLocation();
	Entrances.Add(Entrance);
	TArray<AActor*> Starts;
	UGameplayStatics::GetAllActorsOfClass(World, APlayerStart::StaticClass(), Starts);
	for (const AActor* S : Starts)
	{
		if (S != nullptr)
		{
			Entrances.Add(S->GetActorLocation());
		}
	}

	// Every volume has to be deep enough that a walking character cannot step over it
	// between two frames. At 20 FPS -- the second graded leg -- that step is 25 uu.
	TArray<const UBoxComponent*> AllVolumes;
	for (const FPadRec& P : Pads)   { if (P.Actor.IsValid()) AllVolumes.Add(P.Actor->Trigger); }
	for (const FDoorRec& D : Doors) { if (D.Actor.IsValid()) AllVolumes.Add(D.Actor->PlateTrigger); }
	for (const FCoinRec& C : Coins) { if (C.Actor.IsValid()) AllVolumes.Add(C.Actor->Trigger); }
	AllVolumes.Add(Counter->Trigger);
	for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
	{
		if (H.IsValid()) { AllVolumes.Add(H->Trigger); }
	}
	for (const UBoxComponent* const B : AllVolumes)
	{
		if (B == nullptr)
		{
			Precondition(TEXT("a prop in the yard has no trigger volume"));
			return false;
		}
		const FVector E = B->GetScaledBoxExtent();
		if (FMath::Min(E.X, E.Y) < kMinTriggerHalfUu)
		{
			Precondition(FString::Printf(TEXT("a trigger volume is only %.0f uu deep; at "
				"20 FPS a walking character covers 25 uu a frame and would step over "
				"anything shallower than %.0f"),
				2.0 * FMath::Min(E.X, E.Y), 2.0 * kMinTriggerHalfUu));
			return false;
		}
	}

	OpeningBanked = ReadBankedFace();
	const int32 OpeningCarried = ReadCarriedFace();
	if (OpeningBanked < 0 || OpeningCarried < 0)
	{
		Precondition(TEXT("the counter's faces do not read as numbers, so the yard has "
			"no readable CARRIED or BANKED"));
		return false;
	}
	if (OpeningCarried != 0)
	{
		Precondition(FString::Printf(TEXT("the counter says %d coins are already in hand "
			"when the yard opens, and no coin is missing from its stand"),
			OpeningCarried));
		return false;
	}
	if (OpeningBanked <= 0)
	{
		Precondition(TEXT("BANKED reads 0 when the yard opens; a submission that zeroes "
			"the counter would be indistinguishable from one that left it alone"));
		return false;
	}
	BankedSeen = OpeningBanked;
	return true;
}

bool ACheckpointRestoreFunctionalTest::DeriveCorridor()
{
	// The walking lane is DERIVED, not written down: the yard's props sit in bands, and
	// the corridor is the middle of the widest empty band between them. Re-author the
	// level and the drive follows; make the yard too crowded to walk and the fixture
	// says so instead of jamming the character against something.
	TArray<double> Ys;
	for (const FPadRec& P : Pads)   { if (P.Actor.IsValid()) Ys.Add(P.Actor->Trigger->GetComponentLocation().Y); }
	for (const FDoorRec& D : Doors) { if (D.Actor.IsValid()) Ys.Add(D.Actor->PlateTrigger->GetComponentLocation().Y); }
	for (const FCoinRec& C : Coins) { if (C.Actor.IsValid()) Ys.Add(C.Actor->Trigger->GetComponentLocation().Y); }
	Ys.Add(Counter->Trigger->GetComponentLocation().Y);
	for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
	{
		if (H.IsValid()) { Ys.Add(H->Trigger->GetComponentLocation().Y); }
	}
	Ys.Sort();

	double Best = -1.0;
	for (int32 i = 1; i < Ys.Num(); ++i)
	{
		const double Gap = Ys[i] - Ys[i - 1];
		if (Gap > Best)
		{
			Best = Gap;
			CorridorY = 0.5 * (Ys[i] + Ys[i - 1]);
		}
	}
	if (Best < 0.0)
	{
		Precondition(TEXT("the yard has nothing to lay a walking lane between"));
		return false;
	}

	// Measured against the volumes themselves, not their centres.
	double Clear = TNumericLimits<double>::Max();
	double MinX = TNumericLimits<double>::Max();
	double MaxX = -TNumericLimits<double>::Max();
	TArray<const UBoxComponent*> All;
	for (const FPadRec& P : Pads)   { if (P.Actor.IsValid()) All.Add(P.Actor->Trigger); }
	for (const FDoorRec& D : Doors) { if (D.Actor.IsValid()) All.Add(D.Actor->PlateTrigger); }
	for (const FCoinRec& C : Coins) { if (C.Actor.IsValid()) All.Add(C.Actor->Trigger); }
	All.Add(Counter->Trigger);
	for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
	{
		if (H.IsValid()) { All.Add(H->Trigger); }
	}
	for (const UBoxComponent* const B : All)
	{
		const double X = B->GetComponentLocation().X;
		MinX = FMath::Min(MinX, X);
		MaxX = FMath::Max(MaxX, X);
	}
	MinX -= 400.0;
	MaxX += 400.0;
	constexpr int32 kSamples = 200;
	for (int32 k = 0; k <= kSamples; ++k)
	{
		const FVector P(FMath::Lerp(MinX, MaxX, double(k) / double(kSamples)),
			CorridorY, Entrance.Z);
		for (const UBoxComponent* const B : All)
		{
			Clear = FMath::Min(Clear, DistToVolume(B, P));
		}
	}
	if (Clear < kMinCorridorClearUu)
	{
		Precondition(FString::Printf(TEXT("the widest lane through the yard passes %.0f "
			"uu from something, and the drive needs %.0f; the yard is too crowded to "
			"walk without brushing props the script is not aiming at"),
			Clear, kMinCorridorClearUu));
		return false;
	}
	return true;
}

bool ACheckpointRestoreFunctionalTest::BuildScript()
{
	// TWENTY STOPS, ONE WALK, THREE DEATHS. Read it with the pads' numbering in mind:
	// the marks are set on the DEEPEST pad, then a shallower one, then the shallowest,
	// so recency and depth disagree at the last two deaths.
	auto Add = [&](EStopKind K, int32 I) { Script.Add({K, I}); };

	Add(EStopKind::DoorPlate, 0);   //  1  door 0 opens, before any mark exists
	Add(EStopKind::CoinStand, 0);   //  2  coin 0 taken
	Add(EStopKind::Hazard,    0);   //  3  DEATH 1, with no pad ever stood on
	Add(EStopKind::DoorPlate, 0);   //  4  door 0 must open again
	Add(EStopKind::CoinStand, 0);   //  5  coin 0 must be takeable again
	Add(EStopKind::CoinStand, 1);   //  6
	Add(EStopKind::Pad,       2);   //  7  MARK 1 on the DEEPEST pad
	Add(EStopKind::DoorPlate, 1);   //  8  door 1 opens after mark 1
	Add(EStopKind::Pad,       1);   //  9  MARK 2, doubling back
	Add(EStopKind::CoinStand, 2);   // 10
	Add(EStopKind::Counter,   0);   // 11  three coins go over the line
	Add(EStopKind::DoorPlate, 2);   // 12  door 2 opens after mark 2
	Add(EStopKind::Hazard,    1);   // 13  DEATH 2
	Add(EStopKind::DoorPlate, 2);   // 14  door 2 must open again
	Add(EStopKind::CoinStand, 3);   // 15
	Add(EStopKind::Pad,       0);   // 16  MARK 3 on the SHALLOWEST pad
	Add(EStopKind::CoinStand, 4);   // 17
	Add(EStopKind::Hazard,    0);   // 18  DEATH 3
	Add(EStopKind::CoinStand, 4);   // 19  coin 4 must be takeable again
	Add(EStopKind::Clear,     0);   // 20  and they must be able to walk away

	// NON-VACUITY, measured rather than hoped for. The script marks the pads in
	// DECREASING StandOrder, so recency and numbering can only disagree if the
	// numbering actually tracks how far into the yard a pad is. If the yard were laid
	// out with the numbers scrambled, "the pad furthest in wins" would not be a
	// reading anybody could hold and the headline gate would measure nothing.
	for (int32 i = 1; i < Pads.Num(); ++i)
	{
		const double Shallower = FVector::Dist2D(Entrance,
			Pads[i - 1].Actor->GetActorLocation());
		const double Deeper = FVector::Dist2D(Entrance,
			Pads[i].Actor->GetActorLocation());
		if (Deeper <= Shallower + 500.0)
		{
			Precondition(FString::Printf(TEXT("pad StandOrder %d sits %.0f uu from the "
				"entrance and pad StandOrder %d sits %.0f uu, so the pads are not "
				"numbered by how far into the yard they are and 'the one furthest in "
				"wins' is not a reading the mark gate could catch"),
				Pads[i - 1].Order, Shallower, Pads[i].Order, Deeper));
			return false;
		}
	}

	// EVERY DEATH IS FOLLOWED BY A FRESH MARK BEFORE THE NEXT ONE. That is what makes
	// the respawn re-entering the mark pad's own volume harmless: a submission that
	// honours the re-announced stand and one that suppresses it both end up with the
	// same mark, and any snapshot either of them takes at that instant is superseded
	// before it can be graded.
	int32 LastDeath = INDEX_NONE;
	for (int32 i = 0; i < Script.Num(); ++i)
	{
		if (Script[i].Kind == EStopKind::Hazard)
		{
			if (LastDeath != INDEX_NONE)
			{
				bool bMarked = false;
				for (int32 k = LastDeath + 1; k < i; ++k)
				{
					if (Script[k].Kind == EStopKind::Pad) { bMarked = true; break; }
				}
				if (!bMarked)
				{
					Precondition(TEXT("the script runs two deaths with no pad stood on "
						"between them; a snapshot taken at the respawn instant would "
						"then be the one graded, and two equally reasonable readings of "
						"the rule would disagree"));
					return false;
				}
			}
			LastDeath = i;
		}
	}

	int32 Deaths = 0;
	for (const FStop& S : Script)
	{
		if (S.Kind == EStopKind::Hazard) { ++Deaths; }
	}
	MovedAfterDeath.Init(false, Deaths);

	// THE OPENING SNAPSHOT, read off the world rather than assumed. Before anybody has
	// stood on a pad the mark is the way in, and the moment that mark was set is the
	// moment the yard opened -- so the first death is judged against exactly this.
	SnapDoorOpen.Init(false, Doors.Num());
	SnapCoinPlace.Init(ECoinPlace::OnStand, Coins.Num());
	for (int32 i = 0; i < Doors.Num(); ++i)
	{
		Doors[i].State = ReadDoor(Doors[i]);
		SnapDoorOpen[i] = (Doors[i].State == EDoorState::Open);
	}
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		Coins[i].bVisible = ReadCoinVisible(Coins[i]);
		Coins[i].Place = Coins[i].bVisible ? ECoinPlace::OnStand : ECoinPlace::InHand;
		SnapCoinPlace[i] = Coins[i].Place;
	}
	return true;
}

bool ACheckpointRestoreFunctionalTest::CheckRoute()
{
	// Every leg the drive walks is: straight out to the lane, along the lane, straight
	// in to the stop. The lane itself is already cleared above, so what is left to
	// check is the straight in-and-out at every place the drive ever stands -- every
	// prop, in every position it can occupy, plus every pad a life can send somebody
	// back to.
	TArray<const UBoxComponent*> All;
	for (const FPadRec& P : Pads)   { if (P.Actor.IsValid()) All.Add(P.Actor->Trigger); }
	for (const FDoorRec& D : Doors) { if (D.Actor.IsValid()) All.Add(D.Actor->PlateTrigger); }
	for (const FCoinRec& C : Coins) { if (C.Actor.IsValid()) All.Add(C.Actor->Trigger); }
	All.Add(Counter->Trigger);
	for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
	{
		if (H.IsValid()) { All.Add(H->Trigger); }
	}

	// The coins change places part way through, so the set of coin POSITIONS is what
	// matters, not which coin is at which -- and that set does not change. Checking
	// every position once therefore covers both halves of the run.
	for (const UBoxComponent* const Own : All)
	{
		const FVector From = Own->GetComponentLocation();
		const FVector To(From.X, CorridorY, From.Z);
		constexpr int32 kSamples = 40;
		for (int32 k = 0; k <= kSamples; ++k)
		{
			const FVector P = FMath::Lerp(From, To, double(k) / double(kSamples));
			for (const UBoxComponent* const B : All)
			{
				if (B == Own)
				{
					continue;
				}
				const double D = DistToVolume(B, P);
				if (D < kMinCrossClearUu)
				{
					Precondition(FString::Printf(TEXT("the straight walk in and out of "
						"one prop passes %.0f uu from another, and %.0f is the least "
						"that keeps the character from brushing something the script "
						"never aimed at"), D, kMinCrossClearUu));
					return false;
				}
			}
		}
	}

	// A pad somebody is sent back to must be far enough from hot floor that they are
	// not walking back into it before the fixture has finished judging, and far enough
	// from the line that a respawn cannot bank anything by accident.
	for (const FPadRec& P : Pads)
	{
		if (!P.Actor.IsValid())
		{
			continue;
		}
		const FVector R = P.Actor->GetRespawnTransform().GetLocation();
		for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
		{
			if (!H.IsValid()) { continue; }
			const double D = DistToVolume(H->Trigger, R);
			if (D < kMinRespawnToHazardUu)
			{
				Precondition(FString::Printf(TEXT("pad StandOrder %d sends somebody back "
					"%.0f uu from hot floor, and the gate then watches them stay clear of "
					"it for %.0f s -- %.0f uu of walking. Anything under %.0f uu makes "
					"that clause measure the drive rather than the answer"),
					P.Order, D, kHazardClearS, kHazardClearS * 500.0,
					kMinRespawnToHazardUu));
				return false;
			}
		}
		const double DK = DistToVolume(Counter->Trigger, R);
		if (DK < kMinRespawnToCounterUu)
		{
			Precondition(FString::Printf(TEXT("pad StandOrder %d sends somebody back "
				"%.0f uu from the line; a respawn that close could bank whatever is in "
				"hand without anybody choosing to"), P.Order, DK));
			return false;
		}
		for (const FCoinRec& C : Coins)
		{
			if (!C.Actor.IsValid()) { continue; }
			const double DC = DistToVolume(C.Actor->Trigger, R);
			if (DC < kMinRespawnToCoinUu)
			{
				Precondition(FString::Printf(TEXT("pad StandOrder %d sends somebody back "
					"%.0f uu from coin %s; a coin put back under somebody's feet would be "
					"taken again in the same breath"),
					P.Order, DC, *C.Id.ToString()));
				return false;
			}
		}
	}
	return true;
}

void ACheckpointRestoreFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		return;
	}
	if (!ResolveStaging() || !DeriveCorridor() || !BuildScript() || !CheckRoute())
	{
		return;
	}
	bStaged = true;
	BuildTransits();

	// Gauging instants every 6 s carry the calibration log and the camera plan. The
	// LAST entry is a SENTINEL far past the walk: the base class declares SUCCESS the
	// moment the last scheduled checkpoint is crossed, so a run that stalled half way
	// would otherwise finish green having graded nothing. A run that gets all the way
	// through finishes itself at stop twenty and never reaches the sentinel.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kSentinelIndex; ++k)
	{
		Schedule.Add(double(k) * 6.0);
	}
	Schedule.Add(kSentinelS);
	TimeLimitMargin = 6.0f;
	SetCheckpointSchedule(Schedule);

	UE_LOG(LogTemp, Display,
		TEXT("[t3-yard staging] %d pads %d doors %d coins %d hazards, lane y=%.0f, "
			 "BANKED opens at %d, entrance (%.0f,%.0f)"),
		Pads.Num(), Doors.Num(), Coins.Num(), Hazards.Num(), CorridorY, OpeningBanked,
		Entrance.X, Entrance.Y);
}

// ---------------------------------------------------------------------------
// Deaths
// ---------------------------------------------------------------------------

void ACheckpointRestoreFunctionalTest::OnHazardTouched(AActor* Victim)
{
	if (Hero.IsValid() && Victim == Hero.Get())
	{
		bDeathSignalled = true;
	}
}

void ACheckpointRestoreFunctionalTest::RegisterDeath(double Now)
{
	bDeathSignalled = false;
	bInDeathWindow = true;
	bHoldingInput = true;
	bJudgedThisDeath = false;
	DeathAt = Now;
	++DeathsRegistered;
	BankedBeforeDeath = ReadBankedFace();
	MarkAtDeath = MarkPad;
	DwellUntil = -1.0;
	// The mobility clock belongs to the death about to be judged, not to the last one.
	// Leaving the previous death's distance on the counter would satisfy this death's
	// clause the instant it was judged -- a gate that cannot fail.
	MobilityStartedAt = -1.0;
	MobilitySoFar = 0.0;
}

void ACheckpointRestoreFunctionalTest::ReleaseAfterDeath(double Now)
{
	bInDeathWindow = false;
	bHoldingInput = false;
	bDeathSignalled = false;
	DeathWindowEndedAt = Now;

	// THE COINS CHANGE PLACES once, after the second death has been judged. A
	// submission that remembered WHERE a coin was rather than WHICH coin it was is
	// wrong from here on; one that keyed on the coins themselves does not notice. The
	// moment is chosen because the character is standing on a mark, which every pad is
	// required to keep well clear of every stand, so nothing can be dropped on them.
	if (DeathsJudged == 2 && !bCoinsMoved)
	{
		MoveTheCoins();
	}

	MobilityStartedAt = Now;
	MobilitySoFar = 0.0;
	MobilityLastAt = HeroAt();

	// The hazard stop is finished by the death, not by standing about on it.
	if (Script.IsValidIndex(StepIndex) && Script[StepIndex].Kind == EStopKind::Hazard)
	{
		AdvanceStep(Now);
	}
	else
	{
		BuildTransits();
	}
}

void ACheckpointRestoreFunctionalTest::MoveTheCoins()
{
	bCoinsMoved = true;
	TArray<FVector> Was;
	for (const FCoinRec& C : Coins)
	{
		Was.Add(C.StagedAt);
	}
	const int32 Shift = 2;
	const FVector Here = HeroAt();
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		const FVector To = Was[(i + Shift) % Was.Num()];
		if (FVector::Dist2D(Here, To) < kCoinMoveClearUu)
		{
			Precondition(FString::Printf(TEXT("a coin would land %.0f uu from the "
				"character when the yard rearranges itself, and it would be taken by "
				"accident"), FVector::Dist2D(Here, To)));
			return;
		}
	}
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		const FVector To = Was[(i + Shift) % Was.Num()];
		if (Coins[i].Actor.IsValid())
		{
			Coins[i].Actor->SetActorLocation(To, /*bSweep=*/false);
		}
		Coins[i].StagedAt = To;
	}
	UE_LOG(LogTemp, Display, TEXT("[t3-yard] the coins changed places"));
}

void ACheckpointRestoreFunctionalTest::TakeSnapshot(double Now)
{
	for (int32 i = 0; i < Doors.Num(); ++i)
	{
		SnapDoorOpen[i] = (Doors[i].State == EDoorState::Open);
	}
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		SnapCoinPlace[i] = Coins[i].Place;
	}
	LastArmAt = Now;
}

// ---------------------------------------------------------------------------
// The gates
// ---------------------------------------------------------------------------

void ACheckpointRestoreFunctionalTest::ObserveDoors(double Now)
{
	for (int32 i = 0; i < Doors.Num() && !bGraded; ++i)
	{
		FDoorRec& D = Doors[i];
		const bool bWindow = InWindow(D.Actor.IsValid() ? D.Actor->PlateTrigger : nullptr);
		if (bWindow)
		{
			D.PlateContactAt = Now;
			if (!D.bPlateWindow && D.State == EDoorState::Shut)
			{
				D.bOwesOpen = true;
				D.OwesOpenBy = Now + kReuseWithinS;
			}
		}
		D.bPlateWindow = bWindow;

		const EDoorState S = ReadDoor(D);
		if (S == EDoorState::Neither)
		{
			const FVector At = (D.Actor.IsValid() && D.Actor->Leaf != nullptr)
				? D.Actor->Leaf->GetComponentLocation() : FVector::ZeroVector;
			Fail(FString::Printf(TEXT("TheDoorsComeBackToHowTheyWereWhenYouArmed: door "
				"%s has its leaf at %s, which is neither where it sits shut (%s) nor "
				"where it sits open (%s). A door is in one of two places"),
				*D.Id.ToString(), *At.ToCompactString(),
				*D.ShutAt.ToCompactString(), *D.OpenAt.ToCompactString()));
			return;
		}
		if (S == D.State)
		{
			continue;
		}
		if (bInDeathWindow)
		{
			const bool bWantOpen = SnapDoorOpen[i];
			if ((S == EDoorState::Open) != bWantOpen)
			{
				Fail(FString::Printf(TEXT("TheDoorsComeBackToHowTheyWereWhenYouArmed: at "
					"death %d door %s was put %s, and it was %s when the mark was set. "
					"A life ends and the yard goes back to the moment the mark was set, "
					"not to the moment the yard opened"),
					DeathsRegistered, *D.Id.ToString(),
					S == EDoorState::Open ? TEXT("open") : TEXT("shut"),
					bWantOpen ? TEXT("open") : TEXT("shut")));
				return;
			}
		}
		else if (S == EDoorState::Open && D.State == EDoorState::Shut)
		{
			if (Now - D.PlateContactAt > kChangeWindowS)
			{
				Fail(FString::Printf(TEXT("TheDoorsComeBackToHowTheyWereWhenYouArmed: "
					"door %s opened with nobody on its plate and nobody dead. A door "
					"opens from its own plate"), *D.Id.ToString()));
				return;
			}
		}
		else
		{
			Fail(FString::Printf(TEXT("TheDoorsComeBackToHowTheyWereWhenYouArmed: door "
				"%s went %s with nobody dead. Nothing shuts a door in this yard except "
				"a life ending"),
				*D.Id.ToString(),
				S == EDoorState::Shut ? TEXT("shut") : TEXT("open")));
			return;
		}
		D.State = S;
		if (S == EDoorState::Open)
		{
			D.bOwesOpen = false;
		}
	}
}

void ACheckpointRestoreFunctionalTest::ObserveCoins(double Now)
{
	for (int32 i = 0; i < Coins.Num() && !bGraded; ++i)
	{
		FCoinRec& C = Coins[i];
		const bool bWindow = InWindow(C.Actor.IsValid() ? C.Actor->Trigger : nullptr);
		if (bWindow)
		{
			C.ContactAt = Now;
			if (!C.bStandWindow && C.Place == ECoinPlace::OnStand)
			{
				C.bOwesTake = true;
				C.OwesTakeBy = Now + kReuseWithinS;
			}
		}
		C.bStandWindow = bWindow;

		const bool bVis = ReadCoinVisible(C);
		if (bVis == C.bVisible)
		{
			continue;
		}
		if (!bVis)
		{
			if (Now - C.ContactAt > kChangeWindowS)
			{
				Fail(FString::Printf(TEXT("TheCoinsComeBackToWhereTheyWereWhenYouArmed: "
					"coin %s left its stand with nobody standing at it. A coin is picked "
					"up by walking over its stand"), *C.Id.ToString()));
				return;
			}
			C.Place = ECoinPlace::InHand;
			C.bOwesTake = false;
			LedgerChangedAt = Now;
		}
		else
		{
			if (C.Place == ECoinPlace::OverTheLine)
			{
				Fail(FString::Printf(TEXT("WhatWentOverTheLineStaysOverTheLine: coin %s "
					"went over the line and is back on its stand. What has been banked "
					"is gone for good, even if it was standing there when the mark was "
					"set"), *C.Id.ToString()));
				return;
			}
			if (!bInDeathWindow)
			{
				Fail(FString::Printf(TEXT("TheCoinsComeBackToWhereTheyWereWhenYouArmed: "
					"coin %s came back to its stand with nobody dead. A coin goes back "
					"when a life ends, not before"), *C.Id.ToString()));
				return;
			}
			if (SnapCoinPlace[i] != ECoinPlace::OnStand)
			{
				Fail(FString::Printf(TEXT("TheCoinsComeBackToWhereTheyWereWhenYouArmed: "
					"at death %d coin %s was put back on its stand, and it was %s when "
					"the mark was set. What was already in somebody's hands then is "
					"still in their hands"),
					DeathsRegistered, *C.Id.ToString(),
					PlaceName(static_cast<int32>(SnapCoinPlace[i]))));
				return;
			}
			C.Place = ECoinPlace::OnStand;
			LedgerChangedAt = Now;
		}
		C.bVisible = bVis;
	}
}

void ACheckpointRestoreFunctionalTest::ObserveBanked(double Now)
{
	// A face that stops reading as a number reads as -1 and falls through the gate
	// below as a DROP, on purpose: routing it to a precondition would hand any
	// submission a non-graded exit for the price of blanking the counter.
	const int32 Face = ReadBankedFace();
	if (Face == BankedSeen)
	{
		return;
	}
	if (Face < BankedSeen)
	{
		Fail(FString::Printf(TEXT("WhatWentOverTheLineStaysOverTheLine: BANKED went from "
			"%d down to %d. It never goes down -- not at a death, not when a mark is "
			"set, not ever"), BankedSeen, Face));
		return;
	}
	if (bInDeathWindow)
	{
		Fail(FString::Printf(TEXT("WhatWentOverTheLineStaysOverTheLine: BANKED went from "
			"%d to %d at death %d. It moves only when the line is crossed"),
			BankedSeen, Face, DeathsRegistered));
		return;
	}
	if (Now - CounterContactAt > kChangeWindowS)
	{
		Fail(FString::Printf(TEXT("WhatWentOverTheLineStaysOverTheLine: BANKED went from "
			"%d to %d with nobody at the line. Standing on a pad banks nothing"),
			BankedSeen, Face));
		return;
	}
	const int32 Hand = CountInHand();
	if (Face - BankedSeen != Hand)
	{
		Fail(FString::Printf(TEXT("WhatWentOverTheLineStaysOverTheLine: BANKED went up by "
			"%d at the line and %d coin(s) were in hand (%s). Crossing the line moves "
			"exactly what is being carried"),
			Face - BankedSeen, Hand, *HandList()));
		return;
	}
	for (FCoinRec& C : Coins)
	{
		if (C.Place == ECoinPlace::InHand)
		{
			C.Place = ECoinPlace::OverTheLine;
		}
	}
	BankedSeen = Face;
	LedgerChangedAt = Now;
}

void ACheckpointRestoreFunctionalTest::ObserveOwed(double Now)
{
	for (FDoorRec& D : Doors)
	{
		if (D.bOwesOpen && Now > D.OwesOpenBy)
		{
			Fail(FString::Printf(TEXT("TheYardStillWorksAfterYouComeBack: the character "
				"stood on door %s's plate and %.1f s later the door has not opened. A "
				"door that was put back has to work again from its own plate"),
				*D.Id.ToString(), kReuseWithinS));
			return;
		}
	}
	for (FCoinRec& C : Coins)
	{
		if (!C.bOwesTake)
		{
			continue;
		}
		if (Now > C.OwesTakeBy)
		{
			Fail(FString::Printf(TEXT("TheYardStillWorksAfterYouComeBack: the character "
				"walked over coin %s's stand and %.1f s later the coin is still sitting "
				"there. A coin that was put back has to be pickable again"),
				*C.Id.ToString(), kReuseWithinS));
			return;
		}
	}
	// "and picking it up must move CARRIED" is NOT a separate check here: the counter
	// is compared against the fixture's own ledger every settled frame by
	// TheCounterAgreesWithYourHands, and a pickup that leaves CARRIED where it was
	// fails there with both numbers printed. One gate, one place.
}

void ACheckpointRestoreFunctionalTest::ObserveSettled(double Now)
{
	const bool bSettled = !bInDeathWindow
		&& (Now - LastArmAt > kSettleS)
		&& (Now - DeathWindowEndedAt > kSettleS);
	if (!bSettled)
	{
		return;
	}

	int32 Lit = INDEX_NONE;
	int32 LitCount = 0;
	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		if (ReadPadLit(Pads[i]))
		{
			++LitCount;
			if (Lit == INDEX_NONE) { Lit = i; }
		}
	}
	if (LitCount > 1)
	{
		Fail(FString::Printf(TEXT("TheLitPadIsTheMark: %d pads are lit at once. At most "
			"one pad is ever the mark, and the lit pad is how a player knows which"),
			LitCount));
		return;
	}
	if (MarkPad != INDEX_NONE)
	{
		if (LitCount == 0)
		{
			Fail(FString::Printf(TEXT("TheLitPadIsTheMark: no pad is lit, and the pad "
				"stood on most recently was the one with StandOrder %d. A pad is lit for "
				"as long as it is the mark"), Pads[MarkPad].Order));
			return;
		}
		if (Lit != MarkPad)
		{
			Fail(FString::Printf(TEXT("TheLitPadIsTheMark: the pad with StandOrder %d is "
				"lit and the pad stood on most recently is the one with StandOrder %d. "
				"The mark is simply the pad stood on most recently"),
				Pads[Lit].Order, Pads[MarkPad].Order));
			return;
		}
	}

	if (Now - LedgerChangedAt > kSettleS)
	{
		const int32 Face = ReadCarriedFace();
		const int32 Hand = CountInHand();
		if (Face != Hand)
		{
			Fail(FString::Printf(TEXT("TheCounterAgreesWithYourHands: CARRIED reads %d "
				"and %d coin(s) are in hand (%s). CARRIED always says how many coins are "
				"in hand"), Face, Hand, *HandList()));
			return;
		}
	}
}

void ACheckpointRestoreFunctionalTest::JudgeDeath(double Now)
{
	bJudgedThisDeath = true;
	++DeathsJudged;

	// ---- G1, FIRST, because it is the one an empty answer fails ----------
	{
		const FVector Where = HeroAt();
		double Best = TNumericLimits<double>::Max();
		FString MarkLabel;
		double Tol = kMarkTolUu;
		if (MarkAtDeath != INDEX_NONE && Pads.IsValidIndex(MarkAtDeath)
			&& Pads[MarkAtDeath].Actor.IsValid())
		{
			Best = FVector::Dist2D(Where,
				Pads[MarkAtDeath].Actor->GetRespawnTransform().GetLocation());
			MarkLabel = FString::Printf(TEXT("the pad with StandOrder %d, the one stood "
				"on most recently"), Pads[MarkAtDeath].Order);
		}
		else
		{
			Tol = kEntranceTolUu;
			for (const FVector& E : Entrances)
			{
				Best = FMath::Min(Best, FVector::Dist2D(Where, E));
			}
			MarkLabel = TEXT("the spot the character walked in from, no pad having been "
				"stood on yet");
		}
		bool bInHazard = false;
		for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
		{
			if (H.IsValid() && InVolume(H->Trigger, Where, /*bGrow=*/true))
			{
				bInHazard = true;
			}
		}
		if (Best > Tol || bInHazard)
		{
			Fail(FString::Printf(TEXT("YouComeBackAtTheLastPadYouStoodOn: at death %d the "
				"mark was %s, and %.1f s later the character is %.0f uu away from it at "
				"%s%s. A life that ends on hot floor puts them back on the mark"),
				DeathsJudged, *MarkLabel, kJudgeAtS, Best,
				*Where.ToCompactString(),
				bInHazard ? TEXT(", still standing on hot floor") : TEXT("")));
			return;
		}
	}

	// ---- the yard, against the snapshot taken when the mark was set -------
	for (int32 i = 0; i < Doors.Num(); ++i)
	{
		const bool bOpen = (Doors[i].State == EDoorState::Open);
		if (bOpen != SnapDoorOpen[i])
		{
			Fail(FString::Printf(TEXT("TheDoorsComeBackToHowTheyWereWhenYouArmed: at "
				"death %d door %s is %s and it was %s when the mark was set"),
				DeathsJudged, *Doors[i].Id.ToString(),
				bOpen ? TEXT("open") : TEXT("shut"),
				SnapDoorOpen[i] ? TEXT("open") : TEXT("shut")));
			return;
		}
	}
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		const ECoinPlace Want = (Coins[i].Place == ECoinPlace::OverTheLine)
			? ECoinPlace::OverTheLine : SnapCoinPlace[i];
		if (Coins[i].Place != Want)
		{
			Fail(FString::Printf(TEXT("TheCoinsComeBackToWhereTheyWereWhenYouArmed: at "
				"death %d coin %s is %s and it should be %s"),
				DeathsJudged, *Coins[i].Id.ToString(),
				PlaceName(static_cast<int32>(Coins[i].Place)),
				PlaceName(static_cast<int32>(Want))));
			return;
		}
	}
	{
		const int32 Face = ReadBankedFace();
		if (Face != BankedBeforeDeath)
		{
			Fail(FString::Printf(TEXT("WhatWentOverTheLineStaysOverTheLine: BANKED read "
				"%d before death %d and reads %d after it. It never changes at a death"),
				BankedBeforeDeath, DeathsJudged, Face));
			return;
		}
	}
	{
		const int32 Face = ReadCarriedFace();
		const int32 Hand = CountInHand();
		if (Face != Hand)
		{
			Fail(FString::Printf(TEXT("TheCounterAgreesWithYourHands: after death %d "
				"CARRIED reads %d and %d coin(s) are in hand (%s). Rolling CARRIED back "
				"to what it read when the mark was set is not the same thing -- coins "
				"that have gone over the line since are not in anybody's hands"),
				DeathsJudged, Face, Hand, *HandList()));
			return;
		}
	}
}

void ACheckpointRestoreFunctionalTest::FinalGrade(double Now)
{
	if (bGraded)
	{
		return;
	}
	if (StepIndex < Script.Num())
	{
		Fail(FString::Printf(TEXT("TheYardRanAllThreeDeaths: the walk stalled at stop %d "
			"of %d with the character at %s; %d of 3 deaths were judged. A run that "
			"cannot be walked to the end has not been measured"),
			StepIndex + 1, Script.Num(), *HeroAt().ToCompactString(), DeathsJudged));
		return;
	}
	if (DeathsJudged < 3)
	{
		Fail(FString::Printf(TEXT("TheYardRanAllThreeDeaths: only %d of 3 deaths were "
			"judged, so most of what the yard promises was never tested"), DeathsJudged));
		return;
	}
	for (int32 i = 0; i < MovedAfterDeath.Num(); ++i)
	{
		if (!MovedAfterDeath[i])
		{
			Fail(FString::Printf(TEXT("TheYardRanAllThreeDeaths: after death %d the "
				"character never moved %.0f uu under their own steam inside %.0f s. "
				"Coming back from a death has to leave them able to walk on"),
				i + 1, kMobilityUu, kMobilityWindowS));
			return;
		}
	}
	bGraded = true;
	FinishTest(EFunctionalTestResult::Succeeded, TEXT("the yard came back three times"));
}

// ---------------------------------------------------------------------------
// The drive
// ---------------------------------------------------------------------------

void ACheckpointRestoreFunctionalTest::BuildTransits()
{
	Transits.Reset();
	TransitIndex = 0;
	DwellUntil = -1.0;
	if (!Hero.IsValid() || !Script.IsValidIndex(StepIndex))
	{
		return;
	}
	const FVector Here = HeroAt();
	const FVector Target = StopLocation(Script[StepIndex]);
	// Out to the lane, along the lane, in to the stop. Either of the first two may be
	// where the character already is, in which case it is consumed on the first frame.
	Transits.Add(FVector(Here.X, CorridorY, Here.Z));
	Transits.Add(FVector(Target.X, CorridorY, Here.Z));
}

void ACheckpointRestoreFunctionalTest::AdvanceStep(double Now)
{
	++StepIndex;
	if (StepIndex >= Script.Num())
	{
		FinalGrade(Now);
		return;
	}
	BuildTransits();
}

void ACheckpointRestoreFunctionalTest::DriveHero(double Now)
{
	if (bHoldingInput || !Hero.IsValid() || !Script.IsValidIndex(StepIndex))
	{
		return;
	}
	const FVector Here = HeroAt();
	const FVector Aim = Transits.IsValidIndex(TransitIndex)
		? Transits[TransitIndex] : StopLocation(Script[StepIndex]);
	const FVector Flat(Aim.X - Here.X, Aim.Y - Here.Y, 0.0);
	if (Flat.Size2D() > kWaypointUu)
	{
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		return;
	}
	if (Transits.IsValidIndex(TransitIndex))
	{
		++TransitIndex;
		return;
	}
	// STAND HERE. Every gate is about a state that has settled, and a route that only
	// passes through a spot never gives the yard a chance to be judged.
	if (DwellUntil < 0.0)
	{
		DwellUntil = Now + kDwellS;
	}
	else if (Now >= DwellUntil)
	{
		AdvanceStep(Now);
	}
}

// ---------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------

void ACheckpointRestoreFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || bGraded || !bStaged || !Hero.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	const FVector Here = HeroAt();

	for (const FPadRec& P : Pads)
	{
		if (!P.Actor.IsValid())
		{
			Precondition(TEXT("a checkpoint pad stopped existing mid-run"));
			return;
		}
	}

	if (Counter.IsValid() && InWindow(Counter->Trigger))
	{
		CounterContactAt = Now;
	}

	// ---- DEATHS ARE REGISTERED FIRST, and that ORDER is load-bearing ------
	// A correct submission is told a life ended and puts the yard back inside the very
	// same frame. If the transitions below were observed before the window opened, that
	// submission's restore would be read as doors shutting and coins reappearing with
	// nobody dead -- and every correct answer would fail. Whether this actor ticks
	// before or after the character in a frame is not something a fixture may assume,
	// so the window is opened as early as this tick can possibly open it.
	if (!bInDeathWindow)
	{
		bool bStandingInHotFloor = false;
		for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
		{
			if (H.IsValid() && Touching(H->Trigger))
			{
				bStandingInHotFloor = true;
			}
		}
		// The hazard's own announcement is the primary detector. The sampled overlap is
		// a backstop for a run where no announcement ever arrives; it cannot double
		// count, because it only looks while no window is open and only a second after
		// the last one closed.
		if (bDeathSignalled || (bStandingInHotFloor && Now - DeathWindowEndedAt > 1.0))
		{
			RegisterDeath(Now);
		}
	}

	// ---- the mark, from the pads' OWN overlap sets ------------------------
	// Suppressed while a death is being judged. A respawn lands the character inside
	// the mark pad's own volume and re-announces the stand, and BOTH readings of that
	// -- honour it, or ignore it -- have to pass: the mark is the same pad either way,
	// and the script guarantees a fresh mark before the next death, so no snapshot
	// taken at a respawn instant is ever the one that gets graded.
	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		FPadRec& P = Pads[i];
		const bool bNow = Touching(P.Actor->Trigger);
		if (bNow && !P.bTouching && !bInDeathWindow)
		{
			MarkPad = i;
			TakeSnapshot(Now);
		}
		P.bTouching = bNow;
	}

	// ---- transitions, every frame, windows and all ------------------------
	ObserveDoors(Now);   if (bGraded) { return; }
	ObserveCoins(Now);   if (bGraded) { return; }
	ObserveBanked(Now);  if (bGraded) { return; }
	ObserveOwed(Now);    if (bGraded) { return; }

	// ---- judging, once the transitions for this frame are in --------------
	if (bInDeathWindow)
	{
		if (!bJudgedThisDeath && Now - DeathAt >= kJudgeAtS)
		{
			JudgeDeath(Now);
			if (bGraded) { return; }
		}
		if (bJudgedThisDeath)
		{
			for (const TWeakObjectPtr<AHazardStripActor>& H : Hazards)
			{
				if (H.IsValid() && InVolume(H->Trigger, Here, /*bGrow=*/true))
				{
					Fail(FString::Printf(TEXT("YouComeBackAtTheLastPadYouStoodOn: after "
						"death %d the character is back on hot floor within %.0f s of "
						"being put back, at %s. Coming back has to be coming back "
						"somewhere safe"),
						DeathsJudged, kHazardClearS, *Here.ToCompactString()));
					return;
				}
			}
		}
		if (Now - DeathAt >= kDeathHoldS)
		{
			ReleaseAfterDeath(Now);
			if (bGraded) { return; }
		}
	}

	ObserveSettled(Now); if (bGraded) { return; }

	// ---- can they still walk ----------------------------------------------
	if (MobilityStartedAt >= 0.0 && DeathsJudged >= 1
		&& MovedAfterDeath.IsValidIndex(DeathsJudged - 1)
		&& !MovedAfterDeath[DeathsJudged - 1])
	{
		MobilitySoFar += FVector::Dist2D(Here, MobilityLastAt);
		MobilityLastAt = Here;
		if (MobilitySoFar >= kMobilityUu)
		{
			MovedAfterDeath[DeathsJudged - 1] = true;
		}
		else if (Now - MobilityStartedAt > kMobilityWindowS)
		{
			Fail(FString::Printf(TEXT("TheYardRanAllThreeDeaths: after death %d the "
				"character moved %.0f uu under their own steam in %.0f s, and %.0f uu "
				"was wanted. Coming back from a death has to leave them able to walk on"),
				DeathsJudged, MobilitySoFar, kMobilityWindowS, kMobilityUu));
			return;
		}
	}

	DriveHero(Now);
}

void ACheckpointRestoreFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString Doorline;
	for (const FDoorRec& D : Doors)
	{
		Doorline += FString::Printf(TEXT("%s=%s "), *D.Id.ToString(),
			D.State == EDoorState::Open ? TEXT("open") : TEXT("shut"));
	}
	FString Coinline;
	for (const FCoinRec& C : Coins)
	{
		Coinline += FString::Printf(TEXT("%s=%d "), *C.Id.ToString(),
			static_cast<int32>(C.Place));
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-yard calib] cp%d t=%.2f stop=%d/%d mark=%d deaths=%d/%d at=(%.0f,%.0f) "
			 "carried=%d banked=%d | %s| %s"),
		Index, Now, StepIndex + 1, Script.Num(),
		MarkPad == INDEX_NONE ? -1 : Pads[MarkPad].Order,
		DeathsJudged, DeathsRegistered, HeroAt().X, HeroAt().Y,
		ReadCarriedFace(), ReadBankedFace(), *Doorline, *Coinline);
}

void ACheckpointRestoreFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!bStaged)
	{
		return;
	}
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex >= kSentinelIndex)
	{
		FinalGrade(TimeSeconds);
	}
}
