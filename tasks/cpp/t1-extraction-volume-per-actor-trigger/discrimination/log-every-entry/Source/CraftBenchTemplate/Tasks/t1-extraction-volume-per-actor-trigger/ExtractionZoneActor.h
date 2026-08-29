// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "log-every-entry" for task
// t1-extraction-volume-per-actor-trigger: logs on EVERY begin-overlap with no
// per-individual dedupe. Models anti-gaming note #2 — must FAIL at
// checkpoint 2 ("re-entering to add no new emission").

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

	virtual void NotifyActorBeginOverlap(AActor* OtherActor) override;

protected:
	/** Query-only detection volume + scene root. */
	UPROPERTY(VisibleAnywhere)
	UBoxComponent* ZoneVolume;
};
