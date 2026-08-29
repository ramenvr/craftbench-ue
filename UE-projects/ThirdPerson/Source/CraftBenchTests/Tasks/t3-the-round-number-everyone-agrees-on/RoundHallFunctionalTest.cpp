// Copyright CraftBench. All Rights Reserved.

#include "RoundHallFunctionalTest.h"

#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

// The supplied hall. Included rather than reflected -- see the header, note (5): a
// submission that deletes or renames this file takes a GRADED L1 FAIL instead of being
// handed a HARNESS-PRECONDITION non-verdict.
#include "Tasks/t3-the-round-number-everyone-agrees-on/RoundHallProps.h"

namespace
{
	// ---- DISCLOSED IN THE PROMPT -----------------------------------------
	constexpr double kSignSettleS = 0.5;    // "a sign has half a second to catch up"
	constexpr double kBodyBackS = 2.0;      // "within two seconds a new runner"
	constexpr double kMarkTolUu = 150.0;    // "within 150 centimetres of the middle"
	// "standing on it rather than hanging in the air over it -- its feet within three
	// metres of the mark". DISCLOSED because it gates: an undisclosed vertical bound
	// failed a submission that met every clause the prompt stated (a late respawn with a
	// large spawn lift), and the message below now names it.
	constexpr double kFeetTolUu = 300.0;

	// ---- UNDISCLOSED: fixture clocking and tolerance ----------------------
	// EVERY ONE OF THESE IS A WIDENING OF THE DISCLOSED CONTRACT, NEVER A NARROWING.
	// Two of them also carry an ORDERING duty, which is the only reason they are not
	// simply "the disclosed number times a bit":
	//
	//   kAgreeSuppressS > kRiseDeadlineS   so a cached step is named by the STEP gate
	//                                      rather than by the agreement gate.
	//   kFallSuppressS  > kBodyJudgeS      so a number that did not survive a fall is
	//                                      named by the FALL gate for the same reason.
	constexpr double kRiseDeadlineS = 2.0 * kSignSettleS;     // 1.00 s
	constexpr double kAgreeSuppressS = 2.5 * kSignSettleS;    // 1.25 s
	constexpr double kRaiseGraceS = 2.0 * kSignSettleS;       // 1.00 s
	constexpr double kRaiseSuppressS = 2.5 * kSignSettleS;    // 1.25 s
	constexpr double kBodyJudgeS = kBodyBackS + 0.25;         // 2.25 s
	constexpr double kFallSuppressS = kBodyJudgeS + 0.25;     // 2.50 s
	constexpr double kFallHoldS = 3.50;   // input off for the whole judging window

	// How long the doorplate is left alone after the body in the hall becomes a
	// different object: the two seconds the prompt promises a fresh runner, plus three
	// times the half second it promises a readout. A widening of both.
	constexpr double kDoorGraceS = kBodyBackS + 3.0 * kSignSettleS;   // 3.50 s

	// Nothing is judged before this. The hall opens, the submission's first frame runs,
	// and a sign gets four times the disclosed settle to say something. The empty leg
	// dies here, at t = 2 s, on the agreement gate.
	constexpr double kFirstJudgedS = 2.0;

	// ---- UNDISCLOSED: geometry -------------------------------------------
	// Capsule radius 42 and half height 96 on this substrate's character
	// (ThirdPersonCharacter.cpp: InitCapsuleSize(42, 96)), plus 60 uu of margin. A box
	// grown by this is a STRICT SUPERSET of the region in which the engine's own
	// capsule-versus-box overlap can fire: the fixture's window may open early, never
	// late. Route clearance is held at 200 uu, so a window reaching 102 uu still cannot
	// open on a trigger the script was not aimed at.
	constexpr double kGrowXYUu = 102.0;
	constexpr double kGrowZUu = 156.0;

	constexpr double kWaypointUu = 70.0;
	constexpr double kLegBaseS = 4.0;      // acceleration, settling, and slack
	constexpr double kLegSpeedUu = 220.0;  // 2.3x slower than the 500 uu/s the pawn walks
	constexpr double kRestageClearUu = 400.0;
	constexpr double kHoleWaitS = 8.0;
	constexpr double kHoistMustFireS = 0.75;
	constexpr double kHoleMustTakeS = 1.50;
	constexpr double kPlacementTolUu = 2.0;

	// Route staging, re-checked before the drive starts.
	constexpr double kMinLaneClearUu = 600.0;
	constexpr double kMinCrossClearUu = 200.0;
	constexpr double kMinEntranceClearUu = 600.0;
	constexpr double kMaxStepUpUu = 150.0;

	constexpr double kCheckpointEveryS = 2.0;
	constexpr int32 kGradedCheckpoints = 99;   // 2 s .. 198 s
	constexpr double kSentinelS = 200.0;
	constexpr int32 kSentinelIndex = kGradedCheckpoints;   // 0-based

	constexpr int32 kHallSignsWanted = 4;

	const TCHAR* const kInputActionNames[] = {
		TEXT("MoveAction"), TEXT("LookAction"),
		TEXT("MouseLookAction"), TEXT("JumpAction")};
}

ARoundHallFunctionalTest::ARoundHallFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	// THE NUMBERS ARE WRITTEN BEFORE ANY BeginPlay. OnWorldInitializedActors is
	// broadcast at the end of UWorld::InitializeActorsForPlay, after
	// PostInitializeComponents and before UWorld::BeginPlay dispatches anything -- the
	// same window the t0 sanity fixture installs its log device in. A submission that
	// reads the stone or the mark at play therefore reads the STAGED value, and every
	// gate below is honest. Only CACHING is punished, and only by a move the prompt
	// discloses in as many words.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ARoundHallFunctionalTest::OnWorldActorsInitialized);
}

void ARoundHallFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------
// Verdict helpers -- one place, so every message keeps its own literal and the
// discrimination matrix can quote a contiguous source string.
// ---------------------------------------------------------------------------

void ARoundHallFunctionalTest::Fail(const FString& Message)
{
	if (bGraded)
	{
		return;
	}
	bGraded = true;
	FinishTest(EFunctionalTestResult::Failed, Message);
}

void ARoundHallFunctionalTest::Precondition(const FString& Message)
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
// Staging: the numbers, written before anybody's BeginPlay
// ---------------------------------------------------------------------------

void ARoundHallFunctionalTest::OnWorldActorsInitialized(
	const FActorsInitializedParams& Params)
{
	if (bNumbersStaged || Params.World != GetWorld())
	{
		return;
	}
	bNumbersStaged = true;
	StageTheNumbers();
}

bool ARoundHallFunctionalTest::StageTheNumbers()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}

	TArray<AActor*> Found;

	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("EntranceStone")), Found);
	int32 Stones = 0;
	for (AActor* A : Found)
	{
		if (AEntranceStoneActor* const S = Cast<AEntranceStoneActor>(A))
		{
			++Stones;
			if (!Stone.IsValid())
			{
				Stone = S;
			}
		}
	}

	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("StepMark")), Found);
	int32 Marks = 0;
	for (AActor* A : Found)
	{
		if (AStepMarkActor* const M = Cast<AStepMarkActor>(A))
		{
			++Marks;
			if (!Mark.IsValid())
			{
				Mark = M;
			}
		}
	}

	// THE CAST AND THE COUNT ARE TAKEN HERE, OFF THE LEVEL, and not in PrepareTest off a
	// world the submission's own BeginPlay has already touched. See the header note on
	// StagingFault: read later, "an actor tagged HallSign is not a sign" and "the hall
	// opens with N signs of its own" would both be reachable by a submission that spawns
	// one actor, and each would hand it a HARNESS-PRECONDITION non-verdict instead of a
	// graded result. Taken here they say what they mean -- what the LEVEL shipped -- and
	// anything that appears afterwards is just another sign the hall's number has to
	// reach, which RefreshSigns picks up like any other.
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("HallSign")), Found);
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	Signs.Reset();
	StagedRelics = 0;
	for (AActor* A : Found)
	{
		AHallSignActor* const S = Cast<AHallSignActor>(A);
		if (S == nullptr)
		{
			if (StagingFault.IsEmpty())
			{
				StagingFault = FString::Printf(TEXT("an actor tagged HallSign (%s) is not "
					"a sign, so the fixture cannot read what it is printing"),
					*A->GetName());
			}
			continue;
		}
		if (S->Face == nullptr)
		{
			if (StagingFault.IsEmpty())
			{
				StagingFault = FString::Printf(TEXT("sign %s has no readable face"),
					*S->GetName());
			}
			continue;
		}
		if (S->BelongsToTheHall())
		{
			FSign R;
			R.Actor = S;
			R.Label = S->GetName();
			R.bPlaced = true;
			R.AppearedAt = 0.0;
			Signs.Add(R);
		}
		else
		{
			++StagedRelics;
			Relic = S;
		}
	}

	if (Stones != 1 || Marks != 1 || StagedRelics != 1)
	{
		// Nothing is written. PrepareTest raises the precondition, so that every staging
		// complaint is reported from one readable place.
		if (StagingFault.IsEmpty())
		{
			StagingFault = FString::Printf(TEXT("the level gave the hall %d entrance "
				"stone(s), %d mark(s) in the middle of the room and %d sign(s) that are "
				"not the hall's own, and the run is written around exactly one of each"),
				Stones, Marks, StagedRelics);
		}
		return false;
	}

	// THE COMMITTED NUMBERS ARE THE DECOY. Reading them first is not decoration: the
	// precondition below refuses to run a hall whose committed numbers are the ones the
	// fixture is about to stage, because then a level-file read and a world read would
	// be indistinguishable and the whole read-it-off-the-thing claim would be untested.
	const int32 CommittedStart = Stone->StartNumber;
	const int32 CommittedStep = Mark->StepWritten;
	const int32 CommittedRelic = Relic->PaintedNumber;

	StagedStart = 4;
	StagedStepFirst = 2;
	StagedStepAfterRestage = 3;
	StagedRelic = 1;

	Stone->StartNumber = StagedStart;
	Mark->StepWritten = StagedStepFirst;
	Relic->PaintedNumber = StagedRelic;
	StagedStepNow = StagedStepFirst;
	bNumbersWritten = true;

	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall staging] staged start=%d step=%d->%d relic=%d "
			 "(the level commits start=%d step=%d relic=%d)"),
		StagedStart, StagedStepFirst, StagedStepAfterRestage, StagedRelic,
		CommittedStart, CommittedStep, CommittedRelic);

	if (CommittedStart == StagedStart || CommittedStep == StagedStepFirst
		|| CommittedRelic == StagedRelic)
	{
		// Recorded, not raised here: FinishTest needs a running test. PrepareTest
		// re-derives the same condition from the values it can still see.
		UE_LOG(LogTemp, Warning,
			TEXT("[t3-roundhall staging] a committed number equals a staged one"));
	}
	return true;
}

