// Copyright CraftBench. All Rights Reserved.

#include "YardWatchmanCharacter.h"

#include "Animation/AnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "CollisionQueryParams.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "UObject/ConstructorHelpers.h"

AYardWatchmanCharacter::AYardWatchmanCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	// See the header for why this is not optional: without a controller the movement
	// component discards every AddMovementInput and the watchman is an ornament.
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	GetCapsuleComponent()->InitCapsuleSize(42.0f, 96.0f);

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	if (UCharacterMovementComponent* const Move = GetCharacterMovement())
	{
		// Faces the way it walks, so a human watching can see where it is going.
		Move->bOrientRotationToMovement = true;
		Move->bUseControllerDesiredRotation = false;
		Move->RotationRate = FRotator(0.0f, 420.0f, 0.0f);
		Move->MaxWalkSpeed = WalkPaceUuPerSecond;
		Move->BrakingDecelerationWalking = 2000.0f;
		Move->MaxAcceleration = 1600.0f;
	}

	// Quinn, so the two watchmen read as a different party from Manny, whom the player
	// controls. The -90 offset puts the mesh's feet on the capsule's base.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -96.0), FRotator(0.0, -90.0, 0.0));
	}
	static ConstructorHelpers::FClassFinder<UAnimInstance> AnimFinder(
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
	if (AnimFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetAnimInstanceClass(AnimFinder.Class);
	}

	Tags.Add(FName("YardWatchman"));
}

void AYardWatchmanCharacter::BeginPlay()
{
	Super::BeginPlay();

	// Its post is where the yard put it. Latched once, before anything can move it.
	PostLocation = GetActorLocation();

	// The placed instance carries the yard's pace, which the class default does not
	// know about, so mirror it now rather than in the constructor alone.
	if (UCharacterMovementComponent* const Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = WalkPaceUuPerSecond;
	}
}

bool AYardWatchmanCharacter::CanSeeActor(const AActor* Other) const
{
	if (Other == nullptr)
	{
		return false;
	}
	const UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	// Chest to chest. APawn::GetPawnViewLocation() is GetActorLocation() + eye height
	// (Pawn.cpp:355), so both ends are derived the same way whichever pawn this is.
	const FVector From = GetPawnViewLocation();
	const APawn* const OtherPawn = Cast<APawn>(Other);
	const FVector To = (OtherPawn != nullptr)
		? OtherPawn->GetPawnViewLocation()
		: Other->GetActorLocation();

	if (FVector::Dist(From, To) > SightRangeUu)
	{
		return false;
	}
	FCollisionQueryParams Params(FName(TEXT("YardWatchmanSight")), /*bTraceComplex=*/false, this);
	Params.AddIgnoredActor(Other);
	// NB: belt and braces only. BaseEngine.ini:3110 gives the "Pawn" collision profile
	// (which ACharacter's capsule uses, Character.cpp:79) Visibility=ECR_Ignore, and
	// :3112 does the same for "CharacterMesh", so no pawn can block this trace anyway.
	// Only the yard's walls and its floor can. Anyone re-profiling a wall to something
	// pawn-like deletes every sight break in the level.
	return !World->LineTraceTestByChannel(From, To, ECC_Visibility, Params);
}

void AYardWatchmanCharacter::WalkToSpot(const FVector& Spot)
{
	bHasGoal = true;
	GoalSpot = Spot;
}

void AYardWatchmanCharacter::StandStill()
{
	bHasGoal = false;
}

bool AYardWatchmanCharacter::HasArrivedAtSpot() const
{
	return bHasGoal
		&& FVector::Dist2D(GetActorLocation(), GoalSpot) <= StandOffUu;
}

void AYardWatchmanCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// ---------------------------------------------------------------------------
	// NOTHING DECIDES ANYTHING HERE. This is the whole of the missing work: what
	// this watchman should be doing, and where it should therefore be walking, is
	// the task. See the task prompt.
	// ---------------------------------------------------------------------------

	// The feet. While a goal is set, walk toward it in the plane and stop inside the
	// stand-off. Height is the floor's business, not ours.
	if (!bHasGoal)
	{
		return;
	}
	const FVector Here = GetActorLocation();
	const FVector Flat(GoalSpot.X - Here.X, GoalSpot.Y - Here.Y, 0.0);
	if (Flat.Size2D() > StandOffUu)
	{
		AddMovementInput(Flat.GetSafeNormal2D(), 1.0f);
	}
}
