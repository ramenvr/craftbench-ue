// Copyright CraftBench. All Rights Reserved.

#include "MemoryPadActor.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
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
	// no scale of its own -- so every size below is the size it says it is, rather than
	// a number multiplied by a root nobody re-reads.
	const FVector kPlateScale(3.0f, 3.0f, 0.08f);          // 300 x 300 x 8
	constexpr float kPlateCentreZ = 4.0f;

	const FVector kStepExtent(150.0f, 150.0f, 110.0f);     // 300 x 300 in plan, 220 tall
	constexpr float kStepCentreZ = 110.0f;

	// The mast stands at a corner of the pad, clear of where a person's feet go.
	const FVector kMastXY(-130.0f, -130.0f, 0.0f);
	const FVector kMastScale(0.16f, 0.16f, 1.4f);          // 16 x 16 x 140
	constexpr float kMastCentreZ = 70.0f;

	const FVector kHeadScale(0.5f, 0.5f, 0.5f);            // 50 across
	constexpr float kHeadZ = 165.0f;

	constexpr float kSignZ = 235.0f;

	constexpr float kLitIntensity = 6000.0f;
	const FLinearColor kLampColour(1.0f, 0.86f, 0.42f);

	const TCHAR* const kMastMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kLitMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");

	/** The keeper outlives every pad, so a pad asks for it rather than holding one. */
	UYardMemorySubsystem* KeeperFor(const AActor* Who)
	{
		const UGameInstance* const GI = (Who != nullptr) ? Who->GetGameInstance() : nullptr;
		return (GI != nullptr) ? GI->GetSubsystem<UYardMemorySubsystem>() : nullptr;
	}
}

AMemoryPadActor::AMemoryPadActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));

	USceneComponent* const Base = CreateDefaultSubobject<USceneComponent>(TEXT("Base"));
	SetRootComponent(Base);
	// MOVABLE, and it matters: the yard destroys these and spawns fresh ones part way
	// through, and a Static root placed at runtime logs a PIE mobility warning that a
	// functional test scores as a failure.
	Base->SetMobility(EComponentMobility::Movable);

	Plate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plate"));
	Plate->SetupAttachment(Base);
	if (CubeMesh.Succeeded())
	{
		Plate->SetStaticMesh(CubeMesh.Object);
	}
	Plate->SetRelativeLocation(FVector(0.0f, 0.0f, kPlateCentreZ));
	Plate->SetRelativeScale3D(kPlateScale);
	Plate->SetMobility(EComponentMobility::Movable);
	// Paint, not a step -- the PROFILE as well as the enum, because paint that quietly
	// blocks is indistinguishable from a bug.
	Plate->SetCollisionProfileName(TEXT("NoCollision"));
	Plate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlateLook(kLitMaterial);
	if (PlateLook.Succeeded())
	{
		Plate->SetMaterial(0, PlateLook.Object);
	}

	Step = CreateDefaultSubobject<UBoxComponent>(TEXT("Step"));
	Step->SetupAttachment(Base);
	Step->SetRelativeLocation(FVector(0.0f, 0.0f, kStepCentreZ));
	Step->SetBoxExtent(kStepExtent);
	Step->SetMobility(EComponentMobility::Movable);
	// THE SUBSTRATE'S TRIGGER RECIPE, verbatim: query-only so it never pushes anybody,
	// overlap against everything (a Block on the character's capsule still resolves to
	// Overlap because the pair takes the WEAKER of the two responses), and overlap
	// events on because both sides have to have them on for anything to fire at all.
	Step->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Step->SetCollisionResponseToAllChannels(ECR_Overlap);
	Step->SetGenerateOverlapEvents(true);
	Step->SetHiddenInGame(true);

	LampPost = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LampPost"));
	LampPost->SetupAttachment(Base);
	if (CubeMesh.Succeeded())
	{
		LampPost->SetStaticMesh(CubeMesh.Object);
	}
	LampPost->SetRelativeLocation(FVector(kMastXY.X, kMastXY.Y, kMastCentreZ));
	LampPost->SetRelativeScale3D(kMastScale);
	LampPost->SetMobility(EComponentMobility::Movable);
	// Non-colliding so nothing standing on the pad can be shoved by its own lamp.
	LampPost->SetCollisionProfileName(TEXT("NoCollision"));
	LampPost->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MastLook(kMastMaterial);
	if (MastLook.Succeeded())
	{
		DarkLook = MastLook.Object;
		LampPost->SetMaterial(0, MastLook.Object);
	}

	LampGlow = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LampGlow"));
	LampGlow->SetupAttachment(Base);
	if (SphereMesh.Succeeded())
	{
		LampGlow->SetStaticMesh(SphereMesh.Object);
	}
	LampGlow->SetRelativeLocation(FVector(kMastXY.X, kMastXY.Y, kHeadZ));
	LampGlow->SetRelativeScale3D(kHeadScale);
	LampGlow->SetMobility(EComponentMobility::Movable);
	LampGlow->SetCollisionProfileName(TEXT("NoCollision"));
	LampGlow->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> HeadLit(kLitMaterial);
	if (HeadLit.Succeeded())
	{
		LitLook = HeadLit.Object;
	}
	if (DarkLook != nullptr)
	{
		LampGlow->SetMaterial(0, DarkLook);
	}

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Base);
	Lamp->SetRelativeLocation(FVector(kMastXY.X, kMastXY.Y, kHeadZ));
	Lamp->SetLightColor(kLampColour);
	Lamp->SetIntensity(0.0f);
	Lamp->SetAttenuationRadius(1800.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	PadSign = CreateDefaultSubobject<UTextRenderComponent>(TEXT("PadSign"));
	PadSign->SetupAttachment(Base);
	PadSign->SetRelativeLocation(FVector(kMastXY.X, kMastXY.Y, kSignZ));
	// Yaw -90 turns the text's readable face from +X to -Y, the side the yard is
	// walked from.
	PadSign->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	PadSign->SetMobility(EComponentMobility::Movable);
	PadSign->SetHorizontalAlignment(EHTA_Center);
	PadSign->SetVerticalAlignment(EVRTA_TextBottom);
	PadSign->SetWorldSize(26.0f);
	PadSign->SetTextRenderColor(FColor(190, 235, 255));

	Tags.Add(FName("MemoryPad"));
}

