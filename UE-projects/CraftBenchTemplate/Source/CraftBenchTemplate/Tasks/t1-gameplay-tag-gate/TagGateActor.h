// Copyright CraftBench. All Rights Reserved.
//
// ATagGateActor — pre-existing actor for task t1-gameplay-tag-gate. The
// constructor stamps the "TagGateRoot" identity tag, and the class declares the
// two state-marker accessor functions that external code calls at runtime (by
// name, so keep the function names and signatures as declared). The marker
// storage, the marker query, and the repeating announcement the markers control
// are the agent's to implement. Agents may subclass freely; external code finds
// the actor by its "TagGateRoot" tag, never by class.

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

	/** Adds the given state marker to this actor's marker set. Called by
	 *  external code at runtime; the behavior it controls is specified in the
	 *  task prompt. */
	UFUNCTION()
	void AddGateTag(FGameplayTag Tag);

	/** Removes the given state marker from this actor's marker set. Called by
	 *  external code at runtime. */
	UFUNCTION()
	void RemoveGateTag(FGameplayTag Tag);
};