// ---------------------------------------------------------------------------
// Staging: resolving the hall, and refusing to grade a hall that cannot be graded
// ---------------------------------------------------------------------------

bool ARoundHallFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}

	auto ByTag = [&](const TCHAR* Tag, TArray<AActor*>& Out)
	{
		UGameplayStatics::GetAllActorsWithTag(World, FName(Tag), Out);
		Out.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	};

	TArray<AActor*> Found;

	// -- what the LEVEL shipped, decided before any BeginPlay ---------------
	// StagingFault first: it is the specific complaint, and it is the only one of these
	// that can name WHICH thing the level got wrong.
	if (!StagingFault.IsEmpty())
	{
		Precondition(StagingFault);
		return false;
	}
	if (!bNumbersWritten)
	{
		Precondition(TEXT("the hall could not be staged before it opened, so not one "
			"number in the room is the number the run turns on"));
		return false;
	}
	if (Signs.Num() != kHallSignsWanted || StagedRelics != 1)
	{
		Precondition(FString::Printf(TEXT("the hall opens with %d sign(s) of its own and "
			"%d that is not, and %d plus exactly one relic is what the run is written "
			"around; without a second kind of sign standing in the room there is no "
			"in-scene control"), Signs.Num(), StagedRelics, kHallSignsWanted));
		return false;
	}
	// A sign the level shipped that is already gone by PrepareTest is NOT a staging
	// fault: BeginPlay has run, so the submission is a candidate for having destroyed
	// it. The entry stays in the population and EverySignInTheHallShowsTheNumberTheHall
	// IsOn names it -- graded, which is the direction ambiguity has to resolve in.
	for (const FSign& S : Signs)
	{
		if (!S.Actor.IsValid())
		{
			UE_LOG(LogTemp, Warning,
				TEXT("[t3-roundhall staging] sign %s was gone before the run started"),
				*S.Label);
		}
	}

	// -- the fittings the drive walks into ----------------------------------
	// Stone and Mark are NOT re-resolved here: they were resolved and written to before
	// any BeginPlay, and picking them again by tag could pick a different actor from the
	// one that was staged, which would present as "the staged numbers did not survive".
	ByTag(TEXT("HoistPlate"), Found);
	Hoist = Found.Num() > 0 ? Cast<AHoistPlateActor>(Found[0]) : nullptr;
	ByTag(TEXT("Sinkhole"), Found);
	Hole = Found.Num() > 0 ? Cast<ASinkholeActor>(Found[0]) : nullptr;

	if (!Stone.IsValid() || !Mark.IsValid() || !Hoist.IsValid() || !Hole.IsValid())
	{
		Precondition(FString::Printf(TEXT("the hall is missing a fitting the run needs "
			"(stone=%s mark=%s hoist=%s hole=%s)"),
			Stone.IsValid() ? TEXT("yes") : TEXT("NO"),
			Mark.IsValid() ? TEXT("yes") : TEXT("NO"),
			Hoist.IsValid() ? TEXT("yes") : TEXT("NO"),
			Hole.IsValid() ? TEXT("yes") : TEXT("NO")));
		return false;
	}
	if (Mark->Volume == nullptr || Hoist->Volume == nullptr || Hole->Volume == nullptr)
	{
		Precondition(TEXT("a trigger in the hall has no volume, so the fixture cannot "
			"tell when the runner walked into it"));
		return false;
	}
	if (Stone->Mark == nullptr)
	{
		Precondition(TEXT("the entrance stone has no floor mark, so there is no one "
			"point a fresh runner can be measured against"));
		return false;
	}
	if (Stone->Doorplate == nullptr)
	{
		Precondition(TEXT("the entrance stone has no doorplate, so the one readout that "
			"joins the hall's number to the body walking in it cannot be read"));
		return false;
	}

	// -- the numbers actually landed ---------------------------------------
	if (Stone->StartNumber != StagedStart || Mark->StepWritten != StagedStepFirst
		|| Relic->PaintedNumber != StagedRelic)
	{
		Precondition(FString::Printf(TEXT("the staged numbers did not survive into play "
			"(stone %d wanted %d, mark %d wanted %d, relic %d wanted %d)"),
			Stone->StartNumber, StagedStart, Mark->StepWritten, StagedStepFirst,
			Relic->PaintedNumber, StagedRelic));
		return false;
	}

	// -- the runner ---------------------------------------------------------
	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	APlayerController* const PC = UGameplayStatics::GetPlayerController(World, 0);
	if (!Hero.IsValid() || PC == nullptr || PC->GetPawn() != Hero.Get())
	{
		Precondition(TEXT("no player character is possessed by player 0 when the hall "
			"opens, so there is nobody to walk in and nothing to lose to the hole"));
		return false;
	}
	if (Hero->GetMesh() == nullptr || Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		Precondition(TEXT("the runner the hall opens with has no visible body, so a "
			"fresh runner of the same kind could not be seen to arrive"));
		return false;
	}
	// THERE IS DELIBERATELY NO "exactly one pawn" PRECONDITION HERE. BeginPlay has
	// already run by the time PrepareTest does, so a submission that spawned a spare
	// runner would be handed a HARNESS-PRECONDITION non-verdict for doing so -- a
	// denominator opt-out that needs no correct work at all. "There is never more than
	// one runner alive" is a clause of the prompt, so GateTheBody gauges it on EVERY
	// frame and a spare body takes a graded FAIL. The two checks above still stand off
	// the genuinely ambiguous case: NO controlled body at all cannot be attributed
	// (a level that failed to put a runner in and a submission that removed the one it
	// was given look identical from here), and that one keeps its non-verdict. A level
	// that PLACES a second body is refused at authoring time by authoring/author_map.py,
	// which is a better place for it than a runtime precondition.
	OpeningRunnerClass = Hero->GetClass();
	OpeningRunnerClassName = Hero->GetClass()->GetFName();
	BodyName = Hero->GetFName();

	// -- where everything was given ----------------------------------------
	Fittings.Reset();
	auto Note = [&](AActor* A, const TCHAR* Label)
	{
		FFitting F;
		F.Actor = A;
		F.Label = Label;
		F.At = A->GetActorLocation();
		Fittings.Add(F);
	};
	Note(Stone.Get(), TEXT("the entrance stone"));
	Note(Mark.Get(), TEXT("the mark in the middle of the room"));
	Note(Hoist.Get(), TEXT("the hoist plate"));
	Note(Hole.Get(), TEXT("the sinkhole"));
	Note(Relic.Get(), TEXT("the relic"));
	for (const FSign& S : Signs)
	{
		if (S.Actor.IsValid())
		{
			Note(S.Actor.Get(), TEXT("a pillar sign"));
		}
	}

	ModelNumber = StagedStart;
	ModelChangedAt = -1000.0;
	LastGoodNumber = StagedStart;
	bHaveGoodNumber = false;

	// THE DOORPLATE'S FIRST EPOCH. The runner the hall opens with walked in while the
	// hall was on the number it starts on, so that is what the doorplate has to read
	// until a different body is walking in the room.
	DoorModel = StagedStart;
	// Dated from NOW rather than from world zero, so the opening doorplate always gets
	// the whole grace however long the base class took to declare the test ready. A
	// widening; it can only ever move the first judgement later.
	DoorChangedAt = double(World->GetTimeSeconds());
	DoorEpochs = 1;
	DoorBodyName = BodyName;
	RunnersLostSeen = Hole->GetRunnersLost();
	SignsRaisedSeen = Hoist->GetSignsRaised();
	if (RunnersLostSeen != 0 || SignsRaisedSeen != 0)
	{
		Precondition(FString::Printf(TEXT("the hall opens with %d runner(s) already lost "
			"and %d sign(s) already raised; both counts have to start at zero for the "
			"re-trigger readings to mean anything"), RunnersLostSeen, SignsRaisedSeen));
		return false;
	}
	return true;
}

