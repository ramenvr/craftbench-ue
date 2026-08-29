// Copyright CraftBench. All Rights Reserved.

#include "KeyringFunctionalTest.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED in the prompt ------------------------------------------
	// "Everything has half a second to catch up after whatever it depends on
	// changes." Every dwell gate is sampled at 3x that, so a correct answer is
	// never asked to be quick.
	constexpr double kDisclosedSettleS = 0.5;
	constexpr double kSettleS = 1.5;
	static_assert(kSettleS >= 3.0 * kDisclosedSettleS,
		"a dwell gate must be sampled at least three times the budget the prompt "
		"discloses, or a correct answer can be failed for being slow inside its own "
		"allowance");

	// ---- UNDISCLOSED: where the fixture stands and how long it waits ------
	// All of it biased toward passing correct work, never toward failing it.
	//
	// A stop sits this far into the mat it belongs to, as a fraction of THAT prop's
	// own MatRadiusUu. The bay factor is deliberately larger than the ratio of the
	// two mat sizes: at 0.65 a bay stop is further out than a STAND mat is wide, so
	// a submission that reads one prop's number and uses it for the other kind is
	// caught by a bay that will not open, instead of passing by luck.
	constexpr double kStandStopFactor = 0.50;
	constexpr double kBayStopFactor = 0.65;

	// How close the drive has to get before it stands still. Kept small relative to
	// the mats (asserted in PrepareTest against 0.15x of the smaller radius) so the
	// WORST sample point is still deep inside the mat under a 2D read AND under a 3D
	// read that carries the character capsule's 96 uu of height.
	constexpr double kWaypointUu = 45.0;

	// The accusing halves of the gates use a GENEROUS model: a category counts as
	// held, and a mat counts as stood on, from this multiple of the prop's own
	// radius. The route is built to keep 2.0x away from anything it has not reached
	// yet (asserted), so every accusation still has 0.5x of daylight behind it and
	// no accusing gate is vacuous.
	constexpr double kNearFactor = 1.5;
	constexpr double kRouteClearFactor = 2.0;

	// Nothing solid may come nearer than this to a route point -- except the ONE bay
	// the drive walks through, where the route runs down the middle of the doorway.
	constexpr double kSolidStandoffUu = 400.0;
	constexpr double kDoorwayLaneUu = 120.0;
	// The frame's own footprint: a 700 uu panel plus a post either side, widened by the
	// 42 uu character capsule and some slack. A point out at a post is FAR from the
	// bay's middle and still inside something solid, which a radius alone cannot see.
	constexpr double kFrameHalfUu = 520.0;
	constexpr double kFrameBandUu = 150.0;
	// A key stand's post is 40 uu across.
	constexpr double kPostStandoffUu = 120.0;

	constexpr double kDwellS = 3.0;
	constexpr double kShiftDwellS = 4.0;
	constexpr double kBodyWaitS = 5.0;

	// A panel has slid aside once it has travelled this fraction of its own SlideUu,
	// and it has been moved by something other than one slide if it has gone past the
	// upper bound. Both are read off the panel's pose, never off a flag.
	constexpr double kOpenFraction = 0.90;
	constexpr double kOverTravelFraction = 1.30;

	// The staged props may not drift.
	constexpr double kStagedDriftUu = 2.0;

	// The last checkpoint. ACraftBenchFunctionalTest declares SUCCESS the moment the
	// last scheduled checkpoint is crossed, so this one sits far past the drive and
	// the whole-shift assertions are evaluated AT it. Capped: the L2 leg has a
	// 600 s wall-clock budget covering editor start, map load, PIE and shutdown.
	constexpr double kSentinelFloorS = 300.0;
	constexpr double kSentinelCeilS = 420.0;
	constexpr double kCheckpointEveryS = 10.0;

	constexpr int32 kShiftStop = 9;
	constexpr int32 kLastStop = 19;

	const FName kStandTag(TEXT("Keyring_Stand"));
	const FName kBayTag(TEXT("Keyring_Bay"));
	const FName kBoardTag(TEXT("Keyring_Board"));

	// Twelve names to cut keys from; six are drawn per run. Single ASCII words with
	// no comma in them, because the board separates its entries with commas.
	const TCHAR* const kCategoryPool[] = {
		TEXT("Copper"), TEXT("Amber"), TEXT("Slate"), TEXT("Cobalt"),
		TEXT("Ivory"), TEXT("Verdant"), TEXT("Crimson"), TEXT("Umber"),
		TEXT("Saffron"), TEXT("Indigo"), TEXT("Pewter"), TEXT("Sable")
	};
	constexpr int32 kCategoryPoolNum = UE_ARRAY_COUNT(kCategoryPool);
}

AKeyringFunctionalTest::AKeyringFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	// The re-cut has to land BEFORE any actor's BeginPlay, or a submission that reads
	// a key's category once at BeginPlay would read a value the yard then changed --
	// which would be a trick, not a task. OnWorldInitializedActors is broadcast at the
	// end of UWorld::InitializeActorsForPlay, before UWorld::BeginPlay dispatches
	// anything (the same window the t0 sanity fixture installs its log device in).
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &AKeyringFunctionalTest::OnWorldActorsInitialized);
}

void AKeyringFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------
// Reflection helpers. By NAME rather than by including the agent's header: the
// prop classes are agent-writable, and a rename must produce a message that says
// so rather than a compile error inside the verifier module.
// ---------------------------------------------------------------------------

bool AKeyringFunctionalTest::ReadName(AActor* A, const TCHAR* PropName, FName& Out) const
{
	if (A == nullptr)
	{
		return false;
	}
	const FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), PropName);
	if (P == nullptr)
	{
		return false;
	}
	Out = P->GetPropertyValue_InContainer(A);
	return true;
}

bool AKeyringFunctionalTest::WriteName(AActor* A, const TCHAR* PropName,
	const FName& Value) const
{
	if (A == nullptr)
	{
		return false;
	}
	const FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), PropName);
	if (P == nullptr)
	{
		return false;
	}
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

bool AKeyringFunctionalTest::ReadFloat(AActor* A, const TCHAR* PropName, double& Out) const
{
	if (A == nullptr)
	{
		return false;
	}
	const FFloatProperty* const P = FindFProperty<FFloatProperty>(A->GetClass(), PropName);
	if (P == nullptr)
	{
		return false;
	}
	Out = double(P->GetPropertyValue_InContainer(A));
	return true;
}

USceneComponent* AKeyringFunctionalTest::FindTaggedScene(AActor* A,
	const TCHAR* ComponentTag) const
{
	if (A == nullptr)
	{
		return nullptr;
	}
	const TArray<UActorComponent*> Found =
		A->GetComponentsByTag(USceneComponent::StaticClass(), FName(ComponentTag));
	for (UActorComponent* C : Found)
	{
		if (USceneComponent* const S = Cast<USceneComponent>(C))
		{
			return S;
		}
	}
	return nullptr;
}

UTextRenderComponent* AKeyringFunctionalTest::FindTaggedText(AActor* A,
	const TCHAR* ComponentTag) const
{
	if (A == nullptr)
	{
		return nullptr;
	}
	const TArray<UActorComponent*> Found =
		A->GetComponentsByTag(UTextRenderComponent::StaticClass(), FName(ComponentTag));
	for (UActorComponent* C : Found)
	{
		if (UTextRenderComponent* const T = Cast<UTextRenderComponent>(C))
		{
			return T;
		}
	}
	return nullptr;
}

UPointLightComponent* AKeyringFunctionalTest::FindLamp(AActor* A) const
{
	if (A == nullptr)
	{
		return nullptr;
	}
	TArray<UPointLightComponent*> Lamps;
	A->GetComponents<UPointLightComponent>(Lamps);
	return Lamps.Num() > 0 ? Lamps[0] : nullptr;
}

// ---------------------------------------------------------------------------
// Staging: everything below runs BEFORE any actor's BeginPlay.
// ---------------------------------------------------------------------------

void AKeyringFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bStaged || Params.World != GetWorld())
	{
		return;
	}
	bStaged = true;
	if (!CollectProps())
	{
		return;
	}
	if (!ClassifyYard())
	{
		return;
	}
	if (!CheckPropContract())
	{
		return;
	}
	RecutTheYard();
}

