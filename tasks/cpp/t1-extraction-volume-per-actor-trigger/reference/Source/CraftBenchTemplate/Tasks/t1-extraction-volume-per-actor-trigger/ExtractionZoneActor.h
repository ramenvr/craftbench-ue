// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-extraction-volume-per-actor-trigger.

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
	/** Query-only detection volume + scene root. Other actors entering this box
	 *  are the events the zone reacts to. */
	UPROPERTY(VisibleAnywhere)
	UBoxComponent* ZoneVolume;

private:
	/** Every individual already extracted — each triggers exactly once. */
	TSet<TWeakObjectPtr<AActor>> ExtractedIndividuals;
};
