// Copyright CraftBench. All Rights Reserved.

#include "MarketStallActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/GameInstance.h"
#include "GameFramework/Pawn.h"
#include "MarketKeeperSubsystem.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// A 200 x 100 x 200 counter. The cube mesh is centred on the component origin and
	// the counter IS the root, so a stall stands at half its own height -- the yard
	// places every stall at z = 100 and every offset below is measured from there.
	const FVector kCounterScale(2.0f, 1.0f, 2.0f);

	// The mat sits 300 in FRONT of the counter (-Y is the customer's side) and is 240
	// square in plan. 110 of half-height with its centre 110 up means it spans the
	// floor to 220 -- the walking capsule's centre sits 96 up, so a character standing
	// on the mat is unambiguously inside it and a character walking the lane 580 uu
	// clear of its near edge is unambiguously not.
	const FVector kMatOffset(0.0f, -300.0f, 10.0f);
	const FVector kMatExtent(120.0f, 120.0f, 110.0f);

	// Paint on the floor, in the mat's own footprint: 4 above the floor is -96 from
	// the counter's centre.
	const FVector kMatPlateOffset(0.0f, -300.0f, -96.0f);
	const FVector kMatPlateSize(2.4f, 2.4f, 0.08f);

	const FVector kSignOffset(0.0f, -62.0f, 150.0f);
	const TCHAR* const kCounterMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kMatMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");

	/** The keeper outlives every stall, so a stall asks for it rather than holding one. */
	UMarketKeeperSubsystem* KeeperFor(const AActor* Who)
	{
		const UGameInstance* const GI = (Who != nullptr) ? Who->GetGameInstance() : nullptr;
		return (GI != nullptr) ? GI->GetSubsystem<UMarketKeeperSubsystem>() : nullptr;
	}
}

AMarketStallActor::AMarketStallActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Counter = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Counter"));
	SetRootComponent(Counter);
	if (CubeMesh.Succeeded())
	{
		Counter->SetStaticMesh(CubeMesh.Object);
	}
	Counter->SetRelativeScale3D(kCounterScale);
	// MOVABLE, and it matters: the yard destroys these and spawns fresh ones part way
	// through the day. A Static root that is placed at runtime logs a PIE mobility
	// warning and the functional test scores that as a failure.
	Counter->SetMobility(EComponentMobility::Movable);
	Counter->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> CounterLook(
		kCounterMaterial);
	if (CounterLook.Succeeded())
	{
		Counter->SetMaterial(0, CounterLook.Object);
	}
	Mat = CreateDefaultSubobject<UBoxComponent>(TEXT("Mat"));
	Mat->SetupAttachment(Counter);
	// Divided back out of the counter's scale: children inherit it.
	Mat->SetRelativeLocation(FVector(kMatOffset.X / kCounterScale.X,
		kMatOffset.Y / kCounterScale.Y, kMatOffset.Z / kCounterScale.Z));
	Mat->SetRelativeScale3D(FVector(1.0f / kCounterScale.X, 1.0f / kCounterScale.Y,
		1.0f / kCounterScale.Z));
	Mat->SetBoxExtent(kMatExtent);
	Mat->SetMobility(EComponentMobility::Movable);
	// THE SUBSTRATE'S TRIGGER RECIPE, verbatim: the same three lines the shipped
	// portal and relic scaffolds use. Query-only so it never pushes anybody, overlap
	// against everything (a Block on the character's capsule still resolves to Overlap
	// because the pair takes the WEAKER of the two responses), and overlap events on
	// because both sides have to have them on for anything to fire at all.
	Mat->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Mat->SetCollisionResponseToAllChannels(ECR_Overlap);
	Mat->SetGenerateOverlapEvents(true);
	Mat->SetHiddenInGame(true);

	MatPlate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MatPlate"));
	MatPlate->SetupAttachment(Counter);
	if (CubeMesh.Succeeded())
	{
		MatPlate->SetStaticMesh(CubeMesh.Object);
	}
	// A 240 x 240 x 8 slab lying on the floor, drawn in the mat's own footprint so
	// there is no argument about where the mat is when a person plays this.
	MatPlate->SetRelativeLocation(FVector(kMatPlateOffset.X / kCounterScale.X,
		kMatPlateOffset.Y / kCounterScale.Y, kMatPlateOffset.Z / kCounterScale.Z));
	MatPlate->SetRelativeScale3D(FVector(kMatPlateSize.X / kCounterScale.X,
		kMatPlateSize.Y / kCounterScale.Y, kMatPlateSize.Z / kCounterScale.Z));
	MatPlate->SetMobility(EComponentMobility::Movable);
	// Paint, not a step. The PROFILE as well as the enum: a profile left at BlockAll
	// with collision merely disabled did not survive into a saved level on an earlier
	// task, and paint that quietly blocks is indistinguishable from a bug.
	MatPlate->SetCollisionProfileName(TEXT("NoCollision"));
	MatPlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Sign = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Sign"));
	Sign->SetupAttachment(Counter);
	Sign->SetRelativeLocation(FVector(kSignOffset.X / kCounterScale.X,
		kSignOffset.Y / kCounterScale.Y, kSignOffset.Z / kCounterScale.Z));
	Sign->SetRelativeScale3D(FVector(1.0f / kCounterScale.X, 1.0f / kCounterScale.Y,
		1.0f / kCounterScale.Z));
	// Yaw -90 turns the text's readable face from +X to -Y, which is the side the
	// customer walks up from.
	Sign->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	Sign->SetMobility(EComponentMobility::Movable);
	Sign->SetHorizontalAlignment(EHTA_Center);
	Sign->SetVerticalAlignment(EVRTA_TextBottom);
	Sign->SetWorldSize(26.0f);
	Sign->SetTextRenderColor(FColor(255, 232, 170));

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MatMaterial(
		kMatMaterial);
	if (MatMaterial.Succeeded())
	{
		MatPlate->SetMaterial(0, MatMaterial.Object);
	}

	Tags.Add(FName("MarketStall"));
}

