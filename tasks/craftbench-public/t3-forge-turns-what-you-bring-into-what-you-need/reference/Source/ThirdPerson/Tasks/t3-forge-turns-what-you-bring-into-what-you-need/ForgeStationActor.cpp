// Copyright CraftBench. All Rights Reserved.

#include "ForgeStationActor.h"

#include "CarrySignActor.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "IngredientHeapActor.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "RecipePlaqueActor.h"
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
	// THE ONE THING IN THE HALL THAT TICKS. The heaps, the plaques and the sign answer
	// questions and decide nothing; all four are placed instances in a map that cannot
	// be edited, so the answer has to land on this class.
	PrimaryActorTick.bCanEverTick = true;

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

// ------------------------------------------------------------- the answer

void AForgeStationActor::BeginPlay()
{
	Super::BeginPlay();

	// THE FACES ARE TRUE FROM THE FIRST FRAME, not from the first delivery. The level
	// ships them reading "--", which is neither an empty forge nor a full one.
	RefreshFaces();
}

void AForgeStationActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const APawn* const Walker = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
	if (Walker == nullptr)
	{
		return;
	}

	RefreshLivePlaques();
	ReadNearbyPlaques(*Walker);
	CollectNearbyHeaps(*Walker);

	if (Carried.Num() > 0
		&& FVector::Dist2D(Walker->GetActorLocation(), GetActorLocation()) <= TakeReachUu)
	{
		TakeDelivery();
	}

	// Rebuilt from the holdings and the read set every tick, NOT only when a craft
	// succeeds: a delivery that spends nothing still changes what the forge is holding,
	// and simply walking up to a plaque changes what it could make next without any
	// delivery happening at all. Both faces have to follow both.
	RefreshFaces();
}

int32 AForgeStationActor::CarryCapNow() const
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return 0;
	}
	// READ OFF THE SIGN, EVERY TIME IT MATTERS. The hall re-posts a different number
	// part way through the run; a cap read once at BeginPlay is right until it is not.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CarrySign")), Found);
	for (const AActor* const A : Found)
	{
		if (const ACarrySignActor* const Sign = Cast<ACarrySignActor>(A))
		{
			return FMath::Max(Sign->CarryCapUnits, 0);
		}
	}
	return 0;
}

int32 AForgeStationActor::CarriedTotal() const
{
	int32 Total = 0;
	for (const TPair<FName, int32>& P : Carried)
	{
		Total += P.Value;
	}
	return Total;
}

void AForgeStationActor::CollectNearbyHeaps(const AActor& Walker)
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	// RE-QUERIED EVERY TICK. The forge spawns a heap of its own whenever it makes
	// something, and that heap is an ingredient like any other -- a list gathered once
	// at BeginPlay would never contain it.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("IngredientHeap")), Found);
	const FVector At = Walker.GetActorLocation();
	const int32 Cap = CarryCapNow();
	for (AActor* A : Found)
	{
		AIngredientHeapActor* const Heap = Cast<AIngredientHeapActor>(A);
		if (Heap == nullptr || Heap->IsEmptied())
		{
			continue;
		}
		// EACH HEAP'S OWN REACH, read off the heap. They are not all the same, and the
		// hall re-stocks them mid-run.
		if (FVector::Dist2D(At, Heap->GetActorLocation()) > Heap->ReachUu)
		{
			continue;
		}
		// ROOM, not the whole heap. Recomputed for every heap in the same frame, so
		// walking into two heaps at once fills up on the first and leaves the second
		// standing exactly where it was. TakeUpTo clamps a zero or negative room to
		// nothing, so "already full" is the same code path as "room for two".
		const int32 Room = Cap - CarriedTotal();
		const FName What = Heap->IngredientId;      // read BEFORE the heap is taken
		const int32 Units = Heap->TakeUpTo(Room);
		if (Units > 0)
		{
			Carried.FindOrAdd(What) += Units;
		}
	}
}

void AForgeStationActor::RefreshLivePlaques()
{
	LivePlaques.Reset();
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RecipePlaque")), Found);
	for (AActor* A : Found)
	{
		if (ARecipePlaqueActor* const Plaque = Cast<ARecipePlaqueActor>(A))
		{
			LivePlaques.Add(Plaque);
		}
	}
}

void AForgeStationActor::ReadNearbyPlaques(const AActor& Walker)
{
	const FVector At = Walker.GetActorLocation();
	for (const ARecipePlaqueActor* const Plaque : LivePlaques)
	{
		if (Plaque == nullptr)
		{
			continue;
		}
		if (FVector::Dist2D(At, Plaque->GetActorLocation()) <= Plaque->ReadReachUu)
		{
			// THE CARVING, not the parsed recipe. Storing the text is what makes a
			// re-carve detectable without standing at the plaque: the wall changes,
			// the stored line stops matching, and the plaque is unknown again.
			CarvingsRead.Add(Plaque->GetName(), Plaque->CarvedText);
		}
	}
}

