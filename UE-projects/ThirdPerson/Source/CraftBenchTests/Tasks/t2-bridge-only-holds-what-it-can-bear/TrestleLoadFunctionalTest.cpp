// Copyright CraftBench. All Rights Reserved.

#include "TrestleLoadFunctionalTest.h"

#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "Misc/DateTime.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED IN THE PROMPT -------------------------------------------------
	/** "a tenth of the rating". The fixture allows a shade more, never less. */
	constexpr double kSagTolerance = 0.12;
	/** "within two seconds". The fixture waits two and a half before it asserts. */
	constexpr double kSettleS = 2.5;

	// ---- THE FIXTURE'S OWN CLOCKING AND STAGING (not thresholds a solver needs) ---
	/** How wide the "plainly on the deck" footprint is inset, and how far past the
	 *  deck's edge "plainly off it" starts. Between the two the fixture asserts
	 *  NOTHING: a correct submission may draw that line a few centimetres either side
	 *  of where this one draws it, and no stand is ever taken there. Every staged
	 *  position sits at least 90 cm inside the inner box. */
	constexpr double kInnerInsetCm = 60.0;
	constexpr double kOuterOutsetCm = 150.0;
	/** The height band that counts as "feet on the deck". The top of the band is wide
	 *  because a deck dropping out from under something outruns free fall: 200 cm of
	 *  deck travel takes ~0.30 s and gravity covers only ~45 cm in that time, so the
	 *  gap opens to ~155 cm before it closes again. */
	constexpr double kInnerBelowCm = 20.0;
	constexpr double kInnerAboveCm = 250.0;
	constexpr double kOuterBelowCm = 120.0;
	constexpr double kOuterAboveCm = 400.0;

	/** A span must read EMPTY for this long before the fixture expects it back up.
	 *  Purely a delay on when the fixture starts demanding a recovery, so it can only
	 *  ever be generous to a submission. */
	constexpr double kEmptyDebounceS = 1.0;

	/** Bands the drive is staged to clear, so no correct answer can round the wrong
	 *  way at a sampled stand. A stand that must HOLD is at most 0.85 of the rating;
	 *  one that must GIVE WAY is at least 1.15 of it. */
	constexpr double kHoldBand = 0.85;
	constexpr double kOverBand = 1.15;

	/** Down is at least this much of the full give-way drop; up is at most a full sag
	 *  plus a whisker. */
	constexpr double kDownFraction = 0.9;
	constexpr double kUpSlackCm = 2.0;

	constexpr double kWaypointCm = 90.0;
	constexpr double kCratePinCm = 60.0;
	constexpr double kSpanPinCm = 2.0;
	constexpr double kNumberPinKg = 0.5;

	/** Far past the ~240 s drive. The base class ends the test the moment the last
	 *  scheduled checkpoint is sampled, so the completion gate lives on this one. */
	constexpr double kSentinelTime = 520.0;
	constexpr double kCalibrationEveryS = 10.0;

	double Round10(double V)
	{
		return FMath::RoundToDouble(V / 10.0) * 10.0;
	}

	bool ReadStampedFloat(const AActor* A, const TCHAR* Name, double& Out)
	{
		if (A == nullptr)
		{
			return false;
		}
		const FFloatProperty* const P =
			FindFProperty<FFloatProperty>(A->GetClass(), Name);
		if (P == nullptr)
		{
			return false;
		}
		Out = double(P->GetPropertyValue_InContainer(A));
		return true;
	}

	bool WriteStampedFloat(AActor* A, const TCHAR* Name, double Value)
	{
		if (A == nullptr)
		{
			return false;
		}
		const FFloatProperty* const P =
			FindFProperty<FFloatProperty>(A->GetClass(), Name);
		if (P == nullptr)
		{
			return false;
		}
		P->SetPropertyValue_InContainer(A, float(Value));
		return true;
	}

	/** The deck of a span: the component called Deck if there is one, else the biggest
	 *  static mesh on the actor, ties broken by name so it never depends on component
	 *  enumeration order. */
	UPrimitiveComponent* ResolveDeck(AActor* Span)
	{
		if (Span == nullptr)
		{
			return nullptr;
		}
		TArray<UStaticMeshComponent*> Meshes;
		Span->GetComponents<UStaticMeshComponent>(Meshes);
		if (Meshes.Num() == 0)
		{
			return nullptr;
		}
		for (UStaticMeshComponent* M : Meshes)
		{
			if (M != nullptr && M->GetName() == TEXT("Deck"))
			{
				return M;
			}
		}
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
}

ATrestleLoadFunctionalTest::ATrestleLoadFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	// PRE-BeginPlay. Registered from the constructor and filtered on the world, exactly
	// as the t0/t1 log-window fixtures do, because this is the ONLY hook that fires
	// after PostInitializeComponents and before any placed actor's BeginPlay. Stamping
	// the ratings and weights here is what makes them un-cacheable: a submission that
	// reads a number in BeginPlay reads it AFTER the yard has already written this
	// round's value, so there is no window in which an old number is the right one.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ATrestleLoadFunctionalTest::OnWorldActorsInitialized);
}

void ATrestleLoadFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
	Super::EndPlay(EndPlayReason);
}

// ------------------------------------------------------------------------------------
// Staging
// ------------------------------------------------------------------------------------

void ATrestleLoadFunctionalTest::OnWorldActorsInitialized(
	const FActorsInitializedParams& Params)
{
	if (bStaged || bStampFailed || Params.World != GetWorld())
	{
		return;
	}
	ResolveAndStampTheYard(Params.World);
}

