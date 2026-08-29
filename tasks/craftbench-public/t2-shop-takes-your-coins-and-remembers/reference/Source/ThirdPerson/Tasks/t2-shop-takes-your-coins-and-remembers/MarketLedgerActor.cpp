// Copyright CraftBench. All Rights Reserved.

#include "MarketLedgerActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "MarketKeeperSubsystem.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// A 60 x 60 x 300 post; like the stalls it is placed at half its own height.
	const FVector kPostScale(0.6f, 0.6f, 3.0f);
	const FVector kBoardOffset(0.0f, -40.0f, 100.0f);
	const TCHAR* const kPostMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AMarketLedgerActor::AMarketLedgerActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Post = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Post"));
	SetRootComponent(Post);
	if (CubeMesh.Succeeded())
	{
		Post->SetStaticMesh(CubeMesh.Object);
	}
	Post->SetRelativeScale3D(kPostScale);
	// MOVABLE: the board is destroyed and respawned mid-run, and PIE scores moving a
	// STATIC actor as a failed test.
	Post->SetMobility(EComponentMobility::Movable);
	Post->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PostLook(kPostMaterial);
	if (PostLook.Succeeded())
	{
		Post->SetMaterial(0, PostLook.Object);
	}

	CoinsBoard = CreateDefaultSubobject<UTextRenderComponent>(TEXT("CoinsBoard"));
	CoinsBoard->SetupAttachment(Post);
	// Divided back out of the post's scale: children inherit it.
	CoinsBoard->SetRelativeLocation(FVector(kBoardOffset.X / kPostScale.X,
		kBoardOffset.Y / kPostScale.Y, kBoardOffset.Z / kPostScale.Z));
	CoinsBoard->SetRelativeScale3D(FVector(1.0f / kPostScale.X, 1.0f / kPostScale.Y,
		1.0f / kPostScale.Z));
	// Yaw -90 turns the text's readable face from +X to -Y, the side the yard is
	// walked from.
	CoinsBoard->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	CoinsBoard->SetMobility(EComponentMobility::Movable);
	CoinsBoard->SetHorizontalAlignment(EHTA_Center);
	CoinsBoard->SetVerticalAlignment(EVRTA_TextBottom);
	CoinsBoard->SetWorldSize(34.0f);
	CoinsBoard->SetTextRenderColor(FColor(180, 240, 255));

	Tags.Add(FName("MarketLedger"));
}

void AMarketLedgerActor::BeginPlay()
{
	Super::BeginPlay();

	// The board opens honest, and then the keeper -- which knows whether the day has a
	// history -- corrects it in the same frame. A board that comes back after the yard
	// reopens must NOT refill the purse, and it does not: it only reports itself.
	ShowCoins(StartingCoins);

	const UGameInstance* const GI = GetGameInstance();
	if (UMarketKeeperSubsystem* const Keeper =
			(GI != nullptr) ? GI->GetSubsystem<UMarketKeeperSubsystem>() : nullptr)
	{
		Keeper->AttachBoard(this);
	}
}

void AMarketLedgerActor::ShowCoins(int32 Coins)
{
	LastShownCoins = Coins;

	if (CoinsBoard != nullptr)
	{
		CoinsBoard->SetText(FText::FromString(
			FString::Printf(TEXT("coins %d  carry %d"), Coins, CarryLimit)));
	}
}
