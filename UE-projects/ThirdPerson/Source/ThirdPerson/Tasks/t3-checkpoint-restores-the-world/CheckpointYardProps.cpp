// Copyright CraftBench. All Rights Reserved.
//
// The yard's props. All supplied, all working, none of them deciding anything.
//
// Every trigger volume in here is at least 200 uu deep along the way somebody walks
// through it. That is not decoration: the graded run is replayed at 20 FPS as well as
// 60, and at 20 FPS a walking character advances 25 uu per frame, so a shallow volume
// is one somebody can step straight over without ever overlapping it.
//
// Nothing here hangs a volume off a SCALED mesh. A volume parented to a mesh inherits
// that mesh's scale, and a 2.4x plate would silently make its own trigger 2.4x wide;
// every volume hangs off a plain root instead, so the numbers above are the numbers
// you get.

#include "CheckpointYardProps.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kArmedIntensity = 9000.0f;

	/** The leaf stands 340 uu tall and is anchored at its middle; a capsule dropped
	 *  60 uu above a pad's own origin lands on the slab rather than inside it. Both
	 *  numbers live here once so the two places SetOpen moves between and the spot
	 *  GetRespawnTransform hands back are derived, never repeated. */
	constexpr float kLeafHalfHeight = 170.0f;
	constexpr float kRespawnLiftUu = 60.0f;

	FString Bare(int32 N)
	{
		// A BARE number on the face. FText::AsNumber would group thousands, and a
		// face nobody can parse is a face nobody can check.
		return FString::FromInt(N);
	}

	/** True only for the pawn the player is possessing. Every prop reacts to exactly
	 *  that and to nothing else, so a stray physics body rolling over a plate cannot
	 *  open a door. */
	bool IsThePlayer(const UObject* Ctx, const AActor* Who)
	{
		if (Who == nullptr)
		{
			return false;
		}
		const APawn* const Pawn = UGameplayStatics::GetPlayerPawn(Ctx, 0);
		return Pawn != nullptr && Pawn == Who;
	}
}

// ---------------------------------------------------------------------------
// ACheckpointStandActor
// ---------------------------------------------------------------------------

ACheckpointStandActor::ACheckpointStandActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DarkLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	Trigger->SetBoxExtent(FVector(170.0f, 170.0f, 110.0f));
	Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Trigger->SetGenerateOverlapEvents(true);
	Trigger->SetMobility(EComponentMobility::Movable);

	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	Pad->SetupAttachment(Trigger);
	Pad->SetRelativeLocation(FVector(0.0f, 0.0f, -102.0f));
	Pad->SetRelativeScale3D(FVector(3.4f, 3.4f, 0.16f));
	Pad->SetCollisionProfileName(TEXT("BlockAll"));
	Pad->SetMobility(EComponentMobility::Movable);
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}
	if (DarkLook.Succeeded())
	{
		Pad->SetMaterial(0, DarkLook.Object);
	}

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Trigger);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 170.0f));
	Lamp->SetLightColor(FLinearColor(0.22f, 1.0f, 0.5f));
	Lamp->SetIntensity(0.0f);
	Lamp->SetAttenuationRadius(1400.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName(TEXT("CheckpointStand")));
}

void ACheckpointStandActor::BeginPlay()
{
	Super::BeginPlay();

	// Dark from the first frame, whatever the editor left behind. Nothing here says
	// this pad should be the one; it just starts honest.
	SetArmed(false);

	if (Trigger != nullptr)
	{
		Trigger->OnComponentBeginOverlap.AddDynamic(
			this, &ACheckpointStandActor::OnTriggerBegin);
	}
}

void ACheckpointStandActor::OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other,
	UPrimitiveComponent* OtherComp, int32 BodyIndex, bool bFromSweep,
	const FHitResult& Sweep)
{
	if (!IsThePlayer(this, Other))
	{
		return;
	}
	// Announce, and stop. The pad does not light itself, does not put another pad
	// out, and remembers nothing.
	OnStoodOn.Broadcast(this);
}

void ACheckpointStandActor::SetArmed(bool bNewArmed)
{
	bArmed = bNewArmed;
	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(bNewArmed ? kArmedIntensity : 0.0f);
	}
}

FTransform ACheckpointStandActor::GetRespawnTransform() const
{
	// Clear of the slab, so a capsule put here stands ON the pad rather than inside
	// it, and facing the way the pad faces.
	return FTransform(GetActorRotation(),
		GetActorLocation() + FVector(0.0f, 0.0f, kRespawnLiftUu));
}

// ---------------------------------------------------------------------------
// ALatchDoorActor
// ---------------------------------------------------------------------------

