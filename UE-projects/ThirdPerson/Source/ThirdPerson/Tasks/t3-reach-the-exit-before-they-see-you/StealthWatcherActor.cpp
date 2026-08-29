// Copyright CraftBench. All Rights Reserved.

#include "StealthWatcherActor.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
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
	 *  is laid out with very little to spare at the tightest spot. */
	constexpr double kArriveUu = 6.0;

	constexpr float kLampIntensity = 7000.0f;
	const FLinearColor kLampColour(1.0f, 0.30f, 0.22f);
}

AStealthWatcherActor::AStealthWatcherActor()
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
	// location, the way a character does, so the yard places the watcher at half its
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

	// A cone on the front, laid on its side so it points the way the watcher faces.
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

	HeadLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("HeadLamp"));
	HeadLamp->SetupAttachment(Hull);
	HeadLamp->SetRelativeLocation(FVector(30.0f, 0.0f, 100.0f));
	HeadLamp->SetLightColor(kLampColour);
	HeadLamp->SetIntensity(0.0f);
	HeadLamp->SetAttenuationRadius(1200.0f);
	HeadLamp->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Dark.Succeeded())
	{
		DarkLook = Dark.Object;
		Snout->SetMaterial(0, Dark.Object);
	}

	Tags.Add(FName(TEXT("StealthWatcher")));
}

void AStealthWatcherActor::BeginPlay()
{
	Super::BeginPlay();

	// The watcher starts at its own base pace with its lamp dark. Nothing here ever
	// changes either of them again.
	PaceUuPerSec = BasePaceUuPerSec;
	SetLampLit(false);
	ResolveRound();
}

void AStealthWatcherActor::SetLampLit(bool bNewLit)
{
	bLampLit = bNewLit;
	if (HeadLamp != nullptr)
	{
		HeadLamp->SetIntensity(bNewLit ? kLampIntensity : 0.0f);
	}
	UMaterialInterface* const Look = bNewLit ? LitLook : DarkLook;
	if (Snout != nullptr && Look != nullptr)
	{
		Snout->SetMaterial(0, Look);
	}
}

void AStealthWatcherActor::ResolveRound()
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
	// Walk at the watcher's own height, not the posts'.
	const double Z = GetActorLocation().Z;
	RoundA.Z = Z;
	RoundB.Z = Z;
	bRoundResolved = true;

	// Head for whichever end is further off, so a watcher set down mid-round (or moved
	// onto a new round when the watch changes) starts by walking the long way.
	const FVector Here = GetActorLocation();
	bHeadingToB = FVector::Dist2D(Here, RoundB) >= FVector::Dist2D(Here, RoundA);
}

void AStealthWatcherActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The sergeant can re-tag a watcher mid-night. Notice, and go and find the new
	// round.
	if (!bRoundResolved || ResolvedForTag != RoundTag)
	{
		ResolveRound();
	}
	// A pace of nothing means stand where you are, facing the way you were facing.
	if (!bRoundResolved || DeltaSeconds <= 0.0f || PaceUuPerSec <= 0.0f)
	{
		return;
	}

	const FVector Here = GetActorLocation();
	FVector Target = bHeadingToB ? RoundB : RoundA;
	FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size() <= kArriveUu)
	{
		// Turn round AND keep walking in the same frame: a watcher that stood still
		// for the frame it turned would put a one-frame hole in its own facing, and
		// when a cone edge crosses somebody is the whole arithmetic of this yard.
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
	// Never overshoot: a long frame must not teleport the watcher past the post.
	const double Travel = FMath::Min(Distance, double(PaceUuPerSec) * DeltaSeconds);
	SetActorLocation(Here + Direction * Travel, /*bSweep=*/true);
	SetActorRotation(Direction.Rotation());
}
