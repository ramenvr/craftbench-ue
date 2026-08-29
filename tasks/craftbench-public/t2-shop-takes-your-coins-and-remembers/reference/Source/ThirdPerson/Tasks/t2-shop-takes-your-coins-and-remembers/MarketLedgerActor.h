// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION. Against the scaffold this file adds one thing: the board tells
// the keeper it exists. It still holds no purse -- it is a display, and the purse is on
// something that outlives it.

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
