// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION -- the whole decision layer.
//
// It lives on the game instance because it has to outlive the props: the yard destroys
// every stall and the board part way through the day, so anything that remembers the
// purse cannot itself be a stall or the board. It also writes the record to a slot on
// disk after every change, which is what makes the day survive more than the actors.
//
// The stalls and the board register themselves as they begin play and hand back the
// three questions this class answers: what a step onto a mat does, what a fresh stall
// comes back holding, and what the two displays should read.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "MarketKeeperSubsystem.generated.h"

class AMarketLedgerActor;
class AMarketStallActor;

UCLASS()
class THIRDPERSON_API UMarketKeeperSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** The board is the only place the purse's opening size and the carry limit are
	 *  written, so the day cannot start until one turns up. On a REOPENED board the
	 *  opening size is ignored: the purse already has a history. */
	void AttachBoard(AMarketLedgerActor* InBoard);

	/** A stall reporting for duty. This is where a fresh stall gets reconciled: what
	 *  it had left when it closed, plus what it was delivered while the yard was shut,
	 *  and never more than it can hold. A stall the record has never heard of keeps
	 *  what it arrived with. */
	void AttachStall(AMarketStallActor* Stall);

	void DetachStall(AMarketStallActor* Stall);

	/** ONE attempt to buy ONE thing. Every refusal leaves everything untouched -- the
	 *  three tests are all done before the first byte of state moves, so there is no
	 *  half-transaction to unwind. */
	void TryBuy(AMarketStallActor* Stall);

private:
	void LoadRecordOnce();
	void WriteRecord() const;
	void RefreshBoard() const;
	void RefreshStall(AMarketStallActor* Stall) const;
	void RefreshEverything() const;

	TWeakObjectPtr<AMarketLedgerActor> Board;
	TArray<TWeakObjectPtr<AMarketStallActor>> Stalls;

	int32 Coins = 0;
	int32 CarryLimit = 0;

	/** How many of each kind are owned, and what each stall had left. Both keyed by
	 *  goods, never by index or by where a stall stands. */
	TMap<FName, int32> Owned;
	TMap<FName, int32> StockLeft;

	/** The record is read from disk exactly once per process. After that this object
	 *  IS the record and the disk copy is a mirror of it. */
	bool bRecordRead = false;

	/** True once the purse has a value from somewhere -- the record, or the first
	 *  board of the day. A reopened board must not refill it. */
	bool bPurseKnown = false;
};
