// Copyright CraftBench. All Rights Reserved.

#include "WingHostFunctionalTest.h"

#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/LevelStreaming.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "UObject/UnrealType.h"

namespace
{
	// ================= DISCLOSED IN THE PROMPT =================
	// Every one of these is a number the agent was given. Nothing else gates.
	constexpr double kSettleS = 1.5;      // "within a second and a half of the step"

	// ================= THE LAYOUT TABLE =================
	// IDENTICAL to authoring/author_map.py. These are GRADED (SealedWingUntouched),
	// so the two tables must never drift; the authoring script asserts its own
	// read-back against them before it saves.
	const FVector2D kMarkAt[3] = {
		FVector2D(-1400.0, -1200.0),   // ALPHA
		FVector2D(0.0, -1200.0),       // BETA
		FVector2D(1400.0, -1200.0),    // GAMMA
	};
	const TCHAR* const kMarkIds[3] = { TEXT("ALPHA"), TEXT("BETA"), TEXT("GAMMA") };

	const FVector2D kPostAt[4] = {
		FVector2D(-2250.0, 600.0),     // HALL
		FVector2D(-750.0, 600.0),      // ROSE
		FVector2D(750.0, 600.0),       // GOLD
		FVector2D(2250.0, 600.0),      // SLATE
	};
	const TCHAR* const kWingNames[4] = {
		TEXT("HALL"), TEXT("ROSE"), TEXT("GOLD"), TEXT("SLATE") };
	// THE SECTION NAMES ARE NOT THE WING NAMES, and they are printed nowhere the agent
	// can read. A wing's section is knowable only by reading that wing's own post, so the
	// join from "which wing was called" to "what has to enter the running world" is a
	// SECOND world read rather than a string the agent can concatenate. An earlier draft
	// named them L_Wing<WING>, which UGameplayStatics::GetStreamingLevel resolves
	// case-insensitively by package-name suffix -- so the post was decorative and the
	// join was free.
	const TCHAR* const kSectionIds[4] = {
		TEXT("L_WingVault"), TEXT("L_WingLoft"), TEXT("L_WingKeep"), TEXT("L_WingSpur") };

	// HOW MANY FITTINGS EACH WING HOLDS, in kWingNames order. THE WINGS ARE NOT ALL THE
	// SAME SIZE, and not one of these numbers is written down anywhere the agent can
	// read: the prompt says only that no two wings need hold the same number, and that
	// the board reports how many of the called wing's fittings are STANDING. So the
	// board's number is a second obligatory world read, coupled to the first, and no
	// constant can supply it -- the deals are mirrored, so cp1 wants ROSE's count on the
	// fast leg and GOLD's on the slow one, and a submission that reports the count it
	// had at the instant of the step reports a wing that has not arrived yet.
	constexpr int32 kWingFittings[4] = { 3, 4, 6, 4 };

	// The control gate reads the hall by name rather than by index, so the two can
	// never drift apart in a later edit.
	constexpr int32 kHallFittings = kWingFittings[0];

	const FVector2D kBoardAt(0.0, 2450.0);

	// THE IN-SCENE NEGATIVE CONTROL. Same class, same host, same streaming mechanism
	// as the three callable wings, and indistinguishable from one to any "clear
	// everything, then load the target" loop.
	const FVector kHallFittingAt[3] = {
		FVector(-2670.0, 1250.0, 0.0),
		FVector(-2250.0, 1650.0, 0.0),
		FVector(-1830.0, 1250.0, 0.0),
	};

	// Where the drive stands while the marks are re-lettered: square below ALPHA,
	// 1200 uu from it and 1844 uu from the nearest other mark.
	const FVector2D kClearSpot(-1400.0, -2400.0);

	// Where the drive steps OFF BETA before stepping straight back onto it: square below
	// BETA, 1200 uu from it and 1844 uu from ALPHA and from GAMMA. The same-mark re-step
	// is the ONLY gauge point at which a take-down and a bring-in issued against one
	// shared handle can present -- every other step in the drive is a change of wing,
	// where that slip is invisible because the two calls name different sections.
	const FVector2D kStepOffAt(0.0, -2400.0);

	// ================= THE MIRRORED DEALS =================
	// [leg][deal][mark] -> the wing that mark is showing.
	// GAMMA carries SLATE in both deals of both legs and is never stepped on, which is
	// what makes "a wing nobody has called never has a fitting in the host" a MEASURED
	// statement rather than a slogan.
	const TCHAR* const kDeal[2][2][3] = {
		// leg 0 -- the fast leg (-FPS=60). Deal 0 is what the LEVEL stages, so a human
		// who simply presses Play walks into a coherent, labelled building.
		{ { TEXT("ROSE"), TEXT("GOLD"), TEXT("SLATE") },
		  { TEXT("GOLD"), TEXT("ROSE"), TEXT("SLATE") } },
		// leg 1 -- the slow leg (-FPS=20). MIRRORED: a hard-coded ALPHA->ROSE is wrong
		// at the FIRST gauge point here, and both legs have to pass.
		{ { TEXT("GOLD"), TEXT("ROSE"), TEXT("SLATE") },
		  { TEXT("ROSE"), TEXT("GOLD"), TEXT("SLATE") } },
	};

	// ================= FIXTURE-OWNED GEOMETRY AND CLOCKING =================
	// None of these is a threshold on the answer. Each widens the disclosed contract
	// in the one direction that cannot manufacture a FAIL.

	// The step is registered at 45 uu from the mark's centre. The ENGINE's own
	// begin-overlap fires at about 152 uu (110 uu box half-extent + 42 uu capsule
	// radius), so the submission is ALWAYS notified first and is never handed less
	// than the second the prompt promised.
	constexpr double kArriveCm = 45.0;

	// How near a mark the character has to be for the stall re-check to accept that
	// mark's wing as legitimately standing. Comfortably wider than the engine's own
	// begin-overlap reach, because the whole point is to forgive the window in which a
	// CORRECT submission has already swapped and the fixture has not yet said "landed".
	constexpr double kStallReachCm = 250.0;

	// The approach ramp. At full pace the character's 2000 uu/s^2 braking deceleration
	// carries it 62 cm past the stop point -- off a 220 cm plate. Easing off the stick
	// inside 800 and 350 uu leaves it resting about 50 uu from the centre.
	constexpr double kRampFarCm = 800.0;
	constexpr double kRampNearCm = 350.0;
	constexpr float kRampFarScale = 0.5f;
	constexpr float kRampNearScale = 0.3f;
	constexpr float kFullScale = 1.0f;

	// The re-deal fires only while the character is this far from EVERY mark, so a
	// re-letter can never land during a step and manufacture a FAIL on correct work.
	constexpr double kClearOfMarkCm = 700.0;

	// cp0, the explicitly reported baseline, sampled once the world has settled and
	// well before the first walk.
	constexpr double kBaselineAtS = 1.5;

