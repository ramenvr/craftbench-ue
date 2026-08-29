// Copyright CraftBench. All Rights Reserved.
//
// A muster board for task t2-the-crew-arrives-and-thins-out.
//
// IT IS A BOARD OF CHALK AND A ROW OF LAMPS. Everything the deck works to is chalked
// here and readable here; the mate re-chalks some of it between watches and nothing
// announces it, so read a number at the moment you need it rather than once at the
// start. Each lamp has a switch that works. THE BOARD ITSELF THROWS NO SWITCH.
//
// ======================= WHAT IS NOT HERE ============================
// Nothing on this deck decides anything. Nobody notices a plate being stepped on,
// nobody calls for hands, nobody brings one aboard or chooses where it stands,
// nobody writes a badge, nobody lights a lamp and nobody sends anybody ashore.
// That is the work.
//
// The deck is fixed -- the boards, the standing spots and the plates are placed in a
// level you cannot edit -- so whatever does the deciding has to live on a class the
// level already instantiates: a board, a plate, a standing spot, or the character.
// A brand new class would never be placed and would never run.
// =====================================================================

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MusterBoardActor.generated.h"

class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AMusterBoardActor : public AActor
{
	GENERATED_BODY()

public:
	AMusterBoardActor();

	virtual void Tick(float DeltaSeconds) override;

	/** One lamp per standing spot in front of this board. */
	static constexpr int32 NumLamps = 6;

	/** The board you can see. NON-COLLIDING. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UStaticMeshComponent* Face = nullptr;

	/** What is chalked on the board right now, written up where a person watching
	 *  can read it. Presentation only -- it is a copy of the numbers below, not a
	 *  second source of them. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UTextRenderComponent* Chalk = nullptr;

	/** Which board this is. Every standing spot and floor plate on the deck carries
	 *  the name of the board it belongs to, and only matching names go together. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board")
	FName BoardTag = NAME_None;

	// --- THE CHALK. Re-chalked between watches; nothing announces it. Read a number
	// --- at the moment you need it, not once at the start.

	/** How many hands this board calls for when its call plate is stepped on. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board|Chalk")
	int32 HandsToCall = 0;

	/** How long after the plate is stepped on the first hand turns up, and how long
	 *  between each one after that. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board|Chalk")
	float SecondsBetweenArrivals = 2.0f;

	/** This board's roster of badge numbers, in the order they are written. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board|Chalk")
	TArray<int32> RosterCodes;

	/** Who goes ashore at the next stand-down, written as places in the arrival
	 *  order of the watch just called: 1 is the first to have turned up. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board|Chalk")
	TArray<int32> SlatePositions;

	// --- THE LAMPS. Lamp k belongs to standing spot number k in front of this board.
	// --- The row runs from spot number 1 up to GetLampCount(); ask for a spot number
	// --- outside it and nothing happens.

	/** THE SWITCH. Lights one lamp or puts it out. */
	UFUNCTION(BlueprintCallable, Category = "Board")
	void SetLampLit(int32 SpotNumber, bool bNewLit);

	/** Read straight off the lamp itself, so what is burning and what somebody
	 *  believes is burning can never disagree. */
	UFUNCTION(BlueprintPure, Category = "Board")
	bool IsLampLit(int32 SpotNumber) const;

	UFUNCTION(BlueprintPure, Category = "Board")
	int32 GetLampCount() const;

protected:
	virtual void BeginPlay() override;

	/** Copies the chalk onto the board's face so a person watching can read it.
	 *  Presentation only. */
	void RefreshChalkText();

private:
	UPROPERTY()
	TArray<UStaticMeshComponent*> LampBulbs;

	UPROPERTY()
	TArray<UPointLightComponent*> LampGlows;

	/** The two looks a bulb takes. Swapped wholesale rather than driven by a material
	 *  parameter: not every prototype material in this project carries a colour
	 *  parameter, and a set that silently does nothing leaves the state invisible
	 *  while looking like it worked. */
	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;
};
