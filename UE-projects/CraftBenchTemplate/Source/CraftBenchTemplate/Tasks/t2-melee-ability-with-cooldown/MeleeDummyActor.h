// Copyright CraftBench. All Rights Reserved.
//
// Scaffold for task t2-melee-ability-with-cooldown: a practice-target actor.
// Placed instances carry the "MeleeDummy" tag and a plain Health value gameplay
// code can read and damage. Ships with no behavior of its own.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MeleeDummyActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AMeleeDummyActor : public AActor
{
	GENERATED_BODY()

public:
	AMeleeDummyActor();

	/** Remaining health. Damage subtracts from this value. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee")
	float Health = 100.f;

protected:
	/** Visible body so the dummy can be seen in-editor/preview. Query-free. */
	UPROPERTY(VisibleAnywhere, Category = "Melee")
	TObjectPtr<UStaticMeshComponent> Body;
};
