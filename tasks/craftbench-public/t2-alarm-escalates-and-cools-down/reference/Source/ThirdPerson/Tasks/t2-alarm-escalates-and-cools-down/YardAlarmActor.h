// Copyright CraftBench. All Rights Reserved.
//
// The panel by the gate for task t2-alarm-escalates-and-cools-down.
//
// REFERENCE SOLUTION. The supplied board is a rack of dials with no behaviour at all;
// everything below the dials is the answer. The panel is the host because the yard is
// fixed -- every guard, post, floodlight and this board are placed in a level that is
// not writable -- so a brand new class would never be instantiated.
//
// The dials are read at the point of use, never cached: the sergeant re-sets two of
// them when the watch changes and nothing announces it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardAlarmActor.generated.h"

class AWatchGuardActor;
class AYardLampActor;
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

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** How far this guard can see RIGHT NOW: its own reach plus every burning
	 *  floodlight that throws light down the round it is walking. Read live -- both
	 *  which guard walks which round and which floodlights burn change during the
	 *  night. */
	double EffectiveReachOf(const AWatchGuardActor* Guard) const;

	/** Can this guard see the character at this instant? Flat (the yard is level),
	 *  from the guard's own position to the character's, against the guard's OWN two
	 *  numbers. Inclusive at both edges. */
	bool CanSee(const AWatchGuardActor* Guard, const FVector& Target) const;

	/** The multiplier the panel currently reads for a setting. */
	float ScaleFor(int32 InStage) const;

	/** The yard's setting: 0 calm, 1 watching, 2 hunting. A REMEMBERED state, not a
	 *  function of the count -- the raise numbers and the drop numbers are different,
	 *  and inside the gap between them the setting is whatever it already was. */
	int32 Stage = 0;

	/** Sightings remembered, clamped at the panel's own cap. */
	int32 Sightings = 0;

	/** True while anybody could see the character. A sighting is the FALSE->TRUE edge
	 *  of this, not a length of time. */
	bool bSeenLastFrame = false;

	/** Seconds since anybody last had the character in view. Reset to zero the moment
	 *  anybody does. */
	double QuietFor = 0.0;

	/** Resolved once: the placed cast never changes, only its numbers do. */
	UPROPERTY()
	TArray<AWatchGuardActor*> Guards;

	UPROPERTY()
	TArray<AYardLampActor*> Lamps;
};