bool ATrestleLoadFunctionalTest::DrawTheNumbers(FString& OutWhy)
{
	const int64 Ticks = FDateTime::Now().GetTicks();
	DrawSeed = int32(Ticks ^ (Ticks >> 32));
	const FRandomStream Rng(DrawSeed);

	// EVERY NUMBER IN THE YARD IS DRAWN, and every one of them is derived from the
	// west span's rating so the demonstration holds for any draw. The fractions are
	// what the whole drive is built on:
	//   anvil 0.80 and character 0.40 -- each on its own is comfortably UNDER the
	//     rating (<= 0.85) and together they are comfortably OVER it (1.20 >= 1.15).
	//     That is the seed condition: something here is too much only TOGETHER.
	//   sack 0.24 + keg 0.38 = 0.62 -- two crates a count-based answer collapses under
	//     and a heaviest-item answer sags 0.38 for instead of 0.62.
	//   the packed character 1.35 of the EAST rating -- over on its own, and the only
	//     stand where nothing but the character is on the span.
	const double Rw = 20.0 * double(Rng.RandRange(28, 33));
	const double Frac = 0.56 + 0.02 * double(Rng.RandRange(0, 3));
	const double Re = Round10(Frac * Rw);

	Spans[0].RatedKg = Rw;
	Spans[1].RatedKg = Re;
	Loads[0].WeightKg = Round10(0.24 * Rw);   // the sack
	Loads[1].WeightKg = Round10(0.38 * Rw);   // the keg
	Loads[2].WeightKg = Round10(0.80 * Rw);   // the anvil
	CharacterMassKg = Round10(0.40 * Rw);
	PackedMassKg = Round10(1.35 * Re);

	const double Sack = Loads[0].WeightKg;
	const double Keg = Loads[1].WeightKg;
	const double Anvil = Loads[2].WeightKg;
	const double Base = CharacterMassKg;
	const double Packed = PackedMassKg;

	struct FClaim { const TCHAR* What; bool bHolds; };
	const FClaim Claims[] =
	{
		{ TEXT("the character alone is well under the west rating"),
		  Base <= kHoldBand * Rw },
		{ TEXT("the anvil alone is well under the west rating"),
		  Anvil <= kHoldBand * Rw },
		{ TEXT("the anvil and the character together are well over the west rating"),
		  Base + Anvil >= kOverBand * Rw },
		{ TEXT("the sack and the keg together are well under the west rating"),
		  Sack + Keg <= kHoldBand * Rw },
		{ TEXT("the character alone is well under the east rating"),
		  Base <= kHoldBand * Re },
		{ TEXT("the packed character alone is well over the east rating"),
		  Packed >= kOverBand * Re },
		{ TEXT("the sack, the keg and the packed character are well over the west rating"),
		  Sack + Keg + Packed >= kOverBand * Rw },
		{ TEXT("the two ratings are at least a quarter apart"),
		  Rw - Re >= 0.25 * Rw },
		{ TEXT("no two crates weigh the same"),
		  Sack != Keg && Keg != Anvil && Sack != Anvil },
		{ TEXT("the heaviest crate on its own is far from the pair's sag fraction"),
		  FMath::Abs((Sack + Keg) / Rw - Keg / Rw) > kSagTolerance + 0.05 },
		{ TEXT("the east sag fraction is far from what the west rating would give"),
		  FMath::Abs(Base / Re - Base / Rw) > kSagTolerance + 0.05 },
		{ TEXT("every sagged pose is inside the sag range"),
		  Anvil <= Rw && Base <= Re },
	};
	for (const FClaim& C : Claims)
	{
		if (!C.bHolds)
		{
			OutWhy = FString::Printf(
				TEXT("seed %d drew west=%.0f east=%.0f sack=%.0f keg=%.0f anvil=%.0f "
					 "character=%.0f packed=%.0f, and then %s is false"),
				DrawSeed, Rw, Re, Sack, Keg, Anvil, Base, Packed, C.What);
			return false;
		}
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t2-trestle stage] seed=%d west=%.0f east=%.0f sack=%.0f keg=%.0f "
			 "anvil=%.0f character=%.0f packed=%.0f"),
		DrawSeed, Rw, Re, Sack, Keg, Anvil, Base, Packed);
	return true;
}