	// Widenings of "exactly where they stand" and "do not move a mark, a post or the
	// board". Both are one-sided: they can only ever forgive.
	constexpr double kHallMoveCm = 1.0;
	constexpr double kFurnitureMoveCm = 2.0;

	// How near a placed actor has to be to its slot in the layout table for the
	// fixture to say "this is that one". Far wider than kFurnitureMoveCm on purpose:
	// matching and grading are different questions, and a piece nudged 100 uu should
	// be reported as MOVED, not as MISSING.
	constexpr double kMatchRadiusCm = 400.0;

	// Walk deadlines are derived from the MEASURED distance and the MEASURED pace,
	// never written down. 2.5x plus 8 s covers the ramp-down (which roughly triples
	// the last 800 uu) with about three times the margin the drive actually uses.
	constexpr double kDeadlineSlack = 2.5;
	constexpr double kDeadlineFloorS = 8.0;

	// The dense calibration grid plus a SENTINEL far past the modelled drive: the base
	// class ends the test the moment the last scheduled checkpoint is sampled, and the
	// fixture finishes itself as soon as its last phase completes. The modelled drive
	// is about 62 s of world time (eight straight legs plus seven 1.5 s settles, all
	// PREDICTED and none of it measured yet); every walk carries its own deadline, so
	// the sentinel is belt and braces rather than the mechanism.
	constexpr double kCheckpointEveryS = 2.5;
	constexpr int32 kGradedCheckpoints = 50;   // 2.5 s .. 125 s
	constexpr double kSentinelAtS = 135.0;

	// Which of the two mirrored deal sets this leg runs. 1/60 = 0.0167 and 1/20 = 0.05,
	// so 0.03 separates them with room on both sides. Derived from the leg's FIXED
	// DELTA TIME -- never wall clock, never randomness.
	constexpr double kSlowLegDtS = 0.03;

	const TCHAR* const kGaugeNames[] = {
		TEXT("cp0"), TEXT("cp1"), TEXT("cp2"), TEXT("cp3"),
		TEXT("cp3r"), TEXT("cp4"), TEXT("cp5"), TEXT("cp6") };

	const TCHAR* GaugeName(EWingGauge G)
	{
		const int32 Index = static_cast<int32>(G);
		return (Index >= 0 && Index < UE_ARRAY_COUNT(kGaugeNames))
			? kGaugeNames[Index] : TEXT("cp?");
	}

	FName FittingTag(FName Wing, int32 Ordinal)
	{
		return FName(*FString::Printf(TEXT("Fitting.%s.%d"), *Wing.ToString(), Ordinal));
	}

	/** How many fittings the named wing holds. 0 for a name no post in the host carries,
	 *  which the fixture only ever produces from its own deal table -- so 0 here means an
	 *  authoring fault, never a submission. */
	int32 FittingsForWing(FName Wing)
	{
		for (int32 i = 0; i < 4; ++i)
		{
			if (Wing == FName(kWingNames[i]))
			{
				return kWingFittings[i];
			}
		}
		return 0;
	}

	bool HasTag(const AActor* A, const TCHAR* Tag)
	{
		return A != nullptr && A->ActorHasTag(FName(Tag));
	}
}

AWingHostFunctionalTest::AWingHostFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	for (int32 i = 0; i < 3; ++i)
	{
		DealtWing[i] = NAME_None;
	}
}

// ---------------------------------------------------------------------------
// Reflection helpers. NOTHING in this fixture includes an agent-writable header:
// a submission is free to rename or re-shape its own classes, and the fixture has
// to keep working or a legitimate refactor becomes a verifier build break.
// ---------------------------------------------------------------------------

FName AWingHostFunctionalTest::ReadName(const AActor* A, const TCHAR* PropertyName,
	bool& bOk)
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), PropertyName) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return NAME_None;
}

bool AWingHostFunctionalTest::WriteName(AActor* A, const TCHAR* PropertyName,
	FName Value)
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), PropertyName) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AWingHostFunctionalTest::CallNameFunction(AActor* A, const TCHAR* FunctionName,
	FName Value)
{
	if (A == nullptr)
	{
		return false;
	}
	UFunction* const Fn = A->FindFunction(FName(FunctionName));
	if (Fn == nullptr)
	{
		return false;
	}
	// Marshal defensively: exactly one parameter, and it has to be an FName. A
	// submission that changed the signature gets the property-write fallback instead
	// of a corrupt stack.
	int32 Params = 0;
	const FNameProperty* Only = nullptr;
	for (TFieldIterator<FProperty> It(Fn); It && (It->PropertyFlags & CPF_Parm); ++It)
	{
		++Params;
		Only = CastField<FNameProperty>(*It);
	}
	if (Params != 1 || Only == nullptr || Fn->ParmsSize != sizeof(FName))
	{
		return false;
	}
	struct FOneName { FName Value; } Args{ Value };
	A->ProcessEvent(Fn, &Args);
	return true;
}

// ---------------------------------------------------------------------------
// Staging. Attributed exits ONLY for things no C++ a submission can write changes.
// ---------------------------------------------------------------------------

FString AWingHostFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	TArray<FString> Problems;

	// Half one: the pawn's own Enhanced Input actions. AThirdPersonCharacter DECLARES
	// four and assigns none, so a native pawn subclass binds nothing and the map grades
	// byte-identically while being uncontrollable. Read by PROPERTY NAME so a renamed
	// or subclassed pawn still answers.
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

	// Half two: a mapping context has to be applied, or no key reaches any of those
	// actions even when all four are set. This is the half a level naming its own game
	// mode drops, silently.
	const AGameModeBase* const GameMode = World->GetAuthGameMode();
	const UClass* const PCClass =
		GameMode != nullptr ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the ")
					 TEXT("player gets a bare APlayerController"));
	}
	else if (const FArrayProperty* Contexts = FindFProperty<FArrayProperty>(
				 PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
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
			TEXT("%s carries no DefaultMappingContexts, so nothing here can confirm ")
			TEXT("a key is mapped"), *PCClass->GetName()));
	}

	return FString::Join(Problems, TEXT("; "));
}

bool AWingHostFunctionalTest::CheckSectionsAreStagedForStreaming(UWorld* World)
{
	ULevelStreaming* Found[4] = { nullptr, nullptr, nullptr, nullptr };
	for (int32 i = 0; i < 4; ++i)
	{
		Found[i] = UGameplayStatics::GetStreamingLevel(World, FName(kSectionIds[i]));
		if (Found[i] == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the level declares no section named %s, ")
				TEXT("so the %s wing can never come into the host and nothing about ")
				TEXT("the submission could be measured"),
				kSectionIds[i], kWingNames[i]));
			return false;
		}
		// A section the world refuses to take back out makes SealedWingUntouched an
		// UNFAILABLE DEAD GATE and the whole coupling a permissive fake:
		// ULevelStreamingAlwaysLoaded::ShouldBeLoaded() is { return true; }.
		if (Found[i]->ShouldBeAlwaysLoaded())
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: section %s (%s wing) is staged as an ")
				TEXT("always-loaded section, so the world refuses to take it out and ")
				TEXT("the control the whole task rests on cannot fail"),
				kSectionIds[i], kWingNames[i]));
			return false;
		}
	}
	for (int32 i = 0; i < 4; ++i)
	{
		for (int32 j = i + 1; j < 4; ++j)
		{
			if (Found[i] == Found[j])
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: sections %s and %s resolve to the ")
					TEXT("same streaming section, so two wings share one package and ")
					TEXT("neither can be opened without the other"),
					kSectionIds[i], kSectionIds[j]));
				return false;
			}
		}
	}
	return true;
}

