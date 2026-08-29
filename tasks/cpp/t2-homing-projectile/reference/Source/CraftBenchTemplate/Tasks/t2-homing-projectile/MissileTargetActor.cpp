// Copyright CraftBench. All Rights Reserved.
//
// Reference copy of the AMissileTargetActor scaffold for task
// t2-homing-projectile. Mirrors the substrate scaffold exactly (tick
// disabled, "MissileTarget" identity tag, movable scene root so the fixture
// can relocate it mid-flight) and adds a small cube mesh for review
// visibility only — the verifier asserts tags/transforms, never meshes.

#include "MissileTargetActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

AMissileTargetActor::AMissileTargetActor()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);
	Tags.Add(FName("MissileTarget"));

	// Showcase-visibility only: never asserted by the verifier. Collision is
	// disabled so the cube cannot block the incoming missile's graded flight.
	Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShowcaseVisual"));
	Visual->SetupAttachment(Root);
	Visual->SetMobility(EComponentMobility::Movable);
	Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Visual->SetGenerateOverlapEvents(false);
	Visual->SetRelativeScale3D(FVector(0.4f));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMeshFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMeshFinder.Succeeded())
	{
		Visual->SetStaticMesh(CubeMeshFinder.Object);
	}
}
