// Copyright CraftBench. All Rights Reserved.

#include "WatchGuardActor.h"

#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** How close to a post counts as having reached it. Small on purpose: it is
	 *  subtracted twice from the usable length of the round, and the yard's geometry
	 *  is checked with only ~120 uu of clearance to spare at the tightest spot. */
	constexpr double kArriveUu = 6.0;
}

AWatchGuardActor::AWatchGuardActor()
{
	// The round is supplied and it walks itself.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone"));

	Hull = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Hull"));
	SetRootComponent(Hull);
	// 70 cm across, 180 cm tall. The actor stands with this capsule's CENTRE at its
	// location, the way a character does, so the yard places the guard at half its
	// height and its feet land on the floor.
	Hull->InitCapsuleSize(35.0f, 90.0f);
	Hull->SetCollisionProfileName(TEXT("BlockAll"));
	Hull->SetMobility(EComponentMobility::Movable);

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Hull);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	Body->SetRelativeScale3D(FVector(0.7f, 0.7f, 1.8f));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (BodyLook.Succeeded())
	{
		Body->SetMaterial(0, BodyLook.Object);
	}

	// A cone on the front, laid on its side so it points the way the guard faces.
	// Attached to the HULL, not the body, so the body's scale does not distort it.
	Snout = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Snout"));
	Snout->SetupAttachment(Hull);
	if (ConeMesh.Succeeded())
	{
		Snout->SetStaticMesh(ConeMesh.Object);
	}
	Snout->SetRelativeScale3D(FVector(0.4f, 0.4f, 0.7f));
	Snout->SetRelativeLocation(FVector(45.0f, 0.0f, 60.0f));
	Snout->SetRelativeRotation(FRotator(-90.0f, 0.0f, 0.0f));
	Snout->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SnoutLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (SnoutLook.Succeeded())
	{
		Snout->SetMaterial(0, SnoutLook.Object);
	}

	Tags.Add(FName("WatchGuard"));
}

void AWatchGuardActor::BeginPlay()
{
	Super::BeginPlay();

	// The guard starts at its own base pace. Nothing here ever changes it again.
	PatrolSpeedUuPerSec = BasePatrolSpeedUu;
	ResolveRound();
}

void AWatchGuardActor::ResolveRound()
{
	bRoundResolved = false;
	ResolvedForTag = RoundTag;

	TArray<AActor*> Posts;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), RoundTag, Posts);
	if (Posts.Num() < 2)
	{
		return;
	}
	// A stable order, so the two ends mean the same thing on every frame and on both
	// sides of a watch change.
	Posts.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetName() < R.GetName();
	});
	RoundA = Posts[0]->GetActorLocation();
	RoundB = Posts[1]->GetActorLocation();
	// Walk at the guard's own height, not the posts'.
	const double Z = GetActorLocation().Z;
	RoundA.Z = Z;
	RoundB.Z = Z;
	bRoundResolved = true;

	// Head for whichever end is further off, so a guard set down mid-round (or moved
	// onto a new round when the watch changes) starts by walking the long way.
	const FVector Here = GetActorLocation();
	bHeadingToB = FVector::Dist2D(Here, RoundB) >= FVector::Dist2D(Here, RoundA);
}

void AWatchGuardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The sergeant can re-tag a guard mid-night. Notice, and go and find the new round.
	if (!bRoundResolved || ResolvedForTag != RoundTag)
	{
		ResolveRound();
	}
	if (!bRoundResolved || DeltaSeconds <= 0.0f || PatrolSpeedUuPerSec <= 0.0f)
	{
		return;
	}

	const FVector Here = GetActorLocation();
	FVector Target = bHeadingToB ? RoundB : RoundA;
	FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size() <= kArriveUu)
	{
		// Turn round AND keep walking in the same frame: a guard that stood still for
		// the frame it turned would put a one-frame hole in its own facing, and the
		// yard's whole arithmetic is about when a cone edge crosses somebody.
		bHeadingToB = !bHeadingToB;
		Target = bHeadingToB ? RoundB : RoundA;
		Flat = FVector(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	}
	const double Distance = Flat.Size();
	if (Distance <= KINDA_SMALL_NUMBER)
	{
		return;
	}

	const FVector Direction = Flat / Distance;
	// Never overshoot: a long frame must not teleport the guard past the post.
	const double Travel = FMath::Min(Distance, double(PatrolSpeedUuPerSec) * DeltaSeconds);
	SetActorLocation(Here + Direction * Travel, /*bSweep=*/true);
	SetActorRotation(Direction.Rotation());
}
