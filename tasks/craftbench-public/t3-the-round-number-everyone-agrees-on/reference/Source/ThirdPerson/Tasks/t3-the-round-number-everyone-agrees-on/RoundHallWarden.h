// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t3-the-round-number-everyone-agrees-on.
//
// The round number belongs to the HALL. Not to a sign, and not to the body walking
// around in the room -- both of those come and go while the number does not. So it
// lives on something scoped to the world itself, which exists before the first runner
// does, outlives every runner, and can answer a sign that did not exist when the number
// was last set.
//
// Four numbers are read off the world at the moment they are needed and none of them is
// written down here: the number the hall starts on (off the entrance stone), the step
// (off the mark, EVERY time somebody steps on it, because it changes mid-visit), the
// relic's painted number (never touched -- the relic is simply not one of the signs
// this file writes to), and where the entrance mark is.
//
// THE DOORPLATE IS WHERE THE TWO HALVES MEET. Its value is not a fact about the number
// and not a fact about the body: it is the number READ AT THE MOMENT A BODY WALKS IN.
// So it is written in exactly the two places where a runner starts walking in this hall
// -- once when the hall opens, and once each time a fresh runner is put in -- and it is
// deliberately NOT written by TellEverySignInTheHall, because it does not follow the
// hall.
//
// Nothing in the supplied hall is modified. This file is the whole answer.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "RoundHallWarden.generated.h"

class AEntranceStoneActor;
class AHallSignActor;
class AStepMarkActor;

UCLASS()
class THIRDPERSON_API URoundHallWarden : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

	/** The number the hall is on right now. */
	int32 GetRoundNumber() const { return RoundNumber; }

private:
	/** Somebody stepped onto the mark: the number goes up ONCE by whatever the mark is
	 *  carrying at this moment, and every sign that belongs to the hall follows. */
	UFUNCTION()
	void HandleSteppedOn(AActor* Walker);

	/** The hoist has put a fresh sign up. It is one of the hall's and it is blank, so
	 *  it is told the number the hall is on right now -- not the one it started on. */
	UFUNCTION()
	void HandleSignRaised(AHallSignActor* RaisedSign);

	/** A runner has been lost. The number is not touched by this in any way. */
	UFUNCTION()
	void HandleRunnerLost();

	/** Put a fresh runner on the entrance mark, under the player's control. Safe to
	 *  call when there is already a runner: it does nothing in that case, which is what
	 *  keeps "never more than one alive" true no matter how often it is called. */
	void PutANewRunnerIn();

	/** Tell every sign that belongs to the hall what the hall is on. Signs that do not
	 *  belong to it -- the relic at the back -- are not written to, ever. THE DOORPLATE
	 *  IS NOT ONE OF THESE: it does not follow the hall. */
	void TellEverySignInTheHall();

	/** Somebody is starting their walk through the hall now, so the doorplate takes the
	 *  round the hall is on at this moment and keeps it until the next one starts. */
	void WriteTheDoorplate();

	/** What the hall is on. The one copy; nothing else keeps its own. */
	int32 RoundNumber = 0;

	UPROPERTY()
	AEntranceStoneActor* Stone = nullptr;

	UPROPERTY()
	AStepMarkActor* Mark = nullptr;
};
