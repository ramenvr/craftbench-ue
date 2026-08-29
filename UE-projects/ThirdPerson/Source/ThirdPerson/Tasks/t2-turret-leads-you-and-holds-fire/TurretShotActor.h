// Copyright CraftBench. All Rights Reserved.
//
// The tracer a turret throws for task t2-turret-leads-you-and-holds-fire. It is the
// whole of what "a shot" means here: it leaves where it was launched from, along the
// direction it was launched along, at the speed it was launched at, and NOTHING pulls
// it down or steers it afterwards. Where it ends up is settled at the instant it
// leaves the barrel.
//
// Collision is off outright. That is load-bearing rather than tidy: a colliding
// projectile would be destroyed on its first contact (taking the closest-approach
// measurement with it) and would shove the character off the straight line the
// measurement depends on.
//
// SUPPLIED AND COMPLETE. Nothing here is the agent's to write.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TurretShotActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ATurretShotActor : public AActor
{
	GENERATED_BODY()

public:
	ATurretShotActor();

	/** Stamped once, by LaunchFrom, at the moment the shot leaves the gun. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Shot")
	AActor* Shooter = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Shot")
	FVector LaunchLoc = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Shot")
	FVector LaunchDir = FVector::ForwardVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Shot")
	float LaunchSpeed = 0.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Shot")
	double FiredAtSeconds = 0.0;

	/** Called by ALeadTurretActor::FireNow. Stamps the shot and starts it moving. */
	void LaunchFrom(AActor* InShooter, const FVector& InLoc, const FVector& InDir,
		float InSpeed);

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY()
	UStaticMeshComponent* Tracer = nullptr;
};