bool ATrestleLoadFunctionalTest::ResolveAndStampTheYard(UWorld* World)
{
	if (World == nullptr)
	{
		return false;
	}

	TArray<AActor*> FoundSpans, FoundLoads;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LoadSpan")), FoundSpans);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardLoad")), FoundLoads);

	if (FoundSpans.Num() != 2 || FoundLoads.Num() != 3)
	{
		bStampFailed = true;
		StampFailure = FString::Printf(
			TEXT("the yard staged two spans and three crates; %d span(s) and %d "
				 "crate(s) answer to their tags"),
			FoundSpans.Num(), FoundLoads.Num());
		return false;
	}

	// Stable identities from where the yard put things: the span with the smaller Y is
	// WEST, and the crates are the bank slots in order.
	FoundSpans.Sort([](const AActor& A, const AActor& B)
	{
		return A.GetActorLocation().Y < B.GetActorLocation().Y;
	});
	FoundLoads.Sort([](const AActor& A, const AActor& B)
	{
		const FVector LA = A.GetActorLocation();
		const FVector LB = B.GetActorLocation();
		if (!FMath::IsNearlyEqual(LA.Y, LB.Y, 1.0))
		{
			return LA.Y < LB.Y;
		}
		return LA.X < LB.X;
	});

	const TCHAR* const SpanNames[2] = { TEXT("WEST"), TEXT("EAST") };
	for (int32 i = 0; i < 2; ++i)
	{
		FSpan S;
		S.Actor = FoundSpans[i];
		S.Name = SpanNames[i];
		S.Deck = ResolveDeck(FoundSpans[i]);
		S.StagedAt = FoundSpans[i]->GetActorLocation();
		if (!S.Deck.IsValid())
		{
			bStampFailed = true;
			StampFailure = FString::Printf(
				TEXT("the %s span has no deck to stand on"), S.Name);
			return false;
		}
		Spans.Add(S);
	}

	const TCHAR* const LoadNames[3] = { TEXT("the sack"), TEXT("the keg"),
										TEXT("the anvil") };
	for (int32 i = 0; i < 3; ++i)
	{
		FLoad L;
		L.Actor = FoundLoads[i];
		L.Name = LoadNames[i];
		L.Home = FoundLoads[i]->GetActorLocation();
		L.StagedAt = L.Home;
		const UPrimitiveComponent* const Root =
			Cast<UPrimitiveComponent>(FoundLoads[i]->GetRootComponent());
		L.HalfHeightCm = Root != nullptr ? Root->Bounds.BoxExtent.Z : 60.0;
		Loads.Add(L);
	}

	FString Why;
	if (!DrawTheNumbers(Why))
	{
		// THE FIXTURE'S OWN ARITHMETIC, about numbers the fixture itself drew. No
		// submission can reach this, which is why it is allowed to be an ::Error.
		StampFailure = Why;
		bStampFailed = true;
		return false;
	}

	// Sag distances are stamped too, not read. They are the scale every up/down and
	// sag verdict is measured in, and a submission that shrank the give-way drop to
	// 50 cm would otherwise satisfy every gate with a collapse that is not a collapse.
	for (FSpan& S : Spans)
	{
		S.FullSagCm = 30.0;
		S.DropCm = 200.0;
		AActor* const A = S.Actor.Get();
		const bool bOk =
			WriteStampedFloat(A, TEXT("RatedLoadKg"), S.RatedKg)
			&& WriteStampedFloat(A, TEXT("FullSagCm"), S.FullSagCm)
			&& WriteStampedFloat(A, TEXT("GiveWayDropCm"), S.DropCm);
		if (!bOk)
		{
			bStampFailed = true;
			StampFailure = FString::Printf(
				TEXT("the %s span does not carry a readable rating, sag and drop for "
					 "the yard to stamp"), S.Name);
			return false;
		}
	}
	for (FLoad& L : Loads)
	{
		if (!WriteStampedFloat(L.Actor.Get(), TEXT("WeightKg"), L.WeightKg))
		{
			bStampFailed = true;
			StampFailure = FString::Printf(
				TEXT("%s does not carry a readable weight for the yard to stamp"),
				L.Name);
			return false;
		}
	}

	DeckHalfExtent = Spans[0].Deck->Bounds.BoxExtent;
	bStaged = true;
	return true;
}

