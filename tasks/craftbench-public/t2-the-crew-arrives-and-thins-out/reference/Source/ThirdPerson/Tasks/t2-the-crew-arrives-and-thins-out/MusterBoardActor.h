// Copyright CraftBench. All Rights Reserved.
//
// A muster board for task t2-the-crew-arrives-and-thins-out.
//
// REFERENCE SOLUTION. The supplied board is chalk plus a row of lamps with no
// behaviour at all; everything below the chalk is the answer. The board is the host
// because the deck is fixed -- every board, standing spot and plate is placed in a
// level that is not writable -- so a brand new class would never be instantiated.
//
// THREE THINGS THIS FILE IS CAREFUL ABOUT, because each of them is a way to be wrong
// while looking right:
//
//   1. Every chalked number is read AT THE POINT OF USE, never cached. The mate
//      re-chalks the board between watches and nothing announces it.
//   2. The stand-down slate names PLACES IN THE ARRIVAL ORDER of the watch just
//      called, not standing-spot numbers, and every place is resolved to a body
//      BEFORE anybody is sent ashore -- removing as you walk the list shifts the
//      places under the loop.
//   3. A roster number is spent once for the whole night. The roster is re-chalked
//      longer between watches, so the next number is the first one on it that has
//      not been issued yet -- not the first one on the list.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MusterBoardActor.generated.h"

class ACrewBerthActor;
class ACrewHandActor;
class ACrewPlateActor;
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
	// ---- the answer ----

	/** Start a watch. HandsToCall is read HERE and only here: the prompt pins it to
	 *  the moment the plate is stepped on. */
	void BeginCall(double NowSeconds);

	/** Bring one hand aboard onto the lowest-numbered free spot, wearing the next
	 *  unspent roster number. False when there is nobody to bring or nowhere to put
	 *  them, which ends the call. */
	bool BringOneAboard();

	/** Send ashore the arrival places the slate names, for the watch just called. */
	void StandWatchDown();

	void SendAshore(ACrewHandActor* Hand);

	ACrewBerthActor* LowestFreeBerth() const;

	int32 NextUnspentCode() const;

	void PruneDeparted();

	void RefreshLamps();

	UPROPERTY()
	TArray<ACrewBerthActor*> MyBerths;

	UPROPERTY()
	ACrewPlateActor* CallPlate = nullptr;

	UPROPERTY()
	ACrewPlateActor* StandDownPlate = nullptr;

	/** Standing-spot number -> whoever is standing on it. */
	TMap<int32, TWeakObjectPtr<ACrewHandActor>> Occupant;

	/** The watch just called, in the order it turned up. A slot is emptied rather
	 *  than removed when its hand goes ashore, so the PLACES never shift. */
	TArray<TWeakObjectPtr<ACrewHandActor>> WatchArrivals;

	/** Every roster number issued tonight, on this board. */
	TSet<int32> SpentCodes;

	bool bCallPlatePressed = false;
	bool bStandDownPlatePressed = false;
	bool bCallRunning = false;
	int32 CallSize = 0;
	int32 ArrivalsThisCall = 0;
	double NextArrivalTime = 0.0;

	UPROPERTY()
	TArray<UStaticMeshComponent*> LampBulbs;

	UPROPERTY()
	TArray<UPointLightComponent*> LampGlows;

	UPROPERTY()
	UMaterialInterface* LitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* DarkLook = nullptr;
};
