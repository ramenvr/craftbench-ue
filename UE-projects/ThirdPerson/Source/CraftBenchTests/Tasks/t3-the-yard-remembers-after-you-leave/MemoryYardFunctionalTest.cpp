// Copyright CraftBench. All Rights Reserved.

#include "MemoryYardFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName kPostTag(TEXT("MemoryPost"));
	static const FName kPadTag(TEXT("MemoryPad"));
	static const FName kBoardTag(TEXT("MemoryBoard"));

	// ---- DISCLOSED IN THE PROMPT -------------------------------------------------
	// Every one of these appears in the agent-visible prose. Nothing below this line
	// is a private literal a submission could not have known about.
	constexpr int32 kWorthMin = 3;             // "a whole number between 3 and 17"
	constexpr int32 kWorthMax = 17;
	constexpr double kResumeRadiusUu = 150.0;  // "within 150 cm of the pad"

	// ---- UNDISCLOSED: fixture clocking and geometry ------------------------------
	// Sized from MEASURED substrate movement: AThirdPersonCharacter sets
	// MaxWalkSpeed = 500 and BrakingDecelerationWalking = 2000 (ThirdPersonCharacter.cpp
	// :33,35) -- NOT the engine defaults of 600 / 2048. A 1,050 uu perpendicular leg
	// therefore takes ~2.4 s including both ramps. Every window below was widened only
	// in the direction that cannot fail correct work.
	constexpr double kLaneBeforeS = 1.5;   // settle on the lane, then the pre-sample
	constexpr double kOnTargetS = 1.5;     // stand ON the post's ground / on the pad
	constexpr double kLaneAfterS = 1.5;    // settle clear of it, then the graded sample
	constexpr double kLaneReturnS = 0.8;   // walking off the pad the yard set you down on
	constexpr double kGateDwellS = 1.0;

	// THREE TIMES the one second the prompt allows, with NO movement input at all in
	// between -- the runner is put down on a pad by the submission's own code and must
	// not be walked off the thing it is about to be graded on.
	constexpr double kReopenHoldS = 3.0;
	// The rebuild frame itself plus a little: a teleport legitimately drops the
	// character into a fall for a frame or two, and RunnerKeepsWalking is about a
	// submission that took the controls away, not about that.
	constexpr double kRebuildGraceS = 0.5;

	constexpr double kWaypointUu = 70.0;
	// Tighter ONLY for the leg that steps onto the thing being measured. The post's
	// ground volume is 260 square (130 in half-extent) and the capsule radius is 42, so
	// a runner stopped 35 uu short of the stand point still overlaps the volume by
	// 37 uu; at 70 it would be touching the very edge. Nothing about this can widen a
	// gate -- it only makes the trigger fire reliably.
	constexpr double kOnTargetTolUu = 35.0;
	// Where the runner stands to take a post: 100 uu out from the post's origin toward
	// the lane. Deep inside the 260-square ground volume, and 28 uu clear of the
	// 60-square pillar's face, so a STANDING post is reachable without jamming.
	constexpr double kPostStandInsetUu = 100.0;
	constexpr double kGateOutUu = 650.0;

	constexpr double kMinPropClearanceUu = 250.0;
	constexpr double kMinBoardClearanceUu = 200.0;
	// Where a board stands after each rebuild, as an offset along its own row from where
	// the level put it. BOUNDED rather than cumulative: three rebuilds x a fixed step
	// would walk the far board through the far yard's east wall and off the floor.
	// Every value moves the board, no two are the same, and none crosses the dividing
	// wall. Guarded on top of that: a shift that would land near anything falls back to
	// standing still, so this can never wreck a walk.
	constexpr double kBoardShiftUu[] = { 550.0, 1100.0, 300.0 };

	// The whole day is three rebuilds and eleven walked steps now, so the schedule has
	// to outrun a walk of ~160 s with room for a slow one, without letting a stalled
	// run sit for an age before it reports itself.
	constexpr int32 kSentinelIndex = 78;
	constexpr double kSentinelAtS = 480.0;
	constexpr double kCheckpointEveryS = 6.0;

	/** Every property a gate reads or writes on a post. All of them live in the
	 *  agent's own file, so a missing one is a SCORED failure, never an Error. */
	const TCHAR* const kPostProps[] = { TEXT("WorthNow"), TEXT("LastShownWorth") };
	const TCHAR* const kPadProps[] = { TEXT("PadOrder") };
	const TCHAR* const kBoardProps[] = { TEXT("LastShownTotal") };
}

// ---------------------------------------------------------------------------
// THE THREE STAGED SETS
//
// Post indices are into the near yard SORTED BY THE NAME EACH POST CARRIES, so this
// table never spells an identity and the level owns them. On the committed map that
// order is Ash / Birch / Cedar / Dale / Elm, and the far yard's is Fern / Gorse / Hazel.
//
// THE SETS DIFFER IN SHAPE, NOT ONLY IN NUMBERS. Each one rebuilds the yard three times
// and does WARM, REWIND and COLD once each, in a different order -- so "the cold one is
// the second one", or any other answer that counts rebuilds instead of reading the
// record, is wrong in at least two sets out of three. Which set runs is taken from the
// clock unless -CraftBenchYardSeed= pins it (see ChooseSet), so it cannot be looked up
// in this file or in a published spec either.
//
// BuildDayTrace SIMULATES the script below rather than trusting any number written
// here, and refuses -- as an attributed HARNESS-PRECONDITION -- any set in which a
// naive answer would happen to produce the right reading.
// ---------------------------------------------------------------------------
void AMemoryYardFunctionalTest::ChooseSet()
{
	using S = EStep;
	constexpr int32 W = int32(ERebuild::Warm);
	constexpr int32 R = int32(ERebuild::Rewind);
	constexpr int32 C = int32(ERebuild::Cold);

	static const FStagedSet kSets[] =
	{
		// ---- set 0 -- rebuilds: WARM, REWIND, COLD -------------------------------
		// open  Ash 5 Birch 12 Cedar 7 Dale 16 Elm 9 | Fern 4 Gorse 11 Hazel 14
		//   pad 3 ; take Birch (12) -> 12  << the record is copied here >>
		//   take Dale (16) -> 28 ; pad 2 ; take Ash (5) -> 33
		// WARM  Ash 14 Birch 3 Cedar 11 Dale 6 Elm 17 | Fern 9 Gorse 5 Hazel 12
		//   must reopen: Ash/Birch/Dale gone, board 33, pad 2
		//   (recompute 23, all five 51, count 3, never-visited 0 -- all different)
		//   walk back through Dale's ground ; take Cedar (11) -> 44 ; pad 1
		// REWIND Ash 8 Birch 15 Cedar 4 Dale 13 Elm 6 | Fern 16 Gorse 7 Hazel 3
		//   must reopen ON THE COPY: only Birch gone, board 12, pad 3
		//   (a yard reading anything warm shows 44 with four posts gone on pad 1)
		//   take Dale (13) -> 25 ; pad 2
		// COLD  Ash 7 Birch 10 Cedar 3 Dale 5 Elm 16 | Fern 13 Gorse 17 Hazel 4
		//   must reopen never-visited: all five standing, board 0, pad 1
		//   take Elm (16) -> 16
		{
			{
				{ {  5, 12,  7, 16,  9 }, {  4, 11, 14 } },
				{ { 14,  3, 11,  6, 17 }, {  9,  5, 12 } },
				{ {  8, 15,  4, 13,  6 }, { 16,  7,  3 } },
				{ {  7, 10,  3,  5, 16 }, { 13, 17,  4 } },
			},
			{
				{ S::StandOnPad, 2 }, { S::TakePost, 1 }, { S::TakePost, 3 },
				{ S::StandOnPad, 1 }, { S::TakePost, 0 },
				{ S::Rebuild, W },
				{ S::WalkThroughTakenPost, 3 }, { S::TakePost, 2 },
				{ S::StandOnPad, 0 },
				{ S::Rebuild, R },
				{ S::TakePost, 3 }, { S::StandOnPad, 1 },
				{ S::Rebuild, C },
				{ S::TakePost, 4 },
			},
		},
		// ---- set 1 -- rebuilds: REWIND, COLD, WARM -------------------------------
		//   pad 2 ; take Cedar (15) -> 15  << copied >> ; take Elm (6) -> 21 ;
		//   pad 3 ; take Birch (4) -> 25
		//   REWIND -> only Cedar gone, board 15, pad 2
		//   walk through Cedar's ground ; take Dale (12) -> 27 ; pad 3
		//   COLD   -> all five standing, board 0, pad 1 ; take Ash (3) -> 3 ; pad 2
		//   WARM   -> Ash gone, board 3, pad 2 ; take Birch (7) -> 10
		{
			{
				{ { 11,  4, 15,  8,  6 }, { 13,  3,  9 } },
				{ {  7, 16,  5, 12, 14 }, {  4, 17,  6 } },
				{ {  3,  9, 13, 17, 10 }, { 11,  8, 15 } },
				{ { 12,  7, 16,  4, 11 }, {  5, 14,  3 } },
			},
			{
				{ S::StandOnPad, 1 }, { S::TakePost, 2 }, { S::TakePost, 4 },
				{ S::StandOnPad, 2 }, { S::TakePost, 1 },
				{ S::Rebuild, R },
				{ S::WalkThroughTakenPost, 2 }, { S::TakePost, 3 },
				{ S::StandOnPad, 2 },
				{ S::Rebuild, C },
				{ S::TakePost, 0 }, { S::StandOnPad, 1 },
				{ S::Rebuild, W },
				{ S::TakePost, 1 },
			},
		},
		// ---- set 2 -- rebuilds: COLD, WARM, REWIND -------------------------------
		//   pad 3 ; take Elm (13) -> 13  << copied >> ; take Dale (11) -> 24 ;
		//   pad 2 ; take Birch (17) -> 41
		//   COLD   -> all five standing, board 0, pad 1 ; take Cedar (16) -> 16 ; pad 3
		//   WARM   -> Cedar gone, board 16, pad 3
		//   walk through Cedar's ground ; take Ash (15) -> 31 ; pad 2
		//   REWIND -> only Elm gone, board 13, pad 3 -- a state that existed BEFORE the
		//             record was ever deleted, which nothing but the record can produce
		//   take Dale (16) -> 29
		{
			{
				{ {  9, 17,  3, 11, 13 }, {  6, 15,  8 } },
				{ { 12,  6, 16,  4,  7 }, { 14,  3, 11 } },
				{ { 15, 10,  8,  3, 16 }, {  5, 12, 17 } },
				{ {  4, 13, 11, 16,  9 }, { 10,  7, 14 } },
			},
			{
				{ S::StandOnPad, 2 }, { S::TakePost, 4 }, { S::TakePost, 3 },
				{ S::StandOnPad, 1 }, { S::TakePost, 1 },
				{ S::Rebuild, C },
				{ S::TakePost, 2 }, { S::StandOnPad, 2 },
				{ S::Rebuild, W },
				{ S::WalkThroughTakenPost, 2 }, { S::TakePost, 0 },
				{ S::StandOnPad, 1 },
				{ S::Rebuild, R },
				{ S::TakePost, 3 },
			},
		},
	};

	const int32 Count = int32(UE_ARRAY_COUNT(kSets));

	// A CLOCK-DERIVED DEFAULT, logged and overridable -- the sibling
	// AKeyringFunctionalTest::RecutTheYard pattern. A FIXED default plus a spec that
	// publishes the tables (and tasks/craftbench-public/README.md says these specs are
	// the ones intended for publication) would mean every graded run for ever ran the
	// one set whose numbers are in print, and difficulty condition (c) -- a hard-coded
	// answer must be wrong from the first frame -- would hold only while the print run
	// stayed secret. Pinning stays available so a discrimination leg is byte-
	// reproducible: -CraftBenchYardSeed=0 / 1 / 2 selects a set outright.
	int32 Seed = 0;
	const bool bPinned =
		FParse::Value(FCommandLine::Get(), TEXT("CraftBenchYardSeed="), Seed);
	if (!bPinned)
	{
		Seed = int32(FPlatformTime::Cycles() & 0x7fffffff);
	}
	SetIndex = ((Seed % Count) + Count) % Count;
	Set = &kSets[SetIndex];
	UE_LOG(LogTemp, Display,
		TEXT("[t3-memoryyard] staged set %d of %d (seed %d, %s). Re-run this exact day "
			 "with -CraftBenchYardSeed=%d"),
		SetIndex, Count, Seed, bPinned ? TEXT("pinned") : TEXT("from the clock"),
		SetIndex);
}

// ---------------------------------------------------------------------------
// Lifecycle plumbing
// ---------------------------------------------------------------------------

AMemoryYardFunctionalTest::AMemoryYardFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	// Registered in the CONSTRUCTOR, exactly as ASanityFunctionalTest does: the hook
	// fires after PostInitializeComponents and BEFORE any placed actor's BeginPlay,
	// which is the only window in which the yard's numbers can be staged -- and the
	// only window in which a record left behind on disk can be taken away -- without a
	// submission having already read either.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &AMemoryYardFunctionalTest::OnWorldActorsInitialized);
}

void AMemoryYardFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------
// Reflection helpers. Everything is read and written BY PROPERTY NAME, never by class,
// so a submission is free to subclass or replace the supplied actors.
// ---------------------------------------------------------------------------

bool AMemoryYardFunctionalTest::GetIntProp(const AActor* A, const TCHAR* Name, int32& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	const FIntProperty* const P = FindFProperty<FIntProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	Out = P->GetPropertyValue_InContainer(A);
	return true;
}

bool AMemoryYardFunctionalTest::SetIntProp(AActor* A, const TCHAR* Name, int32 Value)
{
	if (A == nullptr)
	{
		return false;
	}
	FIntProperty* const P = FindFProperty<FIntProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

bool AMemoryYardFunctionalTest::GetBoolProp(const AActor* A, const TCHAR* Name, bool& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	const FBoolProperty* const P = FindFProperty<FBoolProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	Out = P->GetPropertyValue_InContainer(A);
	return true;
}

bool AMemoryYardFunctionalTest::GetNameProp(const AActor* A, const TCHAR* Name, FName& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	const FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	Out = P->GetPropertyValue_InContainer(A);
	return true;
}

bool AMemoryYardFunctionalTest::SetNameProp(AActor* A, const TCHAR* Name, FName Value)
{
	if (A == nullptr)
	{
		return false;
	}
	FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

FString AMemoryYardFunctionalTest::ReadDisplay(const AActor* A, const TCHAR* PreferredName)
{
	if (A == nullptr)
	{
		return FString();
	}
	TArray<UTextRenderComponent*> Texts;
	const_cast<AActor*>(A)->GetComponents<UTextRenderComponent>(Texts);
	const UTextRenderComponent* Chosen = nullptr;
	for (const UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetFName() == FName(PreferredName))
		{
			Chosen = T;
			break;
		}
	}
	if (Chosen == nullptr)
	{
		for (const UTextRenderComponent* T : Texts)
		{
			if (T != nullptr)
			{
				Chosen = T;
				break;
			}
		}
	}
	// THE RENDERED TEXT, not a mirror. The mirrors live in files the agent may edit, so
	// they are only ever a cross-check against this.
	return (Chosen != nullptr) ? Chosen->Text.ToString() : FString();
}

bool AMemoryYardFunctionalTest::ReadPillarVisible(const AActor* A, bool& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	TArray<UStaticMeshComponent*> Meshes;
	const_cast<AActor*>(A)->GetComponents<UStaticMeshComponent>(Meshes);
	if (Meshes.Num() == 0)
	{
		return false;
	}
	const UStaticMeshComponent* Chosen = nullptr;
	for (const UStaticMeshComponent* M : Meshes)
	{
		if (M != nullptr && M->GetFName() == FName(TEXT("Pillar")))
		{
			Chosen = M;
			break;
		}
	}
	if (Chosen == nullptr)
	{
		// Else the TALLEST, not the biggest: the painted patch underfoot is wider than
		// the pillar in plan and would win a volume comparison on some scalings.
		double BestZ = -1.0;
		for (const UStaticMeshComponent* M : Meshes)
		{
			if (M == nullptr)
			{
				continue;
			}
			const double Z = M->Bounds.BoxExtent.Z;
			if (Z > BestZ)
			{
				BestZ = Z;
				Chosen = M;
			}
		}
	}
	if (Chosen == nullptr)
	{
		return false;
	}
	Out = Chosen->IsVisible();
	return true;
}

bool AMemoryYardFunctionalTest::ReadLampLit(const AActor* A, bool& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	TArray<UPointLightComponent*> Lights;
	const_cast<AActor*>(A)->GetComponents<UPointLightComponent>(Lights);
	if (Lights.Num() == 0)
	{
		return false;
	}
	const UPointLightComponent* Chosen = nullptr;
	for (const UPointLightComponent* L : Lights)
	{
		if (L != nullptr && L->GetFName() == FName(TEXT("Lamp")))
		{
			Chosen = L;
			break;
		}
	}
	if (Chosen == nullptr)
	{
		double Best = -1.0;
		for (const UPointLightComponent* L : Lights)
		{
			if (L != nullptr && double(L->Intensity) > Best)
			{
				Best = double(L->Intensity);
				Chosen = L;
			}
		}
	}
	if (Chosen == nullptr)
	{
		return false;
	}
	// BURNING, as a person would see it: the light the lamp actually throws, never the
	// mirror the agent could write.
	Out = (Chosen->Intensity > 0.0f);
	return true;
}

bool AMemoryYardFunctionalTest::ReadTokenInt(const FString& Text, const TCHAR* Token,
	int32& Out)
{
	const int32 At = Text.Find(Token, ESearchCase::CaseSensitive, ESearchDir::FromStart);
	if (At == INDEX_NONE)
	{
		return false;
	}
	int32 i = At + FCString::Strlen(Token);
	while (i < Text.Len() && FChar::IsWhitespace(Text[i]))
	{
		++i;
	}
	bool bNegative = false;
	if (i < Text.Len() && Text[i] == TEXT('-'))
	{
		bNegative = true;
		++i;
	}
	if (i >= Text.Len() || !FChar::IsDigit(Text[i]))
	{
		return false;
	}
	int64 Value = 0;
	while (i < Text.Len() && FChar::IsDigit(Text[i]))
	{
		Value = Value * 10 + int64(Text[i] - TEXT('0'));
		++i;
	}
	Out = int32(bNegative ? -Value : Value);
	return true;
}

FString AMemoryYardFunctionalTest::NameList(const TArray<FName>& Names)
{
	if (Names.Num() == 0)
	{
		return FString(TEXT("none"));
	}
	TArray<FString> S;
	for (const FName& N : Names)
	{
		S.Add(N.ToString());
	}
	S.Sort();
	return FString::Join(S, TEXT(", "));
}

const TCHAR* AMemoryYardFunctionalTest::GateName(EGate Gate)
{
	switch (Gate)
	{
	case EGate::RetakenPostAddsNothing:          return TEXT("RetakenPostAddsNothing");
	case EGate::UntakenPostStillAddsAfterReopen: return TEXT("UntakenPostStillAddsAfterReopen");
	case EGate::LatestPadMovesAfterReopen:       return TEXT("LatestPadMovesAfterReopen");
	case EGate::ColdYardTakesAgain:              return TEXT("ColdYardTakesAgain");
	default:                                     return TEXT("SessionTallyTracksExactly");
	}
}

const TCHAR* AMemoryYardFunctionalTest::ReopenGateName(ERebuild Kind, EClaim Claim)
{
	// A rebuild that did nothing to the record asks three separate questions and each
	// has carried its own name since the task was first written. The other two kinds
	// each make ONE claim about the record -- it was put back, or it was taken away --
	// so each has one name, and a failure under it says which of the three readings
	// went wrong in its own sentence.
	if (Kind == ERebuild::Rewind)
	{
		return TEXT("PutBackRecordRulesTheYard");
	}
	if (Kind == ERebuild::Cold)
	{
		return TEXT("ColdReopenForgetsEverything");
	}
	switch (Claim)
	{
	case EClaim::Board:     return TEXT("BankedTotalSurvivesRestage");
	case EClaim::Placement: return TEXT("RunnerResumesAtLatestPad");
	default:                return TEXT("TakenPostsStayGoneAfterReopen");
	}
}

const TCHAR* AMemoryYardFunctionalTest::ReopenBecause(ERebuild Kind)
{
	// DISCLOSED IN THE PROMPT, all three of them, in these words: the yard shuts and
	// reopens; some days the earlier copy of the record is put back; some days the
	// record is thrown away.
	switch (Kind)
	{
	case ERebuild::Rewind:
		return TEXT("the copy of the written record taken a moment after the counter "
					"board first rose was put back in its place while the yard was "
					"shut, so the yard has to open on exactly what that copy says");
	case ERebuild::Cold:
		return TEXT("the written record was thrown away while the yard was shut, so "
					"the yard has to open as if it had never been visited");
	default:
		return TEXT("nothing was done to the written record while the yard was shut, "
					"so the yard has to come back exactly as it stood");
	}
}

void AMemoryYardFunctionalTest::FailUnderGate(const TCHAR* Gate, const FString& Why)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("%s: %s"), Gate, *Why));
}

const TCHAR* AMemoryYardFunctionalTest::LampWord(bool bLit)
{
	return bLit ? TEXT("burning") : TEXT("dark");
}

// ---------------------------------------------------------------------------
// Staging
// ---------------------------------------------------------------------------

FString AMemoryYardFunctionalTest::DurableStoreDir() const
{
	// THE FOLDER THE PROMPT NAMES: "write it down on disk, in the folder the project
	// keeps its saved games in". Everything this fixture does to the record -- empty
	// it, copy it, put the copy back -- is done to this directory and to nothing else,
	// and no file in it is ever opened, parsed or understood.
	return FPaths::ProjectSavedDir() / TEXT("SaveGames");
}

void AMemoryYardFunctionalTest::SnapshotDurableStores()
{
	// INTO MEMORY, NEVER ONTO DISK. A copy left in Saved/ anywhere is a copy the thing
	// being measured could find and read, which would hand it a second channel for
	// exactly the state the task exists to make it write down properly.
	RecordSnapshot.Reset();
	const FString Dir = DurableStoreDir();
	TArray<FString> Files;
	IFileManager::Get().FindFilesRecursive(Files, *Dir, TEXT("*"), /*Files=*/true,
		/*Directories=*/false, /*bClearFileNames=*/true);
	for (const FString& Full : Files)
	{
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *Full))
		{
			continue;
		}
		FString Rel = Full;
		FPaths::MakePathRelativeTo(Rel, *(Dir / TEXT("")));
		RecordSnapshot.Add(Rel, MoveTemp(Bytes));
	}
	bHaveSnapshot = true;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-memoryyard] took a copy of the written record: %d file(s)"),
		RecordSnapshot.Num());
}

void AMemoryYardFunctionalTest::RestoreDurableStores()
{
	// Whatever the record has become since is thrown away and the earlier bytes are put
	// back in its place. A submission whose memory is the real source of truth cannot
	// notice this at all -- which is the entire point: it reopens on what it remembers,
	// and what it remembers is four posts and a bigger number.
	const FString Dir = DurableStoreDir();
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	for (const TPair<FString, TArray<uint8>>& Entry : RecordSnapshot)
	{
		const FString Full = Dir / Entry.Key;
		IFileManager::Get().MakeDirectory(*FPaths::GetPath(Full), true);
		FFileHelper::SaveArrayToFile(Entry.Value, *Full);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-memoryyard] put the earlier copy of the written record back: "
			 "%d file(s)"), RecordSnapshot.Num());
}

void AMemoryYardFunctionalTest::WipeDurableStores(bool bRecordEmptiness)
{
	// A day written down SURVIVES THE PROCESS. On a second run in the same workdir --
	// a re-capture, a gate re-run, a --keep-workdir iteration -- a correct submission
	// would restore yesterday's yard at t = 0 and be failed for having obeyed the
	// prompt. This is MANDATORY, not tidiness. Its complement is ProbeOpening, which
	// turns a store this could not reach into an attributed Error rather than a FAIL.
	//
	// The same call is what takes the record away while the yard is shut for the
	// second time, which is the whole point of the task.
	const FString SaveDir = DurableStoreDir();
	IFileManager::Get().DeleteDirectory(*SaveDir, false, true);
	if (bRecordEmptiness)
	{
		// READ NOW, NOT LATER. Nothing has begun play, so this answers exactly one
		// question -- did the wipe reach the store? -- with no chance of a record the
		// submission wrote during the run being mistaken for a leftover one.
		bDurableStoreEmptyAtOpen = !IFileManager::Get().DirectoryExists(*SaveDir);
	}
}

void AMemoryYardFunctionalTest::OnWorldActorsInitialized(
	const FActorsInitializedParams& Params)
{
	if (bStaged || Params.World != GetWorld())
	{
		return;
	}
	bStaged = true;

	ChooseSet();
	WipeDurableStores(/*bRecordEmptiness=*/true);

	if (!ResolveYards(true))
	{
		return;   // the reason is remembered and reported from PrepareTest
	}
	bResolved = true;
	StageRound(Set->Rounds[0]);
}

const AMemoryYardFunctionalTest::FRound& AMemoryYardFunctionalTest::RoundFor(
	int32 Reopen) const
{
	return Set->Rounds[FMath::Clamp(Reopen, 0, kRounds - 1)];
}

void AMemoryYardFunctionalTest::StageRound(const FRound& Round)
{
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		SetIntProp(NearPosts[i].Actor.Get(), TEXT("WorthNow"), Round.Near[i]);
	}
	for (int32 i = 0; i < kFarPosts; ++i)
	{
		SetIntProp(FarPostProps[i].Actor.Get(), TEXT("WorthNow"), Round.Far[i]);
	}
}

