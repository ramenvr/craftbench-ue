// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AFireAnimationFunctionalTest implementation. PIE-native (see header). The
// base (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns hero resolution, the reflection fire
// seam, and the four montage-state assertions. All FAIL message text is
// ASCII-only (the cp1252 log read-back rule).

#include "FireAnimationFunctionalTest.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName FireHeroTag(TEXT("FireHero"));
	static const FName FireStartName(TEXT("DoFireStart"));

	// cp2's frozen gate: minimum montage-position advance between cp1 (t=0.8)
	// and cp2 (t=1.4). A playing montage at rate 1.0 advances 0.6s across that
	// gap (spike-proven: position tracks fixed dt exactly); 0.25 leaves a wide
	// margin for blend-in/segment bookkeeping while still failing a paused
	// montage (which advances 0.0).
	constexpr float KMinPositionAdvance = 0.25f;
}

AFireAnimationFunctionalTest::AFireAnimationFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

UFunction* AFireAnimationFunctionalTest::ResolveParameterlessSeam(const FName FunctionName) const
{
	if (!Hero.IsValid())
	{
		return nullptr;
	}
	UFunction* Function = Hero->FindFunction(FunctionName);
	if (Function == nullptr)
	{
		return nullptr;
	}
	// A return value is tolerated (the prompt promises "no parameters", which
	// developers read as the argument list); any real input/output parameter
	// makes the seam uncallable-as-specified.
	for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
	{
		if (!(It->PropertyFlags & CPF_ReturnParm))
		{
			return nullptr;
		}
	}
	return Function;
}

void AFireAnimationFunctionalTest::InvokeSeam(UFunction* Function)
{
	if (!Hero.IsValid() || Function == nullptr)
	{
		return;
	}
	if (Function->ParmsSize > 0)
	{
		// Tolerated return value: give ProcessEvent an initialized buffer.
		TArray<uint8> Buffer;
		Buffer.SetNumZeroed(Function->ParmsSize);
		for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->InitializeValue_InContainer(Buffer.GetData());
		}
		Hero->ProcessEvent(Function, Buffer.GetData());
		for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->DestroyValue_InContainer(Buffer.GetData());
		}
	}
	else
	{
		Hero->ProcessEvent(Function, nullptr);
	}
}

UAnimInstance* AFireAnimationFunctionalTest::ResolveAnimInstance(int32 CheckpointIndex)
{
	USkeletalMeshComponent* Mesh = Hero.IsValid() ? Hero->GetMesh() : nullptr;
	UAnimInstance* Anim = Mesh ? Mesh->GetAnimInstance() : nullptr;
	if (Anim == nullptr)
	{
		// The scaffold ships an animated body (mesh + anim blueprint wired in
		// the constructor); its absence at runtime is an agent-side change, so
		// this is a graded FAIL, not a harness error.
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the character's body has no animation instance to play on."), CheckpointIndex));
	}
	return Anim;
}

bool AFireAnimationFunctionalTest::GuardHero(int32 CheckpointIndex)
{
	if (!Hero.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the player character is no longer valid."), CheckpointIndex));
		return false;
	}
	return true;
}

void AFireAnimationFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class: the game mode spawned the character with
	// the ctor-stamped tag; agents may subclass/rename (the tag inherits).
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FireHeroTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'FireHero' (the playable character) in the running level; found %d."), Found.Num()));
		return;
	}
	ACharacter* Character = Cast<ACharacter>(Found[0]);
	if (Character == nullptr || Character->GetMesh() == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The actor tagged 'FireHero' is not a character-type pawn with a body mesh."));
		return;
	}
	Hero = Character;

	// The FAIL-on-empty gate: the fire seam must exist by reflection. The
	// untouched scaffold compiles (L1 green) but has no such function.
	FireStartFn = ResolveParameterlessSeam(FireStartName);
	if (FireStartFn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No parameterless reflected function named 'DoFireStart' on the player character (fire seam missing)."));
		return;
	}

	// Timeline (see header): silence check + trigger at 0.5; started by 0.8;
	// advancing (or naturally ended) by 1.4; over by 6.0.
	SetCheckpointSchedule({ 0.5, 0.8, 1.4, 6.0 });
}

void AFireAnimationFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!GuardHero(CheckpointIndex))
	{
		return;
	}
	UAnimInstance* Anim = ResolveAnimInstance(CheckpointIndex);
	if (Anim == nullptr)
	{
		return;  // ResolveAnimInstance already raised the named FAIL
	}
	UAnimMontage* Active = Anim->GetCurrentActiveMontage();
	const float Position = Active ? Anim->Montage_GetPosition(Active) : -1.f;
	UE_LOG(LogTemp, Display, TEXT("[t2-fireanim calib] cp%d t=%.2f active=%s pos=%.3f"),
		CheckpointIndex, TimeSeconds, *GetNameSafe(Active), Position);

	switch (CheckpointIndex)
	{
	case 0:  // t=0.5 — settled; nothing may be playing before any request.
		if (Active != nullptr)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the character's body to be idle until a fire request; observed an animation was already playing before any fire request (%s)."), *GetNameSafe(Active)));
			return;
		}
		InvokeSeam(FireStartFn);
		break;

	case 1:  // t=0.8 — 0.3s after the request: a firing animation must be on.
		if (Active == nullptr)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				TEXT("Expected a firing animation shortly after the fire request; observed no firing animation started."));
			return;
		}
		FireMontage = Active;
		PositionAtCp1 = Position;
		break;

	case 2:  // t=1.4 — the same montage, if still on, must be moving forward.
		if (Active != nullptr && FireMontage.IsValid() && Active == FireMontage.Get()
			&& Position < PositionAtCp1 + KMinPositionAdvance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the firing animation to play forward; observed it is frozen, not playing (position %.3f then, %.3f now)."), PositionAtCp1, Position));
			return;
		}
		// A montage that already ran its natural length and ended is fine —
		// short clips legitimately finish inside this window.
		break;

	case 3:  // t=6.0 — well past any natural one-shot clip length.
		if (Active != nullptr)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the firing animation to run once for its natural length and end; observed it never ended (still playing %s at t=%.1f)."), *GetNameSafe(Active), TimeSeconds));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		break;

	default:
		break;
	}
}
