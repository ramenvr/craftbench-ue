// Copyright CraftBench. All Rights Reserved.

#include "GateBoardActor.h"

#include "CallMarkActor.h"
#include "WingFittingActor.h"
#include "WingPostActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/LevelStreaming.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AGateBoardActor::AGateBoardActor()
{
	// The board keeps itself honest every frame: a wing arrives over several frames and
	// the line has to follow it in. Flipping this on the class DOES reach the board
	// already placed in the level: bCanEverTick is a bare UPROPERTY() on FTickFunction
	// (EngineBaseTypes.h:212), and the level was saved while the class default was
	// false, so the instance stores no override of its own and inherits whatever the
	// class now says.
	PrimaryActorTick.bCanEverTick = true;

	Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));

	// A 520 x 30 x 180 cm board hanging over the gate.
	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board"));
	Board->SetupAttachment(Pivot);
	Board->SetRelativeScale3D(FVector(5.2f, 0.3f, 1.8f));
	Board->SetCollisionProfileName(TEXT("NoCollision"));
	Board->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (CubeMesh.Succeeded())
	{
		Board->SetStaticMesh(CubeMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Look.Succeeded())
	{
		Board->SetMaterial(0, Look.Object);
	}

	Line = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Line"));
	Line->SetupAttachment(Pivot);
	Line->SetRelativeLocation(FVector(0.0f, -20.0f, 0.0f));
	Line->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Line->SetHorizontalAlignment(EHTA_Center);
	Line->SetVerticalAlignment(EVRTA_TextCenter);
	Line->SetWorldSize(120.0f);
	Line->SetTextRenderColor(FColor(255, 240, 200));
	Line->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Line->SetText(FText::GetEmpty());

	Tags.Add(FName(TEXT("GateBoard")));
}

void AGateBoardActor::BeginPlay()
{
	Super::BeginPlay();

	// Nothing has been called yet, and the board says so from the first frame.
	OpenWing = NAME_None;
	OpenSection = NAME_None;
	ShownWing = NAME_None;
	ShownCount = 0;
	Report(NAME_None, 0);

	// Listen to every mark in the building. WHICH wing a mark calls is deliberately not
	// looked up here -- a mark's name is re-lettered while play is running, so the only
	// safe moment to read it is the moment somebody steps on it.
	TArray<AActor*> Marks;
	UGameplayStatics::GetAllActorsWithTag(this, FName(TEXT("CallMark")), Marks);
	for (AActor* Actor : Marks)
	{
		ACallMarkActor* Mark = Cast<ACallMarkActor>(Actor);
		if (Mark != nullptr && Mark->StepVolume != nullptr)
		{
			Mark->StepVolume->OnComponentBeginOverlap.AddDynamic(
				this, &AGateBoardActor::OnSomebodyStepped);
		}
	}
}

void AGateBoardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Count what is ACTUALLY standing rather than assuming three: a wing comes in over
	// several frames, and the board is supposed to report the building, not the plan.
	const int32 Standing = CountStandingFittings(OpenWing);
	if (OpenWing != ShownWing || Standing != ShownCount)
	{
		Report(OpenWing, Standing);
	}
}

void AGateBoardActor::OnSomebodyStepped(UPrimitiveComponent* OverlappedComponent,
	AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex,
	bool bFromSweep, const FHitResult& SweepResult)
{
	if (OverlappedComponent == nullptr || Cast<APawn>(OtherActor) == nullptr)
	{
		return;
	}

	const ACallMarkActor* Mark = Cast<ACallMarkActor>(OverlappedComponent->GetOwner());
	if (Mark == nullptr)
	{
		return;
	}

	// READ AT THE MOMENT OF THE STEP. Anything cached earlier is a different question.
	CallWing(Mark->GetCalledWingName());
}

void AGateBoardActor::CallWing(FName WingName)
{
	// A mark with no name calls nothing, and stepping back onto the mark that is
	// already showing the wing standing in the host changes nothing at all.
	if (WingName.IsNone() || WingName == OpenWing)
	{
		return;
	}

	const FName Section = SectionForWing(WingName);
	if (Section.IsNone())
	{
		return;
	}

	// ONLY the wing that was called before this one comes out. Not every part of the
	// building the world knows about: the hall was never called, and a wing nobody has
	// called is already out.
	if (!OpenSection.IsNone())
	{
		ShowSection(OpenSection, false);
	}
	ShowSection(Section, true);

	OpenWing = WingName;
	OpenSection = Section;
}

FName AGateBoardActor::SectionForWing(FName WingName) const
{
	TArray<AActor*> Posts;
	UGameplayStatics::GetAllActorsWithTag(this, FName(TEXT("WingPost")), Posts);
	for (AActor* Actor : Posts)
	{
		const AWingPostActor* Post = Cast<AWingPostActor>(Actor);
		if (Post != nullptr && Post->WingName == WingName)
		{
			return Post->SectionId;
		}
	}
	return NAME_None;
}

void AGateBoardActor::ShowSection(FName SectionId, bool bStanding)
{
	if (SectionId.IsNone())
	{
		return;
	}

	ULevelStreaming* Section = UGameplayStatics::GetStreamingLevel(this, SectionId);
	if (Section == nullptr)
	{
		return;
	}

	if (bStanding)
	{
		Section->SetShouldBeLoaded(true);
		Section->SetShouldBeVisible(true);
	}
	else
	{
		Section->SetShouldBeVisible(false);
		Section->SetShouldBeLoaded(false);
	}
}

int32 AGateBoardActor::CountStandingFittings(FName WingName) const
{
	if (WingName.IsNone())
	{
		return 0;
	}

	int32 Standing = 0;
	TArray<AActor*> Fittings;
	UGameplayStatics::GetAllActorsOfClass(this, AWingFittingActor::StaticClass(), Fittings);
	for (AActor* Actor : Fittings)
	{
		const AWingFittingActor* Fitting = Cast<AWingFittingActor>(Actor);
		if (Fitting != nullptr && Fitting->WingLabel == WingName)
		{
			++Standing;
		}
	}
	return Standing;
}

void AGateBoardActor::Report(FName WingName, int32 StandingCount)
{
	// FName's own empty value prints as "None", which upper-cases to the NONE the
	// board is supposed to show before anything has been called.
	const FString Name = WingName.ToString().ToUpper();
	const int32 Count = FMath::Max(0, StandingCount);

	if (Line != nullptr)
	{
		Line->SetText(FText::FromString(FString::Printf(TEXT("%s %d"), *Name, Count)));
	}

	ShownWing = WingName;
	ShownCount = Count;
}

FString AGateBoardActor::GetReportedLine() const
{
	return Line != nullptr ? Line->Text.ToString() : FString();
}
