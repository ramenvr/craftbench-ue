// Copyright CraftBench. All Rights Reserved.
//
// A square pad set flush into the floor.
//
// As shipped it is inert: the region above the plate notices anything that
// enters or leaves it, and nothing in the project does anything about that.
// Making a character that walks onto the pad get thrown upward is the work.
//
// The pad you are graded on is the instance already placed in the level. You
// may extend this class, subclass it, or put your behaviour anywhere else under
// Source/ThirdPerson/ — the plate and the region are yours to resize or
// re-shape if your answer needs it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ContactPadActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AContactPadActor : public AActor
{
	GENERATED_BODY()

public:
	AContactPadActor();

	/** The visible plate, flush with the floor. 400 x 400 x 20 cm. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	TObjectPtr<UStaticMeshComponent> Plate;

	/** The region standing on the plate. 400 x 400 x 500 cm. It notices
	 *  anything entering or leaving it and does not block anything walking
	 *  through. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	TObjectPtr<UBoxComponent> Region;
};
