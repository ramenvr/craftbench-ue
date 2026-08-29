// Copyright CraftBench. All Rights Reserved.

#include "MemoryPostActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "YardMemorySubsystem.h"

namespace
{
	// The actor's origin sits ON THE FLOOR, and the root is a bare scene component with
	// no scale of its own. That is deliberate: a scaled root multiplies both a child's
	// offset AND its collision extent, so every number below would mean something other
	// than what it says. Sizes here are what they claim to be.
	const FVector kPillarScale(0.6f, 0.6f, 2.4f);      // 60 x 60 x 240
	constexpr float kPillarCentreZ = 120.0f;

	const FVector kPlateScale(2.6f, 2.6f, 0.08f);      // 260 x 260 x 8
	constexpr float kPlateCentreZ = 4.0f;

	const FVector kGroundExtent(130.0f, 130.0f, 110.0f);   // 260 x 260 in plan, 220 tall
	constexpr float kGroundCentreZ = 110.0f;

	constexpr float kSignZ = 290.0f;

	const TCHAR* const kPillarMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kPlateMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");

	/** The keeper outlives every post, so a post asks for it rather than holding one. */
	UYardMemorySubsystem* KeeperFor(const AActor* Who)
	{
		const UGameInstance* const GI = (Who != nullptr) ? Who->GetGameInstance() : nullptr;
		return (GI != nullptr) ? GI->GetSubsystem<UYardMemorySubsystem>() : nullptr;
	}
}

AMemoryPostActor::AMemoryPostActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	USceneComponent* const Base = CreateDefaultSubobject<USceneComponent>(TEXT("Base"));
	SetRootComponent(Base);
	// MOVABLE, and it matters: the yard destroys these and spawns fresh ones part way
	// through, and a Static root placed at runtime logs a PIE mobility warning that a
	// functional test scores as a failure.
	Base->SetMobility(EComponentMobility::Movable);

	GroundPlate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("GroundPlate"));
	GroundPlate->SetupAttachment(Base);
	if (CubeMesh.Succeeded())
	{
		GroundPlate->SetStaticMesh(CubeMesh.Object);
	}
	GroundPlate->SetRelativeLocation(FVector(0.0f, 0.0f, kPlateCentreZ));
	GroundPlate->SetRelativeScale3D(kPlateScale);
	GroundPlate->SetMobility(EComponentMobility::Movable);
	// Paint, not a step. The PROFILE as well as the enum: a profile left at BlockAll
	// with collision merely disabled did not survive into a saved level on an earlier
	// task, and paint that quietly blocks is indistinguishable from a bug.
	GroundPlate->SetCollisionProfileName(TEXT("NoCollision"));
	GroundPlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlateLook(kPlateMaterial);
	if (PlateLook.Succeeded())
	{
		GroundPlate->SetMaterial(0, PlateLook.Object);
	}

	Pillar = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pillar"));
	Pillar->SetupAttachment(Base);
	if (CubeMesh.Succeeded())
	{
		Pillar->SetStaticMesh(CubeMesh.Object);
	}
	Pillar->SetRelativeLocation(FVector(0.0f, 0.0f, kPillarCentreZ));
	Pillar->SetRelativeScale3D(kPillarScale);
	Pillar->SetMobility(EComponentMobility::Movable);
	Pillar->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PillarLook(kPillarMaterial);
	if (PillarLook.Succeeded())
	{
		Pillar->SetMaterial(0, PillarLook.Object);
	}

	Ground = CreateDefaultSubobject<UBoxComponent>(TEXT("Ground"));
	Ground->SetupAttachment(Base);
	Ground->SetRelativeLocation(FVector(0.0f, 0.0f, kGroundCentreZ));
	Ground->SetBoxExtent(kGroundExtent);
	Ground->SetMobility(EComponentMobility::Movable);
	// THE SUBSTRATE'S TRIGGER RECIPE, verbatim: the same three lines the shipped portal
	// and relic scaffolds use. Query-only so it never pushes anybody, overlap against
	// everything (a Block on the character's capsule still resolves to Overlap because
	// the pair takes the WEAKER of the two responses), and overlap events on because
	// both sides have to have them on for anything to fire at all.
	Ground->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Ground->SetCollisionResponseToAllChannels(ECR_Overlap);
	Ground->SetGenerateOverlapEvents(true);
	Ground->SetHiddenInGame(true);

	WorthSign = CreateDefaultSubobject<UTextRenderComponent>(TEXT("WorthSign"));
	WorthSign->SetupAttachment(Base);
	WorthSign->SetRelativeLocation(FVector(0.0f, 0.0f, kSignZ));
	// Yaw -90 turns the text's readable face from +X to -Y, the side the yard is
	// walked from.
	WorthSign->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	WorthSign->SetMobility(EComponentMobility::Movable);
	WorthSign->SetHorizontalAlignment(EHTA_Center);
	WorthSign->SetVerticalAlignment(EVRTA_TextBottom);
	WorthSign->SetWorldSize(30.0f);
	WorthSign->SetTextRenderColor(FColor(255, 232, 170));

	Tags.Add(FName("MemoryPost"));
}

