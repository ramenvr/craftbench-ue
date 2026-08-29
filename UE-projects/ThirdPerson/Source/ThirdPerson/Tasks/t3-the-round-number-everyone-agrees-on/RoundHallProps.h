// Copyright CraftBench. All Rights Reserved.
//
// THE ROUND HALL, for task t3-the-round-number-everyone-agrees-on. Everything in this
// file is SUPPLIED AND WORKING, and not one of these things knows that a round number
// exists.
//
// A sign can print a whole number and can be asked what it is printing. The stone at
// the entrance carries the number the hall starts on and shows it. The mark on the
// floor carries the step it raises the round by, shows it, and says out loud when
// somebody steps on and off it. The hoist runs itself: step on its plate and a fresh
// sign of the same kind as the hall's goes up on the empty pillar, blank. The sinkhole
// runs itself too: a runner who walks in is gone, and it says so once they are.
//
// What NOTHING in here does is decide what any sign should show, what the hall's
// number is, or what should happen after a runner is lost. That decision is the whole
// of the task.
//
// Three things worth reading twice, because they are what a submission has to work
// THROUGH rather than around:
//
//   * A sign will print whatever it is told, on any sign. Nothing in here protects the
//     relic at the back from being written over. Whether a sign belongs to the hall is
//     something the sign can be ASKED; it is not something it enforces.
//   * The mark's step and the stone's start number are read off the things themselves,
//     at the moment you ask. Neither is a constant, and one of them does not stay the
//     same for the whole visit.
//   * The hoist spawns a sign of the SAME KIND as a sign already standing in the hall,
//     and the new sign comes up blank. Nothing tells it what to show.
//   * The stone at the entrance carries a SECOND, smaller plate low on its face -- the
//     doorplate. It comes up blank, it prints whatever it is told whenever it is told,
//     and it never changes by itself. Nothing in this file writes on it, ever, and
//     nothing in this file knows what it is for.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RoundHallProps.generated.h"

class APawn;
class UBoxComponent;
class UMaterialInterface;
class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

class AHallSignActor;

/** Fired the moment somebody steps onto the mark in the middle of the room. The mark
 *  has already done everything it is going to do about it, which is nothing. Standing
 *  still on the mark does not fire it again; stepping off and back on does. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FRoundHallSteppedOnSignature, AActor*, Walker);

/** Fired the moment the last thing standing on the mark leaves it. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FRoundHallSteppedOffSignature, AActor*, Walker);

/** Fired the moment the hoist has finished raising a sign. The sign exists, it belongs
 *  to the hall, and it is blank. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FRoundHallSignRaisedSignature, AHallSignActor*, RaisedSign);

/** Fired once a runner has been lost to the sinkhole. By the time this fires that
 *  runner is already gone and nothing in the hall is under anybody's control. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FRoundHallRunnerLostSignature);

/**
 * A sign. It can print one whole number, large enough to read across the room, and it
 * can be asked what it is printing. It starts blank unless it is a relic, in which case
 * it comes up showing the number painted on it and never touches it again by itself.
 *
 * A sign does not know what the hall's number is and never asks anybody.
 */
UCLASS()
class THIRDPERSON_API AHallSignActor : public AActor
{
	GENERATED_BODY()

public:
	AHallSignActor();

	/** The board the number is painted on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sign")
	UStaticMeshComponent* Board = nullptr;

	/** THE FACE -- what anybody in the room reads off this sign. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sign")
	UTextRenderComponent* Face = nullptr;

	/** Whether this sign is one of the hall's. Set per instance in the level; the one
	 *  at the back of the room is not. Read it off the sign -- do not assume it from an
	 *  ordering, a name or a position. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sign")
	bool bBelongsToTheHall = true;

	/** The number painted on a sign that is NOT one of the hall's. It is what such a
	 *  sign comes up showing and what it must go on showing. Meaningless on a sign that
	 *  does belong to the hall. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sign")
	int32 PaintedNumber = 0;

	/** Print a whole number on the face, big enough to read from anywhere in the room.
	 *  It prints whatever it is given, on any sign. */
	UFUNCTION(BlueprintCallable, Category = "Sign")
	void Print(int32 Number);