ALatchDoorActor::ALatchDoorActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GlowLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GreyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"));

	Frame = CreateDefaultSubobject<USceneComponent>(TEXT("Frame"));
	SetRootComponent(Frame);
	Frame->SetMobility(EComponentMobility::Movable);

	Leaf = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Leaf"));
	Leaf->SetupAttachment(Frame);
	Leaf->SetRelativeLocation(FVector(0.0f, 0.0f, kLeafHalfHeight));
	Leaf->SetRelativeScale3D(FVector(4.0f, 0.4f, 3.4f));
	Leaf->SetCollisionProfileName(TEXT("BlockAll"));
	Leaf->SetMobility(EComponentMobility::Movable);

	Plate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plate"));
	Plate->SetupAttachment(Frame);
	Plate->SetRelativeScale3D(FVector(2.4f, 2.4f, 0.16f));
	Plate->SetCollisionProfileName(TEXT("BlockAll"));
	Plate->SetMobility(EComponentMobility::Movable);

	if (CubeMesh.Succeeded())
	{
		Leaf->SetStaticMesh(CubeMesh.Object);
		Plate->SetStaticMesh(CubeMesh.Object);
	}
	if (GlowLook.Succeeded())
	{
		Leaf->SetMaterial(0, GlowLook.Object);
	}
	if (GreyLook.Succeeded())
	{
		Plate->SetMaterial(0, GreyLook.Object);
	}

	PlateTrigger = CreateDefaultSubobject<UBoxComponent>(TEXT("PlateTrigger"));
	PlateTrigger->SetupAttachment(Frame);
	PlateTrigger->SetBoxExtent(FVector(130.0f, 130.0f, 115.0f));
	PlateTrigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	PlateTrigger->SetGenerateOverlapEvents(true);
	PlateTrigger->SetMobility(EComponentMobility::Movable);

	PlaceThePlate();

	Tags.Add(FName(TEXT("LatchDoor")));
}

void ALatchDoorActor::PlaceThePlate()
{
	if (Plate != nullptr)
	{
		Plate->SetRelativeLocation(PlateOffsetUu + FVector(0.0f, 0.0f, 8.0f));
	}
	if (PlateTrigger != nullptr)
	{
		PlateTrigger->SetRelativeLocation(PlateOffsetUu + FVector(0.0f, 0.0f, 115.0f));
	}
}

void ALatchDoorActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	PlaceThePlate();
	// Keep the picture honest in the editor too: an unplayed door is a shut door.
	if (Leaf != nullptr)
	{
		Leaf->SetWorldLocation(bOpen ? GetLeafOpenLocation() : GetLeafShutLocation());
	}
}

void ALatchDoorActor::BeginPlay()
{
	Super::BeginPlay();

	PlaceThePlate();
	SetOpen(false);

	if (PlateTrigger != nullptr)
	{
		PlateTrigger->OnComponentBeginOverlap.AddDynamic(
			this, &ALatchDoorActor::OnPlateBegin);
	}
}

FVector ALatchDoorActor::GetLeafShutLocation() const
{
	return GetActorLocation()
		+ GetActorQuat().RotateVector(FVector(0.0f, 0.0f, kLeafHalfHeight));
}

FVector ALatchDoorActor::GetLeafOpenLocation() const
{
	return GetLeafShutLocation()
		+ GetActorQuat().RotateVector(FVector(0.0f, OpenSlideUu, 0.0f));
}

void ALatchDoorActor::SetOpen(bool bNewOpen)
{
	bOpen = bNewOpen;
	if (Leaf != nullptr)
	{
		// One step, two places. There is no sliding pose to catch the leaf in, so
		// "where is this door" always has an answer.
		Leaf->SetWorldLocation(bNewOpen ? GetLeafOpenLocation() : GetLeafShutLocation());
	}
}

void ALatchDoorActor::OnPlateBegin(UPrimitiveComponent* Comp, AActor* Other,
	UPrimitiveComponent* OtherComp, int32 BodyIndex, bool bFromSweep,
	const FHitResult& Sweep)
{
	if (!IsThePlayer(this, Other))
	{
		return;
	}
	if (bOpen)
	{
		// Already latched. Standing on the plate of an open door does nothing.
		return;
	}
	SetOpen(true);
}

// ---------------------------------------------------------------------------
// ACoinPickupActor
// ---------------------------------------------------------------------------

