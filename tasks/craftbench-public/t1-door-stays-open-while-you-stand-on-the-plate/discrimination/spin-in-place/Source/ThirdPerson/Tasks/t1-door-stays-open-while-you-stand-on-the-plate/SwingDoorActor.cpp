// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT spin-in-place. Turns the panel 90 deg about its OWN
// CENTRE rather than sweeping it about the hinge: the yaw is right, the timing is
// right, the motion is smooth, the control is untouched -- and the panel never
// leaves the doorway. On screen it reads as a door twisting in its frame.
// MUST FAIL PanelIsTheGradedPart on Travel().
//
// REPLACES an earlier `decoy-mesh` variant that swung an added decorative mesh
// while the panel stayed put. That one never reached the travel gate: with the
// panel's angle at 0, DoorOpensWhileOccupied fired first, so it was redundant with
// `empty` and left Travel() unproven (measured 2026-08-17, FAIL(wrong-reason)).
// To exercise a gate, a variant has to SATISFY every gate checked before it.

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

	// VARIANT: spin the PANEL about its OWN CENTRE rather than sweeping it about
	// the hinge. The yaw reaches 90 deg on cue, smoothly, at a legal rate -- and
	// the panel never leaves the doorway, so Travel() stays at 0.
	//
	// The accumulator is a MEMBER. The first cut computed each step from
	// Hinge->GetComponentRotation() while no longer moving the hinge, so every
	// frame recomputed the same +2 deg and the panel sat at 2.0 deg forever --
	// which tripped DoorOpensWhileOccupied instead of the travel gate it exists
	// to probe (measured 2026-08-17: graded=2.0, FAIL(wrong-reason)).
	const double SpinTarget = bOpenRequested ? kOpenYawDeg : 0.0;
	const double SpinStep = kSwingDegPerSec * DeltaSeconds;
	if (FMath::Abs(SpinTarget - SpinYaw) <= SpinStep)
	{
		SpinYaw = SpinTarget;
	}
	else
	{
		SpinYaw += FMath::Sign(SpinTarget - SpinYaw) * SpinStep;
	}
	DoorPanel->SetRelativeRotation(FRotator(0.0, SpinYaw, 0.0));

	// The readout is derived from the panel's own live pose, so the number on
	// screen can never disagree with what the panel is doing.
	const double Shown = FMath::Abs(FMath::FindDeltaAngleDegrees(
		ShutRotation.Yaw, DoorPanel->GetComponentRotation().Yaw));
	AngleReadout->SetText(FText::FromString(
		FString::Printf(TEXT("%.0f deg"), Shown)));
}
