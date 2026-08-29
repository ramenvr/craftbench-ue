// Copyright CraftBench. All Rights Reserved.

#include "RaceTheClockFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kRoundSeconds = 10.0;
	constexpr double kDeadlineSlackS = 0.5;   // "within 0.5 seconds of 10.0 seconds"
	constexpr double kClockSlackS = 1.0;      // "within 1.0 second of the seconds left"
	constexpr int32 kCoinCount = 7;

	// UNDISCLOSED: fixture geometry and clocking.
	constexpr double kContactCm = 150.0;      // > the 60 cm region + 34 cm capsule
	constexpr double kWaypointReachedCm = 70.0;
	constexpr double kResumeAfterS = 11.2;    // safely past the deadline + its slack

	const TCHAR* const kInProgress = TEXT("InProgress");
	const TCHAR* const kTimedOut = TEXT("TimedOut");

	int32 FirstNumber(const FString& In)
	{
		FString Digits;
		for (const TCHAR C : In)
		{
			if (FChar::IsDigit(C)) { Digits.AppendChar(C); }
			else if (!Digits.IsEmpty()) { break; }
		}
		return Digits.IsEmpty() ? -1 : FCString::Atoi(*Digits);
	}
}

ARaceTheClockFunctionalTest::ARaceTheClockFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

int32 ARaceTheClockFunctionalTest::ReadScore() const
{
	AActor* const R = Round.Get();
	if (const FIntProperty* P = R
			? FindFProperty<FIntProperty>(R->GetClass(), TEXT("Score")) : nullptr)
	{
		return P->GetPropertyValue_InContainer(R);
	}
	return -1;
}

float ARaceTheClockFunctionalTest::ReadTimeRemaining() const
{
	AActor* const R = Round.Get();
	if (const FFloatProperty* P = R
			? FindFProperty<FFloatProperty>(R->GetClass(), TEXT("TimeRemaining")) : nullptr)
	{
		return P->GetPropertyValue_InContainer(R);
	}
	return -1.0f;
}

FString ARaceTheClockFunctionalTest::ReadRoundState() const
{
	AActor* const R = Round.Get();
	if (const FStrProperty* P = R
			? FindFProperty<FStrProperty>(R->GetClass(), TEXT("RoundState")) : nullptr)
	{
		return P->GetPropertyValue_InContainer(R).TrimStartAndEnd();
	}
	return FString();
}

FString ARaceTheClockFunctionalTest::ReadFace(const TCHAR* Name) const
{
	AActor* const R = Round.Get();
	if (R == nullptr)
	{
		return FString();
	}
	// By COMPONENT NAME, so a subclassed round marker still answers and adding more
	// readouts on top cannot confuse this.
	TArray<UTextRenderComponent*> Texts;
	R->GetComponents<UTextRenderComponent>(Texts);
	for (UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetName() == Name)
		{
			return T->Text.ToString();
		}
	}
	return FString();
}

int32 ARaceTheClockFunctionalTest::ReadCoinValue(AActor* Coin) const
{
	if (const FIntProperty* P = Coin
			? FindFProperty<FIntProperty>(Coin->GetClass(), TEXT("PointValue")) : nullptr)
	{
		return P->GetPropertyValue_InContainer(Coin);
	}
	return -1;
}

bool ARaceTheClockFunctionalTest::CoinVisiblyGone(const FCoin& Coin) const
{
	AActor* const A = Coin.Actor.Get();
	if (A == nullptr || !IsValid(A))
	{
		return true;   // destroyed
	}
	if (FVector::Dist(A->GetActorLocation(), Coin.Placed) > 500.0)
	{
		return true;   // taken away
	}
	TArray<UPrimitiveComponent*> Prims;
	A->GetComponents<UPrimitiveComponent>(Prims);
	for (UPrimitiveComponent* P : Prims)
	{
		// Consuming a coin by hiding its mesh reads as gone, exactly like destroying
		// it: both look identical to a human.
		if (P != nullptr && P->IsVisible() && !P->bHiddenInGame
			&& P->GetClass()->GetName().Contains(TEXT("StaticMesh")))
		{
			return false;
		}
	}
	return true;
}

