// Copyright CraftBench. All Rights Reserved.
//
// AGraphMathActor — pre-existing actor for task t1-blueprint-graph-on-beginplay.
// It carries two per-instance editable whole-number values, BaseValue
// (default 7) and BonusValue (default 5), and its constructor stamps the
// "GraphMathRoot" identity tag. No lifecycle overrides are declared and no
// behavior is implemented; the required behavior is specified in the task
// prompt and is the agent's to implement. The two values are per-instance
// data: any placed or spawned instance may carry values different from the
// defaults shown here.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GraphMathActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API AGraphMathActor : public AActor
{
	GENERATED_BODY()

public:
	AGraphMathActor();

	/** Per-instance editable whole-number value; readable from Blueprint graphs. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Task")
	int32 BaseValue = 7;

	/** Per-instance editable whole-number value; readable from Blueprint graphs. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Task")
	int32 BonusValue = 5;
};