bool AKeyringFunctionalTest::CheckPropContract()
{
	// THE NUMBERS ARE PART OF THE SAME CONTRACT AS THE NAMES, and the prompt says so.
	// They live on classes the agent may edit, so shrinking a mat or a slide has to be
	// a failed shift with a message that says which one -- never a staging fault, which
	// would let any submission leave the denominator by editing one float.
	const double StandR = Stands[0].MatRadius;
	for (const FStand& S : Stands)
	{
		if (FMath::Abs(S.MatRadius - StandR) > 0.5 || StandR < 250.0 || StandR > 1000.0)
		{
			PendingBehaviourFault = FString::Printf(
				TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: the key stands' mats read")
				TEXT(" %.0f uu and %.0f uu")
				TEXT(" -- expected the mat the yard painted, found a different number"),
				StandR, S.MatRadius);
			return false;
		}
	}
	const double BayR = Bays[0].MatRadius;
	const double BayS = Bays[0].Slide;
	for (const FBay& B : Bays)
	{
		if (FMath::Abs(B.MatRadius - BayR) > 0.5 || BayR < 400.0 || BayR > 1400.0)
		{
			PendingBehaviourFault = FString::Printf(
				TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: the door bays' mats read")
				TEXT(" %.0f uu and %.0f uu")
				TEXT(" -- expected the mat the yard painted, found a different number"),
				BayR, B.MatRadius);
			return false;
		}
		if (FMath::Abs(B.Slide - BayS) > 0.5 || BayS < 400.0 || BayS > 1600.0)
		{
			PendingBehaviourFault = FString::Printf(
				TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: the bays' panels travel")
				TEXT(" %.0f uu and %.0f uu")
				TEXT(" -- expected the slide the yard built, found a different number"),
				BayS, B.Slide);
			return false;
		}
	}
	// "Stand mats and bay mats are not the same size" is a claim the prompt makes, so
	// the yard has to be able to keep it.
	if (BayR - StandR < 200.0)
	{
		PendingStagingFault = FString::Printf(
			TEXT("HARNESS-PRECONDITION: stand mats reach %.0f uu and bay mats %.0f uu, "
				 "only %.0f apart; one number would fit both and the task would measure "
				 "less than it claims"), StandR, BayR, BayR - StandR);
		return false;
	}
	return true;
}

bool AKeyringFunctionalTest::CollectProps()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> FoundStands;
	TArray<AActor*> FoundBays;
	TArray<AActor*> FoundBoards;
	UGameplayStatics::GetAllActorsWithTag(World, kStandTag, FoundStands);
	UGameplayStatics::GetAllActorsWithTag(World, kBayTag, FoundBays);
	UGameplayStatics::GetAllActorsWithTag(World, kBoardTag, FoundBoards);

	// A prop missing from the LEVEL is a staging fault -- the map is not the agent's
	// to edit, so its absence can only be the yard's own doing.
	if (FoundStands.Num() != 6 || FoundBays.Num() != 7 || FoundBoards.Num() != 1)
	{
		PendingStagingFault = FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard staged %d key stand(s), %d door bay(s) "
				 "and %d board(s); this task needs 6, 7 and 1"),
			FoundStands.Num(), FoundBays.Num(), FoundBoards.Num());
		return false;
	}

	Board = FoundBoards[0];
	Sign = FindTaggedText(FoundBoards[0], TEXT("Sign"));
	if (!Sign.IsValid())
	{
		// The BOARD is in the level; what is missing is the face the yard reads it
		// through, and that face lives in a class the agent may edit. Graded.
		PendingBehaviourFault =
			TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: the board no longer carries")
			TEXT(" a readout tagged Sign")
			TEXT(" -- expected the supplied names and tags to survive, found one gone");
		return false;
	}

	for (AActor* A : FoundStands)
	{
		FStand S;
		S.Actor = A;
		S.StagedAt = A->GetActorLocation();
		S.KeyMesh = FindTaggedScene(A, TEXT("Key"));
		S.Lamp = FindLamp(A);
		if (!ReadName(A, TEXT("KeyCategory"), S.Category)
			|| !ReadFloat(A, TEXT("MatRadiusUu"), S.MatRadius)
			|| !S.KeyMesh.IsValid() || S.Lamp == nullptr)
		{
			PendingBehaviourFault =
				TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: a key stand no longer")
				TEXT(" answers to KeyCategory, MatRadiusUu, a tagged Key and a lamp")
				TEXT(" -- expected the supplied names and tags to survive, found one gone");
			return false;
		}
		Stands.Add(S);
	}

	for (AActor* A : FoundBays)
	{
		FBay B;
		B.Actor = A;
		B.StagedAt = A->GetActorLocation();
		B.Panel = FindTaggedScene(A, TEXT("Panel"));
		if (!ReadName(A, TEXT("WantsCategory"), B.Wants)
			|| !ReadName(A, TEXT("AlsoWantsCategory"), B.AlsoWants)
			|| !ReadFloat(A, TEXT("MatRadiusUu"), B.MatRadius)
			|| !ReadFloat(A, TEXT("SlideUu"), B.Slide)
			|| !B.Panel.IsValid())
		{
			PendingBehaviourFault =
				TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: a door bay no longer")
				TEXT(" answers to WantsCategory, AlsoWantsCategory, MatRadiusUu, SlideUu")
				TEXT(" and a tagged Panel")
				TEXT(" -- expected the supplied names and tags to survive, found one gone");
			return false;
		}
		// The pose the panel is IN before anything has had a chance to move it. Every
		// later read of "open" is a distance from this.
		B.PanelShutRel = B.Panel->GetRelativeLocation();
		Bays.Add(B);
	}
	return true;
}

bool AKeyringFunctionalTest::ClassifyYard()
{
	// Roles are read off the SHAPE of the yard, never off a name or an index the
	// level happened to report. Six bays stand in one row; the seventh stands well
	// off it, inside the walled corner. Two stands are south of the row, one is in
	// the corner with the seventh bay, three are away on the far side.
	TArray<FBay> ByY = Bays;
	ByY.Sort([](const FBay& L, const FBay& R) { return L.StagedAt.Y < R.StagedAt.Y; });
	if (ByY[5].StagedAt.Y - ByY[0].StagedAt.Y > 200.0
		|| ByY[6].StagedAt.Y - ByY[5].StagedAt.Y < 1200.0)
	{
		PendingStagingFault = TEXT("HARNESS-PRECONDITION: the yard's bays are not six "
			"in a row plus one standing well off it, so the fixture cannot tell which "
			"bay is the way into the walled corner");
		return false;
	}
	TArray<FBay> Row;
	for (int32 i = 0; i < 6; ++i)
	{
		Row.Add(ByY[i]);
	}
	Row.Sort([](const FBay& L, const FBay& R) { return L.StagedAt.X < R.StagedAt.X; });
	const FBay AlcoveB = ByY[6];
	RowY = Row[0].StagedAt.Y;

	TArray<FStand> SByY = Stands;
	SByY.Sort([](const FStand& L, const FStand& R) { return L.StagedAt.Y < R.StagedAt.Y; });
	if (SByY[1].StagedAt.Y > RowY - 1200.0 || SByY[2].StagedAt.Y < RowY + 500.0)
	{
		PendingStagingFault = TEXT("HARNESS-PRECONDITION: the yard does not have exactly "
			"two key stands south of the bay row, so the fixture cannot tell which two "
			"keys the first half of the shift is meant to fetch");
		return false;
	}
	TArray<FStand> South;
	South.Add(SByY[0]);
	South.Add(SByY[1]);
	South.Sort([](const FStand& L, const FStand& R) { return L.StagedAt.X < R.StagedAt.X; });

	TArray<FStand> Corner;
	TArray<FStand> Far;
	for (int32 i = 2; i < 6; ++i)
	{
		const double DX = FMath::Abs(SByY[i].StagedAt.X - AlcoveB.StagedAt.X);
		if (DX <= 3000.0)
		{
			Corner.Add(SByY[i]);
		}
		else if (DX >= 4000.0)
		{
			Far.Add(SByY[i]);
		}
	}
	if (Corner.Num() != 1 || Far.Num() != 3)
	{
		PendingStagingFault = TEXT("HARNESS-PRECONDITION: the yard does not have exactly "
			"one key stand inside the walled corner and three away from it, so the "
			"fixture cannot tell which key the fresh body is meant to fetch");
		return false;
	}
	Far.Sort([](const FStand& L, const FStand& R) { return L.StagedAt.X < R.StagedAt.X; });

	// Canonical order. Everything downstream refers to these indices.
	Stands.Reset();
	Stands.Add(South[0]);   // 0 : the first key of the shift
	Stands.Add(South[1]);   // 1 : the second
	Stands.Add(Corner[0]);  // 2 : the one the fresh body fetches
	Stands.Add(Far[0]);     // 3 : nobody ever goes there
	Stands.Add(Far[1]);
	Stands.Add(Far[2]);
	StandI = 0; StandII = 1; StandIII = 2; StandZ = 3;

	Bays.Reset();
	for (const FBay& B : Row)
	{
		Bays.Add(B);
	}
	Bays.Add(AlcoveB);
	BayA1 = 0; BayA2 = 1; BayZ = 2; BayB1 = 3; BayFar = 4; BayWall = 5; BayAlcove = 6;

	for (int32 i = 0; i < Stands.Num(); ++i) { Stands[i].Label = i + 1; }
	for (int32 i = 0; i < Bays.Num(); ++i) { Bays[i].Label = i + 1; }
	return true;
}

