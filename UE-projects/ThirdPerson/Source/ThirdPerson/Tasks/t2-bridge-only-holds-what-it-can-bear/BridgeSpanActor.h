// Copyright CraftBench. All Rights Reserved.
//
// A footbridge span for task t2-bridge-only-holds-what-it-can-bear. Everything the span
// needs to DO is supplied and working: the deck moves, it sags, it gives way, it heaves
// back up, and a lamp on it goes from green to red with the strain. Nothing decides WHEN
// to do any of that.
//
// The yard holds two of these and they are NOT rated the same. Each one's rating is a
// number on it, and the yard stamps fresh numbers each time it opens, so a rating read
// once and remembered is a rating that will be wrong.
//
// WHY THE DECK IS NOT THE ROOT. The actor's origin is the deck's RESTING centre and it
// never moves; the deck slides underneath it. That is what makes "how far has this deck
// dropped" answerable from the outside -- world Z of the deck against world Z of the
// actor -- without trusting anything the span says about itself.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BridgeSpanActor.generated.h"

class UPointLightComponent;
class USceneComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ABridgeSpanActor : public AActor
{
	GENERATED_BODY()

public:
	ABridgeSpanActor();

	/** The actor's origin: where the deck rests. Fixed -- the yard placed it, and the
	 *  deck's height is measured against it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Span")
	USceneComponent* Anchor = nullptr;

	/** The deck you walk on: 900 x 700 x 40, solid, and MOVABLE. Movable is
	 *  load-bearing -- it is what makes somebody standing on the deck ride it when it
	 *  moves, instead of hanging in the air while it slides out from under them. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Span")
	UStaticMeshComponent* Deck = nullptr;

	/** Green when the span is idle, red when it is at its rating or has gone. Rides the
	 *  deck. Presentation only -- nothing is graded on it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Span")
	UPointLightComponent* StrainLamp = nullptr;

	/** How much weight THIS span is rated to hold. Read it off the span: the two spans
	 *  in the yard are not rated the same, and the yard re-stamps both of them. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Span")
	float RatedLoadKg = 600.0f;

	/** How far the deck sits below its rest height when it is carrying exactly its
	 *  rating. Deliberately under the height a character can step up, so the joint
	 *  between the ramp and a fully-laden deck is a step and never a wall. */
	// EditAnywhere, not VisibleAnywhere: this is a STAGING dial the level author
	// sets, and the authoring script sets it. VisibleAnywhere makes it read-only
	// through the Python property path and the map refused to build.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Span")
	float FullSagCm = 30.0f;

	/** How far the deck drops when the span gives way. */
	// EditAnywhere for the same reason as FullSagCm above: the authoring script
	// sets this, and VisibleAnywhere makes it read-only through the Python
	// property path.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Span")
	float GiveWayDropCm = 200.0f;

	/** SWITCH 1 of 3. How far down the deck should be sitting, as a fraction of
	 *  FullSagCm: 0 is dead level, 1 is fully sagged. Clamped. Has no effect while the
	 *  span has given way -- a fallen deck is on the ground, not sagging. */
	UFUNCTION(BlueprintCallable, Category = "Span")
	void SetSagFraction(float NewSagFraction);

	/** SWITCH 2 of 3. The deck drops out: it falls GiveWayDropCm and stays there until
	 *  something puts it back. Whatever was standing on it rides it down. */
	UFUNCTION(BlueprintCallable, Category = "Span")
	void GiveWay();

	/** SWITCH 3 of 3. The span heaves itself back up to whatever sag it was last told
	 *  to hold. */
	UFUNCTION(BlueprintCallable, Category = "Span")
	void HeaveBackUp();

	UFUNCTION(BlueprintPure, Category = "Span")
	bool HasGivenWay() const { return bGivenWay; }

	/** The last fraction SetSagFraction was told, whether or not the deck is there yet. */
	UFUNCTION(BlueprintPure, Category = "Span")
	float GetCommandedSagFraction() const { return CommandedSagFraction; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Moves the deck toward the pose it was last commanded and tints the lamp. Reads
	 *  nothing about the world, counts nothing, decides nothing. */
	void DriveDeckToCommandedPose(float DeltaSeconds);

	float CommandedSagFraction = 0.0f;
	bool bGivenWay = false;
};
