// Copyright CraftBench. All Rights Reserved.

#include "RoundHallProps.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace RoundHall
{
	// NOTHING IN THIS HALL SCALES ITS ROOT. A scaled root multiplies both a child's
	// offset AND a child's collision extent (a box's bounds are transformed by the full
	// local-to-world), which is how a 120 x 120 pad becomes an 840 x 960 pad hanging in
	// mid air. Every root below is a plain scene component at unit scale, so every
	// number written here is the number the thing actually is.

	const FName kHallSignTag(TEXT("HallSign"));
	const FName kEntranceStoneTag(TEXT("EntranceStone"));
	const FName kStepMarkTag(TEXT("StepMark"));
	const FName kHoistPlateTag(TEXT("HoistPlate"));
	const FName kSinkholeTag(TEXT("Sinkhole"));

	// Every one of these is resolved once, on the first constructor that asks, and the
	// finders are function-local statics for exactly that reason.
	UStaticMesh* CubeMesh()
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> F(
			TEXT("/Engine/BasicShapes/Cube.Cube"));
		return F.Succeeded() ? F.Object : nullptr;
	}

	UStaticMesh* CylinderMesh()
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> F(
			TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
		return F.Succeeded() ? F.Object : nullptr;
	}

	UMaterialInterface* StoneLook()
	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> F(
			TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"));
		return F.Succeeded() ? F.Object : nullptr;
	}

	UMaterialInterface* BoardLook()
	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> F(
			TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
		return F.Succeeded() ? F.Object : nullptr;
	}

	UMaterialInterface* DarkLook()
	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> F(
			TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
		return F.Succeeded() ? F.Object : nullptr;
	}

	UMaterialInterface* PaintLook()
	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> F(
			TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
		return F.Succeeded() ? F.Object : nullptr;
	}

	/** One place where a fitting is built, so nothing in this hall can be given a
	 *  mobility or a collision setting by accident. Everything is Movable (the hall is
	 *  staged before it runs, and a Static component under a Movable root is a PIE
	 *  error rather than a warning) and everything blocks nothing, so no fitting in the
	 *  hall can trap or trip a runner. The level's own floor is what holds people up. */
	UStaticMeshComponent* MakeMesh(AActor* Owner, USceneComponent* Parent,
		const TCHAR* Name, UStaticMesh* Mesh, const FVector& Offset,
		const FVector& Scale, UMaterialInterface* Look)
	{
		UStaticMeshComponent* const C =
			Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
		if (Mesh != nullptr)
		{
			C->SetStaticMesh(Mesh);
		}
		C->SetupAttachment(Parent);
		C->SetRelativeLocation(Offset);
		C->SetRelativeScale3D(Scale);
		C->SetMobility(EComponentMobility::Movable);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		if (Look != nullptr)
		{
			C->SetMaterial(0, Look);
		}
		return C;
	}

	UTextRenderComponent* MakeFace(AActor* Owner, USceneComponent* Parent,
		const TCHAR* Name, const FVector& Offset, float SizeUu)
	{
		UTextRenderComponent* const T =
			Owner->CreateDefaultSubobject<UTextRenderComponent>(Name);
		T->SetupAttachment(Parent);
		T->SetRelativeLocation(Offset);
		// The glyphs are drawn in the component's own plane; the half turn puts them the
		// right way round for somebody standing in front of the thing. The level author
		// turns the ACTOR to aim it into the room.
		T->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
		T->SetMobility(EComponentMobility::Movable);
		T->SetHorizontalAlignment(EHTA_Center);
		T->SetVerticalAlignment(EVRTA_TextCenter);
		T->SetWorldSize(SizeUu);
		T->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		T->SetText(FText::GetEmpty());
		return T;
	}

	UBoxComponent* MakeVolume(AActor* Owner, USceneComponent* Parent, const TCHAR* Name,
		const FVector& Offset, const FVector& Extent)
	{
		UBoxComponent* const B = Owner->CreateDefaultSubobject<UBoxComponent>(Name);
		B->SetupAttachment(Parent);
		B->SetRelativeLocation(Offset);
		B->SetRelativeScale3D(FVector::OneVector);
		B->SetBoxExtent(Extent);
		B->SetMobility(EComponentMobility::Movable);
		B->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
		B->SetGenerateOverlapEvents(true);
		return B;
	}

	/** Bodies standing in a volume, ONE ENTRY PER BODY. A character arrives with more
	 *  than one part and the parts do not arrive on the same frame, so counting
	 *  components would report several arrivals for one runner walking in once.
	 *  Returns true when this is the first body to arrive. */
	bool AddStanding(TArray<AActor*>& Standing, AActor* Who)
	{
		if (Who == nullptr || Standing.Contains(Who))
		{
			return false;
		}
		Standing.Add(Who);
		return Standing.Num() == 1;
	}

	/** Returns true when the last body has left. */
	bool RemoveStanding(TArray<AActor*>& Standing, AActor* Who)
	{
		if (Who == nullptr || !Standing.Contains(Who))
		{
			return false;
		}
		Standing.Remove(Who);
		return Standing.Num() == 0;
	}

	bool StillOverlapping(UBoxComponent* Volume, AActor* Who)
	{
		return Volume != nullptr && Who != nullptr && Volume->IsOverlappingActor(Who);
	}

	/** Drop anybody who was destroyed while standing in a volume: a body that is gone
	 *  never sends an end-overlap of its own. */
	void ForgetTheDeparted(TArray<AActor*>& Standing)
	{
		for (int32 i = Standing.Num() - 1; i >= 0; --i)
		{
			if (!IsValid(Standing[i]))
			{
				Standing.RemoveAt(i);
			}
		}
	}
}

