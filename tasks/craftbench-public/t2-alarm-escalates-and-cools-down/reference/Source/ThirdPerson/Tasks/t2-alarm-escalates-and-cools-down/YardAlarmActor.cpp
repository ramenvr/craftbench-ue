// Copyright CraftBench. All Rights Reserved.

#include "YardAlarmActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "WatchGuardActor.h"
#include "YardLampActor.h"

AYardAlarmActor::AYardAlarmActor()
{
	// Every frame: a guard's cone sweeps past somebody at any moment, and the yard is
	// allowed half a second to catch up with what that means.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board"));
	SetRootComponent(Board);
	if (CubeMesh.Succeeded())
	{
		Board->SetStaticMesh(CubeMesh.Object);
	}
	// A 240 x 40 x 200 cm board standing on its edge, centred on the actor's location.
	Board->SetRelativeScale3D(FVector(2.4f, 0.4f, 2.0f));
	// Non-colliding on every channel, and the PROFILE as well as the enum -- see
	// AYardLampActor for why a prop that quietly blocks a sightline is a hazard here.
	Board->SetCollisionProfileName(TEXT("NoCollision"));
	Board->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Look.Succeeded())
	{
		Board->SetMaterial(0, Look.Object);
	}

	Tags.Add(FName("YardAlarm"));
}

void AYardAlarmActor::BeginPlay()
{
	Super::BeginPlay();

	// The CAST is resolved once -- the yard is fixed, nothing is spawned or destroyed.
	// Every NUMBER on them is read live, every frame, because that is what changes.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("WatchGuard")), Found);
	for (AActor* A : Found)
	{
		if (AWatchGuardActor* G = Cast<AWatchGuardActor>(A))
		{
			Guards.Add(G);
		}
	}
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("YardLamp")), Found);
	for (AActor* A : Found)
	{
		if (AYardLampActor* L = Cast<AYardLampActor>(A))
		{
			Lamps.Add(L);
		}
	}

	// The yard begins calm with nothing counted -- and calm is NOT "every floodlight
	// dark": one of them burns from the calmest setting, so the first thing the panel
	// owes the yard is to throw that switch.
	Stage = 0;
	Sightings = 0;
	bSeenLastFrame = false;
	QuietFor = 0.0;
	for (AYardLampActor* L : Lamps)
	{
		if (L != nullptr)
		{
			L->SetLit(L->LitFromStage <= Stage);
		}
	}
	for (AWatchGuardActor* G : Guards)
	{
		if (G != nullptr)
		{
			G->PatrolSpeedUuPerSec = G->BasePatrolSpeedUu * ScaleFor(Stage);
		}
	}
}

float AYardAlarmActor::ScaleFor(int32 InStage) const
{
	// Straight off the board, at the moment of use.
	if (InStage >= 2) { return PatrolScaleWhenHunting; }
	if (InStage == 1) { return PatrolScaleWhenWatching; }
	return PatrolScaleWhenCalm;
}

double AYardAlarmActor::EffectiveReachOf(const AWatchGuardActor* Guard) const
{
	if (Guard == nullptr)
	{
		return 0.0;
	}
	double Reach = Guard->SightRangeUu;
	for (const AYardLampActor* L : Lamps)
	{
		// A BURNING floodlight, and only over the round this guard is actually on.
		// Both halves matter: the floodlights change as the setting moves, and which
		// guard walks which round changes when the watch does.
		if (L != nullptr && L->IsLit() && L->CoversRoundTag == Guard->RoundTag)
		{
			Reach += L->ReachBonusUu;
		}
	}
	return Reach;
}

bool AYardAlarmActor::CanSee(const AWatchGuardActor* Guard, const FVector& Target) const
{
	if (Guard == nullptr)
	{
		return false;
	}
	const FVector Eye = Guard->GetActorLocation();
	// FLAT: the yard is level and height plays no part.
	const FVector To(Target.X - Eye.X, Target.Y - Eye.Y, 0.0);
	const double Distance = To.Size();
	if (Distance > EffectiveReachOf(Guard))
	{
		return false;
	}
	if (Distance <= KINDA_SMALL_NUMBER)
	{
		return true;   // standing on the guard is inside every cone.
	}
	const FVector Facing = FVector(Guard->GetActorForwardVector().X,
		Guard->GetActorForwardVector().Y, 0.0).GetSafeNormal();
	const double AngleDeg = FMath::RadiansToDegrees(FMath::Acos(
		FMath::Clamp(FVector::DotProduct(Facing, To / Distance), -1.0, 1.0)));
	return AngleDeg <= Guard->SightHalfAngleDeg;
}

void AYardAlarmActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const APawn* const Hero = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
	if (Hero == nullptr || DeltaSeconds <= 0.0f)
	{
		return;
	}
	const FVector Target = Hero->GetActorLocation();

	// 1. CAN ANYBODY SEE HIM. Each guard against its OWN two numbers, plus whatever
	//    the floodlights currently burning over its round add to its reach. This is
	//    read before anything below changes the floodlights, so what a guard can see
	//    this instant is decided by the yard as it stands this instant.
	bool bSeen = false;
	for (const AWatchGuardActor* G : Guards)
	{
		if (CanSee(G, Target))
		{
			bSeen = true;
			break;
		}
	}

	// 2. A SIGHTING IS AN EDGE, not a length of time: nobody could see him, and now
	//    somebody can. Clamped at the panel's own cap, so standing in the open all
	//    night is worth no more than the dial says.
	if (bSeen && !bSeenLastFrame)
	{
		Sightings = FMath::Min(Sightings + 1, MaxSightingsRemembered);
	}
	bSeenLastFrame = bSeen;

	// 3. THE QUIET CLOCK. Being seen at all puts it straight back to zero; otherwise
	//    it forgets one sighting per QuietSecondsPerStepDown, and then another, and so
	//    on -- a while, not an if, because a long frame or a long silence must not
	//    lose a step.
	if (bSeen)
	{
		QuietFor = 0.0;
	}
	else
	{
		QuietFor += DeltaSeconds;
		const double Step = FMath::Max(double(QuietSecondsPerStepDown), 0.01);
		while (QuietFor >= Step)
		{
			QuietFor -= Step;
			Sightings = FMath::Max(Sightings - 1, 0);
		}
	}

	// 4. THE SETTING, WHICH IS A MEMORY. The raise numbers and the drop numbers are
	//    different, so between them the panel does not move at all and the setting is
	//    whatever it already was. Deriving the setting from the count with a single
	//    ladder would flap while somebody loiters at the edge of a cone -- which is
	//    exactly what the band in between exists to stop. One step at a time, in both
	//    directions.
	while (Stage < 2
		&& Sightings >= (Stage == 0 ? SightingsToRaiseWatch : SightingsToRaiseHunt))
	{
		++Stage;
	}
	while (Stage > 0
		&& Sightings <= (Stage == 2 ? SightingsToDropWatch : SightingsToDropCalm))
	{
		--Stage;
	}

	// 5. WHAT THE YARD SHOWS. Each floodlight answers to its OWN setting number, and
	//    each guard to its OWN base pace -- there is no "the" pace and no ordering to
	//    the floodlights.
	for (AYardLampActor* L : Lamps)
	{
		if (L != nullptr)
		{
			L->SetLit(L->LitFromStage <= Stage);
		}
	}
	const float Scale = ScaleFor(Stage);
	for (AWatchGuardActor* G : Guards)
	{
		if (G != nullptr)
		{
			G->PatrolSpeedUuPerSec = G->BasePatrolSpeedUu * Scale;
		}
	}
}
