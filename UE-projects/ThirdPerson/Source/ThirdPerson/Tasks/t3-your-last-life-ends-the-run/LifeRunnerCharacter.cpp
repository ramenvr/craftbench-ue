// Copyright CraftBench. All Rights Reserved.

#include "LifeRunnerCharacter.h"

#include "Animation/AnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "InputAction.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** How bright a burning lamp is, and how far its glow carries. */
	constexpr float kLampLitIntensity = 2600.0f;
	constexpr float kLampAttenuationUu = 260.0f;

	/** The row sits above the head, spread across the shoulders. */
	constexpr float kRowHeightUu = 176.0f;
	constexpr float kLampSpacingUu = 30.0f;
	constexpr float kBulbScale = 0.18f;

	/** What the word reads before anything decides what it ought to read. */
	const TCHAR* kPlaceholderWord = TEXT("-");

	UInputAction* FindInputAction(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<UInputAction> Finder(Path);
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}
}

ALifeRunnerCharacter::ALifeRunnerCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	Tags.Add(FName("LifeRunner"));

	// A runner that is PLACED in the level takes a controller of its own the moment
	// the level opens, so it stands on its marker under its own weight and can be
	// walked about. A runner that is SPAWNED (the one a person drives) is left alone
	// here, because the level's own controller takes it instead.
	AutoPossessAI = EAutoPossessAI::PlacedInWorld;

	// AThirdPersonCharacter declares these four and assigns none of them: the template
	// fills them in on its Blueprint character's class defaults, so ANY native
	// subclass inherits four null pointers and binds no input at all. Wired here for
	// the same reason as the body below -- pressing Play has to give a person
	// something they can actually walk around with.
	MoveAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Move"));
	LookAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Look"));
	MouseLookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_MouseLook"));
	JumpAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Jump"));

	// The project's standard body and its animation blueprint. The stock template
	// assigns the mesh in its Blueprint, NOT in C++, so a plain C++ subclass is
	// invisible unless the constructor loads it.
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

	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> LitLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DarkLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	BulbLitLook  = LitLook.Succeeded()  ? LitLook.Object  : nullptr;
	BulbDarkLook = DarkLook.Succeeded() ? DarkLook.Object : nullptr;

	// Six lamps in a row over the head, all of them dark. The row is attached to the
	// capsule, which is not scaled, so each bulb is the size this says it is.
	LampBulbs.Reserve(LampCount);
	LampGlows.Reserve(LampCount);
	const float RowLeftUu = -0.5f * kLampSpacingUu * float(LampCount - 1);
	for (int32 Index = 0; Index < LampCount; ++Index)
	{
		const FVector At(0.0f, RowLeftUu + kLampSpacingUu * float(Index), kRowHeightUu);

		UStaticMeshComponent* const Bulb = CreateDefaultSubobject<UStaticMeshComponent>(
			*FString::Printf(TEXT("Bulb%d"), Index));
		Bulb->SetupAttachment(GetCapsuleComponent());
		if (SphereMesh.Succeeded())
		{
			Bulb->SetStaticMesh(SphereMesh.Object);
		}
		Bulb->SetRelativeLocation(At);
		Bulb->SetRelativeScale3D(FVector(kBulbScale));
		// Ornament, never an obstacle: a bulb that could block would push a runner
		// the level never meant to move.
		Bulb->SetCollisionProfileName(TEXT("NoCollision"));
		Bulb->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		if (BulbDarkLook != nullptr)
		{
			Bulb->SetMaterial(0, BulbDarkLook);
		}
		LampBulbs.Add(Bulb);

		UPointLightComponent* const Glow = CreateDefaultSubobject<UPointLightComponent>(
			*FString::Printf(TEXT("Lamp%d"), Index));
		Glow->SetupAttachment(GetCapsuleComponent());
		Glow->SetRelativeLocation(At);
		Glow->SetLightColor(FLinearColor(1.0f, 0.86f, 0.36f));
		Glow->SetIntensity(0.0f);
		Glow->SetAttenuationRadius(kLampAttenuationUu);
		Glow->SetCastShadows(false);
		Glow->SetMobility(EComponentMobility::Movable);
		LampGlows.Add(Glow);
	}

	// The floating word. It starts on a placeholder on purpose: what it ought to read
	// is something to be worked out, not something to be left where it was authored.
	WordText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("WordText"));
	WordText->SetupAttachment(GetCapsuleComponent());
	WordText->SetRelativeLocation(FVector(0.0f, 0.0f, kRowHeightUu + 46.0f));
	WordText->SetHorizontalAlignment(EHTA_Center);
	WordText->SetWorldSize(46.0f);
	WordText->SetTextRenderColor(FColor(255, 232, 150));
	WordText->SetText(FText::FromString(kPlaceholderWord));
}

void ALifeRunnerCharacter::SetLitCount(int32 Count)
{
	const int32 Lit = FMath::Clamp(Count, 0, LampCount);
	for (int32 Index = 0; Index < LampBulbs.Num(); ++Index)
	{
		const bool bOn = Index < Lit;
		// Each lamp is only touched when it is actually changing, so this is safe to
		// call every frame.
		if (LampGlows.IsValidIndex(Index) && LampGlows[Index] != nullptr
			&& (LampGlows[Index]->Intensity > 0.0f) != bOn)
		{
			LampGlows[Index]->SetIntensity(bOn ? kLampLitIntensity : 0.0f);
		}
		UMaterialInterface* const Look = bOn ? BulbLitLook : BulbDarkLook;
		if (LampBulbs[Index] != nullptr && Look != nullptr
			&& LampBulbs[Index]->GetMaterial(0) != Look)
		{
			LampBulbs[Index]->SetMaterial(0, Look);
		}
	}
}

int32 ALifeRunnerCharacter::GetLitCount() const
{
	// Counted off the lamps themselves, so it can only ever say what is burning.
	int32 Lit = 0;
	for (const UPointLightComponent* const Glow : LampGlows)
	{
		if (Glow != nullptr && Glow->Intensity > 0.0f)
		{
			++Lit;
		}
	}
	return Lit;
}

void ALifeRunnerCharacter::SetStateWord(const FString& Word)
{
	// Only written when it is actually changing, so this is safe to call every frame.
	if (WordText != nullptr && !WordText->Text.ToString().Equals(Word, ESearchCase::CaseSensitive))
	{
		WordText->SetText(FText::FromString(Word));
	}
}

FString ALifeRunnerCharacter::GetStateWord() const
{
	return WordText != nullptr ? WordText->Text.ToString() : FString();
}
