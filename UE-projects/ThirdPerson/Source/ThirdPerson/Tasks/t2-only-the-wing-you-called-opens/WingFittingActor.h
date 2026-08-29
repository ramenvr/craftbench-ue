// Copyright CraftBench. All Rights Reserved.
//
// One fitting of one wing of the host building, for task
// t2-only-the-wing-you-called-opens.
//
// Every one of these is already built and placed, and not one of them is yours to
// place, move, delete or author. They are exactly where they belong. THE WINGS ARE
// NOT ALL THE SAME SIZE -- no two of them need hold the same number of fittings, and
// how many any wing holds is written down nowhere but the building itself. A fitting
// is a plain thing: it stands, it is visible, it blocks whatever walks into it, and a
// small plate on it names the wing it belongs to.
//
// NOTHING HERE DECIDES ANYTHING. A fitting has no idea whether its wing has been
// called; it is either standing in the host or it is not.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WingFittingActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AWingFittingActor : public AActor
{
	GENERATED_BODY()

public:
	AWingFittingActor();

	/** An unscaled pivot, deliberately: a scaled root would multiply every child's
	 *  offset AND its bounds, so the column and the plate are scaled themselves. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Fitting")
	TObjectPtr<USceneComponent> Pivot;

	/** The fitting you can see and walk into. Visible and BlockAll. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Fitting")
	TObjectPtr<UStaticMeshComponent> Column;

	/** The little plate that names this fitting's wing, so a person crossing the hall
	 *  can tell one wing's fittings from another's. Written once when play begins. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Fitting")
	TObjectPtr<UTextRenderComponent> Nameplate;

	/** The name of the wing this fitting belongs to -- the same name that wing's post
	 *  carries. Set on each placed fitting. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fitting")
	FName WingLabel = NAME_None;

protected:
	virtual void BeginPlay() override;
};
