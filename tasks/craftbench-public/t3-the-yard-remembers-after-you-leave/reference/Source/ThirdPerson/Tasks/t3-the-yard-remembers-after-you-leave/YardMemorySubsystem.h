// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION -- the whole decision layer.
//
// THE ONE THING THAT MATTERS ABOUT THIS CLASS: it holds no memory of the yard at all.
// It knows which posts, pads and boards are currently standing -- that is bookkeeping
// about the props, and it is rebuilt from scratch every time the yard opens -- and it
// holds NOTHING about what has been taken, what has been banked, or where the mark is.
// Every one of those questions is answered by reading the record off disk at the moment
// it is asked, and every answer that changes is written straight back.
//
// That is not fastidiousness. This object outlives the props, so if it kept the answer
// warm the yard would reopen correctly even with the record deleted -- and the whole
// point of the exercise is that the record IS the memory. Caching it here is the one
// change that turns a correct solution into a wrong one while every visible number
// still looks right.
//
// It lives on the game instance because it has to outlive the props: the yard destroys
// every post, pad and board when it shuts, so whatever coordinates them cannot itself
// be one of them.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "YardMemorySubsystem.generated.h"

class AMemoryBoardActor;
class AMemoryPadActor;
class AMemoryPostActor;
class UYardMemoryRecord;

UCLASS()
class THIRDPERSON_API UYardMemorySubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** A post reporting for duty. This is where a FRESH post finds out whether it was
	 *  already taken -- and where it is told to show the number it actually arrived
	 *  carrying, never a remembered one. */
	void RegisterPost(AMemoryPostActor* Post);
	void UnregisterPost(AMemoryPostActor* Post);

	/** A pad reporting for duty. Re-resolves which lamp in that yard should be burning,
	 *  and -- only when the yard has been rebuilt into a world that is already running
	 *  -- puts the runner back on the marked pad. Re-run on every pad's arrival, so the
	 *  order the pads turn up in cannot change the answer. */
	void RegisterPad(AMemoryPadActor* Pad);
	void UnregisterPad(AMemoryPadActor* Pad);

	/** A board reporting for duty. It reads its own yard's total and nobody else's. */
	void RegisterBoard(AMemoryBoardActor* Board);
	void UnregisterBoard(AMemoryBoardActor* Board);

	/** Somebody walked into a post. A post that has already been taken is worth
	 *  nothing at all and nothing moves. */
	void TakePost(AMemoryPostActor* Post);

	/** Somebody stood on a pad. That pad becomes the yard's mark. */
	void StandOnPad(AMemoryPadActor* Pad);

private:
	/** Always returns a record. When nothing is written down, that record is empty --
	 *  which is exactly what a yard nobody has ever visited looks like. */
	UYardMemoryRecord* ReadRecord() const;
	void WriteRecord(UYardMemoryRecord* Record) const;

	void ShowYardTotal(const UYardMemoryRecord* Record, FName Yard) const;
	void ShowYardPosts(const UYardMemoryRecord* Record, FName Yard) const;
	/** Not const: setting the runner down raises the re-entrancy flag below. */
	void ShowYardLamps(const UYardMemoryRecord* Record, FName Yard, bool bPlaceRunner);

	/** The pad whose lamp should be burning: the one written down if it is standing in
	 *  this yard, otherwise the yard's first pad. */
	FName ResolveMarkedPad(const UYardMemoryRecord* Record, FName Yard) const;

	void PlaceRunnerOn(const AMemoryPadActor* Pad);

	/** TRUE only for the instant the yard is setting the runner down on a pad.
	 *
	 *  This is load-bearing, and the reason is worth spelling out because it costs a
	 *  correct-looking solution the one gate it cares most about. Moving a character
	 *  fires begin-overlap NOTIFICATIONS SYNCHRONOUSLY -- `USceneComponent`'s move path
	 *  calls `UpdateOverlaps(..., bDoNotifies = true)` before `SetActorLocation`
	 *  returns -- so the pad the runner is put down on immediately reports somebody
	 *  standing on it. Treating that as a visit would let the yard's own placement
	 *  MOVE THE MARK, and because the pads come back one at a time, the first pad to
	 *  arrive is not usually the marked one: the yard would put the runner down on
	 *  whichever pad happened to register first, overwrite the record with it, and then
	 *  faithfully honour its own mistake for the rest of the run. Being set down by the
	 *  yard is not the runner choosing to stand somewhere, so a visit that arrives
	 *  while this flag is up is ignored. */
	bool bSettingRunnerDown = false;

	/** The props that are standing RIGHT NOW. Bookkeeping only -- nothing here is an
	 *  answer, and all of it is thrown away and rebuilt when the yard reopens. */
	TArray<TWeakObjectPtr<AMemoryPostActor>> Posts;
	TArray<TWeakObjectPtr<AMemoryPadActor>> Pads;
	TArray<TWeakObjectPtr<AMemoryBoardActor>> Boards;
};