void AMemoryPostActor::BeginPlay()
{
	Super::BeginPlay();

	// The yard opens honest: whatever the editor left behind, the first frame shows a
	// post standing with the number it is actually carrying. The keeper corrects it in
	// the same frame if the record says this post has already been taken.
	ShowStanding(true);
	ShowWorth(WorthNow);

	if (Ground != nullptr)
	{
		Ground->OnComponentBeginOverlap.AddDynamic(this, &AMemoryPostActor::OnGroundBegin);
		Ground->OnComponentEndOverlap.AddDynamic(this, &AMemoryPostActor::OnGroundEnd);
	}

	// This runs on a FRESH post too -- a reopened yard spawns these into a world that
	// has already begun play, so BeginPlay is where a post finds out what it is coming
	// back to.
	if (UYardMemorySubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->RegisterPost(this);
	}
}

void AMemoryPostActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UYardMemorySubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->UnregisterPost(this);
	}
	Super::EndPlay(EndPlayReason);
}

void AMemoryPostActor::OnGroundBegin(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* Other, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/, const FHitResult& /*Sweep*/)
{
	const APawn* const Runner = Cast<APawn>(Other);
	if (Runner == nullptr || !Runner->IsPlayerControlled() || bRunnerOnGround)
	{
		return;
	}
	bRunnerOnGround = true;

	// Every arrival is offered to the keeper, including arrivals on ground a post has
	// already been taken from -- deciding that such an arrival is worth nothing is the
	// keeper's job and it needs the record to do it.
	if (UYardMemorySubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->TakePost(this);
	}
}

void AMemoryPostActor::OnGroundEnd(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* Other, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/)
{
	const APawn* const Runner = Cast<APawn>(Other);
	if (Runner != nullptr && Runner->IsPlayerControlled())
	{
		bRunnerOnGround = false;
	}
}

void AMemoryPostActor::ShowWorth(int32 Worth)
{
	LastShownWorth = Worth;

	if (WorthSign != nullptr)
	{
		WorthSign->SetText(FText::FromString(
			FString::Printf(TEXT("%s  worth %d"), *PostId.ToString(), Worth)));
	}
}

void AMemoryPostActor::ShowStanding(bool bStanding)
{
	bLastShownStanding = bStanding;

	if (Pillar != nullptr)
	{
		Pillar->SetVisibility(bStanding);
		// The profile, not just the enum: a taken post has to be something a person can
		// walk straight through.
		Pillar->SetCollisionProfileName(bStanding ? TEXT("BlockAll") : TEXT("NoCollision"));
	}
	if (WorthSign != nullptr)
	{
		WorthSign->SetVisibility(bStanding);
	}
	// GroundPlate and Ground are deliberately untouched: the patch stays painted and
	// the volume stays live whether the post is there or not.
}
