// Copyright CraftBench. All Rights Reserved.

#include "YardBarrierActor.h"

#include "GateLampActor.h"
#include "YardPadActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm on a side.
	const FVector kPostScale(0.6f, 0.6f, 5.2f);     // 60 x 60 x 520 cm
	const FVector kLintelScale(0.6f, 5.0f, 0.4f);   // 60 x 500 x 40 cm
	const FVector kPanelScale(0.2f, 3.8f, 5.0f);    // 20 x 380 x 500 cm
	constexpr double kPostY = 220.0;
	constexpr double kHingeY = -190.0;   // the inner face of the near post
	constexpr double kPanelMidY = 190.0; // half the panel's width, out from the hinge

	const TCHAR* const kFrameMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02");
	const TCHAR* const kPanelMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AYardBarrierActor::AYardBarrierActor()
{
	// Ticks so the panel can travel and the readouts can keep up.
	PrimaryActorTick.bCanEverTick = true;

	Frame = CreateDefaultSubobject<USceneComponent>(TEXT("Frame"));
	SetRootComponent(Frame);
	// Movable throughout: the panel has to be able to swing whatever the level was
	// saved holding, and a static parent would freeze every child under it.
	Frame->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> FrameLook(kFrameMaterial);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PanelLook(kPanelMaterial);

	PostLeft = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PostLeft"));
	PostRight = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PostRight"));
	Lintel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Lintel"));

	UStaticMeshComponent* const Uprights[3] = { PostLeft, PostRight, Lintel };
	const FVector UprightScales[3] = { kPostScale, kPostScale, kLintelScale };
	const FVector UprightLocs[3] = {
		FVector(0.0, -kPostY, 260.0),
		FVector(0.0,  kPostY, 260.0),
		FVector(0.0,   0.0,  540.0)
	};
	for (int32 i = 0; i < 3; ++i)
	{
		Uprights[i]->SetupAttachment(Frame);
		if (CubeMesh.Succeeded())
		{
			Uprights[i]->SetStaticMesh(CubeMesh.Object);
		}
		if (FrameLook.Succeeded())
		{
			Uprights[i]->SetMaterial(0, FrameLook.Object);
		}
		Uprights[i]->SetRelativeScale3D(UprightScales[i]);
		Uprights[i]->SetRelativeLocation(UprightLocs[i]);
		Uprights[i]->SetCollisionProfileName(TEXT("BlockAll"));
	}

	// The hinge carries the panel and nothing else, so a swinging panel never takes
	// a readout with it.
	Hinge = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	Hinge->SetupAttachment(Frame);
	Hinge->SetMobility(EComponentMobility::Movable);
	Hinge->SetRelativeLocation(FVector(0.0, kHingeY, 0.0));

	// THE PANEL. Keep it as the component with this name: where it is pointing is the
	// whole of what the yard shows about whether this barrier is open.
	Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));
	Panel->SetupAttachment(Hinge);
	if (CubeMesh.Succeeded())
	{
		Panel->SetStaticMesh(CubeMesh.Object);
	}
	if (PanelLook.Succeeded())
	{
		Panel->SetMaterial(0, PanelLook.Object);
	}
	Panel->SetRelativeScale3D(kPanelScale);
	Panel->SetRelativeLocation(FVector(0.0, kPanelMidY, 250.0));
	Panel->SetMobility(EComponentMobility::Movable);
	Panel->SetCollisionProfileName(TEXT("BlockAll"));

	AngleReadout = CreateDefaultSubobject<UTextRenderComponent>(TEXT("AngleReadout"));
	AngleReadout->SetupAttachment(Frame);
	AngleReadout->SetRelativeLocation(FVector(0.0, 0.0, 640.0));
	AngleReadout->SetHorizontalAlignment(EHTA_Center);
	AngleReadout->SetWorldSize(60.0f);
	AngleReadout->SetTextRenderColor(FColor(255, 200, 120));
	AngleReadout->SetText(FText::FromString(TEXT("0 deg")));
	AngleReadout->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// Absolute rotation so the number stays readable from the camera's side.
	AngleReadout->SetUsingAbsoluteRotation(true);

	CutPlate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("CutPlate"));
	CutPlate->SetupAttachment(Frame);
	CutPlate->SetRelativeLocation(FVector(0.0, 0.0, 740.0));
	CutPlate->SetHorizontalAlignment(EHTA_Center);
	CutPlate->SetWorldSize(52.0f);
	CutPlate->SetTextRenderColor(FColor(180, 230, 255));
	CutPlate->SetText(FText::FromString(TEXT("--")));
	CutPlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	CutPlate->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("YardBarrier")));
}

