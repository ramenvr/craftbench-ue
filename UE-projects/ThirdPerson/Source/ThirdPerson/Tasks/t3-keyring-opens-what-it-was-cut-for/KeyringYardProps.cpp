// Copyright CraftBench. All Rights Reserved.

#include "KeyringYardProps.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* const kCube = TEXT("/Engine/BasicShapes/Cube");
	const TCHAR* const kCylinder = TEXT("/Engine/BasicShapes/Cylinder");
	const TCHAR* const kPlainLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray");
	const TCHAR* const kGlowLook =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");

	// A stand's lamp is lit while the key is still on it.
	constexpr float kStandLampLit = 4000.0f;

	// The panel stands from the floor to 420 uu, so the cube's CENTRE is at 210.
	const FVector kPanelShut(0.0f, 0.0f, 210.0f);

	const FLinearColor kShutColour(1.0f, 0.15f, 0.10f);
	const FLinearColor kOpenColour(0.20f, 1.0f, 0.30f);
	const FLinearColor kKeyColour(1.0f, 0.80f, 0.25f);
}

// ---------------------------------------------------------------------------
// AKeyStandActor
// ---------------------------------------------------------------------------

AKeyStandActor::AKeyStandActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(kCylinder);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kCube);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlainLook(kPlainLook);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GlowLook(kGlowLook);

	// An UNSCALED root at floor level, in the middle of this stand's mat. Everything
	// else hangs off it, so every number below is already in world units and a
	// distance read against the stand's location is a distance to the mat's middle.
	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	SetRootComponent(Mount);
	Mount->SetMobility(EComponentMobility::Movable);

	// A 40 x 40 x 200 post.
	Post = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Post"));
	Post->SetupAttachment(Mount);
	if (CylinderMesh.Succeeded())
	{
		Post->SetStaticMesh(CylinderMesh.Object);
	}
	Post->SetRelativeLocation(FVector(0.0f, 0.0f, 100.0f));
	Post->SetRelativeScale3D(FVector(0.4f, 0.4f, 2.0f));
	Post->SetMobility(EComponentMobility::Movable);
	Post->SetCollisionProfileName(TEXT("BlockAll"));
	if (PlainLook.Succeeded())
	{
		Post->SetMaterial(0, PlainLook.Object);
	}

	// The key floats above the post: a 50 x 20 x 50 nub.
	Key = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Key"));
	Key->SetupAttachment(Mount);
	if (CubeMesh.Succeeded())
	{
		Key->SetStaticMesh(CubeMesh.Object);
	}
	Key->SetRelativeLocation(FVector(0.0f, 0.0f, 260.0f));
	Key->SetRelativeScale3D(FVector(0.5f, 0.2f, 0.5f));
	Key->SetMobility(EComponentMobility::Movable);
	Key->SetCollisionProfileName(TEXT("NoCollision"));
	if (GlowLook.Succeeded())
	{
		Key->SetMaterial(0, GlowLook.Object);
	}
	// How the yard reads a key without caring what anybody called the member.
	Key->ComponentTags.Add(FName(TEXT("Key")));

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Mount);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 330.0f));
	Lamp->SetLightColor(kKeyColour);
	Lamp->SetIntensity(kStandLampLit);
	Lamp->SetAttenuationRadius(900.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName(TEXT("Keyring_Stand")));
}

void AKeyStandActor::BeginPlay()
{
	Super::BeginPlay();

	// Holding its key from the first frame, whatever the editor left behind.
	SetKeyTaken(false);
}

void AKeyStandActor::SetKeyTaken(bool bNewKeyTaken)
{
	bKeyTaken = bNewKeyTaken;
	if (Key != nullptr)
	{
		Key->SetHiddenInGame(bNewKeyTaken);
	}
	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(bNewKeyTaken ? 0.0f : kStandLampLit);
	}
}

// ---------------------------------------------------------------------------
// ADoorBayActor
// ---------------------------------------------------------------------------

ADoorBayActor::ADoorBayActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kCube);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlainLook(kPlainLook);

	// A bare scene root at floor level, so the frame's local X runs along the row and
	// the panel's slide is a straight sideways travel.
	Frame = CreateDefaultSubobject<USceneComponent>(TEXT("Frame"));
	SetRootComponent(Frame);
	Frame->SetMobility(EComponentMobility::Movable);

	auto MakePost = [&](UStaticMeshComponent*& Out, const TCHAR* Name, float X)
	{
		Out = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Out->SetupAttachment(Frame);
		if (CubeMesh.Succeeded())
		{
			Out->SetStaticMesh(CubeMesh.Object);
		}
		// 60 x 60 x 480, standing on the floor.
		Out->SetRelativeLocation(FVector(X, 0.0f, 240.0f));
		Out->SetRelativeScale3D(FVector(0.6f, 0.6f, 4.8f));
		Out->SetMobility(EComponentMobility::Movable);
		Out->SetCollisionProfileName(TEXT("BlockAll"));
		if (PlainLook.Succeeded())
		{
			Out->SetMaterial(0, PlainLook.Object);
		}
	};
	MakePost(PostA, TEXT("PostA"), -390.0f);
	MakePost(PostB, TEXT("PostB"), 390.0f);

	// 700 x 40 x 420 across the frame. The clear opening between the posts' inner
	// faces is 720 uu, which a 42 uu capsule walks through with 300 uu to spare once
	// the panel is out of the way.
	Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));
	Panel->SetupAttachment(Frame);
	if (CubeMesh.Succeeded())
	{
		Panel->SetStaticMesh(CubeMesh.Object);
	}
	Panel->SetRelativeLocation(kPanelShut);
	Panel->SetRelativeScale3D(FVector(7.0f, 0.4f, 4.2f));
	Panel->SetMobility(EComponentMobility::Movable);
	Panel->SetCollisionProfileName(TEXT("BlockAll"));
	if (PlainLook.Succeeded())
	{
		Panel->SetMaterial(0, PlainLook.Object);
	}
	Panel->ComponentTags.Add(FName(TEXT("Panel")));

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Frame);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 520.0f));
	Lamp->SetLightColor(kShutColour);
	Lamp->SetIntensity(5000.0f);
	Lamp->SetAttenuationRadius(1400.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName(TEXT("Keyring_Bay")));
}

