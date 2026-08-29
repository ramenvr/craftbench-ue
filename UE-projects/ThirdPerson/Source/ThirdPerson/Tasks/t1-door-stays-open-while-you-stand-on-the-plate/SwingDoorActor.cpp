// Copyright CraftBench. All Rights Reserved.

#include "SwingDoorActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "UObject/ConstructorHelpers.h"

ASwingDoorActor::ASwingDoorActor()
{
	PrimaryActorTick.bCanEverTick = true;

	Hinge = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	SetRootComponent(Hinge);

	DoorPanel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DoorPanel"));
	DoorPanel->SetupAttachment(Hinge);
	DoorPanel->SetRelativeLocation(FVector(0.0f, 100.0f, 130.0f));
	DoorPanel->SetRelativeScale3D(FVector(0.2f, 2.0f, 2.6f));
	DoorPanel->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		DoorPanel->SetStaticMesh(CubeMesh.Object);
	}

	AngleReadout = CreateDefaultSubobject<UTextRenderComponent>(TEXT("AngleReadout"));
	AngleReadout->SetupAttachment(Hinge);
	AngleReadout->SetRelativeLocation(FVector(0.0f, 100.0f, 300.0f));
	AngleReadout->SetHorizontalAlignment(EHTA_Center);
	AngleReadout->SetWorldSize(28.0f);
	AngleReadout->SetText(FText::FromString(TEXT("0 deg")));
	// Absolute rotation so the number stays readable from the camera's side as the
	// hinge sweeps; parented rotation would swing the text away with the panel.
	AngleReadout->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("SwingDoor")));
}

void ASwingDoorActor::BeginPlay()
{
	Super::BeginPlay();
	ShutRotation = DoorPanel ? DoorPanel->GetComponentRotation() : FRotator::ZeroRotator;
	ShutHingeYaw = Hinge ? Hinge->GetComponentRotation().Yaw : 0.0;
	if (AngleReadout)
	{
		AngleReadout->SetWorldRotation(FRotator(0.0, 180.0, 0.0));
	}
}

void ASwingDoorActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (AngleReadout == nullptr || DoorPanel == nullptr)
	{
		return;
	}

	// Read the angle off the panel's own live pose, so the number on screen can
	// never disagree with what the panel is actually doing. Nothing here moves
	// the door.
	const double Shown = FMath::Abs(FMath::FindDeltaAngleDegrees(
		ShutRotation.Yaw, DoorPanel->GetComponentRotation().Yaw));
	AngleReadout->SetText(FText::FromString(
		FString::Printf(TEXT("%.0f deg"), Shown)));
}
