// Copyright CraftBench. All Rights Reserved.

#include "ContactPadActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The throw. Solving the parabola against the project's own gravity
	// (980 cm/s^2 down) rather than picking a number and hoping:
	//
	//   apex     = v^2 / (2g) = 900^2 / (2 * 980) = 413 cm   (asked: >= 300)
	//   air time = 2v / g     = 2 * 900 / 980     = 1.84 s   (asked: >= 1.0,
	//                                                         and <= 4.0)
	//
	// 900 rather than the 767 that just clears 300 cm, so the throw is visibly
	// past the marked band on the post instead of grazing it, and so a slower
	// frame or a slightly different capsule cannot bring it under the floor.
	// The stock character's own jump is 700, which reaches only 250 cm — a
	// solution that simply re-used the jump impulse would miss.
	constexpr float kThrowSpeed = 900.0f;
}

AContactPadActor::AContactPadActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Plate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plate"));
	SetRootComponent(Plate);
	Plate->SetRelativeScale3D(FVector(4.0f, 4.0f, 0.2f));
	Plate->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Plate->SetStaticMesh(CubeMesh.Object);
	}

	Region = CreateDefaultSubobject<UBoxComponent>(TEXT("Region"));
	Region->SetupAttachment(Plate);
	Region->SetBoxExtent(FVector(200.0f, 200.0f, 250.0f));
	Region->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Region->SetGenerateOverlapEvents(true);
	Region->SetRelativeScale3D(FVector(0.25f, 0.25f, 5.0f));
	Region->SetRelativeLocation(FVector(0.0f, 0.0f, 1300.0f));

	Tags.Add(FName(TEXT("ContactPad")));
}

void AContactPadActor::BeginPlay()
{
	Super::BeginPlay();

	if (Region)
	{
		Region->OnComponentBeginOverlap.AddDynamic(
			this, &AContactPadActor::OnRegionEntered);
	}
}

void AContactPadActor::OnRegionEntered(UPrimitiveComponent* /*OverlappedComponent*/,
                                       AActor* OtherActor,
                                       UPrimitiveComponent* /*OtherComp*/,
                                       int32 /*OtherBodyIndex*/,
                                       bool /*bFromSweep*/,
                                       const FHitResult& /*SweepResult*/)
{
	ACharacter* const Arrival = Cast<ACharacter>(OtherActor);
	if (Arrival == nullptr)
	{
		return;
	}

	// One arrival is one throw: this fires on ENTERING the region, so a
	// character that stays inside it for the whole flight is not thrown again
	// on the way up or down. Walking out and back in is a new arrival, and is
	// meant to throw again.
	//
	// Horizontal velocity is left alone (bXYOverride = false) so the throw
	// carries the character forward along the lane and it lands past the pad,
	// which is what a person watching expects a launch pad to do. Only the
	// vertical component is replaced.
	Arrival->LaunchCharacter(FVector(0.0f, 0.0f, kThrowSpeed),
		/*bXYOverride=*/false, /*bZOverride=*/true);
}
