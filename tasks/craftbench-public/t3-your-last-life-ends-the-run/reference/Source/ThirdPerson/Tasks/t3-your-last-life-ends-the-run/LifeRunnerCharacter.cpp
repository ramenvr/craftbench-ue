// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t3-your-last-life-ends-the-run.

#include "LifeRunnerCharacter.h"

#include "Animation/AnimInstance.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "CrumbleGroundActor.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "FinishDiscActor.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputAction.h"
#include "Kismet/GameplayStatics.h"
#include "LifeMarkerActor.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** How bright a burning lamp is, and how far its glow carries. */
	constexpr float kLampLitIntensity = 2600.0f;
	constexpr float kLampAttenuationUu = 260.0f;

	/** How long a runner with lives left spends off its feet before it is standing on
	 *  its own marker again. The level allows up to a second; this leaves room. */
	constexpr double kComeBackAfterSeconds = 0.30;

	/** The three words a runner ever shows. */
	const TCHAR* kWordRunning = TEXT("RUNNING");
	const TCHAR* kWordWon = TEXT("WON");
	const TCHAR* kWordLost = TEXT("LOST");

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

void ALifeRunnerCharacter::BeginPlay()
{
	Super::BeginPlay();

	// THE MARKER UNDER THIS RUNNER'S FEET WHEN THE RUN OPENS IS ITS OWN, for the rest
	// of the run. Resolved once, on purpose: re-deciding "which marker is nearest"
	// later would hand a runner standing in the crumbling ground somebody else's disc.
	UWorld* const World = GetWorld();
	if (World != nullptr)
	{
		TArray<AActor*> Markers;
		UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LifeMarker")), Markers);
		double Nearest = TNumericLimits<double>::Max();
		for (AActor* const Candidate : Markers)
		{
			ALifeMarkerActor* const Marker = Cast<ALifeMarkerActor>(Candidate);
			if (Marker == nullptr)
			{
				continue;
			}
			const double Flat = FVector::Dist2D(Marker->GetActorLocation(), GetActorLocation());
			if (Flat < Nearest)
			{
				Nearest = Flat;
				OwnMarker = Marker;
			}
		}
	}

	State = ERunState::Running;
	Deaths = 0;
	bReturnPending = false;
	// The edge is what costs a life, so the first frame records where the runner
	// already is rather than counting it as an arrival.
	bWasOnCrumblingGround = IsOnCrumblingGround();

	// Right from the first moment of play, not from the first death.
	ShowState();
}

void ALifeRunnerCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	// A RUN THAT HAS ENDED STAYS ENDED. Nothing below this line runs again: the ground
	// costs nothing and moves nobody, the finish does nothing, and a re-painted marker
	// changes nothing, because the row and the word are simply re-stated as they were.
	if (State != ERunState::Running)
	{
		ShowState();
		return;
	}

	const double Now = World->GetTimeSeconds();

	if (bReturnPending && Now >= ReturnAtSeconds)
	{
		bReturnPending = false;
		if (OwnMarker.IsValid())
		{
			const float Clearance = GetCapsuleComponent() != nullptr
				? GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 6.0f
				: 96.0f;
			const FVector Home = OwnMarker->GetActorLocation() + FVector(0.0, 0.0, Clearance);
			SetActorLocation(Home, false, nullptr, ETeleportType::TeleportPhysics);
			if (UCharacterMovementComponent* const Movement = GetCharacterMovement())
			{
				Movement->StopMovementImmediately();
			}
		}
		// And then let go: nothing here ever pulls this runner back again.
	}

	// A death is a MOMENT, not a length of time: only the crossing costs a life, so
	// standing in the patch drains nothing and stepping off and back on costs another.
	const bool bOnGroundNow = IsOnCrumblingGround();
	if (bOnGroundNow && !bWasOnCrumblingGround)
	{
		ClaimedByTheGround();
	}
	bWasOnCrumblingGround = bOnGroundNow;

	// THE FINISH IS A CONDITION, NOT AN EVENT -- and this is the one place the two
	// triggers must NOT be written the same way. Nothing announces a re-paint, so
	// whether this runner is standing on the disc with at least what the disc asks for
	// is asked EVERY frame: it can become true with nobody moving at all, because the
	// disc's own number came down or this runner's board went up. Only a run that is
	// still going can be won, and the death above may just have ended this one.
	if (State == ERunState::Running)
	{
		const AFinishDiscActor* const Underfoot = FinishUnderfoot();
		if (Underfoot != nullptr && RemainingLives() >= Underfoot->DemandedLives)
		{
			ReachedTheFinish();
		}
	}

	ShowState();
}

