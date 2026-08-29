// Copyright CraftBench. All Rights Reserved.

#include "ForgeStationActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "IngredientHeapActor.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* const kCube = TEXT("/Engine/BasicShapes/Cube");
	const TCHAR* const kAnvilLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kStoneLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray");

	// The shelf-stones stand BEHIND the forge, in two rows either side of the line the
	// forge sits on. 700 uu apart along the row -- comfortably more than a product
	// heap's 220 uu reach with the 1.6x clearance the hall solves every walk against,
	// so a walk to one stone is never within reach of its neighbour.
	//
	// 1250 uu OFF THE LINE, and that number is solved rather than chosen. A walker
	// getting behind the forge runs a lane between the forge and the stones, and that
	// lane has to be BOTH plainly outside the forge's 450 uu take-reach (or a walker
	// hauling three units down it would deliver them halfway) AND plainly clear of
	// every stone's 220 uu reach (or it would pick up whatever is standing there in
	// passing). At 1250 the feasible band for the lane is 585 .. 898 uu off the line,
	// 313 uu wide; at 1000 it was 585 .. 648 and a single retune of either reach would
	// have closed it.
	constexpr double kStoneFirstX = -600.0;
	constexpr double kStoneStepX = -700.0;
	constexpr double kStoneY = 1250.0;
	constexpr double kStoneZ = 20.0;
	constexpr int32 kStonesPerRow = AForgeStationActor::ShelfStoneCount / 2;

	/** A stone is free when nothing with units still in it is standing on it. 150 uu:
	 *  well under half the 700 uu stone spacing, so a heap can only ever be "on" one. */
	constexpr double kStoneOccupiedUu = 150.0;
}

AForgeStationActor::AForgeStationActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kCube);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> AnvilLook(kAnvilLook);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> StoneLook(kStoneLook);

	// A plain root at the actor's own origin, so every offset below reads as the
	// world position the hall places the forge at -- no half-height bookkeeping.
	USceneComponent* const Base = CreateDefaultSubobject<USceneComponent>(TEXT("Base"));
	SetRootComponent(Base);
	Base->SetMobility(EComponentMobility::Movable);

	Anvil = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Anvil"));
	Anvil->SetupAttachment(Base);
	if (CubeMesh.Succeeded())
	{
		Anvil->SetStaticMesh(CubeMesh.Object);
	}
	// 200 x 200 x 160, standing on the floor. Deliberately SMALL: the forge takes what
	// you carry from 450 uu, and a walker stopping 300 uu out has to be able to stand
	// there without touching the anvil at all.
	Anvil->SetRelativeLocation(FVector(0.0f, 0.0f, 80.0f));
	Anvil->SetRelativeScale3D(FVector(2.0f, 2.0f, 1.6f));
	Anvil->SetMobility(EComponentMobility::Movable);
	Anvil->SetCollisionProfileName(TEXT("BlockAll"));
	if (AnvilLook.Succeeded())
	{
		Anvil->SetMaterial(0, AnvilLook.Object);
	}

	auto MakeFace = [&](const TCHAR* Name, double Z, const FColor& Colour)
	{
		UTextRenderComponent* const T =
			CreateDefaultSubobject<UTextRenderComponent>(FName(Name));
		T->SetupAttachment(Base);
		// On the aisle side of the anvil, facing the way a walker comes in.
		T->SetRelativeLocation(FVector(140.0f, 0.0f, Z));
		T->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
		T->SetHorizontalAlignment(EHTA_Center);
		T->SetVerticalAlignment(EVRTA_TextCenter);
		T->SetWorldSize(56.0f);
		T->SetTextRenderColor(Colour);
		T->SetMobility(EComponentMobility::Movable);
		T->SetText(FText::FromString(TEXT("--")));
		return T;
	};
	HeldFace = MakeFace(TEXT("HeldFace"), 300.0, FColor(255, 236, 170));
	CanMakeFace = MakeFace(TEXT("CanMakeFace"), 210.0, FColor(170, 230, 255));

	ShelfStones.Reserve(ShelfStoneCount);
	for (int32 i = 0; i < ShelfStoneCount; ++i)
	{
		const int32 Row = i / kStonesPerRow;          // 0 = the -Y row, 1 = the +Y row
		const int32 Slot = i % kStonesPerRow;
		UStaticMeshComponent* const Stone = CreateDefaultSubobject<UStaticMeshComponent>(
			FName(*FString::Printf(TEXT("Shelf%02d"), i)));
		Stone->SetupAttachment(Base);
		if (CubeMesh.Succeeded())
		{
			Stone->SetStaticMesh(CubeMesh.Object);
		}
		Stone->SetRelativeLocation(FVector(
			kStoneFirstX + kStoneStepX * double(Slot),
			Row == 0 ? -kStoneY : kStoneY,
			kStoneZ));
		Stone->SetRelativeScale3D(FVector(2.4f, 2.4f, 0.4f));
		Stone->SetMobility(EComponentMobility::Movable);
		Stone->SetCollisionProfileName(TEXT("NoCollision"));
		Stone->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		if (StoneLook.Succeeded())
		{
			Stone->SetMaterial(0, StoneLook.Object);
		}
		ShelfStones.Add(Stone);
	}

	ProductHeapClass = AIngredientHeapActor::StaticClass();

	Tags.Add(FName("ForgeStation"));
}

