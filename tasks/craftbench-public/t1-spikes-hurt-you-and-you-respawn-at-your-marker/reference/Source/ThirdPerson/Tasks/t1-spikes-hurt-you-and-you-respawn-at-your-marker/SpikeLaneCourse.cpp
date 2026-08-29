// Copyright CraftBench. All Rights Reserved.

#include "SpikeLaneCourse.h"

#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "LanePadActor.h"

namespace
{
	constexpr double kComeBackAfterS = 0.35;  // the level allows up to 1 second
	constexpr float kFullHealth = 100.0f;
}

ASpikeLaneCourse::ASpikeLaneCourse()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("SpikeLane"));
}

void ASpikeLaneCourse::BeginPlay()
{
	Super::BeginPlay();

	TArray<AActor*> Marks;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("StartMark")), Marks);
	if (Marks.Num() > 0 && Marks[0] != nullptr)
	{
		StartMarkAt = Marks[0]->GetActorLocation();
	}
	RefreshPadMarks();
}

void ASpikeLaneCourse::NotifyPadEntered(ALanePadActor* Pad)
{
	if (Pad == nullptr)
	{
		return;
	}
	// Progress never rolls backwards: an earlier pad leaves a later one current, and
	// re-entering the current pad leaves it current.
	if (Pad->PadOrder > CurrentPadOrder)
	{
		CurrentPadOrder = Pad->PadOrder;
		RefreshPadMarks();
	}
}

void ASpikeLaneCourse::RefreshPadMarks()
{
	// Exactly one pad is marked at a time, and it is the one CurrentPadOrder names.
	TArray<AActor*> Pads;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("LanePad")), Pads);
	for (AActor* A : Pads)
	{
		if (ALanePadActor* const Pad = Cast<ALanePadActor>(A))
		{
			Pad->SetMarkedCurrent(Pad->PadOrder == CurrentPadOrder);
		}
	}
}

FVector ASpikeLaneCourse::RespawnPoint() const
{
	// Derived from the SAME value the course exposes -- there is no second, separately
	// updated copy of "where you come back to" that could disagree with it.
	if (CurrentPadOrder >= 1)
	{
		TArray<AActor*> Pads;
		UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("LanePad")), Pads);
		for (AActor* A : Pads)
		{
			const ALanePadActor* const Pad = Cast<ALanePadActor>(A);
			if (Pad != nullptr && Pad->PadOrder == CurrentPadOrder)
			{
				return Pad->GetActorLocation();
			}
		}
	}
	return StartMarkAt;
}

void ASpikeLaneCourse::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();

	if (Dying.IsValid() && Now >= ReviveAt)
	{
		AActor* const Character = Dying.Get();
		const FVector Back = RespawnPoint();
		// Stand it ON the pad, not in it, and let go: nothing pulls it back after.
		Character->SetActorLocation(Back + FVector(0.0, 0.0, 96.0), false, nullptr,
			ETeleportType::TeleportPhysics);
		if (const FFloatProperty* P =
				FindFProperty<FFloatProperty>(Character->GetClass(), TEXT("Health")))
		{
			P->SetPropertyValue_InContainer(Character, kFullHealth);
		}
		Dying.Reset();
		ReviveAt = -1.0;
		return;
	}

	if (Dying.IsValid())
	{
		return;
	}
	// Anybody at zero health is out, and comes back on the current pad.
	TArray<AActor*> Characters;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("LaneCharacter")), Characters);
	for (AActor* A : Characters)
	{
		const FFloatProperty* const P =
			A ? FindFProperty<FFloatProperty>(A->GetClass(), TEXT("Health")) : nullptr;
		if (P != nullptr && P->GetPropertyValue_InContainer(A) <= 0.0f)
		{
			Dying = A;
			ReviveAt = Now + kComeBackAfterS;
			break;
		}
	}
}
