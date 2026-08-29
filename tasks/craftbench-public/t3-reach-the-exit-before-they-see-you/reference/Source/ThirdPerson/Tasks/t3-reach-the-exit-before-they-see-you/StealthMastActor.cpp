// Copyright CraftBench. All Rights Reserved.

#include "StealthMastActor.h"

#include "CollisionQueryParams.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/EngineTypes.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "StealthGateActor.h"
#include "StealthStartPlateActor.h"
#include "StealthWatcherActor.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kMastLampIntensity = 11000.0f;

	/** The three readings of the board. */
	constexpr int32 kRunning = 0;
	constexpr int32 kAway = 1;
	constexpr int32 kCaught = 2;
}

AStealthMastActor::AStealthMastActor()
{
	// Every frame: a watcher's cone sweeps past somebody at any moment, the truck is
	// always moving, and the yard is allowed a quarter of a second to catch up with
	// what that means.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));

	// An unscaled anchor at floor level is the root, and everything hangs off it at
	// plain centimetres above the floor.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);

	Column = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Column"));
	Column->SetupAttachment(Anchor);
	if (CylMesh.Succeeded())
	{
		Column->SetStaticMesh(CylMesh.Object);
	}
	// A 50 cm mast, 600 cm tall, standing on the floor.
	Column->SetRelativeLocation(FVector(0.0f, 0.0f, 300.0f));
	Column->SetRelativeScale3D(FVector(0.5f, 0.5f, 6.0f));
	Column->SetCollisionProfileName(TEXT("NoCollision"));
	Column->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ColumnLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (ColumnLook.Succeeded())
	{
		Column->SetMaterial(0, ColumnLook.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Dark.Succeeded())
	{
		DarkLook = Dark.Object;
	}

	// Every lamp hangs off the ANCHOR, never off the column: the column is scaled 6x
	// vertically and a child inherits its parent's scale, so 300 cm up a 6x column is
	// 1,800 cm up. Off the anchor these heights are plain centimetres above the floor.
	auto MakeShade = [this](const TCHAR* Name, float FloorZ)
	{
		UStaticMeshComponent* const Shade =
			CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Shade->SetupAttachment(Anchor);
		if (SphereMesh.Succeeded())
		{
			Shade->SetStaticMesh(SphereMesh.Object);
		}
		Shade->SetRelativeLocation(FVector(0.0f, 0.0f, FloorZ));
		// 80 cm across: 0.8 of the engine sphere, with nothing to undo.
		Shade->SetRelativeScale3D(FVector(0.8f, 0.8f, 0.8f));
		Shade->SetCollisionProfileName(TEXT("NoCollision"));
		Shade->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		if (DarkLook != nullptr)
		{
			Shade->SetMaterial(0, DarkLook);
		}
		return Shade;
	};

	auto MakeLight = [this](const TCHAR* Name, float FloorZ, const FLinearColor& Colour)
	{
		UPointLightComponent* const Light =
			CreateDefaultSubobject<UPointLightComponent>(Name);
		Light->SetupAttachment(Anchor);
		Light->SetRelativeLocation(FVector(0.0f, 0.0f, FloorZ));
		Light->SetLightColor(Colour);
		Light->SetIntensity(0.0f);
		Light->SetAttenuationRadius(2600.0f);
		Light->SetMobility(EComponentMobility::Movable);
		return Light;
	};

	RunningShade = MakeShade(TEXT("RunningShade"), 520.0f);
	AwayShade = MakeShade(TEXT("AwayShade"), 400.0f);
	CaughtShade = MakeShade(TEXT("CaughtShade"), 280.0f);

	RunningLight = MakeLight(TEXT("RunningLight"), 520.0f, FLinearColor(1.0f, 0.86f, 0.42f));
	AwayLight = MakeLight(TEXT("AwayLight"), 400.0f, FLinearColor(0.25f, 1.0f, 0.36f));
	CaughtLight = MakeLight(TEXT("CaughtLight"), 280.0f, FLinearColor(1.0f, 0.18f, 0.14f));

	Tags.Add(FName(TEXT("StealthMast")));
}

void AStealthMastActor::BeginPlay()
{
	Super::BeginPlay();

	// The CAST is resolved once -- the yard is fixed, nothing is spawned or destroyed.
	// Every NUMBER on them is read live, every frame, because that is what changes.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("StealthWatcher")), Found);
	for (AActor* A : Found)
	{
		if (AStealthWatcherActor* W = Cast<AStealthWatcherActor>(A))
		{
			Watchers.Add(W);
		}
	}
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("StealthStartPlate")), Found);
	for (AActor* A : Found)
	{
		if (AStealthStartPlateActor* P = Cast<AStealthStartPlateActor>(A))
		{
			Plate = P;
			break;
		}
	}
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("StealthGate")), Found);
	for (AActor* A : Found)
	{
		if (AStealthGateActor* G = Cast<AStealthGateActor>(A))
		{
			Gate = G;
			break;
		}
	}

	// Nobody has stepped on the plate yet, so nothing has ended: the yard is waiting,
	// and waiting reads running. The board owes the yard that light from frame one.
	Outcome = kRunning;
	CaughtBy.Reset();
	SeenRoundIndex = (Plate != nullptr) ? Plate->RoundIndex : 0;
	ShowOutcome();

	for (AStealthWatcherActor* W : Watchers)
	{
		if (W != nullptr)
		{
			W->PaceUuPerSec = W->BasePaceUuPerSec;
			W->SetLampLit(false);
		}
	}
}

