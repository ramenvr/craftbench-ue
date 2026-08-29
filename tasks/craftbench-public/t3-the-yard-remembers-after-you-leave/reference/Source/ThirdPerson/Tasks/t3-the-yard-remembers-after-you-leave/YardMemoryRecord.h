// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION -- what the yard is written down in, and the only place the answer
// lives.
//
// Three things and no more: which posts have been taken, how much each yard has banked,
// and which pad each yard's mark is on. Everything else the yard can be asked at the
// time.
//
// TWO GRANULARITY DECISIONS, both of which a first pass gets wrong:
//
//  1. The BANKED TOTAL is stored, not the worths of the taken posts. What a post is
//     worth is repainted every time the yard opens, so a total re-derived from the
//     taken posts' current numbers is a different -- and wrong -- number. The amount is
//     history; the number over the post is news.
//  2. Taken posts are stored by WHAT THEY ARE CALLED, qualified by their yard, never by
//     index, slot or position. The yard moves its posts about and there is more than
//     one yard, so a slot number hands one yard's leftovers to the other.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "YardMemoryRecord.generated.h"

/** Yard-qualified name for one post, so two yards can never share an entry. */
FORCEINLINE FName MakeYardPostKey(FName Yard, FName Post)
{
	return FName(*FString::Printf(TEXT("%s/%s"), *Yard.ToString(), *Post.ToString()));
}

UCLASS()
class THIRDPERSON_API UYardMemoryRecord : public USaveGame
{
	GENERATED_BODY()

public:
	/** Every post that has been taken, as MakeYardPostKey(yard, post). */
	UPROPERTY()
	TSet<FName> TakenPosts;

	/** What each yard has banked, by yard name. The AMOUNTS, not the posts. */
	UPROPERTY()
	TMap<FName, int32> BankedByYard;

	/** The pad each yard's mark is on, by yard name. Absent until somebody has stood
	 *  on one. */
	UPROPERTY()
	TMap<FName, FName> LatestPadByYard;
};
