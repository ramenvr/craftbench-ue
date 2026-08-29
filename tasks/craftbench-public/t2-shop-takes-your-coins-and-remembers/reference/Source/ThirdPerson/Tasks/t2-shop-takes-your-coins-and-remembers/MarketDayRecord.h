// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION -- what the day is written down in.
//
// Three things and no more: the coins left in the purse, how many of each kind are
// owned, and how many each stall had left when it closed. Keyed by WHAT A STALL SELLS,
// because the stalls come back in a different order along the row and an index would
// hand the rope stall's leftovers to the apple stall.
//
// The price is deliberately NOT here. It is the market's, it is reset while the yard is
// shut, and writing a remembered one back would make the stall lie about what it is
// asking. Serialising "the stall" wholesale is the obvious granularity and it is the
// wrong one.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "MarketDayRecord.generated.h"

UCLASS()
class THIRDPERSON_API UMarketDayRecord : public USaveGame
{
	GENERATED_BODY()

public:
	/** Coins left in the purse. */
	UPROPERTY()
	int32 Coins = 0;

	/** How many of each kind are owned, by goods name. */
	UPROPERTY()
	TMap<FName, int32> Owned;

	/** How many each stall had left, by goods name. */
	UPROPERTY()
	TMap<FName, int32> StockLeft;
};