bool AMemoryYardFunctionalTest::ResolveYards(bool bFirstOpen)
{
	UWorld* const World = GetWorld();

	auto Reject = [this](bool bHarness, const FString& Why) -> bool
	{
		if (this->StagingFailure.IsEmpty())
		{
			this->StagingFailure = Why;
			this->bStagingIsHarnessFault = bHarness;
		}
		if (this->IsRunning())
		{
			this->FinishTest(bHarness ? EFunctionalTestResult::Error
									  : EFunctionalTestResult::Failed, Why);
		}
		return false;
	};

	// ---- the pads say which yard is the near one ------------------------------
	TArray<AActor*> FoundPads;
	UGameplayStatics::GetAllActorsWithTag(World, kPadTag, FoundPads);
	if (FoundPads.Num() != kPads)
	{
		return Reject(false, FString::Printf(
			TEXT("TheYardsOwnPropsAreStillThere: the near yard should hold exactly "
				 "three pads and it holds %d. The pads are supplied and placed; they "
				 "are not yours to add to or take away"), FoundPads.Num()));
	}

	TArray<FProp> Rebuilt;
	Rebuilt.SetNum(kPads);
	FName PadYard = NAME_None;
	for (AActor* const A : FoundPads)
	{
		FName Yard = NAME_None;
		FName Id = NAME_None;
		int32 Order = 0;
		if (!GetNameProp(A, TEXT("YardName"), Yard) || Yard.IsNone()
			|| !GetNameProp(A, TEXT("PadId"), Id) || Id.IsNone()
			|| !GetIntProp(A, TEXT("PadOrder"), Order))
		{
			return Reject(false,
				TEXT("TheYardsOwnPropsAreStillThere: a pad no longer says which yard "
					 "it is in, what it is called, or where it comes in the order, and "
					 "a pad is known by nothing else"));
		}
		for (const TCHAR* const PropName : kPadProps)
		{
			int32 Ignored = 0;
			if (!GetIntProp(A, PropName, Ignored))
			{
				return Reject(false, FString::Printf(
					TEXT("TheYardsOwnPropsAreStillThere: a pad no longer says %s"),
					PropName));
			}
		}
		bool bIgnoredLit = false;
		if (!GetBoolProp(A, TEXT("bLastShownLit"), bIgnoredLit))
		{
			return Reject(false,
				TEXT("TheYardsOwnPropsAreStillThere: a pad no longer reports whether "
					 "its lamp is burning"));
		}
		if (PadYard.IsNone())
		{
			PadYard = Yard;
		}
		else if (PadYard != Yard)
		{
			return Reject(false, FString::Printf(
				TEXT("TheYardsOwnPropsAreStillThere: the pads say they are in %s and "
					 "%s; the marks all belong to one yard"),
				*PadYard.ToString(), *Yard.ToString()));
		}
		if (Order < 1 || Order > kPads || Rebuilt[Order - 1].Actor.IsValid())
		{
			return Reject(false, FString::Printf(
				TEXT("TheYardsOwnPropsAreStillThere: the pads should be the first, the "
					 "second and the third and one of them says it is number %d"),
				Order));
		}
		FProp& Slot = Rebuilt[Order - 1];
		Slot.Actor = A;
		Slot.Id = Id;
		Slot.Order = Order;
		Slot.Home = A->GetActorTransform();
		Slot.Cls = A->GetClass();
	}
	if (bFirstOpen)
	{
		NearYard = PadYard;
	}
	else if (PadYard != NearYard)
	{
		return Reject(false, FString::Printf(
			TEXT("TheYardsOwnPropsAreStillThere: the yard reopened with its pads "
				 "saying they belong to %s rather than %s"),
			*PadYard.ToString(), *NearYard.ToString()));
	}
	for (int32 i = 0; i < kPads; ++i)
	{
		if (!bFirstOpen && PadProps[i].Id != Rebuilt[i].Id)
		{
			// The pads keep their names and their place in the order across a rebuild;
			// only where they lie changes. A mismatch here is the FIXTURE's fault.
			return Reject(true, FString::Printf(
				TEXT("HARNESS-PRECONDITION: pad %d came back called %s, not %s"),
				i + 1, *Rebuilt[i].Id.ToString(), *PadProps[i].Id.ToString()));
		}
		PadProps[i] = Rebuilt[i];
	}

	// ---- the posts: five in the near yard, three in the other one -------------
	TArray<AActor*> FoundPosts;
	UGameplayStatics::GetAllActorsWithTag(World, kPostTag, FoundPosts);
	TArray<AActor*> Near;
	TArray<AActor*> Far;
	FName SeenFar = NAME_None;
	for (AActor* const A : FoundPosts)
	{
		FName Yard = NAME_None;
		FName Id = NAME_None;
		if (!GetNameProp(A, TEXT("YardName"), Yard) || Yard.IsNone()
			|| !GetNameProp(A, TEXT("PostId"), Id) || Id.IsNone())
		{
			return Reject(false,
				TEXT("TheYardsOwnPropsAreStillThere: a post no longer says which yard "
					 "it is in or what it is called, and a post is known by nothing "
					 "else"));
		}
		for (const TCHAR* const PropName : kPostProps)
		{
			int32 Ignored = 0;
			if (!GetIntProp(A, PropName, Ignored))
			{
				return Reject(false, FString::Printf(
					TEXT("TheYardsOwnPropsAreStillThere: a post no longer says %s, so "
						 "nothing can read what it is worth"), PropName));
			}
		}
		bool bIgnoredStanding = false;
		if (!GetBoolProp(A, TEXT("bLastShownStanding"), bIgnoredStanding))
		{
			return Reject(false,
				TEXT("TheYardsOwnPropsAreStillThere: a post no longer reports whether "
					 "it is standing"));
		}
		if (Yard == NearYard)
		{
			Near.Add(A);
		}
		else
		{
			if (SeenFar.IsNone())
			{
				SeenFar = Yard;
			}
			else if (SeenFar != Yard)
			{
				return Reject(false, FString::Printf(
					TEXT("TheYardsOwnPropsAreStillThere: there are posts in %s, %s "
						 "and %s; this level has two yards"),
					*NearYard.ToString(), *SeenFar.ToString(), *Yard.ToString()));
			}
			Far.Add(A);
		}
	}
	if (Near.Num() != kNearPosts || Far.Num() != kFarPosts)
	{
		return Reject(false, FString::Printf(
			TEXT("TheYardsOwnPropsAreStillThere: the near yard should hold five posts "
				 "and the far yard three; they hold %d and %d. The posts are supplied "
				 "and placed"), Near.Num(), Far.Num()));
	}
	if (bFirstOpen)
	{
		FarYard = SeenFar;
	}

	auto TakeRow = [&](TArray<AActor*>& Actors, FProp* Out, int32 Count,
		const FProp* Previous) -> bool
	{
		// A STABLE ORDER that does not depend on where a post stands, because every
		// post moves at both rebuilds. Sorted by the name the post carries.
		Actors.Sort([](const AActor& L, const AActor& R)
		{
			FName LN = NAME_None;
			FName RN = NAME_None;
			GetNameProp(&L, TEXT("PostId"), LN);
			GetNameProp(&R, TEXT("PostId"), RN);
			return LN.ToString() < RN.ToString();
		});
		for (int32 i = 0; i < Count; ++i)
		{
			FName Id = NAME_None;
			GetNameProp(Actors[i], TEXT("PostId"), Id);
			if (i > 0)
			{
				FName Prev = NAME_None;
				GetNameProp(Actors[i - 1], TEXT("PostId"), Prev);
				if (Prev == Id)
				{
					Reject(false, FString::Printf(
						TEXT("TheYardsOwnPropsAreStillThere: two posts are both called "
							 "%s, so one cannot be told from the other"),
						*Id.ToString()));
					return false;
				}
			}
			if (Previous != nullptr && Previous[i].Id != Id)
			{
				Reject(true, FString::Printf(
					TEXT("HARNESS-PRECONDITION: the yard came back with a post called "
						 "%s where %s stood; the fixture puts the same names back"),
					*Id.ToString(), *Previous[i].Id.ToString()));
				return false;
			}
			Out[i].Actor = Actors[i];
			Out[i].Id = Id;
			Out[i].Home = Actors[i]->GetActorTransform();
			Out[i].Cls = Actors[i]->GetClass();
		}
		return true;
	};

	FProp NearRow[kNearPosts];
	FProp FarRow[kFarPosts];
	if (!TakeRow(Near, NearRow, kNearPosts, bFirstOpen ? nullptr : NearPosts))
	{
		return false;
	}
	if (!TakeRow(Far, FarRow, kFarPosts, bFirstOpen ? nullptr : FarPostProps))
	{
		return false;
	}
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		NearPosts[i] = NearRow[i];
	}
	for (int32 i = 0; i < kFarPosts; ++i)
	{
		FarPostProps[i] = FarRow[i];
	}

	// ---- one board per yard ---------------------------------------------------
	TArray<AActor*> FoundBoards;
	UGameplayStatics::GetAllActorsWithTag(World, kBoardTag, FoundBoards);
	AActor* NearB = nullptr;
	AActor* FarB = nullptr;
	for (AActor* const A : FoundBoards)
	{
		FName Yard = NAME_None;
		if (!GetNameProp(A, TEXT("YardName"), Yard))
		{
			return Reject(false,
				TEXT("TheYardsOwnPropsAreStillThere: a counter board no longer says "
					 "which yard it belongs to"));
		}
		for (const TCHAR* const PropName : kBoardProps)
		{
			int32 Ignored = 0;
			if (!GetIntProp(A, PropName, Ignored))
			{
				return Reject(false, FString::Printf(
					TEXT("TheYardsOwnPropsAreStillThere: a counter board no longer "
						 "says %s"), PropName));
			}
		}
		AActor*& Slot = (Yard == NearYard) ? NearB : FarB;
		if (Slot != nullptr)
		{
			return Reject(false, FString::Printf(
				TEXT("TheYardsOwnPropsAreStillThere: %s has more than one counter "
					 "board, so there is no one number to read"), *Yard.ToString()));
		}
		Slot = A;
	}
	if (NearB == nullptr || FarB == nullptr)
	{
		return Reject(false, FString::Printf(
			TEXT("TheYardsOwnPropsAreStillThere: each yard needs a counter board of "
				 "its own; %s %s one and %s %s one"),
			*NearYard.ToString(), NearB != nullptr ? TEXT("has") : TEXT("has not"),
			*FarYard.ToString(), FarB != nullptr ? TEXT("has") : TEXT("has not")));
	}
	NearBoardProp.Actor = NearB;
	NearBoardProp.Cls = NearB->GetClass();
	FarBoardProp.Actor = FarB;
	FarBoardProp.Cls = FarB->GetClass();
	if (bFirstOpen)
	{
		NearBoardProp.Home = NearB->GetActorTransform();
		FarBoardProp.Home = FarB->GetActorTransform();
	}

	// ---- the lane: the clear band between the post row and the pad row --------
	double PostY = 0.0;
	double PadY = 0.0;
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		PostY += NearPosts[i].Home.GetLocation().Y;
	}
	for (int32 i = 0; i < kPads; ++i)
	{
		PadY += PadProps[i].Home.GetLocation().Y;
	}
	LaneY = 0.5 * (PostY / double(kNearPosts) + PadY / double(kPads));
	return true;
}

bool AMemoryYardFunctionalTest::ResolveHero()
{
	// NOT during staging: the props are placed actors and exist the moment the world
	// initialises them, but the runner is spawned by the game mode inside
	// UWorld::BeginPlay, which is AFTER OnWorldInitializedActors has fired. Asking for
	// it there returns null on a perfectly healthy yard.
	Hero = UGameplayStatics::GetPlayerCharacter(GetWorld(), 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: there is no visibly represented player "
				 "character in the yard to walk it. The runner is substrate this "
				 "level ships, never anything the agent was asked to write"));
		return false;
	}
	HeroStart = Hero->GetActorLocation();
	return true;
}

FString AMemoryYardFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	TArray<FString> Problems;

	// Half one: the pawn's own Enhanced Input actions, read BY PROPERTY NAME so a
	// renamed or subclassed pawn still answers.
	if (Hero.IsValid())
	{
		TArray<FString> Unbound;
		for (const TCHAR* Name : { TEXT("MoveAction"), TEXT("LookAction"),
								   TEXT("MouseLookAction"), TEXT("JumpAction") })
		{
			const FObjectProperty* const Prop =
				FindFProperty<FObjectProperty>(Hero->GetClass(), Name);
			if (Prop == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(Hero.Get()) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Problems.Add(FString::Printf(TEXT("the runner (%s) has nothing bound to %s"),
				*Hero->GetClass()->GetName(), *FString::Join(Unbound, TEXT(", "))));
		}
	}

	// Half two: a mapping context has to be applied, or no key reaches any of those
	// actions even when all four are set.
	const AGameModeBase* const GameMode =
		(World != nullptr) ? World->GetAuthGameMode() : nullptr;
	const UClass* const PCClass =
		(GameMode != nullptr) ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the player "
						  "gets a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts =
				 FindFProperty<FArrayProperty>(PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
		FScriptArrayHelper Helper(Contexts,
			Contexts->ContainerPtrToValuePtr<void>(PCClass->GetDefaultObject()));
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
			Problems.Add(FString::Printf(TEXT("%s applies no input mapping context"),
				*PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s carries no DefaultMappingContexts, so nothing here can confirm a "
				 "key is mapped"), *PCClass->GetName()));
	}

	return FString::Join(Problems, TEXT("; "));
}

