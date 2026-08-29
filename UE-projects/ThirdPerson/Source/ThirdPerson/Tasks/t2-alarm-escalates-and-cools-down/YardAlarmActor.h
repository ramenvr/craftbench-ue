// Copyright CraftBench. All Rights Reserved.
//
// The panel by the gate for task t2-alarm-escalates-and-cools-down.
//
// IT IS A BOARD OF DIALS AND NOTHING ELSE. It holds no setting, counts nothing, ticks
// not at all, and has never heard of a guard or a floodlight. Every number the yard
// works to is written on it and readable here; the sergeant re-sets some of them when
// the watch changes, so read a dial at the moment you need it rather than once at the
// start.
//
// It deliberately carries no readout of its own. What the yard is doing shows in the
// floodlights that burn and the pace the guards walk, and nowhere else.
//
// ======================= WHAT IS NOT HERE ============================
// Nothing in this yard decides anything. Nobody notices the character, nobody counts
// sightings, nobody forgets them again, nothing moves the setting up or down, and
// nothing throws a floodlight's switch or writes a guard's pace. That is the work.
//
// The yard is fixed -- the guards, the posts, the floodlights and this panel are placed
// in a level you cannot edit -- so whatever does the deciding has to live on a class
// the level already instantiates: this panel, a guard, a floodlight, or the character.
// A brand new class would never be placed and would never run.
// =====================================================================

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardAlarmActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AYardAlarmActor : public AActor
{
	GENERATED_BODY()

public:
	AYardAlarmActor();

	/** The board you can see. NON-COLLIDING: the yard promises there is nothing to
	 *  hide behind. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alarm")
	UStaticMeshComponent* Board = nullptr;

	// --- The dials. Read them at the point of use: the sergeant re-sets some of them
	// --- part way through the night and nothing announces it.

	/** The count at which the panel goes UP from the calmest setting to the middle
	 *  one. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	int32 SightingsToRaiseWatch = 2;

	/** The count at which the panel goes UP from the middle setting to the highest. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	int32 SightingsToRaiseHunt = 5;

	/** The count at which the panel comes DOWN from the highest setting to the middle
	 *  one. Deliberately not the same as the raise number above it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	int32 SightingsToDropWatch = 2;

	/** The count at which the panel comes DOWN from the middle setting to the calmest.
	 *  Deliberately not the same as the raise number above it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	int32 SightingsToDropCalm = 0;

	/** The most sightings the panel will ever remember. Further sightings past this
	 *  add nothing. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	int32 MaxSightingsRemembered = 5;

	/** How many seconds with nobody in sight it takes to forget ONE sighting. It
	 *  forgets another after the same again, and so on. Being seen at all puts that
	 *  clock straight back to zero. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	float QuietSecondsPerStepDown = 5.0f;

	/** What the guards' own base paces are multiplied by at the calmest setting. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	float PatrolScaleWhenCalm = 1.0f;

	/** ...at the middle setting. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	float PatrolScaleWhenWatching = 1.4f;

	/** ...and at the highest. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Alarm|Dials")
	float PatrolScaleWhenHunting = 1.8f;
};