// --------------------------------------------------------------------------- sign

AHallSignActor::AHallSignActor()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* const Pivot =
		CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	Pivot->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Pivot);

	Board = RoundHall::MakeMesh(this, Pivot, TEXT("Board"), RoundHall::CubeMesh(),
		FVector(0.0f, 0.0f, 90.0f), FVector(0.10f, 2.40f, 1.80f),
		RoundHall::BoardLook());

	Face = RoundHall::MakeFace(this, Pivot, TEXT("Face"),
		FVector(-8.0f, 0.0f, 90.0f), 110.0f);

	Tags.Add(RoundHall::kHallSignTag);
}

void AHallSignActor::BeginPlay()
{
	Super::BeginPlay();

	// A relic comes up showing the number painted on it. One of the hall's signs comes
	// up blank and stays blank until somebody tells it what to show.
	if (bBelongsToTheHall)
	{
		PrintNothing();
	}
	else
	{
		Print(PaintedNumber);
	}
}

void AHallSignActor::Print(int32 Number)
{
	if (Face != nullptr)
	{
		Face->SetText(FText::FromString(FString::FromInt(Number)));
	}
}

void AHallSignActor::PrintNothing()
{
	if (Face != nullptr)
	{
		Face->SetText(FText::GetEmpty());
	}
}

FString AHallSignActor::GetPrintedText() const
{
	return Face != nullptr ? Face->Text.ToString() : FString();
}

// ----------------------------------------------------------------- entrance stone

