// Copyright CraftBench. All Rights Reserved.
//
// A market stall for task t2-shop-takes-your-coins-and-remembers. Everything the stall
// needs to STAND THERE and to SHOW what it is asking is supplied and working: the
// counter, the mat in front of it, the sign above it, and the one call that writes the
// sign. Nothing here decides that a sale has happened, what it costs, what changes, or
// what should be remembered.
//
// The yard holds three of these and they are not alike: each sells a different kind of
// goods and each carries its own price, its own stock, its own capacity, and its own
// delivery. Read those off the stall you are dealing with -- one number does not fit
// three stalls, and the market resets the prices when the yard reopens.
//
// The mat is a trigger volume with NO handler bound. It is set up the way every other
// trigger in this substrate is set up (QueryOnly + overlap-everything + overlap events
// on); what is missing is anything listening to it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MarketStallActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AMarketStallActor : public AActor
{
	GENERATED_BODY()

public:
	AMarketStallActor();

	/** The counter you can see, and the root. Solid -- you walk round it, not through
	 *  it. MOVABLE on purpose: the yard tears the stalls down and puts fresh ones back
	 *  part way through the day, and PIE scores moving a STATIC actor as a failed
	 *  test (the same lesson the crate task's spec records). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	UStaticMeshComponent* Counter = nullptr;

	/** The mat in front of the counter: 240 x 240 in plan and 220 tall, sitting on the
	 *  floor, so a walking character's capsule (centre 96 above the floor) is well
	 *  inside it. Overlap-only, overlap events ON, NOTHING BOUND TO IT. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	UBoxComponent* Mat = nullptr;

	/** The painted square a person actually sees underfoot, exactly the mat's 240 x 240
	 *  footprint. Non-colliding: it is paint, not a step. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	UStaticMeshComponent* MatPlate = nullptr;

	/** The sign above the counter. Written only by ShowSign. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	UTextRenderComponent* Sign = nullptr;

	/** What this stall sells. A stall is known by this and by nothing else -- not by
	 *  where it stands, not by what order it is found in. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stall")
	FName GoodsName = NAME_None;

	/** What one of this stall's goods costs, NOW. The market resets it when the yard
	 *  reopens; it is never yours to write. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 PriceCoins = 0;

	/** How many this stall still has. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 StockCount = 0;

	/** The most this stall can ever hold. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 StockCapacity = 0;

	/** How many of its goods were delivered to this stall while the yard was shut.
	 *  Zero on a stall that has not been away. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 DeliveredSinceClose = 0;

	/** THE DISPLAY. Writes the sign and, in the same breath, the three reflected
	 *  mirrors below, so what a reviewer reads off the sign and what a tool reads off
	 *  the actor are the same numbers by construction.
	 *
	 *  The wording is the yard's. Only the numbers are anybody else's business: a sign
	 *  that says something other than
	 *      "<goods>  price <P>  left <S>  yours <O>  came <D>  holds <C>"
	 *  is a sign a person cannot read the same way twice. */
	UFUNCTION(BlueprintCallable, Category = "Stall")
	void ShowSign(int32 Price, int32 Stock, int32 Owned);

	/** What the sign currently reads, split out. Written ONLY by ShowSign. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 LastShownPrice = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 LastShownStock = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stall")
	int32 LastShownOwned = 0;

protected:
	virtual void BeginPlay() override;
};