bool ARoundHallFunctionalTest::CheckTheStagedTriple()
{
	// THE FIXTURE ASSERTS ITS OWN STAGING. The property the run turns on is not that
	// the three numbers look unlike each other -- it is that no named wrong answer's
	// trajectory ever comes back into agreement with the required one once it has left
	// it, and that the relic's number is never a value the hall takes. Written as a
	// check rather than as prose so a re-staged hall either moves the gates with it or
	// refuses to start.
	if (StagedStepFirst == StagedStepAfterRestage)
	{
		Precondition(FString::Printf(TEXT("the mark carries %d before the re-stage and "
			"%d after it; two equal steps make the whole read-it-at-the-moment-of-use "
			"question unobservable"), StagedStepFirst, StagedStepAfterRestage));
		return false;
	}

	// The required trajectory: start, two advances at the first step, three at the
	// second. Index 0 is the hall as it opens.
	TArray<int32> Required;
	Required.Add(StagedStart);
	Required.Add(Required.Last() + StagedStepFirst);
	Required.Add(Required.Last() + StagedStepFirst);
	Required.Add(Required.Last() + StagedStepAfterRestage);
	Required.Add(Required.Last() + StagedStepAfterRestage);
	Required.Add(Required.Last() + StagedStepAfterRestage);

	for (int32 i = 0; i < Required.Num(); ++i)
	{
		if (Required[i] == StagedRelic)
		{
			Precondition(FString::Printf(TEXT("the relic is painted with %d and the hall "
				"itself takes that value at advance %d; the control has to be a number "
				"the hall never shows"), StagedRelic, i));
			return false;
		}
		for (int32 j = i + 1; j < Required.Num(); ++j)
		{
			if (Required[i] == Required[j])
			{
				Precondition(FString::Printf(TEXT("the hall is on %d at both advance %d "
					"and advance %d; a repeated value lets a stale readout pass for a "
					"fresh one"), Required[i], i, j));
				return false;
			}
		}
	}

	// A step read once at BeginPlay and remembered.
	TArray<int32> CachedStep;
	CachedStep.Add(StagedStart);
	for (int32 i = 1; i < Required.Num(); ++i)
	{
		CachedStep.Add(CachedStep.Last() + StagedStepFirst);
	}

	// NO "private counter on the raised sign" ROW. It was in this list once and it was
	// a strawman: the hoist spawns Template->GetClass() off a sign the LEVEL placed, so
	// the sign it raises is always the stock supplied sign, which blanks its own face. To
	// make a per-sign counter exist at all a submission would have to rewrite the
	// supplied prop file it was told to leave alone. What the late-sign gate really
	// catches is a readout population captured once at BeginPlay -- the raised sign is
	// never written to and stays BLANK, which is not a number and needs no trajectory.

	// The number kept on the body that walks around: it goes back to the stone's number
	// every time a runner is lost. The first fall lands after advance 3, the second
	// after advance 4.
	TArray<int32> BodyScoped;
	BodyScoped.Add(StagedStart);
	BodyScoped.Add(BodyScoped.Last() + StagedStepFirst);
	BodyScoped.Add(BodyScoped.Last() + StagedStepFirst);
	BodyScoped.Add(BodyScoped.Last() + StagedStepAfterRestage);
	BodyScoped.Add(StagedStart + StagedStepAfterRestage);      // after fall 1
	BodyScoped.Add(StagedStart + StagedStepAfterRestage);      // after fall 2

	struct FWrong { const TCHAR* Name; const TArray<int32>* Values; int32 From; };
	const FWrong Wrongs[] = {
		{TEXT("a step read once and remembered"), &CachedStep, 1},
		{TEXT("the number kept on the body that walks around"), &BodyScoped, 4}};

	for (const FWrong& W : Wrongs)
	{
		int32 FirstDiff = INDEX_NONE;
		for (int32 i = W.From; i < Required.Num(); ++i)
		{
			if ((*W.Values)[i] != Required[i])
			{
				FirstDiff = i;
				break;
			}
		}
		if (FirstDiff == INDEX_NONE)
		{
			Precondition(FString::Printf(TEXT("with start %d and steps %d then %d, "
				"'%s' never disagrees with the right answer at any advance, so that "
				"wrong answer would pass the whole run"),
				StagedStart, StagedStepFirst, StagedStepAfterRestage, W.Name));
			return false;
		}
		for (int32 i = FirstDiff; i < Required.Num(); ++i)
		{
			if ((*W.Values)[i] == Required[i])
			{
				Precondition(FString::Printf(TEXT("'%s' first disagrees at advance %d "
					"and comes back into agreement at advance %d; a wrong answer that "
					"re-coincides can slip through the advance it is judged on"),
					W.Name, FirstDiff, i));
				return false;
			}
		}
	}

	// -- THE DOORPLATE: the crossing point, asserted rather than asserted-in-prose ----
	// The doorplate carries the hall's number SAMPLED AT A BODY CHANGE. There are three
	// bodies in the run -- the one the hall opens with, the one put in after fall 1
	// (which lands after advance 3) and the one put in after fall 2 (after advance 4) --
	// so the value the doorplate has to show, indexed by the same advances as above, is:
	TArray<int32> RequiredDoor;
	RequiredDoor.Add(Required[0]);   // the opening runner walked in on the start number
	RequiredDoor.Add(Required[0]);
	RequiredDoor.Add(Required[0]);
	RequiredDoor.Add(Required[0]);   // ... then fall 1 puts a body in on Required[3]
	RequiredDoor.Add(Required[3]);   // ... then fall 2 puts a body in on Required[4]
	RequiredDoor.Add(Required[4]);

	// A doorplate that simply mirrors what the hall is on, i.e. one written like a hall
	// sign on every advance.
	TArray<int32> DoorMirrors = Required;
	// A doorplate written once when the hall opens and never again -- the answer a
	// submission writes when its fall handler touches the body lane and nothing else.
	TArray<int32> DoorWrittenOnce;
	for (int32 i = 0; i < Required.Num(); ++i)
	{
		DoorWrittenOnce.Add(Required[0]);
	}

	const FWrong DoorWrongs[] = {
		{TEXT("a doorplate that shows whatever the hall is on"), &DoorMirrors, 1},
		{TEXT("a doorplate written once when the hall opens"), &DoorWrittenOnce, 4}};

	for (const FWrong& W : DoorWrongs)
	{
		int32 FirstDiff = INDEX_NONE;
		for (int32 i = W.From; i < RequiredDoor.Num(); ++i)
		{
			if ((*W.Values)[i] != RequiredDoor[i])
			{
				FirstDiff = i;
				break;
			}
		}
		if (FirstDiff == INDEX_NONE)
		{
			Precondition(FString::Printf(TEXT("with start %d and steps %d then %d, '%s' "
				"never disagrees with what the doorplate has to show, so that wrong "
				"answer would pass the whole run"),
				StagedStart, StagedStepFirst, StagedStepAfterRestage, W.Name));
			return false;
		}
		for (int32 i = FirstDiff; i < RequiredDoor.Num(); ++i)
		{
			if ((*W.Values)[i] == RequiredDoor[i])
			{
				Precondition(FString::Printf(TEXT("'%s' first disagrees with the "
					"doorplate at advance %d and comes back into agreement at advance "
					"%d; a wrong answer that re-coincides can slip through"),
					W.Name, FirstDiff, i));
				return false;
			}
		}
	}

	// The sign the hoist raises has to come up on a number that is NOT the one the hall
	// started on, or "it came up on the start number" is not a distinguishable mistake.
	if (Required[2] == StagedStart || Required[4] == StagedStart)
	{
		Precondition(FString::Printf(TEXT("the hall is on the number it started with "
			"(%d) at one of the two hoists, so a sign that initialised itself from the "
			"entrance stone would be indistinguishable from a right one"), StagedStart));
		return false;
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall staging] required %d %d %d %d %d %d | cached-step %d %d %d "
			 "%d %d %d | body-scoped %d %d %d %d %d %d | doorplate %d %d %d %d %d %d"),
		Required[0], Required[1], Required[2], Required[3], Required[4], Required[5],
		CachedStep[0], CachedStep[1], CachedStep[2], CachedStep[3], CachedStep[4],
		CachedStep[5], BodyScoped[0], BodyScoped[1], BodyScoped[2], BodyScoped[3],
		BodyScoped[4], BodyScoped[5], RequiredDoor[0], RequiredDoor[1], RequiredDoor[2],
		RequiredDoor[3], RequiredDoor[4], RequiredDoor[5]);
	return true;
}

bool ARoundHallFunctionalTest::CheckTheRoutes()
{
	// The lane the drive walks is the line through the entrance mark. Every leg is
	// out to that lane, along it, and in to the stop -- three straight pieces, no turns
	// mid-stride, because a turn is how this repo has failed correct answers before.
	const FVector Entrance = Stone->GetMarkCentre();
	LaneY = Entrance.Y;

	struct FTrig { const TCHAR* Name; const UBoxComponent* Box; };
	const FTrig Trigs[] = {
		{TEXT("the mark in the middle of the room"), Mark->Volume},
		{TEXT("the hoist plate"), Hoist->Volume},
		{TEXT("the sinkhole"), Hole->Volume}};

	double MinX = Entrance.X;
	double MaxX = Entrance.X;
	for (const FTrig& T : Trigs)
	{
		MinX = FMath::Min(MinX, T.Box->GetComponentLocation().X);
		MaxX = FMath::Max(MaxX, T.Box->GetComponentLocation().X);
	}
	MinX -= 400.0;
	MaxX += 400.0;

	// 1. The lane itself is clear the whole way along.
	for (int32 k = 0; k <= 200; ++k)
	{
		const FVector P(MinX + (MaxX - MinX) * double(k) / 200.0, LaneY, Entrance.Z);
		for (const FTrig& T : Trigs)
		{
			const double D = DistToVolume(T.Box, P);
			if (D < kMinLaneClearUu)
			{
				Precondition(FString::Printf(TEXT("the lane the drive walks passes %.0f "
					"uu from %s and %.0f uu is the least that keeps a walk past a "
					"trigger from firing it"), D, T.Name, kMinLaneClearUu));
				return false;
			}
		}
	}

	// 2. Every walk in and out of a trigger clears every OTHER trigger. That is the
	//    whole of the route geometry, and it is the property the prompt's own layout
	//    claim ("the hole is off any route between the other three") stands on.
	for (const FTrig& Own : Trigs)
	{
		const FVector C = Own.Box->GetComponentLocation();
		for (int32 k = 0; k <= 40; ++k)
		{
			const FVector P(C.X, LaneY + (C.Y - LaneY) * double(k) / 40.0, Entrance.Z);
			for (const FTrig& Other : Trigs)
			{
				if (Other.Box == Own.Box)
				{
					continue;
				}
				const double D = DistToVolume(Other.Box, P);
				if (D < kMinCrossClearUu)
				{
					Precondition(FString::Printf(TEXT("the walk in and out of %s passes "
						"%.0f uu from %s, and %.0f uu is the least that keeps the runner "
						"from brushing a trigger the script never aimed at"),
						Own.Name, D, Other.Name, kMinCrossClearUu));
					return false;
				}
			}
		}
	}

	// 3. A fresh runner is put back on the entrance mark, so nothing may be waiting
	//    under their feet there.
	for (const FTrig& T : Trigs)
	{
		const double D = DistToVolume(T.Box, Entrance);
		if (D < kMinEntranceClearUu)
		{
			Precondition(FString::Printf(TEXT("the entrance mark is %.0f uu from %s; a "
				"runner put back that close would fire it without walking anywhere"),
				D, T.Name));
			return false;
		}
	}

	// 4. The hole is reachable from the entrance on ordinary flat ground.
	const double Rise = FMath::Abs(Hole->GetActorLocation().Z - Entrance.Z);
	if (Rise > kMaxStepUpUu)
	{
		Precondition(FString::Printf(TEXT("the sinkhole sits %.0f uu above or below the "
			"entrance mark and the runner only walks; %.0f uu is the most a flat route "
			"can absorb"), Rise, kMaxStepUpUu));
		return false;
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall staging] lane y=%.0f from x=%.0f to x=%.0f; entrance "
			 "(%.0f,%.0f) mark (%.0f,%.0f) hoist (%.0f,%.0f) hole (%.0f,%.0f)"),
		LaneY, MinX, MaxX, Entrance.X, Entrance.Y,
		Mark->Volume->GetComponentLocation().X, Mark->Volume->GetComponentLocation().Y,
		Hoist->Volume->GetComponentLocation().X, Hoist->Volume->GetComponentLocation().Y,
		Hole->Volume->GetComponentLocation().X, Hole->Volume->GetComponentLocation().Y);
	return true;
}

