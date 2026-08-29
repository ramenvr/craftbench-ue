// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t3-keyring-opens-what-it-was-cut-for.
//
// The ring belongs to the SHIFT, not to the body, so it lives here -- on something that
// comes up with the world and goes down with it. Anywhere that outlives the pawn would
// do (the controller, the player state, a level-resident prop, a save slot); what will
// NOT do is the character, which the yard retires half way through.
//
// Three things this file is careful about, each of which is a way to be wrong that
// looks right until the shift changes:
//
//   1. THE BODY IS NEVER CACHED. It is re-resolved from the controller on every tick.
//      Reading it once and keeping it works perfectly for the whole first half and then
//      goes silently dead, because the pawn the yard retires takes the pointer with it.
//   2. A BAY IS LATCHED, NOT POLLED. Once it is open it is never looked at again --
//      not when the character walks off, not when the ring changes, not when the fresh
//      body takes over. A per-frame `SetOpen(somebody is standing here with the key)`
//      shuts the bay the moment the character steps away.
//   3. THE BOARD IS REDRAWN FROM THE RING, not from the last thing that happened, and
//      whenever what it reads is not what the ring says -- which is the only way to
//      notice the yard blanking it at the shift change, since nothing announces that.
//
// A key is never spent: the ring only ever grows, and opening a bay reads it without
// taking anything out of it.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "KeyringShiftSubsystem.generated.h"

class ADoorBayActor;
class AKeyStandActor;
class ARingBoardActor;

UCLASS()
class THIRDPERSON_API UKeyringShiftSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	/** One pass over the level, the first tick after play begins. */
	void FindTheYard();
	/** Puts on the ring every key the body is standing close enough to take. */
	void TakeKeysWithin(const FVector& BodyAt);
	/** Opens every bay the body is standing at and holds every category for. */
	void OpenBaysWithin(const FVector& BodyAt);
	/** Writes the ring onto the board whenever the board is not already showing it. */
	void RefreshBoard();
	FString RingLine() const;

	/** THE RING. In pickup order, never sorted, never reduced. */
	UPROPERTY()
	TArray<FName> Ring;

	UPROPERTY()
	TArray<AKeyStandActor*> Stands;

	UPROPERTY()
	TArray<ADoorBayActor*> Bays;

	UPROPERTY()
	ARingBoardActor* BoardActor = nullptr;

	bool bFoundTheYard = false;
};
