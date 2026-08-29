// Copyright CraftBench. All Rights Reserved.

#include "LiftCarActor.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The car floor is 700 x 700. That is not decoration: the character brakes over
	// ~62 uu from walking speed, so a pad centred 190 uu off the middle still leaves
	// ~100 uu of platform beyond the point he stops -- he cannot walk himself off the
	// edge on the way to a button. It also keeps the three pads 80 uu clear of each
	// other's capsule footprint, so crossing the car never presses a button by accident.
	constexpr float kCarHalfUu = 350.0f;
	constexpr float kPlatformThicknessUu = 20.0f;

	// PLATFORM IS THE ROOT AND IT IS SCALED, SO EVERY CHILD INHERITS THAT SCALE. The
	// floor is the 100 uu engine cube blown up to 700 x 700 x 20 -- (7, 7, 0.2) -- and
	// UE multiplies BOTH a child's relative offset and a child's own scale by that when
	// it composes the world transform. UBoxComponent::CalcBounds transforms the box
	// EXTENT by the full LocalToWorld too, so a pad is stretched exactly as far as it
	// is displaced.
	//
	// Measured before this was cancelled: Pad1, written at a relative (0, -190), stood
	// at (0, -1330) as an 840 x 840 volume instead of 120 x 120 at (0, -190) -- wide
	// enough that the walk from the PlayerStart to the landing call pad crossed it and
	// the verifier refused to grade the run. Every fitting below therefore states where
	// it wants to be IN WORLD UU and divides this scale back out. The scale is derived
	// from the same two numbers that build the floor and is used to build it, so there
	// is one definition of the car's size and re-sizing the car moves its fittings with
	// it instead of scattering them.
	const FVector kPlatformWorldScale(kCarHalfUu * 2.0f / 100.0f,
		kCarHalfUu * 2.0f / 100.0f, kPlatformThicknessUu / 100.0f);

	/** The relative offset that puts a child of Platform WorldOffsetUu from the car's
	 *  origin, whatever the floor is scaled to. */
	FVector PlatformLocal(const FVector& WorldOffsetUu)
	{
		return WorldOffsetUu / kPlatformWorldScale;
	}

	/** The relative scale that gives a child of Platform the world scale it asks for. */
	FVector PlatformLocalScale(const FVector& WantedWorldScale)
	{
		return WantedWorldScale / kPlatformWorldScale;
	}

	// The doorway faces -X. The leaves slide apart along Y, 90 uu each, from 70 uu
	// either side of the middle. Separation is therefore 140 shut and 320 open, and
	// (Sep - 140) / 180 lands on EXACTLY 0.0 and EXACTLY 1.0 at the two ends.
	constexpr float kDoorFaceX = -345.0f;
	constexpr float kDoorMidZ = 135.0f;
	constexpr float kDoorHalfShutY = 70.0f;
	constexpr float kDoorSlideUu = 90.0f;

	constexpr float kPadOffsetUu = 190.0f;
	constexpr float kPadTopZ = 40.0f;
	constexpr float kLampIntensity = 6000.0f;
	const FLinearColor kLampColour(1.0f, 0.72f, 0.20f);

	const TCHAR* const kCubeMesh = TEXT("/Engine/BasicShapes/Cube.Cube");
	const TCHAR* const kPlainMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kTrimMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");
}

