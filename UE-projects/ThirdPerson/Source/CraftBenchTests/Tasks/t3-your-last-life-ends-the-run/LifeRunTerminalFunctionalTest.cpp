// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See the header for the model, the calibration hazard and the gate precedence.

#include "LifeRunTerminalFunctionalTest.h"

#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---------------------------------------------------------- DISCLOSED numbers
	// Every one of these appears verbatim in the prompt the agent reads.
	constexpr double kSettleS = 0.5;          // "half a second to catch up"
	constexpr double kComeBackS = 1.0;        // "back on its own marker within 1 second"
	constexpr double kOnMarkerUu = 120.0;     // "within 120 cm of that marker's centre"
	constexpr double kLeftWhereClaimedUu = 150.0;  // "within 150 cm of that spot"
	constexpr double kBystanderDriftUu = 40.0;     // "stays within 40 cm of its own marker"
	constexpr int32 kLampCount = 6;           // "six lamps float in a row"
	constexpr int32 kPaintFloor = 1;          // "never less than one"
	constexpr int32 kPaintCeil = 6;           // "never more than six"

	// -------------------------------------- UNDISCLOSED: fixture clocking + geometry.
	// EVERY ONE IS A WIDENING of the contract above, never a narrowing.
	/** Nothing is judged for this long after a runner's own model moves: 1.5x the
	 *  half second the prompt promises. */
	constexpr double kSuppressAfterChangeS = kSettleS * 1.5;      // 0.75
	/** Added to every disclosed deadline before it is gauged, so an answer that uses
	 *  the whole of its allowance is never failed for being late. */
	constexpr double kGaugeSlackS = 0.35;
	constexpr double kComeBackGaugeAtS = kComeBackS + kGaugeSlackS;      // 1.35
	constexpr double kSettleGaugeFromS = kSettleS + kGaugeSlackS;        // 0.85
	/** How long each windowed gate stays armed after its event. */
	constexpr double kCrossWindowS = 1.8;
	constexpr double kLastLifeWindowS = 2.5;
	constexpr double kRepaintWindowS = 1.8;
	constexpr double kWinWindowS = 1.8;
	/** A still-running runner this close to a trigger's edge is not judged: it is the
	 *  band in which an overlap-driven answer and a point-in-box answer legitimately
	 *  disagree (one capsule radius of travel), plus a wide margin. */
	constexpr double kBoundaryBandUu = 160.0;
	/** Every crossing is staged from this far outside the face it approaches, and the
	 *  drive always aims at the patch's own centre line -- head-on, never a skim. */
	constexpr double kApproachClearUu = 400.0;
	constexpr double kWaypointUu = 90.0;
	/** A teleport is anything bigger than this in one frame. 2x the template's top
	 *  walk plus 30 cm; the smallest wrong teleport in this level is 2,400 cm. */
	constexpr double kWalkStepSlack = 2.0;
	constexpr double kWalkStepPadUu = 30.0;
	/** How far from the patch a runner has to be for the drive to conclude that the
	 *  submission moved it, and stop pushing it back in. */
	constexpr double kMovedAwayUu = 600.0;
	/** A cross phase releases input at the plain box; these are its only escapes. */
	constexpr double kCrossCarryTimeoutS = 1.5;
	/** How long each hold lasts, measured from the event it is anchored to. */
	constexpr double kStandAfterCrossS = 2.2;
	constexpr double kStandAfterTerminalS = 3.2;
	constexpr double kStandAfterConflictS = 2.6;
	/** How long the win-leg runner is held on the finish disc while it is SHORT of
	 *  what the disc asks for, and again while the disc's own number moves. */
	constexpr double kStandOnDiscS = 2.8;
	constexpr double kRepaintQuietS = 0.6;
	constexpr double kRepaintHoldS = 2.2;
	constexpr double kSettlePhaseS = 2.0;

	/** Staging safety. */
	constexpr double kMarkerSpacingFloorUu = kOnMarkerUu * 4.0;   // 480
	constexpr double kTriggerClearUu = 600.0;
	constexpr double kPlacementDriftUu = 2.0;
	/** The crossing lane must be THIS much nearer another runner's marker than the
	 *  crossing runner's own, or "go to the nearest marker" is not discriminated. */
	constexpr double kOwnershipMarginUu = 400.0;
	/** How far outside the patch's own Y face the bypass corridor runs. */
	constexpr double kBypassMarginUu = 500.0;
	/** A runner the drive pushed for a whole derived deadline and that moved less
	 *  than this has not been walked -- it is being HELD. Nothing in the level can
	 *  do that: every prop is non-colliding and the route was traced for floor. */
	constexpr double kPinnedUu = 150.0;

	/** Checkpoints are calibration logging plus the sentinel; the fixture finishes
	 *  itself the moment its last phase completes. The base class ends the test at the
	 *  LAST scheduled checkpoint, so the sentinel sits far past the ~200 s the drive
	 *  models -- move it if the drive ever grows. */
	constexpr double kCheckpointEveryS = 5.0;
	constexpr int32 kGradedCheckpoints = 96;      // 5 s .. 480 s
	constexpr double kSentinelAtS = 500.0;

	const TCHAR* kWordRunning = TEXT("RUNNING");
	const TCHAR* kWordWon = TEXT("WON");
	const TCHAR* kWordLost = TEXT("LOST");

	/** The first run of ASCII letters in a string, upper-cased. "LOST!" and "lost"
	 *  both read as LOST -- a widening of the disclosed contract. */
	FString FirstLetterRun(const FString& In)
	{
		int32 Start = INDEX_NONE;
		for (int32 i = 0; i < In.Len(); ++i)
		{
			const TCHAR C = In[i];
			const bool bLetter = (C >= TEXT('A') && C <= TEXT('Z'))
				|| (C >= TEXT('a') && C <= TEXT('z'));
			if (bLetter && Start == INDEX_NONE)
			{
				Start = i;
			}
			else if (!bLetter && Start != INDEX_NONE)
			{
				return In.Mid(Start, i - Start).ToUpper();
			}
		}
		return Start == INDEX_NONE ? FString() : In.Mid(Start).ToUpper();
	}

	FString Describe(const FVector& V)
	{
		return FString::Printf(TEXT("(%.0f,%.0f)"), V.X, V.Y);
	}
}

ALifeRunTerminalFunctionalTest::ALifeRunTerminalFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Reflection. By NAME, never through a cast: the fixture never needs the agent's
// class layout, and the SAME helper writes the paint, so an overridden setter cannot
// intercept the staging and then satisfy the anti-tamper read-back.
// ---------------------------------------------------------------------------

int32 ALifeRunTerminalFunctionalTest::ReadInt(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0;
}

float ALifeRunTerminalFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0.0f;
}

bool ALifeRunTerminalFunctionalTest::WriteInt(AActor* A, const TCHAR* Name,
	int32 Value) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

int32 ALifeRunTerminalFunctionalTest::DemandNow() const
{
	bool bOk = false;
	// LIVE, every frame, exactly like a marker's: the goal's own number moves while
	// the runs are going, and nothing announces it.
	return ReadInt(Disc.Get(), TEXT("DemandedLives"), bOk);
}

int32 ALifeRunTerminalFunctionalTest::PaintedOn(int32 MarkerIndex) const
{
	if (!Markers.IsValidIndex(MarkerIndex))
	{
		return 0;
	}
	bool bOk = false;
	// LIVE, every frame. The board moves while the runs are going.
	return ReadInt(Markers[MarkerIndex].Get(), TEXT("PaintedLives"), bOk);
}

// ---------------------------------------------------------------------------
// The readouts. What a reviewer would see, and nothing else.
// ---------------------------------------------------------------------------

int32 ALifeRunTerminalFunctionalTest::LitCountOf(const FRunner& R, int32& OutTotal) const
{
	OutTotal = 0;
	AActor* const A = R.Actor.Get();
	if (A == nullptr)
	{
		return 0;
	}
	TArray<UPointLightComponent*> Glows;
	A->GetComponents<UPointLightComponent>(Glows);

	// THE ROW THE LEVEL BUILT, resolved by the names the level built it under when all
	// six are still there. Any OTHER light a submission hangs on a runner is then
	// ignored rather than counted -- the prompt never says a runner may not glow, and
	// failing an answer for something nobody asked about is a manufactured FAIL. When
	// the row cannot be resolved by name (a submission may legitimately rebuild it),
	// every point light on the runner counts, which keeps a MISSING lamp a fault
	// either way.
	{
		TArray<UPointLightComponent*> Row;
		Row.Init(nullptr, kLampCount);
		int32 Named = 0;
		for (UPointLightComponent* const G : Glows)
		{
			if (G == nullptr)
			{
				continue;
			}
			const FString Name = G->GetName();
			if (!Name.StartsWith(TEXT("Lamp"), ESearchCase::CaseSensitive))
			{
				continue;
			}
			const FString Tail = Name.RightChop(4);
			if (!Tail.IsNumeric())
			{
				continue;
			}
			const int32 Index = FCString::Atoi(*Tail);
			if (Row.IsValidIndex(Index) && Row[Index] == nullptr)
			{
				Row[Index] = G;
				++Named;
			}
		}
		if (Named == kLampCount)
		{
			Glows = Row;
		}
	}

	OutTotal = Glows.Num();
	int32 Lit = 0;
	for (const UPointLightComponent* const G : Glows)
	{
		if (G == nullptr)
		{
			continue;
		}
		// Hidden and zero-intensity both read as dark: they look identical.
		if (!G->IsVisible() || G->bHiddenInGame)
		{
			continue;
		}
		if (G->Intensity > 0.0f)
		{
			++Lit;
		}
	}
	return Lit;
}

int32 ALifeRunTerminalFunctionalTest::WordComponentsOf(const FRunner& R) const
{
	AActor* const A = R.Actor.Get();
	if (A == nullptr)
	{
		return 0;
	}
	TArray<UTextRenderComponent*> Texts;
	A->GetComponents<UTextRenderComponent>(Texts);
	return Texts.Num();
}

FString ALifeRunTerminalFunctionalTest::WordOf(const FRunner& R) const
{
	AActor* const A = R.Actor.Get();
	if (A == nullptr)
	{
		return FString();
	}
	TArray<UTextRenderComponent*> Texts;
	A->GetComponents<UTextRenderComponent>(Texts);
	const UTextRenderComponent* Chosen = nullptr;
	for (const UTextRenderComponent* const T : Texts)
	{
		if (T != nullptr && T->GetName() == TEXT("WordText"))
		{
			Chosen = T;
			break;
		}
	}
	if (Chosen == nullptr && Texts.Num() == 1)
	{
		Chosen = Texts[0];
	}
	// UTextRenderComponent has no GetText() in 5.8; Text is the public member.
	return Chosen != nullptr ? FirstLetterRun(Chosen->Text.ToString()) : FString();
}

// ---------------------------------------------------------------------------
// The rule the level is asked to run, run here against the same live world.
// ---------------------------------------------------------------------------

int32 ALifeRunTerminalFunctionalTest::RemainingFor(const FRunner& R) const
{
	// READ AT THE POINT OF USE. Nothing here is ever latched.
	return FMath::Max(0, PaintedOn(R.MarkerIndex) - R.Deaths);
}

int32 ALifeRunTerminalFunctionalTest::ExpectedLitFor(const FRunner& R) const
{
	switch (R.State)
	{
	case ERunState::Won:  return R.FrozenLit;
	case ERunState::Lost: return 0;
	default:              return FMath::Clamp(RemainingFor(R), 0, kLampCount);
	}
}

const TCHAR* ALifeRunTerminalFunctionalTest::ExpectedWordFor(const FRunner& R) const
{
	switch (R.State)
	{
	case ERunState::Won:  return kWordWon;
	case ERunState::Lost: return kWordLost;
	default:              return kWordRunning;
	}
}

bool ALifeRunTerminalFunctionalTest::InPatchArmed(const FVector& At) const
{
	if (!PatchBox.IsValid())
	{
		return false;
	}
	const FVector Local = PatchXform.InverseTransformPosition(At);
	return FMath::Abs(Local.X) <= PatchExtent.X + CapsuleRadius
		&& FMath::Abs(Local.Y) <= PatchExtent.Y + CapsuleRadius
		&& FMath::Abs(Local.Z) <= PatchExtent.Z;
}

