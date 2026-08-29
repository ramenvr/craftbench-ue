// Copyright CraftBench. All Rights Reserved.
//
// A floodlight for task t2-alarm-escalates-and-cools-down. Everything it needs to SHOW
// that the yard has changed its mind is supplied and working: a body, a light, and the
// switch that throws it. Nothing decides when to throw that switch.
//
// Every floodlight carries the setting it burns from, and some of them also throw
// light down a round -- which is what lets a guard walking that round see further while
// the floodlight is burning. Both numbers are read off THIS floodlight; the six in the
// yard are not set alike and they are not in any tidy order.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardLampActor.generated.h"

class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AYardLampActor : public AActor
{
	GENERATED_BODY()

public:
	AYardLampActor();

	/** The floodlight housing you can see. NON-COLLIDING: the yard promises there is
	 *  nothing to hide behind. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UStaticMeshComponent* Body = nullptr;

	/** Dark when the yard is calmer than this floodlight's own setting, burning
	 *  otherwise. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UPointLightComponent* Glow = nullptr;

	/** The setting THIS floodlight burns from: it is lit while the panel is at this
	 *  setting or higher, and dark otherwise. 0 is the calmest setting. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lamp")
	int32 LitFromStage = 1;

	/** How much further a guard walking the round below can see while this floodlight
	 *  is burning. Zero on a floodlight that lights nothing but itself. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lamp")
	float ReachBonusUu = 0.0f;

	/** Which round this floodlight throws its light down. Only a guard whose own
	 *  RoundTag matches gains ReachBonusUu from it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lamp")
	FName CoversRoundTag = NAME_None;

	/** THE SWITCH. Lights the floodlight or puts it out. */
	UFUNCTION(BlueprintCallable, Category = "Lamp")
	void SetLit(bool bNewLit);

	UFUNCTION(BlueprintPure, Category = "Lamp")
	bool IsLit() const { return bLit; }

protected:
	virtual void BeginPlay() override;

private:
	bool bLit = false;

	/** The two looks the housing takes. Swapped wholesale rather than driven by a
	 *  material parameter: not every prototype material in this substrate carries a
	 *  colour parameter, and a set that silently does nothing leaves the state
	 *  invisible while looking like it worked. */
	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;
};