bool AWingHostFunctionalTest::ResolveHostFurniture(UWorld* World)
{
	// NOTHING HERE FAILS THE TEST. A missing or moved mark, post or board is something
	// a submission CAN cause (BeginPlay runs before PrepareTest), so it is left for
	// SealedWingUntouched to report by name at cp0. This function only decides which
	// placed actor occupies which slot in the layout table.
	TArray<AActor*> FoundMarks, FoundPosts, FoundBoards;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CallMark")), FoundMarks);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("WingPost")), FoundPosts);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("GateBoard")), FoundBoards);

	auto NearestTo = [](const TArray<AActor*>& Pool, const FVector2D& At) -> AActor*
	{
		AActor* Best = nullptr;
		double BestDist = TNumericLimits<double>::Max();
		for (AActor* A : Pool)
		{
			if (A == nullptr)
			{
				continue;
			}
			const FVector P = A->GetActorLocation();
			const double D = FVector2D::Distance(FVector2D(P.X, P.Y), At);
			if (D < BestDist)
			{
				BestDist = D;
				Best = A;
			}
		}
		return (BestDist <= kMatchRadiusCm) ? Best : nullptr;
	};

	for (int32 i = 0; i < 3; ++i)
	{
		Marks[i] = NearestTo(FoundMarks, kMarkAt[i]);
	}
	for (int32 i = 0; i < 4; ++i)
	{
		Posts[i] = NearestTo(FoundPosts, kPostAt[i]);
	}
	Board = NearestTo(FoundBoards, kBoardAt);

	UE_LOG(LogTemp, Display,
		TEXT("[t2-wing-host staging] marks tagged=%d matched=%d/3; posts tagged=%d ")
		TEXT("matched=%d/4; boards tagged=%d matched=%d/1"),
		FoundMarks.Num(),
		(Marks[0].IsValid() ? 1 : 0) + (Marks[1].IsValid() ? 1 : 0)
			+ (Marks[2].IsValid() ? 1 : 0),
		FoundPosts.Num(),
		(Posts[0].IsValid() ? 1 : 0) + (Posts[1].IsValid() ? 1 : 0)
			+ (Posts[2].IsValid() ? 1 : 0) + (Posts[3].IsValid() ? 1 : 0),
		FoundBoards.Num(), Board.IsValid() ? 1 : 0);
	return true;
}

// ---------------------------------------------------------------------------
// The deal.
// ---------------------------------------------------------------------------

void AWingHostFunctionalTest::DealMarks(int32 InDealIndex)
{
	DealIndex = FMath::Clamp(InDealIndex, 0, 1);
	FString Line;
	for (int32 i = 0; i < 3; ++i)
	{
		const FName Wing(kDeal[LegIndex][DealIndex][i]);
		DealtWing[i] = Wing;

		AActor* const Mark = Marks[i].Get();
		if (Mark == nullptr)
		{
			// A mark a submission removed. The deal is still recorded, so
			// SealedWingUntouched reports the missing mark rather than the fixture
			// quietly grading against a different pairing.
			continue;
		}
		// Prefer the supplied switch, so the floating label a human reads repaints and
		// a submission that overrode it sees exactly what a person re-lettering the
		// mark would produce. Fall back to the property when the switch is gone.
		if (!CallNameFunction(Mark, TEXT("SetCalledWingName"), Wing))
		{
			WriteName(Mark, TEXT("CalledWingName"), Wing);
		}
		Line += FString::Printf(TEXT("%s->%s "), kMarkIds[i], *Wing.ToString());
	}
	UE_LOG(LogTemp, Display, TEXT("[t2-wing-host deal] leg=%d deal=%d : %s"),
		LegIndex, DealIndex, *Line);
}

// ---------------------------------------------------------------------------
// The observables. Identity is the per-instance tag baked into the committed wing
// package -- never a UPROPERTY on an agent-writable class, and never the class tag
// alone (a submission is free to edit its own constructor).
// ---------------------------------------------------------------------------

AWingHostFunctionalTest::FStandingFittings
AWingHostFunctionalTest::ReadStanding() const
{
	FStandingFittings Out;
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return Out;
	}
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* const A = *It;
		if (A == nullptr)
		{
			continue;
		}
		int32 Identities = 0;
		FName Identity = NAME_None;
		for (const FName& Tag : A->Tags)
		{
			if (Tag.ToString().StartsWith(TEXT("Fitting."), ESearchCase::CaseSensitive))
			{
				++Identities;
				Identity = Tag;
			}
		}
		if (Identities == 1)
		{
			Out.CountByTag.FindOrAdd(Identity) += 1;
			if (!Out.ActorByTag.Contains(Identity))
			{
				Out.ActorByTag.Add(Identity, A);
			}
		}
		else if (Identities > 1 || HasTag(A, TEXT("WingFitting")))
		{
			// Either a fitting standing in the host with no identity at all, or one
			// carrying two -- both mean the host holds something nobody can name.
			++Out.Unidentified;
		}
	}
	return Out;
}

TArray<FName> AWingHostFunctionalTest::ExpectedTagsAt(EWingGauge Gauge) const
{
	TArray<FName> Out;
	for (int32 n = 1; n <= kHallFittings; ++n)
	{
		Out.Add(FittingTag(FName(kWingNames[0]), n));   // the hall, always
	}
	if (Gauge != EWingGauge::Cp0 && !ExpectedWing.IsNone())
	{
		// EACH WING IS ITS OWN SIZE. The multiset is exact, so a submission that opens
		// the right wing still has to bring ALL of it in.
		const int32 Wanted = FittingsForWing(ExpectedWing);
		for (int32 n = 1; n <= Wanted; ++n)
		{
			Out.Add(FittingTag(ExpectedWing, n));
		}
	}
	Out.Sort(FNameLexicalLess());
	return Out;
}

FString AWingHostFunctionalTest::DescribeTags(const TArray<FName>& Tags)
{
	TArray<FString> Parts;
	for (const FName& T : Tags)
	{
		Parts.Add(T.ToString());
	}
	Parts.Sort();
	return Parts.Num() > 0 ? FString::Join(Parts, TEXT(", ")) : FString(TEXT("nothing"));
}

