// Copyright CraftBench. All Rights Reserved.

#include "MarketKeeperSubsystem.h"

#include "Kismet/GameplayStatics.h"
#include "MarketDayRecord.h"
#include "MarketLedgerActor.h"
#include "MarketStallActor.h"

namespace
{
	const TCHAR* const kSlotName = TEXT("MarketDay");
	constexpr int32 kUserIndex = 0;
}

void UMarketKeeperSubsystem::LoadRecordOnce()
{
	if (bRecordRead)
	{
		return;
	}
	bRecordRead = true;

	if (!UGameplayStatics::DoesSaveGameExist(kSlotName, kUserIndex))
	{
		return;
	}
	const UMarketDayRecord* const Record =
		Cast<UMarketDayRecord>(UGameplayStatics::LoadGameFromSlot(kSlotName, kUserIndex));
	if (Record == nullptr)
	{
		return;
	}
	Coins = Record->Coins;
	Owned = Record->Owned;
	StockLeft = Record->StockLeft;
	bPurseKnown = true;
}

void UMarketKeeperSubsystem::WriteRecord() const
{
	UMarketDayRecord* const Record = Cast<UMarketDayRecord>(
		UGameplayStatics::CreateSaveGameObject(UMarketDayRecord::StaticClass()));
	if (Record == nullptr)
	{
		return;
	}
	Record->Coins = Coins;
	Record->Owned = Owned;
	Record->StockLeft = StockLeft;
	UGameplayStatics::SaveGameToSlot(Record, kSlotName, kUserIndex);
}

void UMarketKeeperSubsystem::AttachBoard(AMarketLedgerActor* InBoard)
{
	if (InBoard == nullptr)
	{
		return;
	}
	LoadRecordOnce();
	Board = InBoard;
	CarryLimit = InBoard->CarryLimit;
	if (!bPurseKnown)
	{
		// The FIRST board of the day says how much the purse starts with. A board that
		// comes back after the yard reopens says nothing about it -- the purse has
		// been spent from since.
		Coins = InBoard->StartingCoins;
		bPurseKnown = true;
	}
	// The stalls may have begun play before the board did, in which case they painted
	// their signs before the carry limit was known. Repaint everything now.
	RefreshEverything();
	WriteRecord();
}

void UMarketKeeperSubsystem::AttachStall(AMarketStallActor* Stall)
{
	if (Stall == nullptr)
	{
		return;
	}
	LoadRecordOnce();
	Stalls.AddUnique(Stall);

	if (const int32* const Kept = StockLeft.Find(Stall->GoodsName))
	{
		// THE RECONCILIATION. This stall has been here before, so what it holds now is
		// what it had left, plus what it was delivered, capped at what it can hold --
		// NOT what it arrived holding, and NOT what it had left. Both of those are one
		// term short.
		Stall->StockCount =
			FMath::Clamp(*Kept + Stall->DeliveredSinceClose, 0, Stall->StockCapacity);
	}
	// Whatever it holds now is what the record says it holds. On the first open that
	// is simply what it arrived with.
	StockLeft.Add(Stall->GoodsName, Stall->StockCount);

	RefreshStall(Stall);
	WriteRecord();
}

void UMarketKeeperSubsystem::DetachStall(AMarketStallActor* Stall)
{
	Stalls.Remove(Stall);
}

void UMarketKeeperSubsystem::TryBuy(AMarketStallActor* Stall)
{
	if (Stall == nullptr)
	{
		return;
	}
	const FName Goods = Stall->GoodsName;
	const int32 Price = Stall->PriceCoins;

	// EVERY test first, and only then the first change. A refusal that has already
	// taken the coins is the whole bug this shape exists to avoid, so there is nothing
	// below this point that a refusal could reach.
	if (Coins < Price)
	{
		return;                                  // cannot pay
	}
	if (Stall->StockCount < 1)
	{
		return;                                  // this stall has none left
	}
	if (Owned.FindRef(Goods) >= CarryLimit)
	{
		return;                                  // already carrying a full load of it
	}

	Coins -= Price;
	Stall->StockCount -= 1;
	Owned.FindOrAdd(Goods) += 1;
	StockLeft.Add(Goods, Stall->StockCount);

	WriteRecord();
	RefreshStall(Stall);
	RefreshBoard();
}

void UMarketKeeperSubsystem::RefreshBoard() const
{
	if (AMarketLedgerActor* const B = Board.Get())
	{
		B->ShowCoins(Coins);
	}
}

void UMarketKeeperSubsystem::RefreshStall(AMarketStallActor* Stall) const
{
	if (Stall != nullptr)
	{
		// The price shown is the price the stall is asking NOW, straight off the
		// stall. Nothing here ever writes a price.
		Stall->ShowSign(Stall->PriceCoins, Stall->StockCount,
			Owned.FindRef(Stall->GoodsName));
	}
}

void UMarketKeeperSubsystem::RefreshEverything() const
{
	RefreshBoard();
	for (const TWeakObjectPtr<AMarketStallActor>& Weak : Stalls)
	{
		RefreshStall(Weak.Get());
	}
}
