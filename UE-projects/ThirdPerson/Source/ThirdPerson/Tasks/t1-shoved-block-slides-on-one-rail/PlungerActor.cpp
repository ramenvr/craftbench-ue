// Copyright CraftBench. All Rights Reserved.

#include "PlungerActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The push, in kg-cm/s. Split 5 parts along the rail, 2 across it and 1 up,
	// and delivered off the block's centre so it also tries to spin it.
	constexpr double kShoveImpulse = 57500.0;
	// Delivered as a FORCE over this many seconds rather than in one frame. Same
	// total push, but the solver never sees a huge single-frame sideways impulse:
	// as an instantaneous impulse the identical shove landed differently depending
	// on the block's state (a measured 311 cm/s one time and 610 cm/s the next) and
	// the harder one tore a constrained block 20 cm off its line before recovering.
	// A plunger shoving something is a push over time anyway.
	constexpr double kShoveSeconds = 0.15;
	const FVector kShoveMix(5.0, 2.0, 1.0);
	// Where on the block the push lands, in the rail's own frame.
	const FVector kShoveOffset(0.0, 25.0, 20.0);
}

APlungerActor::APlungerActor()
{
	PrimaryActorTick.bCanEverTick = true;

	Post = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Post"));
	SetRootComponent(Post);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		Post->SetStaticMesh(CylinderMesh.Object);
	}
	Post->SetRelativeScale3D(FVector(0.5f, 0.5f, 1.6f));
	Post->SetMobility(EComponentMobility::Static);
	Post->SetCollisionProfileName(TEXT("BlockAll"));

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	Trigger->SetupAttachment(Post);
	Trigger->SetBoxExtent(FVector(110.0f, 110.0f, 120.0f));
	Trigger->SetRelativeLocation(FVector(0.0f, 0.0f, 80.0f));
	Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Trigger->SetGenerateOverlapEvents(true);

	Tags.Add(FName("Plunger"));
}

void APlungerActor::BeginPlay()
{
	Super::BeginPlay();

	// The rail bearing comes off the placed rail marker, so the push stays aimed
	// mostly along whatever direction the level painted the rail.
	TArray<AActor*> Rails;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("RailLine")), Rails);
	if (Rails.Num() > 0 && Rails[0] != nullptr)
	{
		RailForward = Rails[0]->GetActorForwardVector().GetSafeNormal2D();
		RailRight = Rails[0]->GetActorRightVector().GetSafeNormal2D();
	}

	if (Trigger != nullptr)
	{
		Trigger->OnComponentBeginOverlap.AddDynamic(this, &APlungerActor::OnTriggerBegin);
		Trigger->OnComponentEndOverlap.AddDynamic(this, &APlungerActor::OnTriggerEnd);
	}
}

void APlungerActor::OnTriggerBegin(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	if (!bArmed || Cast<ACharacter>(OtherActor) == nullptr)
	{
		return;
	}
	bArmed = false;
	ShoveBlocks();
}

void APlungerActor::OnTriggerEnd(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32)
{
	if (Cast<ACharacter>(OtherActor) != nullptr)
	{
		bArmed = true;  // re-arms as soon as the character steps out
	}
}

void APlungerActor::ShoveBlocks()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	// One push, built once, given to every block the same way.
	const FVector Mix = kShoveMix.GetSafeNormal();
	const FVector Impulse = kShoveImpulse *
		(RailForward * Mix.X + RailRight * Mix.Y + FVector::UpVector * Mix.Z);
	const FVector Offset = RailRight * kShoveOffset.Y + FVector::UpVector * kShoveOffset.Z;

	++ShoveCount;
	PushForce = Impulse / kShoveSeconds;
	PushOffset = Offset;
	PushRemaining = kShoveSeconds;

	UE_LOG(LogTemp, Display,
		TEXT("[t1-rail calib] shove #%d begins, |I|=%.0f over %.2f s "
			 "(along=%.2f across=%.2f up=%.2f)"),
		ShoveCount, kShoveImpulse, kShoveSeconds, Mix.X, Mix.Y, Mix.Z);
}

void APlungerActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (PushRemaining <= 0.0 || GetWorld() == nullptr)
	{
		return;
	}
	const double Slice = FMath::Min(static_cast<double>(DeltaSeconds), PushRemaining);
	PushRemaining -= DeltaSeconds;

	// Every block gets the identical push, applied the same way to both.
	for (const FName Tag : {FName(TEXT("RailBlock")), FName(TEXT("TwinBlock"))})
	{
		TArray<AActor*> Blocks;
		UGameplayStatics::GetAllActorsWithTag(GetWorld(), Tag, Blocks);
		for (AActor* Actor : Blocks)
		{
			UPrimitiveComponent* const Body =
				Actor ? Cast<UPrimitiveComponent>(Actor->GetRootComponent()) : nullptr;
			if (Body == nullptr)
			{
				continue;
			}
			Body->AddImpulseAtLocation(PushForce * Slice,
				Body->GetComponentLocation() + PushOffset);
		}
	}
}