FString AWingHostFunctionalTest::DescribeStanding(const FStandingFittings& Standing)
{
	TArray<FString> Parts;
	for (const TPair<FName, int32>& Pair : Standing.CountByTag)
	{
		Parts.Add(Pair.Value > 1
			? FString::Printf(TEXT("%s x%d"), *Pair.Key.ToString(), Pair.Value)
			: Pair.Key.ToString());
	}
	if (Standing.Unidentified > 0)
	{
		Parts.Add(FString::Printf(TEXT("%d unnamed fitting(s)"), Standing.Unidentified));
	}
	Parts.Sort();
	return Parts.Num() > 0 ? FString::Join(Parts, TEXT(", ")) : FString(TEXT("nothing"));
}

bool AWingHostFunctionalTest::FittingIsSolidAndSeen(const AActor* Fitting,
	FString& OutWhy) const
{
	if (Fitting == nullptr)
	{
		OutWhy = TEXT("it is not in the host at all");
		return false;
	}
	if (Fitting->IsHidden())
	{
		OutWhy = TEXT("the whole fitting is hidden in game");
		return false;
	}

	// The graded part is resolved by the same prefer-the-declared-thing-then-a-
	// deterministic-rule idiom the rest of the tree uses: the component named
	// "Column" if present, else the largest by local bounds, ties by name ascending.
	// Never enumeration order.
	TArray<UStaticMeshComponent*> Meshes;
	const_cast<AActor*>(Fitting)->GetComponents<UStaticMeshComponent>(Meshes);
	if (Meshes.Num() == 0)
	{
		OutWhy = TEXT("it carries nothing anybody could see or walk into");
		return false;
	}
	UStaticMeshComponent* Column = nullptr;
	for (UStaticMeshComponent* M : Meshes)
	{
		if (M != nullptr && M->GetName() == TEXT("Column"))
		{
			Column = M;
			break;
		}
	}
	if (Column == nullptr)
	{
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
		Column = Meshes[0];
	}
	if (Column == nullptr || Column->GetStaticMesh() == nullptr)
	{
		OutWhy = TEXT("its column has no shape to show");
		return false;
	}
	if (Column->bHiddenInGame || !Column->IsVisible())
	{
		OutWhy = TEXT("its column is hidden in game");
		return false;
	}
	const ECollisionEnabled::Type Mode = Column->GetCollisionEnabled();
	if (Mode != ECollisionEnabled::QueryOnly && Mode != ECollisionEnabled::QueryAndPhysics)
	{
		OutWhy = TEXT("nothing can walk into it (its column answers no collision query)");
		return false;
	}
	if (Column->GetCollisionResponseToChannel(ECC_Pawn) != ECR_Block)
	{
		OutWhy = TEXT("nothing can walk into it (its column does not block a pawn)");
		return false;
	}
	OutWhy.Reset();
	return true;
}

FString AWingHostFunctionalTest::ReadBoardLine() const
{
	AActor* const B = Board.Get();
	if (B == nullptr)
	{
		return FString();
	}
	TArray<UTextRenderComponent*> Texts;
	B->GetComponents<UTextRenderComponent>(Texts);
	if (Texts.Num() == 0)
	{
		return FString();
	}
	UTextRenderComponent* Chosen = nullptr;
	for (UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetName() == TEXT("Line"))
		{
			Chosen = T;
			break;
		}
	}
	if (Chosen == nullptr)
	{
		Texts.Sort([](const UTextRenderComponent& A, const UTextRenderComponent& B2)
		{
			if (!FMath::IsNearlyEqual(A.WorldSize, B2.WorldSize, 0.01f))
			{
				return A.WorldSize > B2.WorldSize;
			}
			return A.GetName() < B2.GetName();
		});
		Chosen = Texts[0];
	}
	// The RENDERED text, off the component -- never a flag, and never the actor's own
	// opinion of what it reported.
	return Chosen != nullptr ? Chosen->Text.ToString() : FString();
}

// ---------------------------------------------------------------------------
// The gates, in the precedence order task.md fixes. At most one of 1..3 fires on any
// gauge point, so a named FAIL is never a race between two of them; 4 and 5 are
// independent channels and run last.
// ---------------------------------------------------------------------------

bool AWingHostFunctionalTest::GateCalledWingOpens(EWingGauge Gauge,
	const FStandingFittings& Standing)
{
	if (Gauge == EWingGauge::Cp0 || ExpectedWing.IsNone())
	{
		return true;   // nothing has been called; there is nothing to open
	}
	const int32 Wanted = FittingsForWing(ExpectedWing);
	int32 Present = 0;
	for (int32 n = 1; n <= Wanted; ++n)
	{
		if (Standing.CountByTag.Contains(FittingTag(ExpectedWing, n)))
		{
			++Present;
		}
	}
	if (Wanted > 0 && Present >= Wanted)
	{
		return true;
	}
	const TCHAR* const MarkId = (SteppedMarkIndex >= 0 && SteppedMarkIndex < 3)
		? kMarkIds[SteppedMarkIndex] : TEXT("?");
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("CalledWingOpens: mark %s showed %s at the step; %d of %d %s fittings ")
		TEXT("stand in the host at %s"),
		MarkId, *ExpectedWing.ToString(), Present, Wanted,
		*ExpectedWing.ToString(), GaugeName(Gauge)));
	return false;
}

bool AWingHostFunctionalTest::GateOnlyCalledWingPresent(EWingGauge Gauge,
	const FStandingFittings& Standing)
{
	const TArray<FName> Expected = ExpectedTagsAt(Gauge);

	bool bMatches = (Standing.Unidentified == 0);
	if (bMatches)
	{
		int32 Total = 0;
		for (const TPair<FName, int32>& Pair : Standing.CountByTag)
		{
			Total += Pair.Value;
			if (Pair.Value != 1 || !Expected.Contains(Pair.Key))
			{
				bMatches = false;
				break;
			}
		}
		bMatches = bMatches && (Total == Expected.Num());
	}
	if (bMatches)
	{
		return true;
	}
	// One gate, three wrong answers: load-without-unload (six called fittings),
	// open-everything, and any SLATE fitting ever appearing -- GAMMA is never stepped
	// on, so a slate fitting in the host is a wing nobody called.
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("OnlyCalledWingPresent: at %s the host should hold exactly [%s] and it ")
		TEXT("holds [%s]"),
		GaugeName(Gauge), *DescribeTags(Expected), *DescribeStanding(Standing)));
	return false;
}

