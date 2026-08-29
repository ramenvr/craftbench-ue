// Reference solution for task gp-harvestable-regrow (the g2-3 "Harvestable" port).
// Implements the active/regrowing state machine on the pre-existing
// AHarvestableActor:
//   (1) starts active        — BeginPlay sets the state active and binds the
//                              sphere's begin-overlap event;
//   (2) harvest on overlap   — the first overlap while active logs a message,
//                              switches to regrowing (adds the "Regrowing" tag the
//                              verifier samples), and arms a 5-second one-shot
//                              FTimerManager timer (framerate-independent, not a
//                              tick count — the "Timers" concept the prompt probes);
//   (3) non-harvestable while regrowing — the overlap handler early-returns while
//                              regrowing, so a second walk-in does NOT reset the
//                              5-second clock;
//   (4) returns to active    — the timer callback removes the "Regrowing" tag and
//                              sets the state back to active.

#include "HarvestableActor.h"

#include "Components/SphereComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogHarvestable, Log, All);

AHarvestableActor::AHarvestableActor()
{
	PrimaryActorTick.bCanEverTick = true;

	CollisionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollisionSphere"));
	SetRootComponent(CollisionSphere);
	CollisionSphere->InitSphereRadius(64.0f);
	CollisionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	CollisionSphere->SetCollisionObjectType(ECC_WorldDynamic);
	CollisionSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	CollisionSphere->SetGenerateOverlapEvents(true);

	Tags.Add(FName("HarvestableRoot"));
}

void AHarvestableActor::BeginPlay()
{
	Super::BeginPlay();

	// VARIANT DELTA (starts-regrowing): the initial state is inverted — this
	// submission treats "Regrowing" as the ready-to-harvest marker and tags
	// itself at BeginPlay. The overlap wiring below is byte-identical to the
	// reference; only the starting state differs.
	State = EHarvestableState::Regrowing;
	Tags.AddUnique(FName("Regrowing"));

	if (CollisionSphere != nullptr)
	{
		CollisionSphere->OnComponentBeginOverlap.AddDynamic(this, &AHarvestableActor::OnSphereBeginOverlap);
	}
}

void AHarvestableActor::OnSphereBeginOverlap(
	UPrimitiveComponent* /*OverlappedComponent*/,
	AActor* OtherActor,
	UPrimitiveComponent* /*OtherComp*/,
	int32 /*OtherBodyIndex*/,
	bool /*bFromSweep*/,
	const FHitResult& /*SweepResult*/)
{
	// Ignore self-overlaps and overlaps while already regrowing (no re-harvest,
	// no timer restart).
	if (OtherActor == this || State != EHarvestableState::Active)
	{
		return;
	}

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	// Harvest: log, switch to regrowing, tag it, and arm the 5-second return timer.
	UE_LOG(LogHarvestable, Log, TEXT("Harvested by %s; entering regrowing state."),
		OtherActor != nullptr ? *OtherActor->GetName() : TEXT("unknown"));

	State = EHarvestableState::Regrowing;
	Tags.AddUnique(FName("Regrowing"));

	World->GetTimerManager().SetTimer(
		RegrowTimerHandle, this, &AHarvestableActor::OnRegrowComplete, RegrowSeconds, /*bLoop=*/false);
}

void AHarvestableActor::OnRegrowComplete()
{
	// Return to active: drop the regrowing tag so it can be harvested again.
	State = EHarvestableState::Active;
	Tags.Remove(FName("Regrowing"));
}
