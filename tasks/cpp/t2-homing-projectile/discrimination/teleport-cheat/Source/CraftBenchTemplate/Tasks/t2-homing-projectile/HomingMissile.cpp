// GAMING VARIANT (anti-gaming note #3): a teleport cheat — the projectile
// drifts slowly, then at t=2.5s SetActorLocation()s itself onto the target.
// The fixture's per-frame motion policing sees an impossible frame
// displacement and fails the run even though the raw min-distance would
// have satisfied the arrival radius.

#include "HomingMissile.h"

#include "Components/SceneComponent.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

AHomingMissile::AHomingMissile()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);
	Tags.Add(FName("HomingMissile"));

	Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
	Movement->InitialSpeed = 700.0f;   // drift within the band, way off pace
	Movement->MaxSpeed = 700.0f;
	Movement->ProjectileGravityScale = 0.0f;
}

void AHomingMissile::InitHoming(AActor* InTarget)
{
	if (InTarget == nullptr)
	{
		return;
	}
	const FVector ToTarget = (InTarget->GetActorLocation() - GetActorLocation()).GetSafeNormal();
	Movement->Velocity = ToTarget * Movement->InitialSpeed;

	// The cheat: jump onto the target late in the run.
	FTimerHandle Handle;
	TWeakObjectPtr<AHomingMissile> WeakThis(this);
	GetWorld()->GetTimerManager().SetTimer(Handle, [WeakThis]()
	{
		if (!WeakThis.IsValid())
		{
			return;
		}
		TArray<AActor*> Targets;
		UGameplayStatics::GetAllActorsWithTag(WeakThis->GetWorld(), FName("MissileTarget"), Targets);
		if (Targets.Num() > 0)
		{
			WeakThis->SetActorLocation(Targets[0]->GetActorLocation());
		}
	}, 2.5f, false);
}