bool ALifeRunTerminalFunctionalTest::InPatchPlain(const FVector& At) const
{
	if (!PatchBox.IsValid())
	{
		return false;
	}
	const FVector Local = PatchXform.InverseTransformPosition(At);
	return FMath::Abs(Local.X) <= PatchExtent.X
		&& FMath::Abs(Local.Y) <= PatchExtent.Y
		&& FMath::Abs(Local.Z) <= PatchExtent.Z;
}

double ALifeRunTerminalFunctionalTest::PlanarDistToPatch(const FVector& At) const
{
	if (!PatchBox.IsValid())
	{
		return 1.0e9;
	}
	const FVector Local = PatchXform.InverseTransformPosition(At);
	const double Dx = FMath::Abs(Local.X) - PatchExtent.X;
	const double Dy = FMath::Abs(Local.Y) - PatchExtent.Y;
	if (Dx > 0.0 || Dy > 0.0)
	{
		return FMath::Sqrt(FMath::Square(FMath::Max(Dx, 0.0))
			+ FMath::Square(FMath::Max(Dy, 0.0)));
	}
	return FMath::Max(Dx, Dy);   // negative inside
}

double ALifeRunTerminalFunctionalTest::PlanarDistToDisc(const FVector& At) const
{
	return FVector::Dist2D(At, DiscStagedAt) - double(DiscRadius);
}

bool ALifeRunTerminalFunctionalTest::OnDiscArmed(const FVector& At) const
{
	return PlanarDistToDisc(At) <= CapsuleRadius;
}

void ALifeRunTerminalFunctionalTest::StepModel(double Now)
{
	for (FRunner& R : Runners)
	{
		const ACharacter* const C = R.Actor.Get();
		if (C == nullptr)
		{
			continue;
		}
		const FVector At = C->GetActorLocation();

		// ---- the crumbling ground: an EDGE, never a dwell ----------------------
		const bool bInPatch = InPatchArmed(At);
		if (bInPatch && !R.bInPatchLastFrame)
		{
			++R.Crossings;
			R.LastCrossingAt = Now;
			R.ClaimSpot = At;
			R.bClaimSpotIsPlainEntry = false;
			R.bLastCrossingWasFinal = false;
			if (R.State == ERunState::Running)
			{
				R.LitBeforeCrossing = R.LitLastJudged;
				++R.Deaths;
				++R.SpendingCrossings;
				// THE OFF-BY-ONE THIS TASK IS BUILT AROUND: the life is spent on the
				// DEATH, and "was that the last one?" is asked immediately, of the
				// board as it reads NOW.
				if (RemainingFor(R) <= 0)
				{
					R.State = ERunState::Lost;
					R.bTerminalWasLoss = true;
					R.TerminalAt = Now;
					R.bLastCrossingWasFinal = true;
				}
				R.LastModelChangeAt = Now;
			}
			else
			{
				// A run that has ended stays ended: nothing changes, so nothing is
				// suppressed either -- this is exactly the frame gate 7 must judge.
				++R.ConflictEvents;
			}
		}
		// The claim spot is refined to the PLAIN-box entry the moment it happens: that
		// is the fixture's own geometry, independent of anything the submission does,
		// and it is where a correct answer comes to rest (within ~28 cm of coasting).
		if (!R.bClaimSpotIsPlainEntry && R.LastCrossingAt >= 0.0 && InPatchPlain(At))
		{
			R.ClaimSpot = At;
			R.bClaimSpotIsPlainEntry = true;
		}
		R.bInPatchLastFrame = bInPatch;

		// ---- the finish disc: a CONDITION, not an edge --------------------------
		// The ARRIVAL is an edge -- it is what a conflicting event is counted from --
		// but WINNING is not. The goal opens the instant a still-running runner
		// standing on it is holding at least what the disc asks for, and BOTH halves
		// of that question move under its feet with nothing to announce them: its own
		// board is re-painted, and so is the disc. So it is asked every frame.
		const bool bOnDisc = OnDiscArmed(At);
		if (bOnDisc && !R.bOnDiscLastFrame)
		{
			++R.DiscArrivals;
			if (R.State != ERunState::Running)
			{
				++R.ConflictEvents;
			}
		}
		if (bOnDisc && R.State == ERunState::Running && RemainingFor(R) >= DemandNow())
		{
			// WINNING SPENDS NOTHING: the row freezes exactly where it stood the moment
			// the goal opened, which may be long after this runner walked on.
			R.LitBeforeWin = R.LitLastJudged;
			R.FrozenLit = FMath::Clamp(RemainingFor(R), 0, kLampCount);
			R.State = ERunState::Won;
			R.bTerminalWasLoss = false;
			R.TerminalAt = Now;
			R.FirstWinAt = Now;
			R.LastModelChangeAt = Now;
		}
		R.bOnDiscLastFrame = bOnDisc;
	}
}

// ---------------------------------------------------------------------------
// Resolution. Everything here ends the run as HARNESS-PRECONDITION rather than as a
// model failure: a level that is not staged as authored is ours, never the agent's.
// ---------------------------------------------------------------------------

FString ALifeRunTerminalFunctionalTest::DescribeBrokenPlayerInput() const
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return FString();
	}
	TArray<FString> Problems;

	// Half one: the pawn's own Enhanced Input actions, read by PROPERTY NAME so a
	// renamed or subclassed pawn still answers. AThirdPersonCharacter DECLARES these
	// four and assigns none, so a native subclass that does not load them binds
	// nothing at all -- and the map still grades byte-identically while being
	// completely uncontrollable to play.
	if (Runners.IsValidIndex(0) && Runners[0].Actor.IsValid())
	{
		TArray<FString> Unbound;
		for (const TCHAR* const Name : { TEXT("MoveAction"), TEXT("LookAction"),
										 TEXT("MouseLookAction"), TEXT("JumpAction") })
		{
			const FObjectProperty* const Prop =
				FindFProperty<FObjectProperty>(Runners[0].Actor->GetClass(), Name);
			if (Prop == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(Runners[0].Actor.Get()) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Problems.Add(FString::Printf(TEXT("the runner (%s) has nothing bound to %s"),
				*Runners[0].Actor->GetClass()->GetName(),
				*FString::Join(Unbound, TEXT(", "))));
		}
	}

	// Half two: a mapping context has to be applied, or no key reaches any of those
	// actions even when all four are set. This level names its OWN game mode, which
	// replaces GlobalDefaultGameMode -- so it has to re-state the controller that
	// carries the mapping context, or pressing Play leaves nothing anyone can drive.
	const AGameModeBase* const GameMode = World->GetAuthGameMode();
	const UClass* const PCClass =
		GameMode != nullptr ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the player "
						  "gets a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts = FindFProperty<FArrayProperty>(
				 PCClass, TEXT("DefaultMappingContexts")))
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

bool ALifeRunTerminalFunctionalTest::ResolveLeg()
{
	// The leg is taken from the run's OWN framerate, so the two PIE processes stage
	// different numbers and a life count mined out of the committed .umap is wrong on
	// both. The command line is authoritative (the runner always passes -FPS=<rate>);
	// the engine's fixed timestep is the fallback.
	int32 Fps = 0;
	if (!FParse::Value(FCommandLine::Get(), TEXT("FPS="), Fps) || Fps <= 0)
	{
		const double Dt = FApp::GetFixedDeltaTime();
		Fps = (Dt > KINDA_SMALL_NUMBER) ? FMath::RoundToInt(1.0 / Dt) : 0;
	}

	if (Fps >= 40)
	{
		// 60 Hz leg.
		Stage = FStaging{ Fps, /*A*/3, /*B*/5, /*C*/6, /*A up*/4, /*B down*/3,
						  /*A final*/1, /*B final*/2,
						  /*the finish asks*/3, /*then*/5, /*then*/1 };
		return true;
	}
	if (Fps >= 10 && Fps < 40)
	{
		// 20 Hz leg -- DIFFERENT numbers on every marker.
		Stage = FStaging{ Fps, /*A*/2, /*B*/6, /*C*/3, /*A up*/4, /*B down*/5,
						  /*A final*/6, /*B final*/1,
						  /*the finish asks*/5, /*then*/6, /*then*/2 };
		return true;
	}

	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the run's fixed timestep resolves to %d frames per "
			 "second, which is neither of this task's two legs (60 and 20). The "
			 "staging table is chosen from the framerate, so the fixture cannot tell "
			 "which numbers to paint"), Fps));
	return false;
}

bool ALifeRunTerminalFunctionalTest::ValidateStagingTable()
{
	const int32 Values[] = { Stage.StartA, Stage.StartB, Stage.StartC,
							 Stage.RepaintA, Stage.RepaintB, Stage.FinalA, Stage.FinalB,
							 Stage.DemandStart, Stage.DemandMid, Stage.DemandEnd };
	for (const int32 V : Values)
	{
		if (V < kPaintFloor || V > kPaintCeil)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the %d Hz staging table wants to paint %d, "
					 "and the level promises every marker reads between %d and %d"),
				Stage.Rate, V, kPaintFloor, kPaintCeil));
			return false;
		}
	}

	// No two markers may ever read the same number AT ANY INSTANT -- including the
	// instant between the two final writes, which happen one after the other.
	struct FInstant { int32 A; int32 B; int32 C; const TCHAR* What; };
	const FInstant Instants[] = {
		{ Stage.StartA,   Stage.StartB,   Stage.StartC, TEXT("at the start") },
		{ Stage.RepaintA, Stage.StartB,   Stage.StartC, TEXT("after the near runner's board goes up") },
		{ Stage.RepaintA, Stage.RepaintB, Stage.StartC, TEXT("after the middle runner's board comes down") },
		{ Stage.FinalA,   Stage.RepaintB, Stage.StartC, TEXT("between the two last writes") },
		{ Stage.FinalA,   Stage.FinalB,   Stage.StartC, TEXT("after the two last writes") },
	};
	for (const FInstant& I : Instants)
	{
		if (I.A == I.B || I.A == I.C || I.B == I.C)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the %d Hz staging table has two markers "
					 "reading the same number %s (%d / %d / %d), so a submission that "
					 "read the wrong marker would grade identically"),
				Stage.Rate, I.What, I.A, I.B, I.C));
			return false;
		}
	}

	// A RE-PAINT ALONE NEVER ENDS A RUN -- the prompt says so, so the fixture must
	// never create the ambiguous case. Both mid-run re-paints land on a runner with
	// exactly one death behind it.
	if (Stage.RepaintA - 1 < 1 || Stage.RepaintB - 1 < 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the %d Hz staging table re-paints a marker to "
				 "%d / %d after that runner's first death, which would leave it on "
				 "zero -- and the level promises that moving a marker's number never "
				 "claims anybody"), Stage.Rate, Stage.RepaintA, Stage.RepaintB));
		return false;
	}
	// The first crossing must NOT be the last one, or there is no non-final crossing
	// to gauge the return gate on.
	if (Stage.StartA - 1 < 1 || Stage.StartB - 1 < 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the %d Hz staging table starts a driven runner "
				 "on %d / %d, so its very first crossing would be its last and nothing "
				 "would ever gauge the come-back-to-your-own-marker rule"),
			Stage.Rate, Stage.StartA, Stage.StartB));
		return false;
	}
	// The win leg must be able to survive TWO deaths and still win with lamps lit.
	if (Stage.RepaintB - 2 < 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the %d Hz staging table leaves the win-leg "
				 "runner on %d after two deaths, so it would be LOST before it ever "
				 "reached the finish and the win leg could not run"),
			Stage.Rate, Stage.RepaintB - 2));
		return false;
	}
	// The last re-paint has to be a real change, or the third conflicting event that
	// ARunThatEndedNeverChangesAgain rides on is vacuous.
	if (Stage.FinalA == Stage.RepaintA || Stage.FinalB == Stage.RepaintB)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the %d Hz staging table's last re-paint does "
				 "not change either ended marker (%d -> %d, %d -> %d), so it proves "
				 "nothing about an ended run staying ended"),
			Stage.Rate, Stage.RepaintA, Stage.FinalA, Stage.RepaintB, Stage.FinalB));
		return false;
	}

	// ---- WHAT THE FINISH ASKS FOR -------------------------------------------
	// The win leg reaches the disc holding (RepaintB - 2). Every rule below exists
	// so that the leg MEASURES something rather than happening to pass.
	{
		const int32 Holding = Stage.RepaintB - 2;
		// (1) IT MUST ARRIVE SHORT, or the standing-win half never happens at all.
		if (Stage.DemandStart <= Holding || Stage.DemandMid <= Holding)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the %d Hz staging has the finish asking for "
					 "%d and then %d while the win-leg runner arrives holding %d, so it "
					 "would be let through the moment it walked on and nothing would ever "
					 "gauge what the goal asks for"),
				Stage.Rate, Stage.DemandStart, Stage.DemandMid, Holding));
			return false;
		}
		// (2) IT MUST BE NO MORE THAN THAT RUNNER'S BOARD, so a submission that
		// measures the goal against the PAINTED number instead of against what the
		// runner has LEFT is wrongly let through, and is named for it.
		if (Stage.DemandStart > Stage.RepaintB)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the %d Hz staging has the finish asking for "
					 "%d while the win-leg runner's board reads %d, so reading the board "
					 "instead of what is left would grade exactly like reading what is "
					 "left and that wrong answer would go unnamed"),
				Stage.Rate, Stage.DemandStart, Stage.RepaintB));
			return false;
		}
		// (3) THE LAST MOVE MUST OPEN IT, or the win leg can never be won at all.
		if (Stage.DemandEnd > Holding)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the %d Hz staging brings the finish down to "
					 "%d while the win-leg runner is holding %d, so the goal never opens "
					 "and the win leg is arithmetically unreachable"),
				Stage.Rate, Stage.DemandEnd, Holding));
			return false;
		}
		// (4) BOTH MOVES MUST BE REAL MOVES.
		if (Stage.DemandMid == Stage.DemandStart || Stage.DemandEnd == Stage.DemandMid)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the %d Hz staging moves the finish's number "
					 "%d -> %d -> %d, and a move that changes nothing proves nothing about "
					 "reading it at the moment it is needed"),
				Stage.Rate, Stage.DemandStart, Stage.DemandMid, Stage.DemandEnd));
			return false;
		}
	}

	// The loss leg's terminal crossing index follows from the table: after the
	// re-paint, remaining is (RepaintA - deaths), so the run ends on crossing RepaintA.
	PredictedFinalCrossing = Stage.RepaintA;
	if (PredictedFinalCrossing < 4)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the %d Hz staging table gives the crumbling "
				 "ground only %d spending crossing(s) on the loss-leg runner, and the "
				 "re-trigger rule needs at least four in two matched pairs"),
			Stage.Rate, PredictedFinalCrossing));
		return false;
	}
	return true;
}