void AStealthMastActor::StandDown()
{
	// The outcome feeds back into the watchers -- that is the whole of it. Everybody
	// stands still, whatever any of them might still be able to see from where it
	// stopped; and the only lamps left burning are the ones that were burning when the
	// round ended, which is a REMEMBERED set and not a re-asked question. Asking again
	// here would put every lamp out the moment the runner walked out of the frozen
	// cone, and the yard is supposed to still be showing who caught it.
	for (AStealthWatcherActor* W : Watchers)
	{
		if (W != nullptr)
		{
			W->PaceUuPerSec = 0.0f;
			W->SetLampLit(CaughtBy.Contains(W));
		}
	}
}

bool AStealthMastActor::CanSee(const AStealthWatcherActor* Watcher, const FVector& RunnerAt,
							   const FCollisionQueryParams& Ignore) const
{
	if (Watcher == nullptr)
	{
		return false;
	}
	const FVector Eye = Watcher->GetActorLocation();

	// FLAT: the yard is level and height plays no part in the measurement.
	const FVector To(RunnerAt.X - Eye.X, RunnerAt.Y - Eye.Y, 0.0);
	const double Distance = To.Size();

	// THIS watcher's own reach, read at the moment of use. Inclusive at the edge.
	if (Distance > double(Watcher->SightReachUu))
	{
		return false;
	}
	if (Distance > KINDA_SMALL_NUMBER)
	{
		// THIS watcher's own view width, either side of whichever way it happens to be
		// facing at this instant. Inclusive at the edge.
		const FVector Forward = Watcher->GetActorForwardVector();
		const FVector Facing = FVector(Forward.X, Forward.Y, 0.0).GetSafeNormal();
		const double AngleDeg = FMath::RadiansToDegrees(FMath::Acos(
			FMath::Clamp(FVector::DotProduct(Facing, To / Distance), -1.0, 1.0)));
		if (AngleDeg > double(Watcher->SightHalfAngleDeg))
		{
			return false;
		}
	}

	// Nothing solid between the two of them. The line is taken flat, at the watcher's
	// own height: everything in this yard that blocks stands from the floor to well
	// over head height, and everything that does not block is not solid at all, so the
	// height the line is taken at cannot change the answer.
	const UWorld* const W = GetWorld();
	if (W == nullptr)
	{
		return true;
	}
	const FVector Target(RunnerAt.X, RunnerAt.Y, Eye.Z);
	const bool bBlocked = W->LineTraceTestByChannel(Eye, Target, ECC_Visibility, Ignore);
	return !bBlocked;
}

void AStealthMastActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// 1. HAS A FRESH ROUND BEGUN? The plate clicks its own number up every time
	//    somebody steps on it, and a changed number -- nothing else -- re-arms the
	//    yard. Read it live: the mast keeps no round of its own.
	if (Plate != nullptr && Plate->RoundIndex != SeenRoundIndex)
	{
		SeenRoundIndex = Plate->RoundIndex;
		Outcome = kRunning;
		CaughtBy.Reset();
	}

	// 2. A ROUND THAT IS OVER STAYS OVER. Neither the gate nor a watcher can add to
	//    the first ending or replace it; the yard simply stands down until the plate
	//    clicks again.
	if (Outcome != kRunning)
	{
		StandDown();
		ShowOutcome();
		return;
	}

	APawn* const Runner = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
	if (Runner == nullptr)
	{
		ShowOutcome();
		return;
	}
	const FVector RunnerAt = Runner->GetActorLocation();

	// The runner and the watchers themselves are not what "solid" means here.
	FCollisionQueryParams Ignore(FName(TEXT("StealthYardSight")), /*bTraceComplex=*/false);
	Ignore.AddIgnoredActor(Runner);
	Ignore.AddIgnoredActor(this);
	for (const AStealthWatcherActor* W : Watchers)
	{
		if (W != nullptr)
		{
			Ignore.AddIgnoredActor(W);
		}
	}

	// 3. WHAT EACH WATCHER CAN SEE, RIGHT NOW. Each one against its OWN two numbers,
	//    from where IT is standing and facing this instant, with the truck, the crates
	//    and the wall where they are this instant. Read each for itself: one watcher
	//    seeing the runner says nothing about what another can see.
	TArray<AStealthWatcherActor*> Seeing;
	for (AStealthWatcherActor* W : Watchers)
	{
		if (W == nullptr)
		{
			continue;
		}
		const bool bSees = CanSee(W, RunnerAt, Ignore);
		W->SetLampLit(bSees);
		if (bSees)
		{
			Seeing.Add(W);
		}
	}

	// 4. HOW THE ROUND ENDS -- and, when it ends because somebody saw the runner, WHO
	//    that was. The set has to be taken HERE, on the frame it happened: a second
	//    later the watchers are standing still and the runner is walking away, so the
	//    same question gives a different answer for ever after.
	const bool bAtGate = (Gate != nullptr) && Gate->IsSomebodyStandingInIt();
	if (Seeing.Num() > 0)
	{
		Outcome = kCaught;
		CaughtBy = Seeing;
	}
	else if (bAtGate)
	{
		Outcome = kAway;
		CaughtBy.Reset();   // nobody caught anybody, so no lamp stays on
	}

	// 5. WHAT THE YARD DOES ABOUT IT. Over: everybody still, and only the lamps of
	//    whoever saw the runner when it ended left burning. Still running: everybody
	//    back at its OWN base pace -- there is no "the" pace, and the sergeant may have
	//    re-set it.
	if (Outcome != kRunning)
	{
		StandDown();
	}
	else
	{
		for (AStealthWatcherActor* W : Watchers)
		{
			if (W != nullptr)
			{
				W->PaceUuPerSec = W->BasePaceUuPerSec;
			}
		}
	}

	ShowOutcome();
}

void AStealthMastActor::ShowOutcome()
{
	// Exactly one of the three, always: the board is set as a whole, never one switch
	// thrown while another is left where it was.
	SetRunningLit(Outcome == kRunning);
	SetAwayLit(Outcome == kAway);
	SetCaughtLit(Outcome == kCaught);
}

void AStealthMastActor::Throw(UPointLightComponent* Light, UStaticMeshComponent* Shade,
							  bool bNewLit)
{
	if (Light != nullptr)
	{
		Light->SetIntensity(bNewLit ? kMastLampIntensity : 0.0f);
	}
	UMaterialInterface* const Look = bNewLit ? LitLook : DarkLook;
	if (Shade != nullptr && Look != nullptr)
	{
		Shade->SetMaterial(0, Look);
	}
}

void AStealthMastActor::SetRunningLit(bool bNewLit)
{
	bRunningLit = bNewLit;
	Throw(RunningLight, RunningShade, bNewLit);
}

void AStealthMastActor::SetAwayLit(bool bNewLit)
{
	bAwayLit = bNewLit;
	Throw(AwayLight, AwayShade, bNewLit);
}

void AStealthMastActor::SetCaughtLit(bool bNewLit)
{
	bCaughtLit = bNewLit;
	Throw(CaughtLight, CaughtShade, bNewLit);
}