AEntranceStoneActor::AEntranceStoneActor()
{
	PrimaryActorTick.bCanEverTick = true;

	USceneComponent* const Pivot =
		CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	Pivot->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Pivot);

	Stone = RoundHall::MakeMesh(this, Pivot, TEXT("Stone"), RoundHall::CubeMesh(),
		FVector(0.0f, 0.0f, 60.0f), FVector(0.80f, 1.80f, 1.20f),
		RoundHall::StoneLook());

	Face = RoundHall::MakeFace(this, Pivot, TEXT("Face"),
		FVector(-44.0f, 0.0f, 78.0f), 70.0f);

	Mark = RoundHall::MakeMesh(this, Pivot, TEXT("Mark"), RoundHall::CylinderMesh(),
		FVector(240.0f, 0.0f, 2.0f), FVector(2.60f, 2.60f, 0.04f),
		RoundHall::PaintLook());

	// The doorplate: a second, smaller face low on the same side of the stone. It is
	// built blank and nothing in this file ever writes on it.
	// Low on the same face as the painted number and on the same plane, so both read
	// from the same side of the stone. The big number is 70 uu tall centred at z=78, so
	// its glyphs reach down to about z=43; this one is 34 uu tall centred at z=20 and
	// reaches up to about z=37, and the two never touch.
	Doorplate = RoundHall::MakeFace(this, Pivot, TEXT("Doorplate"),
		FVector(-44.0f, 0.0f, 20.0f), 34.0f);

	Tags.Add(RoundHall::kEntranceStoneTag);
}

void AEntranceStoneActor::BeginPlay()
{
	Super::BeginPlay();
	RefreshFace();
	// The doorplate comes up blank whatever the level did to it, and stays blank until
	// somebody prints on it. Nothing in this file ever does.
	ClearTheDoorplate();
}

void AEntranceStoneActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	RefreshFace();
}

void AEntranceStoneActor::RefreshFace()
{
	// What the stone says and what the stone holds can never disagree.
	if (Face == nullptr)
	{
		return;
	}
	const FString Wanted = FString::FromInt(StartNumber);
	if (!Face->Text.ToString().Equals(Wanted, ESearchCase::CaseSensitive))
	{
		Face->SetText(FText::FromString(Wanted));
	}
}

FVector AEntranceStoneActor::GetMarkCentre() const
{
	return Mark != nullptr ? Mark->GetComponentLocation() : GetActorLocation();
}

void AEntranceStoneActor::PrintOnTheDoorplate(int32 Number)
{
	if (Doorplate != nullptr)
	{
		Doorplate->SetText(FText::FromString(FString::FromInt(Number)));
	}
}

void AEntranceStoneActor::ClearTheDoorplate()
{
	if (Doorplate != nullptr)
	{
		Doorplate->SetText(FText::GetEmpty());
	}
}

FString AEntranceStoneActor::GetDoorplateText() const
{
	return Doorplate != nullptr ? Doorplate->Text.ToString() : FString();
}

// --------------------------------------------------------------------- step mark

AStepMarkActor::AStepMarkActor()
{
	PrimaryActorTick.bCanEverTick = true;

	USceneComponent* const Pivot =
		CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	Pivot->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Pivot);

	Slab = RoundHall::MakeMesh(this, Pivot, TEXT("Slab"), RoundHall::CylinderMesh(),
		FVector(0.0f, 0.0f, 2.0f), FVector(2.80f, 2.80f, 0.04f),
		RoundHall::PaintLook());

	Post = RoundHall::MakeMesh(this, Pivot, TEXT("Post"), RoundHall::CubeMesh(),
		FVector(0.0f, -170.0f, 110.0f), FVector(0.12f, 0.12f, 2.20f),
		RoundHall::StoneLook());

	Face = RoundHall::MakeFace(this, Pivot, TEXT("Face"),
		FVector(0.0f, -170.0f, 250.0f), 90.0f);

	Volume = RoundHall::MakeVolume(this, Pivot, TEXT("Volume"),
		FVector(0.0f, 0.0f, 95.0f), FVector(140.0f, 140.0f, 95.0f));

	Tags.Add(RoundHall::kStepMarkTag);
}

void AStepMarkActor::BeginPlay()
{
	Super::BeginPlay();

	if (Volume != nullptr)
	{
		Volume->OnComponentBeginOverlap.AddDynamic(
			this, &AStepMarkActor::HandleVolumeBegin);
		Volume->OnComponentEndOverlap.AddDynamic(
			this, &AStepMarkActor::HandleVolumeEnd);
	}
	RefreshFace();
}

void AStepMarkActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	RefreshFace();
	RoundHall::ForgetTheDeparted(Standing);
}

