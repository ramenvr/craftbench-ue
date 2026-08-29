// Copyright CraftBench. All Rights Reserved.
//
// A watch guard in the yard for task t1-guard-only-spots-what-it-can-see. Everything
// it needs to SHOW that it has spotted somebody is supplied and working: the lamp, the
// bulb, the eye point it would look from, and the switch that turns the lamp red or
// dark. Nothing decides when to throw that switch.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SightGuardActor.generated.h"

class UMaterialInstanceDynamic;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ASightGuardActor : public AActor
{
	GENERATED_BODY()

public:
	ASightGuardActor();

	/** The guard you can see. Solid: it is a prop, and it blocks. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Body = nullptr;

	/** The sanctioned sight origin, in FRONT of the body so a line drawn from it
	 *  toward anything never starts inside the guard's own collision. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Eye = nullptr;

	/** Red when the guard has spotted somebody, dark grey when it has not. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UStaticMeshComponent* Bulb = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Guard")
	UPointLightComponent* AlertLamp = nullptr;

	/** How far this guard can see. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Guard")
	float SightRangeUu = 1200.0f;

	/** How far either side of its facing this guard can see. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Guard")
	float SightHalfAngleDeg = 45.0f;

	/** THE SWITCH. Lights the lamp red and brightens the bulb, or puts both out. */
	UFUNCTION(BlueprintCallable, Category = "Guard")
	void SetSpotted(bool bNewSpotted);

	UFUNCTION(BlueprintPure, Category = "Guard")
	bool IsSpotted() const { return bSpotted; }

protected:
	virtual void BeginPlay() override;

private:
	bool bSpotted = false;

	UPROPERTY()
	UMaterialInstanceDynamic* BulbMaterial = nullptr;
};
