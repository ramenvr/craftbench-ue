// Reference solution for task gp-harvestable-regrow (the g2-3 "Harvestable" port).
// Keeps the substrate constructor (tick enabled, the USphereComponent overlap
// root, and the HarvestableRoot tag the verifier resolves the host by) and adds
// the agent's responsibility: an active/regrowing state machine driven by overlap.
//   - BeginPlay starts the actor active and binds the sphere's begin-overlap event;
//   - on overlap while active: log a message, switch to regrowing (add the
//     "Regrowing" tag), and arm a 5-second one-shot timer;
//   - while regrowing the overlap handler does nothing (no re-harvest, no timer
//     restart);
//   - the timer callback returns the actor to active (remove the "Regrowing" tag).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HarvestableActor.generated.h"

class USphereComponent;
class UPrimitiveComponent;

UENUM()
enum class EHarvestableState : uint8
{
	Active,
	Regrowing
};

UCLASS()
class CRAFTBENCHTEMPLATE_API AHarvestableActor : public AActor
{
	GENERATED_BODY()

public:
	AHarvestableActor();

	virtual void BeginPlay() override;

protected:
	UPROPERTY(VisibleAnywhere)
	USphereComponent* CollisionSphere;

private:
	UFUNCTION()
	void OnSphereBeginOverlap(
		UPrimitiveComponent* OverlappedComponent,
		AActor* OtherActor,
		UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex,
		bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void OnRegrowComplete();

	EHarvestableState State = EHarvestableState::Active;
	FTimerHandle RegrowTimerHandle;

	static constexpr float RegrowSeconds = 5.0f;
};