bool AKeyringFunctionalTest::RecutTheYard()
{
	// A SEED, logged and overridable, so a run is reproducible while no two runs share
	// their category names. A submission carrying a canned board string, a remembered
	// ordering, or a hard-coded category cannot survive the re-cut.
	if (!FParse::Value(FCommandLine::Get(), TEXT("KeyYardSeed="), RecutSeed) || RecutSeed == 0)
	{
		RecutSeed = int32(FPlatformTime::Cycles() & 0x7fffffff);
	}
	FRandomStream Stream(RecutSeed);

	TArray<FString> Pool;
	for (int32 i = 0; i < kCategoryPoolNum; ++i)
	{
		Pool.Add(FString(kCategoryPool[i]));
	}
	for (int32 i = Pool.Num() - 1; i > 0; --i)
	{
		Pool.Swap(i, Stream.RandRange(0, i));
	}

	bool bWrote = true;
	for (int32 i = 0; i < Stands.Num(); ++i)
	{
		Stands[i].Category = FName(*Pool[i]);
		bWrote &= WriteName(Stands[i].Actor.Get(), TEXT("KeyCategory"), Stands[i].Category);
	}

	// Every bay's demand is derived from a ROLE, never from where the bay stands, so
	// the categories move between runs and the discrimination stops do not.
	const FName A = Stands[StandI].Category;
	const FName B = Stands[StandII].Category;
	const FName C = Stands[StandIII].Category;
	const FName Z = Stands[StandZ].Category;
	const FName None = NAME_None;

	auto Paint = [this, &bWrote](int32 Index, const FName& Wants, const FName& Also)
	{
		Bays[Index].Wants = Wants;
		Bays[Index].AlsoWants = Also;
		bWrote &= WriteName(Bays[Index].Actor.Get(), TEXT("WantsCategory"), Wants);
		bWrote &= WriteName(Bays[Index].Actor.Get(), TEXT("AlsoWantsCategory"), Also);
	};
	Paint(BayA1, A, None);
	Paint(BayA2, A, None);      // the SECOND bay of the first key -- a key is not spent
	Paint(BayZ, Z, None);       // a key nobody ever fetches
	Paint(BayB1, B, None);
	Paint(BayFar, A, C);        // the one bay painted with two
	Paint(BayWall, B, None);    // the way into the walled corner
	Paint(BayAlcove, C, None);

	UE_LOG(LogTemp, Display,
		TEXT("[t3-keyring recut] seed=%d stands=%s/%s/%s/%s/%s/%s bays=%s|%s|%s|%s|%s+%s|%s|%s"),
		RecutSeed,
		*Stands[0].Category.ToString(), *Stands[1].Category.ToString(),
		*Stands[2].Category.ToString(), *Stands[3].Category.ToString(),
		*Stands[4].Category.ToString(), *Stands[5].Category.ToString(),
		*Bays[BayA1].Wants.ToString(), *Bays[BayA2].Wants.ToString(),
		*Bays[BayZ].Wants.ToString(), *Bays[BayB1].Wants.ToString(),
		*Bays[BayFar].Wants.ToString(), *Bays[BayFar].AlsoWants.ToString(),
		*Bays[BayWall].Wants.ToString(), *Bays[BayAlcove].Wants.ToString());

	if (!bWrote)
	{
		// The properties were all readable a moment ago, so a write that did not land
		// means the class changed under the yard. Graded: the class is the agent's.
		PendingBehaviourFault =
			TEXT("ThePropsStillCarryWhatTheYardWroteOnThem: the yard could not cut its")
			TEXT(" keys onto the stands")
			TEXT(" -- expected the supplied names and tags to survive, found one gone");
		return false;
	}
	return true;
}

// ---------------------------------------------------------------------------
// Readbacks
// ---------------------------------------------------------------------------

bool AKeyringFunctionalTest::ReadKeyTaken(const FStand& S) const
{
	// THE KEY AND THE LAMP TOGETHER, never a flag. A bool that says the key is gone
	// while the key is still floating over the post is not a key being taken, and a
	// half-done handover reads as NOT taken -- the safe direction, since the accusing
	// half of the gate only ever fires on a stand that reads taken.
	const USceneComponent* const K = S.KeyMesh.Get();
	const UPointLightComponent* const L = S.Lamp.Get();
	if (K == nullptr || L == nullptr)
	{
		return false;
	}
	return K->bHiddenInGame && L->Intensity <= 0.0f;
}

double AKeyringFunctionalTest::ReadPanelTravel(const FBay& B) const
{
	const USceneComponent* const P = B.Panel.Get();
	if (P == nullptr)
	{
		return 0.0;
	}
	return FVector::Dist(P->GetRelativeLocation(), B.PanelShutRel);
}

bool AKeyringFunctionalTest::ReadBayOpen(const FBay& B) const
{
	// THE PANEL, never a flag. A bay whose panel is still across the frame is shut
	// however loudly anything says otherwise, and a panel that has been hidden,
	// re-collided or slid back reads shut too. Anything short of a full slide reads
	// SHUT, which is the safe direction: a submission part-way through its own
	// animation is judged 1.5 s into a 3.0 s stand, long after it has finished.
	return B.Slide > 1.0 && ReadPanelTravel(B) >= kOpenFraction * B.Slide;
}

FString AKeyringFunctionalTest::ReadBoard() const
{
	const UTextRenderComponent* const T = Sign.Get();
	return T != nullptr ? T->Text.ToString() : FString();
}

void AKeyringFunctionalTest::ParseBoard(TArray<FString>& OutTokens) const
{
	OutTokens.Reset();
	const FString Raw = ReadBoard().TrimStartAndEnd();
	if (Raw.IsEmpty() || Raw == TEXT("--"))
	{
		return;
	}
	TArray<FString> Parts;
	Raw.ParseIntoArray(Parts, TEXT(","), /*InCullEmpty=*/false);
	for (const FString& P : Parts)
	{
		OutTokens.Add(P.TrimStartAndEnd());
	}
}

// ---------------------------------------------------------------------------
// The fixture's own truth about the ring
// ---------------------------------------------------------------------------

FString AKeyringFunctionalTest::RingText() const
{
	FString S;
	for (int32 i = 0; i < PickupOrder.Num(); ++i)
	{
		if (i > 0)
		{
			S += TEXT(", ");
		}
		S += Stands[PickupOrder[i]].Category.ToString();
	}
	return S.IsEmpty() ? FString(TEXT("--")) : S;
}

bool AKeyringFunctionalTest::RingHolds(const FName& Category) const
{
	if (Category.IsNone())
	{
		return true;
	}
	for (int32 Index : PickupOrder)
	{
		if (Stands[Index].Category == Category)
		{
			return true;
		}
	}
	return false;
}

bool AKeyringFunctionalTest::NearModelHolds(const FName& Category) const
{
	// The GENEROUS model: a category counts as held from the moment the character got
	// anywhere near the stand that carries it. Used only where the fixture is about to
	// accuse, so being a little quick on the draw is never punished.
	if (Category.IsNone())
	{
		return true;
	}
	for (const FStand& S : Stands)
	{
		if (S.Category == Category && S.bNearMat)
		{
			return true;
		}
	}
	return false;
}

FString AKeyringFunctionalTest::BayDemandText(const FBay& B) const
{
	return B.AlsoWants.IsNone()
		? B.Wants.ToString()
		: FString::Printf(TEXT("%s + %s"), *B.Wants.ToString(), *B.AlsoWants.ToString());
}

// ---------------------------------------------------------------------------
// Route
// ---------------------------------------------------------------------------

FVector AKeyringFunctionalTest::BayStop(const FBay& B, bool bFromSouth) const
{
	const double Off = kBayStopFactor * B.MatRadius * (bFromSouth ? -1.0 : 1.0);
	return FVector(B.StagedAt.X, B.StagedAt.Y + Off, Muster.Z);
}

FVector AKeyringFunctionalTest::StandStop(const FStand& S, bool bFromNorth) const
{
	const double Off = kStandStopFactor * S.MatRadius * (bFromNorth ? 1.0 : -1.0);
	return FVector(S.StagedAt.X, S.StagedAt.Y + Off, Muster.Z);
}

void AKeyringFunctionalTest::PushCorner(const FVector& Loc)
{
	if (Route.Num() > 0 && FVector::Dist2D(Route.Last().Loc, Loc) < 1.0)
	{
		return;
	}
	FNode N;
	N.Loc = Loc;
	Route.Add(N);
}

void AKeyringFunctionalTest::PushPlazaStop(const FVector& Stop, int32 Label, double Dwell)
{
	const FVector Cursor = Route.Num() > 0 ? Route.Last().Loc : Muster;
	PushCorner(FVector(Cursor.X, LaneY, Muster.Z));
	PushCorner(FVector(Stop.X, LaneY, Muster.Z));
	if (Route.Num() > 0 && Route.Last().Stop == 0
		&& FVector::Dist2D(Route.Last().Loc, Stop) < 1.0)
	{
		Route.Pop();
	}
	FNode N;
	N.Loc = Stop;
	N.Stop = Label;
	N.Dwell = Dwell;
	Route.Add(N);
}

