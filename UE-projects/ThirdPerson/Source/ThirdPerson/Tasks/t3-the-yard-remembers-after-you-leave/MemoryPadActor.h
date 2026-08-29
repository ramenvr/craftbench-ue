// Copyright CraftBench. All Rights Reserved.
//
// A pad for task t3-the-yard-remembers-after-you-leave. Everything the pad needs to LIE
// in the floor, to say WHICH pad it is, to notice somebody standing on it, and to burn
// or not burn its lamp is supplied and working: the plate, the number painted on it,
// the volume that notices, the lamp, and the one call that throws the lamp. Nothing
// here decides which pad's lamp should be burning.
//
// The yard holds several of these. Each carries its own name and its own place in the
// order -- first, second, third -- and the yard moves them around whenever it opens, so
// where a pad is standing says nothing about which pad it is.
//
// The volume is a trigger with NO handler bound. It is set up the way every other
// trigger in this substrate is set up (query-only + overlap-everything + overlap events
// on); what is missing is anything listening to it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MemoryPadActor.generated.h"

class UBoxComponent;
class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AMemoryPadActor : public AActor
{
	GENERATED_BODY()

public:
	AMemoryPadActor();

	/** The painted square a person stands on, 300 x 300, lying in the floor.
	 *  Non-colliding: it is paint, not a step. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UStaticMeshComponent* Plate = nullptr;

	/** The volume that notices somebody standing on the pad: 300 x 300 in plan and 220
	 *  tall, sitting on the floor, so a walking character's capsule (centre 96 above
	 *  the floor) is well inside it. Overlap-only, overlap events ON, NOTHING BOUND TO
	 *  IT. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UBoxComponent* Step = nullptr;

	/** The little mast at the corner of the pad that carries the lamp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UStaticMeshComponent* LampPost = nullptr;

	/** The lamp head a person sees: bright when the lamp is burning, dull when it is
	 *  not. Written only by ShowLamp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UStaticMeshComponent* LampGlow = nullptr;

	/** The light the lamp actually throws. Written only by ShowLamp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UPointLightComponent* Lamp = nullptr;

	/** Which pad this is, written on the pad itself, so a person can see which one is
	 *  the first. Supplied; nobody else writes it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	UTextRenderComponent* PadSign = nullptr;

	/** Which yard this pad belongs to. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pad")
	FName YardName = NAME_None;

	/** What this pad is called. A pad is known by this and by nothing else -- not by
	 *  where it lies, not by what order it is found in. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pad")
	FName PadId = NAME_None;

	/** Where this pad comes in the yard's order: 1 is the first pad, 2 the second, and
	 *  so on. It is painted on the pad. The yard moves the pads about, so this is the
	 *  only thing that says which one is first. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pad")
	int32 PadOrder = 0;

	/** THE SWITCH. Lights this pad's lamp or puts it out, and writes the mirror below
	 *  in the same breath. */
	UFUNCTION(BlueprintCallable, Category = "Pad")
	void ShowLamp(bool bLit);

	/** Whether this pad's lamp is currently shown as burning. Written ONLY by
	 *  ShowLamp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	bool bLastShownLit = false;

protected:
	virtual void BeginPlay() override;

private:
	/** The two looks the lamp head takes. Swapped wholesale rather than driven by a
	 *  material parameter: not every prototype material in this substrate carries a
	 *  colour parameter, and a set that silently does nothing leaves the state
	 *  invisible while looking like it worked. */
	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;
};