ALiftCarActor::ALiftCarActor()
{
	// The car ticks: the supplied door mechanism runs in Tick, and a movable base has
	// to tick for a character standing on it to be carried in the right order --
	// MovementBaseUtility::AddTickDependency makes the rider's movement tick a
	// dependent of THIS actor's tick, but only when bCanEverTick is set (Character.cpp).
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kCubeMesh);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlainLook(kPlainMaterial);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> TrimLook(kTrimMaterial);

	auto MakeMesh = [&](const TCHAR* Name, const FVector& Loc, const FVector& Scale,
		bool bBlocks, UMaterialInterface* Look) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* const C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		if (CubeMesh.Succeeded())
		{
			C->SetStaticMesh(CubeMesh.Object);
		}
		C->SetRelativeLocation(Loc);
		C->SetRelativeScale3D(Scale);
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

	UMaterialInterface* const Plain = PlainLook.Succeeded() ? PlainLook.Object : nullptr;
	UMaterialInterface* const Trim = TrimLook.Succeeded() ? TrimLook.Object : nullptr;

	// THE ROOT. Everything else hangs off the floor, so moving the actor moves the
	// surface the rider is standing on and the engine carries him with it.
	Platform = MakeMesh(TEXT("Platform"), FVector::ZeroVector, kPlatformWorldScale,
		/*bBlocks=*/true, Plain);
	SetRootComponent(Platform);

	// Everything from here down hangs off Platform, so it is stated in WORLD uu and the
	// root's scale is divided back out. MakeFitting is where that division happens, so
	// it happens once and no fitting can be written in the wrong frame by accident.
	auto MakeFitting = [&](const TCHAR* Name, const FVector& WorldOffsetUu,
		const FVector& WorldScale, bool bBlocks, UMaterialInterface* Look)
		-> UStaticMeshComponent*
	{
		UStaticMeshComponent* const C = MakeMesh(Name, PlatformLocal(WorldOffsetUu),
			PlatformLocalScale(WorldScale), bBlocks, Look);
		C->SetupAttachment(Platform);
		return C;
	};

	// Shell. Nothing here blocks: a lift that can pin the character against a wall is
	// a lift whose grade is about collision, not about scheduling. The roof is the same
	// 700 x 700 as the floor and lands on top of the three 250 uu walls (135 +/- 125
	// puts their feet on the floor at +10 and their heads at +260); the walls are 10 uu
	// thick and stand on the floor's own edges at 345.
	Cage = MakeFitting(TEXT("Cage"), FVector(0.0f, 0.0f, 270.0f), kPlatformWorldScale,
		/*bBlocks=*/false, Plain);

	WallBack = MakeFitting(TEXT("WallBack"), FVector(345.0f, 0.0f, kDoorMidZ),
		FVector(0.1f, kPlatformWorldScale.Y, 2.5f), /*bBlocks=*/false, Plain);

	WallLeft = MakeFitting(TEXT("WallLeft"), FVector(0.0f, -345.0f, kDoorMidZ),
		FVector(kPlatformWorldScale.X, 0.1f, 2.5f), /*bBlocks=*/false, Plain);

	WallRight = MakeFitting(TEXT("WallRight"), FVector(0.0f, 345.0f, kDoorMidZ),
		FVector(kPlatformWorldScale.X, 0.1f, 2.5f), /*bBlocks=*/false, Plain);

	// THE TWO LEAVES ARE THE ONE FITTING THAT IS DELIBERATELY *NOT* UNSCALED, AND MOVING
	// THEM BREAKS THE TASK. GetDoorOpenFraction() below -- and the verifier, identically
	// -- measures the doors from the leaves' RELATIVE Y separation and compares it
	// against DoorShutSeparationUu / DoorOpenSeparationUu (140 shut, 320 open). Dividing
	// the root's scale out of the leaves would make that separation 20 / 45.7 while both
	// formulas still read 140 / 320, so the doors would measure permanently shut and
	// nothing anybody builds on them could ever be seen. Their world placement is
	// consequently off, which costs nothing: they are NoCollision, and no gate and
	// nothing in this file reads WHERE they are -- only how far apart.
	DoorLeftLeaf = MakeMesh(TEXT("DoorLeftLeaf"),
		FVector(kDoorFaceX, -kDoorHalfShutY, kDoorMidZ),
		FVector(0.1f, 1.4f, 2.5f), /*bBlocks=*/false, Trim);
	DoorLeftLeaf->SetupAttachment(Platform);

	DoorRightLeaf = MakeMesh(TEXT("DoorRightLeaf"),
		FVector(kDoorFaceX, kDoorHalfShutY, kDoorMidZ),
		FVector(0.1f, 1.4f, 2.5f), /*bBlocks=*/false, Trim);
	DoorRightLeaf->SetupAttachment(Platform);

	// The three pads. The volumes are here and they generate overlap events; nothing
	// listens to them.
	auto MakePad = [&](const TCHAR* Name, const FVector& WorldOffsetUu) -> UBoxComponent*
	{
		UBoxComponent* const B = CreateDefaultSubobject<UBoxComponent>(Name);
		B->SetupAttachment(Platform);
		B->SetRelativeLocation(PlatformLocal(WorldOffsetUu));
		// The extent needs the root's scale taken out of it as well as the offset:
		// CalcBounds transforms the box by the FULL LocalToWorld, so with the scale
		// left in this 120 x 120 pad measured 840 x 840 and swallowed the walk.
		B->SetRelativeScale3D(PlatformLocalScale(FVector::OneVector));
		B->SetBoxExtent(FVector(60.0f, 60.0f, 15.0f));
		B->SetMobility(EComponentMobility::Movable);
		B->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
		B->SetGenerateOverlapEvents(true);
		return B;
	};
	Pad1 = MakePad(TEXT("Pad1"), FVector(0.0f, -kPadOffsetUu, kPadTopZ - 15.0f));
	Pad2 = MakePad(TEXT("Pad2"), FVector(kPadOffsetUu, 0.0f, kPadTopZ - 15.0f));
	Pad3 = MakePad(TEXT("Pad3"), FVector(0.0f, kPadOffsetUu, kPadTopZ - 15.0f));

	auto MakeLamp = [&](const TCHAR* Name, const FVector& WorldOffsetUu)
		-> UPointLightComponent*
	{
		UPointLightComponent* const L = CreateDefaultSubobject<UPointLightComponent>(Name);
		L->SetupAttachment(Platform);
		L->SetRelativeLocation(PlatformLocal(WorldOffsetUu));
		// AttenuationRadius is world uu and is NOT scaled by the component, so this is
		// tidiness rather than optics -- but a lamp left at the root's scale is a trap
		// for the next person who parents a mesh to it.
		L->SetRelativeScale3D(PlatformLocalScale(FVector::OneVector));
		L->SetMobility(EComponentMobility::Movable);
		L->SetLightColor(kLampColour);
		L->SetAttenuationRadius(400.0f);
		L->SetIntensity(0.0f);
		L->SetCastShadows(false);
		return L;
	};
	PadLamp1 = MakeLamp(TEXT("PadLamp1"), FVector(0.0f, -kPadOffsetUu, 95.0f));
	PadLamp2 = MakeLamp(TEXT("PadLamp2"), FVector(kPadOffsetUu, 0.0f, 95.0f));
	PadLamp3 = MakeLamp(TEXT("PadLamp3"), FVector(0.0f, kPadOffsetUu, 95.0f));

	// The three numbers, painted where somebody riding the car can read them.
	NumbersReadout = CreateDefaultSubobject<UTextRenderComponent>(TEXT("NumbersReadout"));
	NumbersReadout->SetupAttachment(Platform);
	NumbersReadout->SetRelativeLocation(PlatformLocal(FVector(335.0f, 0.0f, 170.0f)));
	// SetWorldSize below is world uu, and the glyphs are scaled by the component like
	// any other geometry -- left at the root's scale the three numbers came out 7x wide
	// and a fifth as tall, i.e. unreadable to the rider they are painted for.
	NumbersReadout->SetRelativeScale3D(PlatformLocalScale(FVector::OneVector));
	NumbersReadout->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	NumbersReadout->SetMobility(EComponentMobility::Movable);
	NumbersReadout->SetHorizontalAlignment(EHTA_Center);
	NumbersReadout->SetWorldSize(26.0f);
	NumbersReadout->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Tags.Add(FName(TEXT("LiftCar")));
}