// ---------------------------------------------------------------------------
// The shadow ledger. Every expectation is DERIVED from the staged set here, so a
// change to the table moves the expectations with it and cannot leave a stale
// constant behind. PrepareTest refuses a set that stopped measuring what it claims.
// ---------------------------------------------------------------------------

bool AMemoryYardFunctionalTest::BuildDayTrace()
{
	auto Precondition = [this](const FString& Why) -> bool
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: staged set %d no longer measures what it "
				 "claims. %s"), SetIndex, *Why));
		return false;
	};

	// Every number a person can read must lie in the band the prompt discloses.
	for (int32 R = 0; R < kRounds; ++R)
	{
		const FRound& Round = Set->Rounds[R];
		for (int32 i = 0; i < kNearPosts; ++i)
		{
			if (Round.Near[i] < kWorthMin || Round.Near[i] > kWorthMax)
			{
				return Precondition(FString::Printf(
					TEXT("round %d paints %s with %d, outside the %d..%d the prompt "
						 "states"), R, *NearPosts[i].Id.ToString(), Round.Near[i],
					kWorthMin, kWorthMax));
			}
		}
		for (int32 i = 0; i < kFarPosts; ++i)
		{
			if (Round.Far[i] < kWorthMin || Round.Far[i] > kWorthMax)
			{
				return Precondition(FString::Printf(
					TEXT("round %d paints %s with %d, outside the %d..%d the prompt "
						 "states"), R, *FarPostProps[i].Id.ToString(), Round.Far[i],
					kWorthMin, kWorthMax));
			}
		}
	}

	Visits.Reset();
	Reopens.Reset();
	PhaseStart.Reset();
	PhaseCount.Reset();

	auto SameTaken = [](const FYardState& A, const FYardState& B) -> bool
	{
		for (int32 i = 0; i < kNearPosts; ++i)
		{
			if (A.bTaken[i] != B.bTaken[i])
			{
				return false;
			}
		}
		return true;
	};
	auto GoneList = [this](const FYardState& S) -> FString
	{
		TArray<FName> Gone;
		for (int32 i = 0; i < kNearPosts; ++i)
		{
			if (S.bTaken[i])
			{
				Gone.Add(NearPosts[i].Id);
			}
		}
		return NameList(Gone);
	};

	// ---- SIMULATE THE DAY ----------------------------------------------------
	// Nothing below reads a number written into the table. Every expectation is what
	// walking this script would leave behind, so editing a set moves the expectations
	// with it and a set that stopped discriminating is refused rather than graded.
	FYardState State;
	FYardState Snapshot;
	bool bDaySnapshotTaken = false;
	int32 Round = 0;
	int32 PhaseFirst = 0;
	int32 KindsUsed[3] = { 0, 0, 0 };
	bool bAfterRebuild = false;
	ERebuild LastKind = ERebuild::Warm;
	TArray<int32> BoardsSeen;
	BoardsSeen.Add(0);

	for (int32 s = 0; s < kSteps; ++s)
	{
		const FStep& Step = Set->Script[s];

		if (Step.Kind == EStep::Rebuild)
		{
			if (Visits.Num() == PhaseFirst)
			{
				return Precondition(FString::Printf(
					TEXT("step %d shuts the yard with nothing walked since it last "
						 "opened, so the reopening would grade a stretch nobody was "
						 "in"), s));
			}
			if (Reopens.Num() == 0)
			{
				// The opening stretch is graded at its closing sample, and that sample
				// has to be a post being taken: the counter board, the standing posts
				// and the burning lamp are all read there at once.
				if (Visits.Last().Kind != EVisit::TakePost)
				{
					return Precondition(
						TEXT("the last thing done before the yard first shuts is not a "
							 "post being taken, and that sample is where the opening "
							 "day is read off the boards"));
				}
				Visits.Last().Grade = EGate::SessionTallyTracksExactly;
			}
			PhaseStart.Add(PhaseFirst);
			PhaseCount.Add(Visits.Num() - PhaseFirst);
			PhaseFirst = Visits.Num();

			if (Step.A < 0 || Step.A > int32(ERebuild::Cold))
			{
				return Precondition(FString::Printf(
					TEXT("step %d asks for a kind of reopening that does not exist"),
					s));
			}
			FReopen Reopen;
			Reopen.Kind = ERebuild(Step.A);
			Reopen.Was = State;
			++KindsUsed[Step.A];
			++Round;
			if (Round >= kRounds)
			{
				return Precondition(
					TEXT("the day shuts the yard more times than there are rounds of "
						 "numbers to repaint it with"));
			}
			Reopen.Round = Round;

			switch (Reopen.Kind)
			{
			case ERebuild::Warm:
				break;                       // the record is left exactly as it is
			case ERebuild::Rewind:
				if (!bDaySnapshotTaken)
				{
					return Precondition(FString::Printf(
						TEXT("step %d puts the earlier copy of the record back before "
							 "any copy has been taken"), s));
				}
				State = Snapshot;
				break;
			case ERebuild::Cold:
				State = FYardState();
				break;
			}
			Reopen.Expect = State;

			// ---- WHAT THE NAIVE ANSWERS WOULD SHOW, all of them -----------------
			const FRound& Now = Set->Rounds[Round];
			Reopen.RecomputeTotal = 0;
			Reopen.AllFiveTotal = 0;
			Reopen.TakenCount = 0;
			for (int32 i = 0; i < kNearPosts; ++i)
			{
				Reopen.AllFiveTotal += Now.Near[i];
				if (State.bTaken[i])
				{
					Reopen.RecomputeTotal += Now.Near[i];
					++Reopen.TakenCount;
				}
			}

			if (Reopen.Kind == ERebuild::Cold)
			{
				// A cold reopening measures nothing unless there was something to
				// forget, and unless forgetting it shows in all three readings.
				if (Reopen.Was.Board == 0 || Reopen.Was.MarkedPad == 1)
				{
					return Precondition(FString::Printf(
						TEXT("the record is thrown away at step %d while the board "
							 "already read %d and the mark was already on the first "
							 "pad, so a yard that never remembered anything would read "
							 "the same"), s, Reopen.Was.Board));
				}
				bool bAnyGone = false;
				for (int32 i = 0; i < kNearPosts; ++i)
				{
					bAnyGone = bAnyGone || Reopen.Was.bTaken[i];
				}
				if (!bAnyGone)
				{
					return Precondition(FString::Printf(
						TEXT("the record is thrown away at step %d with every post "
							 "still standing, so nothing about the posts is asked"),
						s));
				}
			}
			else
			{
				// A reopening the record survives has to land on a number none of the
				// four cheap answers produces.
				if (Reopen.Expect.Board == 0
					|| Reopen.Expect.Board == Reopen.RecomputeTotal
					|| Reopen.Expect.Board == Reopen.AllFiveTotal
					|| Reopen.Expect.Board == Reopen.TakenCount)
				{
					return Precondition(FString::Printf(
						TEXT("the yard reopens at step %d on %d, which a naive answer "
							 "would also produce (never-visited 0, a count of %d, a "
							 "total re-derived from the taken posts' new numbers %d, "
							 "the sum of all five new numbers %d)"),
						s, Reopen.Expect.Board, Reopen.TakenCount,
						Reopen.RecomputeTotal, Reopen.AllFiveTotal));
				}
				if (Reopen.Expect.MarkedPad == 1)
				{
					return Precondition(FString::Printf(
						TEXT("the yard reopens at step %d with the mark on the first "
							 "pad, which is where a yard that remembered nothing would "
							 "also put the runner"), s));
				}
				// Every post the record says is gone must have been repainted, or "the
				// amount is history and the number over the post is news" is not
				// something this run can tell apart.
				for (int32 i = 0; i < kNearPosts; ++i)
				{
					if (State.bTaken[i] && State.WorthWhenTaken[i] == Now.Near[i])
					{
						return Precondition(FString::Printf(
							TEXT("%s was worth %d when it was taken and the yard "
								 "repaints it with %d at step %d, so a total re-derived "
								 "from it would be indistinguishable from the banked "
								 "one"), *NearPosts[i].Id.ToString(),
							State.WorthWhenTaken[i], Now.Near[i], s));
					}
				}
			}

			if (Reopen.Kind == ERebuild::Rewind)
			{
				// The whole value of putting the copy back is that MEMORY AND THE
				// RECORD DISAGREE. If the yard already stood in the copy's state, a
				// submission that never read the record passes anyway.
				if (Reopen.Expect.Board == Reopen.Was.Board
					|| SameTaken(Reopen.Expect, Reopen.Was)
					|| Reopen.Expect.MarkedPad == Reopen.Was.MarkedPad)
				{
					return Precondition(FString::Printf(
						TEXT("the copy put back at step %d says board %d, %s gone and "
							 "the mark on pad %d, and the yard already stood at board "
							 "%d, %s gone and pad %d; the two have to disagree in all "
							 "three readings or a warm memory passes anyway"),
						s, Reopen.Expect.Board, *GoneList(Reopen.Expect),
						Reopen.Expect.MarkedPad, Reopen.Was.Board,
						*GoneList(Reopen.Was), Reopen.Was.MarkedPad));
				}
			}

			Reopens.Add(Reopen);
			BoardsSeen.AddUnique(State.Board);
			bAfterRebuild = true;
			LastKind = Reopen.Kind;
			continue;
		}

		// ---- a step the runner walks ----------------------------------------
		FVisit V;
		V.Index = Step.A;
		V.Round = Round;
		V.BoardBefore = State.Board;
		V.BoardAfter = State.Board;

		if (Step.Kind == EStep::StandOnPad)
		{
			const int32 Order = Step.A + 1;
			if (Order < 1 || Order > kPads)
			{
				return Precondition(FString::Printf(
					TEXT("step %d stands on a pad numbered %d and there is no such "
						 "pad"), s, Order));
			}
			if (Order == State.MarkedPad)
			{
				return Precondition(FString::Printf(
					TEXT("step %d stands on pad %d, which is already the mark; a lamp "
						 "that never moves is a lamp nothing is measuring"), s, Order));
			}
			V.Kind = EVisit::StandOnPad;
			V.Grade = bAfterRebuild ? EGate::LatestPadMovesAfterReopen : EGate::None;
			State.MarkedPad = Order;
		}
		else if (Step.Kind == EStep::WalkThroughTakenPost)
		{
			if (Step.A < 0 || Step.A >= kNearPosts || !State.bTaken[Step.A])
			{
				return Precondition(FString::Printf(
					TEXT("step %d walks back through the ground of a post that is "
						 "still standing, so nothing about an already-taken post is "
						 "measured"), s));
			}
			V.Kind = EVisit::WalkThroughTakenPost;
			V.Grade = EGate::RetakenPostAddsNothing;
		}
		else
		{
			if (Step.A < 0 || Step.A >= kNearPosts || State.bTaken[Step.A])
			{
				return Precondition(FString::Printf(
					TEXT("step %d walks into a post that is already gone, so no number "
						 "could be banked there"), s));
			}
			const int32 Worth = Set->Rounds[Round].Near[Step.A];
			V.Kind = EVisit::TakePost;
			V.Worth = Worth;
			V.BoardAfter = State.Board + Worth;
			if (!bAfterRebuild)
			{
				V.Grade = EGate::None;   // the opening stretch is graded at its last take
			}
			else if (LastKind == ERebuild::Cold)
			{
				// A yard that forgot everything still has to be live, and the number it
				// banks must be one no warm yard could show.
				if (BoardsSeen.Contains(V.BoardAfter))
				{
					return Precondition(FString::Printf(
						TEXT("taking %s in the emptied yard banks %d, which the near "
							 "board has already read once today; a yard that opened "
							 "warm and then took a post could show the same number"),
						*NearPosts[Step.A].Id.ToString(), V.BoardAfter));
				}
				V.Grade = EGate::ColdYardTakesAgain;
			}
			else
			{
				// The post must be painted with something no earlier round painted it
				// with, or writing a REMEMBERED number back onto a fresh post would
				// look correct when the next person takes it.
				for (int32 R = 0; R < Round; ++R)
				{
					if (Set->Rounds[R].Near[Step.A] == Worth)
					{
						return Precondition(FString::Printf(
							TEXT("%s is painted %d in round %d and again in round %d, "
								 "so banking a remembered number would look right at "
								 "step %d"), *NearPosts[Step.A].Id.ToString(), Worth, R,
							Round, s));
					}
				}
				V.Grade = EGate::UntakenPostStillAddsAfterReopen;
			}
			State.bTaken[Step.A] = true;
			State.WorthWhenTaken[Step.A] = Worth;
			State.Board = V.BoardAfter;
			BoardsSeen.AddUnique(State.Board);

			if (!bDaySnapshotTaken)
			{
				// THE MOMENT THE COUNTER BOARD FIRST RISES -- disclosed in the prompt in
				// exactly those words. One post gone, one number banked, one mark set:
				// a state the day then leaves far behind, which is what makes putting
				// the copy back a question a warm memory cannot answer.
				V.bSnapshotAfter = true;
				Snapshot = State;
				bDaySnapshotTaken = true;
			}
		}
		Visits.Add(V);
	}

	PhaseStart.Add(PhaseFirst);
	PhaseCount.Add(Visits.Num() - PhaseFirst);

	if (Reopens.Num() != kRebuilds)
	{
		return Precondition(FString::Printf(
			TEXT("the day shuts the yard %d times and this fixture is written around "
				 "%d"), Reopens.Num(), kRebuilds));
	}
	for (int32 k = 0; k < 3; ++k)
	{
		if (KindsUsed[k] != 1)
		{
			return Precondition(FString::Printf(
				TEXT("the three ways of reopening are meant to happen once each and one "
					 "of them happens %d times; a shape every set shares is a shape a "
					 "submission can count instead of reading the record"),
				KindsUsed[k]));
		}
	}
	if (!bDaySnapshotTaken)
	{
		return Precondition(
			TEXT("no post is taken before the yard first shuts, so there is no moment "
				 "at which a copy of the record could be taken"));
	}
	if (PhaseCount.Last() <= 0)
	{
		return Precondition(
			TEXT("the day ends the moment the yard reopens for the last time, so "
				 "nothing proves the reopened yard is live"));
	}
	return true;
}