void AMarketStallActor::BeginPlay()
{
	Super::BeginPlay();

	// The yard opens honest: whatever the editor left on the sign, the first frame
	// shows what this stall is actually asking and actually holding, and nothing
	// owned. The keeper corrects it in the same frame if the day has a history.
	ShowSign(PriceCoins, StockCount, 0);

	if (Mat != nullptr)
	{
		Mat->OnComponentBeginOverlap.AddDynamic(this, &AMarketStallActor::OnMatBegin);
		Mat->OnComponentEndOverlap.AddDynamic(this, &AMarketStallActor::OnMatEnd);
	}
	// This runs on a FRESH stall too -- the reopened yard spawns these into a world
	// that has already begun play, so BeginPlay is where a stall finds out what it is
	// coming back to.
	if (UMarketKeeperSubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->AttachStall(this);
	}
}

void AMarketStallActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UMarketKeeperSubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->DetachStall(this);
	}
	Super::EndPlay(EndPlayReason);
}

void AMarketStallActor::OnMatBegin(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* Other, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/, const FHitResult& /*Sweep*/)
{
	const APawn* const Buyer = Cast<APawn>(Other);
	if (Buyer == nullptr || !Buyer->IsPlayerControlled() || bBuyerOnMat)
	{
		return;
	}
	bBuyerOnMat = true;
	if (UMarketKeeperSubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->TryBuy(this);
	}
}

void AMarketStallActor::OnMatEnd(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* Other, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/)
{
	const APawn* const Buyer = Cast<APawn>(Other);
	if (Buyer != nullptr && Buyer->IsPlayerControlled())
	{
		bBuyerOnMat = false;
	}
}

void AMarketStallActor::ShowSign(int32 Price, int32 Stock, int32 Owned)
{
	LastShownPrice = Price;
	LastShownStock = Stock;
	LastShownOwned = Owned;

	if (Sign != nullptr)
	{
		Sign->SetText(FText::FromString(FString::Printf(
			TEXT("%s  price %d  left %d  yours %d  came %d  holds %d"),
			*GoodsName.ToString(), Price, Stock, Owned, DeliveredSinceClose,
			StockCapacity)));
	}
}
