// Copyright CraftBench. All Rights Reserved.

#include "CraftBenchCharacter.h"

#include "AbilitySystemComponent.h"
#include "Abilities/GameplayAbility.h"
#include "CraftBenchAttributeSet.h"

#include "EnhancedInputComponent.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** Resolve a stock input action, or null. A wrong path must NOT be silent: a
	 *  null action binds nothing and the pawn is undrivable again, which is the
	 *  whole defect Option C exists to remove — so it is logged loudly. */
	UInputAction* FindStockInputAction(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<UInputAction> Finder(Path);
		if (!Finder.Succeeded())
		{
			UE_LOG(LogTemp, Error,
				TEXT("CraftBenchCharacter: input action not found at %s — the pawn "
					 "will not be drivable by hand"), Path);
			return nullptr;
		}
		return Finder.Object;
	}
}

ACraftBenchCharacter::ACraftBenchCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	AbilitySystemComponent = CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("AbilitySystemComponent"));
	AbilitySystemComponent->SetIsReplicated(true);
	AbilitySystemComponent->SetReplicationMode(EGameplayEffectReplicationMode::Minimal);

	// 2026-08-05 stage-1 seam: may return NULL — ACraftBenchBareCharacter
	// suppresses this subobject by name (DoNotCreateDefaultSubobject) so
	// health-first tasks start with an ASC and NO health resource; the agent
	// builds it (stage 1). UCraftBenchAttributeSet stays the contract class.
	// MUST be the Optional variant: UE ignores DoNotCreateDefaultSubobject for
	// a required subobject ("Ignored DoNotCreateDefaultSubobject for
	// AttributeSet as it's marked as required" — live-caught 2026-08-05, it
	// silently un-bares the bare lineage and the stage-1 gate reads the wrong,
	// zero-initialized set).
	AttributeSet = CreateOptionalDefaultSubobject<UCraftBenchAttributeSet>(TEXT("AttributeSet"));

	// Identity tag. Agents may subclass or rename this pawn.
	Tags.Add(FName("CraftBenchPawn"));

	// Human-drivable by default (Option C). Same stock assets the template's own
	// character uses, so a reviewer's controls are identical in a task map and in
	// the ThirdPerson template. Verified git-tracked before wiring: a wrong path
	// makes FObjectFinder return null silently, which would ship a "fix" that does
	// not fix — the exact trap hit by the 2026-08-17 play-lane repair.
	MoveAction      = FindStockInputAction(TEXT("/Game/Input/Actions/IA_Move"));
	LookAction      = FindStockInputAction(TEXT("/Game/Input/Actions/IA_Look"));
	MouseLookAction = FindStockInputAction(TEXT("/Game/Input/Actions/IA_MouseLook"));
	JumpAction      = FindStockInputAction(TEXT("/Game/Input/Actions/IA_Jump"));
}

void ACraftBenchCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	// Reached only when a LOCAL controller possesses this pawn — PawnClientRestart
	// is what calls this, and it is skipped entirely for an AAIController. That is
	// precisely why SpawnAndPossessPawn now possesses the PIE player controller
	// instead of calling SpawnDefaultController().
	UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (EIC == nullptr)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("CraftBenchCharacter: input component is not a "
				 "UEnhancedInputComponent; this pawn will not be drivable"));
		return;
	}

	if (JumpAction != nullptr)
	{
		EIC->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
		EIC->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
	}
	if (MoveAction != nullptr)
	{
		EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &ACraftBenchCharacter::Move);
	}
	if (MouseLookAction != nullptr)
	{
		EIC->BindAction(MouseLookAction, ETriggerEvent::Triggered, this, &ACraftBenchCharacter::Look);
	}
	if (LookAction != nullptr)
	{
		EIC->BindAction(LookAction, ETriggerEvent::Triggered, this, &ACraftBenchCharacter::Look);
	}
}

void ACraftBenchCharacter::Move(const FInputActionValue& Value)
{
	const FVector2D V = Value.Get<FVector2D>();
	if (Controller == nullptr)
	{
		return;
	}
	// Camera-relative, matching the template's feel rather than world axes.
	const FRotator YawOnly(0.0, Controller->GetControlRotation().Yaw, 0.0);
	AddMovementInput(FRotationMatrix(YawOnly).GetUnitAxis(EAxis::Y), V.X);
	AddMovementInput(FRotationMatrix(YawOnly).GetUnitAxis(EAxis::X), V.Y);
}

void ACraftBenchCharacter::Look(const FInputActionValue& Value)
{
	const FVector2D V = Value.Get<FVector2D>();
	AddControllerYawInput(V.X);
	AddControllerPitchInput(V.Y);
}

UAbilitySystemComponent* ACraftBenchCharacter::GetAbilitySystemComponent() const
{
	return AbilitySystemComponent;
}

void ACraftBenchCharacter::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	InitAbilityActorInfo();
	GrantDefaultAbilities();
}

void ACraftBenchCharacter::BeginPlay()
{
	Super::BeginPlay();
	InitAbilityActorInfo();
	GrantDefaultAbilities();
}

void ACraftBenchCharacter::InitAbilityActorInfo()
{
	if (AbilitySystemComponent != nullptr)
	{
		// Pawn-owned ASC: owner and avatar are both this pawn.
		AbilitySystemComponent->InitAbilityActorInfo(this, this);
	}
}

void ACraftBenchCharacter::GrantDefaultAbilities()
{
	if (bAbilitiesGranted || AbilitySystemComponent == nullptr)
	{
		return;
	}
	// Only the authority grants abilities (a pawn in a standalone world has
	// authority).
	if (!HasAuthority())
	{
		return;
	}

	for (const TSubclassOf<UGameplayAbility>& AbilityClass : GrantedAbilities)
	{
		if (AbilityClass != nullptr)
		{
			AbilitySystemComponent->GiveAbility(FGameplayAbilitySpec(AbilityClass, 1, INDEX_NONE, this));
		}
	}
	bAbilitiesGranted = true;
}
