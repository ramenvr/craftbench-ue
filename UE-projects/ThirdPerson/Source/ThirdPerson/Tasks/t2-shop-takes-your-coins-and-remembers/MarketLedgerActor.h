// Copyright CraftBench. All Rights Reserved.
//
// The board by the gate, for task t2-shop-takes-your-coins-and-remembers. It says how
// many coins you start the day with and the most of any one kind of goods you are able
// to carry, and it has one call that writes it. It holds no purse, it counts nothing,
// and it has never heard of a stall.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MarketLedgerActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AMarketLedgerActor : public AActor
{
	GENERATED_BODY()

public:
	AMarketLedgerActor();

	/** The post the board is nailed to, and the root. MOVABLE for the same reason the
	 *  stalls are: the yard takes the board away and puts a fresh one back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ledger")
	UStaticMeshComponent* Post = nullptr;

	/** The board itself. Written only by ShowCoins. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ledger")
	UTextRenderComponent* CoinsBoard = nullptr;

	/** How many coins the day starts with. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ledger")
	int32 StartingCoins = 0;

	/** The most of ANY ONE KIND of goods a person can carry. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ledger")
	int32 CarryLimit = 0;

	/** THE DISPLAY. Writes the board and the mirror below in the same breath. The
	 *  wording is the yard's -- "coins <N>  carry <K>" -- and only <N> is anybody
	 *  else's business; <K> is the board's own number. */
	UFUNCTION(BlueprintCallable, Category = "Ledger")
	void ShowCoins(int32 Coins);

	/** What the board currently reads. Written ONLY by ShowCoins. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ledger")
	int32 LastShownCoins = 0;

protected:
	virtual void BeginPlay() override;
};
