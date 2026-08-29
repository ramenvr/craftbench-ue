// Copyright CraftBench. All Rights Reserved.
//
// A coin lying in the arena for task t2-race-clock-cpp. It arrives
// visible, with a contact region and its own point value, and nothing else:
// walking into one does not yet do anything.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RaceCoinBase.generated.h"

class USphereComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ARaceCoinBase : public AActor
{
	GENERATED_BODY()

public:
	ARaceCoinBase();

	/** The contact region: 60 cm, query-only, overlap events on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Coin")
	USphereComponent* CoinRegion = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Coin")
	UStaticMeshComponent* CoinMesh = nullptr;

	/** What this coin is worth. Authored per placed instance; read it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Coin")
	int32 PointValue = 0;
};