ACoinPickupActor::ACoinPickupActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GlowLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GreyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"));

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	Trigger->SetBoxExtent(FVector(130.0f, 130.0f, 120.0f));
	Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Trigger->SetGenerateOverlapEvents(true);
	// MOVABLE, and the root: the whole coin -- stand, coin and volume -- travels as
	// one piece, and a placed actor whose root is static logs a mobility error the
	// moment anything moves it, which PIE scores as a failed test.
	Trigger->SetMobility(EComponentMobility::Movable);

	Stand = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Stand"));
	Stand->SetupAttachment(Trigger);
	Stand->SetRelativeLocation(FVector(0.0f, 0.0f, -70.0f));
	Stand->SetRelativeScale3D(FVector(0.6f, 0.6f, 1.0f));
	Stand->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Stand->SetMobility(EComponentMobility::Movable);

	Coin = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Coin"));
	Coin->SetupAttachment(Trigger);
	Coin->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
	Coin->SetRelativeRotation(FRotator(0.0f, 0.0f, 90.0f));
	Coin->SetRelativeScale3D(FVector(0.7f, 0.7f, 0.12f));
	Coin->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Coin->SetMobility(EComponentMobility::Movable);

	if (CylinderMesh.Succeeded())
	{
		Stand->SetStaticMesh(CylinderMesh.Object);
		Coin->SetStaticMesh(CylinderMesh.Object);
	}
	if (GreyLook.Succeeded())
	{
		Stand->SetMaterial(0, GreyLook.Object);
	}
	if (GlowLook.Succeeded())
	{
		Coin->SetMaterial(0, GlowLook.Object);
	}

	Tags.Add(FName(TEXT("CoinPickup")));
}

void ACoinPickupActor::BeginPlay()
{
	Super::BeginPlay();

	TArray<AActor*> Counters;
	UGameplayStatics::GetAllActorsOfClass(this, ABankCounterActor::StaticClass(), Counters);
	Counter = Counters.Num() > 0 ? Cast<ABankCounterActor>(Counters[0]) : nullptr;

	// On its stand from the first frame, whatever the editor left behind.
	bCollected = false;
	if (Coin != nullptr)
	{
		Coin->SetHiddenInGame(false);
		Coin->SetVisibility(true);
	}

	if (Trigger != nullptr)
	{
		Trigger->OnComponentBeginOverlap.AddDynamic(
			this, &ACoinPickupActor::OnTriggerBegin);
	}
}

void ACoinPickupActor::OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other,
	UPrimitiveComponent* OtherComp, int32 BodyIndex, bool bFromSweep,
	const FHitResult& Sweep)
{
	if (!IsThePlayer(this, Other))
	{
		return;
	}
	Collect();
}

void ACoinPickupActor::Collect()
{
	if (bCollected)
	{
		return;
	}
	bCollected = true;
	if (Coin != nullptr)
	{
		Coin->SetHiddenInGame(true);
		Coin->SetVisibility(false);
	}
	if (Counter != nullptr)
	{
		Counter->SetCarried(Counter->GetCarried() + 1);
	}
}

void ACoinPickupActor::Restore()
{
	// DELIBERATELY silent about the counter. Putting a coin back on its stand and
	// deciding what somebody is now holding are two different questions, and only one
	// of them is the coin's.
	bCollected = false;
	if (Coin != nullptr)
	{
		Coin->SetHiddenInGame(false);
		Coin->SetVisibility(true);
	}
}

// ---------------------------------------------------------------------------
// ABankCounterActor
// ---------------------------------------------------------------------------

ABankCounterActor::ABankCounterActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DarkLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));

	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);
	Anchor->SetMobility(EComponentMobility::Movable);

	Post = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Post"));
	Post->SetupAttachment(Anchor);
	Post->SetRelativeLocation(FVector(300.0f, 0.0f, 150.0f));
	Post->SetRelativeScale3D(FVector(1.0f, 4.4f, 3.0f));
	Post->SetCollisionProfileName(TEXT("BlockAll"));
	Post->SetMobility(EComponentMobility::Movable);
	if (CubeMesh.Succeeded())
	{
		Post->SetStaticMesh(CubeMesh.Object);
	}
	if (DarkLook.Succeeded())
	{
		Post->SetMaterial(0, DarkLook.Object);
	}

	// THE LINE. It sits on the arriving side of the post, so crossing it is walking
	// up to the counter rather than walking into it.
	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	Trigger->SetupAttachment(Anchor);
	Trigger->SetRelativeLocation(FVector(-150.0f, 0.0f, 120.0f));
	Trigger->SetBoxExtent(FVector(140.0f, 320.0f, 120.0f));
	Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Trigger->SetGenerateOverlapEvents(true);
	Trigger->SetMobility(EComponentMobility::Movable);

	// Two bare numbers, big enough to read from across the yard, facing the side
	// somebody arrives from. Set as properties rather than through the setters
	// because a constructor has no render state to dirty yet.
	CarriedText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("CarriedText"));
	CarriedText->SetupAttachment(Anchor);
	CarriedText->SetRelativeLocation(FVector(240.0f, -150.0f, 300.0f));
	CarriedText->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	CarriedText->HorizontalAlignment = EHTA_Center;
	CarriedText->WorldSize = 130.0f;
	CarriedText->TextRenderColor = FColor(255, 220, 90);
	CarriedText->Text = FText::FromString(Bare(0));

	BankedText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("BankedText"));
	BankedText->SetupAttachment(Anchor);
	BankedText->SetRelativeLocation(FVector(240.0f, 150.0f, 300.0f));
	BankedText->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	BankedText->HorizontalAlignment = EHTA_Center;
	BankedText->WorldSize = 130.0f;
	BankedText->TextRenderColor = FColor(120, 230, 255);
	BankedText->Text = FText::FromString(Bare(0));

	Tags.Add(FName(TEXT("BankCounter")));
}

