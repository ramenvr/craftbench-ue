// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-guard-patrols-until-the-alarm-then-chases.
//
// The whole decision is four lines in Tick: if the alarm is sounding and the character
// is inside this guard's alert range, go at them; otherwise walk to the next post. The
// rest of the file is the supplied body and locomotion, unchanged.

#include "PatrolGuardActor.h"

#include "AlarmPanelActor.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FLinearColor kPatrolColour(0.09f, 0.11f, 0.16f);
	const FLinearColor kChaseColour(0.65f, 0.10f, 0.06f);
}

APatrolGuardActor::APatrolGuardActor()
{
	// Every frame: the alarm is a state that can change at any moment, and the guard
	// has to be moving on the frame after it does.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone"));

	Hull = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Hull"));
	SetRootComponent(Hull);
	// 70 cm across, 180 cm tall. The actor stands with this capsule's CENTRE at its
	// location, the way a character does, so the level places the guard at half its
	// height and its feet land on the floor.
	Hull->InitCapsuleSize(35.0f, 90.0f);
	Hull->SetCollisionProfileName(TEXT("BlockAll"));
	Hull->SetMobility(EComponentMobility::Movable);

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Hull);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	// Centred on the hull, so what a reviewer sees and what the guard bumps into
	// are the same 70 x 180 cm.
	Body->SetRelativeScale3D(FVector(0.7f, 0.7f, 1.8f));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (BodyLook.Succeeded())
	{
		Body->SetMaterial(0, BodyLook.Object);
	}

	// A cone on the front, laid on its side so it points the way the guard faces.
	// Attached to the HULL, not the body, so the body's scale does not distort it.
	Snout = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Snout"));
	Snout->SetupAttachment(Hull);
	if (ConeMesh.Succeeded())
	{
		Snout->SetStaticMesh(ConeMesh.Object);
	}
	Snout->SetRelativeScale3D(FVector(0.4f, 0.4f, 0.7f));
	Snout->SetRelativeLocation(FVector(45.0f, 0.0f, 60.0f));
	Snout->SetRelativeRotation(FRotator(-90.0f, 0.0f, 0.0f));
	Snout->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SnoutLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (SnoutLook.Succeeded())
	{
		Snout->SetMaterial(0, SnoutLook.Object);
	}

	Tags.Add(FName("PatrolGuard"));
}

void APatrolGuardActor::BeginPlay()
{
	Super::BeginPlay();

	if (Body != nullptr)
	{
		BodyMaterial = Body->CreateAndSetMaterialInstanceDynamic(0);
	}

	// THE ACTORS ARE CACHED, NOT THEIR POSITIONS. The yard is staged after this runs,
	// and a remembered coordinate would be pointing at where a post used to be.
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("PatrolPost")), Found);
	for (AActor* A : Found)
	{
		Route.Add(A);
	}
	// A stable order, so the guard paces the same way whatever order the level happens
	// to report its actors in.
	Route.Sort([](const TWeakObjectPtr<AActor>& L, const TWeakObjectPtr<AActor>& R)
	{
		return L.IsValid() && R.IsValid()
			&& L->GetName() < R->GetName();
	});

	TArray<AActor*> Panels;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("AlarmPanel")), Panels);
	if (Panels.Num() > 0)
	{
		Alarm = Cast<AAlarmPanelActor>(Panels[0]);
	}
}

void APatrolGuardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const APawn* const Target = UGameplayStatics::GetPlayerPawn(this, 0);
	// The alarm is the SUPPLIED panel's, read straight off it. Nothing here decides
	// when the yard is alarmed -- only what this guard does about it.
	const bool bAlarmed = Alarm.IsValid() && Alarm->IsRinging();
	const bool bInRange = Target != nullptr
		&& FVector::Dist2D(GetActorLocation(), Target->GetActorLocation())
			<= AlertRangeUu;

	if (bAlarmed && bInRange)
	{
		// Straight at them, at chase speed, aiming at where they are NOW: the target
		// moves, and a destination captured when the alarm rang would be a place they
		// have already left.
		StepToward(Target->GetActorLocation(), ChaseSpeedUu, DeltaSeconds);
		Recolour(true);
		return;
	}

	// Otherwise: back to pacing. Nothing is remembered from the chase, so resuming is
	// the same code as starting -- the guard simply walks to the post it was heading
	// for, from wherever the chase left it.
	Recolour(false);
	if (!Route.IsValidIndex(Leg) || !Route[Leg].IsValid())
	{
		return;
	}
	const FVector Goal = Route[Leg]->GetActorLocation();
	if (HasReached(Goal))
	{
		Leg = (Leg + 1) % Route.Num();
		return;
	}
	StepToward(Goal, PatrolSpeedUu, DeltaSeconds);
}

void APatrolGuardActor::Recolour(bool bChasing)
{
	if (BodyMaterial != nullptr && bWasChasing != bChasing)
	{
		BodyMaterial->SetVectorParameterValue(
			TEXT("Color"), bChasing ? kChaseColour : kPatrolColour);
	}
	bWasChasing = bChasing;
}

void APatrolGuardActor::StepToward(const FVector& Destination, float SpeedUu,
	float DeltaSeconds)
{
	if (DeltaSeconds <= 0.0f || SpeedUu <= 0.0f)
	{
		return;
	}

	const FVector Here = GetActorLocation();
	// Flat: the yard is level, and letting a destination's height into this would walk
	// the guard into the floor or up into the air.
	const FVector Flat(Destination.X - Here.X, Destination.Y - Here.Y, 0.0);
	const double Distance = Flat.Size();
	if (Distance <= KINDA_SMALL_NUMBER)
	{
		return;
	}

	const FVector Direction = Flat / Distance;
	// Never overshoot: a long frame must not teleport the guard past its destination.
	const double Travel = FMath::Min(Distance, double(SpeedUu) * DeltaSeconds);
	SetActorLocation(Here + Direction * Travel, /*bSweep=*/true);
	SetActorRotation(Direction.Rotation());
}

bool APatrolGuardActor::HasReached(const FVector& Point) const
{
	const FVector Here = GetActorLocation();
	return FVector(Point.X - Here.X, Point.Y - Here.Y, 0.0).Size() <= ArriveRadiusUu;
}
