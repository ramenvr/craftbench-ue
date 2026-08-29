// Copyright CraftBench. All Rights Reserved.
//
// THE YARD, for task t3-checkpoint-restores-the-world. Everything in this file is
// SUPPLIED AND WORKING. Not one of these props knows that checkpoints exist: a door
// latches open, a coin can be taken and put back, the counter can be written to, and
// the hot floor reports that somebody stood on it. What none of them does is decide
// WHEN any of that should happen again -- that is the whole of the task, and it lives
// in CheckpointDirectorActor.
//
// Each prop that has something to report announces it and then stops. It does not act
// on its own announcement, and it does not look at any other prop.
//
// Three things in here are worth reading twice, because they are what a restore has to
// go THROUGH rather than around:
//
//   * ALatchDoorActor::SetOpen is the door's own operation. It moves the leaf between
//     two fixed places AND sets the latch, so SetOpen(false) really does un-latch the
//     door and its plate works again afterwards. Moving the leaf yourself puts the
//     picture back and leaves the latch set, and that door never opens again.
//   * ACoinPickupActor::Restore puts the coin back on its stand and DELIBERATELY does
//     not touch the counter. Collect() adds one to CARRIED; Restore() subtracts
//     nothing, because what CARRIED should read after a restore is not this coin's
//     business.
//   * ABankCounterActor writes both numbers only through SetCarried/SetBanked, and
//     both refresh the faces a player reads. What the counter holds and what the
//     counter shows can never disagree.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CheckpointYardProps.generated.h"

class UBoxComponent;
class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

class ACheckpointStandActor;

/** Fired the moment the player character steps onto a checkpoint pad. The pad has
 *  already done everything it is going to do about it, which is nothing. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FCheckpointStoodOnSignature, ACheckpointStandActor*, Stand);

/** Fired the instant the line is crossed with something in hand: Amount is what moved,
 *  NewBanked is what BANKED now reads. Not fired when nothing is being carried. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
	FBankCounterBankedSignature, int32, Amount, int32, NewBanked);

/** Fired when somebody touches hot floor. The strip does nothing else whatsoever. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FHazardLethalTouchSignature, AActor*, Victim);

/**
 * A checkpoint pad. It lights when armed and it knows where somebody sent back here
 * should stand. It does NOT decide which pad is current, and it takes no snapshot of
 * anything.
 */
UCLASS()
class THIRDPERSON_API ACheckpointStandActor : public AActor
{
	GENERATED_BODY()

public:
	ACheckpointStandActor();

	/** The volume just above the pad, and the ROOT: the pad's position IS the
	 *  volume's position, so nothing can drift between what you stand on and what
	 *  notices you. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stand")
	UBoxComponent* Trigger = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stand")
	UStaticMeshComponent* Pad = nullptr;

	/** Dark at intensity 0, bright when armed. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stand")
	UPointLightComponent* Lamp = nullptr;

	/** Pads are numbered along the yard. Later is further in. Nothing here reads it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stand")
	int32 StandOrder = 0;

	/** Announced when the player character steps on. */
	UPROPERTY(BlueprintAssignable, Category = "Stand")
	FCheckpointStoodOnSignature OnStoodOn;

	/** Lit when this is the pad somebody would come back to. */
	UFUNCTION(BlueprintCallable, Category = "Stand")
	void SetArmed(bool bNewArmed);

	UFUNCTION(BlueprintPure, Category = "Stand")
	bool IsArmed() const { return bArmed; }

	/** Where somebody sent back here should stand: clear of the slab, facing the way
	 *  the pad faces. */
	UFUNCTION(BlueprintPure, Category = "Stand")
	FTransform GetRespawnTransform() const;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other, UPrimitiveComponent* OtherComp,
		int32 BodyIndex, bool bFromSweep, const FHitResult& Sweep);

private:
	bool bArmed = false;
};

/**
 * A door with its own floor plate. Step on the plate and the door opens and STAYS
 * open -- it latches, and nothing shuts it behind you.
 *
 * The leaf lives at exactly one of two places, and SetOpen moves it between them in
 * one step; there is no in-between pose to catch it in. GetLeafShutLocation and
 * GetLeafOpenLocation are those two places in world space, derived from the slide
 * this door was authored with, so nobody has to guess a distance.
 *
 * SetOpen(false) is how a door goes back: it moves the leaf AND clears the latch, so
 * the plate opens the door again exactly like the first time.
 */
UCLASS()
class THIRDPERSON_API ALatchDoorActor : public AActor
{
	GENERATED_BODY()

public:
	ALatchDoorActor();

	/** Plain root, so neither the leaf's slide nor the plate's scale drags the other
	 *  around. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	USceneComponent* Frame = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	UStaticMeshComponent* Leaf = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	UStaticMeshComponent* Plate = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	UBoxComponent* PlateTrigger = nullptr;

	/** Which door this is. The yard has more than one and they are not alike. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	FName DoorId = NAME_None;

	/** How far the leaf slides aside, along this actor's local +Y. Authored per door. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	float OpenSlideUu = 450.0f;

	/** Where the plate sits relative to the door, in the actor's local frame. It is
	 *  out on the open floor, on the far side from the way the leaf slides, so the
	 *  leaf can never sweep whoever is standing on it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	FVector PlateOffsetUu = FVector(0.0f, -700.0f, 0.0f);

	/** THE DOOR'S OWN OPERATION. Moves the leaf to one of its two places and sets the
	 *  latch to match. SetOpen(false) leaves the door shut AND workable. */
	UFUNCTION(BlueprintCallable, Category = "Door")
	void SetOpen(bool bNewOpen);

