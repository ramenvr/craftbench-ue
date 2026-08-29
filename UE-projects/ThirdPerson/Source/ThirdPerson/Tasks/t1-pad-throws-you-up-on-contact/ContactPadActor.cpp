// Copyright CraftBench. All Rights Reserved.

#include "ContactPadActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

AContactPadActor::AContactPadActor()
{
	PrimaryActorTick.bCanEverTick = false;

	// The plate: 400 x 400 x 20 cm, flush with the floor. The engine cube is
	// 100 cm to a side, so the scale below is the size in metres.
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

	// The region standing on the plate: 400 x 400 x 500 cm. It reports what
	// enters and leaves it, and lets anything walk straight through.
	Region = CreateDefaultSubobject<UBoxComponent>(TEXT("Region"));
	Region->SetupAttachment(Plate);
	Region->SetBoxExtent(FVector(200.0f, 200.0f, 250.0f));
	Region->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Region->SetGenerateOverlapEvents(true);
	// The region hangs off the plate, so the plate's (4, 4, 0.2) scale
	// multiplies both numbers below. They are chosen to cancel it:
	//   scale    (4, 4, 0.2) * (0.25, 0.25, 5.0) = (1, 1, 1)  -> the extent
	//            above is already in centimetres, unscaled.
	//   location plate top is 0.2 * 50 = 10 cm up, and the region is 250 cm
	//            half-height, so its centre belongs at 260 cm world; in the
	//            plate's own space that is 260 / 0.2 = 1300.
	// Change either line and the other has to move with it.
	Region->SetRelativeScale3D(FVector(0.25f, 0.25f, 5.0f));
	Region->SetRelativeLocation(FVector(0.0f, 0.0f, 1300.0f));

	// How the verifier finds this pad. A subclass or a rename keeps the tag.
	Tags.Add(FName(TEXT("ContactPad")));
}