void ATrestleLoadFunctionalTest::BuildRoute()
{
	Steps.Reset();
	if (Spans.Num() != 2)
	{
		return;
	}
	const double HalfX = DeckHalfExtent.X;
	const double HalfY = DeckHalfExtent.Y;
	const double MidX = Spans[0].StagedAt.X;
	const double MidY = (Spans[0].StagedAt.Y + Spans[1].StagedAt.Y) * 0.5;

	// Every waypoint is derived from where the decks actually are, so re-staging the
	// yard moves the walk with it.
	const double RampFootX = MidX + HalfX + 800.0;   // stood on the floor, off the ramp
	const double LeftFootX = MidX - HalfX - 800.0;
	const double CorridorX = MidX + HalfX + 1350.0;  // east of both ramps
	const double YardX = MidX - HalfX - 1550.0;
	// The character walks one side of each deck's middle and the crates go on the
	// other, so nothing on a span is ever in the character's way.
	const double WalkY[2] = { Spans[0].StagedAt.Y + 200.0, Spans[1].StagedAt.Y + 200.0 };
	// A collapsed deck cannot be left by its ramps -- their tops are two metres above
	// it -- so every exit from a fallen deck is SIDEWAYS, on the character's own side,
	// over a 40 cm lip.
	const double ExitY[2] = { Spans[0].StagedAt.Y + HalfY + 550.0,
							  Spans[1].StagedAt.Y + HalfY + 550.0 };

	auto Add = [this](double X, double Y, double Dwell, EYardAction Action,
					  const TCHAR* Stand, int32 CharOn, bool bCharWeight)
	{
		FStep S;
		S.X = X;
		S.Y = Y;
		S.Dwell = Dwell;
		S.Action = Action;
		S.Stand = Stand;
		S.CharOnSpan = CharOn;
		S.bAboutTheCharactersWeight = bCharWeight;
		Steps.Add(S);
	};

	Add(YardX, MidY, 5.0, EYardAction::None,
		TEXT("both spans empty and level at the start"), INDEX_NONE, false);
	Add(LeftFootX, WalkY[0], 3.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(MidX, WalkY[0], 7.0, EYardAction::None,
		TEXT("WEST holds the character"), 0, false);
	Add(RampFootX, WalkY[0], 4.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(RampFootX, WalkY[0], 7.0, EYardAction::StageAnvil,
		TEXT("WEST holds the anvil on its own"), INDEX_NONE, false);
	Add(MidX, WalkY[0], 9.0, EYardAction::None,
		TEXT("WEST gives way under the anvil and the character together"), 0, false);
	Add(MidX, ExitY[0], 9.0, EYardAction::None,
		TEXT("WEST stays down with the anvil on the fallen deck"), INDEX_NONE, false);
	Add(MidX, ExitY[0], 9.0, EYardAction::LiftAnvil,
		TEXT("WEST heaves back up once the anvil is lifted"), INDEX_NONE, false);
	Add(CorridorX, MidY, 2.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(RampFootX, WalkY[0], 3.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(MidX, WalkY[0], 7.0, EYardAction::None,
		TEXT("WEST holds the character again after coming back up"), 0, false);
	Add(RampFootX, WalkY[0], 4.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(RampFootX, WalkY[0], 7.0, EYardAction::StageSackAndKeg,
		TEXT("WEST holds the sack and the keg together"), INDEX_NONE, false);
	Add(CorridorX, MidY, 2.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(RampFootX, WalkY[1], 3.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(MidX, WalkY[1], 7.0, EYardAction::None,
		TEXT("EAST holds the unpacked character while WEST holds two crates"),
		1, true);
	Add(RampFootX, WalkY[1], 4.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(RampFootX, WalkY[1], 6.0, EYardAction::ShoulderThePack, nullptr, INDEX_NONE,
		false);
	Add(MidX, WalkY[1], 9.0, EYardAction::None,
		TEXT("EAST gives way under the packed character on her own"), 1, true);
	Add(MidX, ExitY[1], 10.0, EYardAction::None,
		TEXT("EAST heaves back up once the character steps off"), INDEX_NONE, false);
	Add(CorridorX, ExitY[1], 2.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(CorridorX, MidY, 2.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(RampFootX, WalkY[0], 3.0, EYardAction::None, nullptr, INDEX_NONE, false);
	Add(MidX, WalkY[0], 9.0, EYardAction::None,
		TEXT("WEST gives way under the sack, the keg and the packed character"),
		0, false);
	Add(MidX, ExitY[0], 9.0, EYardAction::None,
		TEXT("WEST stays down with the sack and the keg on the fallen deck"),
		INDEX_NONE, false);
	Add(MidX, ExitY[0], 10.0, EYardAction::ClearSackAndKeg,
		TEXT("WEST heaves back up once both crates are cleared"), INDEX_NONE, false);
	Add(YardX, MidY, 7.0, EYardAction::None,
		TEXT("both spans empty and level at the end"), INDEX_NONE, false);
}

void ATrestleLoadFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}

	// Belt and braces: if the pre-BeginPlay hook never fired (a fixture spawned after
	// world init), stage now. A submission cannot profit from it -- the stamp
	// overwrites whatever anybody wrote.
	if (!bStaged && !bStampFailed)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("[t2-trestle stage] the pre-BeginPlay window was missed; staging "
				 "from PrepareTest instead"));
		ResolveAndStampTheYard(World);
	}

	if (bStampFailed)
	{
		if (Spans.Num() == 2 && Loads.Num() == 3)
		{
			// The world was there; the fixture's own draw is what failed. Nothing a
			// submission can cause, so this leaves the denominator.
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the fixture's own staging does not "
					 "support the demonstration it is about to make -- %s"),
				*StampFailure));
		}
		else
		{
			FailSetupChanged(StampFailure);
		}
		return;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetCharacterMovement() == nullptr)
	{
		FailSetupChanged(TEXT("there is no character in the yard for the walk"));
		return;
	}
	if (Hero->GetMesh() == nullptr || Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FailSetupChanged(
			TEXT("the character in the yard has no body, so nobody reviewing the "
				 "recording would see who is standing on the spans"));
		return;
	}
	// The yard says what the character weighs. Read back and pinned from here on, so
	// zeroing it is a graded change to the yard rather than a way to vanish from every
	// span's arithmetic.
	Hero->GetCharacterMovement()->Mass = float(CharacterMassKg);

	BuildRoute();

	const double Now = double(World->GetTimeSeconds());
	for (FSpan& S : Spans)
	{
		S.TruthChangedAt = Now;
		S.EmptySince = Now;
	}

	// Ordinary checkpoints every 10 s carry a calibration line per span so a FAIL can
	// be read without a re-run. The last entry is a SENTINEL far past the ~240 s drive,
	// because the base class ends the test the moment the last scheduled checkpoint is
	// sampled -- and the completion gate lives on it.
	TArray<double> Schedule;
	for (double T = kCalibrationEveryS; T < kSentinelTime; T += kCalibrationEveryS)
	{
		Schedule.Add(T);
	}
	// DERIVED, never written down: an off-by-one here would skip the only gate that
	// sees a submission nothing can stand on.
	SentinelIndex = Schedule.Num();
	Schedule.Add(kSentinelTime);
	SetCheckpointSchedule(Schedule);
}

// ------------------------------------------------------------------------------------
// The fixture's own truth
// ------------------------------------------------------------------------------------

bool ATrestleLoadFunctionalTest::GetFootprint(const AActor* A, FVector& OutMiddle,
	double& OutBaseZ)
{
	const UPrimitiveComponent* const Root =
		A != nullptr ? Cast<UPrimitiveComponent>(A->GetRootComponent()) : nullptr;
	if (Root == nullptr)
	{
		return false;
	}
	const FBoxSphereBounds B = Root->Bounds;
	OutMiddle = B.Origin;
	OutBaseZ = B.Origin.Z - B.BoxExtent.Z;
	return true;
}

int32 ATrestleLoadFunctionalTest::ClassifyOnSpan(const FSpan& Span,
	const AActor* Candidate) const
{
	const UPrimitiveComponent* const DeckComp = Span.Deck.Get();
	FVector Mid = FVector::ZeroVector;
	double BaseZ = 0.0;
	if (DeckComp == nullptr || !GetFootprint(Candidate, Mid, BaseZ))
	{
		return 0;
	}
	// WHERE THE DECK IS NOW. After a give-way this box is two metres lower than the
	// one the yard staged, and the anvil is down there with it.
	const FBox Box = DeckComp->Bounds.GetBox();
	const double TopZ = Box.Max.Z;

	const FBox Inner = Box.ExpandBy(FVector(-kInnerInsetCm, -kInnerInsetCm, 0.0));
	if (Mid.X >= Inner.Min.X && Mid.X <= Inner.Max.X
		&& Mid.Y >= Inner.Min.Y && Mid.Y <= Inner.Max.Y
		&& BaseZ >= TopZ - kInnerBelowCm && BaseZ <= TopZ + kInnerAboveCm)
	{
		return 1;
	}
	const FBox Outer = Box.ExpandBy(FVector(kOuterOutsetCm, kOuterOutsetCm, 0.0));
	if (Mid.X >= Outer.Min.X && Mid.X <= Outer.Max.X
		&& Mid.Y >= Outer.Min.Y && Mid.Y <= Outer.Max.Y
		&& BaseZ >= TopZ - kOuterBelowCm && BaseZ <= TopZ + kOuterAboveCm)
	{
		return -1;
	}
	return 0;
}

double ATrestleLoadFunctionalTest::DeckDropCm(const FSpan& Span) const
{
	const UPrimitiveComponent* const DeckComp = Span.Deck.Get();
	if (DeckComp == nullptr)
	{
		return 0.0;
	}
	// The span actor's origin is the deck's RESTING centre and the fixture pins it
	// there every frame, so this is a measurement off two world transforms and not off
	// anything the span says about itself.
	return Span.StagedAt.Z - DeckComp->Bounds.Origin.Z;
}

bool ATrestleLoadFunctionalTest::IsSettled(const FSpan& Span, double Now) const
{
	return Now - Span.TruthChangedAt >= kSettleS;
}

void ATrestleLoadFunctionalTest::UpdateSpanTruth(FSpan& Span, double Now)
{
	double NewTotal = 0.0;
	int32 NewCount = 0;
	bool bAmbiguous = false;
	FString Items;

	for (const FLoad& L : Loads)
	{
		const int32 Where = ClassifyOnSpan(Span, L.Actor.Get());
		if (Where > 0)
		{
			NewTotal += L.WeightKg;
			++NewCount;
			Items += FString::Printf(TEXT("%s%s %.0f kg"),
				Items.IsEmpty() ? TEXT("") : TEXT(" + "), L.Name, L.WeightKg);
		}
		else if (Where < 0)
		{
			bAmbiguous = true;
		}
	}
	const int32 HeroWhere = ClassifyOnSpan(Span, Hero.Get());
	if (HeroWhere > 0)
	{
		NewTotal += CharacterMassKg;
		++NewCount;
		Items += FString::Printf(TEXT("%sthe character %.0f kg"),
			Items.IsEmpty() ? TEXT("") : TEXT(" + "), CharacterMassKg);
	}
	else if (HeroWhere < 0)
	{
		bAmbiguous = true;
	}
	if (Items.IsEmpty())
	{
		Items = TEXT("nothing");
	}

	bool bChanged = NewCount != Span.Occupants
		|| !FMath::IsNearlyEqual(NewTotal, Span.TotalKg, 0.5);
	Span.TotalKg = NewTotal;
	Span.Occupants = NewCount;
	Span.ItemList = Items;
	Span.bAmbiguous = bAmbiguous;

	Span.EmptySince = NewCount == 0
		? (Span.EmptySince < 0.0 ? Now : Span.EmptySince)
		: -1.0;

	if (!Span.bExpectDown)
	{
		if (NewTotal > Span.RatedKg)
		{
			Span.bExpectDown = true;
			bChanged = true;
		}
	}
	else if (Span.EmptySince >= 0.0 && Now - Span.EmptySince >= kEmptyDebounceS)
	{
		Span.bExpectDown = false;
		Span.bRecoveryPending = true;
		bChanged = true;
	}

	// While anything is in the band between plainly-on and plainly-off, the fixture's
	// truth is not settled and nothing is asserted.
	if (bChanged || bAmbiguous)
	{
		Span.TruthChangedAt = Now;
	}

	const double Drop = DeckDropCm(Span);
	const bool bDown = Drop >= kDownFraction * Span.DropCm;
	const bool bUp = Drop <= Span.FullSagCm + kUpSlackCm;
	if (bDown && !Span.bDeckWasDown)
	{
		++Span.GaveWayCount;
		Span.bDeckWasDown = true;
	}
	else if (bUp && Span.bDeckWasDown)
	{
		++Span.CameBackCount;
		Span.bDeckWasDown = false;
	}
	if (bUp && !Span.bExpectDown)
	{
		Span.bRecoveryPending = false;
	}
}

// ------------------------------------------------------------------------------------
// Gates -- one FinishTest(Failed) apiece, so a log says which one fired
// ------------------------------------------------------------------------------------

FString ATrestleLoadFunctionalTest::DescribeSpan(const FSpan& Span) const
{
	return FString::Printf(TEXT("%s (%s) = %.0f kg against a rating of %.0f kg"),
		Span.Name, *Span.ItemList, Span.TotalKg, Span.RatedKg);
}

void ATrestleLoadFunctionalTest::FailHolds(const FSpan& Span)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ItHoldsWhatItIsRatedFor: a span holds anything up to its own rating, and "
			 "this one has dropped out from under a load it is rated for. Carrying %s, "
			 "and its deck sits %.0f cm below where it rests -- a span that is holding "
			 "is never more than %.0f cm down."),
		*DescribeSpan(Span), DeckDropCm(Span), Span.FullSagCm + kUpSlackCm));
}

