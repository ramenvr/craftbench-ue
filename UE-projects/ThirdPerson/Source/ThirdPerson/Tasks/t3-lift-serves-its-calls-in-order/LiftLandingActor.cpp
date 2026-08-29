// Copyright CraftBench. All Rights Reserved.

#include "LiftLandingActor.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The deck is 700 deep (X, away from the shaft) x 800 wide (Y). The shaft side is
	// open -- that is the doorway -- and the other three sides carry a parapet, because
	// two of these landings are 4.5 and 18 metres up and a character who walks off one
	// ends the run for a reason that has nothing to do with lifts.
	constexpr float kDeckDepthUu = 700.0f;
	constexpr float kDeckWidthUu = 800.0f;
	constexpr float kDeckThicknessUu = 20.0f;

	// DECK IS THE ROOT AND IT IS SCALED, SO EVERY CHILD INHERITS THAT SCALE, and it is
	// NON-UNIFORM here: the 100 uu engine cube blown up to 700 x 800 x 20 is
	// (7, 8, 0.2). UE multiplies BOTH a child's relative offset and a child's own scale
	// by that, and UBoxComponent::CalcBounds transforms the box EXTENT by the full
	// LocalToWorld as well.
	//
	// Measured before this was cancelled: the call pad, written at a relative
	// (150, -220), stood at (1050, -1760) from the deck centre -- 1360 uu past the edge
	// of its own 800 uu deck, in mid air, as an 840 x 960 volume. The verifier aims its
	// walk at the pad's real world footprint, so it walked at a point off the map and
	// refused to grade the run. Every fitting below therefore states where it wants to
	// be IN WORLD UU and divides this scale back out; the scale is derived from the
	// three numbers that build the deck and is used to build it, so the deck has one
	// size and its fittings follow it.
	const FVector kDeckWorldScale(kDeckDepthUu / 100.0f, kDeckWidthUu / 100.0f,
		kDeckThicknessUu / 100.0f);

	/** The relative offset that puts a child of Deck WorldOffsetUu from the landing's
	 *  origin, whatever the deck is scaled to. */
	FVector DeckLocal(const FVector& WorldOffsetUu)
	{
		return WorldOffsetUu / kDeckWorldScale;
	}

	/** The relative scale that gives a child of Deck the world scale it asks for. */
	FVector DeckLocalScale(const FVector& WantedWorldScale)
	{
		return WantedWorldScale / kDeckWorldScale;
	}

	constexpr float kCallPadX = 150.0f;
	constexpr float kCallPadY = -220.0f;
	constexpr float kSignX = 300.0f;
	constexpr float kSignZ = 255.0f;

	constexpr float kLampIntensity = 6000.0f;
	const FLinearColor kLampColour(1.0f, 0.72f, 0.20f);

	const TCHAR* const kCubeMesh = TEXT("/Engine/BasicShapes/Cube.Cube");
	const TCHAR* const kConeMesh = TEXT("/Engine/BasicShapes/Cone.Cone");
	const TCHAR* const kPlainMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kTrimMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");
}