bool ALifeRunTerminalFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();

	// ---- the markers -------------------------------------------------------
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LifeMarker")), Found);
	if (Found.Num() != 3)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the floor is not staged as authored - expected "
				 "three marker discs tagged LifeMarker, found %d"), Found.Num()));
		return false;
	}
	Found.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetActorLocation().Y < R.GetActorLocation().Y;
	});
	for (AActor* const A : Found)
	{
		bool bOk = false;
		ReadInt(A, TEXT("PaintedLives"), bOk);
		if (!bOk)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the marker %s does not expose PaintedLives "
					 "readably, so the fixture cannot tell what the board says"),
				*A->GetName()));
			return false;
		}
		Markers.Add(A);
		MarkerStagedAt.Add(A->GetActorLocation());
		MarkerStagedPaint.Add(0);
	}

	// ---- the runners -------------------------------------------------------
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LifeRunner")), Found);
	if (Found.Num() != 3)
	{
		// A submission that dropped the runners' own marking is the submission's
		// doing, not the level's -- and a non-graded harness exit would launder it.
		TArray<AActor*> AnyCharacters;
		UGameplayStatics::GetAllActorsOfClass(World, ACharacter::StaticClass(),
			AnyCharacters);
		if (AnyCharacters.Num() == 3)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: three runners stand in the level and "
					 "only %d of them still carry the marking the level gave them. "
					 "The runners are not yours to re-label"), Found.Num()));
			return false;
		}
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the floor is not staged as authored - expected "
				 "three runners tagged LifeRunner, found %d (and %d character(s) in "
				 "the level at all)"), Found.Num(), AnyCharacters.Num()));
		return false;
	}

	ACharacter* const Player = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (Player == nullptr || !Player->ActorHasTag(FName(TEXT("LifeRunner"))))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the level's own rules did not put a runner "
				 "under the player's control when play began, so there is nobody for a "
				 "person -- or the fixture -- to walk"));
		return false;
	}

	ACharacter* Win = nullptr;
	ACharacter* Bystander = nullptr;
	for (AActor* const A : Found)
	{
		ACharacter* const C = Cast<ACharacter>(A);
		if (C == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s is marked as a runner but is not a "
					 "character, so it cannot be walked"), *A->GetName()));
			return false;
		}
		if (C == Player)
		{
			continue;
		}
		if (A->ActorHasTag(FName(TEXT("RunnerLaneB")))) { Win = C; }
		else if (A->ActorHasTag(FName(TEXT("RunnerLaneC")))) { Bystander = C; }
	}
	if (Win == nullptr || Bystander == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the two placed runners are not told apart by "
				 "the per-instance marks the level authors (RunnerLaneB and "
				 "RunnerLaneC), so the fixture cannot say which one it is driving"));
		return false;
	}

	const TCHAR* const Labels[3] = { TEXT("the near runner"), TEXT("the middle runner"),
									 TEXT("the far runner") };
	ACharacter* const Ordered[3] = { Player, Win, Bystander };
	for (int32 i = 0; i < 3; ++i)
	{
		FRunner R;
		R.Actor = Ordered[i];
		R.Identity = Ordered[i];
		R.Label = Labels[i];
		Runners.Add(R);
	}

	for (const FRunner& R : Runners)
	{
		const ACharacter* const C = R.Actor.Get();
		if (C->GetMesh() == nullptr || C->GetMesh()->GetSkeletalMeshAsset() == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s is not visibly represented, so it would "
					 "grade clean and show a reviewer nothing"), R.Label));
			return false;
		}
		int32 Total = 0;
		LitCountOf(R, Total);
		if (Total != kLampCount || WordComponentsOf(R) < 1)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s carries %d lamp(s) and %d floating "
					 "word(s); the level builds six lamps and one word on every "
					 "runner"), R.Label, Total, WordComponentsOf(R)));
			return false;
		}
	}

	// A PLACED character with no controller is INERT -- AddMovementInput lands nowhere
	// (CharacterMovementComponent.cpp:1749). The class asks for one at level open; ask
	// again here so the drive can never be defeated by that setting alone.
	for (int32 i = 1; i < Runners.Num(); ++i)
	{
		ACharacter* const C = Runners[i].Actor.Get();
		if (C != nullptr && C->GetController() == nullptr)
		{
			C->SpawnDefaultController();
		}
	}

	// ---- whose marker is whose: resolved ONCE, at t=0, exactly as promised ----
	for (FRunner& R : Runners)
	{
		double Nearest = TNumericLimits<double>::Max();
		int32 NearestIdx = INDEX_NONE;
		for (int32 m = 0; m < Markers.Num(); ++m)
		{
			const double D = FVector::Dist2D(MarkerStagedAt[m], R.Actor->GetActorLocation());
			if (D < Nearest) { Nearest = D; NearestIdx = m; }
		}
		if (NearestIdx == INDEX_NONE || Nearest > 200.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not begin the run standing on a "
					 "marker (nearest one is %.0f cm away), and the level promises "
					 "every runner opens on its own"), R.Label, Nearest));
			return false;
		}
		R.MarkerIndex = NearestIdx;
		R.OwnMarker = Markers[NearestIdx];
		R.MarkerAt = MarkerStagedAt[NearestIdx];
	}
	if (Runners[0].MarkerIndex == Runners[1].MarkerIndex
		|| Runners[0].MarkerIndex == Runners[2].MarkerIndex
		|| Runners[1].MarkerIndex == Runners[2].MarkerIndex)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: two runners open the run on the same marker, "
				 "so whose marker is whose is not decidable"));
		return false;
	}

	// ---- the crumbling ground ----------------------------------------------
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrumbleGround")), Found);
	if (Found.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the floor is not staged as authored - expected "
				 "one patch of crumbling ground tagged CrumbleGround, found %d"),
			Found.Num()));
		return false;
	}
	Patch = Found[0];
	{
		TArray<UBoxComponent*> Boxes;
		Found[0]->GetComponents<UBoxComponent>(Boxes);
		for (UBoxComponent* const B : Boxes)
		{
			if (B != nullptr && (PatchBox == nullptr || B->GetName() == TEXT("PatchVolume")))
			{
				PatchBox = B;
			}
		}
	}
	if (!PatchBox.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the crumbling ground has no shape the fixture "
				 "can read, so it cannot tell where the patch is"));
		return false;
	}

	// ---- the finish disc ----------------------------------------------------
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("FinishDisc")), Found);
	if (Found.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the floor is not staged as authored - expected "
				 "one finish disc tagged FinishDisc, found %d"), Found.Num()));
		return false;
	}
	Disc = Found[0];
	{
		bool bOk = false;
		ReadInt(Found[0], TEXT("DemandedLives"), bOk);
		if (!bOk)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the finish disc does not expose DemandedLives "
					 "readably, so the fixture cannot tell what the goal is asking for"));
			return false;
		}
		DiscRadius = ReadFloat(Found[0], TEXT("DiscRadiusUu"), bOk);
		if (!bOk || DiscRadius <= 100.0f)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the finish disc does not expose a usable "
					 "DiscRadiusUu (read %.0f), so the fixture cannot tell what counts "
					 "as standing on it"), DiscRadius));
			return false;
		}
	}

	// ---- measurements, never assumptions ------------------------------------
	if (const UCapsuleComponent* const Capsule = Runners[0].Actor->GetCapsuleComponent())
	{
		CapsuleRadius = FMath::Max(double(Capsule->GetScaledCapsuleRadius()), 1.0);
	}
	if (const UCharacterMovementComponent* const Move =
			Runners[0].Actor->GetCharacterMovement())
	{
		WalkSpeed = FMath::Max(double(Move->GetMaxSpeed()), 100.0);
	}
	WalkZ = Runners[0].Actor->GetActorLocation().Z;
	return true;
}

