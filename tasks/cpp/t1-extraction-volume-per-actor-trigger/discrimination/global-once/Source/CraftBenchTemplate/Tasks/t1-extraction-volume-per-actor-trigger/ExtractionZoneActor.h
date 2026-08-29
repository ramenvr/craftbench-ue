// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "global-once" for task
// t1-extraction-volume-per-actor-trigger: a single global latch — only the
// first individual ever triggers extraction; later distinct individuals are
// ignored. Models anti-gaming note #3 — must FAIL at checkpoint 3 ("after a
// second distinct individual entered").

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

private:
	/** Gamed: one global latch instead of a per-individual record. */
	bool bExtractionTriggered = false;
};
