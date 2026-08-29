// Copyright CraftBench. All Rights Reserved.
//
// The replay pad for task t2-race-clock-cpp. SUPPLIED AND WORKING END TO
// END: stand on it and its lamp lights, step off and it goes out, and it counts its
// own occupants so two figures on one pad do not clear it when the first leaves.
//
// Nothing here knows what a round is. What standing on it should DO is the whole
// question, and nothing answers it yet.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RaceReplayPadActor.generated.h"

class UBoxComponent;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ARaceReplayPadActor : public AActor
{
	GENERATED_BODY()

public:
	ARaceReplayPadActor();

	/** The plate you can see. Flat, and it blocks nothing. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Replay Pad")
	UStaticMeshComponent* Plate = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Replay Pad")
	UBoxComponent* Volume = nullptr;

	/** Lit while somebody is standing on the pad. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Replay Pad")
	UPointLightComponent* Lamp = nullptr;

	/** Whether somebody is standing on it right now. */
	UFUNCTION(BlueprintPure, Category = "Replay Pad")
	bool IsPressed() const { return Occupants > 0; }

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnPadBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void OnPadEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	void RefreshLamp();

	/** Counted, not flagged. */
	int32 Occupants = 0;
};