void ABankCounterActor::BeginPlay()
{
	Super::BeginPlay();

	// The yard already has progress on the board when somebody arrives.
	Carried = 0;
	Banked = StartingBanked;
	RefreshFaces();

	if (Trigger != nullptr)
	{
		Trigger->OnComponentBeginOverlap.AddDynamic(
			this, &ABankCounterActor::OnTriggerBegin);
	}
}

void ABankCounterActor::RefreshFaces()
{
	if (CarriedText != nullptr)
	{
		CarriedText->SetText(FText::FromString(Bare(Carried)));
	}
	if (BankedText != nullptr)
	{
		BankedText->SetText(FText::FromString(Bare(Banked)));
	}
}

void ABankCounterActor::SetCarried(int32 NewCarried)
{
	Carried = FMath::Max(0, NewCarried);
	RefreshFaces();
}

void ABankCounterActor::SetBanked(int32 NewBanked)
{
	Banked = FMath::Max(0, NewBanked);
	RefreshFaces();
}

void ABankCounterActor::OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other,
	UPrimitiveComponent* OtherComp, int32 BodyIndex, bool bFromSweep,
	const FHitResult& Sweep)
{
	if (!IsThePlayer(this, Other))
	{
		return;
	}
	if (Carried <= 0)
	{
		// Crossing the line with empty hands is not an event.
		return;
	}
	const int32 Amount = Carried;
	Carried = 0;
	Banked += Amount;
	RefreshFaces();
	OnBanked.Broadcast(Amount, Banked);
}

// ---------------------------------------------------------------------------
// AHazardStripActor
// ---------------------------------------------------------------------------

AHazardStripActor::AHazardStripActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> LavaLook(
		TEXT("/Game/Variant_Combat/Materials/M_Lava"));

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	Trigger->SetBoxExtent(FVector(700.0f, 300.0f, 60.0f));
	Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Trigger->SetGenerateOverlapEvents(true);
	Trigger->SetMobility(EComponentMobility::Movable);

	Strip = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Strip"));
	Strip->SetupAttachment(Trigger);
	Strip->SetRelativeLocation(FVector(0.0f, 0.0f, -55.0f));
	Strip->SetRelativeScale3D(FVector(14.0f, 6.0f, 0.1f));
	// FLAT AND NON-BLOCKING: hot floor is walked OVER, never bumped into, so nobody
	// can be stopped short of a hazard they were sent at.
	Strip->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Strip->SetMobility(EComponentMobility::Movable);
	if (CubeMesh.Succeeded())
	{
		Strip->SetStaticMesh(CubeMesh.Object);
	}
	if (LavaLook.Succeeded())
	{
		Strip->SetMaterial(0, LavaLook.Object);
	}

	Tags.Add(FName(TEXT("HazardStrip")));
}

void AHazardStripActor::BeginPlay()
{
	Super::BeginPlay();

	if (Trigger != nullptr)
	{
		Trigger->OnComponentBeginOverlap.AddDynamic(
			this, &AHazardStripActor::OnTriggerBegin);
	}
}

void AHazardStripActor::OnTriggerBegin(UPrimitiveComponent* Comp, AActor* Other,
	UPrimitiveComponent* OtherComp, int32 BodyIndex, bool bFromSweep,
	const FHitResult& Sweep)
{
	if (!IsThePlayer(this, Other))
	{
		return;
	}
	// It reports. It does not move anybody and it does not put anything back.
	OnLethalTouch.Broadcast(Other);
}