void ATrestleLoadFunctionalTest::FailGivesWay(const FSpan& Span)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ItGivesWayWhenTheTotalGoesOver: what a span is carrying is everything "
			 "standing on it added together, and this span is over its rating and "
			 "still up. Carrying %s, with its deck only %.0f cm down; a span that has "
			 "given way is %.0f cm down. Not one item on it is over the rating on its "
			 "own -- the total is."),
		*DescribeSpan(Span), DeckDropCm(Span), Span.DropCm));
}

void ATrestleLoadFunctionalTest::FailSag(const FSpan& Span, double Measured,
	double Wanted)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheSagShowsTheWholeLoad: how far a span sags has to show the whole load "
			 "standing on it, as a fraction of its own rating. Carrying %s, so it "
			 "should be sagging %.3f of the way down; its deck is sagging %.3f "
			 "(%.1f cm of a full %.0f cm). The yard allows %.2f either way."),
		*DescribeSpan(Span), Wanted, Measured, DeckDropCm(Span), Span.FullSagCm,
		kSagTolerance));
}

void ATrestleLoadFunctionalTest::FailCharacterWeight(const FSpan& Span,
	bool bShouldHold)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheCharactersOwnWeightCounts: the character standing on a span is part "
			 "of what that span is carrying, and the character does not weigh the same "
			 "all day. The %s span is rated %.0f kg and the only thing standing on it "
			 "is the character, who weighs %.0f kg right now, so the span should be "
			 "%s. Its deck is %.0f cm below rest."),
		Span.Name, Span.RatedKg, CharacterMassKg,
		bShouldHold ? TEXT("holding") : TEXT("on the ground"), DeckDropCm(Span)));
}