void AStepMarkActor::RefreshFace()
{
	// The step written on the mark can change while the hall is running. What the mark
	// SAYS follows what the mark HOLDS, every frame, so a reader and a walker are never
	// looking at two different numbers.
	if (Face == nullptr)
	{
		return;
	}
	const FString Wanted = FString::Printf(TEXT("+%d"), StepWritten);
	if (!Face->Text.ToString().Equals(Wanted, ESearchCase::CaseSensitive))
	{
		Face->SetText(FText::FromString(Wanted));
	}
}

void AStepMarkActor::HandleVolumeBegin(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* OtherActor, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/, const FHitResult& /*SweepResult*/)
{
	if (Cast<APawn>(OtherActor) == nullptr)
	{
		return;
	}
	if (RoundHall::AddStanding(Standing, OtherActor))
	{
		OnSteppedOn.Broadcast(OtherActor);
	}
}

void AStepMarkActor::HandleVolumeEnd(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* OtherActor, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/)
{
	if (Cast<APawn>(OtherActor) == nullptr)
	{
		return;
	}
	// One part of a body leaving is not the body leaving.
	if (RoundHall::StillOverlapping(Volume, OtherActor))
	{
		return;
	}
	if (RoundHall::RemoveStanding(Standing, OtherActor))
	{
		OnSteppedOff.Broadcast(OtherActor);
	}
}

// ------------------------------------------------------------------- hoist plate

AHoistPlateActor::AHoistPlateActor()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* const Pivot =
		CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	Pivot->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Pivot);

	Plate = RoundHall::MakeMesh(this, Pivot, TEXT("Plate"), RoundHall::CylinderMesh(),
		FVector(0.0f, 0.0f, 3.0f), FVector(2.40f, 2.40f, 0.06f),
		RoundHall::PaintLook());

	Volume = RoundHall::MakeVolume(this, Pivot, TEXT("Volume"),
		FVector(0.0f, 0.0f, 95.0f), FVector(120.0f, 120.0f, 95.0f));

	RaiseSocket = CreateDefaultSubobject<USceneComponent>(TEXT("RaiseSocket"));
	RaiseSocket->SetupAttachment(Pivot);
	RaiseSocket->SetRelativeLocation(FVector(0.0f, 320.0f, 240.0f));
	RaiseSocket->SetMobility(EComponentMobility::Movable);

	Tags.Add(RoundHall::kHoistPlateTag);
}

void AHoistPlateActor::BeginPlay()
{
	Super::BeginPlay();

	if (Volume != nullptr)
	{
		Volume->OnComponentBeginOverlap.AddDynamic(
			this, &AHoistPlateActor::HandleVolumeBegin);
		Volume->OnComponentEndOverlap.AddDynamic(
			this, &AHoistPlateActor::HandleVolumeEnd);
	}
}

void AHoistPlateActor::HandleVolumeBegin(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* OtherActor, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/, const FHitResult& /*SweepResult*/)
{
	if (Cast<APawn>(OtherActor) == nullptr)
	{
		return;
	}
	// A body that is gone never sends an end-overlap of its own, so anybody who left the
	// world while standing here is dropped before this arrival is counted. Without it one
	// runner ending on the plate would leave the hoist unable to raise anything ever
	// again -- the plate would still be there, and it would silently do nothing.
	RoundHall::ForgetTheDeparted(Standing);
	if (RoundHall::AddStanding(Standing, OtherActor))
	{
		RaiseSign();
	}
}

void AHoistPlateActor::HandleVolumeEnd(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* OtherActor, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/)
{
	if (Cast<APawn>(OtherActor) == nullptr)
	{
		return;
	}
	if (RoundHall::StillOverlapping(Volume, OtherActor))
	{
		return;
	}
	RoundHall::ForgetTheDeparted(Standing);
	RoundHall::RemoveStanding(Standing, OtherActor);
}