	/** Leave the face blank. */
	UFUNCTION(BlueprintCallable, Category = "Sign")
	void PrintNothing();

	/** Exactly what the face currently reads, as text. Empty when the sign is blank. */
	UFUNCTION(BlueprintPure, Category = "Sign")
	FString GetPrintedText() const;

	/** Whether this sign is one of the hall's. */
	UFUNCTION(BlueprintPure, Category = "Sign")
	bool BelongsToTheHall() const { return bBelongsToTheHall; }

	/** The number painted on this sign. Only means anything on a sign that is not one
	 *  of the hall's. */
	UFUNCTION(BlueprintPure, Category = "Sign")
	int32 GetPaintedNumber() const { return PaintedNumber; }

	/** True for a sign the hoist put up during the visit, false for one that was
	 *  standing when the hall opened. Bookkeeping the hoist writes for itself. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sign")
	bool bWasRaisedByTheHoist = false;

protected:
	virtual void BeginPlay() override;
};

/**
 * The stone at the entrance. The number the hall starts on is painted on it, and the
 * mark at its foot is where a runner walks in. Neither the number nor the mark is the
 * stone's to change and the stone changes neither.
 */
UCLASS()
class THIRDPERSON_API AEntranceStoneActor : public AActor
{
	GENERATED_BODY()

public:
	AEntranceStoneActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Entrance")
	UStaticMeshComponent* Stone = nullptr;

	/** The painted number, kept in step with StartNumber every frame so that what the
	 *  stone says and what the stone holds can never disagree. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Entrance")
	UTextRenderComponent* Face = nullptr;

	/** The mark on the floor at the stone's foot -- where a runner walks in. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Entrance")
	UStaticMeshComponent* Mark = nullptr;

	/** THE DOORPLATE -- the smaller plate low on the stone's face. It comes up blank and
	 *  nothing in the hall ever writes on it. It prints whatever it is told, whenever it
	 *  is told, and it never changes by itself. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Entrance")
	UTextRenderComponent* Doorplate = nullptr;

	/** THE NUMBER THE HALL STARTS ON. Set per instance; it is not the same number every
	 *  visit. Read it off the stone. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Entrance")
	int32 StartNumber = 1;

	UFUNCTION(BlueprintPure, Category = "Entrance")
	int32 GetStartNumber() const { return StartNumber; }

	/** The middle of the mark on the floor, in world space. */
	UFUNCTION(BlueprintPure, Category = "Entrance")
	FVector GetMarkCentre() const;

	/** Print a whole number on the doorplate, big enough to read across the room. It
	 *  prints whatever it is given and goes on showing it until it is told something
	 *  else. */
	UFUNCTION(BlueprintCallable, Category = "Entrance")
	void PrintOnTheDoorplate(int32 Number);

	/** Leave the doorplate blank. */
	UFUNCTION(BlueprintCallable, Category = "Entrance")
	void ClearTheDoorplate();

	/** Exactly what the doorplate currently reads, as text. Empty when it is blank. */
	UFUNCTION(BlueprintPure, Category = "Entrance")
	FString GetDoorplateText() const;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	/** Keeps the painted number in step with the number the stone holds. THE DOORPLATE
	 *  IS NOT TOUCHED BY THIS, or by anything else in this file. */
	void RefreshFace();
};

/**
 * The mark on the floor in the middle of the room. It carries the step it raises the
 * round by, written where anybody can read it, and it says out loud when somebody steps
 * onto it and when the last of them steps off. It raises nothing itself.
 */
UCLASS()
class THIRDPERSON_API AStepMarkActor : public AActor
{
	GENERATED_BODY()

public:
	AStepMarkActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UStaticMeshComponent* Slab = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UStaticMeshComponent* Post = nullptr;

	/** The step, written on the mark. Kept in step with StepWritten every frame. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UTextRenderComponent* Face = nullptr;

	/** The volume that notices somebody standing on the mark. It exists and it is
	 *  already wired to the two announcements below. NOTHING ELSE IS BOUND TO IT. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Mark")
	UBoxComponent* Volume = nullptr;

	/** THE STEP THIS MARK IS CARRYING. Set per instance, and it can be changed while
	 *  the hall is running. Ask for it at the moment you need it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	int32 StepWritten = 1;

	UFUNCTION(BlueprintPure, Category = "Mark")
	int32 GetStepWritten() const { return StepWritten; }

	/** Somebody has just stepped onto the mark. */
	UPROPERTY(BlueprintAssignable, Category = "Mark")
	FRoundHallSteppedOnSignature OnSteppedOn;

