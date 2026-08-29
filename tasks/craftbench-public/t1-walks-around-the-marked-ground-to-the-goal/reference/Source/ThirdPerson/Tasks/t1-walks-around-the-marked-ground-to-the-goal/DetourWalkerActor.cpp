// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-walks-around-the-marked-ground-to-the-goal.
//
// The walker PLANS. Local steering -- head for the goal, sidestep when the next step
// lands on out-of-bounds paint -- does not solve this yard: each patch is a U whose
// mouth straddles the straight line, so a steering walker drives into the pocket,
// finds the back wall, and finds an arm whichever way it slides. Getting out means
// going backwards, which is the one move a greedy rule never makes.
//
// So: a grid search over the yard with the out-of-bounds patch blocked, re-run
// whenever which patch is out of bounds changes, and the resulting waypoints walked
// with the supplied StepToward.

#include "DetourWalkerActor.h"

#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "MarkedGroundActor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** Grid pitch for the search. Fine enough to thread the gaps in this yard,
	 *  coarse enough that a re-plan is a few milliseconds. */
	constexpr double kCellUu = 100.0;
	/** How far the plan keeps off the paint. The walker is 35 across the middle;
	 *  the rest is so it does not clip a corner while turning. */
	constexpr double kClearanceUu = 90.0;
	/** How much room to leave around everything the walker knows about. */
	constexpr double kBoundsPadUu = 200.0;
	/** A waypoint is reached a little loosely, or the walker stalls on rounding. */
	constexpr double kWaypointUu = 70.0;
	constexpr int32 kMaxCells = 400;
}

ADetourWalkerActor::ADetourWalkerActor()
{
	// Every frame: the walk is continuous, and the yard can change which patch is
	// out of bounds at any moment.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone"));

	Hull = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Hull"));
	SetRootComponent(Hull);
	// 70 cm across, 180 cm tall. The actor stands with this capsule's CENTRE at its
	// location, the way a character does, so the yard places it at half its height
	// and its feet land on the floor.
	Hull->InitCapsuleSize(35.0f, 90.0f);
	Hull->SetCollisionProfileName(TEXT("BlockAll"));
	Hull->SetMobility(EComponentMobility::Movable);

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Hull);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	Body->SetRelativeScale3D(FVector(0.7f, 0.7f, 1.8f));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (BodyLook.Succeeded())
	{
		Body->SetMaterial(0, BodyLook.Object);
	}

	Snout = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Snout"));
	Snout->SetupAttachment(Hull);
	if (ConeMesh.Succeeded())
	{
		Snout->SetStaticMesh(ConeMesh.Object);
	}
	Snout->SetRelativeScale3D(FVector(0.4f, 0.4f, 0.7f));
	Snout->SetRelativeLocation(FVector(45.0f, 0.0f, 55.0f));
	Snout->SetRelativeRotation(FRotator(-90.0f, 0.0f, 0.0f));
	Snout->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SnoutLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (SnoutLook.Succeeded())
	{
		Snout->SetMaterial(0, SnoutLook.Object);
	}

	Tags.Add(FName("DetourWalker"));
}

void ADetourWalkerActor::BeginPlay()
{
	Super::BeginPlay();

	if (Body != nullptr)
	{
		BodyMaterial = Body->CreateAndSetMaterialInstanceDynamic(0);
	}

	UWorld* const World = GetWorld();
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MarkedGround")), Found);
	for (AActor* A : Found)
	{
		if (AMarkedGroundActor* const M = Cast<AMarkedGroundActor>(A))
		{
			Patches.Add(M);
		}
	}
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("DetourGoal")), Found);
	if (Found.Num() > 0)
	{
		Goal = Found[0];
	}

	// The area worth searching: everything the walker knows about, plus room to walk
	// round the outside of it. Taken from the patches' own footprints rather than
	// from numbers written down here, so it survives the yard being rearranged.
	Field = FBox(ForceInit);
	Field += GetActorLocation();
	if (Goal.IsValid())
	{
		Field += Goal->GetActorLocation();
	}
	for (const TWeakObjectPtr<AMarkedGroundActor>& P : Patches)
	{
		if (P.IsValid())
		{
			Field += P->WorldFootprint();
		}
	}
	Field = Field.ExpandBy(FVector(kBoundsPadUu, kBoundsPadUu, 0.0));
}

