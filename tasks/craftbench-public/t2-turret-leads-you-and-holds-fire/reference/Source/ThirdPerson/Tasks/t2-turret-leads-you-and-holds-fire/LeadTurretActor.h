// Copyright CraftBench. All Rights Reserved.
//
// A gun turret for task t2-turret-leads-you-and-holds-fire. Everything it needs in
// order to SHOOT is supplied and working: a body bolted to the floor, a barrel that
// swings, an aiming control that drives the barrel, and a trigger that throws a shot
// along wherever the barrel is actually pointing.
//
// REFERENCE SOLUTION. Everything above the marked line in the .cpp is what the task
// supplies; the Tick and the intercept solve below it are the answer. The scaffold
// shipped to the agent is this file with those two removed and ticking off.
//
// The yard holds two of these. They are the same class and they look the same. What
// differs is FOUR numbers, readable on each turret -- and they are not the same on
// both, and the yard RE-TUNES THEM TWICE while it is running. A value read once at
// startup is wrong from the first re-tune onward.
//
// Layout, because it matters to anyone reasoning about the geometry:
//
//   Mount   (root, USceneComponent)   the actor's pivot; this is what "bolted down"
//                                     is measured against
//     Base  (mesh, tag TurretBase)    a 220 cm cylinder standing 320 cm tall, BlockAll
//     Barrel(USceneComponent,         the gun. Its local +X IS THE BORE. Sits 320 cm
//            tag TurretBarrel)        above the floor and is the only thing that turns
//       BarrelMesh                    cosmetic; lies along the bore
//       Muzzle(USceneComponent,       the bore tip, 230 cm out along +X
//              tag TurretMuzzle)
//
// The root is a bare pivot rather than the base mesh on purpose: the base mesh is
// scaled 2.2 x 2.2 x 3.2 to look like a turret body, and a child of a scaled component
// inherits that scale -- which would stretch the barrel and move the muzzle.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LeadTurretActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ALeadTurretActor : public AActor
{
	GENERATED_BODY()

public:
	ALeadTurretActor();

	/** The actor's pivot. Bolted to the floor: the yard places it and nothing may
	 *  turn or move it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Turret")
	USceneComponent* Mount = nullptr;

	/** The body you can see. Solid. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Turret")
	UStaticMeshComponent* Base = nullptr;

	/** THE GUN. Local +X is the bore. This is the only part that turns, and a shot
	 *  always leaves along wherever it is actually pointing at that instant. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Turret")
	USceneComponent* Barrel = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Turret")
	UStaticMeshComponent* BarrelMesh = nullptr;

	/** Where a shot appears. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Turret")
	USceneComponent* Muzzle = nullptr;

	/** How fast THIS turret's shot flies, in cm per second. Read it off the turret,
	 *  every time you need it: the yard re-tunes it mid-run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Turret")
	float ShotSpeedUu = 460.0f;

	/** How far from THIS turret the character has to be before it is willing to
	 *  engage at all, in cm, measured from the turret. Re-tuned mid-run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Turret")
	float EngageRangeUu = 4200.0f;

	/** How quickly THIS turret's barrel can swing, in degrees per second, as a total
	 *  angle. Re-tuned mid-run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Turret")
	float TraverseDegPerSec = 40.0f;

	/** How long THIS turret takes to reload, in seconds. Re-tuned mid-run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Turret")
	float ReloadSeconds = 1.5f;

	/** THE AIMING CONTROL. Swings the barrel toward a world rotation at this turret's
	 *  own TraverseDegPerSec and no faster.
	 *
	 *  Two things about it are deliberate. It is a TOTAL-ANGLE rate limit (a Slerp
	 *  clamped by FQuat::AngularDistance), not a per-Euler-axis one, so the degrees
	 *  per second above means what it says on a diagonal swing as well as on a flat
	 *  one. And it is self-clocked from the world clock and CLAMPED TO ONE FRAME: ten
	 *  calls in one frame swing no further than one call, and a turret that leaves the
	 *  barrel alone for five seconds does not bank those five seconds and then snap. */
	UFUNCTION(BlueprintCallable, Category = "Turret")
	void AimBarrel(FRotator DesiredWorldRotation);

	/** THE TRIGGER. Does nothing and returns false if less than ReloadSeconds of world
	 *  time has passed since this turret last fired. Otherwise throws one shot from
	 *  the muzzle, along the BARREL's current world forward vector, at this turret's
	 *  own ShotSpeedUu, and returns true. */
	UFUNCTION(BlueprintCallable, Category = "Turret")
	bool FireNow();

	UFUNCTION(BlueprintPure, Category = "Turret")
	bool IsReloaded() const;

	/** Where the barrel ACTUALLY is right now -- which is not necessarily where it
	 *  was last told to go. */
	UFUNCTION(BlueprintPure, Category = "Turret")
	FRotator GetBarrelWorldRotation() const;

	UFUNCTION(BlueprintPure, Category = "Turret")
	FVector GetMuzzleWorldLocation() const;

	/** THE DECISION (reference solution). Reads the four numbers off THIS turret every
	 *  frame, solves for where the character will be when a shot leaving now would
	 *  reach them, points the barrel there, and pulls the trigger only when all three
	 *  of range, existence and barrel convergence hold. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

private:
	/** Smallest POSITIVE root of (|V|^2 - s^2)t^2 + 2(D.V)t + |D|^2 = 0, where D is
	 *  the target's offset from the muzzle and V its velocity. False when no such
	 *  root exists -- which IS the "no straight shot could ever catch them" test; it
	 *  does not need a second, separate rule. */
	static bool SolveIntercept(const FVector& D, const FVector& V, double ShotSpeed,
		double& OutFlightSeconds);

	/** World time of the last accepted slew, so AimBarrel can derive its own step. */
	double LastSlewAtSeconds = -1.0;

	/** World time of the last shot. Well in the past so the first shot is free. */
	double LastShotAtSeconds = -1.0e6;
};