void ALiftCarActor::BeginPlay()
{
	Super::BeginPlay();

	// Shut and dark from the first frame, whatever the editor left behind.
	bCommandedOpen = false;
	DoorPhase = 0.0f;
	ApplyDoorLeaves();
	SetPadLit(1, false);
	SetPadLit(2, false);
	SetPadLit(3, false);

	if (NumbersReadout != nullptr)
	{
		// One line, not three: UTextRenderComponent splits on <br>, not on \n.
		NumbersReadout->SetText(FText::FromString(FString::Printf(
			TEXT("%.0f uu/s   doors %.1f s   hold %.1f s"),
			TravelSpeedUuPerSecond, DoorTravelSeconds, DoorHoldSeconds)));
	}
}

void ALiftCarActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// SUPPLIED. The leaves move here and nowhere else. Keep this call.
	AdvanceDoors(DeltaSeconds);

	// ---------------------------------------------------------------------------------
	// NOTHING BELOW THIS LINE EXISTS YET, AND THAT IS THE TASK.
	//
	// No pad is bound, so no press is ever noticed. No call is remembered. No floor is
	// chosen. The car never moves. The landings' signs are never written. Each of those
	// is a decision, and every switch you need to carry it out is already above.
	// ---------------------------------------------------------------------------------
}

void ALiftCarActor::AdvanceDoors(float DeltaSeconds)
{
	const float Travel = FMath::Max(DoorTravelSeconds, 0.05f);
	const float Target = bCommandedOpen ? 1.0f : 0.0f;
	const float Step = DeltaSeconds / Travel;
	if (DoorPhase < Target)
	{
		DoorPhase = FMath::Min(Target, DoorPhase + Step);
	}
	else if (DoorPhase > Target)
	{
		DoorPhase = FMath::Max(Target, DoorPhase - Step);
	}
	ApplyDoorLeaves();
}

void ALiftCarActor::ApplyDoorLeaves()
{
	const float Offset = kDoorHalfShutY + kDoorSlideUu * DoorPhase;
	if (DoorLeftLeaf != nullptr)
	{
		DoorLeftLeaf->SetRelativeLocation(FVector(kDoorFaceX, -Offset, kDoorMidZ));
	}
	if (DoorRightLeaf != nullptr)
	{
		DoorRightLeaf->SetRelativeLocation(FVector(kDoorFaceX, Offset, kDoorMidZ));
	}
}

