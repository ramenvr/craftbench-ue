// Copyright CraftBench. All Rights Reserved.
//
// The exit at the far end of the arena for task t2-collect-then-exit. It arrives
// sealed: the lamp is dark, and walking into it does not yet do anything.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ExitGate.generated.h"

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
};
