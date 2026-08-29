// Copyright CraftBench. All Rights Reserved.
//
// The post standing at the mouth of one wing of the host building, for task
// t2-only-the-wing-you-called-opens. Four of them are already in the level, one per
// wing, and none of them is yours to move.
//
// A post is a wing's identity. It carries the wing's name -- the same name the wing's
// own fittings carry, and the same name a call mark shows when it is calling that wing
// -- and the name of the part of the level that wing's fittings are kept in. THAT
// SECOND NAME IS NOTHING LIKE THE WING'S OWN, and it is written down nowhere else. A
// wing is a place: a post never changes what it says.
//
// NOTHING HERE DECIDES ANYTHING.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WingPostActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AWingPostActor : public AActor
{
	GENERATED_BODY()

public:
	AWingPostActor();

	/** An unscaled pivot, so the post's scale never reaches the nameplate. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	TObjectPtr<USceneComponent> Pivot;

	/** The post you can see. NON-COLLIDING: nothing in the host may stand in anybody's
	 *  way. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	TObjectPtr<UStaticMeshComponent> Post;

	/** The wing's name, painted where anybody crossing the host can read it. Written
	 *  once when play begins. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	TObjectPtr<UTextRenderComponent> Nameplate;

	/** THE WING'S NAME. Set on each placed post. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	FName WingName = NAME_None;

	/** The name of the part of the level this wing's fittings are kept in. Set on each
	 *  placed post, and NOT derived from the wing's own name. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	FName SectionId = NAME_None;

protected:
	virtual void BeginPlay() override;
};
