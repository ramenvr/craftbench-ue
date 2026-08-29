// Copyright CraftBench. All Rights Reserved.

#include "MarkedGroundActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* const kOutOfBoundsMaterial = TEXT("/Game/Variant_Combat/Materials/M_Lava");
	// The U, in centimetres. Both patches are built from these, so "the same shape"
	// is true by construction rather than by two places in a level script agreeing.
	constexpr float kHalfY = 1700.0f;    // outer half-width
	constexpr float kDepth = 1500.0f;    // how far the arms reach back from the mouth
	constexpr float kStroke = 150.0f;    // how wide the painted line is
	constexpr float kPaint = 6.0f;       // how proud of the floor the paint sits
	const TCHAR* const kAllowedMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");
}

AMarkedGroundActor::AMarkedGroundActor()
{
	PrimaryActorTick.bCanEverTick = false;

	// A bare scene root, NOT one of the meshes. A root component's relative location
	// is the actor's location, so a mesh made root cannot be offset from the pivot --
	// and this patch is three meshes at three different offsets.
	USceneComponent* const Pivot =
		CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	// The actor's pivot sits at the MOUTH of the U, on its centreline, so a level
	// places the patch by saying where its opening is.
	const float ArmLen = kDepth - kStroke;
	struct FStrokeSpec { const TCHAR* Name; FVector Centre; FVector Size; };
	const FStrokeSpec Specs[] = {
		{TEXT("StrokeBack"),
			FVector(kDepth - kStroke * 0.5f, 0.0f, 0.0f),
			FVector(kStroke, kHalfY * 2.0f, kPaint)},
		{TEXT("StrokeArmLeft"),
			FVector(ArmLen * 0.5f, kHalfY - kStroke * 0.5f, 0.0f),
			FVector(ArmLen, kStroke, kPaint)},
		{TEXT("StrokeArmRight"),
			FVector(ArmLen * 0.5f, -(kHalfY - kStroke * 0.5f), 0.0f),
			FVector(ArmLen, kStroke, kPaint)},
	};
	for (const FStrokeSpec& Spec : Specs)
	{
		UStaticMeshComponent* const S =
			CreateDefaultSubobject<UStaticMeshComponent>(Spec.Name);
		S->SetupAttachment(Pivot);
		if (CubeMesh.Succeeded())
		{
			S->SetStaticMesh(CubeMesh.Object);
		}
		S->SetRelativeLocation(Spec.Centre);
		// The engine cube is 100 units on a side, centred on its own origin.
		S->SetRelativeScale3D(Spec.Size / 100.0f);
		// PAINT. It blocks nothing, it is not queried by anything, and a figure walks
		// over it without noticing. What it costs is only what the yard says it costs.
		S->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		S->SetMobility(EComponentMobility::Movable);
		Strokes.Add(S);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> OutLook(
		kOutOfBoundsMaterial);
	if (OutLook.Succeeded())
	{
		OutOfBoundsLook = OutLook.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> OkLook(
		kAllowedMaterial);
	if (OkLook.Succeeded())
	{
		AllowedLook = OkLook.Object;
	}

	Tags.Add(FName("MarkedGround"));
}

void AMarkedGroundActor::BeginPlay()
{
	Super::BeginPlay();

	// Repaint from whatever the yard left the flag at, so the first frame is honest.
	SetOutOfBounds(bOutOfBounds);
}

void AMarkedGroundActor::SetOutOfBounds(bool bNewOutOfBounds)
{
	bOutOfBounds = bNewOutOfBounds;
	UMaterialInterface* const Look = bNewOutOfBounds ? OutOfBoundsLook : AllowedLook;
	if (Look == nullptr)
	{
		return;
	}
	for (UStaticMeshComponent* S : Strokes)
	{
		if (S != nullptr)
		{
			S->SetMaterial(0, Look);
		}
	}
}

bool AMarkedGroundActor::CoversPoint(const FVector& WorldPoint) const
{
	for (const UStaticMeshComponent* S : Strokes)
	{
		if (S == nullptr)
		{
			continue;
		}
		// Flat test: the paint is on the floor, and a figure standing on it is a
		// metre above it. Height is nobody's business here.
		const FBox Box = S->Bounds.GetBox();
		if (WorldPoint.X >= Box.Min.X && WorldPoint.X <= Box.Max.X
			&& WorldPoint.Y >= Box.Min.Y && WorldPoint.Y <= Box.Max.Y)
		{
			return true;
		}
	}
	return false;
}

FBox AMarkedGroundActor::WorldFootprint() const
{
	FBox Out(ForceInit);
	for (const UStaticMeshComponent* S : Strokes)
	{
		if (S != nullptr)
		{
			Out += S->Bounds.GetBox();
		}
	}
	return Out;
}
