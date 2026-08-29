// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-glide-stamina-cpp. A character subclass that
// grants the glide ability, starts with Power to spend, and wears the
// template's mannequin body (the checkpoint-0 visible-character gate,
// 2026-08-06).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "GlidePawn.generated.h"

UCLASS()
class AGlidePawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	AGlidePawn();

protected:
	virtual void BeginPlay() override;
};
