// Copyright CraftBench. All Rights Reserved.

#include "MudHeroCharacter.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputAction.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	UInputAction* FindInputAction(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<UInputAction> Finder(Path);
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}
}

AMudHeroCharacter::AMudHeroCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	Tags.Add(FName("MudHero"));

	// AThirdPersonCharacter declares these four as EditAnywhere and assigns none of
	// them: the template fills them in on BP_ThirdPersonCharacter's class defaults,
	// so ANY native subclass inherits four null pointers and binds no input at all.
	MoveAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Move"));
	LookAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Look"));
	MouseLookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_MouseLook"));
	JumpAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Jump"));

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
	static ConstructorHelpers::FClassFinder<UAnimInstance> AnimFinder(
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
	if (AnimFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetAnimInstanceClass(AnimFinder.Class);
	}

	// The supplied wade clip. The scaffold looked for it under the `-cpp` folder,
	// which has never existed, so the inherited value arrives null and the guard in
	// EnterMud below silently never plays anything — the pose keeps being driven by
	// the ordinary walk and the task reads as "the wade was not driving" rather than
	// as a missing asset. Resolving the REAL, un-suffixed path is part of the answer.
	static ConstructorHelpers::FObjectFinder<UAnimSequence> WadeFinder(
		TEXT("/Game/Tasks/t1-mud-wade/A_MudWade"));
	if (WadeFinder.Succeeded())
	{
		WadeMotion = WadeFinder.Object;
	}

	if (UCharacterMovementComponent* const Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = NormalTopSpeed;
	}
}

void AMudHeroCharacter::BeginPlay()
{
	Super::BeginPlay();

	// Remember what the figure ordinarily walks with, so leaving the mud puts back
	// exactly that rather than a guess.
	if (GetMesh() != nullptr)
	{
		OrdinaryWalkClass = GetMesh()->GetAnimClass();
	}
	if (UCharacterMovementComponent* const Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = NormalTopSpeed;
	}
}

bool AMudHeroCharacter::IsOnMud() const
{
	// Identity by TAG: the patch is "a single thing in the level carrying MudPatch",
	// and nothing here assumes what kind of actor it is.
	TArray<AActor*> Patches;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("MudPatch")), Patches);
	for (AActor* P : Patches)
	{
		if (P == nullptr)
		{
			continue;
		}
		FVector Origin, Extent;
		P->GetActorBounds(true, Origin, Extent);
		const FVector Here = GetActorLocation();
		if (FMath::Abs(Here.X - Origin.X) <= Extent.X
			&& FMath::Abs(Here.Y - Origin.Y) <= Extent.Y)
		{
			return true;
		}
	}
	return false;
}

void AMudHeroCharacter::EnterMud()
{
	bWading = true;
	if (UCharacterMovementComponent* const Move = GetCharacterMovement())
	{
		// 40% of the normal top speed, as the level asks.
		Move->MaxWalkSpeed = NormalTopSpeed * 0.4f;
	}
	// The wade genuinely drives the pose: the mesh plays the supplied clip itself
	// rather than the ordinary walk being slowed down.
	if (GetMesh() != nullptr && WadeMotion != nullptr)
	{
		GetMesh()->PlayAnimation(WadeMotion, true);
	}
}

void AMudHeroCharacter::LeaveMud()
{
	bWading = false;
	if (UCharacterMovementComponent* const Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = NormalTopSpeed;
	}
	if (GetMesh() != nullptr && OrdinaryWalkClass != nullptr)
	{
		GetMesh()->SetAnimInstanceClass(OrdinaryWalkClass);
	}
}

void AMudHeroCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Every frame, so both directions settle far inside the half second the level
	// allows, and so a second crossing behaves exactly like the first.
	const bool bOnMud = IsOnMud();
	if (bOnMud && !bWading)
	{
		EnterMud();
	}
	else if (!bOnMud && bWading)
	{
		LeaveMud();
	}
}