void AKeyringFunctionalTest::PushAlcoveStop(const FVector& Stop, int32 Label, double Dwell)
{
	const FVector Cursor = Route.Num() > 0 ? Route.Last().Loc : AlcoveEntry;
	PushCorner(FVector(Cursor.X, AlcoveEntry.Y, Muster.Z));
	PushCorner(FVector(Stop.X, AlcoveEntry.Y, Muster.Z));
	if (Route.Num() > 0 && Route.Last().Stop == 0
		&& FVector::Dist2D(Route.Last().Loc, Stop) < 1.0)
	{
		Route.Pop();
	}
	FNode N;
	N.Loc = Stop;
	N.Stop = Label;
	N.Dwell = Dwell;
	Route.Add(N);
}

void AKeyringFunctionalTest::BuildRoute()
{
	Route.Reset();

	FNode First;
	First.Loc = Muster;
	First.Stop = 1;
	First.Dwell = kDwellS;
	Route.Add(First);

	PushPlazaStop(BayStop(Bays[BayA1], true), 2, kDwellS);
	PushPlazaStop(StandStop(Stands[StandI], true), 3, kDwellS);
	PushPlazaStop(BayStop(Bays[BayA1], true), 4, kDwellS);
	PushPlazaStop(BayStop(Bays[BayA2], true), 5, kDwellS);
	PushPlazaStop(BayStop(Bays[BayZ], true), 6, kDwellS);
	PushPlazaStop(StandStop(Stands[StandII], true), 7, kDwellS);
	PushPlazaStop(BayStop(Bays[BayB1], true), 8, kDwellS);

	// The relief mark: the lane corner opposite the bay just opened. The shift changes
	// at the END of this dwell.
	{
		FNode N;
		N.Loc = FVector(Bays[BayB1].StagedAt.X, LaneY, Muster.Z);
		N.Stop = kShiftStop;
		N.Dwell = kShiftDwellS;
		Route.Add(N);
	}
	// The fresh body takes over at the gate, which is where this stop already is, so
	// there is nothing to walk: the dwell starts the frame the new body is possessed.
	{
		FNode N;
		N.Loc = Muster;
		N.Stop = 10;
		N.Dwell = kShiftDwellS;
		Route.Add(N);
	}

	PushPlazaStop(BayStop(Bays[BayFar], true), 11, kDwellS);
	PushPlazaStop(BayStop(Bays[BayWall], true), 12, kDwellS);

	// Straight through the bay just opened, into the walled corner. If it did not
	// really open, the panel is still across the way and the drive stalls HERE -- the
	// watchdog names the bay rather than blaming the yard.
	PushCorner(AlcoveEntry);
	PushAlcoveStop(BayStop(Bays[BayAlcove], true), 13, kDwellS);
	PushAlcoveStop(StandStop(Stands[StandIII], false), 14, kDwellS);
	PushAlcoveStop(BayStop(Bays[BayAlcove], true), 15, kDwellS);

	// Back out the same way.
	PushCorner(FVector(Route.Last().Loc.X, AlcoveEntry.Y, Muster.Z));
	PushCorner(AlcoveEntry);
	PushCorner(FVector(AlcoveEntry.X, BayStop(Bays[BayWall], true).Y, Muster.Z));

	PushPlazaStop(BayStop(Bays[BayFar], true), 16, kDwellS);
	PushPlazaStop(BayStop(Bays[BayZ], true), 17, kDwellS);
	PushPlazaStop(BayStop(Bays[BayA1], true), 18, kDwellS);
	PushPlazaStop(Muster, kLastStop, kDwellS);

	RouteLength = 0.0;
	for (int32 i = 0; i + 1 < Route.Num(); ++i)
	{
		RouteLength += FVector::Dist2D(Route[i].Loc, Route[i + 1].Loc);
	}
}

bool AKeyringFunctionalTest::CheckRouteStaging()
{
	// Where each prop is first STOOD ON. Everything before that node has to keep well
	// clear of it, or the accusing half of a gate ("nobody has been near this yet")
	// could never fire.
	TArray<int32> FirstBayNode;
	TArray<int32> FirstStandNode;
	FirstBayNode.Init(INDEX_NONE, Bays.Num());
	FirstStandNode.Init(INDEX_NONE, Stands.Num());
	for (int32 n = 0; n < Route.Num(); ++n)
	{
		if (Route[n].Stop == 0)
		{
			continue;
		}
		for (int32 b = 0; b < Bays.Num(); ++b)
		{
			if (FirstBayNode[b] == INDEX_NONE
				&& FVector::Dist2D(Route[n].Loc, Bays[b].StagedAt) <= Bays[b].MatRadius)
			{
				FirstBayNode[b] = n;
			}
		}
		for (int32 s = 0; s < Stands.Num(); ++s)
		{
			if (FirstStandNode[s] == INDEX_NONE
				&& FVector::Dist2D(Route[n].Loc, Stands[s].StagedAt) <= Stands[s].MatRadius)
			{
				FirstStandNode[s] = n;
			}
		}
	}
	for (int32 b = 0; b < Bays.Num(); ++b)
	{
		if (FirstBayNode[b] == INDEX_NONE)
		{
			PendingStagingFault = FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive never stands on bay %d's mat, so "
					 "nothing about that bay could ever be measured"), b + 1);
			return false;
		}
	}
	for (int32 s = 0; s < 3; ++s)
	{
		if (FirstStandNode[s] == INDEX_NONE)
		{
			PendingStagingFault = FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive never stands on stand %d's mat, "
					 "so its key could never be fetched"), s + 1);
			return false;
		}
	}
	for (int32 s = 3; s < Stands.Num(); ++s)
	{
		if (FirstStandNode[s] != INDEX_NONE)
		{
			PendingStagingFault = FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive stands on stand %d's mat, and that "
					 "stand's key is the one no bay may open for"), s + 1);
			return false;
		}
	}

	// Every stop has to be plainly inside the mat it is about -- under a flat read AND
	// under a read that carries the character capsule's height, and at the worst point
	// the drive is allowed to stop.
	for (const FNode& N : Route)
	{
		if (N.Stop == 0)
		{
			continue;
		}
		for (const FBay& B : Bays)
		{
			const double D = FVector::Dist2D(N.Loc, B.StagedAt);
			if (D > B.MatRadius)
			{
				continue;
			}
			const double Worst2D = D + kWaypointUu;
			const double Worst3D = FMath::Sqrt(Worst2D * Worst2D + HeroHalfHeight * HeroHalfHeight);
			if (Worst3D > 0.75 * B.MatRadius || kWaypointUu > 0.15 * B.MatRadius)
			{
				PendingStagingFault = FString::Printf(
					TEXT("HARNESS-PRECONDITION: a stop on bay %d's mat could settle "
						 "%.0f uu out on a mat %.0f uu wide; a correct answer could be "
						 "failed for standing where the yard put it"),
					B.Label, Worst3D, B.MatRadius);
				return false;
			}
		}
		for (const FStand& S : Stands)
		{
			const double D = FVector::Dist2D(N.Loc, S.StagedAt);
			if (D > S.MatRadius)
			{
				continue;
			}
			const double Worst2D = D + kWaypointUu;
			const double Worst3D = FMath::Sqrt(Worst2D * Worst2D + HeroHalfHeight * HeroHalfHeight);
			if (Worst3D > 0.75 * S.MatRadius || kWaypointUu > 0.15 * S.MatRadius)
			{
				PendingStagingFault = FString::Printf(
					TEXT("HARNESS-PRECONDITION: a stop on stand %d's mat could settle "
						 "%.0f uu out on a mat %.0f uu wide; a correct answer could be "
						 "failed for standing where the yard put it"),
					S.Label, Worst3D, S.MatRadius);
				return false;
			}
		}
	}

	// A bay stop has to be further out than a STAND mat is wide, or a submission that
	// reads one prop's number and uses it on the other kind would pass by luck.
	double MaxStandR = 0.0;
	for (const FStand& S : Stands)
	{
		MaxStandR = FMath::Max(MaxStandR, S.MatRadius);
	}
	for (const FBay& B : Bays)
	{
		if (kBayStopFactor * B.MatRadius - kWaypointUu <= MaxStandR)
		{
			PendingStagingFault = FString::Printf(
				TEXT("HARNESS-PRECONDITION: a bay stop stands %.0f uu out and the widest "
					 "stand mat is %.0f uu; using the wrong prop's number would open the "
					 "bay anyway and the task would measure less than it claims"),
				kBayStopFactor * B.MatRadius - kWaypointUu, MaxStandR);
			return false;
		}
	}

	// Nothing may be approached before its own stop, and nothing solid may be walked
	// into. Both are sampled along every leg, not just at the corners.
	constexpr int32 kSamples = 48;
	for (int32 k = 0; k + 1 < Route.Num(); ++k)
	{
		for (int32 t = 0; t <= kSamples; ++t)
		{
			const FVector P = FMath::Lerp(Route[k].Loc, Route[k + 1].Loc,
				double(t) / double(kSamples));
			for (int32 b = 0; b < Bays.Num(); ++b)
			{
				const double D = FVector::Dist2D(P, Bays[b].StagedAt);
				const double DX = FMath::Abs(P.X - Bays[b].StagedAt.X);
				const double DY = FMath::Abs(P.Y - Bays[b].StagedAt.Y);
				// The one bay the drive walks THROUGH: allowed, but only down the
				// middle of its doorway.
				const bool bThroughDoorway = (b == BayWall) && DX <= kDoorwayLaneUu;
				// Radial standoff catches an approach from anywhere; the band catches
				// the case the radius cannot -- a point out at the frame post, which is
				// far from the bay's middle and right inside something solid.
				const bool bInTheFrame = (DY < kFrameBandUu) && (DX < kFrameHalfUu);
				if (!bThroughDoorway && (bInTheFrame || D < kSolidStandoffUu))
				{
					PendingStagingFault = FString::Printf(
						TEXT("HARNESS-PRECONDITION: leg %d of the walk passes %.0f uu "
							 "from bay %d's frame; the character would jam against it"),
						k, D, b + 1);
					return false;
				}
				// Everything the drive has not reached yet stays two mats away.
				if (k + 1 < FirstBayNode[b]
					&& D < kRouteClearFactor * Bays[b].MatRadius)
				{
					PendingStagingFault = FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walk comes %.0f uu from bay %d "
							 "before the drive ever stands on its mat, so the yard could "
							 "never say nobody had been there"), D, b + 1);
					return false;
				}
			}
			for (int32 s = 0; s < Stands.Num(); ++s)
			{
				const double D = FVector::Dist2D(P, Stands[s].StagedAt);
				if (D < kPostStandoffUu)
				{
					PendingStagingFault = FString::Printf(
						TEXT("HARNESS-PRECONDITION: leg %d of the walk passes %.0f uu "
							 "from stand %d's post; the character would jam against it"),
						k, D, s + 1);
					return false;
				}
				if (k + 1 < FirstStandNode[s] || FirstStandNode[s] == INDEX_NONE)
				{
					if (D < kRouteClearFactor * Stands[s].MatRadius)
					{
						PendingStagingFault = FString::Printf(
							TEXT("HARNESS-PRECONDITION: the walk comes %.0f uu from stand "
								 "%d before the drive ever stands on its mat, so the yard "
								 "could never say nobody had been there"), D, s + 1);
						return false;
					}
				}
			}
		}
	}
	return true;
}

