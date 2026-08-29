// GAMING VARIANT (teleports-to-player). See header.

#include "ChaserNpcCharacter.h"

#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

AChaserNpcCharacter::AChaserNpcCharacter()
{
	Tags.Add(FName("ChaserNpc"));
}

void AChaserNpcCharacter::BeginPlay()
{
	Super::BeginPlay();
	// First snap at 1.5s, then every 1.5s: always "caught up" at any sampled
	// instant without ever walking.
	GetWorldTimerManager().SetTimer(
		SnapTimer, this, &AChaserNpcCharacter::SnapToPlayer, 1.5f, /*bLoop=*/true, /*FirstDelay=*/1.5f);
}

void AChaserNpcCharacter::SnapToPlayer()
{
	if (ACharacter* Player = UGameplayStatics::GetPlayerCharacter(this, 0))
	{
		const FVector ToNpc = (GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
		SetActorLocation(Player->GetActorLocation() + ToNpc * 150.0 + FVector(0, 0, 2.0),
			false, nullptr, ETeleportType::TeleportPhysics);
	}
}
