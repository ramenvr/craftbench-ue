// Copyright CraftBench. All Rights Reserved.
//
// The duty board on the hall wall, for task t3-hold-the-marks-in-the-order-given.
//
// IT IS A LIST AND A TALLY FACE AND NOTHING ELSE. It holds no progress, decides
// nothing, and it has never heard of anybody walking about. It carries tonight's list
// of names, in order, and it paints that list on its own so that a person standing in
// the hall can read the round. It does NOT paint the tally: the tally face ships blank
// and only ShowTally ever writes it.
//
// THE LIST IS NOT FIXED FOR THE NIGHT. It can be replaced at any time -- a different
// order, a different set of names, a different NUMBER of names -- and nothing announces
// it. Read the list at the moment you need it; a list read once and kept will be wrong
// before the night is out.
//
// ======================= WHAT IS NOT HERE ============================
// Nothing in this hall decides anything. Nobody notices where the character is
// standing, nothing banks a second, nothing works out whose turn it is, nothing starts
// a round over, and nothing writes a mark's face, throws a mark's lamp or writes this
// board's tally. That is the work.
//
// The hall is fixed -- the marks and this board are placed in a level you cannot edit
// -- so whatever does the deciding has to live on a class the level already
// instantiates: a mark, this board, or the character. A brand new actor class would
// never be placed and would never run.
// =====================================================================

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DutyBoardActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ADutyBoardActor : public AActor
{
	GENERATED_BODY()

public:
	ADutyBoardActor();

	/** An un-scaled anchor, so sizing one part of the board cannot re-size another. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	USceneComponent* Anchor = nullptr;

	/** The board you can see. Non-colliding. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UStaticMeshComponent* Panel = nullptr;

	/** TONIGHT'S LIST, IN ORDER, by mark name. The first name is the first mark of the
	 *  round. It can be replaced at any time; nothing announces it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board")
	TArray<FName> ListedMarkNames;

	/** The board paints its own list here so a person can read the round. It follows
	 *  ListedMarkNames by itself and it is NOT the tally. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UTextRenderComponent* OrderFace = nullptr;

	/** THE TALLY FACE. Blank from the first frame. Written only by ShowTally. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UTextRenderComponent* TallyFace = nullptr;

	/** THE TALLY. Writes the two numbers a person reads off the board and mirrors them
	 *  below in the same breath -- so what a reviewer reads and what a tool reads are
	 *  the same numbers by construction.
	 *
	 *  The hall owns the wording. Only the two numbers are anybody else's business. */
	UFUNCTION(BlueprintCallable, Category = "Board")
	void ShowTally(int32 FinishedCount, int32 ListLength);

	// ---------------------------------------------------------------------------
	//  MIRRORS of what the tally face currently reads. WRITTEN ONLY BY ShowTally --
	//  never set these by hand: a mirror that disagrees with the glass is worth
	//  nothing.
	// ---------------------------------------------------------------------------

	/** The left-hand half of what the tally face reads. Negative until it has ever
	 *  been written. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board|Tally")
	int32 LastShownFinished = -1;

	/** The right-hand half of what the tally face reads. Negative until it has ever
	 *  been written. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board|Tally")
	int32 LastShownListLength = -1;

	/** False until somebody has written the tally face at least once. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board|Tally")
	bool bTallyEverWritten = false;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Re-paints the ORDER face from ListedMarkNames. Presentation only: it never
	 *  touches the tally. */
	void RefreshOrderFace();

private:
	/** What the order face was last painted from, so the paint follows a change to the
	 *  list without anybody having to remember to ask. */
	TArray<FName> PaintedOrder;
};
