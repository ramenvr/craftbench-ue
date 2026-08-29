// Copyright CraftBench. All Rights Reserved.

#include "FloorMarkActor.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** Comfortably past the "at least 5000" the hall promises a burning lamp. */
	constexpr float kLampLitIntensity = 6500.0f;
	const FLinearColor kLampColour(1.0f, 0.86f, 0.42f);

	/** /Engine/BasicShapes/Cylinder is 100 uu across and 100 uu tall, so an XY scale of
	 *  <radius in uu> / 50 lands the painted circle exactly on the disclosed radius. */
	constexpr float kBasicCylinderRadiusUu = 50.0f;
	constexpr float kRingThicknessUu = 4.0f;
	constexpr float kMastHeightUu = 220.0f;
}

AFloorMarkActor::AFloorMarkActor()
{
	// The mark ticks for ONE reason: to keep its name plate reading whatever it is
	// currently called. It decides nothing, banks nothing and watches nobody.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));

	// An UNSCALED root. Everything below is sized on its own, so that changing the
	// ring can never quietly move the lamp or squash the text.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);

	Ring = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Ring"));
	Ring->SetupAttachment(Anchor);
	if (CylMesh.Succeeded())
	{
		Ring->SetStaticMesh(CylMesh.Object);
	}
	const float RingScaleXY = RingRadiusUu / kBasicCylinderRadiusUu;
	Ring->SetRelativeScale3D(
		FVector(RingScaleXY, RingScaleXY, kRingThicknessUu / 100.0f));
	Ring->SetRelativeLocation(FVector(0.0f, 0.0f, kRingThicknessUu * 0.5f));
	// It is PAINT. Non-colliding on the PROFILE as well as the enum -- a profile left
	// behind is how a decoration quietly becomes a step you trip over.
	Ring->SetCollisionProfileName(TEXT("NoCollision"));
	Ring->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Mast = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mast"));
	Mast->SetupAttachment(Anchor);
	if (CylMesh.Succeeded())
	{
		Mast->SetStaticMesh(CylMesh.Object);
	}
	Mast->SetRelativeScale3D(FVector(0.16f, 0.16f, kMastHeightUu / 100.0f));
	Mast->SetRelativeLocation(FVector(0.0f, 0.0f, kMastHeightUu * 0.5f));
	Mast->SetCollisionProfileName(TEXT("NoCollision"));
	Mast->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Anchor);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, kMastHeightUu + 20.0f));
	Lamp->SetLightColor(kLampColour);
	Lamp->SetAttenuationRadius(1400.0f);
	Lamp->SetCastShadows(false);
	Lamp->SetMobility(EComponentMobility::Movable);
	Lamp->SetIntensity(0.0f);

	Face = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Face"));
	Face->SetupAttachment(Anchor);
	Face->SetRelativeLocation(FVector(0.0f, 0.0f, kMastHeightUu + 90.0f));
	// Yawed so the face reads from the open side of the hall, where the board is.
	Face->SetRelativeRotation(FRotator(0.0f, 90.0f, 0.0f));
	Face->SetHorizontalAlignment(EHTA_Center);
	Face->SetWorldSize(64.0f);
	Face->SetMobility(EComponentMobility::Movable);
	Face->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// The graded numbers have to be READABLE, not merely present.
	Face->SetTextRenderColor(FColor(255, 244, 214));
	Face->SetText(FText::GetEmpty());

	NamePlate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("NamePlate"));
	NamePlate->SetupAttachment(Anchor);
	NamePlate->SetRelativeLocation(FVector(0.0f, 0.0f, kMastHeightUu + 175.0f));
	NamePlate->SetRelativeRotation(FRotator(0.0f, 90.0f, 0.0f));
	NamePlate->SetHorizontalAlignment(EHTA_Center);
	NamePlate->SetWorldSize(46.0f);
	NamePlate->SetMobility(EComponentMobility::Movable);
	NamePlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	NamePlate->SetTextRenderColor(FColor(150, 205, 255));
	NamePlate->SetText(FText::GetEmpty());

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> RingLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (RingLook.Succeeded() && Ring != nullptr)
	{
		Ring->SetMaterial(0, RingLook.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MastLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (MastLook.Succeeded() && Mast != nullptr)
	{
		Mast->SetMaterial(0, MastLook.Object);
	}

	Tags.Add(FName(TEXT("HallMark")));
}

void AFloorMarkActor::BeginPlay()
{
	Super::BeginPlay();

	// Blank face and dark lamp from the first frame, whatever the editor left behind.
	// NOTE that a blank face is NOT what the hall is supposed to read: at the start of
	// a round every mark reads nothing-banked out of its own number, and somebody has
	// to write that.
	if (Face != nullptr)
	{
		Face->SetText(FText::GetEmpty());
	}
	LastShownBankedSeconds = -1.0f;
	LastShownRequiredSeconds = -1.0f;
	bFaceEverWritten = false;

	SetLampLit(false);
	RefreshNamePlate();
}

void AFloorMarkActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The plate follows the name and nothing else happens here.
	if (MarkName != PaintedName)
	{
		RefreshNamePlate();
	}
}

void AFloorMarkActor::RefreshNamePlate()
{
	PaintedName = MarkName;
	if (NamePlate != nullptr)
	{
		NamePlate->SetText(FText::FromString(MarkName.ToString().ToUpper()));
	}
}

void AFloorMarkActor::ShowBank(float BankedSeconds, float RequiredSecondsShown)
{
	LastShownBankedSeconds = BankedSeconds;
	LastShownRequiredSeconds = RequiredSecondsShown;
	bFaceEverWritten = true;

	if (Face != nullptr)
	{
		Face->SetText(FText::FromString(FString::Printf(
			TEXT("%.1f/%.1f"), BankedSeconds, RequiredSecondsShown)));
	}
}

void AFloorMarkActor::SetLampLit(bool bNewLit)
{
	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(bNewLit ? kLampLitIntensity : 0.0f);
		Lamp->SetVisibility(true, /*bPropagateToChildren=*/true);
	}
}

bool AFloorMarkActor::IsLampLit() const
{
	return Lamp != nullptr && Lamp->Intensity > 0.0f;
}

bool AFloorMarkActor::IsInsideRing(const FVector& WorldPoint) const
{
	const FVector Centre = GetActorLocation();
	// FLAT. The hall is level and height plays no part.
	const double DX = WorldPoint.X - Centre.X;
	const double DY = WorldPoint.Y - Centre.Y;
	// Exactly on the ring still counts as on.
	return (DX * DX + DY * DY) <= (static_cast<double>(RingRadiusUu)
		* static_cast<double>(RingRadiusUu));
}

void AFloorMarkActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	// The circle a person SEES and the circle the hall MEANS are the same circle. If
	// this mark's ring number is set to something else in the hall, the paint follows
	// it -- nobody should ever have to guess which of the two is the real one.
	if (Ring != nullptr && RingRadiusUu > 0.0f)
	{
		const float RingScaleXY = RingRadiusUu / kBasicCylinderRadiusUu;
		Ring->SetRelativeScale3D(
			FVector(RingScaleXY, RingScaleXY, kRingThicknessUu / 100.0f));
	}
}