void ATrestleLoadFunctionalTest::FailStaysDown(const FSpan& Span)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ItStaysDownWhileSomethingIsOnIt: a span that has given way stays down "
			 "until nothing at all is left standing on the fallen deck -- which is not "
			 "the same as the load dropping back under the rating. The %s span still "
			 "has %s standing on its fallen deck and it has come back up to %.0f cm "
			 "below rest. The deck moved when it fell; what counts as standing on it "
			 "moved with it."),
		Span.Name, *Span.ItemList, DeckDropCm(Span)));
}

void ATrestleLoadFunctionalTest::FailHeavesBackUp(const FSpan& Span, double Now)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ItHeavesBackUpOnceNothingIsOnIt: once nothing at all is left on a fallen "
			 "span it heaves itself back up, level, and works exactly as it did "
			 "before. Nothing has been standing on the %s span for %.1f s and its deck "
			 "is still %.0f cm below rest."),
		Span.Name, Now - FMath::Max(Span.EmptySince, 0.0), DeckDropCm(Span)));
}

void ATrestleLoadFunctionalTest::FailSetupChanged(const FString& What)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheYardsSetupIsNotYoursToChange: where the yard puts things, what they "
			 "weigh, what a span is rated to hold and the span's own body are the "
			 "yard's, not the solution's. %s"),
		*What));
}

void ATrestleLoadFunctionalTest::FailRoundsUnfinished(const FString& What)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheYardFinishedItsRounds: the character is walked on and off both spans "
			 "over and over, and by the end each span must have given way at least "
			 "once and come back at least once. A span the character cannot stand on "
			 "at all has not held anything. %s"),
		*What));
}

