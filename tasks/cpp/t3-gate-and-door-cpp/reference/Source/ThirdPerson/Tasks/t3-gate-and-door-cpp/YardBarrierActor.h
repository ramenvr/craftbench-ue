// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t3-gate-and-door.
//
// THE WHOLE CHANGE, IN ONE SENTENCE: the narrowing belongs to the gate's question,
// not to the yard's pads. The pads still answer the question they have always
// answered -- who is resting on me, person or crate alike -- because that is what
// makes the old door work. What is new is that a barrier which is CUT FOR NAMES asks
// a different question of the same pads, and answers it from the crates' own names
// read live, plus a lamp per name slot.
//
// Two things it deliberately does NOT do, because each of them is a wrong answer that
// compiles and reads beautifully:
//   * it does not narrow AYardPadActor's occupancy to crates -- that would fix the
//     gate and kill the old door, which nobody ever puts a crate on;
//   * it does not turn the yard's ANY-pad rule into an ALL-pads rule -- that would
//     keep the old door working and let a person standing on a gate pad, or a crate
//     the gate is not cut for, open the gate.
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
// ================= THE RULE THAT ALREADY RAN, AND STILL DOES ===============
// ShouldBeOpen's FIRST branch is untouched from the scaffold, and that is deliberate:
// while any single body -- a person or a crate, the yard has never cared which -- is
// resting on a pad that answers for this barrier, this barrier is open, and otherwise
// it is shut. Both doors take that branch. It is what makes the old door work, and
// narrowing it anywhere (here, or inside the pad's own occupancy question) is what
// would silently stop the old door ever opening again, because nobody ever puts a
// crate on the old door's pad.
// ===========================================================================
//
// ========================= WHAT WAS ADDED HERE =============================
// A SECOND branch in ShouldBeOpen, taken only by a barrier that is cut for a pair of
// names, plus the three helpers it needs (IsCutForNames, IsNamedCrateHome,
// GetCutNameForSlot) and a per-slot lamp pass (DriveLamps). Nothing else in the yard
// changed: the pads, the crates and the lamps are byte-identical to the scaffold.
//
// IsCutForNames is the whole brownfield decision, written down: a barrier is only
// special when the yard has written a pair of names on THAT barrier. Not its class,
// not which pads it owns, not where it stands -- data carried on the instance. That is
// what leaves both doors, which are cut for nothing, on the branch they shipped with.
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

	/** THE YARD'S RULE, for a barrier that is cut for nothing: open while any single
	 *  body is resting on any pad that answers for this barrier, shut otherwise. For a
	 *  barrier that IS cut for a pair of names, open exactly while a crate carrying
	 *  each of those two names is resting on one of its pads. */
	UFUNCTION(BlueprintNativeEvent, Category = "Barrier")
	bool ShouldBeOpen() const;
	virtual bool ShouldBeOpen_Implementation() const;

	/** ADDED. Has the yard written a pair of names on THIS barrier. Nothing about the
	 *  class, the pads or the position: a barrier is special only when its own two
	 *  slots carry something, which is exactly what both doors do not. */
	UFUNCTION(BlueprintPure, Category = "Barrier")
	bool IsCutForNames() const;

	/** Is a crate carrying exactly this name resting on one of this barrier's pads
	 *  right now. A person is not a crate and never counts; an empty name is nobody.
	 *  Asked afresh every time, because what the barrier is cut for changes without
	 *  announcement. */
	UFUNCTION(BlueprintPure, Category = "Barrier")
	bool IsNamedCrateHome(FName WantedName) const;

	/** What this barrier is cut for in the given slot, right now. */
	UFUNCTION(BlueprintPure, Category = "Barrier")
	FName GetCutNameForSlot(int32 Slot) const;

protected:
	/** Sweeps the panel one frame's worth toward the pose it should be holding,
	 *  never faster than TravelRateDegPerSec. */
	void DrivePanel(float DeltaSeconds, bool bWantOpen);

	/** Keeps the two floating readouts in step with what is actually true. */
	void UpdateReadouts();

	/** Each lamp burns exactly while a crate carrying the name in ITS OWN slot is
	 *  resting on one of this barrier's pads. Worked out per slot, never from whether
	 *  the panel happens to be open. */
	void DriveLamps();

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