// ---------------------------------------------------------------------------
// Reading the yards, off what a person standing in them would see
// ---------------------------------------------------------------------------

bool AMemoryYardFunctionalTest::ReadWorld(FWorldRead& Out, FString& Why)
{
	Out = FWorldRead();
	ReadFailGate = nullptr;

	auto ReadBoard = [&](const FProp& Board, FName Yard, int32& OutValue,
		FString& OutText) -> bool
	{
		const AActor* const A = Board.Actor.Get();
		if (A == nullptr)
		{
			ReadFailGate = TEXT("TheYardsOwnPropsAreStillThere");
			Why = FString::Printf(TEXT("%s has no counter board any more, and a yard "
				"without one has no number for anybody to read"), *Yard.ToString());
			return false;
		}
		OutText = ReadDisplay(A, TEXT("Board"));
		if (!ReadTokenInt(OutText, TEXT("banked"), OutValue))
		{
			Why = FString::Printf(TEXT("the counter board in %s reads [%s], which does "
				"not say what has been banked in the wording the yard prints"),
				*Yard.ToString(), *OutText);
			return false;
		}
		int32 Mirror = 0;
		if (!GetIntProp(A, TEXT("LastShownTotal"), Mirror) || Mirror != OutValue)
		{
			Why = FString::Printf(TEXT("the counter board in %s reads [%s] but reports "
				"its own last shown total as %d"), *Yard.ToString(), *OutText, Mirror);
			return false;
		}
		return true;
	};

	if (!ReadBoard(NearBoardProp, NearYard, Out.NearBoard, Out.NearBoardText))
	{
		return false;
	}
	FString FarText;
	if (!ReadBoard(FarBoardProp, FarYard, Out.FarBoard, FarText))
	{
		return false;
	}

	auto ReadPostRow = [&](const FProp* Row, int32 Count, FPostRead* OutRow) -> bool
	{
		for (int32 i = 0; i < Count; ++i)
		{
			OutRow[i].Id = Row[i].Id;
			const AActor* const A = Row[i].Actor.Get();
			if (A == nullptr)
			{
				// A POST THAT HAS BEEN REMOVED FROM THE WORLD IS NOT A POST THAT IS
				// "GONE". Being taken hides a post's pillar and its number and leaves
				// the patch of ground it stood on there to walk over -- which is what
				// the prompt describes and what RetakenPostAddsNothing depends on --
				// while destroying the actor takes the ground away too.
				//
				// This used to be tolerated here and refused, one rebuild later, by
				// ResolveYards' "five posts and three" count: a destroy-based
				// submission graded green through the whole opening stretch and then
				// failed under a gate whose value it had never been told. The two
				// halves now agree, the prompt states the rule outright ("never take
				// one out of the world"), and the failure names the right gate at the
				// first sample instead of the wrong one much later.
				ReadFailGate = TEXT("TheYardsOwnPropsAreStillThere");
				Why = FString::Printf(TEXT("the post called %s is not in the yard at "
					"all any more. The yard always has exactly its own five posts: a "
					"post that has been taken is still one of them, standing or not, "
					"and the patch of ground it stood on is still there to walk over"),
					*Row[i].Id.ToString());
				return false;
			}
			OutRow[i].bPresent = true;

			bool bVisible = false;
			if (!ReadPillarVisible(A, bVisible))
			{
				Why = FString::Printf(TEXT("the post called %s has nothing anybody "
					"could see standing there"), *Row[i].Id.ToString());
				return false;
			}
			bool bMirrorStanding = false;
			if (!GetBoolProp(A, TEXT("bLastShownStanding"), bMirrorStanding)
				|| bMirrorStanding != bVisible)
			{
				Why = FString::Printf(TEXT("the post called %s is %s but reports "
					"itself as %s"), *Row[i].Id.ToString(),
					bVisible ? TEXT("standing") : TEXT("gone"),
					bMirrorStanding ? TEXT("standing") : TEXT("gone"));
				return false;
			}
			OutRow[i].bStanding = bVisible;

			const FString SignText = ReadDisplay(A, TEXT("WorthSign"));
			int32 Shown = 0;
			if (!ReadTokenInt(SignText, TEXT("worth"), Shown))
			{
				Why = FString::Printf(TEXT("the number over the post called %s reads "
					"[%s], which does not say what it is worth in the wording the yard "
					"prints"), *Row[i].Id.ToString(), *SignText);
				return false;
			}
			int32 Mirror = 0;
			if (!GetIntProp(A, TEXT("LastShownWorth"), Mirror) || Mirror != Shown)
			{
				Why = FString::Printf(TEXT("the number over the post called %s reads "
					"[%s] but the post reports last showing %d"),
					*Row[i].Id.ToString(), *SignText, Mirror);
				return false;
			}
			OutRow[i].ShownWorth = Shown;
		}
		return true;
	};

	if (!ReadPostRow(NearPosts, kNearPosts, Out.Near))
	{
		return false;
	}
	if (!ReadPostRow(FarPostProps, kFarPosts, Out.Far))
	{
		return false;
	}

	for (int32 i = 0; i < kPads; ++i)
	{
		const AActor* const A = PadProps[i].Actor.Get();
		Out.Pad[i].Id = PadProps[i].Id;
		Out.Pad[i].Order = PadProps[i].Order;
		if (A == nullptr)
		{
			ReadFailGate = TEXT("TheYardsOwnPropsAreStillThere");
			Why = FString::Printf(TEXT("the pad called %s is gone; the marks are the "
				"yard's and are not yours to take away"), *PadProps[i].Id.ToString());
			return false;
		}
		bool bLit = false;
		if (!ReadLampLit(A, bLit))
		{
			Why = FString::Printf(TEXT("the pad called %s has no lamp anybody could "
				"see"), *PadProps[i].Id.ToString());
			return false;
		}
		bool bMirror = false;
		if (!GetBoolProp(A, TEXT("bLastShownLit"), bMirror) || bMirror != bLit)
		{
			Why = FString::Printf(TEXT("the lamp on the pad called %s is %s but the pad "
				"reports it as %s"), *PadProps[i].Id.ToString(),
				LampWord(bLit), LampWord(bMirror));
			return false;
		}
		Out.Pad[i].bLit = bLit;
		Out.Pad[i].Loc = A->GetActorLocation();
	}
	return true;
}

bool AMemoryYardFunctionalTest::ProbeOpening(const FWorldRead& Now)
{
	// ATTRIBUTED OR SCORED, AND THE WIPE DECIDES WHICH. The reason this probe exists is
	// that a day written down SURVIVES THE WORKDIR: on a second run in the same workdir
	// a correct submission would restore yesterday's yard at t = 0 and be failed for
	// having obeyed the prompt. That explanation is only available when the wipe could
	// not reach the store -- so when the wipe verifiably emptied it before anything
	// began play, the leftover-record account is RULED OUT and what is left is the
	// submission's own code repainting the posts, hiding them, or moving the board
	// before it was asked to. That is reachable from Source/ThirdPerson/ and is scored.
	//
	// The alternative -- attributing every mismatch to the workdir -- hands any
	// submission a denominator opt-out that needs no correct behaviour at all: repaint
	// a post in BeginPlay and the run goes UNGRADED instead of FAILED. Ambiguity
	// resolves toward GRADED (the repo conventions, the verdict contract); this splits the
	// ambiguity at the only place it can be measured.
	//
	// DELIBERATELY NOT PROBED HERE: which lamp is burning. A yard nobody has visited
	// shows the first pad's lamp, but an EMPTY submission leaves every lamp dark -- so
	// probing lamps here would turn the empty leg into a non-graded Error instead of
	// the FAIL it has to be. The opening lamp is graded, as a scored FAIL, by
	// ColdReopenForgetsEverything.
	bool bAsStaged = (Now.NearBoard == 0) && (Now.FarBoard == 0);
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		bAsStaged = bAsStaged && Now.Near[i].bPresent && Now.Near[i].bStanding
			&& Now.Near[i].ShownWorth == Set->Rounds[0].Near[i];
	}
	for (int32 i = 0; i < kFarPosts; ++i)
	{
		bAsStaged = bAsStaged && Now.Far[i].bPresent && Now.Far[i].bStanding
			&& Now.Far[i].ShownWorth == Set->Rounds[0].Far[i];
	}
	if (bAsStaged)
	{
		return true;
	}

	FString Shown;
	FString Staged;
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		Shown += FString::Printf(TEXT("%s %d%s "), *Now.Near[i].Id.ToString(),
			Now.Near[i].ShownWorth, Now.Near[i].bStanding ? TEXT("") : TEXT("(gone)"));
		Staged += FString::Printf(TEXT("%s %d "), *NearPosts[i].Id.ToString(),
			Set->Rounds[0].Near[i]);
	}
	if (!bDurableStoreEmptyAtOpen)
	{
		// The wipe did not leave the store empty, so a day written down by an earlier
		// run in this workdir is live and is the likely cause. NOT the model's fault.
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard did not open on the numbers the "
				 "fixture staged, and the project's save-game directory was still "
				 "there after the fixture tried to empty it. Board %d (expected 0), "
				 "far board %d (expected 0), posts %s-- expected %s. A record left "
				 "behind on disk by an earlier run in this workdir is the usual "
				 "cause; run it in a clean workdir before believing anything else"),
			Now.NearBoard, Now.FarBoard, *Shown, *Staged));
		return false;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("SessionTallyTracksExactly: the yard painted %s-- and should have opened "
			 "on exactly that, with both counter boards reading 0 and all five posts "
			 "standing; it opened showing %s, near board %d, far board %d. Nobody has "
			 "walked into anything yet, and the project's save-game directory was "
			 "verified EMPTY before the first thing began play, so there is nothing "
			 "written down anywhere for the yard to have opened on. What a post is "
			 "worth, and whether it is standing, are the yard's business until "
			 "somebody walks into it"),
		*Staged, *Shown, Now.NearBoard, Now.FarBoard));
	return false;
}

// ---------------------------------------------------------------------------
// The walk
// ---------------------------------------------------------------------------

FVector AMemoryYardFunctionalTest::LanePointFor(const FVector& Where) const
{
	return FVector(Where.X, LaneY, Where.Z);
}

FVector AMemoryYardFunctionalTest::StandPointFor(const FProp& Post) const
{
	const FVector Home = Post.Home.GetLocation();
	FVector Dir = (LanePointFor(Home) - Home).GetSafeNormal2D();
	if (Dir.IsNearlyZero())
	{
		Dir = FVector(0.0, -1.0, 0.0);
	}
	return Home + Dir * kPostStandInsetUu;
}