bool AWingHostFunctionalTest::GateSealedWingUntouched(EWingGauge Gauge,
	const FStandingFittings& Standing)
{
	const TCHAR* const Where = GaugeName(Gauge);

	// (a) THE HALL -- the matched twin. Built from the same fitting class, standing in
	//     the same host, streamed exactly like the other three, and indistinguishable
	//     from a callable wing to any "clear everything, then load the target" loop.
	for (int32 n = 1; n <= kHallFittings; ++n)
	{
		const FName Tag = FittingTag(FName(kWingNames[0]), n);
		const TWeakObjectPtr<AActor>* const Slot = Standing.ActorByTag.Find(Tag);
		AActor* const A = (Slot != nullptr) ? Slot->Get() : nullptr;
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: hall fitting HALL.%d absent from the host ")
				TEXT("at %s (no mark ever calls the hall and nothing may disturb it)"),
				n, Where));
			return false;
		}
		const double Moved = FVector::Dist(A->GetActorLocation(), kHallFittingAt[n - 1]);
		if (Moved > kHallMoveCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: hall fitting HALL.%d is %.1f uu from where ")
				TEXT("the level stands it, at %s"), n, Moved, Where));
			return false;
		}
		FString Why;
		if (!FittingIsSolidAndSeen(A, Why))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: hall fitting HALL.%d is standing at %s but ")
				TEXT("%s"), n, Where, *Why));
			return false;
		}
	}

	// (b) THE HOST'S FIXED FURNITURE. Graded rather than attributed, deliberately: an
	//     attributed exit a submission can trigger is a free way out of the denominator.
	for (int32 i = 0; i < 3; ++i)
	{
		AActor* const M = Marks[i].Get();
		if (M == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the call mark the level set into the floor ")
				TEXT("at (%.0f, %.0f) is missing from the host at %s"),
				kMarkAt[i].X, kMarkAt[i].Y, Where));
			return false;
		}
		const FVector P = M->GetActorLocation();
		const double Moved = FVector2D::Distance(FVector2D(P.X, P.Y), kMarkAt[i]);
		if (Moved > kFurnitureMoveCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the mark %s has moved %.1f uu from where ")
				TEXT("the level put it, at %s"), kMarkIds[i], Moved, Where));
			return false;
		}
		bool bOk = false;
		const FName Id = ReadName(M, TEXT("MarkId"), bOk);
		if (!bOk || Id != FName(kMarkIds[i]))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the mark the level named %s now reads '%s' ")
				TEXT("at %s"), kMarkIds[i], *Id.ToString(), Where));
			return false;
		}
		// The mark's CURRENT label is excluded from the do-not-rewrite rule and checked
		// against the fixture's OWN deal instead: the fixture re-letters the marks, and
		// only the fixture may.
		const FName Showing = ReadName(M, TEXT("CalledWingName"), bOk);
		if (!bOk || Showing != DealtWing[i])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the mark %s is showing '%s' at %s and the ")
				TEXT("level last lettered it %s"),
				kMarkIds[i], *Showing.ToString(), Where, *DealtWing[i].ToString()));
			return false;
		}
	}
	for (int32 i = 0; i < 4; ++i)
	{
		AActor* const P = Posts[i].Get();
		if (P == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the post at the %s wing's mouth is missing ")
				TEXT("from the host at %s"), kWingNames[i], Where));
			return false;
		}
		const FVector At = P->GetActorLocation();
		const double Moved = FVector2D::Distance(FVector2D(At.X, At.Y), kPostAt[i]);
		if (Moved > kFurnitureMoveCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the %s post has moved %.1f uu from where ")
				TEXT("the level put it, at %s"), kWingNames[i], Moved, Where));
			return false;
		}
		bool bOk = false;
		const FName WingName = ReadName(P, TEXT("WingName"), bOk);
		if (!bOk || WingName != FName(kWingNames[i]))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the post the level named %s now carries the ")
				TEXT("name '%s' at %s"), kWingNames[i], *WingName.ToString(), Where));
			return false;
		}
		const FName Section = ReadName(P, TEXT("SectionId"), bOk);
		if (!bOk || Section != FName(kSectionIds[i]))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the %s post should point at %s and it ")
				TEXT("points at '%s' at %s"),
				kWingNames[i], kSectionIds[i], *Section.ToString(), Where));
			return false;
		}
	}
	{
		AActor* const B = Board.Get();
		if (B == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the board over the host gate is missing ")
				TEXT("from the host at %s"), Where));
			return false;
		}
		const FVector At = B->GetActorLocation();
		const double Moved = FVector2D::Distance(FVector2D(At.X, At.Y), kBoardAt);
		if (Moved > kFurnitureMoveCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: the gate board has moved %.1f uu from ")
				TEXT("where the level put it, at %s"), Moved, Where));
			return false;
		}
	}
	return true;
}

bool AWingHostFunctionalTest::GateOpenWingIsSolidAndSeen(EWingGauge Gauge,
	const FStandingFittings& Standing)
{
	if (Gauge == EWingGauge::Cp0 || ExpectedWing.IsNone())
	{
		return true;
	}
	const int32 Wanted = FittingsForWing(ExpectedWing);
	for (int32 n = 1; n <= Wanted; ++n)
	{
		const FName Tag = FittingTag(ExpectedWing, n);
		const TWeakObjectPtr<AActor>* const Slot = Standing.ActorByTag.Find(Tag);
		AActor* const A = (Slot != nullptr) ? Slot->Get() : nullptr;
		if (A == nullptr)
		{
			continue;   // absence is CalledWingOpens' business, and it ran first
		}
		FString Why;
		if (!FittingIsSolidAndSeen(A, Why))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("OpenWingIsSolidAndSeen: fitting %s.%d stands in the host at %s ")
				TEXT("but %s"), *ExpectedWing.ToString(), n, GaugeName(Gauge), *Why));
			return false;
		}
	}
	return true;
}

bool AWingHostFunctionalTest::GateBoardNamesTheOpenWing(EWingGauge Gauge,
	const FStandingFittings& Standing)
{
	// The EXPECTED line, derived from the stepped mark's label AT THE STEP -- never
	// from what the submission actually opened. Asserting against the expected value
	// rather than the submission's own belief is what keeps this independent of
	// CalledWingOpens: an implementation that opens the wrong wing and reports it
	// consistently still fails here.
	//
	// BOTH HALVES OF THE LINE ARE LOAD-BEARING. The number is that wing's own size,
	// and no size appears in the prompt: the wings hold 3/4/6/4 and the deals are
	// mirrored, so a CONSTANT is wrong at cp1 or cp2 of BOTH legs, and the count a
	// submission takes inside the step handler is the count of a wing that has not
	// arrived yet -- it reads 0 and stays there. Until 2026-08-19 every wing held
	// three and this gate demanded the literal '<WING> 3' everywhere, which made
	// 'count what is standing' unobservable BY CONSTRUCTION rather than merely
	// unpunished. Nothing here grades a sub-second transient: the gauge point is at
	// the CLOSE of the disclosed window, and a board that has caught up by then
	// passes however it got there.
	const FString Expected = (Gauge == EWingGauge::Cp0 || ExpectedWing.IsNone())
		? FString(TEXT("NONE 0"))
		: FString::Printf(TEXT("%s %d"), *ExpectedWing.ToString().ToUpper(),
								FittingsForWing(ExpectedWing));

	const FString Found = ReadBoardLine();
	if (Found.Equals(Expected, ESearchCase::CaseSensitive))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("BoardNamesTheOpenWing: the board should read '%s' at %s and it reads ")
		TEXT("'%s'"), *Expected, GaugeName(Gauge), *Found));
	return false;
}