void ALiftCarActor::OpenDoors()
{
	bCommandedOpen = true;
}

void ALiftCarActor::CloseDoors()
{
	bCommandedOpen = false;
}

float ALiftCarActor::GetDoorOpenFraction() const
{
	if (DoorLeftLeaf == nullptr || DoorRightLeaf == nullptr)
	{
		return 0.0f;
	}
	const double Span = double(DoorOpenSeparationUu) - double(DoorShutSeparationUu);
	if (FMath::Abs(Span) < 1.0)
	{
		return 0.0f;
	}
	const double Sep = FMath::Abs(DoorRightLeaf->GetRelativeLocation().Y
		- DoorLeftLeaf->GetRelativeLocation().Y);

	// THE END SNAP THIS FUNCTION PROMISES, AND WHY IT CANNOT BE LEFT TO THE LEAVES.
	//
	// AdvanceDoors asks for the exact end position; the engine is entitled not to
	// deliver it. USceneComponent::InternalSetWorldLocationAndRotation only writes the
	// new relative location when it differs from the stored one by more than
	// UE_KINDA_SMALL_NUMBER -- FVector::Equals, SceneComponent.cpp:3315 -- and the last
	// step of the ramp is a sliver. At the fixed 60 Hz this task runs at, over a 2.0 s
	// door travel, DoorPhase accumulates to 0.99999940 on frame 120 and the clamp to 1
	// on frame 121 asks each leaf to move 6.1e-05 uu. THAT WRITE IS DROPPED. The leaves
	// stop 6.1e-05 uu short, the measured separation comes out 319.99988 instead of 320,
	// the raw fraction is 0.9999993 -- and `>= 1.0f` is false forever. The shut end is
	// the same defect mirrored: the leaves settle at a separation of 140.00011, so
	// `<= 0.0f` is false forever too.
	//
	// That is not a rounding curiosity, it is a trap. A lift written against the promise
	// at the top of this class ("exactly 0.0f and exactly 1.0f at the two ends") hangs
	// with its doors open and a call it can never discharge, or holds a door interlock
	// that will never read shut. Measured on 2026-08-19: the reference solution itself
	// hung at its very first opening for exactly this reason.
	//
	// So the promise is kept HERE, where the fraction is derived. A leaf can be short by
	// at most UE_KINDA_SMALL_NUMBER (a bigger move is never dropped), so the separation
	// can be out by at most twice that; the band is twice again for margin. It is 4e-4 uu
	// of a 180 uu span -- two millionths of the travel, about a thousandth of one frame
	// of door movement -- so nothing that is genuinely moving is ever snapped. The band
	// is stated in SEPARATION uu and divided into the span, so it stays correct whatever
	// this car's two separations are and whichever way round they are written.
	constexpr double kLeafEndSlackUu = 4.0 * double(UE_KINDA_SMALL_NUMBER);
	const double Raw =
		FMath::Clamp((Sep - double(DoorShutSeparationUu)) / Span, 0.0, 1.0);
	const double EndSnap = kLeafEndSlackUu / FMath::Abs(Span);
	if (Raw <= EndSnap)
	{
		return 0.0f;
	}
	if (Raw >= 1.0 - EndSnap)
	{
		return 1.0f;
	}
	return static_cast<float>(Raw);
}

UPointLightComponent* ALiftCarActor::GetPadLamp(int32 FloorNumber) const
{
	switch (FloorNumber)
	{
	case 1: return PadLamp1;
	case 2: return PadLamp2;
	case 3: return PadLamp3;
	default: return nullptr;
	}
}

UBoxComponent* ALiftCarActor::GetPad(int32 FloorNumber) const
{
	switch (FloorNumber)
	{
	case 1: return Pad1;
	case 2: return Pad2;
	case 3: return Pad3;
	default: return nullptr;
	}
}

void ALiftCarActor::SetPadLit(int32 FloorNumber, bool bLit)
{
	if (UPointLightComponent* const Lamp = GetPadLamp(FloorNumber))
	{
		Lamp->SetIntensity(bLit ? kLampIntensity : 0.0f);
	}
}

bool ALiftCarActor::IsPadLit(int32 FloorNumber) const
{
	const UPointLightComponent* const Lamp = GetPadLamp(FloorNumber);
	return Lamp != nullptr && Lamp->Intensity > 0.0f;
}

float ALiftCarActor::GetSillHeight() const
{
	if (Platform == nullptr)
	{
		return static_cast<float>(GetActorLocation().Z);
	}
	return static_cast<float>(Platform->Bounds.GetBox().Max.Z);
}