	UFUNCTION(BlueprintPure, Category = "Door")
	bool IsOpen() const { return bOpen; }

	/** The leaf's two places, in world space. */
	UFUNCTION(BlueprintPure, Category = "Door")
	FVector GetLeafShutLocation() const;

	UFUNCTION(BlueprintPure, Category = "Door")
	FVector GetLeafOpenLocation() const;

protected:
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnPlateBegin(UPrimitiveComponent* Comp, AActor* Other, UPrimitiveComponent* OtherComp,
		int32 BodyIndex, bool bFromSweep, const FHitResult& Sweep);

	/** Puts the plate and its volume where PlateOffsetUu says, without letting the
	 *  plate's own scale reach the volume. */
	void PlaceThePlate();

private:
	bool bOpen = false;
};

/**
 * A coin on a stand. Taking it hides the coin and adds one to CARRIED. Restore puts it
 * back on its stand and deliberately leaves CARRIED alone -- what the counter should
 * read after somebody has been sent back is not this coin's business.
 */
UCLASS()
class THIRDPERSON_API ACoinPickupActor : public AActor
{
	GENERATED_BODY()

public:
	ACoinPickupActor();

	/** Root, so the whole coin -- stand, coin and volume -- moves as one piece. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Coin")
	UBoxComponent* Trigger = nullptr;

	/** The post the coin sits on. Always there, taken or not. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Coin")
	UStaticMeshComponent* Stand = nullptr;

	/** The coin itself. Hidden while it is in somebody's hands. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Coin")
	UStaticMeshComponent* Coin = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Coin")
	FName CoinId = NAME_None;

	/** Hides the coin and adds one to CARRIED. Does nothing if it is already taken. */
	UFUNCTION(BlueprintCallable, Category = "Coin")
	void Collect();

	/** Puts it back on its stand, untaken, and does NOT touch the counter. */
	UFUNCTION(BlueprintCallable, Category = "Coin")
	void Restore();

	UFUNCTION(BlueprintPure, Category = "Coin")
	bool IsCollected() const { return bCollected; }

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other, UPrimitiveComponent* OtherComp,
		int32 BodyIndex, bool bFromSweep, const FHitResult& Sweep);

	/** The counter this coin reports to, found once at BeginPlay. */
	UPROPERTY()
	class ABankCounterActor* Counter = nullptr;

private:
	bool bCollected = false;
};

/**
 * The counter on the wall. It holds TWO numbers and they mean different things.
 *
 *   CARRIED  what somebody is holding right now, not yet safe.
 *   BANKED   what they have already walked across the line with. Progress.
 *
 * Walking into the counter's volume with something in hand banks it: CARRIED empties,
 * BANKED goes up by exactly what was carried, and OnBanked says so. Both numbers can
 * be written from outside and both writers refresh the faces, so what a player sees
 * and what the counter holds can never disagree. The counter has no opinion about
 * when a write is right.
 */
UCLASS()
class THIRDPERSON_API ABankCounterActor : public AActor
{
	GENERATED_BODY()

public:
	ABankCounterActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bank")
	USceneComponent* Anchor = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bank")
	UStaticMeshComponent* Post = nullptr;

	/** The volume over the painted line. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bank")
	UBoxComponent* Trigger = nullptr;

	/** The two faces a player reads. Bare numbers, nothing else. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bank")
	UTextRenderComponent* CarriedText = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bank")
	UTextRenderComponent* BankedText = nullptr;

	/** What BANKED already reads when the yard opens. The yard has progress on the
	 *  board before anybody arrives; read it, never assume it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bank")
	int32 StartingBanked = 0;

	/** Announced the instant the line is crossed with something in hand. */
	UPROPERTY(BlueprintAssignable, Category = "Bank")
	FBankCounterBankedSignature OnBanked;

	UFUNCTION(BlueprintPure, Category = "Bank")
	int32 GetCarried() const { return Carried; }

	UFUNCTION(BlueprintPure, Category = "Bank")
	int32 GetBanked() const { return Banked; }

	UFUNCTION(BlueprintCallable, Category = "Bank")
	void SetCarried(int32 NewCarried);

	UFUNCTION(BlueprintCallable, Category = "Bank")
	void SetBanked(int32 NewBanked);

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other, UPrimitiveComponent* OtherComp,
		int32 BodyIndex, bool bFromSweep, const FHitResult& Sweep);

private:
	void RefreshFaces();

	int32 Carried = 0;
	int32 Banked = 0;
};

/**
 * The floor that kills. On contact it says so, and does nothing else -- it does not
 * move anybody, and it does not put anything back.
 */
UCLASS()
class THIRDPERSON_API AHazardStripActor : public AActor
{
	GENERATED_BODY()

public:
	AHazardStripActor();

	/** Root. Query-only: it notices, it does not block. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hazard")
	UBoxComponent* Trigger = nullptr;

	/** The hot floor you can see. Flat and non-blocking, so it is walked OVER. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hazard")
	UStaticMeshComponent* Strip = nullptr;

	UPROPERTY(BlueprintAssignable, Category = "Hazard")
	FHazardLethalTouchSignature OnLethalTouch;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other, UPrimitiveComponent* OtherComp,
		int32 BodyIndex, bool bFromSweep, const FHitResult& Sweep);
};
