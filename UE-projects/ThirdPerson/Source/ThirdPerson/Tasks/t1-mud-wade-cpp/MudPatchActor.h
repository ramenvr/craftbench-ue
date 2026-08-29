// Copyright CraftBench. All Rights Reserved.
//
// The patch of dark wet ground. It blocks nothing -- a figure walks straight onto and
// through it -- and it does nothing to whoever is standing on it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MudPatchActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AMudPatchActor : public AActor
{
	GENERATED_BODY()

public:
	AMudPatchActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mud")
	UStaticMeshComponent* PatchMesh = nullptr;

	/** Query-only volume over the patch. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mud")
	UBoxComponent* PatchVolume = nullptr;
};