bool ARaceTheClockFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Rounds, CoinActors;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RaceRound")), Rounds);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RaceCoin")), CoinActors);
	if (Rounds.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the coin arena is not staged as authored - "
				 "expected one round marker, found %d"), Rounds.Num()));
		return false;
	}
	if (CoinActors.Num() != kCoinCount)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the coin arena is not staged as authored - "
				 "expected %d coins, found %d"), kCoinCount, CoinActors.Num()));
		return false;
	}
	// THE SURFACE SWAP. This task's agent delivers TWO classes -- the round and the
	// coin -- so both are offered to the Blueprint lane, and the coins are swapped
	// as a SET because a half-swapped row would grade C++ for some coins and
	// Blueprint for others, which is a verdict about neither surface. The two
	// classes are unrelated, so resolving each against its own placed class cannot
	// collide. Nothing happens on the C++ lane, where no Blueprint under
	// /Game/Tasks derives from either placed class.
	SwapAllForGradedBlueprint(CoinActors);
	SwapForGradedBlueprint(Rounds[0]);
	// Self-check rather than trusting the swap: re-resolve both by tag and require
	// the authored counts again. A swap that half-completed shows up here as a
	// HARNESS-PRECONDITION, not as a graded failure of the submission.
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RaceRound")), Rounds);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RaceCoin")), CoinActors);
	if (Rounds.Num() != 1 || CoinActors.Num() != kCoinCount)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the surface swap left the arena mis-staged - "
				 "%d round marker(s) and %d coin(s) after it, not 1 and %d"),
			Rounds.Num(), CoinActors.Num(), kCoinCount));
		return false;
	}

	Round = Rounds[0];
	{
		TArray<AActor*> Pads;
		UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RaceReplayPad")),
			Pads);
		if (Pads.Num() != 1)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %d actor(s) tagged RaceReplayPad, "
					 "expected 1; without one the fixture cannot ask for a second "
					 "round"), Pads.Num()));
			return false;
		}
		ReplayPad = Pads[0];
		ReplayPadAt = ReplayPad->GetActorLocation();
		RoundSeconds = ReadTimeRemaining();
		if (RoundSeconds < 1.0f)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the round ships showing %.1f s, so the "
					 "fixture cannot tell what a full clock looks like"),
				RoundSeconds));
			return false;
		}
	}
	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no possessed player character in the arena"));
		return false;
	}
	if (Hero->GetMesh() == nullptr || Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the driven character is not visibly "
				 "represented, so a reviewer would see nothing"));
		return false;
	}
	for (const TCHAR* Face : {TEXT("ScoreText"), TEXT("ClockText"), TEXT("StateText")})
	{
		if (ReadFace(Face).IsEmpty())
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a readable round surface is missing - the "
					 "readout named %s was not found on the round marker"), Face));
			return false;
		}
	}
	if (ReadScore() < 0 || ReadTimeRemaining() < 0.0f || ReadRoundState().IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: a readable round surface is missing - Score, "
				 "TimeRemaining or RoundState could not be read"));
		return false;
	}

	// Coins, ordered along the route, with the control identified by being the one
	// off the Y = 0 line the route walks.
	for (AActor* A : CoinActors)
	{
		FCoin C;
		C.Actor = A;
		C.Placed = A->GetActorLocation();
		C.Value = ReadCoinValue(A);
		if (C.Value <= 0)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a readable round surface is missing - a "
					 "coin carries no PointValue"));
			return false;
		}
		Coins.Add(C);
	}
	Coins.Sort([](const FCoin& A, const FCoin& B) { return A.Placed.X < B.Placed.X; });
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (FMath::Abs(Coins[i].Placed.Y) > 100.0)
		{
			ControlIndex = i;
		}
	}
	if (ControlIndex == INDEX_NONE)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the coin arena is not staged as authored - no "
				 "coin sits off the route, so there is no control"));
		return false;
	}
	return true;
}

