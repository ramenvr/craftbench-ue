// Copyright CraftBench. All Rights Reserved.

#include "YardCrateActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm on a side.
	const FVector kCrateScale(1.2f, 1.2f, 1.2f);
	constexpr double kCrateHalfHeightUu = 60.0;

	/** The crate's own footprint across the ground: two crate centres closer
	 *  together than this would be standing in the same place. */
	constexpr double kFootprintUu = 120.0;

	/** How squarely somebody has to be behind the crate along its rail. 0.5 is a
	 *  60 degree half-cone about the rail, which is the difference between standing
	 *  behind the crate and brushing past its corner. */
	constexpr double kMinAlongness = 0.5;

	/** How squarely somebody has to be walking INTO the rail before it counts as a
	 *  shove. 0.35 is about 70 degrees either side of the rail bearing. */
	constexpr double kMinIntoRail = 0.35;

	const TCHAR* const kCrateMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02");
}

AYardCrateActor::AYardCrateActor()
{
	// Ticks so the crate can run along its rail while somebody shoves it, and so the
	// name plate always shows the name the crate is actually carrying.
	PrimaryActorTick.bCanEverTick = true;

	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	SetRootComponent(Mount);
	// Movable: the crate slides, so nothing under it may be pinned static.
	Mount->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> CrateLook(kCrateMaterial);

	Crate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Crate"));
	Crate->SetupAttachment(Mount);
	if (CubeMesh.Succeeded())
	{
		Crate->SetStaticMesh(CubeMesh.Object);
	}
	if (CrateLook.Succeeded())
	{
		Crate->SetMaterial(0, CrateLook.Object);
	}
	Crate->SetRelativeScale3D(kCrateScale);
	Crate->SetRelativeLocation(FVector(0.0, 0.0, kCrateHalfHeightUu));
	Crate->SetMobility(EComponentMobility::Movable);
	Crate->SetCollisionProfileName(TEXT("BlockAll"));

	NamePlate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("NamePlate"));
	NamePlate->SetupAttachment(Mount);
	NamePlate->SetRelativeLocation(FVector(0.0, 0.0, 190.0));
	NamePlate->SetHorizontalAlignment(EHTA_Center);
	NamePlate->SetWorldSize(46.0f);
	NamePlate->SetTextRenderColor(FColor(255, 236, 170));
	NamePlate->SetText(FText::FromString(TEXT("--")));
	NamePlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// Absolute rotation so the name stays readable from the camera's side wherever
	// the crate is standing.
	NamePlate->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("YardCrate")));
}

void AYardCrateActor::BeginPlay()
{
	Super::BeginPlay();

	// The rail is fixed the moment play begins: this spot is one hard stop and the
	// crate's own forward line is the bearing. Nothing after this changes either.
	RailAnchor = GetActorLocation();
	RailAxis = GetActorForwardVector().GetSafeNormal2D();
	if (RailAxis.IsNearlyZero())
	{
		RailAxis = FVector::ForwardVector;
	}

	if (NamePlate != nullptr)
	{
		NamePlate->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
	}
}

float AYardCrateActor::GetRailParamUu() const
{
	return static_cast<float>(
		FVector::DotProduct(GetActorLocation() - RailAnchor, RailAxis));
}

void AYardCrateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Presentation: the plate always prints the name the crate is carrying, read off
	// the crate itself, so what a person reads in the level and what the crate says
	// about itself can never come apart.
	if (NamePlate != nullptr && ShownName != CrateName)
	{
		ShownName = CrateName;
		NamePlate->SetText(CrateName.IsNone()
			? FText::FromString(TEXT("--"))
			: FText::FromName(CrateName));
	}

	if (Mount == nullptr || GetWorld() == nullptr)
	{
		return;
	}

	// Who is shoving, and which way. Somebody shoves the crate when they are up
	// against it, squarely behind it along its rail, and walking into it. This is the
	// only thing that ever moves the crate.
	const FVector Here = GetActorLocation();
	double Direction = 0.0;
	for (TActorIterator<APawn> It(GetWorld()); It; ++It)
	{
		const APawn* const Shover = *It;
		if (Shover == nullptr)
		{
			continue;
		}
		const FVector ShoverPos = Shover->GetActorLocation();
		if (FVector::Dist2D(Here, ShoverPos) > ShoveReachUu)
		{
			continue;
		}

		const FVector ToCrate = (Here - ShoverPos).GetSafeNormal2D();
		const double Alongness = FVector::DotProduct(ToCrate, RailAxis);
		if (FMath::Abs(Alongness) < kMinAlongness)
		{
			// Beside the crate rather than behind it along the rail.
			continue;
		}

		// What the body is ASKING to do, not what it has managed to do. A crate you
		// are leaning on brings your speed to nothing while you are still walking
		// into it, and that is precisely the moment the shove has to count -- reading
		// the speed instead would leave crate and shover deadlocked against each
		// other. The fallback covers anything that moves without asking.
		FVector Wish = Shover->GetLastMovementInputVector();
		if (Wish.IsNearlyZero())
		{
			Wish = Shover->GetVelocity();
		}
		const FVector Flat(Wish.X, Wish.Y, 0.0);
		if (Flat.IsNearlyZero())
		{
			continue;
		}
		const double Into = FVector::DotProduct(Flat.GetSafeNormal(), RailAxis);

		if (Alongness > 0.0 && Into >= kMinIntoRail)
		{
			Direction = 1.0;
		}
		else if (Alongness < 0.0 && Into <= -kMinIntoRail)
		{
			Direction = -1.0;
		}
	}

	if (Direction == 0.0)
	{
		return;
	}

	// It runs at its own speed and stops dead at whichever hard stop it reaches. The
	// height never changes: the crate slides along the ground, it does not climb.
	const double Mine = GetRailParamUu();
	double Wanted = Mine + Direction * ShoveSpeedUu * DeltaSeconds;

	// It also stops short of another crate standing in its way. Two crates cannot
	// occupy the same ground, so two rails that share a stop can only take it one at
	// a time: shove the one that is home off it before the other can have it.
	for (TActorIterator<AYardCrateActor> It(GetWorld()); It; ++It)
	{
		const AYardCrateActor* const Other = *It;
		if (Other == nullptr || Other == this)
		{
			continue;
		}

		const FVector ToOther = Other->GetActorLocation() - RailAnchor;
		const double Along = FVector::DotProduct(ToOther, RailAxis);
		const FVector Sideways =
			FVector(ToOther.X, ToOther.Y, 0.0) - RailAxis * Along;
		if (Sideways.Size() > kFootprintUu)
		{
			// Standing beside this rail rather than on it.
			continue;
		}

		// Never a shove backwards: a crate that is somehow already too close stays
		// where it is instead of being pulled away.
		if (Direction > 0.0 && Along >= Mine)
		{
			Wanted = FMath::Min(Wanted, FMath::Max(Mine, Along - kFootprintUu));
		}
		else if (Direction < 0.0 && Along <= Mine)
		{
			Wanted = FMath::Max(Wanted, FMath::Min(Mine, Along + kFootprintUu));
		}
	}

	const double Param =
		FMath::Clamp(Wanted, 0.0, static_cast<double>(RailLengthUu));
	const FVector Slid = RailAnchor + RailAxis * Param;
	SetActorLocation(FVector(Slid.X, Slid.Y, RailAnchor.Z), /*bSweep=*/true);
}