bool ALifeRunTerminalFunctionalTest::ValidateGeometry()
{
	PatchXform = PatchBox->GetComponentTransform();
	PatchExtent = PatchBox->GetUnscaledBoxExtent();
	PatchStagedAt = Patch->GetActorLocation();
	DiscStagedAt = Disc->GetActorLocation();
	DiscStagedRadius = DiscRadius;

	// The drive routes head-on along world X, so the patch has to be square to the
	// floor and unscaled -- otherwise "300 cm clear of the near face" means nothing.
	const FVector Scale = PatchXform.GetScale3D();
	const FRotator Rot = PatchXform.Rotator();
	if (!FMath::IsNearlyEqual(Scale.X, 1.0, 0.01) || !FMath::IsNearlyEqual(Scale.Y, 1.0, 0.01)
		|| FMath::Abs(FRotator::NormalizeAxis(Rot.Yaw)) > 1.0
		|| FMath::Abs(Rot.Pitch) > 1.0 || FMath::Abs(Rot.Roll) > 1.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the crumbling ground is scaled %s and turned "
				 "%s; the fixture drives head-on across a patch that is square to the "
				 "floor and unscaled"), *Scale.ToCompactString(), *Rot.ToCompactString()));
		return false;
	}

	PatchCentreX = PatchXform.GetLocation().X;
	PatchNearX = PatchCentreX - PatchExtent.X;
	PatchFarX = PatchCentreX + PatchExtent.X;
	PatchHalfY = PatchExtent.Y;

	// A runner's capsule centre has to be able to be INSIDE the patch box vertically,
	// or nothing the drive does will ever be a crossing.
	const double LocalZ = WalkZ - PatchXform.GetLocation().Z;
	if (FMath::Abs(LocalZ) > PatchExtent.Z)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: a runner stands with its middle %.0f cm above "
				 "the crumbling ground's own middle and the patch reaches only %.0f cm; "
				 "walking onto it would never be noticed at all"), LocalZ, PatchExtent.Z));
		return false;
	}

	// Every lane has to be covered, or a runner could simply walk past the hazard on
	// its own line and the whole ledger would be unreachable.
	for (const FRunner& R : Runners)
	{
		const double LaneY = FMath::Abs(R.MarkerAt.Y - PatchXform.GetLocation().Y);
		if (LaneY + CapsuleRadius > PatchHalfY)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s runs on a lane %.0f cm off the crumbling "
					 "ground's centre and the patch is only %.0f cm across from there, "
					 "so that runner could walk straight past the hazard"),
				R.Label, LaneY, PatchHalfY));
			return false;
		}
	}

	// The markers must be far enough apart that "on your own marker" is a real
	// question -- four times the tolerance the prompt discloses.
	for (int32 i = 0; i < Markers.Num(); ++i)
	{
		for (int32 j = i + 1; j < Markers.Num(); ++j)
		{
			const double D = FVector::Dist2D(MarkerStagedAt[i], MarkerStagedAt[j]);
			if (D < kMarkerSpacingFloorUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: two markers are %.0f cm apart and "
						 "standing 'on' one reaches %.0f cm, so going to the wrong "
						 "marker would grade the same as going to the right one"),
					D, kOnMarkerUu));
				return false;
			}
		}
		const double ToPatch = PlanarDistToPatch(
			FVector(MarkerStagedAt[i].X, MarkerStagedAt[i].Y, WalkZ));
		if (ToPatch < kTriggerClearUu)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a marker is only %.0f cm from the "
					 "crumbling ground and the fixture needs %.0f cm, or a runner put "
					 "back on its marker would be claimed again at once"),
				ToPatch, kTriggerClearUu));
			return false;
		}
	}
	{
		const double PatchToDisc = PlanarDistToDisc(
			FVector(PatchFarX, PatchXform.GetLocation().Y, WalkZ));
		if (PatchToDisc < kTriggerClearUu)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the finish disc reaches to within %.0f cm "
					 "of the crumbling ground and the fixture needs %.0f cm, or the "
					 "two triggers would fire together"), PatchToDisc, kTriggerClearUu));
			return false;
		}
	}

	// ---- the off-lane crossing spot: DERIVED, never written down -------------
	// One of the loss-leg runner's crossings is taken at a spot whose nearest marker
	// is NOT its own -- which is what makes "send them back to the nearest marker" a
	// fair, fully disclosed discriminator rather than a gotcha.
	OffLaneY = 0.0;
	OffLaneMarginUu = -1.0;
	const FRunner& A = Runners[0];
	const double LaneLimit = PatchHalfY - CapsuleRadius - 100.0;
	for (double Y = -LaneLimit; Y <= LaneLimit; Y += 25.0)
	{
		const FVector P(PatchNearX, PatchXform.GetLocation().Y + Y, WalkZ);
		const double ToOwn = FVector::Dist2D(P, A.MarkerAt);
		double ToOther = TNumericLimits<double>::Max();
		int32 OtherIdx = INDEX_NONE;
		for (int32 m = 0; m < Markers.Num(); ++m)
		{
			if (m == A.MarkerIndex) { continue; }
			const double D = FVector::Dist2D(P, MarkerStagedAt[m]);
			if (D < ToOther) { ToOther = D; OtherIdx = m; }
		}
		const double Margin = ToOwn - ToOther;
		if (Margin > OffLaneMarginUu)
		{
			OffLaneMarginUu = Margin;
			OffLaneY = P.Y;
			OffLaneNearestMarker = OtherIdx;
		}
	}
	if (OffLaneMarginUu < kOwnershipMarginUu)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: nowhere on the crumbling ground is more than "
				 "%.0f cm nearer another runner's marker than the near runner's own "
				 "(best is %.0f cm), so 'go back to the nearest marker' would grade "
				 "exactly like 'go back to your own' and the ownership rule would "
				 "measure nothing"), kOwnershipMarginUu, OffLaneMarginUu));
		return false;
	}

	// ---- the bypass corridor -------------------------------------------------
	// The finish has to be reachable WITHOUT crossing the hazard, or the win leg
	// spends a life it does not have and can never be won at all.
	BypassY = PatchXform.GetLocation().Y - (PatchHalfY + kBypassMarginUu);
	return true;
}

bool ALifeRunTerminalFunctionalTest::BuildPhases()
{
	const double PatchMidY = PatchXform.GetLocation().Y;
	const FVector DiscSpotWin(DiscStagedAt.X, DiscStagedAt.Y - DiscRadius * 0.5, WalkZ);
	const FVector DiscSpotLost(DiscStagedAt.X, DiscStagedAt.Y + DiscRadius * 0.6, WalkZ);
	// Clear of the disc's own reach by a full approach margin, so stepping off and
	// back on is a REAL second arrival and not a boundary skim.
	const FVector DiscStepOff(DiscStagedAt.X - DiscRadius - kApproachClearUu,
		DiscSpotWin.Y, WalkZ);

	auto NearStage = [this](double Y) { return FVector(PatchNearX - kApproachClearUu, Y, WalkZ); };
	auto FarStage = [this](double Y) { return FVector(PatchFarX + kApproachClearUu, Y, WalkZ); };
	auto CrossTo = [this](double Y) { return FVector(PatchCentreX, Y, WalkZ); };

	auto AddWalk = [this](int32 Who, const TArray<FVector>& Pts, const TCHAR* What)
	{
		FPhase P;
		P.Kind = EPhaseKind::Walk;
		P.Runner = Who;
		P.Waypoints = Pts;
		P.Label = What;
		Phases.Add(P);
	};
	auto AddCross = [this](int32 Who, const FVector& Stage_, const FVector& Target,
						   const TCHAR* What)
	{
		FPhase P;
		P.Kind = EPhaseKind::Cross;
		P.Runner = Who;
		P.Waypoints = { Stage_, Target };
		P.Label = What;
		Phases.Add(P);
	};
	auto AddStand = [this](int32 Who, double Hold, bool bFromPhaseStart, const TCHAR* What)
	{
		FPhase P;
		P.Kind = EPhaseKind::Stand;
		P.Runner = Who;
		P.HoldSeconds = Hold;
		P.bAnchorIsPhaseStart = bFromPhaseStart;
		P.Label = What;
		Phases.Add(P);
	};
	auto AddRepaint = [this](int32 MarkerIdx, int32 To, const TCHAR* What)
	{
		FPhase P;
		P.Kind = EPhaseKind::Repaint;
		P.MarkerIndex = MarkerIdx;
		P.PaintTo = To;
		P.Label = What;
		Phases.Add(P);
	};
	auto AddDemand = [this](int32 To, const TCHAR* What)
	{
		FPhase P;
		P.Kind = EPhaseKind::Demand;
		P.PaintTo = To;
		P.Label = What;
		Phases.Add(P);
	};

	// Phase 0: nothing is driven while the level settles; no gate is armed.
	{
		FPhase P;
		P.Kind = EPhaseKind::Settle;
		P.HoldSeconds = kSettlePhaseS;
		P.Label = TEXT("the level settles");
		Phases.Add(P);
	}

	const double OwnLaneA = Runners[0].MarkerAt.Y;
	const double OwnLaneB = Runners[1].MarkerAt.Y;

	// ---- the loss leg: matched pairs of crossings, own lane / off lane -------
	for (int32 k = 1; k <= PredictedFinalCrossing; ++k)
	{
		const bool bOwnLane = (k % 2) == 1;
		const double Y = bOwnLane ? OwnLaneA : OffLaneY;
		const bool bFinal = (k == PredictedFinalCrossing);
		AddWalk(0, { NearStage(Y) }, bOwnLane
			? TEXT("the near runner lines up on its own lane")
			: TEXT("the near runner lines up on the off lane"));
		AddCross(0, NearStage(Y), CrossTo(Y), bOwnLane
			? TEXT("the near runner walks onto the crumbling ground on its own lane")
			: TEXT("the near runner walks onto the crumbling ground off its lane"));
		AddStand(0, bFinal ? kStandAfterTerminalS : kStandAfterCrossS, false,
			bFinal ? TEXT("the near runner is left where the ground claimed it")
				   : TEXT("the near runner is given its second to come back"));
		if (k == 1)
		{
			AddRepaint(Runners[0].MarkerIndex, Stage.RepaintA,
				TEXT("the near runner's board is re-painted UP"));
		}
	}

	// ---- the win leg --------------------------------------------------------
	AddWalk(1, { NearStage(OwnLaneB) }, TEXT("the middle runner lines up"));
	AddCross(1, NearStage(OwnLaneB), CrossTo(OwnLaneB),
		TEXT("the middle runner walks onto the crumbling ground"));
	AddStand(1, kStandAfterCrossS, false,
		TEXT("the middle runner is given its second to come back"));
	AddRepaint(Runners[1].MarkerIndex, Stage.RepaintB,
		TEXT("the middle runner's board is re-painted DOWN"));
	AddWalk(1, { NearStage(OwnLaneB) }, TEXT("the middle runner lines up again"));
	AddCross(1, NearStage(OwnLaneB), CrossTo(OwnLaneB),
		TEXT("the middle runner walks onto the crumbling ground a second time"));
	AddStand(1, kStandAfterCrossS, false,
		TEXT("the middle runner is given its second to come back"));
	// AROUND the hazard, never through it: a third crossing here would spend a life
	// the win leg does not have and the finish could never be reached at all.
	AddWalk(1, { FVector(PatchNearX - kApproachClearUu, BypassY, WalkZ),
				 FVector(PatchFarX + kApproachClearUu, BypassY, WalkZ),
				 DiscSpotWin },
		TEXT("the middle runner goes round the hazard to the finish"));
	// IT ARRIVES SHORT OF WHAT THE FINISH IS ASKING FOR, and must simply go on
	// running -- walking on is not the question. Then the goal's own number moves
	// UP (still short: moving a number never opens anything by itself), the arrival
	// is repeated so the trigger fires twice, and only then does the number come
	// DOWN below what this runner is holding -- which wins the run WITH NOBODY
	// MOVING. An answer that decides the finish on the step that carried a runner
	// on has no event to hang that win on and never wins at all.
	AddStand(1, kStandOnDiscS, true,
		TEXT("the middle runner stands on the finish short of what it asks"));
	AddDemand(Stage.DemandMid, TEXT("the finish's own number is re-painted UP"));
	AddStand(1, kStandOnDiscS, true,
		TEXT("the middle runner stands on the finish with its number moved up"));
	AddWalk(1, { DiscStepOff }, TEXT("the middle runner steps back off the finish"));
	AddWalk(1, { DiscSpotWin }, TEXT("the middle runner walks onto the finish again"));
	AddStand(1, kStandOnDiscS, true,
		TEXT("the middle runner stands on the finish short of what it asks a second "
			 "time"));
	AddDemand(Stage.DemandEnd, TEXT("the finish's own number is re-painted DOWN"));
	AddStand(1, kStandAfterConflictS, true,
		TEXT("the goal opens where the middle runner already stands"));

	// ---- the ended runs are driven at, on BOTH terminal kinds ----------------
	AddWalk(0, { NearStage(OffLaneY) },
		TEXT("the lost runner is walked back off the crumbling ground"));
	AddCross(0, NearStage(OffLaneY), CrossTo(OffLaneY),
		TEXT("the lost runner is walked onto the crumbling ground again"));
	AddStand(0, kStandAfterConflictS, false, TEXT("the lost runner is watched"));
	AddWalk(0, { FarStage(OffLaneY), DiscSpotLost },
		TEXT("the lost runner is walked onto the finish"));
	AddStand(0, kStandAfterConflictS, true, TEXT("the lost runner is watched"));

	AddWalk(1, { FarStage(PatchMidY) },
		TEXT("the won runner is walked back to the hazard"));
	AddCross(1, FarStage(PatchMidY), CrossTo(PatchMidY),
		TEXT("the won runner is walked onto the crumbling ground"));
	AddStand(1, kStandAfterConflictS, false, TEXT("the won runner is watched"));
	AddWalk(1, { FarStage(PatchMidY), DiscSpotWin },
		TEXT("the won runner is walked onto the finish a second time"));
	AddStand(1, kStandAfterConflictS, true, TEXT("the won runner is watched"));

	// ---- and the board is moved under both ended runs ------------------------
	AddRepaint(Runners[0].MarkerIndex, Stage.FinalA,
		TEXT("the lost runner's board is re-painted"));
	AddRepaint(Runners[1].MarkerIndex, Stage.FinalB,
		TEXT("the won runner's board is re-painted"));
	AddStand(INDEX_NONE, 2.4, true, TEXT("nothing is driven"));

	{
		FPhase P;
		P.Kind = EPhaseKind::Complete;
		P.Label = TEXT("the run-level gate");
		Phases.Add(P);
	}
	return true;
}

