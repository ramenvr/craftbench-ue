// Copyright CraftBench. All Rights Reserved.

#include "LeadTurretActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "TurretShotActor.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kBaseTopUu = 320.0f;     // the barrel's height above the floor
	constexpr float kBoreLenUu = 230.0f;     // muzzle offset along the bore
	constexpr float kBaseScaleXY = 2.2f;     // a 220 cm cylinder ...
	constexpr float kBaseScaleZ = 3.2f;      // ... standing 320 cm tall

	const TCHAR* const kBaseLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kBarrelLook = TEXT("/Game/Variant_Combat/Materials/M_Lava");
}

ALeadTurretActor::ALeadTurretActor()
{
	// NOTHING HERE DECIDES ANYTHING. Turn this on if your solution needs it.
	PrimaryActorTick.bCanEverTick = false;

	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	SetRootComponent(Mount);
	Mount->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cyl(
		TEXT("/Engine/BasicShapes/Cylinder"));

	Base = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Base"));
	Base->SetupAttachment(Mount);
	if (Cyl.Succeeded())
	{
		Base->SetStaticMesh(Cyl.Object);
	}
	// The cylinder is 100 cm across and 100 cm tall about its own centre, so a 3.2
	// scale standing on the floor puts its centre at 160.
	Base->SetRelativeLocation(FVector(0.0f, 0.0f, kBaseTopUu * 0.5f));
	Base->SetRelativeScale3D(FVector(kBaseScaleXY, kBaseScaleXY, kBaseScaleZ));
	Base->SetMobility(EComponentMobility::Movable);
	Base->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BaseMat(kBaseLook);
	if (BaseMat.Succeeded())
	{
		Base->SetMaterial(0, BaseMat.Object);
	}
	Base->ComponentTags.Add(FName("TurretBase"));

	// THE GUN. Attached to the MOUNT, not to the base mesh, so it does not inherit the
	// base's 2.2 x 3.2 scale.
	Barrel = CreateDefaultSubobject<USceneComponent>(TEXT("Barrel"));
	Barrel->SetupAttachment(Mount);
	Barrel->SetRelativeLocation(FVector(0.0f, 0.0f, kBaseTopUu));
	// PARKED SIDEWAYS, pointing across the yard rather than down it. Acquiring a
	// target for the first time is therefore a real swing, and how long that swing
	// takes is this turret's own business.
	Barrel->SetRelativeRotation(FRotator(0.0f, 90.0f, 0.0f));
	Barrel->SetMobility(EComponentMobility::Movable);
	Barrel->ComponentTags.Add(FName("TurretBarrel"));

	BarrelMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BarrelMesh"));
	BarrelMesh->SetupAttachment(Barrel);
	if (Cyl.Succeeded())
	{
		BarrelMesh->SetStaticMesh(Cyl.Object);
	}
	// The cylinder mesh runs along its own +Z. A pitch of -90 sends local +Z to the
	// parent's +X, i.e. lays the tube along the bore. (Pitch is a rotation about Y:
	// -90 maps +Z -> +X and +X -> -Z.)
	BarrelMesh->SetRelativeRotation(FRotator(-90.0f, 0.0f, 0.0f));
	BarrelMesh->SetRelativeLocation(FVector(kBoreLenUu * 0.5f, 0.0f, 0.0f));
	BarrelMesh->SetRelativeScale3D(FVector(0.30f, 0.30f, kBoreLenUu / 100.0f));
	BarrelMesh->SetMobility(EComponentMobility::Movable);
	BarrelMesh->SetCollisionProfileName(TEXT("NoCollision"));
	BarrelMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BarrelMat(kBarrelLook);
	if (BarrelMat.Succeeded())
	{
		BarrelMesh->SetMaterial(0, BarrelMat.Object);
	}

	Muzzle = CreateDefaultSubobject<USceneComponent>(TEXT("Muzzle"));
	Muzzle->SetupAttachment(Barrel);
	Muzzle->SetRelativeLocation(FVector(kBoreLenUu, 0.0f, 0.0f));
	Muzzle->SetMobility(EComponentMobility::Movable);
	Muzzle->ComponentTags.Add(FName("TurretMuzzle"));

	Tags.Add(FName("LeadTurret"));
}

void ALeadTurretActor::BeginPlay()
{
	Super::BeginPlay();

	// Start the slew clock. Without this the first AimBarrel call would derive its
	// step from a world time of zero.
	const UWorld* const World = GetWorld();
	LastSlewAtSeconds = World ? double(World->GetTimeSeconds()) : 0.0;
}

void ALeadTurretActor::AimBarrel(FRotator DesiredWorldRotation)
{
	const UWorld* const World = GetWorld();
	if (World == nullptr || Barrel == nullptr)
	{
		return;
	}
	const double Now = double(World->GetTimeSeconds());
	// One frame's worth, at most, however long it has been since the last call and
	// however many times this is called in a frame.
	const double Frame = FMath::Max(double(World->GetDeltaSeconds()), 1.0 / 240.0);
	const double Step = FMath::Clamp(Now - LastSlewAtSeconds, 0.0, Frame);
	LastSlewAtSeconds = Now;
	if (Step <= 0.0)
	{
		return;
	}

	const FQuat Have = Barrel->GetComponentQuat();
	const FQuat Want = DesiredWorldRotation.Quaternion();
	// AngularDistance is the FULL angle between the two orientations, in radians --
	// not a per-axis figure. Clamping the Slerp by it is what makes
	// TraverseDegPerSec an honest total-angle rate. FMath::RInterpConstantTo would
	// clamp Pitch, Yaw and Roll independently and let a diagonal swing run up to
	// sqrt(2) faster than the advertised rate.
	const double Remaining = double(Have.AngularDistance(Want));
	const double CanMove = FMath::DegreesToRadians(
		double(FMath::Max(TraverseDegPerSec, 0.0f))) * Step;
	if (Remaining <= CanMove || Remaining <= UE_KINDA_SMALL_NUMBER)
	{
		Barrel->SetWorldRotation(Want);
	}
	else
	{
		Barrel->SetWorldRotation(FQuat::Slerp(Have, Want, CanMove / Remaining));
	}
}

bool ALeadTurretActor::IsReloaded() const
{
	const UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	return double(World->GetTimeSeconds()) - LastShotAtSeconds
		>= double(FMath::Max(ReloadSeconds, 0.0f));
}

FRotator ALeadTurretActor::GetBarrelWorldRotation() const
{
	return Barrel != nullptr ? Barrel->GetComponentRotation() : FRotator::ZeroRotator;
}

FVector ALeadTurretActor::GetMuzzleWorldLocation() const
{
	return Muzzle != nullptr ? Muzzle->GetComponentLocation() : GetActorLocation();
}

bool ALeadTurretActor::FireNow()
{
	UWorld* const World = GetWorld();
	if (World == nullptr || Barrel == nullptr || Muzzle == nullptr || !IsReloaded())
	{
		return false;
	}
	LastShotAtSeconds = double(World->GetTimeSeconds());

	const FVector From = Muzzle->GetComponentLocation();
	// WHEREVER THE BARREL IS ACTUALLY POINTING. Not where it was told to go.
	const FVector Along = Barrel->GetForwardVector();

	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ATurretShotActor* const Shot = World->SpawnActor<ATurretShotActor>(
		ATurretShotActor::StaticClass(), From, Along.Rotation(), Params);
	if (Shot == nullptr)
	{
		return false;
	}
	Shot->LaunchFrom(this, From, Along, ShotSpeedUu);
	return true;
}
