// Copyright CraftBench. All Rights Reserved.

#include "MusterBoardActor.h"

#include "Components/SceneComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kLampLitIntensity = 7000.0f;
	constexpr float kLampSpacingUu = 500.0f;
	const FLinearColor kLampColour(0.35f, 1.0f, 0.55f);
}

AMusterBoardActor::AMusterBoardActor()
{
	// Ticks only to keep the chalk written up on its own face honest. It decides
	// nothing.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	// A bare scene root at unit scale; the face is scaled, the root never is, so no
	// child's offset or size is multiplied behind your back.
	USceneComponent* const Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	// A 40 x 3000 x 500 cm board standing on its edge. Local +X is the side the deck
	// is on: the lamps and the chalk are on that side.
	Face = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Face"));
	Face->SetupAttachment(Pivot);
	Face->SetRelativeLocation(FVector(0.0f, 0.0f, 250.0f));
	Face->SetRelativeScale3D(FVector(0.4f, 30.0f, 5.0f));
	if (CubeMesh.Succeeded())
	{
		Face->SetStaticMesh(CubeMesh.Object);
	}
	// Non-colliding on every channel, PROFILE as well as enum: nothing on this deck
	// is allowed to get between the character and a plate.
	Face->SetCollisionProfileName(TEXT("NoCollision"));
	Face->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BoardLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (BoardLook.Succeeded())
	{
		Face->SetMaterial(0, BoardLook.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Dark.Succeeded())
	{
		DarkLook = Dark.Object;
	}

	// One lamp per standing spot, in spot order along the face, left to right.
	LampBulbs.Reserve(NumLamps);
	LampGlows.Reserve(NumLamps);
	for (int32 Index = 0; Index < NumLamps; ++Index)
	{
		const float AlongFace =
			(static_cast<float>(Index) - 0.5f * (NumLamps - 1)) * kLampSpacingUu;

		UStaticMeshComponent* const Bulb = CreateDefaultSubobject<UStaticMeshComponent>(
			*FString::Printf(TEXT("LampBulb%d"), Index));
		Bulb->SetupAttachment(Pivot);
		Bulb->SetRelativeLocation(FVector(60.0f, AlongFace, 330.0f));
		Bulb->SetRelativeScale3D(FVector(0.9f, 0.9f, 0.9f));
		if (SphereMesh.Succeeded())
		{
			Bulb->SetStaticMesh(SphereMesh.Object);
		}
		if (DarkLook != nullptr)
		{
			Bulb->SetMaterial(0, DarkLook);
		}
		Bulb->SetCollisionProfileName(TEXT("NoCollision"));
		Bulb->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		LampBulbs.Add(Bulb);

		UPointLightComponent* const Glow = CreateDefaultSubobject<UPointLightComponent>(
			*FString::Printf(TEXT("LampGlow%d"), Index));
		Glow->SetupAttachment(Pivot);
		Glow->SetRelativeLocation(FVector(140.0f, AlongFace, 330.0f));
		Glow->SetLightColor(kLampColour);
		Glow->SetIntensity(0.0f);
		Glow->SetAttenuationRadius(900.0f);
		Glow->SetMobility(EComponentMobility::Movable);
		LampGlows.Add(Glow);
	}

	Chalk = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Chalk"));
	Chalk->SetupAttachment(Pivot);
	Chalk->SetRelativeLocation(FVector(60.0f, 0.0f, 230.0f));
	Chalk->SetHorizontalAlignment(EHTA_Center);
	Chalk->SetWorldSize(46.0f);
	Chalk->SetTextRenderColor(FColor(240, 240, 220));

	Tags.Add(FName(TEXT("MusterBoard")));
}

void AMusterBoardActor::BeginPlay()
{
	Super::BeginPlay();

	// Every lamp dark from the first frame, whatever the editor left behind. Every
	// standing spot starts empty, so this is the honest starting state.
	for (int32 Spot = 1; Spot <= GetLampCount(); ++Spot)
	{
		SetLampLit(Spot, false);
	}

	RefreshChalkText();
}

void AMusterBoardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Presentation only. The chalk on the face is a copy of the numbers, so when the
	// mate re-chalks the board a person watching can see that it happened.
	RefreshChalkText();
}

void AMusterBoardActor::RefreshChalkText()
{
	if (Chalk == nullptr)
	{
		return;
	}

	FString Roster;
	for (int32 Index = 0; Index < RosterCodes.Num(); ++Index)
	{
		Roster += (Index == 0 ? TEXT("") : TEXT(" "));
		Roster += FString::FromInt(RosterCodes[Index]);
	}
	FString Slate;
	for (int32 Index = 0; Index < SlatePositions.Num(); ++Index)
	{
		Slate += (Index == 0 ? TEXT("") : TEXT(" "));
		Slate += FString::FromInt(SlatePositions[Index]);
	}

	Chalk->SetText(FText::FromString(FString::Printf(
		TEXT("CALL %d   EVERY %.1fs<br>ROSTER %s<br>ASHORE %s"),
		HandsToCall, SecondsBetweenArrivals, *Roster, *Slate)));
}

void AMusterBoardActor::SetLampLit(int32 SpotNumber, bool bNewLit)
{
	// The lamp row is numbered the way the standing spots are: the first lamp belongs
	// to spot number 1.
	const int32 Index = SpotNumber - 1;
	if (LampGlows.IsValidIndex(Index) && LampGlows[Index] != nullptr)
	{
		LampGlows[Index]->SetIntensity(bNewLit ? kLampLitIntensity : 0.0f);
	}
	if (LampBulbs.IsValidIndex(Index) && LampBulbs[Index] != nullptr)
	{
		UMaterialInterface* const Look = bNewLit ? LitLook : DarkLook;
		if (Look != nullptr)
		{
			LampBulbs[Index]->SetMaterial(0, Look);
		}
	}
}

bool AMusterBoardActor::IsLampLit(int32 SpotNumber) const
{
	const int32 Index = SpotNumber - 1;
	return LampGlows.IsValidIndex(Index)
		&& LampGlows[Index] != nullptr
		&& LampGlows[Index]->Intensity > 0.0f;
}

int32 AMusterBoardActor::GetLampCount() const
{
	return LampGlows.Num();
}
