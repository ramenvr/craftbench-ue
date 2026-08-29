// Copyright CraftBench. All Rights Reserved.

#include "SpikeSlabActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "SpikeLaneCourse.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr double kSpeedCmS = 300.0;   // the level's stated speed
	constexpr float kCostPerTouch = 25.0f;
	constexpr double kEndOfRailCm = 5.0;
	// A touch that ends and begins again inside this is the same touch.
	constexpr double kSameTouchS = 0.6;
}

ASpikeSlabActor::ASpikeSlabActor()
{
	PrimaryActorTick.bCanEverTick = true;

	SlabMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SlabMesh"));
	SetRootComponent(SlabMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		SlabMesh->SetStaticMesh(CubeMesh.Object);
	}
	SlabMesh->SetRelativeScale3D(FVector(2.4f, 2.4f, 2.0f));
	SlabMesh->SetMobility(EComponentMobility::Movable);
	SlabMesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	SlabMesh->SetCollisionResponseToAllChannels(ECR_Overlap);
	SlabMesh->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hazard(
		TEXT("/Game/Variant_Combat/Materials/M_Lava"));
	if (Hazard.Succeeded())
	{
		SlabMesh->SetMaterial(0, Hazard.Object);
	}

	Tags.Add(FName("SlidingSpikes"));
}

void ASpikeSlabActor::BeginPlay()
{
	Super::BeginPlay();

	// The rail is whatever the level's two posts say it is, so nothing here assumes
	// a world axis or a hard-coded length.
	TArray<AActor*> Posts;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("RailPost")), Posts);
	if (Posts.Num() >= 2 && Posts[0] != nullptr && Posts[1] != nullptr)
	{
		const FVector A = Posts[0]->GetActorLocation();
		const FVector B = Posts[1]->GetActorLocation();
		const FVector Here = GetActorLocation();
		// Start heading toward the far post.
		const bool bNearerA = FVector::Dist2D(Here, A) <= FVector::Dist2D(Here, B);
		RailFrom = bNearerA ? A : B;
		RailTo = bNearerA ? B : A;
		Heading = (RailTo - RailFrom).GetSafeNormal2D();
	}

	if (SlabMesh != nullptr)
	{
		SlabMesh->OnComponentBeginOverlap.AddDynamic(this, &ASpikeSlabActor::OnSlabBegin);
		SlabMesh->OnComponentEndOverlap.AddDynamic(this, &ASpikeSlabActor::OnSlabEnd);
	}
}

void ASpikeSlabActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Heading.IsNearlyZero())
	{
		return;
	}
	// Steady speed, never stopping and never changing -- including at the moment it
	// hurts somebody, which is why nothing in the overlap handlers touches motion.
	const FVector Next = GetActorLocation() + Heading * (kSpeedCmS * DeltaSeconds);
	SetActorLocation(Next, false, nullptr, ETeleportType::TeleportPhysics);

	if (FVector::DotProduct(RailTo - GetActorLocation(), Heading) <= kEndOfRailCm)
	{
		Swap(RailFrom, RailTo);
		Heading = (RailTo - RailFrom).GetSafeNormal2D();
	}
}

void ASpikeSlabActor::OnSlabBegin(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	ACharacter* const Character = Cast<ACharacter>(OtherActor);
	UWorld* const World = GetWorld();
	if (Character == nullptr || World == nullptr)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();
	if (const double* const Next = ArmedAt.Find(Character))
	{
		if (Now < *Next)
		{
			return;  // still the same touch
		}
	}
	ArmedAt.Add(Character, Now + kSameTouchS);

	// One 25 per touch, however long the slab stays against the character.
	if (const FFloatProperty* P =
			FindFProperty<FFloatProperty>(Character->GetClass(), TEXT("Health")))
	{
		const float Current = P->GetPropertyValue_InContainer(Character);
		if (Current > 0.0f)
		{
			P->SetPropertyValue_InContainer(Character, FMath::Max(0.0f, Current - kCostPerTouch));
		}
	}
}

void ASpikeSlabActor::OnSlabEnd(UPrimitiveComponent*, AActor*,
	UPrimitiveComponent*, int32)
{
	// Nothing to do: whether the next begin is a new touch is decided by time in
	// OnSlabBegin, not by whether an end happened to fire.
}
