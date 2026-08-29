// Reference solution for task gp-spawner-population (the g2-4 "Spawner" port).
// Implements the three required behaviors on the pre-existing ASpawnerActor:
//   (1) spawn-on-BeginPlay  — N minions at random points within SpawnRadius,
//                             each tagged "SpawnedMinion" and given a scene root
//                             so its world location is real (the verifier checks
//                             each minion is within radius of the host);
//   (2) respawn-on-destroy  — each minion's OnDestroyed delegate calls back here
//                             and a replacement is spawned (delegate-driven, the
//                             "Delegates" concept the prompt probes);
//   (3) cleanup-on-destroy  — EndPlay destroys every tracked minion. bShuttingDown
//                             gates OnMinionDestroyed so the cascade of teardown
//                             callbacks does NOT respawn during shutdown.

#include "SpawnerActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

ASpawnerActor::ASpawnerActor()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("SpawnerRoot"));
}

void ASpawnerActor::BeginPlay()
{
	Super::BeginPlay();

	// Showcase-visibility only: a small cone marks the spawner itself; the
	// verifier never asserts on meshes. Attached at runtime (not in the
	// constructor) so the map-placed instance's serialized root/transform is
	// untouched; collision is disabled so gameplay/verifier behavior is
	// byte-identical.
	if (USceneComponent* ExistingRoot = GetRootComponent())
	{
		if (UStaticMesh* ConeMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone")))
		{
			UStaticMeshComponent* SpawnerVisual = NewObject<UStaticMeshComponent>(this, TEXT("SpawnerShowcaseVisual"));
			SpawnerVisual->SetMobility(EComponentMobility::Movable);
			SpawnerVisual->SetStaticMesh(ConeMesh);
			SpawnerVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			SpawnerVisual->SetGenerateOverlapEvents(false);
			SpawnerVisual->SetupAttachment(ExistingRoot);
			SpawnerVisual->SetRelativeScale3D(FVector(0.5f));
			SpawnerVisual->RegisterComponent();
		}
	}

	bShuttingDown = false;
	Minions.Reset();
	for (int32 i = 0; i < TargetPopulation; ++i)
	{
		SpawnOneMinion();
	}
}

void ASpawnerActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	// Mark shutdown first so the OnDestroyed callbacks below do not respawn.
	bShuttingDown = true;

	// Snapshot + clear the list before destroying so the (synchronous) destroyed
	// callbacks don't mutate the array we're iterating.
	TArray<AActor*> ToDestroy = Minions;
	Minions.Reset();
	for (AActor* Minion : ToDestroy)
	{
		if (IsValid(Minion))
		{
			Minion->Destroy();
		}
	}

	Super::EndPlay(EndPlayReason);
}

AActor* ASpawnerActor::SpawnOneMinion()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return nullptr;
	}

	// VARIANT DELTA (far-offset-spawn): the spawn ring is TEN TIMES the
	// intended radius — a units/scale slip, e.g. reading "500" as metres. The
	// distance is FIXED rather than random so the leg is deterministic: every
	// minion lands 5000 units out, well past the verifier's 650 limit, no
	// matter where the host reports itself. Each minion still gets a real
	// scene root, so its location is genuinely read back — this leg probes the
	// RADIUS gate, not the rootless one (see MATRIX.md for why the rootless
	// route cannot be probed at all).
	const float Angle = FMath::FRandRange(0.0f, 2.0f * PI);
	const float Distance = SpawnRadius * 10.0f;
	const FVector Target = GetActorLocation() + FVector(FMath::Cos(Angle) * Distance, FMath::Sin(Angle) * Distance, 0.0f);

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* Minion = World->SpawnActor<AActor>(AActor::StaticClass(), Target, FRotator::ZeroRotator, Params);
	if (Minion == nullptr)
	{
		return nullptr;
	}

	// A bare AActor has no root component, so its world location would read as
	// (0,0,0). Give it a scene root and place it so the radius check is meaningful.
	// The root is a small cube mesh for review visibility only — the verifier
	// asserts tags/counts/locations, never meshes or pixels; collision is
	// disabled so the mesh cannot perturb any graded behavior.
	UStaticMeshComponent* Root = NewObject<UStaticMeshComponent>(Minion, TEXT("MinionRoot"));
	Root->SetMobility(EComponentMobility::Movable);
	if (UStaticMesh* CubeMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")))
	{
		Root->SetStaticMesh(CubeMesh);
	}
	Root->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Root->SetGenerateOverlapEvents(false);
	// Relative (not world) scale: with no attach parent they are identical,
	// and relative stays correct if an attach is ever inserted above.
	Root->SetRelativeScale3D(FVector(0.4f));
	Minion->SetRootComponent(Root);
	Root->RegisterComponent();
	Minion->SetActorLocation(Target);

	Minion->Tags.Add(FName("SpawnedMinion"));
	Minion->OnDestroyed.AddDynamic(this, &ASpawnerActor::OnMinionDestroyed);
	Minions.Add(Minion);
	return Minion;
}

void ASpawnerActor::OnMinionDestroyed(AActor* DestroyedActor)
{
	Minions.Remove(DestroyedActor);
	if (!bShuttingDown)
	{
		SpawnOneMinion();
	}
}
