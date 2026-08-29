// Copyright CraftBench. All Rights Reserved.
//
// AExtractionZoneActor — pre-existing actor for task
// t1-extraction-volume-per-actor-trigger. The constructor creates a query-only
// UBoxComponent detection volume as the root (so other actors entering the zone
// can be detected) and stamps the "ExtractionZone" identity tag. No overlap
// handling, bookkeeping, or logging is provided; the required behavior is
// specified in the task prompt and is the agent's to implement. Agents may
// subclass or rename freely.

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
	/** Query-only detection volume + scene root. Other actors entering this box
	 *  are the events the zone reacts to. */
	UPROPERTY(VisibleAnywhere)
	UBoxComponent* ZoneVolume;
};