bool AForgeStationActor::IsKnown(const ARecipePlaqueActor& Plaque) const
{
	const FString* const Read = CarvingsRead.Find(Plaque.GetName());
	return Read != nullptr && *Read == Plaque.CarvedText;
}

bool AForgeStationActor::CoveredBy(const TMap<FName, int32>& Have,
	const TArray<FName>& Need)
{
	// MULTIPLICITIES, and NO MUTATION. "EMBER EMBER EMBER" needs three EMBER, so the
	// units are folded up before comparing -- and nothing is taken out of Have while
	// the test is running, because a recipe that turns out not to fit must leave the
	// holdings exactly as it found them.
	TMap<FName, int32> Want;
	for (const FName& N : Need)
	{
		Want.FindOrAdd(N) += 1;
	}
	for (const TPair<FName, int32>& P : Want)
	{
		const int32* const Got = Have.Find(P.Key);
		if (Got == nullptr || *Got < P.Value)
		{
			return false;
		}
	}
	return true;
}

ARecipePlaqueActor* AForgeStationActor::ChooseRecipe(const TMap<FName, int32>& From) const
{
	// RE-PARSED every time, off THIS TICK's wall. The plaques are re-carved part way
	// through the run, so both the steps and the recipes have to be read now --
	// GetInputs()/GetOutput()/GetTier() re-parse on every call and cache nothing.
	ARecipePlaqueActor* Best = nullptr;
	int32 BestTier = 0;
	for (ARecipePlaqueActor* const Plaque : LivePlaques)
	{
		if (Plaque == nullptr || !IsKnown(*Plaque))
		{
			continue;
		}
		const TArray<FName> Inputs = Plaque->GetInputs();
		if (Inputs.Num() == 0 || Plaque->GetOutput().IsNone() || !CoveredBy(From, Inputs))
		{
			continue;
		}
		// THE HIGHEST STEP CARVED. Not the first that fits: every recipe in this hall
		// takes the same three units, so a count says nothing and the step says
		// everything.
		const int32 Tier = Plaque->GetTier();
		if (Best == nullptr || Tier > BestTier)
		{
			Best = Plaque;
			BestTier = Tier;
		}
	}
	return Best;
}

void AForgeStationActor::TakeDelivery()
{
	// EVERYTHING AT ONCE, added to what it was already holding.
	for (const TPair<FName, int32>& P : Carried)
	{
		Holdings.FindOrAdd(P.Key) += P.Value;
	}
	Carried.Reset();

	// AT MOST ONE THING. Not a loop: having made its one thing the forge stops, even
	// when what is left over could make something else.
	const ARecipePlaqueActor* const Pick = ChooseRecipe(Holdings);
	if (Pick == nullptr)
	{
		// Nothing fits, so nothing is spent and nothing is made. Two units sitting in
		// the forge come out of this delivery as two units.
		return;
	}
	for (const FName& N : Pick->GetInputs())
	{
		int32& Have = Holdings.FindOrAdd(N);
		--Have;
		if (Have <= 0)
		{
			Holdings.Remove(N);
		}
	}
	EjectProduct(Pick->GetOutput());
}

FString AForgeStationActor::FormatHeld(const TMap<FName, int32>& Held)
{
	TArray<FName> Kinds;
	for (const TPair<FName, int32>& P : Held)
	{
		if (P.Value > 0)
		{
			Kinds.Add(P.Key);
		}
	}
	if (Kinds.Num() == 0)
	{
		return TEXT("EMPTY");
	}
	Kinds.Sort([](const FName& A, const FName& B) { return A.ToString() < B.ToString(); });
	FString Line;
	for (int32 i = 0; i < Kinds.Num(); ++i)
	{
		Line += FString::Printf(TEXT("%s%s x%d"), i ? TEXT(" ") : TEXT(""),
			*Kinds[i].ToString(), Held[Kinds[i]]);
	}
	return Line;
}

void AForgeStationActor::RefreshFaces()
{
	const FString HeldLine = FormatHeld(Holdings);
	// The SAME rule, asked of what is being held right now over the recipes that are
	// known right now. It is a forecast, not a second craft: nothing is spent and
	// nothing is set down.
	const ARecipePlaqueActor* const Next = ChooseRecipe(Holdings);
	const FString CanMakeLine = Next != nullptr ? Next->GetOutput().ToString()
											    : FString(TEXT("NOTHING"));
	if (HeldLine == LastHeldLine && CanMakeLine == LastCanMakeLine)
	{
		return;
	}
	LastHeldLine = HeldLine;
	LastCanMakeLine = CanMakeLine;
	ShowReadout(HeldLine, CanMakeLine);
}