bool ATrestleLoadFunctionalTest::CheckTheYardIsAsTheYardLeftIt()
{
	for (const FSpan& S : Spans)
	{
		AActor* const A = S.Actor.Get();
		if (A == nullptr || !S.Deck.IsValid())
		{
			FailSetupChanged(FString::Printf(
				TEXT("the %s span stopped existing mid-round."), S.Name));
			return false;
		}
		if (!A->GetActorLocation().Equals(S.StagedAt, kSpanPinCm))
		{
			FailSetupChanged(FString::Printf(
				TEXT("the %s span has moved from %s to %s; the deck is meant to drop, "
					 "not the span to walk."),
				S.Name, *S.StagedAt.ToCompactString(),
				*A->GetActorLocation().ToCompactString()));
			return false;
		}
		struct FPin { const TCHAR* Name; double Want; };
		const FPin Pins[3] =
		{
			{ TEXT("RatedLoadKg"), S.RatedKg },
			{ TEXT("FullSagCm"), S.FullSagCm },
			{ TEXT("GiveWayDropCm"), S.DropCm },
		};
		for (const FPin& P : Pins)
		{
			double Now = 0.0;
			if (!ReadStampedFloat(A, P.Name, Now)
				|| !FMath::IsNearlyEqual(Now, P.Want, kNumberPinKg))
			{
				FailSetupChanged(FString::Printf(
					TEXT("the %s span reads %s = %.1f and the yard stamped %.1f; "
						 "rewriting the number a rule is about is not implementing "
						 "the rule."),
					S.Name, P.Name, Now, P.Want));
				return false;
			}
		}
		const UPrimitiveComponent* const DeckComp = S.Deck.Get();
		if (!DeckComp->IsCollisionEnabled()
			|| DeckComp->GetCollisionResponseToChannel(ECC_Pawn) != ECR_Block
			|| !DeckComp->IsVisible() || DeckComp->bHiddenInGame)
		{
			FailSetupChanged(FString::Printf(
				TEXT("the %s span's deck has stopped being something you can stand on "
					 "or see. A span drops its load by falling, not by turning into "
					 "thin air."), S.Name));
			return false;
		}
	}

	for (const FLoad& L : Loads)
	{
		AActor* const A = L.Actor.Get();
		if (A == nullptr)
		{
			FailSetupChanged(FString::Printf(
				TEXT("%s stopped existing mid-round."), L.Name));
			return false;
		}
		if (FVector::Dist2D(A->GetActorLocation(), L.StagedAt) > kCratePinCm)
		{
			FailSetupChanged(FString::Printf(
				TEXT("%s has been shifted %.0f cm sideways from where the yard put it; "
					 "a span keeps its load off itself by giving way, not by pushing "
					 "the cargo aside."),
				L.Name, FVector::Dist2D(A->GetActorLocation(), L.StagedAt)));
			return false;
		}
		double NowKg = 0.0;
		if (!ReadStampedFloat(A, TEXT("WeightKg"), NowKg)
			|| !FMath::IsNearlyEqual(NowKg, L.WeightKg, kNumberPinKg))
		{
			FailSetupChanged(FString::Printf(
				TEXT("%s reads WeightKg = %.1f and the yard stamped %.1f."),
				L.Name, NowKg, L.WeightKg));
			return false;
		}
	}

	const ACharacter* const H = Hero.Get();
	const UCharacterMovementComponent* const Move =
		H != nullptr ? H->GetCharacterMovement() : nullptr;
	if (Move == nullptr)
	{
		FailSetupChanged(TEXT("the character stopped existing mid-round."));
		return false;
	}
	if (!FMath::IsNearlyEqual(double(Move->Mass), CharacterMassKg, kNumberPinKg))
	{
		FailSetupChanged(FString::Printf(
			TEXT("the character weighs %.1f kg and the yard put %.1f kg on her; what "
				 "the character weighs is the yard's to set."),
			Move->Mass, CharacterMassKg));
		return false;
	}
	return true;
}

bool ATrestleLoadFunctionalTest::YardFinishedItsRounds(FString& OutWhy) const
{
	TArray<FString> Missing;
	for (const FStep& S : Steps)
	{
		if (S.Stand != nullptr && !S.bSampled)
		{
			Missing.Add(FString(S.Stand));
		}
	}
	for (const FSpan& S : Spans)
	{
		if (S.GaveWayCount < 1)
		{
			Missing.Add(FString::Printf(
				TEXT("the %s span never gave way"), S.Name));
		}
		if (S.CameBackCount < 1)
		{
			Missing.Add(FString::Printf(
				TEXT("the %s span never came back up"), S.Name));
		}
	}
	if (Missing.Num() == 0)
	{
		return true;
	}
	OutWhy = FString::Printf(TEXT("Stopped at stop %d of %d, and %d thing(s) never "
								  "happened: %s"),
		Step, Steps.Num(), Missing.Num(), *FString::Join(Missing, TEXT("; ")));
	return false;
}

// ------------------------------------------------------------------------------------
// The drive
// ------------------------------------------------------------------------------------

void ATrestleLoadFunctionalTest::PutCrateOnSpan(FLoad& Load, const FSpan& Span,
	double OffsetX)
{
	AActor* const A = Load.Actor.Get();
	if (A == nullptr)
	{
		return;
	}
	// The yard only ever sets a crate down on an EMPTY span, so the deck's resting top
	// is where it goes. The 2 cm is inside the crate's own settle window.
	const double TopZ = Span.StagedAt.Z + DeckHalfExtent.Z;
	const FVector At(Span.StagedAt.X + OffsetX, Span.StagedAt.Y - 200.0,
		TopZ + Load.HalfHeightCm + 2.0);
	A->SetActorLocation(At, /*bSweep=*/false);
	Load.StagedAt = At;
}

void ATrestleLoadFunctionalTest::SendCrateHome(FLoad& Load)
{
	AActor* const A = Load.Actor.Get();
	if (A == nullptr)
	{
		return;
	}
	A->SetActorLocation(Load.Home, /*bSweep=*/false);
	Load.StagedAt = Load.Home;
}

void ATrestleLoadFunctionalTest::RunYardAction(EYardAction Action)
{
	switch (Action)
	{
	case EYardAction::StageAnvil:
		PutCrateOnSpan(Loads[2], Spans[0], -250.0);
		break;
	case EYardAction::LiftAnvil:
		SendCrateHome(Loads[2]);
		break;
	case EYardAction::StageSackAndKeg:
		PutCrateOnSpan(Loads[0], Spans[0], -250.0);
		PutCrateOnSpan(Loads[1], Spans[0], 150.0);
		break;
	case EYardAction::ClearSackAndKeg:
		SendCrateHome(Loads[0]);
		SendCrateHome(Loads[1]);
		break;
	case EYardAction::ShoulderThePack:
		CharacterMassKg = PackedMassKg;
		if (Hero.IsValid() && Hero->GetCharacterMovement() != nullptr)
		{
			Hero->GetCharacterMovement()->Mass = float(CharacterMassKg);
		}
		break;
	default:
		break;
	}
}

