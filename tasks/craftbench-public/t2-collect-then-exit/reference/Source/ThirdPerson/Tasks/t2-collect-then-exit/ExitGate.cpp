// Copyright CraftBench. All Rights Reserved.

#include "ExitGate.h"

#include "ArenaSignboard.h"
#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kOpenIntensity = 6000.0f;  // the level asks for at least 5000
}

AExitGate::AExitGate()
{
	PrimaryActorTick.bCanEverTick = false;

	ExitMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ExitMesh"));
	SetRootComponent(ExitMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		ExitMesh->SetStaticMesh(CubeMesh.Object);
	}
	ExitMesh->SetRelativeScale3D(FVector(0.5f, 5.0f, 3.0f));
	ExitMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 150.0f));
	ExitMesh->SetMobility(EComponentMobility::Static);
	ExitMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	ExitVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("ExitVolume"));
	ExitVolume->SetupAttachment(ExitMesh);
	ExitVolume->SetBoxExtent(FVector(240.0f, 50.0f, 50.0f));
	ExitVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	ExitVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	ExitVolume->SetGenerateOverlapEvents(true);

	ExitLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("ExitLamp"));
	ExitLamp->SetupAttachment(ExitMesh);
	ExitLamp->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
	ExitLamp->SetIntensity(0.0f);
	ExitLamp->SetAttenuationRadius(1500.0f);
	ExitLamp->SetLightColor(FLinearColor(0.35f, 1.0f, 0.45f));
	ExitLamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("ArenaExit"));
}

void AExitGate::BeginPlay()
{
	Super::BeginPlay();

	TArray<AActor*> Boards;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("ArenaBoard")), Boards);
	if (Boards.Num() > 0)
	{
		Board = Cast<AArenaSignboard>(Boards[0]);
	}

	if (ExitVolume != nullptr)
	{
		ExitVolume->OnComponentBeginOverlap.AddDynamic(this, &AExitGate::OnExitBegin);
	}

	// The arena is sealed and empty-handed from the first frame, on screen.
	RefreshReadouts();
}

void AExitGate::NotifyRelicGathered()
{
	if (bWon)
	{
		return;
	}
	++Gathered;
	if (!bOpen && Gathered >= RequiredRelics)
	{
		bOpen = true;
		if (ExitLamp != nullptr)
		{
			ExitLamp->SetIntensity(kOpenIntensity);
			ExitLamp->SetVisibility(true);
		}
	}
	RefreshReadouts();
}

void AExitGate::OnExitBegin(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	// Only an OPEN exit wins, and once won it stays won -- walking out and back in
	// changes nothing.
	if (bWon || !bOpen || Cast<ACharacter>(OtherActor) == nullptr)
	{
		return;
	}
	bWon = true;
	RefreshReadouts();
}

void AExitGate::RefreshReadouts()
{
	AArenaSignboard* const B = Board.Get();
	if (B == nullptr)
	{
		return;
	}
	if (B->TallyText != nullptr)
	{
		B->TallyText->SetText(FText::FromString(
			FString::Printf(TEXT("%d/%d"), Gathered, RequiredRelics)));
	}
	if (B->StatusText != nullptr)
	{
		const TCHAR* const Word = bWon ? TEXT("ESCAPED")
			: (bOpen ? TEXT("OPEN") : TEXT("SEALED"));
		B->StatusText->SetText(FText::FromString(Word));
	}
}
