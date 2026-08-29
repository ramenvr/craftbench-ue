// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "log-on-beginplay" for task
// t1-extraction-volume-per-actor-trigger: emits the marker unconditionally at
// BeginPlay, never on entry. Models anti-gaming note #1 — must FAIL at
// checkpoint 0 ("NOT be logged before any entry").

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ExtractionZoneActor.generated.h"

class UBoxComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AExtractionZoneActor : public AActor
{
	GENERATED_BODY()

public:
	AExtractionZoneActor();

protected:
	virtual void BeginPlay() override;

	/** Query-only detection volume + scene root. */
	UPROPERTY(VisibleAnywhere)
	UBoxComponent* ZoneVolume;
};
