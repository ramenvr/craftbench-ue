// Copyright CraftBench. All Rights Reserved.
//
// A numbered standing spot for task t2-the-crew-arrives-and-thins-out.
//
// SUPPLIED AND WORKING, and completely passive: a painted square on the deck with its
// number painted on it, the board it belongs to written on it, and the exact place a
// hand stands when it takes this spot. It notices nothing and reports nothing.
//
// Non-colliding on every channel, so nothing standing here is ever in anybody's way.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CrewBerthActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ACrewBerthActor : public AActor
{
	GENERATED_BODY()

public:
	ACrewBerthActor();

	/** The painted square you can see. NON-COLLIDING. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Berth")
	UStaticMeshComponent* Paint = nullptr;

	/** This spot's number, painted on the deck so a person can read it too. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Berth")
	UTextRenderComponent* PaintedNumber = nullptr;

	/** Which board this standing spot belongs to. Every board, standing spot and
	 *  floor plate on the deck carries the name of the board it belongs to, and only
	 *  matching names go together. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Berth")
	FName BoardTag = NAME_None;

	/** This spot's number, as painted on the deck. Lower numbers come first. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Berth")
	int32 SpotNumber = 1;

	/** Exactly where somebody stands when they take this spot. The way the spot
	 *  itself faces is the way they stand. */
	UFUNCTION(BlueprintPure, Category = "Berth")
	FVector GetStandLocation() const;

protected:
	/** Keeps the number painted on the deck honest about SpotNumber. Presentation
	 *  only. */
	virtual void OnConstruction(const FTransform& Transform) override;
};
