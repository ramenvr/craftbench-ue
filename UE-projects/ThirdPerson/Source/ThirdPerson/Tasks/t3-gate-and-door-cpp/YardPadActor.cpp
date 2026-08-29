// Copyright CraftBench. All Rights Reserved.

#include "YardPadActor.h"

#include "YardCrateActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm on a side; the mat is 240 x 240 x 4 cm.
	const FVector kMatScale(2.4f, 2.4f, 0.04f);
	constexpr double kMatCentreZ = 2.0;

	const FVector kMarkerScale(0.3f, 0.3f, 0.3f);
	constexpr double kMarkerRestZ = 90.0;
	constexpr double kMarkerRaisedZ = 130.0;

	const TCHAR* const kMatMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AYardPadActor::AYardPadActor()
{
	// Ticks for the marker only. Nothing here moves a door.
	PrimaryActorTick.bCanEverTick = true;

	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	SetRootComponent(Mount);
	// The pad itself never moves, but its marker rides up and down, and a static
	// parent would pin it.
	Mount->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MatLook(kMatMaterial);

	Mat = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mat"));
	Mat->SetupAttachment(Mount);
	if (CubeMesh.Succeeded())
	{
		Mat->SetStaticMesh(CubeMesh.Object);
	}
	if (MatLook.Succeeded())
	{
		Mat->SetMaterial(0, MatLook.Object);
	}
	Mat->SetRelativeScale3D(kMatScale);
	Mat->SetRelativeLocation(FVector(0.0, 0.0, kMatCentreZ));
	// Painted on, not built up: nothing is ever stepped onto or bumped into here.
	Mat->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mat->SetCollisionProfileName(TEXT("NoCollision"));

	Marker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Marker"));
	Marker->SetupAttachment(Mount);
	if (SphereMesh.Succeeded())
	{
		Marker->SetStaticMesh(SphereMesh.Object);
	}
	Marker->SetRelativeScale3D(kMarkerScale);
	Marker->SetRelativeLocation(FVector(0.0, 0.0, kMarkerRestZ));
	Marker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Marker->SetCollisionProfileName(TEXT("NoCollision"));

	// Sized generously so nothing standing near the mat goes unnoticed. It reports
	// what comes and goes for anybody who wants to hear it; the question of what is
	// RESTING here is answered by measuring, not by remembering.
	PadVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PadVolume"));
	PadVolume->SetupAttachment(Mount);
	PadVolume->SetBoxExtent(FVector(170.0f, 170.0f, 150.0f));
	PadVolume->SetRelativeLocation(FVector(0.0, 0.0, 150.0));
	PadVolume->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	PadVolume->SetGenerateOverlapEvents(true);

	Tags.Add(FName(TEXT("YardPad")));
}

FVector AYardPadActor::GetPadCentre() const
{
	return Mount != nullptr ? Mount->GetComponentLocation() : GetActorLocation();
}

bool AYardPadActor::IsBodyResting(const AActor* Body) const
{
	if (Body == nullptr)
	{
		return false;
	}

	// A person or a crate. The yard has never cared which, and every pad in it asks
	// the same question the same way.
	const bool bIsBody =
		Body->IsA(APawn::StaticClass()) || Body->IsA(AYardCrateActor::StaticClass());
	if (!bIsBody)
	{
		return false;
	}

	// Measured off the body's own solid shape, so a name floating over a crate or a
	// number floating over a head plays no part.
	FVector Origin = FVector::ZeroVector;
	FVector Extent = FVector::ZeroVector;
	Body->GetActorBounds(/*bOnlyCollidingComponents=*/true, Origin, Extent);
	if (Extent.IsNearlyZero())
	{
		return false;
	}

	const FVector Centre = GetPadCentre();
	if (FVector::Dist2D(Origin, Centre) > ContactRadiusUu)
	{
		return false;
	}

	const double BaseZ = Origin.Z - Extent.Z;
	return FMath::Abs(BaseZ - Centre.Z) <= GroundedBandUu;
}

void AYardPadActor::GetRestingBodies(TArray<AActor*>& OutBodies) const
{
	OutBodies.Reset();

	UWorld* const W = GetWorld();
	if (W == nullptr)
	{
		return;
	}

	// Asked by measuring the two kinds of body that exist in this yard, rather than
	// by remembering what has come and gone. The yard is small, the answer is the
	// same however often it is asked, and it is never one frame out of date.
	for (TActorIterator<APawn> It(W); It; ++It)
	{
		if (IsBodyResting(*It))
		{
			OutBodies.Add(*It);
		}
	}
	for (TActorIterator<AYardCrateActor> It(W); It; ++It)
	{
		if (IsBodyResting(*It))
		{
			OutBodies.Add(*It);
		}
	}
}

bool AYardPadActor::HasAnyRestingBody() const
{
	TArray<AActor*> Resting;
	GetRestingBodies(Resting);
	return Resting.Num() > 0;
}

void AYardPadActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Presentation only: the marker rides up while something is resting here, so a
	// person watching sees the pad register without reading any numbers. Nothing
	// about any door is decided here.
	if (Marker != nullptr)
	{
		Marker->SetRelativeLocation(FVector(
			0.0, 0.0, HasAnyRestingBody() ? kMarkerRaisedZ : kMarkerRestZ));
	}
}
