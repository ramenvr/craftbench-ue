// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT throws-everything. NOTE: the reference's own trailing
// LaunchCharacter call had to be DELETED, not just bypassed with an early return --
// UE compiles warnings as errors, so unreachable code is C4702 and fails L1 outright
// (measured 2026-08-17). A variant that does not compile grades as FAIL(skipped),
// which looks exactly like a task whose gates do not discriminate.
// DISCRIMINATION VARIANT throws-everything. The arrival IS thrown correctly, so gates
// 2/3/3b/4/5/6 all pass -- but it throws the bystander too. MUST FAIL gate 7
// (ControlStaysGroundedThroughout). This is the variant that proves the in-scene
// control is load-bearing rather than decoration.

#include "ContactPadActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
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
	// VARIANT: throws EVERY character in the level, not just the one that arrived.
	TArray<AActor*> Everyone;
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), ACharacter::StaticClass(), Everyone);
	for (AActor* A : Everyone)
	{
		if (ACharacter* const C = Cast<ACharacter>(A))
		{
			C->LaunchCharacter(FVector(0.0f, 0.0f, kThrowSpeed), false, true);
		}
	}
	return;
}