AHallSignActor* AHoistPlateActor::RaiseSign()
{
	UWorld* const World = GetWorld();
	if (World == nullptr || RaiseSocket == nullptr)
	{
		return nullptr;
	}

	// The new sign is of the SAME KIND as a sign the hall already has. The kind is read
	// off a standing sign at the moment of raising rather than named here, so a hall
	// whose signs are of some other kind raises that kind too.
	TArray<AActor*> Signs;
	UGameplayStatics::GetAllActorsWithTag(World, RoundHall::kHallSignTag, Signs);

	AHallSignActor* Template = nullptr;
	for (AActor* A : Signs)
	{
		AHallSignActor* const S = Cast<AHallSignActor>(A);
		if (S != nullptr && S->BelongsToTheHall() && !S->bWasRaisedByTheHoist)
		{
			Template = S;
			break;
		}
	}
	if (Template == nullptr)
	{
		return nullptr;
	}

	const FVector Up = RaiseSocket->GetUpVector() * (RaiseStackStepUu * SignsRaised);
	const FTransform Where(RaiseSocket->GetComponentRotation(),
		RaiseSocket->GetComponentLocation() + Up, FVector::OneVector);

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.Owner = this;

	AHallSignActor* const Raised =
		World->SpawnActor<AHallSignActor>(Template->GetClass(), Where, Params);
	if (Raised == nullptr)
	{
		return nullptr;
	}

	// It is one of the hall's from the moment it exists, and it is blank.
	Raised->bBelongsToTheHall = true;
	Raised->bWasRaisedByTheHoist = true;
	Raised->PrintNothing();
	++SignsRaised;

	OnSignRaised.Broadcast(Raised);
	return Raised;
}

// ---------------------------------------------------------------------- sinkhole

ASinkholeActor::ASinkholeActor()
{
	PrimaryActorTick.bCanEverTick = true;

	USceneComponent* const Pivot =
		CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	Pivot->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Pivot);

	Rim = RoundHall::MakeMesh(this, Pivot, TEXT("Rim"), RoundHall::CylinderMesh(),
		FVector(0.0f, 0.0f, 4.0f), FVector(4.40f, 4.40f, 0.08f),
		RoundHall::DarkLook());

	Shaft = RoundHall::MakeMesh(this, Pivot, TEXT("Shaft"), RoundHall::CylinderMesh(),
		FVector(0.0f, 0.0f, -240.0f), FVector(4.00f, 4.00f, 4.80f),
		RoundHall::DarkLook());

	Volume = RoundHall::MakeVolume(this, Pivot, TEXT("Volume"),
		FVector(0.0f, 0.0f, 90.0f), FVector(200.0f, 200.0f, 90.0f));

	Tags.Add(RoundHall::kSinkholeTag);
}

void ASinkholeActor::BeginPlay()
{
	Super::BeginPlay();

	if (Volume != nullptr)
	{
		Volume->OnComponentBeginOverlap.AddDynamic(
			this, &ASinkholeActor::HandleVolumeBegin);
	}
}

void ASinkholeActor::HandleVolumeBegin(UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* OtherActor, UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/, const FHitResult& /*SweepResult*/)
{
	APawn* const Runner = Cast<APawn>(OtherActor);
	if (Runner == nullptr || Falling.Contains(Runner))
	{
		return;
	}
	// The hole lets the frame finish before it takes anybody, so nothing is destroyed
	// in the middle of the engine noticing the touch.
	Falling.Add(Runner);
}

void ASinkholeActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Falling.Num() == 0)
	{
		return;
	}

	int32 Taken = 0;
	for (APawn* Runner : Falling)
	{
		if (IsValid(Runner))
		{
			Runner->Destroy();
			++Taken;
		}
	}
	Falling.Reset();

	// Said only once the runner is actually gone, so whoever listens is free to act on
	// the same frame.
	for (int32 i = 0; i < Taken; ++i)
	{
		++RunnersLost;
		OnRunnerLost.Broadcast();
	}
}
