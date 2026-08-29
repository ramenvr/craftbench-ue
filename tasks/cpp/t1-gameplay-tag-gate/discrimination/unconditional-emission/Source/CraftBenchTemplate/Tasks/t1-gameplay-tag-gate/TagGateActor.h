// Copyright CraftBench. All Rights Reserved.
//
// ATagGateActor — reference solution for task t1-gameplay-tag-gate. Keeps the
// scaffold's identity tag, native marker definition, and accessor seam; adds a
// gameplay-tag container as the marker store, a looping 0.5 s timer, and a
// HasTag gate on each fire.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameplayTagContainer.h"
#include "NativeGameplayTags.h"
#include "TagGateActor.generated.h"

/** The state marker named in the task prompt ("CraftBench.TagGate.Active"),
 *  registered natively by this module so it is always resolvable at runtime. */
UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_CraftBench_TagGate_Active);

UCLASS()
class CRAFTBENCHTEMPLATE_API ATagGateActor : public AActor
{
	GENERATED_BODY()

public:
	ATagGateActor();

	/** Adds the given state marker to this actor's marker set. */
	UFUNCTION()
	void AddGateTag(FGameplayTag Tag);

	/** Removes the given state marker from this actor's marker set. */
	UFUNCTION()
	void RemoveGateTag(FGameplayTag Tag);

protected:
	virtual void BeginPlay() override;

private:
	/** Fires every 0.5 s; emits the announcement only while the gate marker is
	 *  present in the marker set (the timer itself never stops — the gate is
	 *  the HasTag query, so remove/re-add reacts within one period). */
	void HandleGateTick();

	/** The actor's marker set. */
	FGameplayTagContainer StateMarkers;

	FTimerHandle GateTickTimer;
};
