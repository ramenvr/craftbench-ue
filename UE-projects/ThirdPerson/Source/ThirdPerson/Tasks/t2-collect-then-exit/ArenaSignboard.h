// Copyright CraftBench. All Rights Reserved.
//
// The board beside the exit for task t2-collect-then-exit. Both faces ship BLANK:
// nothing writes to either of them yet.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ArenaSignboard.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AArenaSignboard : public AActor
{
	GENERATED_BODY()

public:
	AArenaSignboard();

	/** Unscaled root. The board mesh is scaled; the text is NOT attached to it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	USceneComponent* BoardRoot = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UStaticMeshComponent* BoardMesh = nullptr;

	/** The face that shows how many relics have been gathered, out of three. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UTextRenderComponent* TallyText = nullptr;

	/** The face that shows the run's status word. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UTextRenderComponent* StatusText = nullptr;
};