bool ARoundHallFunctionalTest::CheckTheLevelCanBePlayed()
{
	// THE LEVEL'S FAULT, NOT THE MODEL'S. Five of six ThirdPerson maps once shipped
	// visible, animated and completely uncontrollable, grading byte-identically with a
	// playable one. This reads the level's OWN configuration -- the game mode class
	// default -- and never the live instance, because a submission can rewrite the live
	// instance and a rewritten one is that submission's failure (the body gates and the
	// drive gate name it), not a reason to hand the whole run a non-verdict.
	//
	// IDENTITY BY PROPERTY, NEVER BY CLASS: a pawn that HAS a MoveAction property is a
	// template-style playable pawn and then all four actions must be set; a pawn without
	// that property belongs to a substrate that does not use the pattern, and this stays
	// silent there.
	UWorld* const World = GetWorld();
	AGameModeBase* const Live = World != nullptr ? World->GetAuthGameMode() : nullptr;
	if (Live == nullptr)
	{
		Precondition(TEXT("the level has no rules object at all, so nothing spawns a "
			"runner and nothing could put a fresh one in"));
		return false;
	}
	const AGameModeBase* const Rules =
		Live->GetClass()->GetDefaultObject<AGameModeBase>();
	if (Rules == nullptr)
	{
		return true;
	}

	UClass* const PawnClass = Rules->DefaultPawnClass.Get();
	if (PawnClass == nullptr)
	{
		Precondition(TEXT("the level's rules name no kind of runner, so 'a new runner of "
			"the same kind' has no kind to be"));
		return false;
	}
	if (FindFProperty<FObjectProperty>(PawnClass, kInputActionNames[0]) != nullptr)
	{
		const UObject* const PawnCDO = PawnClass->GetDefaultObject();
		TArray<FString> Unbound;
		for (const TCHAR* const Name : kInputActionNames)
		{
			const FObjectProperty* const Prop =
				FindFProperty<FObjectProperty>(PawnClass, Name);
			if (Prop == nullptr || PawnCDO == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(PawnCDO) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Precondition(FString::Printf(TEXT("this level cannot be played by hand: the "
				"runner (%s) has nothing bound to %s, so a person would get a body that "
				"cannot move and the run would grade identically"),
				*PawnClass->GetName(), *FString::Join(Unbound, TEXT(", "))));
			return false;
		}
	}

	UClass* const PCClass = Rules->PlayerControllerClass.Get();
	if (PCClass == nullptr)
	{
		Precondition(TEXT("this level cannot be played by hand: its rules name no "
			"controller, so the player gets a bare one and no key reaches the runner"));
		return false;
	}
	if (const FArrayProperty* const Contexts =
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
			Precondition(FString::Printf(TEXT("this level cannot be played by hand: the "
				"controller (%s) applies no key mapping, so nothing a person presses "
				"reaches the runner"), *PCClass->GetName()));
			return false;
		}
	}
	return true;
}

bool ARoundHallFunctionalTest::BuildScript()
{
	const FVector Entrance = Stone->GetMarkCentre();
	const FVector MarkC = Mark->Volume->GetComponentLocation();
	const FVector HoistC = Hoist->Volume->GetComponentLocation();
	const FVector HoleC = Hole->Volume->GetComponentLocation();

	auto Lane = [&](const FVector& V) { return FVector(V.X, LaneY, Entrance.Z); };
	auto Add = [&](EStopKind Kind, const FVector& Where, double Dwell)
	{
		FStop S;
		S.Kind = Kind;
		S.Where = Where;
		S.DwellS = Dwell;
		Script.Add(S);
	};

	// NINETEEN STOPS. Five entries onto the mark, two onto the hoist plate, two into
	// the hole -- every trigger fires at least twice, AND THE SECOND FIRING OF EACH ONE
	// ASKS SOMETHING THE FIRST COULD NOT:
	//
	//   * the second FALL lands on a different number from the first (14, not 11), so a
	//     doorplate written once passes fall 1 and dies at fall 2;
	//   * the second HOIST is placed immediately AFTER the second fall with no advance
	//     in between, so the sign it raises has to come up on a number that survived a
	//     re-body -- the first hoist raises on a freshly advanced number and no body has
	//     been lost yet, so it cannot ask that;
	//   * the third entry onto the MARK is the first one after the re-stage.
	//
	//   4 -> 6 -> 8 -> [hoist 1: the new sign must read 8] -> [the step becomes 3]
	//     -> 11 -> [fall 1: still 11, doorplate 11] -> 14
	//     -> [fall 2: still 14, doorplate 14] -> [hoist 2: the new sign must read 14]
	//     -> 17
	Add(EStopKind::Settle, Entrance, 3.0);          // 0
	Add(EStopKind::Mark, MarkC, 2.5);               // 1  advance 1 -> 6
	Add(EStopKind::Clear, Lane(MarkC), 1.5);        // 2  step off
	Add(EStopKind::Mark, MarkC, 2.5);               // 3  advance 2 -> 8
	Add(EStopKind::Clear, Lane(MarkC), 1.5);        // 4  step off
	Add(EStopKind::Hoist, HoistC, 2.5);             // 5  hoist 1
	Add(EStopKind::Restage, Lane(HoistC), 3.0);     // 6  the step becomes 3
	Add(EStopKind::Mark, MarkC, 2.5);               // 7  advance 3 -> 11
	Add(EStopKind::Clear, Lane(MarkC), 1.5);        // 8  step off
	Add(EStopKind::Hole, HoleC, kHoleWaitS);        // 9  fall 1  -> doorplate 11
	Add(EStopKind::Mark, MarkC, 2.5);               // 10 advance 4 -> 14
	Add(EStopKind::Clear, Lane(MarkC), 1.5);        // 11 step off
	Add(EStopKind::Hole, HoleC, kHoleWaitS);        // 12 fall 2  -> doorplate 14
	Add(EStopKind::Hoist, HoistC, 2.5);             // 13 hoist 2, on the survived 14
	Add(EStopKind::Clear, Lane(HoistC), 1.5);       // 14 step off
	Add(EStopKind::Mark, MarkC, 2.5);               // 15 advance 5 -> 17
	Add(EStopKind::Clear, Lane(MarkC), 1.5);        // 16 step off
	Add(EStopKind::Settle, Lane(MarkC), 4.0);       // 17 stand and settle
	Add(EStopKind::Finish, Lane(MarkC), 0.0);       // 18

	StopIndex = 0;
	return true;
}

void ARoundHallFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		return;
	}
	if (!bNumbersStaged)
	{
		Precondition(TEXT("the fixture never got the pre-play window in which it writes "
			"the numbers the hall runs on, so every number in the room would be the one "
			"committed in the level file"));
		return;
	}
	if (!ResolveStaging() || !CheckTheStagedTriple() || !CheckTheRoutes()
		|| !CheckTheLevelCanBePlayed() || !BuildScript())
	{
		return;
	}
	bStaged = true;

	// Checkpoints every two seconds carry the calibration log and the camera plan. The
	// LAST entry is a SENTINEL far past the ~110 s the drive models, because the base
	// class declares SUCCESS the moment the last scheduled checkpoint is crossed -- a
	// run that stalled half way would otherwise finish green having graded nothing. A
	// run that gets all the way through grades itself at the last stop and never reaches
	// the sentinel; a run that does reach it is graded there, and FAILS.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelS);
	TimeLimitMargin = 6.0f;
	SetCheckpointSchedule(Schedule);

	BuildTransits(0.0);

	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall staging] %d hall sign(s) + one relic, %d stop(s) on the "
			 "script, runner %s of kind %s"),
		Signs.Num(), Script.Num(), *BodyName.ToString(),
		*OpeningRunnerClassName.ToString());
}

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

FVector ARoundHallFunctionalTest::HeroAt() const
{
	return Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
}

bool ARoundHallFunctionalTest::InVolume(const UBoxComponent* Box, const FVector& P,
	bool bGrow) const
{
	if (Box == nullptr)
	{
		return false;
	}
	const FVector Rel =
		Box->GetComponentQuat().UnrotateVector(P - Box->GetComponentLocation());
	FVector E = Box->GetScaledBoxExtent();
	if (bGrow)
	{
		E += FVector(kGrowXYUu, kGrowXYUu, kGrowZUu);
	}
	return FMath::Abs(Rel.X) <= E.X && FMath::Abs(Rel.Y) <= E.Y
		&& FMath::Abs(Rel.Z) <= E.Z;
}

bool ARoundHallFunctionalTest::InsideTrigger(const UBoxComponent* Box) const
{
	// ONE-SIDED BY CONSTRUCTION: the union of what the prop's own trigger sees and a box
	// grown past the capsule. True whenever the prop could have fired, and true for
	// about a capsule radius of travel BEFORE that. The direction matters -- a window
	// that opened late would score the prop's own instant reaction as a rise nobody
	// asked for, on every submission ever made, including the reference.
	if (Box == nullptr || !Hero.IsValid())
	{
		return false;
	}
	return Box->IsOverlappingActor(Hero.Get()) || InVolume(Box, HeroAt(), /*bGrow=*/true);
}

double ARoundHallFunctionalTest::DistToVolume(const UBoxComponent* Box, const FVector& P)
{
	if (Box == nullptr)
	{
		return TNumericLimits<double>::Max();
	}
	const FVector Rel =
		Box->GetComponentQuat().UnrotateVector(P - Box->GetComponentLocation());
	const FVector E = Box->GetScaledBoxExtent();
	// Flat: the hall is one storey and every rule that uses this is about where
	// somebody is standing, not how high they are.
	const double DX = FMath::Max(0.0, FMath::Abs(Rel.X) - E.X);
	const double DY = FMath::Max(0.0, FMath::Abs(Rel.Y) - E.Y);
	return FMath::Sqrt(DX * DX + DY * DY);
}

// ---------------------------------------------------------------------------
// Reading the room
// ---------------------------------------------------------------------------

int32 ARoundHallFunctionalTest::FirstWholeNumber(const FString& In, bool& bOk)
{
	bOk = false;
	FString Digits;
	bool bNegative = false;
	for (int32 i = 0; i < In.Len(); ++i)
	{
		const TCHAR C = In[i];
		if (FChar::IsDigit(C))
		{
			if (Digits.IsEmpty() && i > 0 && In[i - 1] == TEXT('-'))
			{
				bNegative = true;
			}
			Digits.AppendChar(C);
		}
		else if (!Digits.IsEmpty())
		{
			break;
		}
	}
	if (Digits.IsEmpty())
	{
		// A BLANK SIGN IS NOT A ZERO. Reading it as one would be a permissive fake the
		// moment a wrong answer's value happened to be zero.
		return 0;
	}
	bOk = true;
	const int32 V = FCString::Atoi(*Digits);
	return bNegative ? -V : V;
}