void ARaceTheClockFunctionalTest::PrepareTest()
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

	// The route walks the Y = 0 line and visits the on-route coins in X order. The
	// first four are reached inside the round; the drive then HOLDS until the clock
	// is safely past zero before walking into the last two, which is what makes
	// "after zero the score is final" a measured fact rather than a promise.
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (i != ControlIndex)
		{
			Route.Add(FVector(Coins[i].Placed.X, 0.0, 0.0));
		}
	}

	// 14 gauging instants, plus a SENTINEL far past any real grade: the base declares
	// success the moment the last scheduled checkpoint is crossed.
	TArray<double> Schedule;
	for (int32 i = 0; i < 14; ++i)
	{
		Schedule.Add(1.0 + 1.5 * i);
	}
	Schedule.Add(60.0);
	TimeLimitMargin = 6.0f;
	// After the coins and the wait-out, the drive walks to the replay pad: a second
	// round has to have somewhere to come from.
	Route.Add(FVector(ReplayPadAt.X, ReplayPadAt.Y,
		Route.Num() ? Route.Last().Z : ReplayPadAt.Z));
	SetCheckpointSchedule(Schedule);
}

void ARaceTheClockFunctionalTest::SampleReadoutsAndReplay()
{
	AActor* const R = Round.Get();
	if (R == nullptr || !Hero.IsValid())
	{
		return;
	}
	const FVector HeroAt = Hero->GetActorLocation();

	// THE READOUTS HAVE TO FACE THE PLAYER. A board somebody has to walk around to
	// read is not a readout. Sampled every frame and judged over the whole run, so a
	// board that swings round to follow is allowed to lag.
	TArray<UTextRenderComponent*> Texts;
	R->GetComponents<UTextRenderComponent>(Texts);
	for (const UTextRenderComponent* Txt : Texts)
	{
		if (Txt == nullptr)
		{
			continue;
		}
		const FVector ToHero =
			(HeroAt - Txt->GetComponentLocation()).GetSafeNormal2D();
		if (ToHero.IsNearlyZero())
		{
			continue;
		}
		// A UTextRenderComponent reads along its own +X.
		const FVector Facing =
			Txt->GetComponentRotation().Vector().GetSafeNormal2D();
		++FacingSamples;
		FacingHits += (FVector::DotProduct(Facing, ToHero)
			>= FMath::Cos(FMath::DegreesToRadians(35.0))) ? 1 : 0;
	}

	// READ THE PAD, not a distance. A radius picked by hand does not match the pad's
	// own trigger volume: the character brushed the corner of the box, the pad fired,
	// and the fixture -- still measuring 140 cm to the centre -- called it a round
	// that restarted on its own.
	if (!bStoodOnReplayPad && ReplayPad.IsValid())
	{
		TArray<UPointLightComponent*> Lamps;
		ReplayPad->GetComponents<UPointLightComponent>(Lamps);
		for (const UPointLightComponent* L : Lamps)
		{
			if (L != nullptr && L->Intensity > 0.0f)
			{
				bStoodOnReplayPad = true;
			}
		}
	}

	const bool bTimedOut =
		ReadRoundState().Equals(TEXT("TimedOut"), ESearchCase::IgnoreCase);
	if (bWasTimedOut && ReadTimeRemaining() >= RoundSeconds * 0.9f)
	{
		++RoundsSeen;
		RoundStartedAtWorld = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
		// A fresh round starts from nothing, so the running score check re-baselines
		// here rather than reporting the reset as a score that went down. Every coin
		// the first round ate is still gone, so the second round's ceiling is
		// whatever is left on the floor -- which is what makes the replay a
		// different round rather than the same one again.
		LastScore = 0;
		ExpectedScore = 0;
		// And the round is no longer over, so "the score is final" starts again from
		// the next whistle rather than from the last one.
		bEverTimedOut = false;
		ScoreAtTimeout = 0;
		if (!bStoodOnReplayPad)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRoundOnlyRestartsFromThePad: the clock went back to %.1f s "
					 "with nobody having stood on the replay pad; a round that "
					 "restarts on its own is not one a player asked for"),
				ReadTimeRemaining()));
			return;
		}
		if (ReadScore() != 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheRoundCanBeRunAgain: the clock restarted but the score still "
					 "reads %d; a fresh round starts from nothing"), ReadScore()));
			return;
		}
	}
	bWasTimedOut = bTimedOut;
}

void ARaceTheClockFunctionalTest::LogCalib(int32 Index, double Now) const
{
	int32 Gone = 0;
	for (const FCoin& C : Coins)
	{
		if (CoinVisiblyGone(C)) { ++Gone; }
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-race calib] cp%d t=%.2f score=%d remain=%.2f state='%s' gone=%d "
			 "faces='%s'/'%s'/'%s' wp=%d"),
		Index, Now, ReadScore(), ReadTimeRemaining(), *ReadRoundState(), Gone,
		*ReadFace(TEXT("ScoreText")), *ReadFace(TEXT("ClockText")),
		*ReadFace(TEXT("StateText")), Waypoint);
}

void ARaceTheClockFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Round.IsValid() || !Hero.IsValid())
	{
		return;
	}
	SampleReadoutsAndReplay();
	const UWorld* const World = GetWorld();
	// Play begins at world time zero, and that is the instant the 10 seconds are
	// measured from -- the prompt says so, so the fixture uses the same clock.
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;
	// MEASURED FROM THIS ROUND'S START, not from world time. The arena can be replayed
	// now, so "seconds since the level began" stops being the same thing as "seconds
	// since the round began" the moment somebody stands on the pad.
	const double TrueRemaining =
		FMath::Max(0.0, double(RoundSeconds) - (Now - RoundStartedAtWorld));

	const int32 Score = ReadScore();
	const float Remaining = ReadTimeRemaining();
	const FString State = ReadRoundState();

	// ---- THE CLOCK, CONTINUOUSLY ----
	if (Remaining < -0.001f)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ClockNeverGoesNegative: the clock showed a negative number (%.2f)"),
			Remaining));
		return;
	}
	if (FMath::Abs(static_cast<double>(Remaining) - TrueRemaining) > kClockSlackS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ClockTracksTheRound: the clock read %.2f with %.2f seconds actually "
				 "left (the level allows %.1f of drift)"),
			Remaining, TrueRemaining, kClockSlackS));
		return;
	}
	if (State != kInProgress && State != kTimedOut)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RoundStateIsOneOfTwoWords: the round state read '%s', which is "
				 "neither InProgress nor TimedOut"), *State));
		return;
	}
	// INTO THIS ROUND, not into the level. The arena can be replayed, so a second
	// round is legitimately still running long after ten seconds of play.
	const double IntoRound = Now - RoundStartedAtWorld;
	if (IntoRound < kRoundSeconds - kDeadlineSlackS && State != kInProgress)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RoundRunsForTenSeconds: the round ended early (state '%s' at %.2f "
				 "seconds of play)"), *State, Now));
		return;
	}
	if (IntoRound > kRoundSeconds + kDeadlineSlackS && State != kTimedOut)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RoundRunsForTenSeconds: the round was still running at %.2f seconds "
				 "of play"), Now));
		return;
	}
	if (State == kTimedOut && !bEverTimedOut)
	{
		bEverTimedOut = true;
		ScoreAtTimeout = Score;
		TimeoutSeenAt = Now;
		if (Remaining > 0.001f)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ClockReadsZeroWhenTheRoundEnds: the round timed out with the "
					 "clock still reading %.2f"), Remaining));
			return;
		}
	}

	// ---- SCORE ----
	if (Score < LastScore)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ScoreOnlyRisesFromCoins: the score went down (%d to %d)"),
			LastScore, Score));
		return;
	}
	if (bEverTimedOut && Score != ScoreAtTimeout)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ScoreIsFinalAfterTheRound: the score changed after the round ended "
				 "(%d at the whistle, %d now)"), ScoreAtTimeout, Score));
		return;
	}

	// ---- COINS ----
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		FCoin& C = Coins[i];
		const bool bGone = CoinVisiblyGone(C);
		if (bGone && !C.bConsumed)
		{
			C.bConsumed = true;
			if (i == ControlIndex)
			{
				FinishTest(EFunctionalTestResult::Failed,
					TEXT("TheUntouchedCoinSurvives: the coin the character never "
						 "walked into was consumed anyway"));
				return;
			}
			if (bEverTimedOut)
			{
				FinishTest(EFunctionalTestResult::Failed,
					TEXT("ScoreIsFinalAfterTheRound: a coin was consumed after the "
						 "round had ended"));
				return;
			}
			ExpectedScore += C.Value;
			if (Score != ExpectedScore)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("CoinAddsItsOwnValue: a coin worth %d was consumed and the "
						 "score read %d where %d was due"),
					C.Value, Score, ExpectedScore));
				return;
			}
		}
	}
	if (ControlIndex != INDEX_NONE && Coins.IsValidIndex(ControlIndex))
	{
		const FCoin& Ctrl = Coins[ControlIndex];
		if (Ctrl.Actor.IsValid()
			&& FVector::Dist(Ctrl.Actor->GetActorLocation(), Ctrl.Placed) > 200.0)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheUntouchedCoinSurvives: the coin the character never walked "
					 "into left the spot it was placed on"));
			return;
		}
		if (Ctrl.Actor.IsValid() && ReadCoinValue(Ctrl.Actor.Get()) != Ctrl.Value)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheUntouchedCoinSurvives: the coin the character never walked "
					 "into lost its own point value"));
			return;
		}
	}

	// ---- THE READOUTS ----
	{
		const int32 ShownScore = FirstNumber(ReadFace(TEXT("ScoreText")));
		if (ShownScore >= 0 && ShownScore != Score)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ReadoutsShowTheLiveValues: the score readout shows %d with a "
					 "score of %d"), ShownScore, Score));
			return;
		}
		const int32 ShownClock = FirstNumber(ReadFace(TEXT("ClockText")));
		if (ShownClock >= 0
			&& FMath::Abs(static_cast<double>(ShownClock) - Remaining) > kClockSlackS + 1.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ReadoutsShowTheLiveValues: the clock readout shows %d with %.2f "
					 "seconds left"), ShownClock, Remaining));
			return;
		}
		const FString ShownState = ReadFace(TEXT("StateText")).TrimStartAndEnd();
		if (!ShownState.IsEmpty() && !ShownState.Contains(State))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ReadoutsShowTheLiveValues: the state readout shows '%s' with a "
					 "round state of '%s'"), *ShownState, *State));
			return;
		}
	}

	// ---- DRIVE ----
	// Four coins inside the round, then HOLD until the clock is safely past zero, then
	// the last two: that is what makes "after zero the score is final" measured.
	if (bWaitingOutTheClock && Now >= kResumeAfterS)
	{
		bWaitingOutTheClock = false;
	}
	if (!bWaitingOutTheClock && Route.IsValidIndex(Waypoint))
	{
		const FVector Here = Hero->GetActorLocation();
		const FVector Target = Route[Waypoint];
		const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
		if (Flat.Size2D() <= kWaypointReachedCm)
		{
			++Waypoint;
			if (Waypoint == 4) { bWaitingOutTheClock = true; }
		}
		else
		{
			Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		}
	}

	LastScore = Score;
}