// ---------------------------------------------------------------------------
// PrepareTest
// ---------------------------------------------------------------------------

void AKeyringFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}
	if (!PendingBehaviourFault.IsEmpty())
	{
		FailBehaviour(PendingBehaviourFault);
		return;
	}
	if (!PendingStagingFault.IsEmpty())
	{
		FailStaging(PendingStagingFault);
		return;
	}
	if (!bStaged)
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: the yard was never staged; the "
			"pre-BeginPlay pass did not run for this world"));
		return;
	}

	// Six distinct categories, one bay painted with two, and at least one bay asking
	// for a key the drive never fetches. Without all three the task measures less
	// than it claims.
	for (int32 i = 0; i < Stands.Num(); ++i)
	{
		if (Stands[i].Category.IsNone())
		{
			FailStaging(TEXT("HARNESS-PRECONDITION: a key stand has no category cut "
				"into it"));
			return;
		}
		for (int32 j = i + 1; j < Stands.Num(); ++j)
		{
			if (Stands[i].Category == Stands[j].Category)
			{
				FailStaging(TEXT("HARNESS-PRECONDITION: two key stands carry the same "
					"category, so the yard cannot tell one key from the other"));
				return;
			}
		}
	}
	int32 TwoCat = 0;
	for (const FBay& B : Bays)
	{
		if (!B.AlsoWants.IsNone())
		{
			++TwoCat;
		}
	}
	if (TwoCat != 1)
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: %d bay(s) are painted "
			"with two categories; this task needs exactly one"), TwoCat));
		return;
	}
	// At least one bay has to ask for a key the drive never fetches, or the gate that
	// catches "any key opens any door" would have nothing to catch it with.
	bool bUnreachableDemand = false;
	for (const FBay& B : Bays)
	{
		bool bAnyVisitedCarriesIt = false;
		for (int32 s = 0; s < 3; ++s)
		{
			bAnyVisitedCarriesIt |= (Stands[s].Category == B.Wants);
		}
		bUnreachableDemand |= !bAnyVisitedCarriesIt;
	}
	if (!bUnreachableDemand)
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: every bay in the yard asks for a key the "
			"drive fetches, so nothing would ever have to stay shut and the task would "
			"measure less than it claims"));
		return;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid())
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: no player character in the yard"));
		return;
	}
	if (const UCapsuleComponent* const Capsule = Hero->GetCapsuleComponent())
	{
		HeroHalfHeight = Capsule->GetScaledCapsuleHalfHeight();
	}
	if (const UCharacterMovementComponent* const Move = Hero->GetCharacterMovement())
	{
		WalkSpeed = FMath::Max(50.0, double(Move->MaxWalkSpeed));
	}

	// EXACTLY ONE PlayerStart. ChoosePlayerStart picks at random among the unoccupied
	// ones, so a second start would move the fresh body somewhere else on some runs
	// and the whole second half of the drive would change length.
	int32 StartCount = 0;
	for (TActorIterator<APlayerStart> It(World); It; ++It)
	{
		Start = *It;
		++StartCount;
	}
	if (StartCount != 1)
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: the yard has %d "
			"PlayerStart(s); the shift change needs exactly one so the fresh body "
			"always takes over in the same place"), StartCount));
		return;
	}
	AGameModeBase* const GM = World->GetAuthGameMode();
	if (GM == nullptr || GM->DefaultPawnClass == nullptr)
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: the level's game mode has no default "
			"pawn class, so nothing can be spawned for the fresh body"));
		return;
	}

	// Geometry, all of it derived from where the props actually stand.
	double MaxBayR = 0.0;
	for (const FBay& B : Bays)
	{
		MaxBayR = FMath::Max(MaxBayR, B.MatRadius);
	}
	LaneY = RowY - 2.4 * MaxBayR;
	AlcoveEntry = FVector(Bays[BayWall].StagedAt.X,
		RowY + 0.7 * MaxBayR, Hero->GetActorLocation().Z);
	Muster = FVector(Start->GetActorLocation().X, LaneY, Hero->GetActorLocation().Z);
	if (FMath::Abs(Start->GetActorLocation().Y - LaneY) > 250.0)
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: the PlayerStart sits "
			"%.0f uu off the lane the drive walks; the fresh body would take over "
			"somewhere the drive is not"),
			FMath::Abs(Start->GetActorLocation().Y - LaneY)));
		return;
	}

	BuildRoute();
	if (!CheckRouteStaging())
	{
		FailStaging(PendingStagingFault);
		return;
	}

	// The sentinel is derived from the MEASURED route, not guessed, and then capped:
	// the L2 leg has a fixed wall-clock budget and a schedule that outran it would
	// look like a hung test.
	double Dwells = 0.0;
	for (const FNode& N : Route)
	{
		Dwells += N.Dwell;
	}
	// 0.35 s per corner covers the ramp up to walking speed out of every standstill
	// (2048 uu/s/s to 500 uu/s is 0.25 s), measured against the drive, not guessed.
	const double Estimate = RouteLength / WalkSpeed + Dwells + 0.35 * double(Route.Num());
	SentinelAt = FMath::Clamp(Estimate * 1.6 + 30.0, kSentinelFloorS, kSentinelCeilS);
	if (Estimate * 1.35 + 20.0 > kSentinelCeilS)
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: the drive is %.0f uu "
			"long and would need about %.0f s, which does not fit inside the %.0f s "
			"the shift is given"), RouteLength, Estimate, kSentinelCeilS));
		return;
	}

	TArray<double> Schedule;
	for (double T = kCheckpointEveryS; T < SentinelAt - 1.0; T += kCheckpointEveryS)
	{
		Schedule.Add(T);
	}
	Schedule.Add(SentinelAt);
	SentinelIndex = Schedule.Num() - 1;
	SetCheckpointSchedule(Schedule);

	SegmentStartedAt = World->GetTimeSeconds();
	UE_LOG(LogTemp, Display,
		TEXT("[t3-keyring route] nodes=%d length=%.0f uu speed=%.0f estimate=%.0f s "
			 "sentinel=%.0f s laneY=%.0f entry=(%.0f,%.0f)"),
		Route.Num(), RouteLength, WalkSpeed, Estimate, SentinelAt, LaneY,
		AlcoveEntry.X, AlcoveEntry.Y);
}