int32 ARoundHallFunctionalTest::ReadSign(const AHallSignActor* S, bool& bOk) const
{
	bOk = false;
	if (S == nullptr)
	{
		return 0;
	}
	return FirstWholeNumber(S->GetPrintedText(), bOk);
}

bool ARoundHallFunctionalTest::ReadHallNumber(double Now, int32& Out,
	FString& Detail) const
{
	Detail = SignReadout(Now);
	Out = 0;
	bool bAny = false;
	bool bAgreed = true;
	for (const FSign& S : Signs)
	{
		if (!S.Actor.IsValid())
		{
			bAgreed = false;
			continue;
		}
		if (!S.bPlaced && Now - S.AppearedAt < kRaiseSuppressS)
		{
			continue;   // a sign that has only just gone up; it has its own gate
		}
		if (!S.Actor->BelongsToTheHall())
		{
			bAgreed = false;
			continue;
		}
		bool bRead = false;
		const int32 V = ReadSign(S.Actor.Get(), bRead);
		if (!bRead)
		{
			bAgreed = false;
			continue;
		}
		if (!bAny)
		{
			Out = V;
			bAny = true;
		}
		else if (V != Out)
		{
			bAgreed = false;
		}
	}
	return bAny && bAgreed;
}

FString ARoundHallFunctionalTest::SignReadout(double Now) const
{
	FString Line;
	for (const FSign& S : Signs)
	{
		if (!S.Actor.IsValid())
		{
			Line += FString::Printf(TEXT("%s=<gone> "), *S.Label);
			continue;
		}
		const FString Text = S.Actor->GetPrintedText();
		Line += FString::Printf(TEXT("%s='%s'%s "), *S.Label,
			Text.IsEmpty() ? TEXT("") : *Text,
			(!S.bPlaced && Now - S.AppearedAt < kRaiseSuppressS)
				? TEXT("(just up)") : TEXT(""));
	}
	if (Relic.IsValid())
	{
		Line += FString::Printf(TEXT("relic='%s'"), *Relic->GetPrintedText());
	}
	return Line;
}

// ---------------------------------------------------------------------------
// Housekeeping
// ---------------------------------------------------------------------------

void ARoundHallFunctionalTest::RefreshSigns(double Now)
{
	UWorld* const World = GetWorld();
	if (World == nullptr || !Hoist.IsValid())
	{
		return;
	}
	const int32 RaisedNow = Hoist->GetSignsRaised();

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("HallSign")), Found);
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });

	for (AActor* A : Found)
	{
		AHallSignActor* const S = Cast<AHallSignActor>(A);
		if (S == nullptr || S == Relic.Get() || !S->BelongsToTheHall())
		{
			continue;
		}
		bool bKnown = false;
		for (const FSign& K : Signs)
		{
			if (K.Actor.Get() == S)
			{
				bKnown = true;
				break;
			}
		}
		if (bKnown)
		{
			continue;
		}
		// A SIGN THE HALL DID NOT HAVE A MOMENT AGO. Whether the hoist put it there is
		// taken from BOTH the hoist's own count and the sign's own bookkeeping, so a
		// submission that clears the flag to dodge the late-sign gate is still caught by
		// it, and one that raises a sign of its own is simply another sign the hall's
		// number has to reach.
		FSign R;
		R.Actor = S;
		R.Label = S->GetName();
		R.bPlaced = false;
		R.AppearedAt = Now;
		R.bFromTheHoist = (RaisedNow > SignsRaisedSeen) || S->bWasRaisedByTheHoist;
		R.RaisedOnNumber = ModelNumber;
		R.bLateWindowOpen = R.bFromTheHoist;
		Signs.Add(R);

		UE_LOG(LogTemp, Display,
			TEXT("[t3-roundhall] t=%.2f a sign went up (%s), the hall is on %d, it reads "
				 "'%s'"), Now, *R.Label, ModelNumber, *S->GetPrintedText());
	}
	SignsRaisedSeen = RaisedNow;
}

void ARoundHallFunctionalTest::NoteAdvance(double Now, int32 Step)
{
	ModelNumber += Step;
	ModelChangedAt = Now;
	for (FSign& S : Signs)
	{
		// The late-sign window runs from the moment a sign goes up until the next
		// advance; after that the agreement gate carries the same fact forever.
		S.bLateWindowOpen = false;
	}
}

void ARoundHallFunctionalTest::ObserveMark(double Now)
{
	if (!Mark.IsValid())
	{
		return;
	}
	const bool bNow = InsideTrigger(Mark->Volume);
	if (bNow && !bOnTheMark)
	{
		++EntriesSeen;
		EntryAt = Now;
		bEntryOpen = true;
		bEntryJudged = false;
		StepAtEntry = Mark->GetStepWritten();
		NumberBeforeEntry = LastGoodNumber;
		NoteAdvance(Now, StepAtEntry);
		UE_LOG(LogTemp, Display,
			TEXT("[t3-roundhall] t=%.2f entry %d onto the mark, it carries +%d, the "
				 "hall was on %d and must be on %d"),
			Now, EntriesSeen, StepAtEntry, NumberBeforeEntry, ModelNumber);
	}
	bOnTheMark = bNow;
	if (bEntryOpen && bEntryJudged && !bOnTheMark)
	{
		bEntryOpen = false;
	}
}

void ARoundHallFunctionalTest::ObserveFall(double Now)
{
	if (!Hole.IsValid() || bInFallWindow)
	{
		return;
	}
	const int32 Lost = Hole->GetRunnersLost();
	if (Lost <= RunnersLostSeen)
	{
		return;
	}
	RunnersLostSeen = Lost;
	++FallsSeen;
	bInFallWindow = true;
	bFallJudged = false;
	bHoldingInput = true;
	FallAt = Now;
	NumberBeforeFall = LastGoodNumber;
	BodyBeforeFallName = BodyName;
	DwellUntil = -1.0;
	InsideHoleSince = -1.0;
	InsideHoistSince = -1.0;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall] t=%.2f fall %d: %s is gone, the hall was on %d"),
		Now, FallsSeen, *BodyBeforeFallName.ToString(), NumberBeforeFall);
}

void ARoundHallFunctionalTest::DoTheRestage(double Now)
{
	if (bRestaged || !Mark.IsValid())
	{
		return;
	}
	if (bOnTheMark || Mark->IsSomebodyStandingOnIt()
		|| (Hero.IsValid() && DistToVolume(Mark->Volume, HeroAt()) < kRestageClearUu))
	{
		Precondition(TEXT("the fixture's own re-stage of the mark landed while somebody "
			"was standing on or beside it, which would change the step under a walk "
			"already in progress"));
		return;
	}
	Mark->StepWritten = StagedStepAfterRestage;
	StagedStepNow = StagedStepAfterRestage;
	bRestaged = true;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall] t=%.2f the mark now carries +%d (it carried +%d)"),
		Now, StagedStepAfterRestage, StagedStepFirst);
}

// ---------------------------------------------------------------------------
// The gates
// ---------------------------------------------------------------------------

bool ARoundHallFunctionalTest::GateTheRelic(double Now)
{
	// THE IN-SCENE NEGATIVE CONTROL, gauged on every frame with no settle window at
	// all. Same class, same face, same Print() as the hall's four, distinguished only
	// by the flag the level set on it -- and nothing protects it, because a control
	// that could not be broken would not be a control.
	if (!Relic.IsValid())
	{
		Fail(FString::Printf(
			TEXT("TheRelicKeepsItsOwnNumber: the sign at the back of the hall is gone. ")
			TEXT("It is not one of the hall's and nothing may touch it -- t=%.2f"), Now));
		return false;
	}
	if (Relic->BelongsToTheHall())
	{
		Fail(FString::Printf(
			TEXT("TheRelicKeepsItsOwnNumber: the sign at the back of the hall now says ")
			TEXT("it is one of the hall's. It is not, and whether a sign belongs to the ")
			TEXT("hall is not the submission's to change -- t=%.2f"), Now));
		return false;
	}
	bool bOk = false;
	const int32 V = ReadSign(Relic.Get(), bOk);
	if (!bOk || V != StagedRelic)
	{
		Fail(FString::Printf(
			TEXT("TheRelicKeepsItsOwnNumber: the sign at the back of the hall is ")
			TEXT("painted with %d and reads '%s' at t=%.2f. It is not one of the ")
			TEXT("hall's signs: it goes on showing its own number and nothing may write ")
			TEXT("over it. %s"),
			StagedRelic, *Relic->GetPrintedText(), Now, *SignReadout(Now)));
		return false;
	}
	return true;
}

bool ARoundHallFunctionalTest::GateTheHall(double Now)
{
	for (const FFitting& F : Fittings)
	{
		if (!F.Actor.IsValid())
		{
			Fail(FString::Printf(
				TEXT("TheHallKeepsWhatWasGivenToIt: %s is gone at t=%.2f. The hall's ")
				TEXT("fittings are the hall's, not the submission's"), *F.Label, Now));
			return false;
		}
		const double Moved = FVector::Dist(F.Actor->GetActorLocation(), F.At);
		if (Moved > kPlacementTolUu)
		{
			Fail(FString::Printf(
				TEXT("TheHallKeepsWhatWasGivenToIt: %s has moved %.1f uu from where the ")
				TEXT("hall put it, at t=%.2f. Do not move the marks, the pillars, the ")
				TEXT("hoist or the sinkhole"), *F.Label, Moved, Now));
			return false;
		}
	}
	if (Stone->StartNumber != StagedStart)
	{
		Fail(FString::Printf(
			TEXT("TheHallKeepsWhatWasGivenToIt: the number painted on the entrance ")
			TEXT("stone now reads %d and the hall was given %d. That number is the ")
			TEXT("hall's to state and the submission's to read, never to rewrite"),
			Stone->StartNumber, StagedStart));
		return false;
	}
	if (Mark->StepWritten != StagedStepNow)
	{
		Fail(FString::Printf(
			TEXT("TheHallKeepsWhatWasGivenToIt: the step written on the mark now reads ")
			TEXT("%d and the hall was given %d. Read the step -- do not write it"),
			Mark->StepWritten, StagedStepNow));
		return false;
	}
	if (Relic->PaintedNumber != StagedRelic)
	{
		Fail(FString::Printf(
			TEXT("TheHallKeepsWhatWasGivenToIt: the number painted on the relic now ")
			TEXT("reads %d and the hall was given %d"),
			Relic->PaintedNumber, StagedRelic));
		return false;
	}
	for (const FSign& S : Signs)
	{
		if (S.bPlaced && S.Actor.IsValid() && !S.Actor->BelongsToTheHall())
		{
			Fail(FString::Printf(
				TEXT("TheHallKeepsWhatWasGivenToIt: pillar sign %s has stopped saying it ")
				TEXT("is one of the hall's. Which signs belong to the hall is the ")
				TEXT("hall's to say"), *S.Label));
			return false;
		}
	}

	// The hall was given a working hoist and a working hole; whether they still work is
	// gauged in Tick, where the fixture knows how long the runner has been standing in
	// each of them.
	return true;
}

