// Copyright CraftBench. All Rights Reserved.
//
// A hand for task t2-the-crew-arrives-and-thins-out.
//
// SUPPLIED AND WORKING. It has a body anyone can see and a badge over its head that
// anyone can read, and the badge can be written on. That is all it does: it has never
// heard of a board, a standing spot, a plate or a lamp, it does not move, and nothing
// brings it aboard or sends it ashore.
//
// A hand blocks nothing on any channel -- somebody walking the deck cannot shove one
// off its spot, and one cannot shove them.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CrewHandActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ACrewHandActor : public AActor
{
	GENERATED_BODY()

public:
	ACrewHandActor();

	/** The body you can see. NON-COLLIDING on every channel. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hand")
	UStaticMeshComponent* Body = nullptr;

	/** The head, so which way a hand faces reads at a glance. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hand")
	UStaticMeshComponent* Head = nullptr;

	/** The number over this hand's head. This IS the badge -- there is no second,
	 *  private copy of it anywhere. What is written here is what the hand is
	 *  wearing. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hand")
	UTextRenderComponent* Badge = nullptr;

	/** Write a number on this hand's badge, where anyone can read it. */
	UFUNCTION(BlueprintCallable, Category = "Hand")
	void SetBadgeCode(int32 NewCode);

	/** Read back whatever is written on the badge. Zero means the badge is blank. */
	UFUNCTION(BlueprintPure, Category = "Hand")
	int32 GetBadgeCode() const;
};
