// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-guard-only-spots-what-it-can-see.

#include "SightGuardActor.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kLitIntensity = 5000.0f;
	const FLinearColor kLitColour(1.0f, 0.08f, 0.05f);
	const FLinearColor kDarkColour(0.06f, 0.06f, 0.07f);

	// Look at the character's chest rather than the point its capsule stands on: a
	// line aimed at the feet grazes the floor and reads as blocked.
	constexpr double kChestUu = 40.0;
}

ASightGuardActor::ASightGuardActor()
{
	// Every frame, so the lamp is right on the frame the answer changes -- far inside
	// the half second the brief allows.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	// ~60 cm across, 180 cm tall, sitting on the floor.
	Body->SetRelativeScale3D(FVector(0.6f, 0.6f, 1.8f));
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, 90.0f));
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (BodyLook.Succeeded())
	{
		Body->SetMaterial(0, BodyLook.Object);
	}

	// In FRONT of the body on purpose: a line drawn from here toward anything never
	// starts inside the guard's own collision.
	Eye = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Eye"));
	Eye->SetupAttachment(Body);
	if (SphereMesh.Succeeded())
	{
		Eye->SetStaticMesh(SphereMesh.Object);
	}
	// The body is scaled (0.6, 0.6, 1.8), so the offsets below are undone from it to
	// land the eye at world (40, 0, 170) relative to the guard.
	Eye->SetRelativeScale3D(FVector(0.25f / 0.6f, 0.25f / 0.6f, 0.25f / 1.8f));
	Eye->SetRelativeLocation(FVector(40.0f / 0.6f, 0.0f, (170.0f - 90.0f) / 1.8f));
	Eye->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Bulb = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Bulb"));
	Bulb->SetupAttachment(Body);
	if (SphereMesh.Succeeded())
	{
		Bulb->SetStaticMesh(SphereMesh.Object);
	}
	Bulb->SetRelativeScale3D(FVector(0.45f / 0.6f, 0.45f / 0.6f, 0.45f / 1.8f));
	Bulb->SetRelativeLocation(FVector(0.0f, 0.0f, (200.0f - 90.0f) / 1.8f));
	Bulb->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	AlertLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("AlertLamp"));
	AlertLamp->SetupAttachment(Body);
	AlertLamp->SetRelativeLocation(FVector(0.0f, 0.0f, (200.0f - 90.0f) / 1.8f));
	AlertLamp->SetLightColor(kLitColour);
	AlertLamp->SetIntensity(0.0f);
	AlertLamp->SetAttenuationRadius(600.0f);
	AlertLamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("SightGuard"));
}

void ASightGuardActor::BeginPlay()
{
	Super::BeginPlay();

	if (Bulb != nullptr)
	{
		BulbMaterial = Bulb->CreateAndSetMaterialInstanceDynamic(0);
	}
	// Dark from the first frame, whatever the editor left behind.
	SetSpotted(false);
}

bool ASightGuardActor::CanSee(const AActor& Target) const
{
	const UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}

	// The sanctioned sight origin, not the actor pivot: the pivot sits at the guard's
	// feet, inside its own collision.
	const FVector Origin =
		Eye != nullptr ? Eye->GetComponentLocation() : GetActorLocation();
	const FVector Aim = Target.GetActorLocation() + FVector(0.0, 0.0, kChestUu);
	const FVector ToTarget = Aim - Origin;

	// 1. Near enough. Measured against this guard's own number, so a guard configured
	// differently behaves differently without a line of code changing.
	if (ToTarget.Size() > SightRangeUu)
	{
		return false;
	}

	// 2. Far enough forward. Measured against the direction THIS guard faces -- never
	// against a world axis, which would stop working the moment a guard is turned.
	const FVector Facing = GetActorForwardVector().GetSafeNormal();
	const double CosAngle = FVector::DotProduct(Facing, ToTarget.GetSafeNormal());
	const double AngleDeg =
		FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(CosAngle, -1.0, 1.0)));
	if (AngleDeg > SightHalfAngleDeg)
	{
		return false;
	}

	// 3. Nothing solid in between. Both endpoints are ignored: the guard because a
	// turned body can still swing into its own eye line, and the target because it is
	// the thing being looked at, not an obstacle.
	FCollisionQueryParams Params(SCENE_QUERY_STAT(GuardSight), /*bTraceComplex=*/true);
	Params.AddIgnoredActor(this);
	Params.AddIgnoredActor(&Target);
	FHitResult Hit;
	return !World->LineTraceSingleByChannel(Hit, Origin, Aim, ECC_Visibility, Params);
}

void ASightGuardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The character the player controls. Resolved every frame rather than cached at
	// BeginPlay: the pawn is spawned and possessed by the game mode, and a cached
	// pointer would be null on any frame before that has happened.
	const APawn* const Watched = UGameplayStatics::GetPlayerPawn(this, 0);
	SetSpotted(Watched != nullptr && CanSee(*Watched));
}

void ASightGuardActor::SetSpotted(bool bNewSpotted)
{
	bSpotted = bNewSpotted;
	if (AlertLamp != nullptr)
	{
		AlertLamp->SetIntensity(bNewSpotted ? kLitIntensity : 0.0f);
	}
	if (BulbMaterial != nullptr)
	{
		BulbMaterial->SetVectorParameterValue(
			TEXT("Color"), bNewSpotted ? kLitColour : kDarkColour);
	}
}