bool AWingHostFunctionalTest::Gauge(EWingGauge InGauge, double Now)
{
	const FStandingFittings Standing = ReadStanding();
	LastGauge = InGauge;
	LastGaugeName = GaugeName(InGauge);

	UE_LOG(LogTemp, Display,
		TEXT("[t2-wing-host gauge] %s t=%.2f leg=%d deal=%d expect=%s board='%s' ")
		TEXT("standing=[%s]"),
		GaugeName(InGauge), Now, LegIndex, DealIndex,
		ExpectedWing.IsNone() ? TEXT("nothing") : *ExpectedWing.ToString(),
		*ReadBoardLine(), *DescribeStanding(Standing));

	if (!GateCalledWingOpens(InGauge, Standing)) { return false; }
	if (!GateOnlyCalledWingPresent(InGauge, Standing)) { return false; }
	if (!GateSealedWingUntouched(InGauge, Standing)) { return false; }
	if (!GateOpenWingIsSolidAndSeen(InGauge, Standing)) { return false; }
	if (!GateBoardNamesTheOpenWing(InGauge, Standing)) { return false; }
	return true;
}

bool AWingHostFunctionalTest::RecheckStallableGates(const TCHAR* Where)
{
	// A HARNESS EXIT CAN NEVER LAUNDER A FAIL. These are the gates a submission can
	// trip while ALSO stalling the drive -- a fitting standing where it should not be
	// is solid, and solid things block a walk -- so that path is closed explicitly
	// rather than by luck.
	//
	// AND IT MUST NEVER MANUFACTURE ONE. The CHECKPOINT form of OnlyCalledWingPresent
	// compares against the wing the LAST GAUGE POINT expected, and a stall can strand
	// the character mid-approach: past the ENGINE's own begin-overlap (about 152 uu,
	// where a correct submission has ALREADY swapped the new wing in and the previous
	// one out) and short of the 45 uu at which this fixture calls the step landed.
	// Re-using the stale expectation across that window would name a gate against
	// correct work -- a mechanism that can only ever invent a FAIL, which is the exact
	// opposite of why this re-check exists. So the stall form asks the weaker question
	// that is still true in that window: the hall, plus the COMPLETE fitting set of AT
	// MOST ONE called wing, and that wing must be either the one the last gauge point
	// expected or the one lettered on a mark the character is already close enough to
	// have triggered. Everything a stalling submission can actually be caught by --
	// two wings at once, a duplicate, an unnamed fitting, slate, a missing or moved
	// hall, moved or renamed furniture -- still fails here, by name.
	const FStandingFittings Standing = ReadStanding();
	UE_LOG(LogTemp, Display,
		TEXT("[t2-wing-host stall] re-checking the stallable gates at %s; ")
		TEXT("standing=[%s]"), Where, *DescribeStanding(Standing));

	// SealedWingUntouched is expectation-independent -- the hall, the host's fixed
	// furniture, and the labels the fixture itself dealt -- so it is re-checked whole.
	if (!GateSealedWingUntouched(LastGauge, Standing)) { return false; }

	TArray<FName> Candidates;
	if (!ExpectedWing.IsNone())
	{
		Candidates.AddUnique(ExpectedWing);
	}
	for (int32 i = 0; i < 3; ++i)
	{
		if (DistanceToMark(i) <= kStallReachCm && !DealtWing[i].IsNone())
		{
			Candidates.AddUnique(DealtWing[i]);
		}
	}

	auto HallPlus = [](FName Wing) -> TArray<FName>
	{
		TArray<FName> Out;
		for (int32 n = 1; n <= kHallFittings; ++n)
		{
			Out.Add(FittingTag(FName(kWingNames[0]), n));
		}
		const int32 Wanted = FittingsForWing(Wing);
		for (int32 n = 1; n <= Wanted; ++n)
		{
			Out.Add(FittingTag(Wing, n));
		}
		return Out;
	};
	auto Matches = [&Standing](const TArray<FName>& Expected) -> bool
	{
		if (Standing.Unidentified != 0)
		{
			return false;
		}
		int32 Total = 0;
		for (const TPair<FName, int32>& Pair : Standing.CountByTag)
		{
			Total += Pair.Value;
			if (Pair.Value != 1 || !Expected.Contains(Pair.Key))
			{
				return false;
			}
		}
		return Total == Expected.Num();
	};

	if (Matches(HallPlus(NAME_None)))
	{
		return true;   // the hall alone, nothing called: always legitimate
	}
	TArray<FString> Named;
	for (const FName& Wing : Candidates)
	{
		if (Matches(HallPlus(Wing)))
		{
			return true;
		}
		Named.Add(Wing.ToString());
	}
	const FString Which = Named.Num() > 0
		? FString::Join(Named, TEXT(" or "))
		: FString(TEXT("none -- nothing had been called"));
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("OnlyCalledWingPresent: the walk to %s stalled, and the host should ")
		TEXT("hold the hall plus at most one called wing (%s) and it holds [%s]"),
		Where, *Which, *DescribeStanding(Standing)));
	return false;
}

bool AWingHostFunctionalTest::GuardControlsContinuously()
{
	// THE IN-SCENE NEGATIVE CONTROL, every frame rather than only at gauge points.
	// A correct answer never touches the hall or the furniture, so this can only ever
	// catch a wrong one -- and it is the only thing that catches a hall taken out and
	// put back INSIDE a settle window, which every checkpoint-only sample would miss.
	// Armed only once cp0 has been sampled, so nothing is judged before the run has a
	// reported baseline.
	if (!bCp0Sampled)
	{
		return true;
	}
	const FStandingFittings Standing = ReadStanding();
	for (int32 n = 1; n <= kHallFittings; ++n)
	{
		const FName Tag = FittingTag(FName(kWingNames[0]), n);
		const TWeakObjectPtr<AActor>* const Slot = Standing.ActorByTag.Find(Tag);
		AActor* const A = (Slot != nullptr) ? Slot->Get() : nullptr;
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: hall fitting HALL.%d left the host between ")
				TEXT("%s and the next gauge point; the hall is open when play begins ")
				TEXT("and stays open all night"), n, *LastGaugeName));
			return false;
		}
		const double Moved = FVector::Dist(A->GetActorLocation(), kHallFittingAt[n - 1]);
		if (Moved > kHallMoveCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SealedWingUntouched: hall fitting HALL.%d moved %.1f uu from ")
				TEXT("where the level stands it, after %s"), n, Moved, *LastGaugeName));
			return false;
		}
	}
	return true;
}

// ---------------------------------------------------------------------------
// The drive. Tier-1 throughout: locomotion into a thing, driven by the shipping
// per-frame AddMovementInput timeline -- the same path a human drives with WASD. No
// key is ever synthesised and no behaviour is ever invoked by calling into the
// submission.
// ---------------------------------------------------------------------------

