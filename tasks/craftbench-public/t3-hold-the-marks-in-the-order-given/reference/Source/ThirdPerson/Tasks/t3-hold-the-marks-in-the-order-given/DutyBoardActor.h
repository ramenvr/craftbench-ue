// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION -- the duty board on the hall wall, for task
// t3-hold-the-marks-in-the-order-given.
//
// The board is the one thing in the hall that can see the whole round, so the deciding
// lives here. Two things are woven together and neither works alone:
//
//   A. PER-MARK TIME BANKING. A mark banks game-time second for second while the
//      character stands inside its own ring, keeps that value when they step off,
//      carries on from it when they step back on, and is finished the moment its bank
//      reaches ITS OWN number as that number reads AT THAT MOMENT.
//
//   B. THE ORDER, READ LIVE OFF THIS BOARD. Only the mark whose turn it is banks
//      anything; a step onto any other LISTED mark starts the whole round over there
//      and then; a mark the list does not name is inert; and replacing the list starts
//      the round over with a new length.
//
// B GATES A and A FEEDS B: a mark may bank only while it is the current one, and a
// mark finishing is what moves the turn on and moves the tally.
//
// NOTHING IS CACHED THAT CAN CHANGE. The list, its length and every mark's number of
// seconds are read at the moment they are used, every frame -- the hall re-writes all
// of them part way through the night, one of them while somebody is standing on it.
// The only thing resolved once is the SET OF ACTORS, because the hall is fixed.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DutyBoardActor.generated.h"

class AFloorMarkActor;
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
	 *  below in the same breath. */
	UFUNCTION(BlueprintCallable, Category = "Board")
	void ShowTally(int32 FinishedCount, int32 ListLength);

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
	/** What the order face was last painted from. */
	TArray<FName> PaintedOrder;

	/** Every mark in the hall, resolved ONCE by tag -- the hall is fixed, nothing is
	 *  spawned or destroyed. Every NUMBER on them is read live, every frame, because
	 *  that is what changes. */
	UPROPERTY()
	TArray<AFloorMarkActor*> Marks;

	/** The list the board was carrying last frame. The moment it stops matching what
	 *  the board reads NOW, the round starts over. */
	TArray<FName> LastSeenList;

	/** Banked seconds, by mark name, for the current attempt. A name the list does not
	 *  carry never gets an entry -- that is what "an unnamed mark banks nothing"
	 *  means. */
	TMap<FName, float> Banked;

	/** How many of the list's names are finished. It is also the index of the name
	 *  whose turn it is, which is why one number carries both. */
	int32 TurnIndex = 0;

	/** The mark somebody stepped onto out of turn, for as long as they stay standing
	 *  on it: it banks nothing however long they stand there. Cleared the moment they
	 *  step off it. */
	TWeakObjectPtr<AFloorMarkActor> PoisonedMark;

	/** Which mark the character was inside last frame, so a STEP ONTO can be told from
	 *  a stand. The whole out-of-turn rule turns on that difference. */
	TWeakObjectPtr<AFloorMarkActor> OccupiedLastFrame;

	/** The mark whose ring the character is inside, or null. The hall keeps its marks
	 *  at least 500 cm apart against a 150 cm ring, so there is never more than one. */
	AFloorMarkActor* MarkUnderCharacter() const;

	/** Where a name sits in the list the board is carrying now, or INDEX_NONE. */
	int32 IndexInList(FName Name) const;

	/** The mark carrying a name, or null. */
	AFloorMarkActor* MarkNamed(FName Name) const;

	/** Empties every bank and puts the turn back on the first name. */
	void StartRoundOver();

	/** Writes every face, every lamp and the tally from the state above. Called every
	 *  frame: nothing the hall shows is ever allowed to be stale. */
	void PaintHall();
};
