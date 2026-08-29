// Copyright CraftBench. All Rights Reserved.
//
// One landing of the tower for task t3-lift-serves-its-calls-in-order. Three of these
// are placed in the level, one above the other. Each ships a deck you walk on, a call
// pad you step on, a lamp on that pad, and a sign. Every one of them can be told what to
// do and none of them is told anything.
//
// WHERE THIS LANDING'S FLOOR IS IS NOT A CONSTANT. Deck is Movable and the shaft is put
// together before the lift ever runs, so the height you would read off the level in the
// editor is not the height the landing has at run time -- and one landing is moved again
// part way through. Ask GetSillHeight() at the moment you need the answer.
//
// GetSillHeight() is the top of Deck's world bounds. The car's own GetSillHeight() is
// the top of ITS floor's world bounds, so "level with the landing" is one subtraction
// between two numbers derived the same way, and the verifier derives them the same way
// again.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LiftLandingActor.generated.h"

class UBoxComponent;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ALiftLandingActor : public AActor
{
	GENERATED_BODY()

public:
	ALiftLandingActor();

	/** THE ROOT and the floor you walk on. Movable, BlockAll. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UStaticMeshComponent* Deck = nullptr;

	/** Waist-high walls on the three sides away from the shaft, so nobody walks off the
	 *  back of a landing 18 metres up. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UStaticMeshComponent* ParapetFar = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UStaticMeshComponent* ParapetLeft = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UStaticMeshComponent* ParapetRight = nullptr;

	/** The pad you step on to send for the lift. It exists and it generates overlap
	 *  events. NOTHING IS BOUND TO IT. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UBoxComponent* CallPad = nullptr;

	/** The lamp over the call pad -- the visible face of a latched call. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UPointLightComponent* CallLamp = nullptr;

	/** THE SIGN: the number half. Starts blank. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing|Sign")
	UTextRenderComponent* Readout = nullptr;

	/** THE SIGN: the arrow half. Starts hidden. Points along its own up axis. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing|Sign")
	UStaticMeshComponent* Arrow = nullptr;

	/** A fixed plate naming this landing, so a human can tell the three apart. Written
	 *  once at play from FloorNumber; it is not the sign and it never changes. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Landing")
	UTextRenderComponent* FloorPlate = nullptr;

	/** Which landing this is: 1 at the bottom, 3 at the top. Set per instance in the
	 *  level; read it, do not assume it from an ordering. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing")
	int32 FloorNumber = 1;

	/** Light or clear this landing's call lamp. */
	UFUNCTION(BlueprintCallable, Category = "Landing")
	void SetCallLit(bool bLit);

	UFUNCTION(BlueprintPure, Category = "Landing")
	bool IsCallLit() const;

	/** World Z of the TOP of Deck -- the surface somebody standing here is standing on.
	 *  ASK IT WHEN YOU NEED IT. It is not the same number all run. */
	UFUNCTION(BlueprintPure, Category = "Landing")
	float GetSillHeight() const;

	/** THE SIGN. InFloorNumber is printed as a number (0 or less blanks it); Direction
	 *  is +1 to show the arrow pointing up, -1 pointing down, 0 to hide it. */
	UFUNCTION(BlueprintCallable, Category = "Landing|Sign")
	void Show(int32 InFloorNumber, int32 Direction);

protected:
	virtual void BeginPlay() override;
};