ALiftLandingActor::ALiftLandingActor()
{
	// A landing decides nothing, so it does not need to tick. Turn it on if your own
	// design wants it; nothing here depends on it either way.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kCubeMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(kConeMesh);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlainLook(kPlainMaterial);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> TrimLook(kTrimMaterial);

	UMaterialInterface* const Plain = PlainLook.Succeeded() ? PlainLook.Object : nullptr;
	UMaterialInterface* const Trim = TrimLook.Succeeded() ? TrimLook.Object : nullptr;

	auto MakeMesh = [&](const TCHAR* Name, UStaticMesh* Mesh, const FVector& Loc,
		const FVector& Scale, bool bBlocks, UMaterialInterface* Look) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* const C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		if (Mesh != nullptr)
		{
			C->SetStaticMesh(Mesh);
		}
		C->SetRelativeLocation(Loc);
		C->SetRelativeScale3D(Scale);
		// Movable throughout: the shaft is staged before the lift runs and one landing
		// is re-staged mid-run, and a Static component under a Movable root is a PIE
		// error, not a warning.
		C->SetMobility(EComponentMobility::Movable);
		if (bBlocks)
		{
			C->SetCollisionProfileName(TEXT("BlockAll"));
		}
		else
		{
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		}
		if (Look != nullptr)
		{
			C->SetMaterial(0, Look);
		}
		return C;
	};

	UStaticMesh* const Cube = CubeMesh.Succeeded() ? CubeMesh.Object : nullptr;
	UStaticMesh* const Cone = ConeMesh.Succeeded() ? ConeMesh.Object : nullptr;

	Deck = MakeMesh(TEXT("Deck"), Cube, FVector::ZeroVector, kDeckWorldScale,
		/*bBlocks=*/true, Plain);
	SetRootComponent(Deck);

	// Everything from here down hangs off Deck, so it is stated in WORLD uu and the
	// root's scale is divided back out. MakeFitting is where that division happens, so
	// it happens once and no fitting can be written in the wrong frame by accident.
	auto MakeFitting = [&](const TCHAR* Name, UStaticMesh* Mesh,
		const FVector& WorldOffsetUu, const FVector& WorldScale, bool bBlocks,
		UMaterialInterface* Look) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* const C = MakeMesh(Name, Mesh, DeckLocal(WorldOffsetUu),
			DeckLocalScale(WorldScale), bBlocks, Look);
		C->SetupAttachment(Deck);
		return C;
	};

	// 20 uu thick, 120 tall, standing on the deck's own three closed edges (70 +/- 60
	// puts their feet at +10, which is the deck's top, and their heads at +130). These
	// are the fall rails, and with the root's scale left in them they stood 24 and 31
	// metres off the deck -- i.e. two landings 4.5 and 18 m up had no rail at all.
	ParapetFar = MakeFitting(TEXT("ParapetFar"), Cube,
		FVector(-kDeckDepthUu / 2.0f + 10.0f, 0.0f, 70.0f),
		FVector(0.2f, kDeckWorldScale.Y, 1.2f), /*bBlocks=*/true, Plain);

	ParapetLeft = MakeFitting(TEXT("ParapetLeft"), Cube,
		FVector(0.0f, -kDeckWidthUu / 2.0f + 10.0f, 70.0f),
		FVector(kDeckWorldScale.X, 0.2f, 1.2f), /*bBlocks=*/true, Plain);

	ParapetRight = MakeFitting(TEXT("ParapetRight"), Cube,
		FVector(0.0f, kDeckWidthUu / 2.0f - 10.0f, 70.0f),
		FVector(kDeckWorldScale.X, 0.2f, 1.2f), /*bBlocks=*/true, Plain);

	CallPad = CreateDefaultSubobject<UBoxComponent>(TEXT("CallPad"));
	CallPad->SetupAttachment(Deck);
	CallPad->SetRelativeLocation(DeckLocal(FVector(kCallPadX, kCallPadY, 25.0f)));
	// The extent needs the root's scale taken out of it as well as the offset:
	// CalcBounds transforms the box by the FULL LocalToWorld, so with the scale left in
	// this 120 x 120 pad measured 840 x 960.
	CallPad->SetRelativeScale3D(DeckLocalScale(FVector::OneVector));
	CallPad->SetBoxExtent(FVector(60.0f, 60.0f, 15.0f));
	CallPad->SetMobility(EComponentMobility::Movable);
	CallPad->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	CallPad->SetGenerateOverlapEvents(true);

	CallLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("CallLamp"));
	CallLamp->SetupAttachment(Deck);
	CallLamp->SetRelativeLocation(DeckLocal(FVector(kCallPadX, kCallPadY, 95.0f)));
	// AttenuationRadius is world uu and is NOT scaled by the component, so this is
	// tidiness rather than optics -- but a lamp left at the root's scale is a trap for
	// the next person who parents a mesh to it.
	CallLamp->SetRelativeScale3D(DeckLocalScale(FVector::OneVector));
	CallLamp->SetMobility(EComponentMobility::Movable);
	CallLamp->SetLightColor(kLampColour);
	CallLamp->SetAttenuationRadius(400.0f);
	CallLamp->SetIntensity(0.0f);
	CallLamp->SetCastShadows(false);

	Readout = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Readout"));
	Readout->SetupAttachment(Deck);
	Readout->SetRelativeLocation(DeckLocal(FVector(kSignX, 90.0f, kSignZ)));
	// SetWorldSize below is world uu, and the glyphs are scaled by the component like
	// any other geometry -- left at the root's scale the floor number came out 7x wide,
	// 8x deep and a fifth as tall, and 21 metres off the front of the deck.
	Readout->SetRelativeScale3D(DeckLocalScale(FVector::OneVector));
	Readout->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Readout->SetMobility(EComponentMobility::Movable);
	Readout->SetHorizontalAlignment(EHTA_Center);
	Readout->SetWorldSize(90.0f);
	Readout->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Readout->SetText(FText::GetEmpty());

	// The arrow's DIRECTION survives any scale -- a world up-vector comes off the
	// rotation alone -- but where it is and how big it is do not, and the sign is only
	// worth grading if somebody standing on the landing can see it.
	Arrow = MakeFitting(TEXT("Arrow"), Cone, FVector(kSignX, -90.0f, kSignZ),
		FVector(0.7f, 0.7f, 1.2f), /*bBlocks=*/false, Trim);
	Arrow->SetVisibility(false, true);

	FloorPlate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("FloorPlate"));
	FloorPlate->SetupAttachment(Deck);
	FloorPlate->SetRelativeLocation(
		DeckLocal(FVector(-kDeckDepthUu / 2.0f + 30.0f, 0.0f, 140.0f)));
	FloorPlate->SetRelativeScale3D(DeckLocalScale(FVector::OneVector));
	FloorPlate->SetRelativeRotation(FRotator(0.0f, 0.0f, 0.0f));
	FloorPlate->SetMobility(EComponentMobility::Movable);
	FloorPlate->SetHorizontalAlignment(EHTA_Center);
	FloorPlate->SetWorldSize(60.0f);
	FloorPlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Tags.Add(FName(TEXT("LiftLanding")));
}