bool ALifeRunTerminalFunctionalTest::ValidateRoutes()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(LifeRunRoute), false);
	for (const FRunner& R : Runners)
	{
		Params.AddIgnoredActor(R.Actor.Get());
	}
	// A capsule a little smaller than the runner's, lifted clear of the floor: the
	// question is "is there an OBSTACLE here", never "is there ground here".
	const FCollisionShape Probe = FCollisionShape::MakeCapsule(
		float(CapsuleRadius * 0.9), 88.0f);

	// WHERE EACH RUNNER ACTUALLY IS WHEN A PHASE OPENS. Walked forward phase by
	// phase, because the routes are a SEQUENCE: validating every phase from the
	// runner's t=0 position instead would check journeys the drive never makes -- and
	// would condemn the correct level, since "walk from the finish disc back to the
	// hazard" reads as a walk straight across the patch from a runner's marker.
	TArray<FVector> Cursor;
	for (const FRunner& R : Runners)
	{
		FVector At = R.Actor.IsValid() ? R.Actor->GetActorLocation() : FVector::ZeroVector;
		At.Z = WalkZ;
		Cursor.Add(At);
	}

	for (int32 p = 0; p < Phases.Num(); ++p)
	{
		const FPhase& Ph = Phases[p];
		if (Ph.Waypoints.Num() == 0 || !Runners.IsValidIndex(Ph.Runner))
		{
			continue;
		}
		FVector From = Cursor[Ph.Runner];
		From.Z = WalkZ;
		// A phase may OPEN with the runner standing in the patch (it was just claimed
		// there, or it is the lost runner being walked out of it). Walking OUT is not a
		// crossing; walking back IN is. So the hazard rule below arms only once the
		// route has left the patch.
		bool bLeftPatch = !InPatchArmed(From);
		for (int32 w = 0; w < Ph.Waypoints.Num(); ++w)
		{
			const FVector To = Ph.Waypoints[w];
			const bool bCrossSegment =
				(Ph.Kind == EPhaseKind::Cross) && (w == Ph.Waypoints.Num() - 1);
			for (int32 s = 0; s <= 12; ++s)
			{
				const FVector At = FMath::Lerp(From, To, double(s) / 12.0);
				// There has to be floor under every step of the route.
				FHitResult Ground;
				if (!World->LineTraceSingleByChannel(Ground, At + FVector(0, 0, 200.0),
						At - FVector(0, 0, 400.0), ECC_Visibility, Params))
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the drive would walk %s over %s and "
							 "there is no floor there; the level is not staged as "
							 "authored"), *Ph.Label, *Describe(At)));
					return false;
				}
				// And nothing may block the walk.
				if (World->OverlapBlockingTestByChannel(At + FVector(0, 0, 10.0),
						FQuat::Identity, ECC_Pawn, Probe, Params))
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: something in the level blocks the "
							 "drive at %s during '%s'; nothing but the floor may stop a "
							 "runner walking"), *Describe(At), *Ph.Label));
					return false;
				}
				// NO ROUTE BUT A CROSSING ROUTE MAY TOUCH THE HAZARD. This is the check
				// that catches a drive which spends a life it never meant to -- the
				// exact defect the design's own drive table carried, where the win-leg
				// runner walked to the finish straight through the patch and would have
				// been LOST before it could win.
				if (!InPatchArmed(At))
				{
					bLeftPatch = true;
				}
				else if (!bCrossSegment && bLeftPatch)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the drive's route '%s' walks back "
							 "onto the crumbling ground at %s, which would spend a life "
							 "the staging never allowed for"), *Ph.Label, *Describe(At)));
					return false;
				}
			}
			From = To;
		}
		Cursor[Ph.Runner] = Ph.Waypoints.Last();
		Cursor[Ph.Runner].Z = WalkZ;
	}
	return true;
}

// ---------------------------------------------------------------------------
// PrepareTest
// ---------------------------------------------------------------------------

void ALifeRunTerminalFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}
	if (!ResolveStaging() || !ResolveLeg() || !ValidateStagingTable() || !ValidateGeometry())
	{
		return;
	}

	// THE LEVEL CANNOT BE PLAYED BY HAND is a HARNESS fault, never the agent's: the
	// input lane is substrate we ship, and a map that grades byte-identically while
	// being uncontrollable is how five of six ThirdPerson maps once shipped.
	if (const FString Unwired = DescribeBrokenPlayerInput(); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. The "
				 "graded drive would still pass, so fix the substrate, not the task."),
			*Unwired));
		return;
	}

	// ---- paint this leg's board --------------------------------------------
	const int32 Wanted[3] = { Stage.StartA, Stage.StartB, Stage.StartC };
	for (int32 i = 0; i < Runners.Num(); ++i)
	{
		const int32 M = Runners[i].MarkerIndex;
		if (!WriteInt(Markers[M].Get(), TEXT("PaintedLives"), Wanted[i]))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s's marker would not take a painted "
					 "number, so this leg's board cannot be staged"), Runners[i].Label));
			return;
		}
		MarkerStagedPaint[M] = Wanted[i];
	}

	// ---- and what the finish asks for, for this leg -------------------------
	if (!WriteInt(Disc.Get(), TEXT("DemandedLives"), Stage.DemandStart))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the finish would not take a painted number, so "
				 "this leg's goal cannot be staged"));
		return;
	}
	DiscStagedDemand = Stage.DemandStart;

	if (!BuildPhases() || !ValidateRoutes())
	{
		return;
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-liferun] leg %d Hz: board %d/%d/%d, up to %d, down to %d, last %d/%d; "
			 "the finish asks %d -> %d -> %d; "
			 "patch x %.0f..%.0f y +/-%.0f; off lane y=%.0f (%.0f cm nearer marker %d "
			 "than its own); disc at %s r=%.0f; walk %.0f cm/s; %d phases"),
		Stage.Rate, Stage.StartA, Stage.StartB, Stage.StartC, Stage.RepaintA,
		Stage.RepaintB, Stage.FinalA, Stage.FinalB, Stage.DemandStart, Stage.DemandMid,
		Stage.DemandEnd, PatchNearX, PatchFarX, PatchHalfY,
		OffLaneY, OffLaneMarginUu, OffLaneNearestMarker, *Describe(DiscStagedAt),
		DiscRadius, WalkSpeed, Phases.Num());

	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	// THE SENTINEL, far past the ~200 s the drive models: the base class ends the test
	// the moment the LAST scheduled checkpoint is sampled, so a run-level gate with
	// nothing after it would be the base fixture's auto-success trap.
	Schedule.Add(kSentinelAtS);
	TimeLimitMargin = 8.0f;
	SetCheckpointSchedule(Schedule);

	StagingUntil = 0.0;
	bPrepared = true;
}

// ---------------------------------------------------------------------------
// Suppression. Each of these is a WIDENING of the disclosed contract.
// ---------------------------------------------------------------------------

bool ALifeRunTerminalFunctionalTest::SuppressedFor(const FRunner& R, double Now) const
{
	if (Now < StagingUntil)
	{
		return true;   // the fixture itself is moving the level's numbers
	}
	if (Now - R.LastModelChangeAt < kSuppressAfterChangeS)
	{
		return true;   // 1.5x the half second the prompt promises
	}
	// A STILL-RUNNING runner near a trigger's edge is not judged: this is the only
	// band in which two honest entry models legitimately disagree. Once a run has
	// ended, its readouts are frozen and no entry model can move them, so the band is
	// dropped -- otherwise the lost runner, which comes to rest just inside the patch,
	// would never be judged again at all.
	if (R.State == ERunState::Running && R.Actor.IsValid())
	{
		const FVector At = R.Actor->GetActorLocation();
		const double ToPatch = PlanarDistToPatch(At);
		const double ToDisc = PlanarDistToDisc(At);
		// THE AMBIGUITY IS ONE-SIDED, and banding both sides of it left a real gate
		// unable to fire. Both distances go NEGATIVE the moment the capsule CENTRE is
		// inside the trigger, and that is the LATEST instant any honest answer can
		// have noticed -- the fixture armed one capsule radius earlier, and the 0.75 s
		// model-change suppression above already covers that lag plus a frame of tick
		// order on top of it. So only the APPROACH and the shell between the two entry
		// models need the band. Banding the inside as well made a runner LEFT LYING IN
		// THE PATCH permanently unjudgeable (it comes to rest ~36-53 cm inside the
		// near face, well within 160) -- and a runner left lying in the patch with
		// lives still on its own board is exactly the submission
		// WhileLivesRemainYouComeBackToYourMarker is written to name, so that gate
		// could not fire against its own target. It never showed up on a correct
		// answer, which puts the runner back on its marker inside the second the level
		// allows and is far outside the band by the time the gate gauges at +1.35 s --
		// i.e. the old band could only ever hide a WRONG answer, never fail a right
		// one.
		if ((ToPatch >= 0.0 && ToPatch < kBoundaryBandUu)
			|| (ToDisc >= 0.0 && ToDisc < kBoundaryBandUu))
		{
			return true;
		}
	}
	return false;
}

// ---------------------------------------------------------------------------
// The gates.
// ---------------------------------------------------------------------------

FString ALifeRunTerminalFunctionalTest::DescribeRunner(const FRunner& R) const
{
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	return FString::Printf(
		TEXT("%s: its marker reads %d, it has been claimed %d time(s), so %d lamp(s) "
			 "should be lit and it should read %s; %d lamp(s) are lit and it reads "
			 "'%s'"),
		R.Label, PaintedOn(R.MarkerIndex), R.Deaths, ExpectedLitFor(R),
		ExpectedWordFor(R), Lit, *WordOf(R));
}

bool ALifeRunTerminalFunctionalTest::GateNotRewired(double Now)
{
	(void)Now;

	// Nobody is ever replaced, and every runner still carries what the level built.
	TArray<AActor*> Tagged;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("LifeRunner")), Tagged);
	if (Tagged.Num() != 3)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRunIsNotYoursToRewire: the level opened with three runners and "
				 "there are now %d. Nobody is ever replaced -- destroying a runner and "
				 "spawning a fresh one loses that run's whole history with it"),
			Tagged.Num()));
		return false;
	}
	for (const FRunner& R : Runners)
	{
		if (!R.Actor.IsValid() || R.Identity.Get() != R.Actor.Get())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: %s is not the runner that was standing "
					 "there when the run opened. Nobody is ever replaced"), R.Label));
			return false;
		}
		int32 Total = 0;
		LitCountOf(R, Total);
		if (Total != kLampCount || WordComponentsOf(R) < 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: %s now carries %d lamp(s) and %d "
					 "floating word(s); the level gives every runner six lamps and one "
					 "word, and they are the only place its state is ever shown"),
				R.Label, Total, WordComponentsOf(R)));
			return false;
		}
	}

	// The board is the level's to write, never the submission's.
	for (int32 m = 0; m < Markers.Num(); ++m)
	{
		const AActor* const M = Markers[m].Get();
		if (M == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheRunIsNotYoursToRewire: a marker disc stopped existing mid-run"));
			return false;
		}
		const int32 Painted = PaintedOn(m);
		if (Painted != MarkerStagedPaint[m])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: a marker's painted number was changed. "
					 "The level painted %d on it and it now reads %d. Re-painting a "
					 "marker is not yours to do"), MarkerStagedPaint[m], Painted));
			return false;
		}
		if (!M->GetActorLocation().Equals(MarkerStagedAt[m], kPlacementDriftUu))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: a marker disc was moved. The level put "
					 "it at %s and it is now at %s. The floor is not yours to "
					 "rearrange"), *Describe(MarkerStagedAt[m]),
				*Describe(M->GetActorLocation())));
			return false;
		}
	}

	if (!Patch.IsValid() || !Patch->GetActorLocation().Equals(PatchStagedAt, kPlacementDriftUu))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRunIsNotYoursToRewire: the crumbling ground was moved. The level "
				 "put it at %s and it is now at %s"), *Describe(PatchStagedAt),
			*Describe(Patch.IsValid() ? Patch->GetActorLocation() : FVector::ZeroVector)));
		return false;
	}
	{
		bool bOk = false;
		const float NowRadius = ReadFloat(Disc.Get(), TEXT("DiscRadiusUu"), bOk);
		if (!Disc.IsValid() || !Disc->GetActorLocation().Equals(DiscStagedAt, kPlacementDriftUu)
			|| !bOk || !FMath::IsNearlyEqual(NowRadius, DiscStagedRadius, 0.5f))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: the finish disc was moved or resized. "
					 "The level put it at %s reaching %.0f cm; it is now at %s "
					 "reaching %.0f cm"), *Describe(DiscStagedAt), DiscStagedRadius,
				*Describe(Disc.IsValid() ? Disc->GetActorLocation() : FVector::ZeroVector),
				NowRadius));
			return false;
		}
	}
	{
		// WHAT THE GOAL ASKS FOR IS THE LEVEL'S TO WRITE TOO, exactly like a board.
		bool bOk = false;
		const int32 NowDemand = ReadInt(Disc.Get(), TEXT("DemandedLives"), bOk);
		if (!bOk || NowDemand != DiscStagedDemand)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRunIsNotYoursToRewire: the finish's painted number was changed. "
					 "The level painted %d on it and it now reads %d. Re-painting what "
					 "the goal asks for is not yours to do"),
				DiscStagedDemand, NowDemand));
			return false;
		}
	}
	return true;
}