void AMemoryYardFunctionalTest::BuildRoute(int32 FirstVisit, int32 VisitCount,
	bool bLaneReturnFirst, bool bGateAtEnd)
{
	Route.Reset();
	Waypoint = 0;
	DwellUntil = -1.0;
	bHaveWas = false;
	if (!Hero.IsValid())
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const double Z = Here.Z;

	// EVERY TRAVERSE RUNS ALONG THE LANE. The posts are one side of it and the pads the
	// other, so a runner that always comes back to the lane before moving on can never
	// clip a prop the step is not about. That is a property of the ROUTE, not of the
	// level's numbers, so it survives both rebuilds moving everything.
	if (bLaneReturnFirst)
	{
		FLeg Back;
		Back.Target = FVector(Here.X, LaneY, Z);
		Back.Dwell = kLaneReturnS;
		Back.Kind = 4;
		Route.Add(Back);
	}

	for (int32 k = 0; k < VisitCount; ++k)
	{
		const int32 Index = FirstVisit + k;
		if (!Visits.IsValidIndex(Index))
		{
			break;
		}
		const FVisit& V = Visits[Index];
		const FProp& P = (V.Kind == EVisit::StandOnPad) ? PadProps[V.Index]
														: NearPosts[V.Index];
		const FVector Home = P.Home.GetLocation();

		FLeg Before;
		Before.Target = FVector(Home.X, LaneY, Z);
		Before.Dwell = kLaneBeforeS;
		Before.Kind = 0;
		Before.Visit = Index;
		Route.Add(Before);

		FLeg On;
		// The pad is stood ON; the post is stood IN FRONT OF, inside its ground and
		// clear of its pillar, so a STANDING post never jams the walk.
		On.Target = (V.Kind == EVisit::StandOnPad) ? FVector(Home.X, Home.Y, Z)
												   : StandPointFor(P);
		On.Target.Z = Z;
		On.Dwell = kOnTargetS;
		On.Kind = 1;
		On.Visit = Index;
		Route.Add(On);

		FLeg After = Before;
		After.Dwell = kLaneAfterS;
		After.Kind = 2;
		Route.Add(After);
	}

	if (bGateAtEnd)
	{
		FLeg Gate;
		Gate.Target = FVector(GatePoint.X, LaneY, Z);
		Gate.Dwell = kGateDwellS;
		Gate.Kind = 3;
		Route.Add(Gate);
	}
}

bool AMemoryYardFunctionalTest::CheckRouteIsWalkable()
{
	// A route that walks through a pillar jams the runner and the run simply stops,
	// which reads as the submission's fault. A leg that clips a pad the step is not
	// about moves a mark nobody asked to move. Both are the YARD's fault, so both are
	// an attributed Error.
	TArray<TPair<FName, FVector>> Props;
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		Props.Add({ NearPosts[i].Id, NearPosts[i].Home.GetLocation() });
	}
	for (int32 i = 0; i < kPads; ++i)
	{
		Props.Add({ PadProps[i].Id, PadProps[i].Home.GetLocation() });
	}

	auto PropOfLeg = [this](const FLeg& L) -> FName
	{
		if (L.Kind != 1 || !Visits.IsValidIndex(L.Visit))
		{
			return NAME_None;
		}
		const FVisit& V = Visits[L.Visit];
		return (V.Kind == EVisit::StandOnPad) ? PadProps[V.Index].Id
											  : NearPosts[V.Index].Id;
	};

	for (int32 s = 0; s < Route.Num(); ++s)
	{
		const FName About = PropOfLeg(Route[s]);
		for (const TPair<FName, FVector>& Prop : Props)
		{
			if (Prop.Key == About)
			{
				continue;
			}
			const double D = FVector::Dist2D(Route[s].Target, Prop.Value);
			if (D < kMinPropClearanceUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: waypoint %d stands %.0f uu from %s, "
						 "which this step is not about; the runner would be standing "
						 "on it"), s, D, *Prop.Key.ToString()));
				return false;
			}
		}
		for (const FProp* Board : { &NearBoardProp, &FarBoardProp })
		{
			const double D = FVector::Dist2D(Route[s].Target,
				Board->Home.GetLocation());
			if (D < kMinBoardClearanceUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: waypoint %d stands %.0f uu from a "
						 "counter board; the runner would be pushing it"), s, D));
				return false;
			}
		}
	}

	for (int32 s = 0; s + 1 < Route.Num(); ++s)
	{
		const FName AboutA = PropOfLeg(Route[s]);
		const FName AboutB = PropOfLeg(Route[s + 1]);
		constexpr int32 kSamples = 40;
		for (int32 k = 0; k <= kSamples; ++k)
		{
			const FVector P = FMath::Lerp(Route[s].Target, Route[s + 1].Target,
				double(k) / double(kSamples));
			for (const TPair<FName, FVector>& Prop : Props)
			{
				if (Prop.Key == AboutA || Prop.Key == AboutB)
				{
					continue;
				}
				const double D = FVector::Dist2D(P, Prop.Value);
				if (D < kMinPropClearanceUu)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walk from waypoint %d to %d "
							 "passes %.0f uu from %s, which neither step is about"),
						s, s + 1, D, *Prop.Key.ToString()));
					return false;
				}
			}
		}
	}
	return true;
}

void AMemoryYardFunctionalTest::DriveHero(double Now)
{
	if (!Hero.IsValid())
	{
		return;
	}
	if (!Route.IsValidIndex(Waypoint))
	{
		if (ReopenIndex >= Reopens.Num() && VisitsDone >= Visits.Num())
		{
			FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
				TEXT("The yard remembered: %d steps on staged set %d, the yard shut and "
					 "rebuilt %d times -- once with the record left alone, once with an "
					 "earlier copy of it put back, once with it thrown away -- and "
					 "every board, number, pillar and lamp told the truth throughout"),
				VisitsDone, SetIndex, ReopenIndex));
		}
		return;
	}

	const FLeg Leg = Route[Waypoint];
	const double Tol = (Leg.Kind == 1) ? kOnTargetTolUu : kWaypointUu;
	const FVector Here = Hero->GetActorLocation();
	const FVector Flat(Leg.Target.X - Here.X, Leg.Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() > Tol)
	{
		// THE SAME INPUT PATH A HUMAN USES.
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		return;
	}
	if (DwellUntil < 0.0)
	{
		// STAND here. Every gate is about a state that has settled, and a route that
		// only passes through a spot never gives the yard a chance to be judged.
		DwellUntil = Now + Leg.Dwell;
		return;
	}
	if (Now < DwellUntil)
	{
		return;
	}

	const EGate Gate = Visits.IsValidIndex(Leg.Visit) ? Visits[Leg.Visit].Grade
													 : EGate::None;
	if (Leg.Kind == 0 || Leg.Kind == 2)
	{
		FWorldRead Sample;
		FString Why;
		if (!ReadWorld(Sample, Why))
		{
			// A prop that has been removed from the world is TheYardsOwnPropsAreStill-
			// There's business, not the business of whichever gate is in flight.
			FailUnderGate(ReadFailGate != nullptr ? ReadFailGate : GateName(Gate), Why);
			return;
		}
		if (Leg.Kind == 0 && !bOpeningProbed)
		{
			bOpeningProbed = true;
			if (!ProbeOpening(Sample))
			{
				return;
			}
		}
		if (!GaugeTwinYard(Sample))
		{
			return;
		}
		if (Leg.Kind == 0)
		{
			Was = Sample;
			bHaveWas = true;
		}
		else if (bHaveWas)
		{
			GradeVisit(Visits[Leg.Visit], Was, Sample);
			if (!IsRunning())
			{
				return;
			}
			++VisitsDone;
			bHaveWas = false;
			// The fixture's OWN record of what the runner did, never read back off the
			// submission: standing on a pad is the runner's act, not the yard's.
			if (Visits[Leg.Visit].Kind == EVisit::StandOnPad)
			{
				MarkedPadId = PadProps[Visits[Leg.Visit].Index].Id;
			}
			if (Visits[Leg.Visit].bSnapshotAfter)
			{
				// A MOMENT AFTER THE COUNTER BOARD FIRST ROSE, and after the runner has
				// settled clear of the post and the yard has been read once. The prompt
				// discloses this moment, so a submission that has not written the day
				// down by now is failing a stated contract, not an ambush.
				SnapshotDurableStores();
			}
		}
	}
	else if (Leg.Kind == 3)
	{
		RebuildBothYards(Now);
		return;
	}

	++Waypoint;
	DwellUntil = -1.0;
}

// ---------------------------------------------------------------------------
// The yard is carried away and rebuilt
// ---------------------------------------------------------------------------

void AMemoryYardFunctionalTest::RebuildBothYards(double Now)
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the yard could not be put back together"));
		return;
	}
	bYardDown = true;
	++ReopenIndex;

	struct FRebuild
	{
		UClass* Cls = nullptr;
		FTransform Where;
		FName Yard = NAME_None;
		FName Id = NAME_None;
		int32 Order = 0;
		int32 Worth = 0;
	};

	const FRound& Round = RoundFor(ReopenIndex);
	TArray<FRebuild> Plan;
	RebuildClasses.Reset();

	// HOW FAR ALONG ITS OWN ROW EVERY PROP MOVES THIS TIME. Never zero, so nothing is
	// ever found where it was left -- and 1, 1, 2 rather than 1, 1, 1 because a row of
	// three (the pads, and the far yard's posts) walked three single places would land
	// every one of them back on its ORIGINAL slot at the third reopening, handing a
	// position-keyed restore a free pass at the one rebuild it is most likely to
	// survive. Cumulative offsets are 1, 2, 1 for a row of three and 1, 2, 4 for the
	// row of five: never the identity, at any reopening, in any row.
	const int32 Shift = (ReopenIndex >= 3) ? 2 : 1;
	auto Rotate = [Shift](const FProp* Row, int32 Count, int32 i) -> FTransform
	{
		// Rotating among the slots the props are already on needs no knowledge of the
		// level at all.
		return Row[(i + Shift) % Count].Home;
	};

	for (int32 i = 0; i < kNearPosts; ++i)
	{
		FRebuild R;
		R.Cls = NearPosts[i].Cls;
		R.Where = Rotate(NearPosts, kNearPosts, i);
		R.Yard = NearYard;
		R.Id = NearPosts[i].Id;
		R.Worth = Round.Near[i];
		Plan.Add(R);
	}
	for (int32 i = 0; i < kFarPosts; ++i)
	{
		FRebuild R;
		R.Cls = FarPostProps[i].Cls;
		R.Where = Rotate(FarPostProps, kFarPosts, i);
		R.Yard = FarYard;
		R.Id = FarPostProps[i].Id;
		R.Worth = Round.Far[i];
		Plan.Add(R);
	}
	const int32 FirstPad = Plan.Num();
	for (int32 i = 0; i < kPads; ++i)
	{
		FRebuild R;
		R.Cls = PadProps[i].Cls;
		R.Where = Rotate(PadProps, kPads, i);
		R.Yard = NearYard;
		R.Id = PadProps[i].Id;
		R.Order = PadProps[i].Order;
		Plan.Add(R);
	}
	const int32 FirstBoard = Plan.Num();
	for (const FProp* Board : { &NearBoardProp, &FarBoardProp })
	{
		FRebuild R;
		R.Cls = Board->Cls;
		// The boards move too, along the row they stand in. GUARDED: a shift that
		// would land near anything the walk touches falls back to standing still, so
		// this can never wreck a route, and nothing is graded on where a board is.
		FTransform Shifted = Board->Home;
		const int32 Which = FMath::Clamp(ReopenIndex - 1, 0,
			int32(UE_ARRAY_COUNT(kBoardShiftUu)) - 1);
		FVector Candidate = Board->Home.GetLocation()
			+ FVector(kBoardShiftUu[Which], 0.0, 0.0);
		bool bSafe = FMath::Abs(Candidate.Y - LaneY) > 400.0;
		for (const FRebuild& Other : Plan)
		{
			bSafe = bSafe && FVector::Dist2D(Candidate, Other.Where.GetLocation())
				> kMinPropClearanceUu + kMinBoardClearanceUu;
		}
		if (bSafe)
		{
			Shifted.SetLocation(Candidate);
		}
		R.Where = Shifted;
		R.Yard = (Board == &NearBoardProp) ? NearYard : FarYard;
		Plan.Add(R);
	}
	for (const FRebuild& R : Plan)
	{
		if (R.Cls == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a prop could not be put back because "
					 "nothing remembers what kind of thing it was"));
			return;
		}
		RebuildClasses.Add(R.Cls);
	}

	// ---- (1) the yard is taken away -------------------------------------------
	// Every prop's EndPlay runs here -- a perfectly legitimate place for a submission
	// to write the day down, which is why the record is not taken away until after it.
	auto Kill = [](FProp& P)
	{
		if (AActor* const A = P.Actor.Get())
		{
			A->Destroy();
		}
		P.Actor = nullptr;
	};
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		Kill(NearPosts[i]);
	}
	for (int32 i = 0; i < kFarPosts; ++i)
	{
		Kill(FarPostProps[i]);
	}
	for (int32 i = 0; i < kPads; ++i)
	{
		Kill(PadProps[i]);
	}
	Kill(NearBoardProp);
	Kill(FarBoardProp);

	// ---- (2) whatever this reopening does to the written record ---------------
	// AFTER the closing writes rather than before them.
	//
	// DELIBERATE DEVIATION from the order the spec's build brief states (act on the
	// record, then destroy). Acting first would leave a submission that batches its
	// write into EndPlay holding a record the fixture never touched -- and that
	// submission would then open on stale state and be failed for having done exactly
	// what the prompt asked. Acting after the closing writes is both stronger (nothing
	// on disk survives the closing writes either) and fairer. The spec's actual
	// requirement -- no gap in which a timer-flushing solution can re-create the record
	// -- is preserved: all three phases are one tick, adjacent statements, with nothing
	// else running in between.
	//
	// WHICH of the three happens is the STAGED SET's business, not this function's. The
	// old code hard-wired "the second one is the cold one", which made the shape of the
	// day a constant a submission could count instead of reading the record.
	const ERebuild Kind = Reopens.IsValidIndex(ReopenIndex - 1)
		? Reopens[ReopenIndex - 1].Kind : ERebuild::Warm;
	switch (Kind)
	{
	case ERebuild::Warm:
		break;                                   // the record is left exactly as it is
	case ERebuild::Rewind:
		if (!bHaveSnapshot)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the yard was asked to reopen on an earlier "
					 "copy of the written record and no copy was ever taken"));
			return;
		}
		RestoreDurableStores();
		break;
	case ERebuild::Cold:
		WipeDurableStores(/*bRecordEmptiness=*/false);
		break;
	}

	// ---- (3) a brand new yard, on each other's slots, repainted ---------------
	for (int32 i = 0; i < Plan.Num(); ++i)
	{
		const FRebuild& R = Plan[i];
		// OverrideRootScale, not the default MultiplyWithRoot: the transform captured
		// off the destroyed prop already carries whatever root scale it had, and
		// multiplying it by the fresh actor's default would spawn it at the square of
		// that scale -- with its trigger volume scaled to match.
		AActor* const A = World->SpawnActorDeferred<AActor>(R.Cls, R.Where, nullptr,
			nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn,
			ESpawnActorScaleMethod::OverrideRootScale);
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s could not be put back"),
				R.Id.IsNone() ? TEXT("a counter board") : *R.Id.ToString()));
			return;
		}
		// DEFERRED on purpose: a fresh prop paints itself in BeginPlay, so what it is
		// called, which yard it is in and what is painted over it all have to be on it
		// BEFORE that runs, or a correct submission would be failed for the fixture's
		// own ordering.
		SetNameProp(A, TEXT("YardName"), R.Yard);
		if (i < FirstPad)
		{
			SetNameProp(A, TEXT("PostId"), R.Id);
			SetIntProp(A, TEXT("WorthNow"), R.Worth);
		}
		else if (i < FirstBoard)
		{
			SetNameProp(A, TEXT("PadId"), R.Id);
			SetIntProp(A, TEXT("PadOrder"), R.Order);
		}
		A->FinishSpawning(R.Where);
	}

	if (!ResolveYards(false))
	{
		return;
	}
	bYardDown = false;
	RebuiltAt = Now;
	bAwaitingReopenGrade = true;
	Route.Reset();
	Waypoint = 0;
	DwellUntil = -1.0;
	bHaveWas = false;
}