void ALiftLandingActor::BeginPlay()
{
	Super::BeginPlay();

	// Blank sign, dark lamp, from the first frame.
	SetCallLit(false);
	Show(0, 0);

	if (FloorPlate != nullptr)
	{
		FloorPlate->SetText(FText::FromString(
			FString::Printf(TEXT("LANDING %d"), FloorNumber)));
	}
}

void ALiftLandingActor::SetCallLit(bool bLit)
{
	if (CallLamp != nullptr)
	{
		CallLamp->SetIntensity(bLit ? kLampIntensity : 0.0f);
	}
}

bool ALiftLandingActor::IsCallLit() const
{
	return CallLamp != nullptr && CallLamp->Intensity > 0.0f;
}

float ALiftLandingActor::GetSillHeight() const
{
	if (Deck == nullptr)
	{
		return static_cast<float>(GetActorLocation().Z);
	}
	return static_cast<float>(Deck->Bounds.GetBox().Max.Z);
}

void ALiftLandingActor::Show(int32 InFloorNumber, int32 Direction)
{
	if (Readout != nullptr)
	{
		Readout->SetText(InFloorNumber > 0
			? FText::FromString(FString::FromInt(InFloorNumber))
			: FText::GetEmpty());
	}
	if (Arrow != nullptr)
	{
		if (Direction > 0)
		{
			// The cone points along its own +Z, so an unrotated arrow points up.
			Arrow->SetRelativeRotation(FRotator::ZeroRotator);
			Arrow->SetVisibility(true, /*bPropagateToChildren=*/true);
		}
		else if (Direction < 0)
		{
			// Roll 180 turns +Z into -Z: the same arrow, pointing down.
			Arrow->SetRelativeRotation(FRotator(0.0f, 0.0f, 180.0f));
			Arrow->SetVisibility(true, /*bPropagateToChildren=*/true);
		}
		else
		{
			Arrow->SetVisibility(false, /*bPropagateToChildren=*/true);
		}
	}
}