bool ALifeRunTerminalFunctionalTest::GateLastLife(FRunner& R, double Now)
{
	const double Since = Now - R.TerminalAt;

	// NOT SENT HOME. Measured from where the ground claimed it -- the fixture's own
	// geometry, so a submission that whisks the runner away cannot move the yardstick.
	const FVector At = R.Actor->GetActorLocation();
	const double Away = FVector::Dist2D(At, R.ClaimSpot);
	if (Away > kLeftWhereClaimedUu)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheLastLifeEndsTheRun: that crossing was %s's last life and it was "
				 "sent home anyway. Its marker read %d, the ground had claimed it %d "
				 "time(s), so nothing was left. The ground claimed it at %s and %.2f s "
				 "later it is at %s -- %.0f cm away, and the level allows %.0f. When a "
				 "runner runs out, nobody comes back for it"),
			R.Label, PaintedOn(R.MarkerIndex), R.Deaths, *Describe(R.ClaimSpot), Since,
			*Describe(At), Away, kLeftWhereClaimedUu));
		return false;
	}

	// AND THE ROW AND THE WORD FOLLOW, within the second the level allows.
	if (Since >= kComeBackGaugeAtS)
	{
		int32 Total = 0;
		const int32 Lit = LitCountOf(R, Total);
		const FString Word = WordOf(R);
		if (Lit != 0 || !Word.Equals(kWordLost))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheLastLifeEndsTheRun: that crossing was %s's last life and its "
					 "run did not end. Its marker reads %d and the ground has claimed "
					 "it %d time(s), so nothing is left; %.2f s later every lamp should "
					 "be dark and it should read %s, and %d lamp(s) are lit while it "
					 "reads '%s'. THE LIFE IS SPENT ON THE DEATH, and whether that was "
					 "the last one is asked at that moment -- not on the way back"),
				R.Label, PaintedOn(R.MarkerIndex), R.Deaths, Since, kWordLost, Lit,
				*Word));
			return false;
		}
	}
	return true;
}

bool ALifeRunTerminalFunctionalTest::GateComeBack(FRunner& R, double Now)
{
	if (Now - R.LastCrossingAt < kComeBackGaugeAtS)
	{
		return true;
	}
	const FVector At = R.Actor->GetActorLocation();
	const double ToOwn = FVector::Dist2D(At, R.MarkerAt);
	if (ToOwn <= kOnMarkerUu)
	{
		return true;
	}
	// Which marker DID it go to? That is the whole diagnosis.
	int32 NearestIdx = INDEX_NONE;
	double Nearest = TNumericLimits<double>::Max();
	for (int32 m = 0; m < Markers.Num(); ++m)
	{
		const double D = FVector::Dist2D(At, MarkerStagedAt[m]);
		if (D < Nearest) { Nearest = D; NearestIdx = m; }
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("WhileLivesRemainYouComeBackToYourMarker: %s still had %d live(s) after "
			 "that crossing (its marker reads %d, claimed %d time(s)), so %.2f s later "
			 "it should be standing within %.0f cm of ITS OWN marker at %s. It is at "
			 "%s -- %.0f cm from its own, and %.0f cm from the marker at %s, which is "
			 "not its. The disc a runner stands on when the run opens is its own for "
			 "the rest of the run, wherever it is later claimed"),
		R.Label, RemainingFor(R), PaintedOn(R.MarkerIndex), R.Deaths,
		Now - R.LastCrossingAt, kOnMarkerUu, *Describe(R.MarkerAt), *Describe(At),
		ToOwn, Nearest,
		*Describe(Markers.IsValidIndex(NearestIdx) ? MarkerStagedAt[NearestIdx]
												   : FVector::ZeroVector)));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateSpendOne(FRunner& R, double Now)
{
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	const int32 Want = ExpectedLitFor(R);
	if (Lit == Want)
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("EachDeathSpendsExactlyOneLife: crossing %d claimed %s and the row did "
			 "not come down by exactly one. Its marker reads %d and it had %d lamp(s) "
			 "lit on the step before, so %.2f s after walking on it should show %d; it "
			 "shows %d. Walking on costs one life ONCE, however long the runner then "
			 "stands there, and stepping off and walking on again costs another"),
		R.Crossings, R.Label, PaintedOn(R.MarkerIndex), R.LitBeforeCrossing,
		Now - R.LastCrossingAt, Want, Lit));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateBoardRead(FRunner& R, double Now)
{
	if (Now - R.RepaintAt < kSettleGaugeFromS)
	{
		return true;
	}
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	const int32 Want = ExpectedLitFor(R);
	const FString Word = WordOf(R);
	if (Lit == Want && Word.Equals(kWordRunning))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheBoardIsReadWhenItMatters: %s's marker was re-painted from %d to %d "
			 "while its run was still going, and %.2f s later the row has not "
			 "followed. It has been claimed %d time(s), so %d lamp(s) should be lit "
			 "and it should still read %s; %d lamp(s) are lit and it reads '%s'. "
			 "Whatever a marker says at the moment you need its number IS the number "
			 "-- and re-painting a marker never claims anybody, it only changes "
			 "which death is the last one"),
		R.Label, R.RepaintFrom, R.RepaintTo, Now - R.RepaintAt, R.Deaths, Want,
		kWordRunning, Lit, *Word));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateGoalShort(FRunner& R, double Now)
{
	(void)Now;
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	const FString Word = WordOf(R);
	const int32 Want = ExpectedLitFor(R);
	if (Lit == Want && Word.Equals(kWordRunning))
	{
		// Counted, because a leg in which the runner was never short of the goal
		// proves nothing about what the goal asks for -- FinalGrade checks the tally.
		++R.ShortOnDiscJudged;
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheGoalOnlyOpensToWhatItAsksFor: %s is standing on the finish holding "
			 "%d life/lives -- its marker reads %d and the ground has claimed it %d "
			 "time(s) -- and the finish is asking for %d. It is not through: %d "
			 "lamp(s) should be lit and it should still read %s, and %d lamp(s) are "
			 "lit while it reads '%s'. What the goal asks for is measured against "
			 "what a runner HAS LEFT, never against what its board says; and walking "
			 "on is not the question -- whether it is holding enough is, for as long "
			 "as it stands there"),
		R.Label, RemainingFor(R), PaintedOn(R.MarkerIndex), R.Deaths, DemandNow(),
		Want, kWordRunning, Lit, *Word));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateGoalWins(FRunner& R, double Now)
{
	if (Now - R.FirstWinAt < kSettleGaugeFromS)
	{
		return true;
	}
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	const FString Word = WordOf(R);
	if (Lit == R.FrozenLit && Word.Equals(kWordWon))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ReachingTheGoalWinsAndSpendsNothing: %s was standing on the finish with "
			 "its run still going and %d lamp(s) lit (its marker reads %d, claimed %d "
			 "time(s)) when the finish came down to asking for %d -- which it was "
			 "already holding, so that is the moment the goal opened to it. Nothing "
			 "had to be walked onto again: the question is asked for as long as a "
			 "runner stands there, and both numbers move with nothing to announce "
			 "them. %.2f s later it should read %s with those same %d lamp(s) still "
			 "lit -- winning spends nothing and lights nothing. It reads '%s' with "
			 "%d lit"),
		R.Label, R.LitBeforeWin, PaintedOn(R.MarkerIndex), R.Deaths, DemandNow(),
		Now - R.FirstWinAt, kWordWon, R.FrozenLit, *Word, Lit));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateEndedNeverChanges(FRunner& R, double Now)
{
	(void)Now;
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	const FString Word = WordOf(R);
	const int32 Want = ExpectedLitFor(R);
	if (Lit == Want && Word.Equals(ExpectedWordFor(R)))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ARunThatEndedNeverChangesAgain: %s's run ended %s and has been driven at "
			 "%d time(s) since -- walked back onto the crumbling ground, walked onto "
			 "the finish disc, and had its marker re-painted (it now reads %d). Its "
			 "row froze at %d lamp(s) reading %s and must never move again; it shows "
			 "%d lamp(s) and reads '%s'. An ended run's ground costs nothing, its "
			 "finish does nothing, and its board changes nothing"),
		R.Label, R.bTerminalWasLoss ? TEXT("in a loss") : TEXT("in a win"),
		R.ConflictEvents, PaintedOn(R.MarkerIndex), Want, ExpectedWordFor(R), Lit,
		*Word));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateRunReads(FRunner& R, double Now)
{
	(void)Now;
	int32 Total = 0;
	const int32 Lit = LitCountOf(R, Total);
	const FString Word = WordOf(R);
	const int32 Want = ExpectedLitFor(R);
	if (Lit == Want && Word.Equals(ExpectedWordFor(R)))
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheRunReadsWhatItIs: a runner is not showing what its run is. %s. "
			 "Remaining lives is the number CURRENTLY painted on that runner's own "
			 "marker minus the number of times the crumbling ground has claimed it, "
			 "never below zero, and the six lamps are the only place it is ever shown"),
		*DescribeRunner(R)));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateNoTeleport(FRunner& R, double Now, double Dt)
{
	if (!R.bHaveWasAt || R.Crossings == 0 || Now < StagingUntil)
	{
		return true;
	}
	// Not armed until the runner has had the whole second the level allows to come
	// back, so a legitimate return is never read as a jump.
	if (R.State == ERunState::Running && Now - R.LastCrossingAt < kComeBackGaugeAtS)
	{
		return true;
	}
	const FVector At = R.Actor->GetActorLocation();
	const double Step = FVector::Dist2D(At, R.WasAt);
	const double Allowed = kWalkStepSlack * WalkSpeed * FMath::Max(Dt, 0.001)
		+ kWalkStepPadUu;
	if (Step <= Allowed)
	{
		return true;
	}
	if (R.State == ERunState::Lost)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheLastLifeEndsTheRun: %s ran out %.2f s ago and something moved it "
				 "%.0f cm in one frame, from %s to %s (walking covers at most %.0f cm "
				 "in that time). It is left where the ground claimed it and nothing of "
				 "yours may ever move it from there again"),
			R.Label, Now - R.TerminalAt, Step, *Describe(R.WasAt), *Describe(At),
			Allowed));
		return false;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("WhileLivesRemainYouComeBackToYourMarker: %s was put back on its marker "
			 "and then pulled again -- it moved %.0f cm in one frame, from %s to %s, "
			 "and walking covers at most %.0f cm in that time. Once a runner is back "
			 "on its own marker it is free to walk away and nothing may pull it back"),
		R.Label, Step, *Describe(R.WasAt), *Describe(At), Allowed));
	return false;
}

