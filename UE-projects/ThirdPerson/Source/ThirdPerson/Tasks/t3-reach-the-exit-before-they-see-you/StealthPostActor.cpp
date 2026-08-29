// Copyright CraftBench. All Rights Reserved.

#include "StealthPostActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AStealthPostActor::AStealthPostActor()
{
	// Nothing to tick: a post is a place, not a decision.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	// 40 cm across, 300 cm tall, standing with its centre at the actor's location, so
	// the yard places it at half its height.
	Body->SetRelativeScale3D(FVector(0.4f, 0.4f, 3.0f));
	// The PROFILE as well as the enum: on an earlier task set_collision_enabled alone
	// did not survive into the saved level, and a post that quietly stops a line is
	// indistinguishable from a bug in the submission.
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Look.Succeeded())
	{
		Body->SetMaterial(0, Look.Object);
	}
}