// ---------------------------------------------------------------------------
// Grading
// ---------------------------------------------------------------------------

void AMemoryYardFunctionalTest::GradeVisit(const FVisit& Visit, const FWorldRead& Before,
	const FWorldRead& After)
{
	switch (Visit.Grade)
	{
	case EGate::SessionTallyTracksExactly:
	{
		// EVERYTHING THE OPENING STRETCH WAS SUPPOSED TO DO, read off the boards, the
		// pillars and the lamps in one settled sample. The state it is compared against
		// is the one the simulated day says the yard shuts in.
		if (!Reopens.IsValidIndex(0))
		{
			return;
		}
		const FYardState& Exp = Reopens[0].Was;
		TArray<FName> Taken;
		TArray<FName> Standing;
		FString Terms;
		for (int32 i = 0; i < kNearPosts; ++i)
		{
			if (Exp.bTaken[i])
			{
				Taken.Add(NearPosts[i].Id);
				Terms += FString::Printf(TEXT("%s%d"),
					Terms.IsEmpty() ? TEXT("") : TEXT("+"), Exp.WorthWhenTaken[i]);
			}
			if (After.Near[i].bStanding)
			{
				Standing.Add(After.Near[i].Id);
			}
		}
		// THE BOARD FIRST, always: an empty submission is wrong about everything at
		// this sample, and a fixed order is what makes its named failure the same one
		// every time.
		if (After.NearBoard != Exp.Board)
		{
			FailUnderGate(TEXT("SessionTallyTracksExactly"), FString::Printf(
				TEXT("the counter board should read %d after taking posts %s (worth "
					 "%s), it reads %d; posts still standing: %s"),
				Exp.Board, *NameList(Taken), *Terms, After.NearBoard,
				*NameList(Standing)));
			return;
		}
		for (int32 i = 0; i < kNearPosts; ++i)
		{
			const bool bShouldStand = !Exp.bTaken[i];
			if (After.Near[i].bStanding != bShouldStand)
			{
				FailUnderGate(TEXT("SessionTallyTracksExactly"), FString::Printf(
					TEXT("exactly the posts walked into should be gone. %s were walked "
						 "into; %s is %s"), *NameList(Taken),
					*After.Near[i].Id.ToString(),
					bShouldStand ? TEXT("gone and was never touched")
								 : TEXT("still standing")));
				return;
			}
			if (bShouldStand && After.Near[i].ShownWorth != Set->Rounds[0].Near[i])
			{
				FailUnderGate(TEXT("SessionTallyTracksExactly"), FString::Printf(
					TEXT("the yard painted %s with %d and the number over it reads %d. "
						 "What a post is worth is the yard's business, never yours to "
						 "write"), *After.Near[i].Id.ToString(), Set->Rounds[0].Near[i],
					After.Near[i].ShownWorth));
				return;
			}
		}
		for (int32 i = 0; i < kPads; ++i)
		{
			const bool bShouldBurn = (After.Pad[i].Order == Exp.MarkedPad);
			if (After.Pad[i].bLit != bShouldBurn)
			{
				FailUnderGate(TEXT("SessionTallyTracksExactly"), FString::Printf(
					TEXT("the last pad stood on was pad %d, so its lamp and no other "
						 "should be burning; the lamp on %s (pad %d) is %s"),
					Exp.MarkedPad, *After.Pad[i].Id.ToString(), After.Pad[i].Order,
					LampWord(After.Pad[i].bLit)));
				return;
			}
		}
		return;
	}

	case EGate::RetakenPostAddsNothing:
	{
		// BYTE-IDENTICAL TO THE SAMPLE TAKEN ON THE LANE A MOMENT EARLIER. Comparing
		// against the settled reading immediately before the walk-through, rather than
		// against a text remembered from the reopening, keeps the claim exactly what
		// the prompt states -- walking back through changes nothing -- wherever in the
		// day the step happens to fall.
		const FName Id = NearPosts[Visit.Index].Id;
		if (After.NearBoardText != Before.NearBoardText)
		{
			FailUnderGate(TEXT("RetakenPostAddsNothing"), FString::Printf(
				TEXT("the counter board read [%s] before the runner walked back through "
					 "the ground %s stood on and reads [%s] after. A post that is "
					 "already gone is worth nothing at all"),
				*Before.NearBoardText, *Id.ToString(), *After.NearBoardText));
			return;
		}
		if (After.Near[Visit.Index].bStanding)
		{
			FailUnderGate(TEXT("RetakenPostAddsNothing"), FString::Printf(
				TEXT("%s was taken earlier in the day, and after walking back through "
					 "the ground it stood on there is a post called %s standing there "
					 "again"), *Id.ToString(), *Id.ToString()));
			return;
		}
		return;
	}

	case EGate::UntakenPostStillAddsAfterReopen:
	{
		const int32 i = Visit.Index;
		const int32 Staged = Visit.Worth;
		const FName Id = NearPosts[i].Id;
		// BOTH HALVES FACE THE FIXTURE. "What is shown equals what the post says" is
		// satisfied by a submission that wrote a remembered number over a fresh post,
		// so the amount banked and the number shown are each compared against what the
		// fixture painted, never against the post's own property.
		if (Before.Near[i].ShownWorth != Staged)
		{
			FailUnderGate(TEXT("UntakenPostStillAddsAfterReopen"), FString::Printf(
				TEXT("the yard repainted %s with %d when it rebuilt, and the number "
					 "over it read %d when the runner walked in. The numbers over the "
					 "posts are the yard's to paint"),
				*Id.ToString(), Staged, Before.Near[i].ShownWorth));
			return;
		}
		if (After.NearBoard - Before.NearBoard != Staged)
		{
			FailUnderGate(TEXT("UntakenPostStillAddsAfterReopen"), FString::Printf(
				TEXT("%s was standing and painted with %d, so taking it should have "
					 "carried the counter board from %d to %d; it reads %d. The "
					 "reopened yard has to be live, not a picture of one"),
				*Id.ToString(), Staged, Before.NearBoard, Before.NearBoard + Staged,
				After.NearBoard));
			return;
		}
		if (After.Near[i].bStanding)
		{
			FailUnderGate(TEXT("UntakenPostStillAddsAfterReopen"), FString::Printf(
				TEXT("the runner walked into %s and it is still standing there"),
				*Id.ToString()));
			return;
		}
		return;
	}

	case EGate::LatestPadMovesAfterReopen:
	{
		const FName Stood = PadProps[Visit.Index].Id;
		const int32 Order = Visit.Index + 1;
		for (int32 i = 0; i < kPads; ++i)
		{
			const bool bShouldBurn = (After.Pad[i].Id == Stood);
			if (After.Pad[i].bLit != bShouldBurn)
			{
				FailUnderGate(TEXT("LatestPadMovesAfterReopen"), FString::Printf(
					TEXT("the runner stood on %s (pad %d) after the yard reopened, so "
						 "its lamp and no other should be burning; the lamp on %s "
						 "(pad %d) is %s"), *Stood.ToString(), Order,
					*After.Pad[i].Id.ToString(), After.Pad[i].Order,
					LampWord(After.Pad[i].bLit)));
				return;
			}
		}
		return;
	}

	case EGate::ColdYardTakesAgain:
	{
		const int32 i = Visit.Index;
		const FName Id = NearPosts[i].Id;
		if (Before.NearBoard != 0)
		{
			FailUnderGate(TEXT("ColdYardTakesAgain"), FString::Printf(
				TEXT("the counter board read %d in a yard that had to open as if it had "
					 "never been visited"), Before.NearBoard));
			return;
		}
		if (After.NearBoard != Visit.BoardAfter)
		{
			FailUnderGate(TEXT("ColdYardTakesAgain"), FString::Printf(
				TEXT("%s is painted with %d in the emptied yard, so taking it should "
					 "carry the counter board from 0 to %d; it reads %d. A yard that "
					 "forgot everything still has to be live"),
				*Id.ToString(), Visit.Worth, Visit.BoardAfter, After.NearBoard));
			return;
		}
		if (After.Near[i].bStanding)
		{
			FailUnderGate(TEXT("ColdYardTakesAgain"), FString::Printf(
				TEXT("the runner walked into %s in the emptied yard and it is still "
					 "standing there"), *Id.ToString()));
			return;
		}
		return;
	}

	default:
		return;
	}
}

