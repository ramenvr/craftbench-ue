// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t3-checkpoint-restores-the-world.
//
// The yard reports; this decides. Three things it keeps, and the whole task is that
// they have to agree with each other:
//
//   Mark        the pad stood on most recently, and nothing to do with the numbering.
//   Places      where every coin is, in THREE states. "Taken" and "banked" look the
//               same from the outside -- both are a coin that is not on its stand --
//               and only one of them ever comes back.
//   MarkPlaces  the same thing, frozen at the instant the mark was set, together with
//               which doors were open then. Frozen at EVERY mark, not once.
//
// What comes back after a life ends is MarkPlaces intersected with what has happened
// since: a coin the mark remembers on its stand is put back UNLESS it has been over the
// line in the meantime, in which case it is gone for good. CARRIED is then DERIVED from
// the answer rather than restored from the snapshot -- rolling it back to what it read
// when the mark was set would hand back coins that are already progress. BANKED is not
// written at all, ever, by anything in here.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CheckpointDirectorActor.generated.h"

class ABankCounterActor;
class ACheckpointStandActor;
class ACoinPickupActor;
class AHazardStripActor;
class ALatchDoorActor;

UCLASS()
class THIRDPERSON_API ACheckpointDirectorActor : public AActor
{
	GENERATED_BODY()

public:
	ACheckpointDirectorActor();

	/** Somewhere for the piece to stand in the yard. It has no size and no collision. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Director")
	USceneComponent* Root = nullptr;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	/** A pad was stood on. That pad is now the mark, and the yard as it stands right
	 *  now is what a life ending will come back to. */
	UFUNCTION()
	void OnPadStoodOn(ACheckpointStandActor* Stand);

	/** The line was crossed. Whatever was in hand AT THIS INSTANT is progress from now
	 *  on -- which is the only moment that fact is knowable, so it is written down here
	 *  and never recomputed. */
	UFUNCTION()
	void OnCoinsBanked(int32 Amount, int32 NewBanked);

	/** A life ended on hot floor. */
	UFUNCTION()
	void OnLifeEnded(AActor* Victim);

private:
	/** Three places, not two. */
	enum class EPlace : uint8 { OnStand, InHand, OverTheLine };

	void FindTheYard();
	/** Re-reads each coin from the coin itself. Never demotes anything that has been
	 *  over the line: from there a coin is not on a stand and not in a hand. */
	void ReadTheCoins();
	void RememberThisMoment();
	void PutTheYardBack();
	int32 CountInHand() const;

	UPROPERTY() TArray<ACheckpointStandActor*> Stands;
	UPROPERTY() TArray<ALatchDoorActor*> Doors;
	UPROPERTY() TArray<ACoinPickupActor*> Coins;
	UPROPERTY() TArray<AHazardStripActor*> Hazards;
	UPROPERTY() ABankCounterActor* Counter = nullptr;

	/** The pad stood on most recently, and the one that is lit. */
	UPROPERTY() ACheckpointStandActor* Mark = nullptr;

	TArray<EPlace> Places;
	TArray<EPlace> MarkPlaces;
	TArray<bool> MarkDoorOpen;

	/** Where somebody came in from -- the mark before any pad has been stood on. */
	FTransform Entrance;
	bool bHaveEntrance = false;
	bool bRemembered = false;

	/** The respawn lands on the mark pad and the pad announces the stand again. Both
	 *  readings of that have to work, so this suppresses it AND the character is moved
	 *  last, when the yard is already back. */
	bool bPuttingBack = false;
};