void ATrestleLoadFunctionalTest::DriveHero(double Now)
{
	if (!Steps.IsValidIndex(Step) || !Hero.IsValid())
	{
		return;
	}
	const FStep& S = Steps[Step];
	const FVector Here = Hero->GetActorLocation();
	const FVector Flat(S.X - Here.X, S.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointCm)
	{
		if (!bActionRun)
		{
			RunYardAction(S.Action);
			bActionRun = true;
		}
		// STAND here. Every gate is about a state that has settled, and a route that
		// only passes through a spot never gives a span the chance to be judged.
		if (DwellUntil < 0.0)
		{
			DwellUntil = Now + S.Dwell;
		}
		else if (Now >= DwellUntil)
		{
			++Step;
			DwellUntil = -1.0;
			bActionRun = false;
		}
	}
	else
	{
		// The same input path a human uses. Consumed per frame, so it is re-applied
		// every tick; the world is never ticked from here.
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
	}
}

void ATrestleLoadFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Hero is deliberately NOT in this guard: a character that stopped existing is a
	// change to the yard, and is graded as one rather than quietly stalling the run.
	if (!IsRunning() || !bStaged || Spans.Num() != 2)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World != nullptr ? double(World->GetTimeSeconds()) : 0.0;

	if (!CheckTheYardIsAsTheYardLeftIt())
	{
		return;
	}

	const bool bCharWeightStand = Steps.IsValidIndex(Step)
		&& Steps[Step].bAboutTheCharactersWeight;
	const int32 AttributedSpan = bCharWeightStand ? Steps[Step].CharOnSpan : INDEX_NONE;

	for (int32 i = 0; i < Spans.Num(); ++i)
	{
		FSpan& S = Spans[i];
		UpdateSpanTruth(S, Now);
		if (S.bAmbiguous || !IsSettled(S, Now))
		{
			continue;
		}
		const double Drop = DeckDropCm(S);
		const bool bDown = Drop >= kDownFraction * S.DropCm;
		const bool bUp = Drop <= S.FullSagCm + kUpSlackCm;

		if (S.bExpectDown)
		{
			if (bDown)
			{
				continue;
			}
			if (S.TotalKg >= kOverBand * S.RatedKg)
			{
				if (i == AttributedSpan) { FailCharacterWeight(S, /*bShouldHold=*/false); }
				else                     { FailGivesWay(S); }
				return;
			}
			if (S.Occupants > 0)
			{
				FailStaysDown(S);
				return;
			}
			// Empty and on its way back up: the fixture demands nothing here.
			continue;
		}

		if (!bUp)
		{
			if (S.bRecoveryPending)          { FailHeavesBackUp(S, Now); }
			else if (i == AttributedSpan)    { FailCharacterWeight(S, /*bShouldHold=*/true); }
			else                             { FailHolds(S); }
			return;
		}
		const double Measured = Drop / FMath::Max(S.FullSagCm, 1.0);
		const double Wanted = S.TotalKg / FMath::Max(S.RatedKg, 1.0);
		if (FMath::Abs(Measured - Wanted) > kSagTolerance)
		{
			FailSag(S, Measured, Wanted);
			return;
		}
	}

	// A stand counts as SAMPLED only when the character is standing where the stand
	// says she is. A submission that drops the deck's collision instead of the deck
	// walks the whole route on the floor below and samples nothing.
	if (Steps.IsValidIndex(Step) && Steps[Step].Stand != nullptr
		&& !Steps[Step].bSampled && DwellUntil >= 0.0)
	{
		bool bSettled = true;
		for (const FSpan& S : Spans)
		{
			bSettled = bSettled && !S.bAmbiguous && IsSettled(S, Now);
		}
		bool bCharWhereExpected = true;
		for (int32 i = 0; i < Spans.Num(); ++i)
		{
			const bool bWant = (Steps[Step].CharOnSpan == i);
			bCharWhereExpected = bCharWhereExpected
				&& ((ClassifyOnSpan(Spans[i], Hero.Get()) > 0) == bWant);
		}
		if (bSettled && bCharWhereExpected)
		{
			Steps[Step].bSampled = true;
		}
	}

	DriveHero(Now);

	// ONE predicate, and the sentinel below evaluates the same one. A healthy run does
	// not burn the whole schedule; an unhealthy one is named by the gate rather than
	// quietly skipping it.
	if (Step >= Steps.Num())
	{
		FString Why;
		if (YardFinishedItsRounds(Why))
		{
			FinishTest(EFunctionalTestResult::Succeeded,
				TEXT("The yard finished its rounds: both spans held what they were "
					 "rated for, gave way when they were overloaded, stayed down while "
					 "anything was on them and came back up when they were clear."));
		}
	}
}

void ATrestleLoadFunctionalTest::LogCalibration(int32 CheckpointIndex, double Now) const
{
	const FVector At = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	FString S;
	for (const FSpan& Span : Spans)
	{
		const double Drop = DeckDropCm(Span);
		S += FString::Printf(
			TEXT("%s[rate%.0f load%.0f sag%.2f/%.2f drop%.0f exp%s amb%d gw%d up%d] "),
			Span.Name, Span.RatedKg, Span.TotalKg,
			Drop / FMath::Max(Span.FullSagCm, 1.0),
			Span.TotalKg / FMath::Max(Span.RatedKg, 1.0), Drop,
			Span.bExpectDown ? TEXT("DOWN") : TEXT("UP"), Span.bAmbiguous ? 1 : 0,
			Span.GaveWayCount, Span.CameBackCount);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-trestle calib] cp%d t=%.2f step=%d/%d at=(%.0f,%.0f,%.0f) "
			 "char=%.0fkg %s"),
		CheckpointIndex, Now, Step, Steps.Num(), At.X, At.Y, At.Z, CharacterMassKg, *S);
}

void ATrestleLoadFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalibration(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < SentinelIndex)
	{
		return;
	}
	FString Why;
	if (!YardFinishedItsRounds(Why))
	{
		FailRoundsUnfinished(Why);
	}
}