bool ARoundHallFunctionalTest::GateTheFall(double Now)
{
	if (!bInFallWindow || bFallJudged || Now - FallAt < kBodyJudgeS)
	{
		return true;
	}
	bFallJudged = true;
	++FallsJudged;

	int32 N = 0;
	FString Detail;
	const bool bOk = ReadHallNumber(Now, N, Detail);
	if (!bOk)
	{
		Fail(FString::Printf(
			TEXT("TheNumberSurvivesANewRunner: %.2f s after fall %d the hall's signs do ")
			TEXT("not agree on a number at all, and the hall was on %d before the fall. ")
			TEXT("Losing a runner does not cost the hall its place. %s"),
			Now - FallAt, FallsJudged, NumberBeforeFall, *Detail));
		return false;
	}
	if (N != NumberBeforeFall)
	{
		Fail(FString::Printf(
			TEXT("TheNumberSurvivesANewRunner: the hall was on %d before fall %d and its ")
			TEXT("signs read %d %.2f s after it. The round number is not touched by a ")
			TEXT("runner being lost. %s"),
			NumberBeforeFall, FallsJudged, N, Now - FallAt, *Detail));
		return false;
	}
	LastGoodNumber = N;
	bHaveGoodNumber = true;
	bAwaitAdvanceAfterFall = true;
	return true;
}

bool ARoundHallFunctionalTest::GateTheBody(double Now)
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Pawns;
	UGameplayStatics::GetAllActorsOfClass(World, APawn::StaticClass(), Pawns);

	// THE ONE-RUNNER CLAUSE IS CONTINUOUS, and that is the point. "There is never more
	// than one runner alive in the hall at a time" is a promise about every frame; a
	// spare body parked out of the way would otherwise be invisible except inside the
	// two fall windows. It is safe to gauge on every frame because a destroyed body is
	// already invisible to the actor iterator, so the correct answer -- the hole takes
	// one and a fresh one is put in on the same frame -- never reads as two. Only MORE
	// than one is judged here; FEWER is a statement about a fall and belongs to the
	// window below, where the fixture knows a fall happened and how long ago.
	if (Pawns.Num() > 1)
	{
		FString Who;
		for (const AActor* A : Pawns)
		{
			Who += FString::Printf(TEXT("%s "), *A->GetName());
		}
		Fail(FString::Printf(
			TEXT("ANewRunnerOfTheSameKindStandsOnTheEntranceMark: %d runners are alive ")
			TEXT("in the hall at t=%.2f and there is never more than one at a time. ")
			TEXT("Alive: %s"), Pawns.Num(), Now, *Who));
		return false;
	}

	if (!bInFallWindow || Now - FallAt < kBodyJudgeS)
	{
		return true;
	}
	// Gauged from kBodyJudgeS after the fall until the fixture lets go of its own input
	// at kFallHoldS -- not on one frame. A fresh runner that appears on the mark and is
	// then taken away again inside the judging window is not a fresh runner standing on
	// the mark, and re-reading costs nothing.
	if (Pawns.Num() != 1)
	{
		FString Who;
		for (const AActor* A : Pawns)
		{
			Who += FString::Printf(TEXT("%s "), *A->GetName());
		}
		Fail(FString::Printf(
			TEXT("ANewRunnerOfTheSameKindStandsOnTheEntranceMark: %.2f s after fall %d ")
			TEXT("there are %d runner(s) alive in the hall and there is never more than ")
			TEXT("one, nor fewer -- within two seconds a new one is standing on the mark ")
			TEXT("at the entrance stone. Alive: %s"),
			Now - FallAt, FallsJudged, Pawns.Num(), Pawns.Num() == 0 ? TEXT("none") : *Who));
		return false;
	}

	APawn* const Fresh = Cast<APawn>(Pawns[0]);
	if (Fresh == nullptr)
	{
		return true;
	}
	if (Fresh->GetFName() == BodyBeforeFallName)
	{
		Fail(FString::Printf(
			TEXT("ANewRunnerOfTheSameKindStandsOnTheEntranceMark: %.2f s after fall %d ")
			TEXT("the runner in the hall is still %s, the one that fell. That runner ")
			TEXT("ends there and a new one comes in"),
			Now - FallAt, FallsJudged, *BodyBeforeFallName.ToString()));
		return false;
	}
	if (Fresh->GetClass() != OpeningRunnerClass.Get())
	{
		Fail(FString::Printf(
			TEXT("ANewRunnerOfTheSameKindStandsOnTheEntranceMark: %.2f s after fall %d ")
			TEXT("the runner in the hall is a %s and the hall began with a %s. A new ")
			TEXT("runner of the SAME KIND comes in"),
			Now - FallAt, FallsJudged, *Fresh->GetClass()->GetName(),
			*OpeningRunnerClassName.ToString()));
		return false;
	}
	APlayerController* const PC = UGameplayStatics::GetPlayerController(World, 0);
	if (PC == nullptr || PC->GetPawn() != Fresh)
	{
		Fail(FString::Printf(
			TEXT("ANewRunnerOfTheSameKindStandsOnTheEntranceMark: %.2f s after fall %d ")
			TEXT("the runner %s is not under the player's control (the player holds %s). ")
			TEXT("A new runner comes in under the player's control and able to walk on"),
			Now - FallAt, FallsJudged, *Fresh->GetName(),
			(PC != nullptr && PC->GetPawn() != nullptr) ? *PC->GetPawn()->GetName()
													   : TEXT("nobody")));
		return false;
	}

	const FVector MarkCentre = Stone->GetMarkCentre();
	const FVector Where = Fresh->GetActorLocation();
	const double Flat = FVector::Dist2D(Where, MarkCentre);

	// MEASURED FROM THE RUNNER'S FEET, NOT FROM ITS MIDDLE. An actor location on this
	// substrate is the capsule centre, ~96 uu above the floor a standing body is on
	// (ThirdPersonCharacter.cpp: InitCapsuleSize(42, 96)), so comparing actor Z against
	// the mark spent half the allowance before the runner had done anything wrong -- and
	// the prompt discloses a bound on where the runner IS STANDING, not on where its
	// middle is. Subtracting the half height makes the measured quantity the one the
	// prompt names.
	double FeetZ = Where.Z;
	if (const ACharacter* const AsChar = Cast<ACharacter>(Fresh))
	{
		if (const UCapsuleComponent* const Cap = AsChar->GetCapsuleComponent())
		{
			FeetZ = Where.Z - double(Cap->GetScaledCapsuleHalfHeight());
		}
	}
	const double Rise = FMath::Abs(FeetZ - MarkCentre.Z);
	if (Flat > kMarkTolUu || Rise > kFeetTolUu)
	{
		Fail(FString::Printf(
			TEXT("ANewRunnerOfTheSameKindStandsOnTheEntranceMark: %.2f s after fall %d ")
			TEXT("the new runner's feet are %.0f uu across the mark at the entrance ")
			TEXT("stone and %.0f uu clear of it. A runner standing on the mark is within ")
			TEXT("%.0f uu of the middle of it across the floor and within %.0f uu of it ")
			TEXT("up or down -- standing on it, not hanging in the air over it. They are ")
			TEXT("at %s and the middle of the mark is at %s"),
			Now - FallAt, FallsJudged, Flat, Rise, kMarkTolUu, kFeetTolUu,
			*Where.ToCompactString(), *MarkCentre.ToCompactString()));
		return false;
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall] t=%.2f fall %d judged: %s (%s) on the entrance mark, %.0f "
			 "uu across, the hall still on %d"),
		Now, FallsJudged, *Fresh->GetName(), *Fresh->GetClass()->GetName(), Flat,
		NumberBeforeFall);
	return true;
}

bool ARoundHallFunctionalTest::GateTheStep(double Now)
{
	int32 N = 0;
	FString Detail;
	const bool bOk = ReadHallNumber(Now, N, Detail);

	if (bEntryOpen && !bEntryJudged && Now - EntryAt >= kRiseDeadlineS)
	{
		if (!bOk)
		{
			Fail(FString::Printf(
				TEXT("EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries: %.2f s ")
				TEXT("after entry %d onto the mark the hall's signs do not agree on a ")
				TEXT("number at all. The mark carried +%d and the hall was on %d, so it ")
				TEXT("must be on %d. %s"),
				Now - EntryAt, EntriesSeen, StepAtEntry, NumberBeforeEntry,
				NumberBeforeEntry + StepAtEntry, *Detail));
			return false;
		}
		if (bAwaitAdvanceAfterFall)
		{
			// THE SECOND HALF OF THE FALL GATE. A submission whose signs read the right
			// number after a fall but whose own bookkeeping went back to the start is
			// only visible here: the next advance carries on from the wrong place.
			const int32 Want = NumberBeforeFall + StepAtEntry;
			if (N != Want)
			{
				Fail(FString::Printf(
					TEXT("TheNumberSurvivesANewRunner: the hall was on %d before fall ")
					TEXT("%d, and the first step onto the mark afterwards put it on %d ")
					TEXT("when it must carry on from there to %d. The next step carries ")
					TEXT("on from where the hall was, not from the entrance stone and ")
					TEXT("not from nothing. %s"),
					NumberBeforeFall, FallsJudged, N, Want, *Detail));
				return false;
			}
			bAwaitAdvanceAfterFall = false;
		}
		const int32 Delta = N - NumberBeforeEntry;
		if (Delta != StepAtEntry)
		{
			Fail(FString::Printf(
				TEXT("EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries: at entry ")
				TEXT("%d the mark carried +%d, the hall was on %d, and %.2f s later its ")
				TEXT("signs read %d -- a rise of %d. Each step onto the mark raises the ")
				TEXT("number exactly once, by the step the mark is carrying at that ")
				TEXT("moment. %s"),
				EntriesSeen, StepAtEntry, NumberBeforeEntry, Now - EntryAt, N, Delta,
				*Detail));
			return false;
		}
		bEntryJudged = true;
		LastGoodNumber = N;
		bHaveGoodNumber = true;
		UE_LOG(LogTemp, Display,
			TEXT("[t3-roundhall] t=%.2f entry %d judged: %d + %d = %d"),
			Now, EntriesSeen, NumberBeforeEntry, StepAtEntry, N);
		return true;
	}

	if (bEntryOpen && bEntryJudged && bOnTheMark && bOk && N != LastGoodNumber)
	{
		Fail(FString::Printf(
			TEXT("EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries: after entry ")
			TEXT("%d the hall went from %d to %d while the runner went on standing on ")
			TEXT("the mark without stepping off it. Standing on the mark does not keep ")
			TEXT("raising the number. %s"),
			EntriesSeen, LastGoodNumber, N, *Detail));
		return false;
	}

	if (!bEntryOpen && !bInFallWindow && bOk && bHaveGoodNumber
		&& Now - ModelChangedAt >= kAgreeSuppressS && Now - FallAt >= kFallSuppressS
		&& N != LastGoodNumber)
	{
		Fail(FString::Printf(
			TEXT("EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries: the hall went ")
			TEXT("from %d to %d at t=%.2f with nobody having stepped onto the mark. ")
			TEXT("Nothing else ever changes the number. %s"),
			LastGoodNumber, N, Now, *Detail));
		return false;
	}

	if (bOk && !bEntryOpen && !bInFallWindow && Now - ModelChangedAt >= kAgreeSuppressS
		&& Now - FallAt >= kFallSuppressS)
	{
		LastGoodNumber = N;
		bHaveGoodNumber = true;
	}
	return true;
}