bool ALifeRunTerminalFunctionalTest::GateBystander(double Now)
{
	(void)Now;
	FRunner& C = Runners[2];
	if (!C.Actor.IsValid())
	{
		return true;
	}
	int32 Total = 0;
	const int32 Lit = LitCountOf(C, Total);
	const FString Word = WordOf(C);
	const int32 Painted = PaintedOn(C.MarkerIndex);
	const double Drift = FVector::Dist2D(C.Actor->GetActorLocation(), C.MarkerAt);
	if (Lit == Painted && Word.Equals(kWordRunning) && Drift <= kBystanderDriftUu)
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheBystanderIsUntouched: %s has never been driven anywhere, has never "
			 "been claimed by anything, and its marker has never been re-painted. Its "
			 "marker reads %d, so all %d of its lamps should be lit, it should read "
			 "%s, and it should be within %.0f cm of its own marker at %s. It shows %d "
			 "lamp(s), reads '%s', and is %.0f cm away. A runner's lives, its lamps "
			 "and its word belong to that runner alone -- one runner running out or "
			 "finishing must never reach another"),
		C.Label, Painted, Painted, kWordRunning, kBystanderDriftUu,
		*Describe(C.MarkerAt), Lit, *Word, Drift));
	return false;
}

bool ALifeRunTerminalFunctionalTest::ReCheckDisplays(double Now)
{
	// UNCONDITIONAL, before any harness exit: a submission that parks a runner, moves
	// a marker or pulls a runner back is exactly what makes a phase overrun, so a
	// rewired level must be a FAIL and not an uncredited non-graded exit.
	if (!GateNotRewired(Now))
	{
		return false;
	}
	for (FRunner& R : Runners)
	{
		if (!R.Actor.IsValid())
		{
			continue;
		}
		const bool bOk = (R.State == ERunState::Running)
			? GateRunReads(R, Now) : GateEndedNeverChanges(R, Now);
		if (!bOk)
		{
			return false;
		}
	}
	return GateBystander(Now);
}

bool ALifeRunTerminalFunctionalTest::BlamedAPinnedRunner(const FPhase& P, double Now)
{
	// Only a WALKING phase can be stalled by a held body; a Stand or a Repaint that
	// overruns is ours. And only a body that went NOWHERE counts: a runner that
	// moved and simply did not arrive is a route we got wrong.
	if ((P.Kind != EPhaseKind::Walk && P.Kind != EPhaseKind::Cross)
		|| !Runners.IsValidIndex(P.Runner) || !Runners[P.Runner].Actor.IsValid())
	{
		return false;
	}
	FRunner& R = Runners[P.Runner];
	const double Moved = FVector::Dist2D(R.Actor->GetActorLocation(), PhaseStartLocation);
	if (Moved > kPinnedUu)
	{
		return false;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ARunnerIsAlwaysFreeToWalk: %s has been walked at for %.0f s during "
			 "'%s' and has moved %.0f cm. It stands on floor, nothing in the level "
			 "blocks it, and its own movement was driven every one of those frames, "
			 "so something of the submission's is holding it where it is. Its run "
			 "reads %s. Putting a runner back on its own marker after a death is the "
			 "ONE time anything of yours moves a runner; apart from that a runner is "
			 "a body like any other, and a run that has ended does not nail its body "
			 "down -- it is simply never moved BY YOU again"),
		R.Label, Now - PhaseStartedAt, *P.Label, Moved, ExpectedWordFor(R)));
	return true;
}

// ---------------------------------------------------------------------------
// The drive.
// ---------------------------------------------------------------------------

void ALifeRunTerminalFunctionalTest::BeginPhase(int32 NewPhase, double Now)
{
	PhaseIndex = NewPhase;
	PhaseStartedAt = Now;
	WaypointIndex = 0;
	bRepaintPending = false;
	if (!Phases.IsValidIndex(PhaseIndex))
	{
		return;
	}
	const FPhase& P = Phases[PhaseIndex];
	CrossingsAtPhaseStart = Runners.IsValidIndex(P.Runner)
		? Runners[P.Runner].Crossings : 0;
	// Where the phase's subject stood when it opened. A walking phase that overruns
	// having moved this body nowhere at all is not a staging fault -- it is a
	// submission holding a runner in place, and it is named as one.
	PhaseStartLocation = (Runners.IsValidIndex(P.Runner)
		&& Runners[P.Runner].Actor.IsValid())
		? Runners[P.Runner].Actor->GetActorLocation() : FVector::ZeroVector;

	switch (P.Kind)
	{
	case EPhaseKind::Settle:
		PhaseDeadline = Now + P.HoldSeconds + 10.0;
		break;
	case EPhaseKind::Stand:
		PhaseDeadline = Now + P.HoldSeconds + 15.0;
		break;
	case EPhaseKind::Repaint:
	case EPhaseKind::Demand:
		// A number is moved half a second AFTER the phase opens and nothing is judged
		// for half a second either side of the write, so a runner is never graded on a
		// frame in which the fixture itself moved a number.
		bRepaintPending = true;
		StagingUntil = Now + kRepaintQuietS;
		PhaseDeadline = Now + kRepaintQuietS + kRepaintHoldS + 10.0;
		break;
	case EPhaseKind::Complete:
		PhaseDeadline = Now + 10.0;
		break;
	default:
	{
		// A WALKING deadline derived from the MEASURED route and the MEASURED walk
		// speed, never from a written number of seconds: 2.5x the ideal plus twelve,
		// which covers the acceleration ramp and a settle at every waypoint.
		double Length = 0.0;
		FVector From = Runners.IsValidIndex(P.Runner) && Runners[P.Runner].Actor.IsValid()
			? Runners[P.Runner].Actor->GetActorLocation() : FVector::ZeroVector;
		for (const FVector& W : P.Waypoints)
		{
			Length += FVector::Dist2D(From, W);
			From = W;
		}
		PhaseDeadline = Now + Length / WalkSpeed * 2.5 + 12.0;
		break;
	}
	}
}

void ALifeRunTerminalFunctionalTest::DrivePhase(double Now)
{
	(void)Now;
	if (!Phases.IsValidIndex(PhaseIndex))
	{
		return;
	}
	const FPhase& P = Phases[PhaseIndex];
	if ((P.Kind != EPhaseKind::Walk && P.Kind != EPhaseKind::Cross)
		|| !Runners.IsValidIndex(P.Runner) || !Runners[P.Runner].Actor.IsValid()
		|| !P.Waypoints.IsValidIndex(WaypointIndex))
	{
		return;
	}
	ACharacter* const C = Runners[P.Runner].Actor.Get();
	const FVector Here = C->GetActorLocation();
	const FVector Target = P.Waypoints[WaypointIndex];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointUu)
	{
		++WaypointIndex;
		return;
	}
	C->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
}

void ALifeRunTerminalFunctionalTest::AdvancePhases(double Now)
{
	if (!Phases.IsValidIndex(PhaseIndex))
	{
		return;
	}
	const FPhase& P = Phases[PhaseIndex];
	const double Elapsed = Now - PhaseStartedAt;
	bool bDone = false;

	switch (P.Kind)
	{
	case EPhaseKind::Settle:
		bDone = Elapsed >= P.HoldSeconds;
		break;

	case EPhaseKind::Walk:
		bDone = WaypointIndex >= P.Waypoints.Num();
		break;

	case EPhaseKind::Cross:
	{
		const FRunner& R = Runners[P.Runner];
		const bool bCrossed = R.Crossings > CrossingsAtPhaseStart;
		if (bCrossed && R.Actor.IsValid())
		{
			const FVector At = R.Actor->GetActorLocation();
			// RELEASE AT THE PLAIN BOX, NOT AT THE MODEL'S EDGE. The character coasts
			// only ~28 cm once input stops -- less than one capsule radius -- so a
			// drive that let go at the grown box would leave a point-in-box answer
			// standing outside the patch, never claimed at all.
			bDone = InPatchPlain(At)
				|| PlanarDistToPatch(At) > kMovedAwayUu
				|| (Now - R.LastCrossingAt) > kCrossCarryTimeoutS;
		}
		break;
	}

	case EPhaseKind::Stand:
	{
		const double Anchor = (P.bAnchorIsPhaseStart || !Runners.IsValidIndex(P.Runner))
			? PhaseStartedAt : Runners[P.Runner].LastCrossingAt;
		bDone = Now - FMath::Max(Anchor, PhaseStartedAt - 30.0) >= P.HoldSeconds
			&& Elapsed >= 0.25;
		break;
	}

	case EPhaseKind::Repaint:
		if (bRepaintPending && Elapsed >= kRepaintQuietS)
		{
			AActor* const M = Markers.IsValidIndex(P.MarkerIndex)
				? Markers[P.MarkerIndex].Get() : nullptr;
			// WRITTEN BY REFLECTION, never through a setter: a submission that
			// overrode the marker's refresh could otherwise intercept the staging and
			// then satisfy the anti-tamper read-back with its own number.
			if (M == nullptr || !WriteInt(M, TEXT("PaintedLives"), P.PaintTo))
			{
				ReCheckDisplays(Now);
				if (IsRunning())
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: a marker would not take a new "
							 "painted number during '%s', so half of this task is "
							 "unreachable"), *P.Label));
				}
				return;
			}
			for (FRunner& R : Runners)
			{
				if (R.MarkerIndex == P.MarkerIndex)
				{
					R.RepaintFrom = MarkerStagedPaint[P.MarkerIndex];
					R.RepaintTo = P.PaintTo;
					R.RepaintAt = Now;
					if (R.State != ERunState::Running)
					{
						// MOVING AN ENDED RUN'S BOARD IS ONE OF THE THREE CONFLICTING
						// EVENTS ARunThatEndedNeverChangesAgain rides on -- the other
						// two are the ground and the finish, which StepModel counts.
						// Without this the run ends with two apiece and the final
						// tally reads the drive as short, on a correct submission.
						++R.ConflictEvents;
					}
				}
			}
			UE_LOG(LogTemp, Display, TEXT("[t3-liferun] t=%.2f %s: %d -> %d"),
				Now, *P.Label, MarkerStagedPaint[P.MarkerIndex], P.PaintTo);
			MarkerStagedPaint[P.MarkerIndex] = P.PaintTo;
			bRepaintPending = false;
			StagingUntil = Now + kRepaintQuietS;
		}
		bDone = !bRepaintPending && Elapsed >= kRepaintQuietS + kRepaintHoldS;
		break;

	case EPhaseKind::Demand:
		if (bRepaintPending && Elapsed >= kRepaintQuietS)
		{
			// THE GOAL'S OWN NUMBER, written the same way and for the same reason: a
			// submission that overrode the disc's refresh could otherwise intercept the
			// staging and then satisfy the anti-tamper read-back with its own number.
			AActor* const D = Disc.Get();
			if (D == nullptr || !WriteInt(D, TEXT("DemandedLives"), P.PaintTo))
			{
				ReCheckDisplays(Now);
				if (IsRunning())
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the finish would not take a new painted "
							 "number during '%s', so the win leg is unreachable"), *P.Label));
				}
				return;
			}
			UE_LOG(LogTemp, Display, TEXT("[t3-liferun] t=%.2f %s: %d -> %d"),
				Now, *P.Label, DiscStagedDemand, P.PaintTo);
			DiscStagedDemand = P.PaintTo;
			++DemandWrites;
			bRepaintPending = false;
			StagingUntil = Now + kRepaintQuietS;
		}
		bDone = !bRepaintPending && Elapsed >= kRepaintQuietS + kRepaintHoldS;
		break;

	case EPhaseKind::Complete:
		bDriveComplete = true;
		return;

	default:
		bDone = true;
		break;
	}

	if (!bDone)
	{
		if (Now > PhaseDeadline)
		{
			// A PHASE THAT OVERRAN. Before this is written off as a staging fault,
			// every display gate is re-checked unconditionally.
			if (!ReCheckDisplays(Now))
			{
				return;
			}
			// ...and then the one NON-display way a submission stalls the drive: it is
			// holding the very body the drive has been pushing. That is the submission's,
			// not ours, and a non-graded exit would launder it.
			if (BlamedAPinnedRunner(P, Now))
			{
				return;
			}
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: phase %d of the drive ('%s') ran past its "
					 "derived deadline of %.0f s with every display gate green. The "
					 "near runner has been claimed %d time(s) and the middle one %d; "
					 "the level is staged so the drive cannot finish, which is ours "
					 "and not the submission's"),
				PhaseIndex, *P.Label, PhaseDeadline - PhaseStartedAt,
				Runners[0].Deaths, Runners[1].Deaths));
		}
		return;
	}

	if (PhaseIndex + 1 < Phases.Num())
	{
		BeginPhase(PhaseIndex + 1, Now);
	}
	else
	{
		bDriveComplete = true;
	}
}

