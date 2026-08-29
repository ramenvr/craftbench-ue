// Copyright CraftBench. All Rights Reserved.

#include "BenchBlockActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

ABenchBlockActor::ABenchBlockActor()
{
	PrimaryActorTick.bCanEverTick = true;

	Block = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Block"));
	SetRootComponent(Block);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		Block->SetStaticMesh(CubeMesh.Object);
	}
	// The engine cube is 100 cm, so 0.6 gives the 60 cm block.
	Block->SetRelativeScale3D(FVector(0.6f));
	Block->SetMobility(EComponentMobility::Movable);
	Block->SetCollisionProfileName(TEXT("BlockAll"));
	Block->SetSimulatePhysics(true);
	Block->SetNotifyRigidBodyCollision(true);
	Block->BodyInstance.SetMassOverride(50.0f, true);
	// Left ON deliberately: a block that falls asleep mid-slide stops responding
	// to anything, which is not the behaviour this lane is meant to show.
	Block->BodyInstance.SleepFamily = ESleepFamily::Sensitive;

	Readout = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Readout"));
	Readout->SetupAttachment(Block);
	Readout->SetRelativeLocation(FVector(0.0f, 0.0f, 110.0f));
	Readout->SetHorizontalAlignment(EHTA_Center);
	Readout->SetWorldSize(64.0f);
	Readout->SetTextRenderColor(FColor(255, 240, 120));
	Readout->SetText(FText::FromString(TEXT("off line 0 cm   turned 0 deg")));
	// A shoved block has to come to REST before the next shove, or the pushes
	// accumulate and it slides away for ever - which is what it did with no
	// damping at all (measured 3,502 cm and still moving at 805 cm/s). Identical
	// on both blocks, because they are the same body.
	Block->SetLinearDamping(1.2f);
	Block->SetAngularDamping(0.8f);
}

void ABenchBlockActor::BeginPlay()
{
	Super::BeginPlay();

	// The rail frame, read off the placed marker, so the readout can say how far off
	// the painted line this block is.
	TArray<AActor*> Rails;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("RailLine")), Rails);
	if (Rails.Num() > 0 && Rails[0] != nullptr)
	{
		RailDir = Rails[0]->GetActorForwardVector().GetSafeNormal2D();
		RailRight = FVector::CrossProduct(FVector::UpVector, RailDir).GetSafeNormal2D();
		RailPoint = Rails[0]->GetActorLocation();
		bRailKnown = true;
	}
	StartRotation = GetActorQuat();
	StartLocation = GetActorLocation();
}

void ABenchBlockActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Readout == nullptr || !bRailKnown)
	{
		return;
	}
	// Measured from THIS block's own start line, not from the rail line. For the
	// railed block those are the same thing (it starts on the rail), but the twin
	// starts 300 cm across, so against the rail line it printed 564 cm while the
	// graded quantity was 264 -- a readout that disagrees with the grade is worse
	// than none (measured 2026-08-17).
	const FVector P = GetActorLocation();
	const double OffLine = FVector::DotProduct(P - StartLocation, RailRight);
	const double Turn = FMath::RadiansToDegrees(
		StartRotation.AngularDistance(GetActorQuat()));
	Readout->SetText(FText::FromString(FString::Printf(
		TEXT("off line %.0f cm   turned %.0f deg"), OffLine, Turn)));
	// Keep it upright and facing the same way however the block tumbles. MINUS 90,
	// not plus: the camera plan views this lane from across the rail, and +90 pointed
	// the text's face the other way, so every readout came out MIRRORED and unreadable
	// in the stills (measured 2026-08-17 -- the same trap the pad task hit).
	Readout->SetWorldRotation(FRotator(0.0, RailDir.Rotation().Yaw - 90.0, 0.0));
}