FVector ADoorBayActor::PanelShutRelative() const
{
	return kPanelShut;
}

void ADoorBayActor::BeginPlay()
{
	Super::BeginPlay();

	// Shut from the first frame, whatever the editor left behind.
	SetOpen(false);
}

void ADoorBayActor::SetOpen(bool bNewOpen)
{
	bOpen = bNewOpen;
	if (Panel != nullptr)
	{
		// SET, never ADD. A polling predicate that calls this on every frame has to
		// leave the panel exactly where ONE slide puts it -- an accumulating nudge
		// would walk the panel out of the level and the failure would land somewhere
		// nobody could read.
		Panel->SetRelativeLocation(
			kPanelShut + (bNewOpen ? FVector(SlideUu, 0.0f, 0.0f) : FVector::ZeroVector));
		// Dropping the collision is half of what opening MEANS here: the walled corner
		// behind the last bay in the row has no other way in.
		Panel->SetCollisionProfileName(
			bNewOpen ? TEXT("NoCollision") : TEXT("BlockAll"));
	}
	if (Lamp != nullptr)
	{
		Lamp->SetLightColor(bNewOpen ? kOpenColour : kShutColour);
	}
}

// ---------------------------------------------------------------------------
// ARingBoardActor
// ---------------------------------------------------------------------------

ARingBoardActor::ARingBoardActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kCube);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlainLook(kPlainLook);

	// An UNSCALED root: the slab and the face are SIBLINGS, so the face never inherits
	// the slab's 0.4 x 9 x 5 and never photographs as a smear (the sibling t2 task had
	// to move its readouts off its board face for exactly that reason).
	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	SetRootComponent(Mount);
	Mount->SetMobility(EComponentMobility::Movable);

	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board"));
	Board->SetupAttachment(Mount);
	if (CubeMesh.Succeeded())
	{
		Board->SetStaticMesh(CubeMesh.Object);
	}
	// 40 x 900 x 500, standing on the floor and facing the yard along +X.
	Board->SetRelativeLocation(FVector(0.0f, 0.0f, 250.0f));
	Board->SetRelativeScale3D(FVector(0.4f, 9.0f, 5.0f));
	Board->SetMobility(EComponentMobility::Movable);
	Board->SetCollisionProfileName(TEXT("BlockAll"));
	if (PlainLook.Succeeded())
	{
		Board->SetMaterial(0, PlainLook.Object);
	}

	Sign = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Sign"));
	Sign->SetupAttachment(Mount);
	Sign->SetRelativeLocation(FVector(30.0f, 0.0f, 300.0f));
	Sign->SetHorizontalAlignment(EHTA_Center);
	Sign->SetVerticalAlignment(EVRTA_TextCenter);
	Sign->SetWorldSize(90.0f);
	Sign->SetTextRenderColor(FColor(255, 236, 170));
	Sign->Text = FText::FromString(TEXT("--"));
	Sign->ComponentTags.Add(FName(TEXT("Sign")));

	Tags.Add(FName(TEXT("Keyring_Board")));
}

void ARingBoardActor::BeginPlay()
{
	Super::BeginPlay();

	// Blank from the first frame, whatever the editor left behind. An empty ring reads
	// "--", and at the start of the shift the ring is empty.
	ShowRing(TArray<FName>());
}

void ARingBoardActor::ShowRing(const TArray<FName>& CategoriesInOrder)
{
	if (Sign == nullptr)
	{
		return;
	}
	// Exactly what it is handed, in exactly that order. No sorting, no de-duplicating:
	// the board is a readout, not a fixer-up.
	FString Line;
	for (int32 i = 0; i < CategoriesInOrder.Num(); ++i)
	{
		if (i > 0)
		{
			Line += TEXT(", ");
		}
		Line += CategoriesInOrder[i].ToString();
	}
	if (Line.IsEmpty())
	{
		Line = TEXT("--");
	}
	Sign->SetText(FText::FromString(Line));
}

FString ARingBoardActor::CurrentReadout() const
{
	return Sign != nullptr ? Sign->Text.ToString() : FString();
}