void AKeyringFunctionalTest::FailStaging(const FString& Why)
{
	FinishTest(EFunctionalTestResult::Error, Why);
}

void AKeyringFunctionalTest::FailBehaviour(const FString& Why)
{
	FinishTest(EFunctionalTestResult::Failed, Why);
}

// ---------------------------------------------------------------------------
// Per-frame
// ---------------------------------------------------------------------------

void AKeyringFunctionalTest::UpdateModels(const FVector& HeroAt, double Now)
{
	for (int32 i = 0; i < Stands.Num(); ++i)
	{
		FStand& S = Stands[i];
		const double D = FVector::Dist2D(HeroAt, S.StagedAt);
		if (D <= S.MatRadius && !S.bStoodOnMat)
		{
			S.bStoodOnMat = true;
			PickupOrder.Add(i);
			PickupTimes.Add(Now);
		}
		if (D <= kNearFactor * S.MatRadius)
		{
			S.bNearMat = true;
		}
	}
	for (FBay& B : Bays)
	{
		if (FVector::Dist2D(HeroAt, B.StagedAt) <= kNearFactor * B.MatRadius)
		{
			B.bNearMat = true;
		}
	}
}

bool AKeyringFunctionalTest::CheckPropsIntact(double Now)
{
	for (const FStand& S : Stands)
	{
		const AActor* const A = S.Actor.Get();
		if (A == nullptr || !S.KeyMesh.IsValid() || !S.Lamp.IsValid())
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardStagedThisAndItIsNotYoursToChange: stand %d has lost a piece")
				TEXT(" the yard reads it through")
				TEXT(" -- expected every prop still standing and readable, found one gone"),
				S.Label));
			return false;
		}
		const double Drift = FVector::Dist(A->GetActorLocation(), S.StagedAt);
		if (Drift > kStagedDriftUu)
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardStagedThisAndItIsNotYoursToChange: stand %d has moved %.0f uu")
				TEXT(" from where the yard put it")
				TEXT(" -- expected the props left where they stand, found one shifted"),
				S.Label, Drift));
			return false;
		}
	}
	for (const FBay& B : Bays)
	{
		const AActor* const A = B.Actor.Get();
		if (A == nullptr || !B.Panel.IsValid())
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardStagedThisAndItIsNotYoursToChange: bay %d has lost its panel")
				TEXT(" -- expected a panel still in the frame, found none"),
				B.Label));
			return false;
		}
		const double Drift = FVector::Dist(A->GetActorLocation(), B.StagedAt);
		if (Drift > kStagedDriftUu)
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardStagedThisAndItIsNotYoursToChange: bay %d has moved %.0f uu")
				TEXT(" from where the yard put it")
				TEXT(" -- expected the props left where they stand, found one shifted"),
				B.Label, Drift));
			return false;
		}
		const double Travel = ReadPanelTravel(B);
		if (Travel > kOverTravelFraction * B.Slide)
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardStagedThisAndItIsNotYoursToChange: bay %d's panel travelled")
				TEXT(" %.0f uu and one slide is %.0f uu")
				TEXT(" -- expected a panel slid aside once at most, found one gone further"),
				B.Label, Travel, B.Slide));
			return false;
		}
	}
	if (!Board.IsValid() || !Sign.IsValid())
	{
		FailBehaviour(
			TEXT("TheYardStagedThisAndItIsNotYoursToChange: the board has lost the face")
			TEXT(" the yard reads it through")
			TEXT(" -- expected every prop still standing and readable, found one gone"));
		return false;
	}
	return true;
}

bool AKeyringFunctionalTest::RunContinuousGates(double Now)
{
	for (FBay& B : Bays)
	{
		const bool bOpen = ReadBayOpen(B);
		if (bOpen && !B.bEverOpen)
		{
			B.bEverOpen = true;
			B.OpenedAt = Now;
		}
		if (!bOpen && B.bEverOpen)
		{
			FailBehaviour(FString::Printf(
				TEXT("ADoorThatOpenedStaysOpen: bay %d opened at t=%.1f s and its panel is")
				TEXT(" back across the frame at t=%.1f s")
				TEXT(" -- expected a bay that opened to stay open, found it shut again"),
				B.Label, B.OpenedAt, Now));
			return false;
		}
		if (!bOpen)
		{
			continue;
		}
		if (!NearModelHolds(B.Wants) || !NearModelHolds(B.AlsoWants))
		{
			FailBehaviour(FString::Printf(
				TEXT("ADoorAnswersOnlyToTheKeysItAsksFor: bay %d is painted with '%s' and")
				TEXT(" the shift has not been to the stand that carries it")
				TEXT(" -- expected this bay shut, found it open"),
				B.Label, *BayDemandText(B)));
			return false;
		}
		if (!B.bNearMat)
		{
			FailBehaviour(FString::Printf(
				TEXT("ADoorAnswersOnlyToTheKeysItAsksFor: bay %d is open and nobody has")
				TEXT(" stood anywhere near its mat")
				TEXT(" -- expected a bay nobody has stood at to stay shut, found it open"),
				B.Label));
			return false;
		}
	}
	for (const FStand& S : Stands)
	{
		if (ReadKeyTaken(S) && !S.bNearMat)
		{
			FailBehaviour(FString::Printf(
				TEXT("OnlyTheKeysYouWentToAreGone: stand %d is empty and nobody has walked")
				TEXT(" anywhere near its mat")
				TEXT(" -- expected a stand nobody stood at to keep its key, found it gone"),
				S.Label));
			return false;
		}
	}
	return true;
}

void AKeyringFunctionalTest::DoShiftChange(double Now)
{
	UWorld* const World = GetWorld();
	APlayerController* const PC = UGameplayStatics::GetPlayerController(World, 0);
	if (PC == nullptr || PC->GetPawn() == nullptr || !Start.IsValid())
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: there was no body on the controller to "
			"retire at the shift change"));
		return;
	}

	// (a) The yard blanks the board ITSELF, straight onto the face. No agent-facing
	//     call is made, so nothing a submission does can be clobbered by this and a
	//     submission that never redraws has nowhere to hide.
	if (UTextRenderComponent* const T = Sign.Get())
	{
		T->SetText(FText::FromString(TEXT("--")));
	}

	// (b) Retire the body. APawn::Destroyed detaches it from the controller
	//     synchronously (UnPossess + ChangeState(Inactive)); the controller and its
	//     player state survive, because AController only destroys itself when it has
	//     no player state and a PlayerController always has one.
	RetiredBody = PC->GetPawn();
	RetiredBodyName = PC->GetPawn()->GetFName();
	PC->GetPawn()->Destroy();

	// (c) A fresh body at the gate, on the SAME frame. RestartPlayerAtTransform only
	//     spawns when the controller's pawn is already null -- which (b) has just made
	//     true -- and taking the transform rather than a player start keeps the fresh
	//     body's position exactly where the yard wants it.
	if (AGameModeBase* const GM = World->GetAuthGameMode())
	{
		GM->RestartPlayerAtTransform(PC, Start->GetActorTransform());
	}

	bShiftDone = true;
	ShiftAt = Now;
	bAwaitingBody = true;
	AwaitUntil = Now + kBodyWaitS;
	Hero.Reset();
	UE_LOG(LogTemp, Display, TEXT("[t3-keyring shift] t=%.2f retired=%s board wiped"),
		Now, *RetiredBodyName.ToString());
}

void AKeyringFunctionalTest::DriveAndGrade(double Now)
{
	if (!Route.IsValidIndex(NodeIndex) || !Hero.IsValid())
	{
		return;
	}
	const FNode& N = Route[NodeIndex];
	const FVector HeroAt = Hero->GetActorLocation();
	const FVector Flat(N.Loc.X - HeroAt.X, N.Loc.Y - HeroAt.Y, 0.0);

	if (Flat.Size2D() > kWaypointUu)
	{
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);

		// A stall is only the submission's fault when something the submission was
		// supposed to open is still across the way. Anything else is the yard's.
		const FVector From = NodeIndex > 0 ? Route[NodeIndex - 1].Loc : Muster;
		const double Expected = FVector::Dist2D(From, N.Loc) / WalkSpeed;
		if (Now > SegmentStartedAt + 3.0 * Expected + 25.0)
		{
			// Corners have no number of their own; name the stop the drive is heading
			// for, which is what a reader can find on the route.
			int32 Heading = kLastStop;
			for (int32 i = NodeIndex; i < Route.Num(); ++i)
			{
				if (Route[i].Stop > 0)
				{
					Heading = Route[i].Stop;
					break;
				}
			}
			for (const FBay& B : Bays)
			{
				const bool bOnTheWay =
					FMath::Abs(B.StagedAt.X - N.Loc.X) <= kDoorwayLaneUu
					&& FMath::Min(From.Y, N.Loc.Y) - 100.0 <= B.StagedAt.Y
					&& B.StagedAt.Y <= FMath::Max(From.Y, N.Loc.Y) + 100.0;
				if (bOnTheWay && !ReadBayOpen(B))
				{
					FailBehaviour(FString::Printf(
						TEXT("TheYardRanTheWholeShift: the shift has been stuck short of")
						TEXT(" stop %d for %.0f s with bay %d's panel across the way")
						TEXT(" -- expected a bay that opened to let the shift through, found it shut"),
						Heading, Now - SegmentStartedAt, B.Label));
					return;
				}
			}
			FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: the drive has not "
				"reached stop %d in %.0f s and no bay panel is across the way; the yard "
				"cannot walk its own route"), Heading, Now - SegmentStartedAt));
		}
		return;
	}

	// STANDING. Every gate that needs a settled state is measured from here.
	if (DwellStart < 0.0)
	{
		DwellStart = Now;
		if (N.Stop > 0)
		{
			LastStopReached = N.Stop;
		}
	}
	const double Elapsed = Now - DwellStart;
	if (N.Stop > 0 && !bGradedThisNode && Elapsed >= kSettleS)
	{
		bGradedThisNode = true;
		GradeStop(N.Stop, Now);
		if (!IsRunning())
		{
			return;
		}
	}
	if (Elapsed < N.Dwell)
	{
		return;
	}
	if (N.Stop == kShiftStop && !bShiftDone)
	{
		DoShiftChange(Now);
		return;
	}
	++NodeIndex;
	DwellStart = -1.0;
	bGradedThisNode = false;
	SegmentStartedAt = Now;
}

void AKeyringFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || Route.Num() == 0)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	if (!CheckPropsIntact(Now))
	{
		return;
	}

	// The body is NEVER cached across the swap: it is re-resolved from the controller
	// every frame, which is the same thing a submission has to do.
	if (bAwaitingBody)
	{
		ACharacter* const Fresh = UGameplayStatics::GetPlayerCharacter(GetWorld(), 0);
		if (Fresh != nullptr && !RetiredBody.IsValid()
			&& Fresh->GetFName() != RetiredBodyName)
		{
			Hero = Fresh;
			bAwaitingBody = false;
			bFreshBodyConfirmed = true;
			++NodeIndex;
			DwellStart = -1.0;
			bGradedThisNode = false;
			SegmentStartedAt = Now;
		}
		else if (Now > AwaitUntil)
		{
			FailStaging(TEXT("HARNESS-PRECONDITION: the shift change produced no fresh "
				"body on the controller within five seconds"));
		}
		return;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(GetWorld(), 0);
	if (Hero.IsValid())
	{
		UpdateModels(Hero->GetActorLocation(), Now);
	}
	if (!RunContinuousGates(Now))
	{
		return;
	}
	DriveAndGrade(Now);
}

// ---------------------------------------------------------------------------
// The gates
// ---------------------------------------------------------------------------

void AKeyringFunctionalTest::GateBoardShowsRing(int32 Stop, double Now)
{
	TArray<FString> Tokens;
	ParseBoard(Tokens);
	if (Tokens.Num() != PickupOrder.Num())
	{
		FailBehaviour(FString::Printf(
			TEXT("TheBoardShowsWhatIsOnTheRing: at stop %d the board reads '%s' and the")
			TEXT(" ring is '%s' -- expected %d category name(s) on the board, found %d"),
			Stop, *ReadBoard(), *RingText(), PickupOrder.Num(), Tokens.Num()));
		return;
	}
	for (int32 i = 0; i < Tokens.Num(); ++i)
	{
		if (!Tokens[i].Equals(Stands[PickupOrder[i]].Category.ToString(),
			ESearchCase::IgnoreCase))
		{
			FailBehaviour(FString::Printf(
				TEXT("TheBoardShowsWhatIsOnTheRing: at stop %d the board reads '%s' and")
				TEXT(" the shift picked up '%s'")
				TEXT(" -- expected the categories in pickup order, found another order"),
				Stop, *ReadBoard(), *RingText()));
			return;
		}
	}
}

void AKeyringFunctionalTest::GateBoardAfterShift(int32 Stop, double Now)
{
	TArray<FString> Tokens;
	ParseBoard(Tokens);
	bool bSame = Tokens.Num() == PickupOrder.Num();
	for (int32 i = 0; bSame && i < Tokens.Num(); ++i)
	{
		bSame = Tokens[i].Equals(Stands[PickupOrder[i]].Category.ToString(),
			ESearchCase::IgnoreCase);
	}
	if (!bSame)
	{
		FailBehaviour(FString::Printf(
			TEXT("TheRingOutlivesTheBody: the yard wiped the board and swapped the body")
			TEXT(" %.1f s ago, the board now reads '%s' and the shift carries '%s'")
			TEXT(" -- expected the ring back on the board after the change, found none"),
			Now - ShiftAt, *ReadBoard(), *RingText()));
	}
}

void AKeyringFunctionalTest::GateBoardForNewBody(int32 Stop, double Now)
{
	TArray<FString> Tokens;
	ParseBoard(Tokens);
	bool bSame = Tokens.Num() == PickupOrder.Num();
	for (int32 i = 0; bSame && i < Tokens.Num(); ++i)
	{
		bSame = Tokens[i].Equals(Stands[PickupOrder[i]].Category.ToString(),
			ESearchCase::IgnoreCase);
	}
	if (!bSame)
	{
		FailBehaviour(FString::Printf(
			TEXT("TheNewBodyPicksUpWhereTheOldOneLeftOff: the board reads '%s' and the")
			TEXT(" shift carries '%s' -- expected every category on the board after")
			TEXT(" the fresh body picked one up, found %d of them"),
			*ReadBoard(), *RingText(), Tokens.Num()));
	}
}

void AKeyringFunctionalTest::GateStandGaveItsKey(int32 Stop, const FStand& S, double Now)
{
	if (!ReadKeyTaken(S))
	{
		FailBehaviour(FString::Printf(
			TEXT("OnlyTheKeysYouWentToAreGone: the character has stood on stand %d's mat")
			TEXT(" for %.1f s -- expected 1 key gone from that stand, found 0"),
			S.Label, Now - DwellStart));
	}
}

void AKeyringFunctionalTest::GateStandGaveItsKeyToNewBody(int32 Stop, const FStand& S,
	double Now)
{
	if (!ReadKeyTaken(S))
	{
		FailBehaviour(FString::Printf(
			TEXT("TheNewBodyPicksUpWhereTheOldOneLeftOff: the fresh body has stood on")
			TEXT(" stand %d's mat for %.1f s, %.0f s after taking over")
			TEXT(" -- expected that stand's key on the ring, found it still on the stand"),
			S.Label, Now - DwellStart, Now - ShiftAt));
	}
}

void AKeyringFunctionalTest::GateBayShut(int32 Stop, const FBay& B, double Now)
{
	// PREMISE FIRST. A negative result is only worth what the state behind it is worth:
	// if the drive HAS fetched everything this bay asks for, the stop is not a shut-bay
	// stop at all and calling it one would fail correct work.
	if (RingHolds(B.Wants) && RingHolds(B.AlsoWants))
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: stop %d expects bay %d "
			"to be shut, but the ring already holds '%s'; the drive is not walking the "
			"route this gate was written for"), Stop, B.Label, *BayDemandText(B)));
		return;
	}
	if (ReadBayOpen(B))
	{
		FailBehaviour(FString::Printf(
			TEXT("ADoorAnswersOnlyToTheKeysItAsksFor: bay %d is painted with '%s' and the")
			TEXT(" ring holds '%s' -- expected this bay shut, found it open"),
			B.Label, *BayDemandText(B), *RingText()));
	}
}

void AKeyringFunctionalTest::GateBayOpen(int32 Stop, const FBay& B, double Now)
{
	// PREMISE FIRST: an open-bay stop is only a fair demand once the drive has actually
	// been to every stand this bay asks for.
	if (!RingHolds(B.Wants) || !RingHolds(B.AlsoWants))
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: stop %d expects bay %d "
			"to open for '%s' and the drive has not fetched all of it; the drive is not "
			"walking the route this gate was written for"),
			Stop, B.Label, *BayDemandText(B)));
		return;
	}
	if (!ReadBayOpen(B))
	{
		FailBehaviour(FString::Printf(
			TEXT("ADoorAnswersOnlyToTheKeysItAsksFor: bay %d is painted with '%s', the")
			TEXT(" ring holds '%s', and the character has stood on its mat for %.1f s")
			TEXT(" -- expected this bay open, found it shut"),
			B.Label, *BayDemandText(B), *RingText(), Now - DwellStart));
	}
}

