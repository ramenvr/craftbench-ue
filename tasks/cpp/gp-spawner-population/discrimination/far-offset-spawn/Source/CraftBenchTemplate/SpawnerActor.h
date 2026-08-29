// Reference solution for task gp-spawner-population (the g2-4 "Spawner" port).
// Keeps the substrate constructor (tick enabled + the SpawnerRoot tag the
// verifier resolves the host by) and adds the agent's responsibility:
//   - BeginPlay spawns a population of N minions at random points within radius;
//   - each minion's OnDestroyed delegate triggers a replacement (respawn);
//   - EndPlay tears down every tracked minion (cleanup), guarded so the teardown
//     does not re-trigger a respawn.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpawnerActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ASpawnerActor : public AActor
{
	GENERATED_BODY()

public:
	ASpawnerActor();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	UFUNCTION()
	void OnMinionDestroyed(AActor* DestroyedActor);

	AActor* SpawnOneMinion();

	UPROPERTY()
	TArray<AActor*> Minions;

	bool bShuttingDown = false;

	static constexpr int32 TargetPopulation = 5;
	static constexpr float SpawnRadius = 500.0f;
};
