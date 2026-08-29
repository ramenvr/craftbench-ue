// Copyright CraftBench. All Rights Reserved.
//
// A barrier in the yard, for task t3-gate-and-door-cpp. Every
// door in this yard is one of these, and so is the new gate on the west arch.
//
// Everything a barrier needs in order to SHOW what it is doing is supplied and
// working: the panel sweeps about its hinge toward whichever pose it has been told to
// hold, never faster than its own travel rate; the floating number above it prints how
// far the panel has turned from the pose it started play in, read off the panel's own
// live pose so the two can never disagree; and the plate on the frame prints what this
// barrier is cut for, read off the barrier's own live properties for the same reason.
//
// ====================== THE RULE THAT ALREADY RUNS =========================
// ShouldBeOpen is the yard's one rule, and it has run every pad in this yard for
// years: while any single body -- a person or a crate, the yard has never cared which
// -- is resting on a pad that answers for this barrier, this barrier is open, and
// otherwise it is shut. That one rule is what makes the old door work.
// ===========================================================================
//
// ============================ THE YARD IS FIXED ============================
// The barriers, the pads, the crates and the lamps are all placed in a level you
// cannot edit, so whatever does the deciding has to live on a class the level already
// instantiates: a barrier, a pad, a crate, a lamp, or the character. A brand new class
// would never be placed and would never run.
// ===========================================================================
//
// CutForFirstName and CutForSecondName are what THIS barrier is cut for, in that
// order. Whoever is in charge of the yard re-cuts them, and does not announce it.
// Keep them as properties with these names and this type.
//
// SetCommandedOpen is an override for whoever wants to drive a barrier from somewhere
// else: whatever was passed to it most recently within a frame is what the barrier
// holds for that frame, and if nobody called it the yard's own rule decides. The
// barrier never asks who called.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardBarrierActor.generated.h"

class AGateLampActor;
class AYardPadActor;
class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AYardBarrierActor : public AActor
{
	GENERATED_BODY()

public:
	AYardBarrierActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Root, at floor level in the middle of the opening. It never moves: the panel
	 *  moves inside it. Everything hangs off it unscaled. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	USceneComponent* Frame = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	UStaticMeshComponent* PostLeft = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	UStaticMeshComponent* PostRight = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	UStaticMeshComponent* Lintel = nullptr;

	/** What the panel sweeps about. Nothing else is attached to it, so swinging the
	 *  panel never carries a readout away with it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	USceneComponent* Hinge = nullptr;

	/** THE PANEL. The part a person watches swing, and the part that says whether
	 *  this barrier is open. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	UStaticMeshComponent* Panel = nullptr;

	/** Prints how far the panel has turned from its play-start pose, in degrees. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	UTextRenderComponent* AngleReadout = nullptr;

	/** Prints the pair of names this barrier is cut for, in order. Reads "--" on a
	 *  barrier that is cut for nothing. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	UTextRenderComponent* CutPlate = nullptr;

	/** How far the panel turns from its play-start pose when this barrier is open. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Barrier")
	float OpenAngleDeg = 90.0f;

	/** The fastest this barrier's panel ever travels, in degrees per second. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Barrier")
	float TravelRateDegPerSec = 180.0f;

	/** The first of the two names this barrier is cut for. Empty on a barrier that is
	 *  cut for nothing. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Barrier")
	FName CutForFirstName;

	/** The second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Barrier")
	FName CutForSecondName;

	/** The panel's yaw when play began -- what "shut" means for this barrier.
	 *  Recorded once, so a barrier that has been driven still knows its way home. */
	UFUNCTION(BlueprintPure, Category = "Barrier")
	double GetShutPanelYaw() const { return ShutPanelYaw; }

	/** How far the panel has turned from that pose right now. Read off the panel's
	 *  own live pose, never off a stored number. */
	UFUNCTION(BlueprintPure, Category = "Barrier")
	double GetPanelAngleFromShutDeg() const;

	/** The pads in the yard that answer for this barrier. Worked out once, when play
	 *  begins, from what each pad says it answers for. */
	const TArray<AYardPadActor*>& GetPadsAnsweringForMe() const { return Pads; }

	/** The lamps bolted to this barrier, in whatever order the level hands them
	 *  over. Worked out once, when play begins. Empty on a barrier carrying none. */
	const TArray<AGateLampActor*>& GetMyLamps() const { return Lamps; }

	/** Tell this barrier whether it should be open, for this frame. The most recent
	 *  call within a frame is the one that counts; with no call at all the yard's own
	 *  rule below decides. */
	UFUNCTION(BlueprintCallable, Category = "Barrier")
	void SetCommandedOpen(bool bOpen);

	/** THE YARD'S RULE. Open while any single body is resting on any pad that answers
	 *  for this barrier; shut otherwise. This is the decision the yard makes, and it
	 *  is yours to change -- in native code or in a Blueprint subclass, whichever you
	 *  are working in. Whatever answers it, the panel is driven the same way and the
	 *  old door is judged the same way it has always been judged. */
	UFUNCTION(BlueprintNativeEvent, Category = "Barrier")
	bool ShouldBeOpen() const;
	virtual bool ShouldBeOpen_Implementation() const;

protected:
	/** Sweeps the panel one frame's worth toward the pose it should be holding,
	 *  never faster than TravelRateDegPerSec. */
	void DrivePanel(float DeltaSeconds, bool bWantOpen);

	/** Keeps the two floating readouts in step with what is actually true. */
	void UpdateReadouts();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	TArray<AYardPadActor*> Pads;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrier")
	TArray<AGateLampActor*> Lamps;

private:
	double ShutPanelYaw = 0.0;
	double SweptAngleDeg = 0.0;

	bool bHasCommandThisTick = false;
	bool bCommandedOpen = false;

	FString ShownCut;
};
