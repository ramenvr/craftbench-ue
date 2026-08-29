// Copyright CraftBench. All Rights Reserved.
//
// One painted mark on the hall floor for task t3-hold-the-marks-in-the-order-given.
// Five of these stand in the hall. Everything a mark needs in order to SHOW what is
// happening to it is supplied and working -- a ring painted on the floor, a plate
// carrying its name, a face above it and a lamp on a short mast -- and NOTHING DECIDES
// WHAT TO WRITE ON ANY OF IT. Every face ships blank and every lamp ships dark.
//
// EVERY NUMBER ON A MARK IS ITS OWN, AND NONE OF THEM IS A CONSTANT. The five marks are
// not set alike, and the hall re-writes some of them part way through the night --
// including while somebody is standing on one. Ask a mark for its number at the moment
// you need the answer; a number read once and kept will be wrong before the night is
// out.
//
// A mark holds NO clock, NO progress, NO idea of whose turn it is, and it has never
// heard of the board or of anybody walking about.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FloorMarkActor.generated.h"

class UPointLightComponent;
class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AFloorMarkActor : public AActor
{
	GENERATED_BODY()

public:
	AFloorMarkActor();

	/** An un-scaled anchor, so that sizing one part of the mark can never quietly
	 *  re-size another. (A scaled root multiplies BOTH a child's offset and its own
	 *  extent.) The mark's CENTRE is this actor's location. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	USceneComponent* Anchor = nullptr;

	/** The circle painted on the floor -- exactly RingRadiusUu across the ground from
	 *  the centre. It is PAINT: non-colliding on every channel, you walk over it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UStaticMeshComponent* Ring = nullptr;

	/** The short mast the lamp sits on. Non-colliding. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UStaticMeshComponent* Mast = nullptr;

	/** THIS MARK'S LAMP. Dark from the first frame. Thrown only by SetLampLit. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UPointLightComponent* Lamp = nullptr;

	/** THIS MARK'S FACE. Blank from the first frame. Written only by ShowBank. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UTextRenderComponent* Face = nullptr;

	/** The plate carrying this mark's name, so a person can tell the five apart. It is
	 *  painted from MarkName and it is not the face; nothing else ever writes it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UTextRenderComponent* NamePlate = nullptr;

	// ---------------------------------------------------------------------------
	//  THIS MARK'S OWN NUMBERS. Set per instance in the hall; read them off the mark
	//  you are dealing with. One number does not fit five marks.
	// ---------------------------------------------------------------------------

	/** What this mark is called. A mark is known by this and by nothing else -- not by
	 *  where it stands, not by the order it is found in. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	FName MarkName = NAME_None;

	/** How long somebody has to stand on THIS mark, in seconds. NOT FIXED FOR THE
	 *  NIGHT: the hall re-writes it, including while somebody is standing here. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	float RequiredSeconds = 4.0f;

	/** How far this mark's ring reaches from its centre, in cm. It is the circle you
	 *  can see painted on the floor. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	float RingRadiusUu = 150.0f;

	// ---------------------------------------------------------------------------
	//  WHAT THE MARK CAN DO. All of it works. None of it is ever called.
	// ---------------------------------------------------------------------------

	/** THE FACE. Writes the two numbers a person reads off this mark, one decimal
	 *  each, and mirrors them below in the same breath -- so what a reviewer reads and
	 *  what a tool reads are the same numbers by construction.
	 *
	 *  The hall owns the wording. Only the two numbers are anybody else's business. */
	UFUNCTION(BlueprintCallable, Category = "Mark")
	void ShowBank(float BankedSeconds, float RequiredSecondsShown);

	/** THE LAMP'S SWITCH. Dark, or burning. */
	UFUNCTION(BlueprintCallable, Category = "Mark")
	void SetLampLit(bool bNewLit);

	UFUNCTION(BlueprintPure, Category = "Mark")
	bool IsLampLit() const;

	/** Is a point inside this mark's ring? The hall is flat and HEIGHT PLAYS NO PART:
	 *  this measures across the ground from the mark's centre to the point and answers
	 *  true at RingRadiusUu exactly. Supplied so that everybody in the hall -- and
	 *  everybody looking at it -- means the same thing by "standing on the mark". */
	UFUNCTION(BlueprintPure, Category = "Mark")
	bool IsInsideRing(const FVector& WorldPoint) const;

	/** Re-paints the name plate from MarkName. Called at play; call it again if a
	 *  mark is ever re-named under you. */
	UFUNCTION(BlueprintCallable, Category = "Mark")
	void RefreshNamePlate();

	// ---------------------------------------------------------------------------
	//  MIRRORS of what the face currently reads. WRITTEN ONLY BY ShowBank -- never set
	//  these by hand: a mirror that disagrees with the glass is worth nothing.
	// ---------------------------------------------------------------------------

	/** The banked half of what the face reads. Negative until the face has ever been
	 *  written. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark|Face")
	float LastShownBankedSeconds = -1.0f;

	/** The required half of what the face reads. Negative until the face has ever been
	 *  written. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark|Face")
	float LastShownRequiredSeconds = -1.0f;

	/** False until somebody has written this mark's face at least once. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark|Face")
	bool bFaceEverWritten = false;

protected:
	virtual void BeginPlay() override;
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** What the name plate was last painted from, so the plate can follow a re-name
	 *  without anybody having to remember to ask. */
	FName PaintedName = NAME_None;
};
