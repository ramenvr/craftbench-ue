// Copyright CraftBench. All Rights Reserved.
//
// The carry sign for task t3-forge-turns-what-you-bring-into-what-you-need.
//
// One number, posted where a player walks in: how many units you can have on you at
// once. The post, the notice you can read, and the switch that rewrites it are all
// supplied and working. Nothing here counts anything, nothing here knows where the
// character is, and nothing here decides anything.
//
// THE NUMBER IS THE HALL'S, NOT YOURS. CarryCapUnits is how the hall re-posts the cap
// part way through the run: it is written from outside, by name, while the level is
// playing. Keep it as a property with this name and this type, and read it at the
// moment you pick something up rather than remembering it from when play began.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CarrySignActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ACarrySignActor : public AActor
{
	GENERATED_BODY()

public:
	ACarrySignActor();

	/** The post you can see. Non-colliding: it stands next to where the character
	 *  starts, and a sign you can bump into is a sign that can jam the first step of
	 *  every walk. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sign")
	UStaticMeshComponent* Post = nullptr;

	/** Reads "CARRY AT MOST N" -- the same line a human reads off the sign. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sign")
	UTextRenderComponent* Notice = nullptr;

	/** How many units the character may have on them at once. Read it off the sign:
	 *  the hall re-posts a different number part way through the run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sign")
	int32 CarryCapUnits = 3;

	/** Rewrites the visible notice from CarryCapUnits. Presentation only -- it decides
	 *  nothing. Supplied so the hall's re-post and your own code write the same face. */
	UFUNCTION(BlueprintCallable, Category = "Sign")
	void RefreshNotice();

protected:
	virtual void BeginPlay() override;
};