bool ARoundHallFunctionalTest::GateTheLateSign(double Now)
{
	for (FSign& S : Signs)
	{
		if (!S.bFromTheHoist || !S.bLateWindowOpen)
		{
			continue;
		}
		if (Now - S.AppearedAt < kRaiseGraceS)
		{
			continue;
		}
		if (!S.Actor.IsValid())
		{
			continue;   // the agreement gate names a sign that stopped existing
		}
		bool bOk = false;
		const int32 V = ReadSign(S.Actor.Get(), bOk);
		if (!bOk)
		{
			Fail(FString::Printf(
				TEXT("TheNewSignComesUpOnTheNumberTheHallIsOn: the sign the hoist put up ")
				TEXT("(%s) is still blank %.2f s after it went up, and the hall was on ")
				TEXT("%d when it went up. A sign that arrives late comes up already ")
				TEXT("showing the number the hall is on. %s"),
				*S.Label, Now - S.AppearedAt, S.RaisedOnNumber, *SignReadout(Now)));
			return false;
		}
		if (V != S.RaisedOnNumber)
		{
			Fail(FString::Printf(
				TEXT("TheNewSignComesUpOnTheNumberTheHallIsOn: the sign the hoist put up ")
				TEXT("(%s) came up on %d and the hall was on %d when it went up (it ")
				TEXT("started the visit on %d). A sign that arrives late comes up ")
				TEXT("already showing the number the hall is on -- not the number the ")
				TEXT("hall started on, and not blank. %s"),
				*S.Label, V, S.RaisedOnNumber, StagedStart, *SignReadout(Now)));
			return false;
		}
	}
	return true;
}

bool ARoundHallFunctionalTest::GateTheDoorplate(double Now)
{
	// THE CROSSING POINT OF THE TWO HALVES OF THE TASK, and the only value in the run
	// that neither half produces on its own: the hall's number, sampled at the moment
	// the body walking in the room became a different object. Owning the number
	// perfectly and never noticing the body change fails here; re-bodying perfectly and
	// keeping the number on the body fails here too.
	if (!Stone.IsValid() || Stone->Doorplate == nullptr)
	{
		return true;   // GateTheHall owns "the stone is gone"
	}
	// The fresh runner has the two seconds the prompt promises it, plus three times the
	// half second a readout is promised, before this is looked at at all -- and never
	// while the fixture is still holding its own input after a fall.
	if (bInFallWindow || Now - DoorChangedAt < kDoorGraceS)
	{
		return true;
	}

	bool bOk = false;
	const int32 V = FirstWholeNumber(Stone->GetDoorplateText(), bOk);
	if (!bOk)
	{
		Fail(FString::Printf(
			TEXT("TheDoorplateShowsTheRoundTheRunnerWalkedInOn: the doorplate on the ")
			TEXT("entrance stone is blank at t=%.2f, and the runner now in the hall ")
			TEXT("(number %d of the visit) walked in while the hall was on %d. The ")
			TEXT("doorplate shows the round the runner now in the hall walked in on, and ")
			TEXT("a blank doorplate is not showing it. The hall is on %d. %s"),
			Now, DoorEpochs, DoorModel, ModelNumber, *SignReadout(Now)));
		return false;
	}
	if (V != DoorModel)
	{
		Fail(FString::Printf(
			TEXT("TheDoorplateShowsTheRoundTheRunnerWalkedInOn: the doorplate on the ")
			TEXT("entrance stone reads %d at t=%.2f and the runner now in the hall ")
			TEXT("(number %d of the visit) walked in while the hall was on %d. The hall ")
			TEXT("is on %d now, and the doorplate does not follow the hall -- it shows ")
			TEXT("the round the runner in the room walked in on, and it changes when a ")
			TEXT("different runner walks in. %s"),
			V, Now, DoorEpochs, DoorModel, ModelNumber, *SignReadout(Now)));
		return false;
	}
	return true;
}

bool ARoundHallFunctionalTest::GateEverybodyAgrees(double Now, bool bIgnoreSuppression)
{
	if (!bIgnoreSuppression)
	{
		if (Now < kFirstJudgedS)
		{
			return true;
		}
		if (Now - ModelChangedAt < kAgreeSuppressS)
		{
			return true;
		}
		if (bInFallWindow || Now - FallAt < kFallSuppressS)
		{
			return true;
		}
	}

	for (const FSign& S : Signs)
	{
		if (!S.Actor.IsValid())
		{
			Fail(FString::Printf(
				TEXT("EverySignInTheHallShowsTheNumberTheHallIsOn: sign %s belonged to ")
				TEXT("the hall and is no longer there to show anything, at t=%.2f. The ")
				TEXT("hall is on %d. %s"),
				*S.Label, Now, ModelNumber, *SignReadout(Now)));
			return false;
		}
		if (!S.Actor->BelongsToTheHall())
		{
			Fail(FString::Printf(
				TEXT("EverySignInTheHallShowsTheNumberTheHallIsOn: sign %s has stopped ")
				TEXT("saying it belongs to the hall, at t=%.2f. Every sign that belongs ")
				TEXT("to the hall shows the round number, and which ones do is not the ")
				TEXT("submission's to decide. %s"),
				*S.Label, Now, *SignReadout(Now)));
			return false;
		}
		if (!S.bPlaced && Now - S.AppearedAt < kRaiseSuppressS)
		{
			continue;
		}
		bool bOk = false;
		const int32 V = ReadSign(S.Actor.Get(), bOk);
		if (!bOk)
		{
			Fail(FString::Printf(
				TEXT("EverySignInTheHallShowsTheNumberTheHallIsOn: the hall is on %d and ")
				TEXT("sign %s is blank at t=%.2f. Every sign that belongs to the hall ")
				TEXT("shows the round number the hall is on, and a hall sign left blank ")
				TEXT("is not showing it. %s"),
				ModelNumber, *S.Label, Now, *SignReadout(Now)));
			return false;
		}
		if (V != ModelNumber)
		{
			Fail(FString::Printf(
				TEXT("EverySignInTheHallShowsTheNumberTheHallIsOn: the hall is on %d and ")
				TEXT("sign %s reads %d at t=%.2f. Every sign that belongs to the hall ")
				TEXT("shows the round number the hall is on, and they all show the same ")
				TEXT("one. %s"),
				ModelNumber, *S.Label, V, Now, *SignReadout(Now)));
			return false;
		}
	}

	int32 N = 0;
	FString Detail;
	if (ReadHallNumber(Now, N, Detail))
	{
		LastGoodNumber = N;
		bHaveGoodNumber = true;
	}
	return true;
}

// ---------------------------------------------------------------------------
// The drive
// ---------------------------------------------------------------------------

void ARoundHallFunctionalTest::BuildTransits(double Now)
{
	Transits.Reset();
	TransitIndex = 0;
	DwellUntil = -1.0;
	if (!Script.IsValidIndex(StopIndex))
	{
		return;
	}
	const FVector Here = Hero.IsValid() ? HeroAt() : Script[StopIndex].Where;
	const FVector Target = Script[StopIndex].Where;
	// Out to the lane, along the lane, in to the stop. Either of the first two may be
	// where the runner already is, in which case it is consumed on the first frame.
	Transits.Add(FVector(Here.X, LaneY, Here.Z));
	Transits.Add(FVector(Target.X, LaneY, Here.Z));

	double PathUu = FVector::Dist2D(Here, Transits[0]);
	PathUu += FVector::Dist2D(Transits[0], Transits[1]);
	PathUu += FVector::Dist2D(Transits[1], Target);
	// GENEROUS BY DESIGN, AND ONLY IN THE DIRECTION THAT CANNOT MASK A WRONG ANSWER.
	// The pawn walks at 500 uu/s; this allows for 220 uu/s plus four seconds of
	// acceleration and settling. A deadline that expired on a correct answer would
	// manufacture a failure, and this repo has done that four times in one night.
	LegDeadline = Now + kLegBaseS + PathUu / kLegSpeedUu;
}

void ARoundHallFunctionalTest::AdvanceStop(double Now)
{
	++StopIndex;
	if (!Script.IsValidIndex(StopIndex) || Script[StopIndex].Kind == EStopKind::Finish)
	{
		FinalGrade(Now);
		return;
	}
	BuildTransits(Now);
}