void AKeyringFunctionalTest::GateBaySecondOfItsKind(int32 Stop, const FBay& B, double Now)
{
	int32 Already = INDEX_NONE;
	for (const FBay& Other : Bays)
	{
		if (Other.Label != B.Label && Other.bEverOpen && Other.Wants == B.Wants)
		{
			Already = Other.Label;
			break;
		}
	}
	// PREMISE FIRST: "a key is never used up" can only be measured once that key has
	// already opened something else.
	if (Already == INDEX_NONE || !RingHolds(B.Wants))
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: stop %d expects bay %d "
			"to be the second bay '%s' opens, and no earlier bay of that key is open; "
			"the drive is not walking the route this gate was written for"),
			Stop, B.Label, *B.Wants.ToString()));
		return;
	}
	if (!ReadBayOpen(B))
	{
		FailBehaviour(FString::Printf(
			TEXT("AKeyOpensEveryDoorItWasCutFor: '%s' already opened bay %d and bay %d is")
			TEXT(" painted with it too -- expected this bay open too, found it shut"),
			*B.Wants.ToString(), Already, B.Label));
	}
}

void AKeyringFunctionalTest::GateBayOpenForNewBody(int32 Stop, const FBay& B, double Now)
{
	// PREMISE FIRST: the whole point of this stop is a bay that was never opened before
	// the swap, opening for a key the RETIRED body fetched.
	const bool bOpenedBeforeTheSwap = B.OpenedAt >= 0.0 && B.OpenedAt < ShiftAt;
	if (!bShiftDone || !RingHolds(B.Wants) || !RingHolds(B.AlsoWants) || bOpenedBeforeTheSwap)
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: stop %d expects bay %d to "
			"open for the fresh body for the first time, and either the shift never "
			"changed or the bay was already open before it did; the drive is not walking "
			"the route this gate was written for"), Stop, B.Label));
		return;
	}
	if (!ReadBayOpen(B))
	{
		FailBehaviour(FString::Printf(
			TEXT("TheRingOutlivesTheBody: bay %d is painted with '%s', the shift picked")
			TEXT(" that key up %.0f s before the change and has never opened this bay")
			TEXT(" -- expected this bay open for the fresh body, found it shut"),
			B.Label, *BayDemandText(B), Now - ShiftAt));
	}
}

void AKeyringFunctionalTest::GateFarBayOpen(int32 Stop, const FBay& B, double Now)
{
	// PREMISE FIRST: this stop only means anything if the ring is genuinely carrying
	// one key from before the shift change and one from after it.
	bool bOneEachSide = false;
	if (B.AlsoWants.IsNone() || !bShiftDone)
	{
		bOneEachSide = false;
	}
	else
	{
		bool bBefore = false;
		bool bAfter = false;
		for (int32 i = 0; i < PickupOrder.Num(); ++i)
		{
			const FStand& S = Stands[PickupOrder[i]];
			if (S.Category != B.Wants && S.Category != B.AlsoWants)
			{
				continue;
			}
			// Which body fetched it is decided by the clock, not by a count.
			if (PickupTimes[i] < ShiftAt)
			{
				bBefore = true;
			}
			else
			{
				bAfter = true;
			}
		}
		bOneEachSide = bBefore && bAfter;
	}
	if (!bOneEachSide)
	{
		FailStaging(FString::Printf(TEXT("HARNESS-PRECONDITION: stop %d expects the bay "
			"painted with two categories to hold one key from each side of the shift "
			"change, and the ring is '%s'; the drive is not walking the route this gate "
			"was written for"), Stop, *RingText()));
		return;
	}
	if (!ReadBayOpen(B))
	{
		FailBehaviour(FString::Printf(
			TEXT("TheNewBodyPicksUpWhereTheOldOneLeftOff: bay %d is painted with '%s',")
			TEXT(" one fetched by the retired body and one by the fresh one")
			TEXT(" -- expected the bay that asks for two to open, found it shut"),
			B.Label, *BayDemandText(B)));
	}
}

void AKeyringFunctionalTest::GateBayStillOpen(int32 Stop, const FBay& B, double Now)
{
	if (!ReadBayOpen(B))
	{
		FailBehaviour(FString::Printf(
			TEXT("ADoorThatOpenedStaysOpen: bay %d opened %.0f s and one shift change ago")
			TEXT(" -- expected it still open, found it shut"),
			B.Label, Now - B.OpenedAt));
	}
}

void AKeyringFunctionalTest::GradeStop(int32 Stop, double Now)
{
	switch (Stop)
	{
	case 1:
		GateBoardShowsRing(Stop, Now);
		break;
	case 2:
		GateBayShut(Stop, Bays[BayA1], Now);
		break;
	case 3:
		// The stand first, then the board: an untouched yard has to fail on the thing
		// that plainly did not happen, not on a readout that follows from it.
		GateStandGaveItsKey(Stop, Stands[StandI], Now);
		if (IsRunning()) { GateBoardShowsRing(Stop, Now); }
		break;
	case 4:
		GateBayOpen(Stop, Bays[BayA1], Now);
		break;
	case 5:
		GateBaySecondOfItsKind(Stop, Bays[BayA2], Now);
		break;
	case 6:
		GateBayShut(Stop, Bays[BayZ], Now);
		break;
	case 7:
		GateStandGaveItsKey(Stop, Stands[StandII], Now);
		if (IsRunning()) { GateBoardShowsRing(Stop, Now); }
		break;
	case 8:
		GateBayOpen(Stop, Bays[BayB1], Now);
		break;
	case 9:
		break;   // the shift changes at the END of this dwell; nothing is graded here
	case 10:
		GateBoardAfterShift(Stop, Now);
		break;
	case 11:
		GateBayShut(Stop, Bays[BayFar], Now);
		break;
	case 12:
		GateBayOpenForNewBody(Stop, Bays[BayWall], Now);
		break;
	case 13:
		GateBayShut(Stop, Bays[BayAlcove], Now);
		break;
	case 14:
		GateStandGaveItsKeyToNewBody(Stop, Stands[StandIII], Now);
		if (IsRunning()) { GateBoardForNewBody(Stop, Now); }
		break;
	case 15:
		GateBayOpen(Stop, Bays[BayAlcove], Now);
		break;
	case 16:
		GateFarBayOpen(Stop, Bays[BayFar], Now);
		break;
	case 17:
		GateBayShut(Stop, Bays[BayZ], Now);
		break;
	case 18:
		GateBayStillOpen(Stop, Bays[BayA1], Now);
		break;
	case kLastStop:
		GateBoardShowsRing(Stop, Now);
		break;
	default:
		break;
	}
}

// ---------------------------------------------------------------------------
// Checkpoints: calibration, and the sentinel
// ---------------------------------------------------------------------------

void AKeyringFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString Open;
	for (const FBay& B : Bays)
	{
		Open += FString::Printf(TEXT("%d"), ReadBayOpen(B) ? 1 : 0);
	}
	FString Taken;
	for (const FStand& S : Stands)
	{
		Taken += FString::Printf(TEXT("%d"), ReadKeyTaken(S) ? 1 : 0);
	}
	const FVector At = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-keyring calib] cp%d t=%.2f stop=%d node=%d at=(%.0f,%.0f) bays=%s "
			 "stands=%s board='%s' ring='%s' shift=%d"),
		Index, Now, LastStopReached, NodeIndex, At.X, At.Y, *Open, *Taken,
		*ReadBoard(), *RingText(), bShiftDone ? 1 : 0);
}

void AKeyringFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < SentinelIndex)
	{
		return;
	}

	// THE SENTINEL. Everything deferred is evaluated here, because the base class ends
	// the test the moment the last scheduled checkpoint is crossed and a grade hung off
	// a measured event that never happened would simply be skipped.
	if (LastStopReached < kLastStop)
	{
		FailBehaviour(FString::Printf(
			TEXT("TheYardRanTheWholeShift: the drive reached stop %d of %d")
			TEXT(" -- expected the whole shift walked, found it stopped short"),
			LastStopReached, kLastStop));
		return;
	}
	if (!bShiftDone || !bFreshBodyConfirmed)
	{
		FailStaging(TEXT("HARNESS-PRECONDITION: the shift change never produced a fresh "
			"body, so nothing about the ring outliving one was measured"));
		return;
	}
	for (const FBay& B : Bays)
	{
		if (!B.Actor.IsValid() || !B.Panel.IsValid()
			|| FVector::Dist(B.Actor->GetActorLocation(), B.StagedAt) > kStagedDriftUu)
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardRanTheWholeShift: bay %d is not where the yard staged it, or")
				TEXT(" has lost its panel")
				TEXT(" -- expected every prop still where it was put, found one missing"),
				B.Label));
			return;
		}
	}
	for (const FStand& S : Stands)
	{
		if (!S.Actor.IsValid() || !S.KeyMesh.IsValid()
			|| FVector::Dist(S.Actor->GetActorLocation(), S.StagedAt) > kStagedDriftUu)
		{
			FailBehaviour(FString::Printf(
				TEXT("TheYardRanTheWholeShift: stand %d is not where the yard staged it,")
				TEXT(" or has lost its key")
				TEXT(" -- expected every prop still where it was put, found one missing"),
				S.Label));
			return;
		}
	}
}