void AMemoryPadActor::BeginPlay()
{
	Super::BeginPlay();

	// The pad says which pad it is, from the first frame. Supplied; nobody else writes
	// this.
	if (PadSign != nullptr)
	{
		PadSign->SetText(FText::FromString(FString::Printf(TEXT("pad %d"), PadOrder)));
	}

	// Dark from the first frame, whatever the editor left behind. The keeper lights the
	// right one in the same frame.
	ShowLamp(false);

	if (Step != nullptr)
	{
		Step->OnComponentBeginOverlap.AddDynamic(this, &AMemoryPadActor::OnStepBegin);
		Step->OnComponentEndOverlap.AddDynamic(this, &AMemoryPadActor::OnStepEnd);
	}

	// This runs on a FRESH pad too. Registering is also how a reopened yard finds out
	// that the runner has to be set back down, because a pad that turns up in a world
	// already at play is a pad the yard has just put back.
	if (UYardMemorySubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->RegisterPad(this);
	}
}

void AMemoryPadActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UYardMemorySubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->UnregisterPad(this);
	}
	Super::EndPlay(EndPlayReason);
}

void AMemoryPadActor::OnStepBegin(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* Other, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/, const FHitResult& /*Sweep*/)
{
	const APawn* const Runner = Cast<APawn>(Other);
	if (Runner == nullptr || !Runner->IsPlayerControlled() || bRunnerOnPad)
	{
		return;
	}
	bRunnerOnPad = true;

	if (UYardMemorySubsystem* const Keeper = KeeperFor(this))
	{
		Keeper->StandOnPad(this);
	}
}

void AMemoryPadActor::OnStepEnd(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* Other, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/)
{
	const APawn* const Runner = Cast<APawn>(Other);
	if (Runner != nullptr && Runner->IsPlayerControlled())
	{
		bRunnerOnPad = false;
	}
}

void AMemoryPadActor::ShowLamp(bool bLit)
{
	bLastShownLit = bLit;

	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(bLit ? kLitIntensity : 0.0f);
	}
	UMaterialInterface* const Look = bLit ? LitLook : DarkLook;
	if (LampGlow != nullptr && Look != nullptr)
	{
		LampGlow->SetMaterial(0, Look);
	}
}
