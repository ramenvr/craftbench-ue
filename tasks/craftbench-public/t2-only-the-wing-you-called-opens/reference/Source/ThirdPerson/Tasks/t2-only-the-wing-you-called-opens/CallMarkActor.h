// Copyright CraftBench. All Rights Reserved.
//
// A call mark set into the host floor, for task t2-only-the-wing-you-called-opens.
// Three of them are already in the level and none of them is yours to move.
//
// A mark is a pad you can stand on, a region just above it that reports what walks in
// and what walks out, and a name floating in the air over it. THE NAME IS THE POINT:
// a mark calls the wing whose name it is showing at the moment somebody steps onto it.
//
// THE NAME IS NOT FIXED FOR THE RUN. Marks are re-lettered while play is running, and
// nothing announces it -- what a mark showed a minute ago tells you nothing about what
// it calls now.
//
// ======================= WHAT IS NOT HERE ============================
// NOTHING IS BOUND TO THE REGION. The mark reports that somebody has stepped on it and
// no one is listening; nothing calls a wing, nothing brings anything into the host,
// nothing takes anything out, and nothing writes the board over the gate. That is the
// work.
//
// The host and all four of its wings are already built, in a level that is not yours to
// edit -- so whatever does the deciding has to live on a class the level already
// instantiates: a mark, a wing post, the gate board, a fitting, or the character. A
// brand new actor class would never be placed and would never run.
// =====================================================================

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CallMarkActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ACallMarkActor : public AActor
{
	GENERATED_BODY()

public:
	ACallMarkActor();

	/** The region just above the pad. THE ROOT, so the mark's position IS the region's
	 *  position. It reports what enters and leaves, and it blocks nothing. NOTHING IS
	 *  BOUND TO IT. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	TObjectPtr<UBoxComponent> StepVolume;

	/** The 220 x 220 cm pad set into the floor. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	TObjectPtr<UStaticMeshComponent> Pad;

	/** The name floating over this mark -- what a person reads before they step. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	TObjectPtr<UTextRenderComponent> Label;

	/** Which mark this is, so a person can tell the three apart. It never changes and
	 *  it says nothing about which wing the mark calls. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	FName MarkId = NAME_None;

	/** The name this mark is showing right now. Read it at the moment of the step; it
	 *  is re-lettered while play is running. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	FName CalledWingName = NAME_None;

	/** Sets the name shown above this mark, and paints it on the floating label so a
	 *  person can read the change as it happens. */
	UFUNCTION(BlueprintCallable, Category = "Mark")
	void SetCalledWingName(FName InWingName);

	/** The name this mark is showing at this instant. */
	UFUNCTION(BlueprintPure, Category = "Mark")
	FName GetCalledWingName() const { return CalledWingName; }

protected:
	virtual void BeginPlay() override;
};