AMarkedGroundActor* ADetourWalkerActor::OutOfBoundsPatch() const
{
	for (const TWeakObjectPtr<AMarkedGroundActor>& P : Patches)
	{
		if (P.IsValid() && P->IsOutOfBounds())
		{
			return P.Get();
		}
	}
	return nullptr;
}

bool ADetourWalkerActor::Blocked(const FVector& P,
	const AMarkedGroundActor* Forbidden) const
{
	if (Forbidden == nullptr)
	{
		return false;
	}
	// Sample a ring around the point rather than the point alone: the walker has a
	// width, and a plan that only clears its centre scrapes every corner.
	static const FVector2D kRing[] = {
		{0.0, 0.0}, {1.0, 0.0}, {-1.0, 0.0}, {0.0, 1.0}, {0.0, -1.0},
		{0.7, 0.7}, {0.7, -0.7}, {-0.7, 0.7}, {-0.7, -0.7}};
	for (const FVector2D& O : kRing)
	{
		const FVector Probe(P.X + O.X * kClearanceUu, P.Y + O.Y * kClearanceUu, P.Z);
		if (Forbidden->CoversPoint(Probe))
		{
			return true;
		}
	}
	return false;
}

bool ADetourWalkerActor::Replan()
{
	Plan.Reset();
	Leg = 0;
	if (!Goal.IsValid() || !Field.IsValid)
	{
		return false;
	}
	AMarkedGroundActor* const Forbidden = OutOfBoundsPatch();
	const FVector Here = GetActorLocation();
	const FVector There = Goal->GetActorLocation();

	const int32 NX = FMath::Min(kMaxCells,
		int32((Field.Max.X - Field.Min.X) / kCellUu) + 1);
	const int32 NY = FMath::Min(kMaxCells,
		int32((Field.Max.Y - Field.Min.Y) / kCellUu) + 1);
	if (NX < 2 || NY < 2)
	{
		return false;
	}

	auto PosOf = [&](int32 ix, int32 iy)
	{
		return FVector(Field.Min.X + ix * kCellUu, Field.Min.Y + iy * kCellUu, Here.Z);
	};
	auto CellOf = [&](const FVector& P)
	{
		return TPair<int32, int32>(
			FMath::Clamp(int32(FMath::RoundToInt((P.X - Field.Min.X) / kCellUu)), 0, NX - 1),
			FMath::Clamp(int32(FMath::RoundToInt((P.Y - Field.Min.Y) / kCellUu)), 0, NY - 1));
	};

	TArray<uint8> Open;
	Open.SetNumZeroed(NX * NY);
	for (int32 ix = 0; ix < NX; ++ix)
	{
		for (int32 iy = 0; iy < NY; ++iy)
		{
			Open[ix * NY + iy] = Blocked(PosOf(ix, iy), Forbidden) ? 0 : 1;
		}
	}

	const TPair<int32, int32> S = CellOf(Here);
	const TPair<int32, int32> G = CellOf(There);
	// The walker may legitimately be standing where the plan says it should not be
	// -- it has just been put back at the start, or the marking changed under it.
	// Let it out rather than refusing to plan.
	Open[S.Key * NY + S.Value] = 1;
	Open[G.Key * NY + G.Value] = 1;

	TArray<double> Dist;
	Dist.Init(TNumericLimits<double>::Max(), NX * NY);
	TArray<int32> Came;
	Came.Init(INDEX_NONE, NX * NY);

	auto Index = [&](const TPair<int32, int32>& C) { return C.Key * NY + C.Value; };
	// A plain binary heap over (cost, index). Dijkstra rather than A*: the yard is a
	// few thousand cells and the extra code buys nothing measurable.
	TArray<TPair<double, int32>> Heap;
	Heap.Heapify();
	Dist[Index(S)] = 0.0;
	Heap.HeapPush(TPair<double, int32>(0.0, Index(S)));

	const int32 GoalIndex = Index(G);
	bool bFound = false;
	while (Heap.Num() > 0)
	{
		TPair<double, int32> Top;
		Heap.HeapPop(Top);
		if (Top.Value == GoalIndex)
		{
			bFound = true;
			break;
		}
		if (Top.Key > Dist[Top.Value])
		{
			continue;
		}
		const int32 CX = Top.Value / NY;
		const int32 CY = Top.Value % NY;
		for (int32 DX = -1; DX <= 1; ++DX)
		{
			for (int32 DY = -1; DY <= 1; ++DY)
			{
				if (DX == 0 && DY == 0)
				{
					continue;
				}
				const int32 NXi = CX + DX;
				const int32 NYi = CY + DY;
				if (NXi < 0 || NXi >= NX || NYi < 0 || NYi >= NY)
				{
					continue;
				}
				const int32 NIdx = NXi * NY + NYi;
				if (Open[NIdx] == 0)
				{
					continue;
				}
				const double Cost = Top.Key
					+ kCellUu * FMath::Sqrt(double(DX * DX + DY * DY));
				if (Cost < Dist[NIdx])
				{
					Dist[NIdx] = Cost;
					Came[NIdx] = Top.Value;
					Heap.HeapPush(TPair<double, int32>(Cost, NIdx));
				}
			}
		}
	}
	if (!bFound)
	{
		return false;
	}

	TArray<FVector> Reverse;
	for (int32 At = GoalIndex; At != INDEX_NONE; At = Came[At])
	{
		Reverse.Add(PosOf(At / NY, At % NY));
		if (At == Index(S))
		{
			break;
		}
	}
	Algo::Reverse(Reverse);

	// Keep only the corners. Walking every grid cell makes the route jagged and
	// longer than it needs to be, and the yard grades distance travelled.
	for (int32 i = 0; i < Reverse.Num(); ++i)
	{
		bool bCorner = (i == 0) || (i == Reverse.Num() - 1);
		if (!bCorner)
		{
			const FVector In = (Reverse[i] - Reverse[i - 1]).GetSafeNormal2D();
			const FVector Out = (Reverse[i + 1] - Reverse[i]).GetSafeNormal2D();
			bCorner = FVector::DotProduct(In, Out) < 0.999;
		}
		if (bCorner)
		{
			Plan.Add(Reverse[i]);
		}
	}
	// The real goal, not the grid cell nearest it.
	Plan.Add(FVector(There.X, There.Y, Here.Z));
	PlannedAgainst = Forbidden;
	return Plan.Num() > 0;
}

void ADetourWalkerActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!Goal.IsValid())
	{
		return;
	}
	AMarkedGroundActor* const Forbidden = OutOfBoundsPatch();
	// Re-plan when there is no plan, or when the yard has changed WHICH patch is out
	// of bounds. A route worked out once and reused is exactly what the second trip
	// is there to catch.
	if (Plan.Num() == 0 || Leg >= Plan.Num() || PlannedAgainst.Get() != Forbidden)
	{
		if (!Replan())
		{
			return;
		}
	}

	const FVector Target = Plan[Leg];
	if (FVector::Dist2D(GetActorLocation(), Target) <= kWaypointUu)
	{
		++Leg;
		if (Leg >= Plan.Num())
		{
			return;
		}
	}
	StepToward(Plan[Leg], WalkSpeedUu, DeltaSeconds);
}

void ADetourWalkerActor::StepToward(const FVector& Destination, float SpeedUu,
	float DeltaSeconds)
{
	if (DeltaSeconds <= 0.0f || SpeedUu <= 0.0f)
	{
		return;
	}

	const FVector Here = GetActorLocation();
	// Flat: the yard is level, and letting a destination's height into this would
	// walk the figure into the floor or up into the air.
	const FVector Flat(Destination.X - Here.X, Destination.Y - Here.Y, 0.0);
	const double Distance = Flat.Size();
	if (Distance <= KINDA_SMALL_NUMBER)
	{
		return;
	}

	const FVector Direction = Flat / Distance;
	// Never overshoot: a long frame must not teleport the figure past its target.
	const double Travel = FMath::Min(Distance, double(SpeedUu) * DeltaSeconds);
	SetActorLocation(Here + Direction * Travel, /*bSweep=*/true);
	SetActorRotation(Direction.Rotation());
}

bool ADetourWalkerActor::HasReached(const FVector& Point) const
{
	const FVector Here = GetActorLocation();
	return FVector(Point.X - Here.X, Point.Y - Here.Y, 0.0).Size() <= ArriveRadiusUu;
}
