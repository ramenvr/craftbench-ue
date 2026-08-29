// Copyright CraftBench. All Rights Reserved.
//
// A lamp on a gate's frame, for task t3-gate-and-door-cpp.
//
// Supplied and working: the switch. Throw it and the lamp burns; throw it back and it
// goes dark. It starts dark and it stays dark until something throws it, and nothing
// in the yard ever does.
//
// NameSlot says which of the two names written on the gate this lamp stands for --
// 0 for the first, 1 for the second. It stands for the SLOT, not for any particular
// name: what is written in that slot is the gate's business and it does not stay the
// same all shift. LampBarrier says which gate this lamp is bolted to. Both are set as
// the yard is laid out and neither is the lamp's to change.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GateLampActor.generated.h"

class UMaterialInterface;
class USceneComponent;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AGateLampActor : public AActor
{
	GENERATED_BODY()

public:
	AGateLampActor();

	virtual void BeginPlay() override;

	/** Root, at the lamp's mounting point. Everything else hangs off it unscaled. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	USceneComponent* Mount = nullptr;

	/** The bracket the lamp hangs from. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UStaticMeshComponent* Bracket = nullptr;

	/** The bulb. Swells and changes colour while the lamp burns. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UStaticMeshComponent* Bulb = nullptr;

	/** The light itself. This is what "lit" means. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UPointLightComponent* Light = nullptr;

	/** Prints which of the gate's two slots this lamp stands for. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UTextRenderComponent* SlotPlate = nullptr;

	/** 0 for the first of the two names written on the gate, 1 for the second. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lamp")
	int32 NameSlot = 0;

	/** The gate this lamp is bolted to. Set on each placed lamp. */
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Lamp")
	AActor* LampBarrier = nullptr;

	/** How brightly the lamp burns when it is lit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lamp")
	float LitIntensity = 12000.0f;

	/** What the bulb is faced with while the lamp burns, and while it is dark.
	 *  Resolved once, when the lamp is built. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lamp")
	UMaterialInterface* DarkLook = nullptr;

	/** THE SWITCH. */
	UFUNCTION(BlueprintCallable, Category = "Lamp")
	void SetLit(bool bLit);

	/** Is this lamp burning right now. Read off the light, never off a flag. */
	UFUNCTION(BlueprintPure, Category = "Lamp")
	bool IsLit() const;
};
