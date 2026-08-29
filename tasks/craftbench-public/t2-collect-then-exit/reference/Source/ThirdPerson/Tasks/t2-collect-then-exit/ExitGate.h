// Copyright CraftBench. All Rights Reserved.
//
// The exit at the far end of the arena for task t2-collect-then-exit. It also holds
// the run's objective state: how many relics have been gathered, whether the exit is
// open, and whether the run has been won.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ExitGate.generated.h"

class AArenaSignboard;
class UBoxComponent;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AExitGate : public AActor
{
	GENERATED_BODY()

public:
	AExitGate();

	/** The archway you can see. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Exit")
	UStaticMeshComponent* ExitMesh = nullptr;

	/** Where the character has to be standing to be in the exit. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Exit")
	UBoxComponent* ExitVolume = nullptr;

	/** Dark while the exit is sealed. This is a readout, not decoration. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Exit")
	UPointLightComponent* ExitLamp = nullptr;

	/** Called by a relic the character has just walked into. Counts it once. */
	void NotifyRelicGathered();

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnExitBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

private:
	void RefreshReadouts();

	/** How many relics have been gathered, and the three the exit waits for. */
	int32 Gathered = 0;
	static constexpr int32 RequiredRelics = 3;

	bool bOpen = false;
	bool bWon = false;

	TWeakObjectPtr<AArenaSignboard> Board;
};