void AYardBarrierActor::BeginPlay()
{
	Super::BeginPlay();

	// Square the hinge FIRST, then take the reading. "Shut" is the pose the panel
	// holds from the first frame of play, and it has to mean the same thing whatever
	// pose the level happened to be saved in -- otherwise a barrier could start play
	// already reading as part-open and never be able to get home.
	if (Hinge != nullptr)
	{
		Hinge->SetRelativeRotation(FRotator::ZeroRotator);
	}
	SweptAngleDeg = 0.0;
	ShutPanelYaw = Panel != nullptr ? Panel->GetComponentRotation().Yaw : 0.0;

	if (AngleReadout != nullptr)
	{
		AngleReadout->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
	}
	if (CutPlate != nullptr)
	{
		CutPlate->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
	}

	// Which pads answer for this barrier, and which lamps are bolted to it. The yard
	// is wired as it is laid out and the wiring does not change, so this is worked
	// out once.
	Pads.Reset();
	Lamps.Reset();
	if (UWorld* const W = GetWorld())
	{
		for (TActorIterator<AYardPadActor> It(W); It; ++It)
		{
			if (It->AnsweredBarrier == this)
			{
				Pads.Add(*It);
			}
		}
		for (TActorIterator<AGateLampActor> It(W); It; ++It)
		{
			if (It->LampBarrier == this)
			{
				Lamps.Add(*It);
			}
		}
	}
}

double AYardBarrierActor::GetPanelAngleFromShutDeg() const
{
	if (Panel == nullptr)
	{
		return 0.0;
	}
	return FMath::Abs(FMath::FindDeltaAngleDegrees(
		ShutPanelYaw, Panel->GetComponentRotation().Yaw));
}

void AYardBarrierActor::SetCommandedOpen(bool bOpen)
{
	bHasCommandThisTick = true;
	bCommandedOpen = bOpen;
}

bool AYardBarrierActor::ShouldBeOpen_Implementation() const
{
	// The yard's one rule, as it has always run: any single body resting on any pad
	// that answers for this barrier is enough.
	for (const AYardPadActor* const Pad : Pads)
	{
		if (Pad != nullptr && Pad->HasAnyRestingBody())
		{
			return true;
		}
	}
	return false;
}

void AYardBarrierActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Whoever spoke most recently within this frame decides; with nobody speaking,
	// the yard's own rule does. The barrier never asks who called.
	const bool bWantOpen = bHasCommandThisTick ? bCommandedOpen : ShouldBeOpen();
	bHasCommandThisTick = false;

	DrivePanel(DeltaSeconds, bWantOpen);
	UpdateReadouts();
}

void AYardBarrierActor::DrivePanel(float DeltaSeconds, bool bWantOpen)
{
	if (Hinge == nullptr)
	{
		return;
	}

	// It travels. The panel never jumps: it sweeps toward the pose it should be
	// holding at this barrier's own rate and no faster.
	const double Target = bWantOpen ? OpenAngleDeg : 0.0;
	const double Step = FMath::Max(0.0, TravelRateDegPerSec * static_cast<double>(DeltaSeconds));
	SweptAngleDeg = FMath::Clamp(Target, SweptAngleDeg - Step, SweptAngleDeg + Step);
	Hinge->SetRelativeRotation(FRotator(0.0, SweptAngleDeg, 0.0));
}

void AYardBarrierActor::UpdateReadouts()
{
	// Both readouts are derived from what is actually true right now, so neither can
	// ever disagree with the thing it is describing.
	if (AngleReadout != nullptr)
	{
		AngleReadout->SetText(FText::FromString(
			FString::Printf(TEXT("%.0f deg"), GetPanelAngleFromShutDeg())));
	}

	if (CutPlate != nullptr)
	{
		const FString Wanted =
			(CutForFirstName.IsNone() && CutForSecondName.IsNone())
			? FString(TEXT("--"))
			: FString::Printf(TEXT("%s + %s"),
				*CutForFirstName.ToString(), *CutForSecondName.ToString());
		if (ShownCut != Wanted)
		{
			ShownCut = Wanted;
			CutPlate->SetText(FText::FromString(Wanted));
		}
	}
}