// ---------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------

void ALifeRunTerminalFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);   // base first: checkpoint clock + timeout machinery

	if (!IsRunning() || !bPrepared || Runners.Num() != 3)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;
	const double Dt = FMath::Max(double(DeltaSeconds), 0.0001);

	if (PhaseIndex < 0)
	{
		BeginPhase(0, Now);
	}

	StepModel(Now);

	if (!GateNotRewired(Now))
	{
		return;
	}

	// Nothing is judged during the opening settle: the level is still arriving.
	const bool bArmed = Phases.IsValidIndex(PhaseIndex)
		&& Phases[PhaseIndex].Kind != EPhaseKind::Settle;

	if (bArmed)
	{
		bool bAnyJudged = false;
		for (FRunner& R : Runners)
		{
			if (!R.Actor.IsValid() || SuppressedFor(R, Now))
			{
				// The stay-put watch is a separate channel and runs even here: it is
				// about the submission MOVING a runner, which no entry-model
				// disagreement can excuse.
				if (R.Actor.IsValid() && !GateNoTeleport(R, Now, Dt))
				{
					return;
				}
				continue;
			}
			bAnyJudged = true;

			// PRECEDENCE. At most one of these is armed for this runner this frame.
			const bool bLastLifeWindow = R.State == ERunState::Lost && R.bTerminalWasLoss
				&& R.TerminalAt >= 0.0 && (Now - R.TerminalAt) <= kLastLifeWindowS;
			const bool bCrossWindow = R.State == ERunState::Running
				&& R.LastCrossingAt >= 0.0 && (Now - R.LastCrossingAt) <= kCrossWindowS;
			const bool bRepaintWindow = R.State == ERunState::Running
				&& R.RepaintAt >= 0.0 && (Now - R.RepaintAt) <= kRepaintWindowS;
			const bool bWinWindow = R.State == ERunState::Won && R.FirstWinAt >= 0.0
				&& (Now - R.FirstWinAt) <= kWinWindowS;
			// A still-running runner STANDING ON the finish is holding less than the
			// disc asks for -- otherwise the model would already have won it this very
			// frame, in StepModel, which runs first.
			const bool bShortOnDisc = R.State == ERunState::Running
				&& OnDiscArmed(R.Actor->GetActorLocation());

			bool bOk = true;
			if (bLastLifeWindow)
			{
				bOk = GateLastLife(R, Now);
			}
			else if (bCrossWindow)
			{
				// Two DIFFERENT channels on the same window -- position and lamps --
				// and both run.
				bOk = GateComeBack(R, Now) && GateSpendOne(R, Now);
			}
			else if (bRepaintWindow)
			{
				bOk = GateBoardRead(R, Now);
			}
			else if (bWinWindow)
			{
				bOk = GateGoalWins(R, Now);
			}
			else if (bShortOnDisc)
			{
				bOk = GateGoalShort(R, Now);
			}
			else if (R.State != ERunState::Running)
			{
				bOk = GateEndedNeverChanges(R, Now);
			}
			else
			{
				bOk = GateRunReads(R, Now);
			}
			if (bOk)
			{
				bOk = GateNoTeleport(R, Now, Dt);
			}
			if (!bOk)
			{
				return;
			}

			int32 Total = 0;
			R.LitLastJudged = LitCountOf(R, Total);
			const FString Word = WordOf(R);
			R.bEverReadWon = R.bEverReadWon || Word.Equals(kWordWon);
			R.bEverReadLost = R.bEverReadLost || Word.Equals(kWordLost);
		}

		// THE IN-SCENE NEGATIVE CONTROL, ALWAYS LAST and only once whichever gate was
		// armed has already agreed: a submission that teleports a runner onto the
		// bystander's disc trips this as well as the return gate, and the RETURN gate
		// is the diagnosis that matters. A submission whose two legs are perfect and
		// whose ownership is shared has nothing else armed, and is named here.
		if (bAnyJudged && !GateBystander(Now))
		{
			return;
		}
	}

	for (FRunner& R : Runners)
	{
		if (R.Actor.IsValid())
		{
			R.WasAt = R.Actor->GetActorLocation();
			R.bHaveWasAt = true;
		}
	}

	DrivePhase(Now);
	AdvancePhases(Now);

	if (bDriveComplete && IsRunning() && !bGraded)
	{
		FinalGrade(Now);
	}
}

void ALifeRunTerminalFunctionalTest::FinalGrade(double Now)
{
	bGraded = true;
	const FRunner& A = Runners[0];
	const FRunner& B = Runners[1];
	const FRunner& C = Runners[2];

	// ---- first: did the DRIVE happen at all? --------------------------------
	// The fixture's own model of the three runs is set by geometry and staging and
	// nothing a submission does can move it, so a model that did not reach one
	// loss, one win and one still-running is OURS. It is checked here, and
	// attributed here, before anything is asked of the submission.
	if (!(A.State == ERunState::Lost && B.State == ERunState::Won
		  && C.State == ERunState::Running))
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the drive was meant to put the near runner out, "
				 "win the middle one and leave the far one alone, and the fixture's own "
				 "model says %s / %s / %s. The staging and the drive do not agree, which "
				 "is ours and not the submission's"),
			ExpectedWordFor(A), ExpectedWordFor(B), ExpectedWordFor(C)));
		return;
	}

	// ---- then, what the LEVEL IS SHOWING at the end --------------------------
	// CORROBORATIVE, and declared as such: a runner reading the wrong word has
	// already been named by a per-frame gate long before this line. It is read off
	// the three runners' own lamps and words anyway -- never off the model above --
	// so that the run-level statement is a statement about the SUBMISSION.
	{
		int32 TotalA = 0, TotalB = 0, TotalC = 0;
		const int32 LitA = LitCountOf(A, TotalA);
		const int32 LitB = LitCountOf(B, TotalB);
		const int32 LitC = LitCountOf(C, TotalC);
		const FString WordA = WordOf(A);
		const FString WordB = WordOf(B);
		const FString WordC = WordOf(C);
		if (!WordA.Equals(kWordLost) || LitA != 0 || !WordB.Equals(kWordWon)
			|| LitB != B.FrozenLit || !WordC.Equals(kWordRunning)
			|| LitC != PaintedOn(C.MarkerIndex)
			|| A.bEverReadWon || B.bEverReadLost)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("BothRunsEndedTheirOwnWay: at the end of the run exactly one runner "
					 "had to be reading %s with every lamp dark, exactly one %s with the "
					 "%d lamp(s) it won with, and the third %s with the %d its own board "
					 "calls for. The near runner reads '%s' with %d lit (it %s read won "
					 "at some point), the middle runner reads '%s' with %d lit (it %s "
					 "read lost), and the far runner reads '%s' with %d lit. A run is won "
					 "or lost, never both, and whichever came first is the one that "
					 "stands"),
				kWordLost, kWordWon, B.FrozenLit, kWordRunning, PaintedOn(C.MarkerIndex),
				*WordA, LitA, A.bEverReadWon ? TEXT("DID") : TEXT("never"),
				*WordB, LitB, B.bEverReadLost ? TEXT("DID") : TEXT("never"),
				*WordC, LitC));
			return;
		}
	}

	// ---- then, everything the RUN owes: a leg that never happened proves nothing --
	if (A.SpendingCrossings < 4 || B.SpendingCrossings < 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the crumbling ground only spent %d life/lives "
				 "on the near runner and %d on the middle one; the re-trigger rule "
				 "needs at least four and two, in matched pairs, or a one-shot latch "
				 "would grade exactly like a working hazard"),
			A.SpendingCrossings, B.SpendingCrossings));
		return;
	}
	if (A.Crossings != PredictedFinalCrossing + 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the staging says the near runner runs out on "
				 "crossing %d and the drive produced %d crossing(s) in total; the "
				 "drive and the staging table do not agree, which is ours and not the "
				 "submission's"), PredictedFinalCrossing, A.Crossings));
		return;
	}
	if (A.ConflictEvents < 3 || B.ConflictEvents < 3)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the ended runs were driven at only %d and %d "
				 "time(s); ARunThatEndedNeverChangesAgain needs three conflicting "
				 "events on each terminal kind or it graded nothing about permanence"),
			A.ConflictEvents, B.ConflictEvents));
		return;
	}
	if (B.DiscArrivals < 2 || A.DiscArrivals < 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the finish disc was arrived at %d time(s) by "
				 "the middle runner and %d by the near one; the re-trigger rule needs "
				 "the finish walked onto more than once"), B.DiscArrivals,
			A.DiscArrivals));
		return;
	}
	if (DemandWrites < 2 || B.ShortOnDiscJudged < 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the finish's own number moved %d time(s) and "
				 "the win-leg runner was judged standing on the disc short of it on "
				 "%d frame(s). Without both, the leg never gauged what the goal asks "
				 "for and an answer that opens the goal to anybody who walks on would "
				 "have graded exactly like one that reads the number"),
			DemandWrites, B.ShortOnDiscJudged));
		return;
	}

	FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
		TEXT("Leg %d Hz: the near runner was claimed %d time(s) and ran out on the "
			 "last one (board %d -> %d -> %d); the middle runner was claimed %d "
			 "time(s), stood on the finish short of it on %d judged frame(s) while "
			 "the goal asked %d -> %d -> %d, and won with %d lamp(s) lit (board "
			 "%d -> %d -> %d); the far "
			 "runner was never touched and still reads %s with %d lamp(s) lit. Both "
			 "ended runs were driven at %d and %d times afterwards and neither moved. "
			 "Finished at t=%.1f s"),
		Stage.Rate, A.Deaths, Stage.StartA, Stage.RepaintA, Stage.FinalA, B.Deaths,
		B.ShortOnDiscJudged, Stage.DemandStart, Stage.DemandMid, Stage.DemandEnd,
		B.FrozenLit, Stage.StartB, Stage.RepaintB, Stage.FinalB, kWordRunning,
		PaintedOn(C.MarkerIndex), A.ConflictEvents, B.ConflictEvents, Now));
}

// ---------------------------------------------------------------------------
// Calibration logging + the sentinel
// ---------------------------------------------------------------------------

void ALifeRunTerminalFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString Bits;
	for (const FRunner& R : Runners)
	{
		int32 Total = 0;
		const int32 Lit = LitCountOf(R, Total);
		const FVector At = R.Actor.IsValid() ? R.Actor->GetActorLocation() : FVector::ZeroVector;
		Bits += FString::Printf(TEXT("[%s paint=%d d=%d want=%d/%s got=%d/'%s' at=%s] "),
			R.Label, PaintedOn(R.MarkerIndex), R.Deaths, ExpectedLitFor(R),
			ExpectedWordFor(R), Lit, *WordOf(R), *Describe(At));
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-liferun calib] cp%d t=%.2f leg=%dHz goal-asks=%d phase=%d('%s') %s"),
		Index, Now, Stage.Rate, DemandNow(), PhaseIndex,
		Phases.IsValidIndex(PhaseIndex) ? *Phases[PhaseIndex].Label : TEXT("-"), *Bits);
}

void ALifeRunTerminalFunctionalTest::OnCheckpoint(int32 CheckpointIndex,
	double TimeSeconds)
{
	if (!bPrepared || Runners.Num() != 3)
	{
		return;
	}
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kGradedCheckpoints)
	{
		return;
	}
	// THE SENTINEL. The base class ends the test the moment the last scheduled
	// checkpoint is sampled, so the run-level gate is evaluated here too -- whichever
	// comes first.
	if (bDriveComplete || bGraded)
	{
		return;
	}
	if (!ReCheckDisplays(TimeSeconds))
	{
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the drive was still at phase %d ('%s') at the "
			 "sentinel with every display gate green and nothing in the level moved; "
			 "the level is staged so the drive cannot finish, which is ours and not "
			 "the submission's"), PhaseIndex,
		Phases.IsValidIndex(PhaseIndex) ? *Phases[PhaseIndex].Label : TEXT("-")));
}
