// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT snap-open. Correct in every other respect - open while
// occupied, shut when vacated, both cycles, right angle, control untouched - but
// it TELEPORTS to the pose in a single frame. MUST FAIL DoorSwingsSmoothly on the
// frame it snaps: 90 deg in one 60 Hz frame is 5400 deg/s against a 720 ceiling.

#include "SwingDoorActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// Where "open" is, and how fast the door gets there.
	//
	// 90 degrees is what the level asks for. The rate is chosen against the two
	// limits the level states rather than picked by feel:
	//
	//   angular  120 deg/s              vs the 720 deg/s ceiling      -> 6x under
	//   linear   120 deg/s at the panel's 100 cm hinge offset
	//            = 100 * (120 * pi/180) = 209 cm/s
	//                                    vs the 3000 cm/s ceiling     -> 14x under
	//   time     90 / 120 = 0.75 s      vs the 2 s the level allows   -> 2.7x under
	//
	// So the swing is unmistakably a travel rather than a snap, and it still
	// settles well inside the deadline at both frame rates the task is graded at.
	constexpr double kOpenYawDeg = 90.0;
	constexpr double kSwingDegPerSec = 120.0;
}

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

void ASwingDoorActor::SetOpenRequested(bool bWantOpen)
{
	bOpenRequested = bWantOpen;
}

void ASwingDoorActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Hinge == nullptr || DoorPanel == nullptr)
	{
		return;
	}

	// RATE-BASED, not per-frame. The task is graded at 60 Hz AND 20 Hz, so a
	// fixed increment per tick would take three times as long at the lower rate
	// and miss its own 2-second deadline. Multiplying by DeltaSeconds makes the
	// swing take 0.75 s of world time at either.
	// VARIANT: teleport straight to the target pose in one frame.
	FRotator Now = Hinge->GetComponentRotation();
	Now.Yaw = ShutHingeYaw + (bOpenRequested ? 90.0 : 0.0);
	Hinge->SetWorldRotation(Now);

	// The readout is derived from the panel's own live pose, so the number on
	// screen can never disagree with what the panel is doing.
	const double Shown = FMath::Abs(FMath::FindDeltaAngleDegrees(
		ShutRotation.Yaw, DoorPanel->GetComponentRotation().Yaw));
	AngleReadout->SetText(FText::FromString(
		FString::Printf(TEXT("%.0f deg"), Shown)));
}
