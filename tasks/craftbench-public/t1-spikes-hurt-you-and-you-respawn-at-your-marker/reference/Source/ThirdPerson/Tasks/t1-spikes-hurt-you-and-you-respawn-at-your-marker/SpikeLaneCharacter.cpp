// Copyright CraftBench. All Rights Reserved.

#include "SpikeLaneCharacter.h"

#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/SkeletalMesh.h"
#include "InputAction.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	UInputAction* FindInputAction(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<UInputAction> Finder(Path);
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}
}

ASpikeLaneCharacter::ASpikeLaneCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	Tags.Add(FName("LaneCharacter"));

	// AThirdPersonCharacter declares these four as EditAnywhere and assigns none of
	// them: the template fills them in on BP_ThirdPersonCharacter's class defaults,
	// so ANY native subclass inherits four null pointers and binds no input at all.
	// Wired here for the same reason as the body below -- pressing Play has to give a
	// person something they can actually walk around with.
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

	// The floating number. Authored as 100 to match the starting health; keeping it
	// truthful once health changes is part of the work.
	HealthReadout = CreateDefaultSubobject<UTextRenderComponent>(TEXT("HealthReadout"));
	HealthReadout->SetupAttachment(GetRootComponent());
	HealthReadout->SetRelativeLocation(FVector(0.0f, 0.0f, 130.0f));
	HealthReadout->SetHorizontalAlignment(EHTA_Center);
	HealthReadout->SetWorldSize(52.0f);
	HealthReadout->SetTextRenderColor(FColor(255, 226, 120));
	HealthReadout->SetText(FText::FromString(TEXT("100")));
}

void ASpikeLaneCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The floating number follows Health every frame, so it can never lag by more
	// than the one frame the level allows.
	if (HealthReadout != nullptr)
	{
		HealthReadout->SetText(FText::FromString(
			FString::Printf(TEXT("%d"), FMath::RoundToInt(Health))));
	}
}