int32 ALifeRunnerCharacter::RemainingLives() const
{
	if (!OwnMarker.IsValid())
	{
		return 0;
	}
	// READ AT THE POINT OF USE. The board is re-painted while runs are going, and the
	// number it shows at the moment it is needed is the number.
	return FMath::Max(0, OwnMarker->PaintedLives - Deaths);
}

bool ALifeRunnerCharacter::IsOnCrumblingGround() const
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	TArray<AActor*> Grounds;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrumbleGround")), Grounds);
	const FVector Here = GetActorLocation();
	for (AActor* const Candidate : Grounds)
	{
		const ACrumbleGroundActor* const Ground = Cast<ACrumbleGroundActor>(Candidate);
		if (Ground == nullptr || Ground->PatchVolume == nullptr)
		{
			continue;
		}
		// The patch is a box that may be placed at any angle, so the question is asked
		// in the box's own frame. InverseTransformPosition takes the scale out, which
		// is why the UNSCALED extent is the right one to compare against.
		const FVector Local =
			Ground->PatchVolume->GetComponentTransform().InverseTransformPosition(Here);
		const FVector Extent = Ground->PatchVolume->GetUnscaledBoxExtent();
		if (FMath::Abs(Local.X) <= Extent.X
			&& FMath::Abs(Local.Y) <= Extent.Y
			&& FMath::Abs(Local.Z) <= Extent.Z)
		{
			return true;
		}
	}
	return false;
}

const AFinishDiscActor* ALifeRunnerCharacter::FinishUnderfoot() const
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return nullptr;
	}
	TArray<AActor*> Discs;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("FinishDisc")), Discs);
	const FVector Here = GetActorLocation();
	for (AActor* const Candidate : Discs)
	{
		const AFinishDiscActor* const Disc = Cast<AFinishDiscActor>(Candidate);
		if (Disc == nullptr)
		{
			continue;
		}
		// Flat along the floor: how tall a runner is has nothing to do with whether it
		// is standing on the disc, and the disc's own painted width is the reach.
		if (FVector::Dist2D(Disc->GetActorLocation(), Here) <= double(Disc->DiscRadiusUu))
		{
			return Disc;
		}
	}
	return nullptr;
}

void ALifeRunnerCharacter::ClaimedByTheGround()
{
	++Deaths;

	// THE OFF-BY-ONE THIS TASK IS BUILT AROUND. The life is spent on the DEATH, and
	// the question "was that the last one?" is asked immediately, of the board as it
	// reads NOW -- not on the way back, and not against a countdown latched at the
	// start. If nothing is left, nobody comes back for this runner.
	if (RemainingLives() <= 0)
	{
		State = ERunState::Lost;
		FrozenLitCount = 0;
		bReturnPending = false;
		return;
	}

	bReturnPending = true;
	ReturnAtSeconds = GetWorld() != nullptr
		? GetWorld()->GetTimeSeconds() + kComeBackAfterSeconds
		: 0.0;
}

void ALifeRunnerCharacter::ReachedTheFinish()
{
	// WINNING SPENDS NOTHING: the row is frozen exactly where it stood the moment the
	// disc opened -- which may be long after this runner walked on -- so a re-paint
	// afterwards cannot move it either.
	FrozenLitCount = RemainingLives();
	State = ERunState::Won;
	bReturnPending = false;
}

void ALifeRunnerCharacter::ShowState()
{
	switch (State)
	{
	case ERunState::Won:
		SetLitCount(FrozenLitCount);
		SetStateWord(kWordWon);
		break;
	case ERunState::Lost:
		SetLitCount(0);
		SetStateWord(kWordLost);
		break;
	case ERunState::Running:
	default:
		SetLitCount(RemainingLives());
		SetStateWord(kWordRunning);
		break;
	}
}
