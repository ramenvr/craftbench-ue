// Copyright CraftBench. All Rights Reserved.

#include "LiftDoorActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm.
	const FVector kPanelScale(0.4f, 4.0f, 4.0f);   // 40 x 400 x 400 cm slab
	const FVector kPostScale(0.6f, 0.6f, 7.5f);    // 60 x 60 x 750 cm posts
	const FVector kLintelScale(0.6f, 5.2f, 0.4f);  // 60 x 520 x 40 cm head
	constexpr double kPostY = 230.0;
	// The yard calls a door open at 250 cm of lift and shut within 20 cm of home.
	constexpr double kOpenLiftCm = 320.0;
	constexpr double kLiftSpeedCmS = 400.0;
	const TCHAR* const kFrameMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02");
	const TCHAR* const kPanelMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

ALiftDoorActor::ALiftDoorActor()
{
	// Ticks for the readout only. Nothing here moves the slab.
	PrimaryActorTick.bCanEverTick = true;

	Frame = CreateDefaultSubobject<USceneComponent>(TEXT("Frame"));
	SetRootComponent(Frame);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> FrameLook(kFrameMaterial);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PanelLook(kPanelMaterial);

	// Unrolled rather than hidden behind a helper: CreateDefaultSubobject has to
	// run in the constructor's own scope, and this is the one thing a reader of
	// this file needs to be able to see at a glance.
	PostLeft = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PostLeft"));
	PostRight = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PostRight"));
	Lintel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Lintel"));
	// THE SLAB -- resolved by the NAME "Panel", never by enumeration order.
	Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));

	UStaticMeshComponent* const Parts[4] = { PostLeft, PostRight, Lintel, Panel };
	const FVector Scales[4] = { kPostScale, kPostScale, kLintelScale, kPanelScale };
	const FVector Locs[4] = {
		FVector(0.0, -kPostY, 375.0),
		FVector(0.0, kPostY, 375.0),
		FVector(0.0, 0.0, 770.0),
		FVector(0.0, 0.0, 200.0)     // the slab fills the doorway, floor to 400 cm
	};
	for (int32 i = 0; i < 4; ++i)
	{
		Parts[i]->SetupAttachment(Frame);
		if (CubeMesh.Succeeded())
		{
			Parts[i]->SetStaticMesh(CubeMesh.Object);
		}
		Parts[i]->SetRelativeScale3D(Scales[i]);
		Parts[i]->SetRelativeLocation(Locs[i]);
		Parts[i]->SetMobility(EComponentMobility::Movable);
		Parts[i]->SetCollisionProfileName(TEXT("BlockAll"));
		UMaterialInterface* const M = (i == 3)
			? (PanelLook.Succeeded() ? PanelLook.Object : nullptr)
			: (FrameLook.Succeeded() ? FrameLook.Object : nullptr);
		if (M != nullptr)
		{
			Parts[i]->SetMaterial(0, M);
		}
	}

	LiftLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("LiftLabel"));
	LiftLabel->SetupAttachment(Frame);
	LiftLabel->SetRelativeLocation(FVector(0.0, 0.0, 900.0));
	LiftLabel->SetHorizontalAlignment(EHTA_Center);
	LiftLabel->SetWorldSize(80.0f);
	LiftLabel->SetTextRenderColor(FColor(255, 180, 90));
	LiftLabel->SetText(FText::FromString(TEXT("up 0 cm")));
	LiftLabel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	LiftLabel->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("LiftDoor")));
}

void ALiftDoorActor::BeginPlay()
{
	Super::BeginPlay();
	ShutPanelZ = Panel != nullptr ? Panel->GetComponentLocation().Z : 0.0;
	ShutPanelRelZ = Panel != nullptr ? Panel->GetRelativeLocation().Z : 0.0;
	bHeldOpen = false;
	if (LiftLabel != nullptr)
	{
		LiftLabel->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
	}
}

void ALiftDoorActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Panel == nullptr)
	{
		return;
	}

	// The slab travels: 320 cm of lift clears the yard's 250 cm "open" line with
	// room to spare, and at 400 cm a second it gets there in 0.8 s, inside the two
	// seconds the yard allows either way. It is driven toward a TARGET rather than
	// set to one, so the same code answers "shut it again" without a second path.
	const double Target = ShutPanelRelZ + (bHeldOpen ? kOpenLiftCm : 0.0);
	const double Rel = Panel->GetRelativeLocation().Z;
	const double Step = kLiftSpeedCmS * static_cast<double>(DeltaSeconds);
	const double Next = FMath::Abs(Target - Rel) <= Step
		? Target
		: Rel + FMath::Sign(Target - Rel) * Step;
	Panel->SetRelativeLocation(FVector(
		Panel->GetRelativeLocation().X, Panel->GetRelativeLocation().Y, Next));

	if (LiftLabel == nullptr)
	{
		return;
	}
	// Measured off the slab's own live pose, so the number on screen is the number
	// the grade reads.
	const double Risen = Panel->GetComponentLocation().Z - ShutPanelZ;
	LiftLabel->SetText(FText::FromString(
		FString::Printf(TEXT("up %.0f cm"), Risen)));
}