double AWingHostFunctionalTest::DistanceToMark(int32 MarkIndex) const
{
	if (!Hero.IsValid() || MarkIndex < 0 || MarkIndex >= 3)
	{
		return TNumericLimits<double>::Max();
	}
	const FVector H = Hero->GetActorLocation();
	return FVector2D::Distance(FVector2D(H.X, H.Y), kMarkAt[MarkIndex]);
}

double AWingHostFunctionalTest::NearestMarkDistance() const
{
	double Best = TNumericLimits<double>::Max();
	for (int32 i = 0; i < 3; ++i)
	{
		Best = FMath::Min(Best, DistanceToMark(i));
	}
	return Best;
}

bool AWingHostFunctionalTest::DriveTo(const FVector& Target)
{
	ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		return false;
	}
	const FVector Here = H->GetActorLocation();
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	const double Dist = Flat.Size2D();

	const UCharacterMovementComponent* const CMC = H->GetCharacterMovement();
	const bool bGrounded = (CMC == nullptr) || !CMC->IsFalling();

	if (Dist <= kArriveCm && bGrounded)
	{
		return true;
	}
	// Ease off the stick on approach. Movement input is consumed per frame, so it is
	// re-applied every tick.
	const float Scale = (Dist > kRampFarCm) ? kFullScale
		: (Dist > kRampNearCm) ? kRampFarScale : kRampNearScale;
	H->AddMovementInput(Flat.GetSafeNormal(), Scale);
	return false;
}

void AWingHostFunctionalTest::BeginWalk(const FVector& Target, const TCHAR* What,
	double Now)
{
	WalkTarget = Target;
	PhaseWhat = What;
	const FVector Here = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	const double Dist = FVector2D::Distance(
		FVector2D(Here.X, Here.Y), FVector2D(Target.X, Target.Y));
	// Derived from the MEASURED distance and the MEASURED pace, never written down.
	PhaseDeadline = Now + Dist / FMath::Max(HeroSpeed, 1.0) * kDeadlineSlack
		+ kDeadlineFloorS;
}

void AWingHostFunctionalTest::BeginStand(EWingPhase NextPhase, int32 SteppedMark,
	double Now)
{
	Phase = NextPhase;
	SteppedMarkIndex = SteppedMark;
	// THE GRADE COMES FROM THE FIXTURE'S OWN DEAL TABLE, never from a read-back of the
	// mark: by construction those are the same name, and SealedWingUntouched proves
	// they still are.
	ExpectedWing = DealtWing[SteppedMark];
	StepLandedAt = Now;
	UE_LOG(LogTemp, Display,
		TEXT("[t2-wing-host step] t=%.2f landed on %s, which the level letters %s"),
		Now, kMarkIds[SteppedMark], *ExpectedWing.ToString());
}

void AWingHostFunctionalTest::LogCalib(int32 CheckpointIndex, double Now) const
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t2-wing-host calib] cp%d t=%.2f phase=%d hero=(%.0f,%.0f) ")
		TEXT("nearestMark=%.0f expect=%s board='%s'"),
		CheckpointIndex, Now, static_cast<int32>(Phase), H.X, H.Y,
		NearestMarkDistance(),
		ExpectedWing.IsNone() ? TEXT("nothing") : *ExpectedWing.ToString(),
		*ReadBoardLine());
}

// ---------------------------------------------------------------------------

void AWingHostFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}

	// Identity by POSSESSION for the character (the level names NO game mode, so the
	// project default spawns the stock pawn at the PlayerStart), by TAG for everything
	// placed.
	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no possessed player character in the host"));
		return;
	}

	// This fixture drives the character through AddMovementInput and never presses a
	// key, so a level whose keyboard lane is dead grades exactly like a healthy one.
	// Five of six ThirdPerson maps once shipped visible, animated and completely
	// uncontrollable. Substrate, never anything the agent was asked to write.
	if (const FString Unwired = DescribeBrokenPlayerInput(World); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. The ")
			TEXT("graded drive would still pass, so fix the substrate, not the task."),
			*Unwired));
		return;
	}

	if (!CheckSectionsAreStagedForStreaming(World))
	{
		return;
	}
	if (!ResolveHostFurniture(World))
	{
		return;
	}

	if (const UCharacterMovementComponent* const CMC = Hero->GetCharacterMovement())
	{
		HeroSpeed = FMath::Max<double>(CMC->GetMaxSpeed(), 1.0);
	}

	// WHICH LEG THIS IS, from the leg's own fixed delta time. The runner's -FPS sets it
	// (LaunchEngineLoop.cpp:4727); it is never wall clock and never random, so the same
	// input gives the same deal every run.
	const double Dt = FApp::GetFixedDeltaTime();
	LegIndex = (Dt > kSlowLegDtS) ? 1 : 0;
	UE_LOG(LogTemp, Display,
		TEXT("[t2-wing-host] fixed dt=%.5f s -> leg %d (%s); hero pace %.0f uu/s"),
		Dt, LegIndex, LegIndex == 0 ? TEXT("fast") : TEXT("slow"), HeroSpeed);

	DealMarks(0);

	Phase = EWingPhase::Settle;
	bCp0Sampled = false;
	bDriveComplete = false;
	ExpectedWing = NAME_None;
	SteppedMarkIndex = -1;
	StepLandedAt = -1.0;
	ReletteredAt = -1.0;

	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelAtS);
	SetCheckpointSchedule(Schedule);
	bPrepared = true;
}

void AWingHostFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);   // base first: checkpoint clock + timeout machinery

	if (!IsRunning() || !bPrepared || !Hero.IsValid())
	{
		return;
	}
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();

	// The continuous control guard runs BEFORE the drive, so a hall lost inside a
	// settle window is caught in the frame it happens.
	if (!GuardControlsContinuously())
	{
		return;
	}

	switch (Phase)
	{
	case EWingPhase::Settle:
		if (Now >= kBaselineAtS)
		{
			if (!Gauge(EWingGauge::Cp0, Now)) { return; }
			bCp0Sampled = true;
			Phase = EWingPhase::ToAlpha1;
			BeginWalk(FVector(kMarkAt[0].X, kMarkAt[0].Y, 0.0), TEXT("ALPHA (1st)"), Now);
		}
		break;

	case EWingPhase::ToAlpha1:
	case EWingPhase::ToAlpha2:
	case EWingPhase::ToAlpha3:
	case EWingPhase::ToBeta1:
	case EWingPhase::ToBeta2:
	case EWingPhase::ToBeta3:
	{
		const int32 TargetMark =
			(Phase == EWingPhase::ToBeta1 || Phase == EWingPhase::ToBeta2
				|| Phase == EWingPhase::ToBeta3) ? 1 : 0;
		if (DriveTo(WalkTarget))
		{
			switch (Phase)
			{
			case EWingPhase::ToAlpha1: BeginStand(EWingPhase::StandAlpha1, 0, Now); break;
			case EWingPhase::ToBeta1:  BeginStand(EWingPhase::StandBeta1, 1, Now); break;
			case EWingPhase::ToAlpha2: BeginStand(EWingPhase::StandAlpha2, 0, Now); break;
			case EWingPhase::ToAlpha3: BeginStand(EWingPhase::StandAlpha3, 0, Now); break;
			case EWingPhase::ToBeta2:  BeginStand(EWingPhase::StandBeta2, 1, Now); break;
			case EWingPhase::ToBeta3:  BeginStand(EWingPhase::StandBeta3, 1, Now); break;
			default: break;
			}
		}
		else if (Now > PhaseDeadline)
		{
			if (!RecheckStallableGates(*PhaseWhat)) { return; }
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive could not reach %s (%.0f uu ")
				TEXT("away at t=%.2f) with every gate a submission could stall it ")
				TEXT("with green; the walk is the fixture's own"),
				*PhaseWhat, DistanceToMark(TargetMark), Now));
			return;
		}
		break;
	}

	case EWingPhase::StandAlpha1:
	case EWingPhase::StandBeta1:
	case EWingPhase::StandAlpha2:
	case EWingPhase::StandAlpha3:
	case EWingPhase::StandBeta2:
	case EWingPhase::StandBeta3:
	{
		// No input: the character brakes and settles on the plate. The gate is
		// evaluated at the CLOSE of the disclosed second, never during it.
		if (Now - StepLandedAt < kSettleS)
		{
			break;
		}
		switch (Phase)
		{
		case EWingPhase::StandAlpha1:
			if (!Gauge(EWingGauge::Cp1, Now)) { return; }
			Phase = EWingPhase::ToBeta1;
			BeginWalk(FVector(kMarkAt[1].X, kMarkAt[1].Y, 0.0), TEXT("BETA (1st)"), Now);
			break;
		case EWingPhase::StandBeta1:
			if (!Gauge(EWingGauge::Cp2, Now)) { return; }
			Phase = EWingPhase::ToAlpha2;
			BeginWalk(FVector(kMarkAt[0].X, kMarkAt[0].Y, 0.0), TEXT("ALPHA (2nd)"), Now);
			break;
		case EWingPhase::StandAlpha2:
			// THE RE-TRIGGER: same mark, same deal, and the gates have just demanded
			// the same measured outcome as cp1.
			if (!Gauge(EWingGauge::Cp3, Now)) { return; }
			Phase = EWingPhase::ToClear;
			BeginWalk(FVector(kClearSpot.X, kClearSpot.Y, 0.0),
				TEXT("the clear ground below ALPHA"), Now);
			break;
		case EWingPhase::StandAlpha3:
			if (!Gauge(EWingGauge::Cp4, Now)) { return; }
			Phase = EWingPhase::ToBeta2;
			BeginWalk(FVector(kMarkAt[1].X, kMarkAt[1].Y, 0.0), TEXT("BETA (2nd)"), Now);
			break;
		case EWingPhase::StandBeta2:
			if (!Gauge(EWingGauge::Cp5, Now)) { return; }
			Phase = EWingPhase::ToStepOff;
			BeginWalk(FVector(kStepOffAt.X, kStepOffAt.Y, 0.0),
				TEXT("the clear ground below BETA"), Now);
			break;
		case EWingPhase::StandBeta3:
			// THE SAME-MARK RE-STEP. BETA has not been re-lettered since cp5, so this
			// step calls the wing that is ALREADY standing and the demanded outcome is
			// cp5's, UNCHANGED. It is the only gauge point at which a take-down and a
			// bring-in issued against one shared handle can present: every other step
			// in the drive is a change of wing, where that slip is invisible because
			// the two calls name different sections.
			if (!Gauge(EWingGauge::Cp6, Now)) { return; }
			Phase = EWingPhase::Done;
			break;
		default:
			break;
		}
		break;
	}

	case EWingPhase::ToClear:
		if (DriveTo(WalkTarget) && NearestMarkDistance() >= kClearOfMarkCm)
		{
			// EVENT-DRIVEN, never a clock: the re-deal fires after cp3 has been sampled
			// and while the character overlaps no mark, so a re-letter can never land
			// during a step and manufacture a FAIL on correct work.
			DealMarks(1);
			ReletteredAt = Now;
			Phase = EWingPhase::Reletter;
		}
		else if (Now > PhaseDeadline)
		{
			if (!RecheckStallableGates(*PhaseWhat)) { return; }
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive could not reach %s at t=%.2f ")
				TEXT("with every gate a submission could stall it with green"),
				*PhaseWhat, Now));
			return;
		}
		break;

	case EWingPhase::ToStepOff:
		if (DriveTo(WalkTarget) && NearestMarkDistance() >= kClearOfMarkCm)
		{
			// Off the plate and well clear of every step volume, so the walk back is a
			// genuine second step onto BETA rather than an overlap that never ended.
			Phase = EWingPhase::ToBeta3;
			BeginWalk(FVector(kMarkAt[1].X, kMarkAt[1].Y, 0.0), TEXT("BETA (3rd)"), Now);
		}
		else if (Now > PhaseDeadline)
		{
			if (!RecheckStallableGates(*PhaseWhat)) { return; }
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the drive could not reach %s at t=%.2f ")
				TEXT("with every gate a submission could stall it with green"),
				*PhaseWhat, Now));
			return;
		}
		break;

	case EWingPhase::Reletter:
		if (Now - ReletteredAt >= kSettleS)
		{
			// RE-LETTERING IS NOT A CALL. The expectation here is cp3's, UNCHANGED, so
			// a submission that polls the label and swaps whenever it moves -- a
			// plausible reading of "read the mark, never assume a pairing" -- dies
			// here and nowhere else.
			if (!Gauge(EWingGauge::Cp3r, Now)) { return; }
			Phase = EWingPhase::ToAlpha3;
			BeginWalk(FVector(kMarkAt[0].X, kMarkAt[0].Y, 0.0), TEXT("ALPHA (3rd)"), Now);
		}
		break;

	case EWingPhase::Done:
		if (!bDriveComplete)
		{
			bDriveComplete = true;
			FinishTest(EFunctionalTestResult::Succeeded,
				TEXT("every called wing came in whole and the one before it went out ")
				TEXT("inside the disclosed window, the board counted what was actually ")
				TEXT("standing, re-stepping a mark already calling its wing changed ")
				TEXT("nothing, the hall never moved and slate never appeared"));
		}
		break;

	default:
		break;
	}
}

void AWingHostFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kGradedCheckpoints)
	{
		return;
	}
	// THE SENTINEL. The base class ends the test the moment the last scheduled
	// checkpoint is sampled, so the run-level verdict is settled here as well as when
	// the drive completes -- whichever comes first.
	if (bDriveComplete)
	{
		return;
	}
	if (!RecheckStallableGates(TEXT("the sentinel")))
	{
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the drive was still at phase %d at the sentinel ")
		TEXT("with every gate a submission could stall it with green; the host is ")
		TEXT("staged so the walk cannot finish, which is ours and not the ")
		TEXT("submission's"), static_cast<int32>(Phase)));
}
