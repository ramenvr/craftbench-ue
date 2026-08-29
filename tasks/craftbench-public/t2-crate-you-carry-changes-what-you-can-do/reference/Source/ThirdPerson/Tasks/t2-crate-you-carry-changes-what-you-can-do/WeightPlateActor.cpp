// Copyright CraftBench. All Rights Reserved.

#include "WeightPlateActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "HaulCrateActor.h"
#include "Kismet/GameplayStatics.h"
#include "LiftDoorActor.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm: a 900 x 900 x 20 cm pad.
	const FVector kPadScale(9.0f, 9.0f, 0.2f);
	const TCHAR* const kPadMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray");

	// Stated in the brief: a crate counts when its middle is over the pad and its
	// underside is within 12 cm of the pad's surface. Both halves matter -- the
	// height half is what stops a crate merely carried OVER the pad from counting.
	constexpr double kRestingWithinCm = 12.0;

	/** An actor's own solid box. COLLIDING components only, so a floating readout
	 *  or a label can never widen it. */
	FBox SolidBox(const AActor* A)
	{
		return A != nullptr ? A->GetComponentsBoundingBox(false) : FBox(ForceInit);
	}
}

AWeightPlateActor::AWeightPlateActor()
{
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	SetRootComponent(Pad);
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}
	Pad->SetRelativeScale3D(kPadScale);
	Pad->SetMobility(EComponentMobility::Movable);
	Pad->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kPadMaterial);
	if (Look.Succeeded())
	{
		Pad->SetMaterial(0, Look.Object);
	}

	HoldLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("HoldLabel"));
	HoldLabel->SetupAttachment(Pad);
	// Divided back out of the pad's scale so the sign stands 200 cm over the pad
	// however the pad is scaled.
	HoldLabel->SetRelativeLocation(FVector(0.0f, 0.0f, 200.0f / kPadScale.Z));
	HoldLabel->SetRelativeScale3D(FVector(1.0f / kPadScale.X, 1.0f / kPadScale.Y,
		1.0f / kPadScale.Z));
	HoldLabel->SetHorizontalAlignment(EHTA_Center);
	HoldLabel->SetWorldSize(70.0f);
	HoldLabel->SetTextRenderColor(FColor(150, 220, 255));
	HoldLabel->SetText(FText::FromString(TEXT("holds from")));
	HoldLabel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	HoldLabel->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("WeightPlate")));
}

void AWeightPlateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// ---- WHAT IS RESTING ON THE PAD, worked out fresh every frame ----
	// A SET, not a flag and not one remembered occupant: lifting one of two crates
	// off has to leave the other one still weighing on the plate.
	const FBox PadBox = SolidBox(this);
	double Total = 0.0;
	if (PadBox.IsValid != 0)
	{
		TArray<AActor*> Crates;
		UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("HaulCrate")),
			Crates);
		for (const AActor* C : Crates)
		{
			const AHaulCrateActor* const Crate = Cast<AHaulCrateActor>(C);
			if (Crate == nullptr)
			{
				continue;
			}
			const FBox Box = SolidBox(Crate);
			if (Box.IsValid == 0)
			{
				continue;
			}
			const FVector Middle = Crate->GetActorLocation();
			const bool bOverPad =
				Middle.X >= PadBox.Min.X && Middle.X <= PadBox.Max.X &&
				Middle.Y >= PadBox.Min.Y && Middle.Y <= PadBox.Max.Y;
			const bool bSittingOnIt =
				FMath::Abs(Box.Min.Z - PadBox.Max.Z) <= kRestingWithinCm;
			if (bOverPad && bSittingOnIt)
			{
				// Read NOW, not remembered: the yard re-prices itself part way
				// through and a copy taken at BeginPlay goes stale.
				Total += static_cast<double>(Crate->MassKg);
			}
		}
	}
	RestingLoadKg = static_cast<float>(Total);

	// ---- THIS plate's own number, and THIS plate's own door ----
	// A person standing here is not cargo: only crates were ever counted above.
	if (ALiftDoorActor* const Door = Cast<ALiftDoorActor>(LinkedDoor))
	{
		Door->SetHeldOpen(RestingLoadKg >= MinimumHoldKg);
	}

	if (HoldLabel == nullptr)
	{
		return;
	}
	// Derived from the property every frame, so a re-priced plate repaints itself.
	HoldLabel->SetText(FText::FromString(
		FString::Printf(TEXT("holds from %.0f kg"), MinimumHoldKg)));
	HoldLabel->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
}