void ARoundHallFunctionalTest::DriveRunner(double Now)
{
	if (bHoldingInput || bGraded || !Script.IsValidIndex(StopIndex))
	{
		return;
	}
	if (!Hero.IsValid())
	{
		if (Now > LegDeadline)
		{
			if (!GateEverybodyAgrees(Now, /*bIgnoreSuppression=*/true) || !GateTheHall(Now))
			{
				return;
			}
			Fail(FString::Printf(
				TEXT("TheRunnerCouldNotGetWhereHeWasGoing: there is no live runner under ")
				TEXT("the player's control at stop %d of %d, at t=%.2f, long past the ")
				TEXT("time the walk needed. There is always a runner in the hall, and ")
				TEXT("after a fall a new one comes in within two seconds, able to walk on"),
				StopIndex + 1, Script.Num(), Now));
		}
		return;
	}

	const FStop& S = Script[StopIndex];
	const FVector Here = HeroAt();
	const FVector Aim = Transits.IsValidIndex(TransitIndex) ? Transits[TransitIndex]
														   : S.Where;
	const FVector Flat(Aim.X - Here.X, Aim.Y - Here.Y, 0.0);
	if (Flat.Size2D() > kWaypointUu)
	{
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		if (Now > LegDeadline)
		{
			// BEFORE ANY DEADLINE OVERRUN IS WRITTEN OFF, the two gates that describe a
			// broken hall are re-checked unconditionally, so a hall the submission
			// broke is named by its own gate rather than laundered into a drive fault.
			if (!GateEverybodyAgrees(Now, /*bIgnoreSuppression=*/true) || !GateTheHall(Now))
			{
				return;
			}
			Fail(FString::Printf(
				TEXT("TheRunnerCouldNotGetWhereHeWasGoing: the runner is still %.0f uu ")
				TEXT("short of stop %d of %d at t=%.2f, long past the time the walk ")
				TEXT("needed. They are at %s and were sent to %s -- either nothing the ")
				TEXT("player does reaches them, or they were put back somewhere they ")
				TEXT("cannot walk out of"),
				Flat.Size2D(), StopIndex + 1, Script.Num(), Now,
				*Here.ToCompactString(), *Aim.ToCompactString()));
		}
		return;
	}
	if (Transits.IsValidIndex(TransitIndex))
	{
		++TransitIndex;
		return;
	}

	// STAND HERE. Every gate is about a state that has settled, and a route that only
	// passes through a spot never gives the hall a chance to be judged.
	if (DwellUntil < 0.0)
	{
		DwellUntil = Now + S.DwellS;
		if (S.Kind == EStopKind::Restage)
		{
			DoTheRestage(Now);
		}
	}
	else if (Now >= DwellUntil)
	{
		if (S.Kind == EStopKind::Hole)
		{
			// The hole ends this stop by taking the runner. Getting here means it did
			// not, and the hall was given a hole that works.
			if (!GateEverybodyAgrees(Now, /*bIgnoreSuppression=*/true) || !GateTheHall(Now))
			{
				return;
			}
			Fail(FString::Printf(
				TEXT("TheHallKeepsWhatWasGivenToIt: the runner stood in the sinkhole for ")
				TEXT("%.1f s at t=%.2f and it took nobody. The hall was given a hole ")
				TEXT("that takes whoever walks in, and that is not the submission's to ")
				TEXT("stop"), S.DwellS, Now));
			return;
		}
		AdvanceStop(Now);
	}
}

void ARoundHallFunctionalTest::FinalGrade(double Now)
{
	if (bGraded)
	{
		return;
	}
	if (EntriesSeen < 5 || FallsJudged < 2 || SignsRaisedSeen < 2)
	{
		Fail(FString::Printf(
			TEXT("TheRunnerCouldNotGetWhereHeWasGoing: the walk ended at t=%.2f with %d ")
			TEXT("of 5 steps onto the mark, %d of 2 falls and %d of 2 signs raised. ")
			TEXT("Every one of those has to happen twice or more for the run to have ")
			TEXT("measured what it says it measures"),
			Now, EntriesSeen, FallsJudged, SignsRaisedSeen));
		return;
	}
	if (!GateEverybodyAgrees(Now, /*bIgnoreSuppression=*/true))
	{
		return;
	}
	if (!GateTheRelic(Now) || !GateTheHall(Now) || !GateTheDoorplate(Now))
	{
		return;
	}
	bGraded = true;
	FinishTest(EFunctionalTestResult::Succeeded,
		FString::Printf(TEXT("the hall came back on %d, all %d of its signs said so, and "
			"the doorplate said %d"), ModelNumber, Signs.Num(), DoorModel));
}

// ---------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------

void ARoundHallFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || bGraded || !bStaged)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World != nullptr ? double(World->GetTimeSeconds()) : 0.0;

	// -- A FALL IS REGISTERED BEFORE THE FIXTURE LOOKS FOR A BODY, and that ORDER
	// is load-bearing. A correct submission puts a fresh runner in on the very frame
	// the hole takes the old one, so by the time GetPlayerCharacter is asked again the
	// answer is already the NEW body. Noticing the fall first is what keeps
	// BodyBeforeFallName the name of the runner that actually fell -- reading it after
	// would record the replacement, and then "it is a DIFFERENT object from the one
	// that fell" would be false for every correct answer ever written.
	ObserveFall(Now);

	// -- who is walking now -------------------------------------------------
	if (ACharacter* const Live = UGameplayStatics::GetPlayerCharacter(GetWorld(), 0))
	{
		if (Live != Hero.Get())
		{
			Hero = Live;
			BodyName = Live->GetFName();
		}
		// A DIFFERENT BODY IS IN THE ROOM. Whatever the hall is on at this instant is
		// the round this runner walked in on, and it is what the doorplate has to show
		// from now until the next one walks in. Sampled here, off the fixture's own
		// model, so it is the same number whether the submission put the body in on the
		// frame of the fall or a second and a half later.
		if (BodyName != DoorBodyName)
		{
			DoorBodyName = BodyName;
			DoorModel = ModelNumber;
			DoorChangedAt = Now;
			++DoorEpochs;
			UE_LOG(LogTemp, Display,
				TEXT("[t3-roundhall] t=%.2f runner %d of the visit (%s) is in the hall, "
					 "and the hall is on %d -- that is what the doorplate has to show"),
				Now, DoorEpochs, *BodyName.ToString(), DoorModel);
		}
	}
	else
	{
		Hero.Reset();
	}

	// -- housekeeping, before anything is judged ----------------------------
	RefreshSigns(Now);
	ObserveMark(Now);

	// -- was the hall's own machinery still working when it was stood on? ----
	// Not a route check and not a drive check: a submission that quietly stops the
	// hoist or the hole would otherwise dodge the two gates they exist to feed, and
	// nothing else in the run would notice.
	if (!Hero.IsValid())
	{
		InsideHoistSince = -1.0;
		InsideHoleSince = -1.0;
	}
	else if (Hoist.IsValid() && Hole.IsValid())
	{
		const bool bOnPlate = InsideTrigger(Hoist->Volume);
		if (bOnPlate)
		{
			if (InsideHoistSince < 0.0)
			{
				InsideHoistSince = Now;
				HoistCountAtEnter = Hoist->GetSignsRaised();
			}
			else if (Now - InsideHoistSince > kHoistMustFireS
				&& Hoist->GetSignsRaised() == HoistCountAtEnter)
			{
				Fail(FString::Printf(
					TEXT("TheHallKeepsWhatWasGivenToIt: the runner has stood on the ")
					TEXT("hoist plate for %.1f s at t=%.2f and no sign has gone up. The ")
					TEXT("hall was given a hoist that runs itself, and stopping it is ")
					TEXT("not the submission's to do"), Now - InsideHoistSince, Now));
				return;
			}
		}
		else
		{
			InsideHoistSince = -1.0;
		}

		const bool bInHole = InsideTrigger(Hole->Volume);
		if (bInHole)
		{
			if (InsideHoleSince < 0.0)
			{
				InsideHoleSince = Now;
				LostCountAtEnter = Hole->GetRunnersLost();
			}
			else if (Now - InsideHoleSince > kHoleMustTakeS
				&& Hole->GetRunnersLost() == LostCountAtEnter)
			{
				Fail(FString::Printf(
					TEXT("TheHallKeepsWhatWasGivenToIt: the runner has stood in the ")
					TEXT("sinkhole for %.1f s at t=%.2f and it has taken nobody. The ")
					TEXT("hall was given a hole that takes whoever walks in, and ")
					TEXT("stopping it is not the submission's to do"),
					Now - InsideHoleSince, Now));
				return;
			}
		}
		else
		{
			InsideHoleSince = -1.0;
		}
	}

	// -- the gates, in the order that makes each one name its own answer ----
	if (!GateTheRelic(Now)) { return; }
	if (!GateTheHall(Now)) { return; }
	if (!GateTheFall(Now)) { return; }
	if (!GateTheBody(Now)) { return; }
	if (!GateTheStep(Now)) { return; }
	if (!GateTheLateSign(Now)) { return; }
	if (!GateTheDoorplate(Now)) { return; }
	if (!GateEverybodyAgrees(Now, /*bIgnoreSuppression=*/false)) { return; }

	// -- let go of the fresh body once it has been judged -------------------
	if (bInFallWindow && Now - FallAt >= kFallHoldS)
	{
		bInFallWindow = false;
		bHoldingInput = false;
		if (Script.IsValidIndex(StopIndex) && Script[StopIndex].Kind == EStopKind::Hole)
		{
			AdvanceStop(Now);
		}
		else
		{
			BuildTransits(Now);
		}
		if (bGraded)
		{
			return;
		}
	}

	DriveRunner(Now);
}

void ARoundHallFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FString DoorReads =
		Stone.IsValid() ? Stone->GetDoorplateText() : FString(TEXT("<no stone>"));
	const FString Readout = SignReadout(Now);
	UE_LOG(LogTemp, Display,
		TEXT("[t3-roundhall calib] cp%d t=%.2f stop=%d/%d model=%d step=%d entries=%d "
			 "falls=%d/%d raised=%d door=%d/'%s' at=(%.0f,%.0f) | %s"),
		Index, Now, StopIndex + 1, Script.Num(), ModelNumber, StagedStepNow, EntriesSeen,
		FallsJudged, FallsSeen, SignsRaisedSeen, DoorModel, *DoorReads,
		HeroAt().X, HeroAt().Y, *Readout);
}

void ARoundHallFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!bStaged)
	{
		return;
	}
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex >= kSentinelIndex)
	{
		// THE BASE-FIXTURE LAW. The run-level gate is evaluated when the walk completes
		// AND again here, because the base class ends the test the moment the last
		// scheduled checkpoint is sampled -- a grade hung off an event that never
		// arrives would otherwise be skipped and the run would read green.
		FinalGrade(TimeSeconds);
	}
}
