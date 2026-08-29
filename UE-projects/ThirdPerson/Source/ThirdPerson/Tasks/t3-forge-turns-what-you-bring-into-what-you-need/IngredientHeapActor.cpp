// Copyright CraftBench. All Rights Reserved.

#include "IngredientHeapActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* const kHeapMesh = TEXT("/Engine/BasicShapes/Cone");
	const TCHAR* const kHeapLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AIngredientHeapActor::AIngredientHeapActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(kHeapMesh);

	Heap = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Heap"));
	SetRootComponent(Heap);
	if (ConeMesh.Succeeded())
	{
		Heap->SetStaticMesh(ConeMesh.Object);
	}
	Heap->SetRelativeScale3D(FVector(1.4f, 1.4f, 1.0f));
	Heap->SetMobility(EComponentMobility::Movable);
	// NO COLLISION, both ways round: the profile AND the enum. A heap you can walk
	// into is the whole point, and paint that quietly blocks is indistinguishable
	// from a bug in the submission.
	Heap->SetCollisionProfileName(TEXT("NoCollision"));
	Heap->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kHeapLook);
	if (Look.Succeeded())
	{
		Heap->SetMaterial(0, Look.Object);
	}

	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(Heap);
	// Divided back out of the heap's scale so the label floats just above the pile.
	Label->SetRelativeLocation(FVector(0.0f, 0.0f, 220.0f));
	Label->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetWorldSize(64.0f);
	Label->SetTextRenderColor(FColor(255, 216, 120));
	Label->SetMobility(EComponentMobility::Movable);
	Label->SetText(FText::FromString(TEXT("--")));

	Tags.Add(FName("IngredientHeap"));
}

void AIngredientHeapActor::BeginPlay()
{
	Super::BeginPlay();

	// Say what you are from the first frame, whatever the editor left behind.
	RefreshLabel();
}

int32 AIngredientHeapActor::TakeUpTo(int32 MaxUnits)
{
	// CLAMPED BOTH WAYS. A MaxUnits of zero or less hands over nothing and leaves the
	// heap exactly as it found it -- somebody already carrying all they can walks up to
	// a heap and it is still standing afterwards with every unit it had. A MaxUnits
	// bigger than the heap hands over the heap and no more.
	const int32 Standing = FMath::Max(UnitsInHeap, 0);
	const int32 Handed = FMath::Clamp(MaxUnits, 0, Standing);
	UnitsInHeap = Standing - Handed;
	RefreshLabel();
	return Handed;
}

void AIngredientHeapActor::RefreshLabel()
{
	const bool bStanding = UnitsInHeap > 0;
	if (Label != nullptr)
	{
		Label->SetText(bStanding
			? FText::FromString(FString::Printf(TEXT("%s x%d"),
				*IngredientId.ToString(), UnitsInHeap))
			: FText::FromString(FString()));
		Label->SetVisibility(bStanding, false);
		Label->SetHiddenInGame(!bStanding, false);
	}
	if (Heap != nullptr)
	{
		Heap->SetVisibility(bStanding, false);
		Heap->SetHiddenInGame(!bStanding, false);
	}
}