void AMemoryYardFunctionalTest::GradeReopen(const FWorldRead& Now)
{
	// ONE FUNCTION, THREE KINDS OF REOPENING. Every reopening asks the same three
	// questions -- which posts are gone, what the counter board reads, where the runner
	// is standing and which lamp burns -- and only the answer the WRITTEN RECORD gives
	// differs between them:
	//
	//   WARM   the record was left alone, so the yard comes back as it stood;
	//   REWIND an earlier copy of the record was put back, so the yard comes back as it
	//          stood THEN -- a state a warm memory cannot produce, because memory moved
	//          on and the copy did not. This is the gate that grades what is IN the
	//          record: a submission whose file is a token and whose memory is the truth
	//          reopens on its memory and is wrong in all three readings.
	//   COLD   the record was thrown away, so the yard opens as if never visited.
	//
	// The kind in force is the STAGED SET's, and the sets order the three differently,
	// so nothing here is countable.
	if (!Reopens.IsValidIndex(ReopenIndex - 1))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the yard reopened more times than the day says "
				 "it should have"));
		return;
	}
	const FReopen& R = Reopens[ReopenIndex - 1];
	const TCHAR* const Because = ReopenBecause(R.Kind);

	// ---- exactly the posts the record says are gone ---------------------------
	// KEYED ON THE NAME THE POST CARRIES, never on index, spawn order or where it
	// stands: everything came back on somebody else's slot.
	TArray<FName> Should;
	TArray<FName> Gone;
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		if (R.Expect.bTaken[i])
		{
			Should.Add(NearPosts[i].Id);
		}
		if (!Now.Near[i].bStanding)
		{
			Gone.Add(Now.Near[i].Id);
		}
	}
	const FString ShouldPhrase = (Should.Num() == 0)
		? FString(TEXT("every post should be standing and takeable"))
		: FString::Printf(TEXT("exactly %s should be gone and the rest standing and "
			"takeable"), *NameList(Should));
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		if (Now.Near[i].bStanding == R.Expect.bTaken[i])
		{
			FailUnderGate(ReopenGateName(R.Kind, EClaim::Posts), FString::Printf(
				TEXT("%s -- so %s; %s are gone. The yard was standing at %s gone when "
					 "it shut, and everything came back on a different slot, so a post "
					 "is known by the name it carries and by nothing else"),
				Because, *ShouldPhrase, *NameList(Gone), *NameList(Should)));
			return;
		}
	}

	// ---- the board reads what the record says, not what the posts show now ----
	if (Now.NearBoard != R.Expect.Board)
	{
		FailUnderGate(ReopenGateName(R.Kind, EClaim::Board), FString::Printf(
			TEXT("%s -- so the counter board reads %d; it reads %d. The yard was "
				 "standing at %d when it shut. A total re-derived from the freshly "
				 "painted numbers over the posts the record says are gone would read "
				 "%d; the sum of all five fresh numbers is %d; the posts gone number "
				 "%d; a yard that never remembered anything reads 0. What was banked "
				 "is history, and the number over a post is news"),
			Because, R.Expect.Board, Now.NearBoard, R.Was.Board, R.RecomputeTotal,
			R.AllFiveTotal, R.TakenCount));
		return;
	}

	// ---- the runner is standing on the mark the record says -------------------
	const FPadRead* Mark = nullptr;
	for (int32 i = 0; i < kPads; ++i)
	{
		if (Now.Pad[i].Order == R.Expect.MarkedPad)
		{
			Mark = &Now.Pad[i];
		}
	}
	if (Mark == nullptr || !Hero.IsValid())
	{
		FailUnderGate(ReopenGateName(R.Kind, EClaim::Placement), FString::Printf(
			TEXT("%s -- and the rebuilt yard has no pad %d for the runner to be "
				 "standing on"), Because, R.Expect.MarkedPad));
		return;
	}
	// AGAINST THE FRESH PAD'S OWN TRANSFORM, never a written-down coordinate: the pads
	// moved when the yard was rebuilt.
	const double D = FVector::Dist2D(Hero->GetActorLocation(), Mark->Loc);
	if (D > kResumeRadiusUu)
	{
		FailUnderGate(ReopenGateName(R.Kind, EClaim::Placement), FString::Printf(
			TEXT("%s -- so the runner stands within %.0f uu of %s (pad %d), which the "
				 "rebuilt yard put at (%.0f,%.0f); the runner is %.0f uu away at "
				 "(%.0f,%.0f). The mark carried out through the gate was pad %d"),
			Because, kResumeRadiusUu, *Mark->Id.ToString(), Mark->Order, Mark->Loc.X,
			Mark->Loc.Y, D, Hero->GetActorLocation().X, Hero->GetActorLocation().Y,
			R.Was.MarkedPad));
		return;
	}
	for (int32 i = 0; i < kPads; ++i)
	{
		const bool bShouldBurn = (Now.Pad[i].Order == R.Expect.MarkedPad);
		if (Now.Pad[i].bLit != bShouldBurn)
		{
			FailUnderGate(ReopenGateName(R.Kind, EClaim::Placement), FString::Printf(
				TEXT("%s -- so the lamp on pad %d and no other burns in the rebuilt "
					 "yard; the lamp on %s (pad %d) is %s"),
				Because, R.Expect.MarkedPad, *Now.Pad[i].Id.ToString(),
				Now.Pad[i].Order, LampWord(Now.Pad[i].bLit)));
			return;
		}
	}
}

bool AMemoryYardFunctionalTest::GaugeTwinYard(const FWorldRead& Now)
{
	// THE IN-SCENE NEGATIVE CONTROL. The far yard is torn down and rebuilt in the same
	// tick as the near one and is never walked into, so anything that changes there is
	// a restore applied to a yard nobody was in.
	const FRound& Round = RoundFor(ReopenIndex);
	for (int32 i = 0; i < kFarPosts; ++i)
	{
		if (!Now.Far[i].bPresent || !Now.Far[i].bStanding)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TwinYardNeverChanges: nobody has ever walked into %s, and the "
					 "post called %s over there is gone"), *FarYard.ToString(),
				*Now.Far[i].Id.ToString()));
			return false;
		}
		if (Now.Far[i].ShownWorth != Round.Far[i])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TwinYardNeverChanges: %s painted the post called %s with %d and "
					 "the number over it reads %d. What the other yard's posts are "
					 "worth is nothing to do with this one"), *FarYard.ToString(),
				*Now.Far[i].Id.ToString(), Round.Far[i], Now.Far[i].ShownWorth));
			return false;
		}
	}
	if (Now.FarBoard != 0)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TwinYardNeverChanges: nothing has ever been banked in %s and its "
				 "counter board reads %d. It is a separate yard"),
			*FarYard.ToString(), Now.FarBoard));
		return false;
	}
	return true;
}

bool AMemoryYardFunctionalTest::CheckRunnerKeepsWalking(double Now)
{
	// Stood down for the rebuild frame and a little after it: a submission that sets
	// the runner down on a pad legitimately teleports it, and a teleport drops a
	// character into a fall for a frame or two. This gate is about somebody being held
	// still, not about that.
	if (bYardDown || (RebuiltAt >= 0.0 && Now < RebuiltAt + kRebuildGraceS))
	{
		return true;
	}
	ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RunnerKeepsWalking: the runner stopped existing part way through the "
				 "day"));
		return false;
	}
	// Each of these is a separate way to hold somebody on a pad, and each is readable.
	// APawn overrides DisableInput to clear bInputEnabled and APawn::InputEnabled() is
	// public, so the "hold the runner still so the placement sticks" answer is caught
	// even though this fixture drives through AddMovementInput rather than the input
	// stack.
	if (!H->InputEnabled())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RunnerKeepsWalking: the runner's controls were taken away part way "
				 "through the day and not given back"));
		return false;
	}
	if (H->IsMoveInputIgnored())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RunnerKeepsWalking: the runner's movement input is being ignored part "
				 "way through the day"));
		return false;
	}
	const UCharacterMovementComponent* const Move = H->GetCharacterMovement();
	if (Move == nullptr || Move->MovementMode == MOVE_None
		|| Move->GetMaxSpeed() <= 0.0f)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RunnerKeepsWalking: the runner can no longer walk (movement mode %d, "
				 "top speed %.0f). Setting somebody down on a pad is not the same as "
				 "holding them there"),
			Move != nullptr ? int32(Move->MovementMode.GetValue()) : -1,
			Move != nullptr ? Move->GetMaxSpeed() : 0.0f));
		return false;
	}
	return true;
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

void AMemoryYardFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}
	if (!StagingFailure.IsEmpty())
	{
		FinishTest(bStagingIsHarnessFault ? EFunctionalTestResult::Error
										  : EFunctionalTestResult::Failed,
			StagingFailure);
		return;
	}
	if (Set == nullptr || !bResolved)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the yards were never staged; the fixture's "
				 "world-init hook did not fire for this world"));
		return;
	}
	if (!ResolveHero())
	{
		return;
	}
	// This fixture drives the runner through AddMovementInput and never presses a key,
	// so a level whose keyboard lane is dead grades exactly like a healthy one -- which
	// is how five of six ThirdPerson maps once shipped authored, lit, certified and
	// completely uncontrollable. Both halves are asserted BY PROPERTY NAME so a
	// subclassed or renamed pawn still answers. HARNESS precondition: the input lane is
	// substrate we ship, never anything the agent was asked to write.
	if (const FString Unwired = DescribeBrokenPlayerInput(World); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. The "
				 "graded drive would still pass, so fix the substrate, not the task."),
			*Unwired));
		return;
	}
	if (!BuildDayTrace())
	{
		return;
	}

	// THE WAY OUT IS THE LEVEL'S, NOT THE RUNNER'S. Derived from the PlayerStart the
	// map ships rather than from wherever the runner is standing when the test starts,
	// because a submission is expressly allowed to set the runner down at the level's
	// FIRST open -- and a gate waypoint that moved with it would be a waypoint the
	// submission chose, in a route CheckRouteIsWalkable can refuse as an attributed
	// Error. A submission must never be able to move a waypoint, least of all into a
	// non-graded verdict. Falls back to the runner's own start when the level has no
	// single PlayerStart, which authoring/author_map.py refuses to save.
	FVector GateFrom = HeroStart;
	{
		TArray<AActor*> Starts;
		UGameplayStatics::GetAllActorsOfClass(World, APlayerStart::StaticClass(), Starts);
		if (Starts.Num() == 1 && Starts[0] != nullptr)
		{
			GateFrom = Starts[0]->GetActorLocation();
		}
	}
	GatePoint = FVector(GateFrom.X - kGateOutUu, LaneY, HeroStart.Z);
	// THE PHASES ARE THE DAY'S, NOT A CONSTANT. How many steps are walked before the
	// yard first shuts, and after each reopening, is whatever the staged set's script
	// says -- the sets differ, and a fixture that hard-coded "five then three then one"
	// would silently mis-slice two of the three.
	Phase = 0;
	BuildRoute(PhaseStart[0], PhaseCount[0], /*bLaneReturnFirst=*/false,
		/*bGateAtEnd=*/true);
	if (Route.Num() == 0)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no walk could be built for this yard"));
		return;
	}
	if (!CheckRouteIsWalkable())
	{
		return;
	}

	// The last entry is a SENTINEL, far past a walk that measures ~160 s at 500 uu/s
	// (eleven steps and three rebuilds), because the base class ends the test the
	// moment the last scheduled checkpoint is sampled. Without it a submission that
	// never lets the walk get anywhere would ride an automatic Success.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kSentinelIndex; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelAtS);
	SetCheckpointSchedule(Schedule);
}

void AMemoryYardFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || Set == nullptr || !bResolved || Visits.Num() == 0)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = (World != nullptr) ? double(World->GetTimeSeconds()) : 0.0;

	if (!CheckRunnerKeepsWalking(Now))
	{
		return;
	}

	if (bAwaitingReopenGrade)
	{
		// NO MOVEMENT INPUT AT ALL while the yard settles. The runner is set down on a
		// pad by the submission's own code, and a drive that kept steering would walk
		// it off the thing it is about to be graded on -- the single easiest way for a
		// fixture to fail correct work.
		if (Now < RebuiltAt + kReopenHoldS)
		{
			return;
		}
		bAwaitingReopenGrade = false;

		FWorldRead Sample;
		FString Why;
		const ERebuild Kind = Reopens.IsValidIndex(ReopenIndex - 1)
			? Reopens[ReopenIndex - 1].Kind : ERebuild::Warm;
		if (!ReadWorld(Sample, Why))
		{
			FailUnderGate(ReadFailGate != nullptr
				? ReadFailGate : ReopenGateName(Kind, EClaim::Posts), Why);
			return;
		}
		if (!GaugeTwinYard(Sample))
		{
			return;
		}
		GradeReopen(Sample);
		if (!IsRunning())
		{
			return;
		}
		++Phase;
		if (!PhaseStart.IsValidIndex(Phase))
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the yard reopened onto a stretch of the day "
					 "that the staged set does not have"));
			return;
		}
		BuildRoute(PhaseStart[Phase], PhaseCount[Phase], /*bLaneReturnFirst=*/true,
			/*bGateAtEnd=*/Phase < Reopens.Num());
		CheckRouteIsWalkable();
		return;
	}

	DriveHero(Now);
}

void AMemoryYardFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString S;
	for (int32 i = 0; i < kNearPosts; ++i)
	{
		bool bStanding = false;
		ReadPillarVisible(NearPosts[i].Actor.Get(), bStanding);
		int32 W = 0;
		GetIntProp(NearPosts[i].Actor.Get(), TEXT("LastShownWorth"), W);
		S += FString::Printf(TEXT("%s[%d%s] "), *NearPosts[i].Id.ToString(), W,
			bStanding ? TEXT("") : TEXT("x"));
	}
	int32 Board = 0;
	GetIntProp(NearBoardProp.Actor.Get(), TEXT("LastShownTotal"), Board);
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-memoryyard calib] cp%d t=%.2f set=%d visits=%d/%d wp=%d/%d reopen=%d "
			 "board=%d mark=%s %sat=(%.0f,%.0f)"),
		Index, Now, SetIndex, VisitsDone, Visits.Num(), Waypoint, Route.Num(),
		ReopenIndex, Board, *MarkedPadId.ToString(), *S, H.X, H.Y);
}

void AMemoryYardFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	// THE IN-SCENE CONTROL, GAUGED AT EVERY CHECKPOINT. Tolerant on purpose: a
	// checkpoint that lands while the yard is being put back reads nothing, and a
	// fixture that failed a run for its own timing would be manufacturing failures.
	// Every graded sample gauges it too, and those are never tolerant.
	if (IsRunning() && !bYardDown && Set != nullptr && bResolved
		&& !(RebuiltAt >= 0.0 && TimeSeconds < RebuiltAt + kReopenHoldS))
	{
		FWorldRead Sample;
		FString Why;
		if (ReadWorld(Sample, Why))
		{
			GaugeTwinYard(Sample);
		}
	}

	if (CheckpointIndex < kSentinelIndex || !IsRunning())
	{
		return;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheYardDayFinished: the day never finished -- %d of %d steps done, the "
			 "yard was rebuilt %d of %d times, and the walk is stuck at waypoint %d of "
			 "%d. Nothing about remembering a yard may take the runner away from the "
			 "player"), VisitsDone, Visits.Num(), ReopenIndex, Reopens.Num(), Waypoint,
		Route.Num()));
}