void ARaceTheClockFunctionalTest::OnCheckpoint(int32 Index, double TimeSeconds)
{
	if (!Round.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : TimeSeconds;
	LogCalib(Index, Now);

	if (Index < 14)
	{
		return;
	}

	// ---- THE TWO THINGS A REVIEWER FOUND BY PLAYING IT ----
	if (FacingSamples > 0 && double(FacingHits) < double(FacingSamples) * 0.8)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheReadoutsFaceYou: the readouts pointed at the character on %d of "
				 "%d samples. A board somebody has to walk around to read is not a "
				 "readout"), FacingHits, FacingSamples));
		return;
	}
	if (RoundsSeen < 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRoundCanBeRunAgain: %d round ran. The arena carries a replay pad "
				 "and the drive stands on it after the first round times out; "
				 "standing there has to start a fresh round, from a full clock and no "
				 "score"), RoundsSeen));
		return;
	}
	// The SENTINEL. Everything below is vacuously true if its leg never happened, so
	// each carries its own precondition-reached message.
	if (!bEverTimedOut)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RoundRunsForTenSeconds: the round never ended, so nothing about "
				 "what happens after the whistle was measured"));
		return;
	}
	int32 Consumed = 0;
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (i != ControlIndex && Coins[i].bConsumed) { ++Consumed; }
	}
	if (Consumed < 4)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("CoinAddsItsOwnValue: only %d coin(s) were consumed inside the "
				 "round, so per-coin scoring was never measured"), Consumed));
		return;
	}
	if (Waypoint < Route.Num())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ScoreIsFinalAfterTheRound: the run never reached the coins it was "
				 "meant to touch after the whistle (%d of %d waypoints)"),
			Waypoint, Route.Num()));
		return;
	}
	if (CoinVisiblyGone(Coins[ControlIndex]))
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheUntouchedCoinSurvives: the coin the character never walked into "
				 "was gone by the end of the run"));
		return;
	}
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("the round ran its ten seconds, each coin added its own value while it "
			 "ran, the score was final afterwards, and the coin nobody walked into "
			 "was still there"));
}
