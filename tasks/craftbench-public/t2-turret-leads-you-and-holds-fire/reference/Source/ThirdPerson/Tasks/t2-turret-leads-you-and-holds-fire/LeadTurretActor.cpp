// Copyright CraftBench. All Rights Reserved.

#include "LeadTurretActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "TurretShotActor.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// HOW CLOSE THE BARREL HAS TO BE BEFORE THE TRIGGER IS PULLED. Derived, not
	// picked: the yard says a shot connects if it passes within 120 cm of the middle
	// of the character, so an aiming error of e radians at a meeting point D away
	// costs about D*sin(e) of miss. Spending a third of the allowance on the barrel
	// leaves the rest for everything else, and the cone therefore has to be scaled to
	// the range -- a fixed number of degrees is either useless at 40 m or so tight the
	// turret never fires at 8 m.
	constexpr double kAimBudgetUu = 42.0;

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
	// The decision is re-taken every frame, because all four numbers can change under
	// it and the character never stops moving.
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

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

// ---------------------------------------------------------------------------------
// THE DECISION. Everything below this line is the solution; everything above it was
// supplied.
// ---------------------------------------------------------------------------------

bool ALeadTurretActor::SolveIntercept(const FVector& D, const FVector& V,
	double ShotSpeed, double& OutFlightSeconds)
{
	// |D + V t| = s t, squared:  (|V|^2 - s^2) t^2 + 2 (D.V) t + |D|^2 = 0.
	const double A = V.SizeSquared() - ShotSpeed * ShotSpeed;
	const double B = 2.0 * FVector::DotProduct(D, V);
	const double C = D.SizeSquared();
	if (C <= UE_KINDA_SMALL_NUMBER)
	{
		OutFlightSeconds = 0.0;
		return true;
	}
	if (ShotSpeed <= UE_KINDA_SMALL_NUMBER)
	{
		return false;
	}
	if (FMath::Abs(A) < 1.0e-4)
	{
		// Target running at exactly the shot's speed: the quadratic degenerates.
		if (FMath::Abs(B) < 1.0e-6)
		{
			return false;
		}
		const double T = -C / B;
		if (T <= 1.0e-4)
		{
			return false;
		}
		OutFlightSeconds = T;
		return true;
	}
	const double Disc = B * B - 4.0 * A * C;
	if (Disc < 0.0)
	{
		// NO REAL ROOT -- no straight shot leaving now at this speed ever meets them.
		// This is the hold-fire test; taking a square root of it anyway and firing
		// along the resulting direction is the failure this branch exists to avoid.
		return false;
	}
	const double Root = FMath::Sqrt(Disc);
	const double T1 = (-B - Root) / (2.0 * A);
	const double T2 = (-B + Root) / (2.0 * A);
	// The SMALLEST POSITIVE root, which is not the same as the smaller root: when the
	// target outruns the shot, A > 0 and both roots are positive or both negative.
	const double Lo = FMath::Min(T1, T2);
	const double Hi = FMath::Max(T1, T2);
	if (Lo > 1.0e-4)
	{
		OutFlightSeconds = Lo;
		return true;
	}
	if (Hi > 1.0e-4)
	{
		OutFlightSeconds = Hi;
		return true;
	}
	return false;
}

void ALeadTurretActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* const World = GetWorld();
	if (World == nullptr || Barrel == nullptr || Muzzle == nullptr)
	{
		return;
	}
	const ACharacter* const Target = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (Target == nullptr)
	{
		return;
	}

	// READ THE NUMBERS OFF THIS TURRET, THIS FRAME. Caching them in BeginPlay is
	// right for exactly as long as the yard leaves them alone, which is not long.
	const double ShotSpeed = double(ShotSpeedUu);
	const double Reach = double(EngageRangeUu);

	const FVector From = Muzzle->GetComponentLocation();
	const FVector Where = Target->GetActorLocation();
	const FVector Moving = Target->GetVelocity();

	double Flight = 0.0;
	if (!SolveIntercept(Where - From, Moving, ShotSpeed, Flight))
	{
		// Nowhere to aim. Not "aim at them anyway and hope" -- nothing at all.
		return;
	}
	const FVector Meet = Where + Moving * Flight;
	const FVector Bore = (Meet - From).GetSafeNormal();
	if (Bore.IsNearlyZero())
	{
		return;
	}

	// Point the gun. The servo gets it as far as this turret's own rate allows this
	// frame; it is asked again next frame, against a freshly re-solved meeting point.
	// This runs whether or not the turret is allowed to fire, so the barrel is already
	// tracking when a window opens rather than starting a swing at that moment.
	const FRotator Want = Bore.Rotation();
	AimBarrel(Want);

	// IN REACH, measured from the turret, against THIS turret's own number.
	if (FVector::Dist(Where, GetActorLocation()) > Reach)
	{
		return;
	}
	if (!IsReloaded())
	{
		return;
	}

	// AND THE BARREL HAS TO HAVE ARRIVED. Comparing forward vectors rather than
	// rotators keeps roll out of it -- a shot leaves along the bore, and the bore does
	// not care how the gun is rolled about it.
	const double MeetRange = FMath::Max(FVector::Dist(From, Meet), 1.0);
	const double ConeRad = FMath::Asin(
		FMath::Clamp(kAimBudgetUu / MeetRange, 0.0, 1.0));
	const double PointingErr = FMath::Acos(
		FMath::Clamp(FVector::DotProduct(Barrel->GetForwardVector(), Bore),
			-1.0, 1.0));
	if (PointingErr > ConeRad)
	{
		return;
	}

	FireNow();
}