	/** The last thing standing on the mark has just stepped off it. */
	UPROPERTY(BlueprintAssignable, Category = "Mark")
	FRoundHallSteppedOffSignature OnSteppedOff;

	/** Whether anybody is standing on the mark right now. */
	UFUNCTION(BlueprintPure, Category = "Mark")
	bool IsSomebodyStandingOnIt() const { return Standing.Num() > 0; }

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	/** Keeps the written step in step with the step the mark holds. */
	void RefreshFace();

	UFUNCTION()
	void HandleVolumeBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void HandleVolumeEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	/** Who is on the mark right now, one entry per body rather than per limb, so a
	 *  body whose parts arrive separately still counts as one arrival. */
	UPROPERTY()
	TArray<AActor*> Standing;
};

/**
 * The hoist. It runs itself: step on the plate and a fresh sign of the same kind as the
 * hall's own goes up on the empty pillar beside it, blank, already one of the hall's.
 * It can be used more than once, and each new sign goes above the last.
 *
 * The hoist decides nothing about what that sign should show.
 */
UCLASS()
class THIRDPERSON_API AHoistPlateActor : public AActor
{
	GENERATED_BODY()

public:
	AHoistPlateActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hoist")
	UStaticMeshComponent* Plate = nullptr;

	/** The plate's volume. Already wired to the hoist itself. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hoist")
	UBoxComponent* Volume = nullptr;

	/** Where on the pillar the first raised sign lands. Each later one goes above it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hoist")
	USceneComponent* RaiseSocket = nullptr;

	/** How far above the last one each further sign goes. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Hoist")
	float RaiseStackStepUu = 220.0f;

	/** Raise one fresh sign now. Supplied and working; the plate already calls it when
	 *  somebody steps on. Returns the sign that went up, or null if the hall has no
	 *  sign of its own to copy. */
	UFUNCTION(BlueprintCallable, Category = "Hoist")
	AHallSignActor* RaiseSign();

	/** How many signs this hoist has put up so far. */
	UFUNCTION(BlueprintPure, Category = "Hoist")
	int32 GetSignsRaised() const { return SignsRaised; }

	/** A sign has just gone up. It is blank. */
	UPROPERTY(BlueprintAssignable, Category = "Hoist")
	FRoundHallSignRaisedSignature OnSignRaised;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void HandleVolumeBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void HandleVolumeEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	UPROPERTY()
	int32 SignsRaised = 0;

	UPROPERTY()
	TArray<AActor*> Standing;
};

/**
 * The sinkhole. It runs itself: a runner who walks in is gone, and once they are gone
 * it says so. It decides nothing about what happens next, and nothing in the hall sends
 * anybody back in.
 */
UCLASS()
class THIRDPERSON_API ASinkholeActor : public AActor
{
	GENERATED_BODY()

public:
	ASinkholeActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sinkhole")
	UStaticMeshComponent* Rim = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sinkhole")
	UStaticMeshComponent* Shaft = nullptr;

	/** The mouth of the hole. Already wired to the hole itself. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Sinkhole")
	UBoxComponent* Volume = nullptr;

	/** A runner has been lost. By the time this fires that runner is already gone. */
	UPROPERTY(BlueprintAssignable, Category = "Sinkhole")
	FRoundHallRunnerLostSignature OnRunnerLost;

	/** How many runners the hole has taken so far this visit. */
	UFUNCTION(BlueprintPure, Category = "Sinkhole")
	int32 GetRunnersLost() const { return RunnersLost; }

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void HandleVolumeBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

private:
	/** Whoever fell in this frame. The hole lets the frame finish before it takes them,
	 *  so nothing is destroyed in the middle of noticing it. */
	UPROPERTY()
	TArray<APawn*> Falling;

	UPROPERTY()
	int32 RunnersLost = 0;
};