void AForgeStationActor::ShowReadout(const FString& HeldLine, const FString& CanMakeLine)
{
	if (HeldFace != nullptr)
	{
		HeldFace->SetText(FText::FromString(HeldLine));
	}
	if (CanMakeFace != nullptr)
	{
		CanMakeFace->SetText(FText::FromString(CanMakeLine));
	}
}

AIngredientHeapActor* AForgeStationActor::EjectProduct(FName ProductId)
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return nullptr;
	}

	// Everything with units still in it, so "is this stone free" is decided by what is
	// actually standing in the hall rather than by a counter that would go on believing
	// a stone is taken after its heap has been carried away.
	TArray<AActor*> Standing;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("IngredientHeap")), Standing);

	USceneComponent* Chosen = nullptr;
	for (UStaticMeshComponent* const Stone : ShelfStones)
	{
		if (Stone == nullptr)
		{
			continue;
		}
		const FVector At = Stone->GetComponentLocation();
		bool bOccupied = false;
		for (const AActor* const A : Standing)
		{
			const AIngredientHeapActor* const H = Cast<AIngredientHeapActor>(A);
			if (H != nullptr && !H->IsEmptied()
				&& FVector::Dist2D(H->GetActorLocation(), At) < kStoneOccupiedUu)
			{
				bOccupied = true;
				break;
			}
		}
		if (!bOccupied)
		{
			Chosen = Stone;
			break;
		}
	}

	double StackZ = 0.0;
	if (Chosen == nullptr)
	{
		// EVERY STONE TAKEN. Stack on the last one rather than dropping the product:
		// a product that vanished reads exactly like a product that was never made,
		// and this branch is only ever reached by a submission that is already making
		// too many of them.
		Chosen = ShelfStones.Num() > 0 ? ShelfStones.Last() : GetRootComponent();
		StackZ = 120.0;
		UE_LOG(LogTemp, Warning,
			TEXT("[forge] every shelf-stone is taken; %s is stacked on the last one"),
			*ProductId.ToString());
	}
	if (Chosen == nullptr)
	{
		return nullptr;
	}

	const FTransform Where(FRotator::ZeroRotator,
		Chosen->GetComponentLocation() + FVector(0.0, 0.0, 40.0 + StackZ));
	UClass* const HeapClass = ProductHeapClass != nullptr
		? ProductHeapClass.Get() : AIngredientHeapActor::StaticClass();
	AIngredientHeapActor* const Made =
		World->SpawnActorDeferred<AIngredientHeapActor>(HeapClass, Where);
	if (Made == nullptr)
	{
		return nullptr;
	}
	// Set BEFORE BeginPlay so the heap's label is right on the first frame it exists.
	Made->IngredientId = ProductId;
	Made->UnitsInHeap = 1;
	Made->FinishSpawning(Where);
	return Made;
}
