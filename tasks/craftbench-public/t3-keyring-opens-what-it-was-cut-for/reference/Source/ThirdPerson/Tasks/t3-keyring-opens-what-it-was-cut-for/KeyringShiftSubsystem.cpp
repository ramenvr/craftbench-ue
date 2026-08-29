// Copyright CraftBench. All Rights Reserved.

#include "KeyringShiftSubsystem.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "KeyringYardProps.h"
#include "Kismet/GameplayStatics.h"
#include "Stats/Stats.h"

void UKeyringShiftSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
}

void UKeyringShiftSubsystem::Deinitialize()
{
	Super::Deinitialize();
}

bool UKeyringShiftSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	// Only where there is something to walk around. The editor world has the props in
	// it but nobody driving them.
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UKeyringShiftSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UKeyringShiftSubsystem, STATGROUP_Tickables);
}

void UKeyringShiftSubsystem::FindTheYard()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	for (TActorIterator<AKeyStandActor> It(World); It; ++It)
	{
		Stands.Add(*It);
	}
	for (TActorIterator<ADoorBayActor> It(World); It; ++It)
	{
		Bays.Add(*It);
	}
	for (TActorIterator<ARingBoardActor> It(World); It; ++It)
	{
		BoardActor = *It;
		break;
	}
	bFoundTheYard = Stands.Num() > 0 && Bays.Num() > 0;
}

FString UKeyringShiftSubsystem::RingLine() const
{
	FString Line;
	for (int32 i = 0; i < Ring.Num(); ++i)
	{
		if (i > 0)
		{
			Line += TEXT(", ");
		}
		Line += Ring[i].ToString();
	}
	return Line.IsEmpty() ? FString(TEXT("--")) : Line;
}

void UKeyringShiftSubsystem::TakeKeysWithin(const FVector& BodyAt)
{
	for (AKeyStandActor* const S : Stands)
	{
		if (S == nullptr || S->IsKeyTaken())
		{
			// ONCE ONLY. The stand's own state is the guard, so standing there longer
			// cannot put the same key on the ring twice -- and the board, which neither
			// sorts nor de-duplicates, would say so loudly if it could.
			continue;
		}
		// Measured ON THE GROUND, against THIS stand's own mat. The character's origin
		// sits a capsule half-height above the floor, so a flat distance is the honest
		// reading of "standing inside the mat".
		if (FVector::Dist2D(BodyAt, S->GetActorLocation()) <= S->MatRadiusUu)
		{
			S->SetKeyTaken(true);
			Ring.Add(S->KeyCategory);
		}
	}
}

void UKeyringShiftSubsystem::OpenBaysWithin(const FVector& BodyAt)
{
	for (ADoorBayActor* const B : Bays)
	{
		if (B == nullptr || B->IsOpen())
		{
			// OPEN IS FOREVER. An open bay is never reconsidered, so walking off its
			// mat, the ring changing, and the whole shift changing all leave it open.
			continue;
		}
		if (FVector::Dist2D(BodyAt, B->GetActorLocation()) > B->MatRadiusUu)
		{
			continue;
		}
		// EVERY category it is painted with, not any of them.
		if (!Ring.Contains(B->WantsCategory))
		{
			continue;
		}
		if (!B->AlsoWantsCategory.IsNone() && !Ring.Contains(B->AlsoWantsCategory))
		{
			continue;
		}
		// Nothing is taken off the ring: the same key opens the next bay too.
		B->SetOpen(true);
	}
}

void UKeyringShiftSubsystem::RefreshBoard()
{
	if (BoardActor == nullptr)
	{
		return;
	}
	// Driven from the RING, never from the key that just went on it, and compared
	// against what the board is actually showing. That second half is what survives the
	// yard blanking the board at the shift change: nothing announces the wipe, so the
	// only way to notice it is to keep checking that the board still agrees.
	if (BoardActor->CurrentReadout() != RingLine())
	{
		BoardActor->ShowRing(Ring);
	}
}

void UKeyringShiftSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	UWorld* const World = GetWorld();
	if (World == nullptr || !World->HasBegunPlay())
	{
		return;
	}
	if (!bFoundTheYard)
	{
		FindTheYard();
		if (!bFoundTheYard)
		{
			return;
		}
	}

	// THE BODY, RE-RESOLVED. Never held from one frame to the next, so the shift change
	// costs nothing: the controller and the ring both outlive the pawn, and this is the
	// only line that has to notice a new one.
	const ACharacter* const Body = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (Body != nullptr)
	{
		const FVector BodyAt = Body->GetActorLocation();
		TakeKeysWithin(BodyAt);
		OpenBaysWithin(BodyAt);
	}
	// Even with nobody on the controller for a frame, the board still has to say what
	// the shift is carrying.
	RefreshBoard();
}
