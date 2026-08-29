// Copyright CraftBench. All Rights Reserved.

#include "YardMemorySubsystem.h"

#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Templates/UnrealTemplate.h"
#include "MemoryBoardActor.h"
#include "MemoryPadActor.h"
#include "MemoryPostActor.h"
#include "YardMemoryRecord.h"

namespace
{
	const TCHAR* const kSlotName = TEXT("YardMemory");
	constexpr int32 kUserIndex = 0;

	/** A little clearance so a runner set down on a pad is standing on the floor rather
	 *  than starting the frame inside it. */
	constexpr float kFootroom = 4.0f;
}

UYardMemoryRecord* UYardMemorySubsystem::ReadRecord() const
{
	// EVERY read goes to disk. Nothing on this object remembers the answer between
	// calls, which is what makes deleting the record actually forget the day.
	if (UGameplayStatics::DoesSaveGameExist(kSlotName, kUserIndex))
	{
		if (UYardMemoryRecord* const Loaded = Cast<UYardMemoryRecord>(
				UGameplayStatics::LoadGameFromSlot(kSlotName, kUserIndex)))
		{
			return Loaded;
		}
	}
	// Nothing written down -- a yard nobody has ever visited.
	return Cast<UYardMemoryRecord>(
		UGameplayStatics::CreateSaveGameObject(UYardMemoryRecord::StaticClass()));
}

void UYardMemorySubsystem::WriteRecord(UYardMemoryRecord* Record) const
{
	if (Record != nullptr)
	{
		UGameplayStatics::SaveGameToSlot(Record, kSlotName, kUserIndex);
	}
}

void UYardMemorySubsystem::RegisterPost(AMemoryPostActor* Post)
{
	if (Post == nullptr)
	{
		return;
	}
	Posts.AddUnique(Post);

	const UYardMemoryRecord* const Record = ReadRecord();
	if (Record == nullptr)
	{
		return;
	}
	// The number over a post is the yard's business and always the one this post
	// arrived carrying. Writing a remembered number back here would make the post lie
	// about what it is worth NOW, and the next person to take it would be paid the
	// wrong amount.
	Post->ShowWorth(Post->WorthNow);
	Post->ShowStanding(
		!Record->TakenPosts.Contains(MakeYardPostKey(Post->YardName, Post->PostId)));
}

void UYardMemorySubsystem::UnregisterPost(AMemoryPostActor* Post)
{
	Posts.Remove(Post);
}

void UYardMemorySubsystem::RegisterPad(AMemoryPadActor* Pad)
{
	if (Pad == nullptr)
	{
		return;
	}
	Pads.AddUnique(Pad);

	const UYardMemoryRecord* const Record = ReadRecord();
	if (Record == nullptr)
	{
		return;
	}
	// A pad that turns up in a world that has ALREADY begun play is a pad the yard has
	// just put back -- which is the moment the runner is set down again. A pad that was
	// simply standing there when the level opened is not.
	const UWorld* const World = Pad->GetWorld();
	const bool bYardReopened = (World != nullptr) && World->HasBegunPlay();

	// Re-resolved on every arrival, so whichever pad turns up last still leaves the
	// right lamp burning and the runner on the right pad.
	ShowYardLamps(Record, Pad->YardName, bYardReopened);
}

void UYardMemorySubsystem::UnregisterPad(AMemoryPadActor* Pad)
{
	Pads.Remove(Pad);
}

void UYardMemorySubsystem::RegisterBoard(AMemoryBoardActor* Board)
{
	if (Board == nullptr)
	{
		return;
	}
	Boards.AddUnique(Board);

	if (const UYardMemoryRecord* const Record = ReadRecord())
	{
		// Its OWN yard's total. A board that showed the other yard's number would be a
		// board about a yard nobody was in.
		ShowYardTotal(Record, Board->YardName);
	}
}

void UYardMemorySubsystem::UnregisterBoard(AMemoryBoardActor* Board)
{
	Boards.Remove(Board);
}

void UYardMemorySubsystem::TakePost(AMemoryPostActor* Post)
{
	if (Post == nullptr)
	{
		return;
	}
	UYardMemoryRecord* const Record = ReadRecord();
	if (Record == nullptr)
	{
		return;
	}
	const FName Key = MakeYardPostKey(Post->YardName, Post->PostId);
	if (Record->TakenPosts.Contains(Key))
	{
		// Already gone. Walking back over the ground it stood on is worth nothing, and
		// nothing below this line runs.
		return;
	}

	Record->TakenPosts.Add(Key);
	// THE NUMBER IT IS SHOWING RIGHT NOW. Banking the amount, rather than the post, is
	// what makes the total survive the yard repainting its posts.
	Record->BankedByYard.FindOrAdd(Post->YardName) += Post->WorthNow;
	WriteRecord(Record);

	ShowYardPosts(Record, Post->YardName);
	ShowYardTotal(Record, Post->YardName);
}

void UYardMemorySubsystem::StandOnPad(AMemoryPadActor* Pad)
{
	if (Pad == nullptr)
	{
		return;
	}
	// The yard SETTING the runner down on a pad is not the runner standing on one.
	// The move fires begin-overlap synchronously, so without this the placement would
	// move the mark to whichever pad happened to come back first.
	if (bSettingRunnerDown)
	{
		return;
	}

	UYardMemoryRecord* const Record = ReadRecord();
	if (Record == nullptr)
	{
		return;
	}
	if (Record->LatestPadByYard.FindRef(Pad->YardName) == Pad->PadId)
	{
		return;                                  // already the mark
	}

	Record->LatestPadByYard.Add(Pad->YardName, Pad->PadId);
	WriteRecord(Record);

	// The mark moves; the runner does not. Setting somebody down on a pad they are
	// already standing on is not something the yard does.
	ShowYardLamps(Record, Pad->YardName, /*bPlaceRunner=*/false);
}

void UYardMemorySubsystem::ShowYardTotal(const UYardMemoryRecord* Record, FName Yard) const
{
	if (Record == nullptr)
	{
		return;
	}
	const int32 Total = Record->BankedByYard.FindRef(Yard);
	for (const TWeakObjectPtr<AMemoryBoardActor>& Weak : Boards)
	{
		if (AMemoryBoardActor* const Board = Weak.Get())
		{
			if (Board->YardName == Yard)
			{
				Board->ShowTotal(Total);
			}
		}
	}
}

void UYardMemorySubsystem::ShowYardPosts(const UYardMemoryRecord* Record, FName Yard) const
{
	if (Record == nullptr)
	{
		return;
	}
	for (const TWeakObjectPtr<AMemoryPostActor>& Weak : Posts)
	{
		if (AMemoryPostActor* const Post = Weak.Get())
		{
			if (Post->YardName == Yard)
			{
				Post->ShowStanding(
					!Record->TakenPosts.Contains(MakeYardPostKey(Yard, Post->PostId)));
			}
		}
	}
}

void UYardMemorySubsystem::ShowYardLamps(const UYardMemoryRecord* Record, FName Yard,
	bool bPlaceRunner)
{
	if (Record == nullptr)
	{
		return;
	}
	const FName Marked = ResolveMarkedPad(Record, Yard);
	for (const TWeakObjectPtr<AMemoryPadActor>& Weak : Pads)
	{
		if (AMemoryPadActor* const Pad = Weak.Get())
		{
			if (Pad->YardName == Yard)
			{
				const bool bLit = (Pad->PadId == Marked) && !Marked.IsNone();
				Pad->ShowLamp(bLit);
				if (bLit && bPlaceRunner)
				{
					PlaceRunnerOn(Pad);
				}
			}
		}
	}
}

FName UYardMemorySubsystem::ResolveMarkedPad(const UYardMemoryRecord* Record, FName Yard) const
{
	if (Record != nullptr)
	{
		if (const FName* const Written = Record->LatestPadByYard.Find(Yard))
		{
			// Honour it only if a pad of that name is actually standing in this yard.
			for (const TWeakObjectPtr<AMemoryPadActor>& Weak : Pads)
			{
				if (const AMemoryPadActor* const Pad = Weak.Get())
				{
					if (Pad->YardName == Yard && Pad->PadId == *Written)
					{
						return *Written;
					}
				}
			}
		}
	}
	// Nothing written down: the yard's FIRST pad, found by the order painted on the
	// pads rather than by the order they happen to have been spawned in.
	FName Best = NAME_None;
	int32 BestOrder = MAX_int32;
	for (const TWeakObjectPtr<AMemoryPadActor>& Weak : Pads)
	{
		if (const AMemoryPadActor* const Pad = Weak.Get())
		{
			if (Pad->YardName == Yard && Pad->PadOrder < BestOrder)
			{
				BestOrder = Pad->PadOrder;
				Best = Pad->PadId;
			}
		}
	}
	return Best;
}

void UYardMemorySubsystem::PlaceRunnerOn(const AMemoryPadActor* Pad)
{
	if (Pad == nullptr)
	{
		return;
	}
	UWorld* const World = Pad->GetWorld();
	if (World == nullptr)
	{
		return;
	}
	APawn* const Runner = UGameplayStatics::GetPlayerPawn(World, 0);
	if (Runner == nullptr)
	{
		return;
	}

	// Lift measured off the runner that is actually here, never a constant: the pad's
	// origin is on the floor, so the pawn has to be raised by its own half height.
	float Lift = 100.0f;
	if (const UCapsuleComponent* const Capsule =
			Cast<UCapsuleComponent>(Runner->GetRootComponent()))
	{
		Lift = Capsule->GetScaledCapsuleHalfHeight();
	}

	FVector Target = Pad->GetActorLocation();
	Target.Z += Lift + kFootroom;

	// The move below fires the pad's begin-overlap SYNCHRONOUSLY (USceneComponent's
	// move path calls UpdateOverlaps with notifications on), so the flag has to be up
	// across the move itself: being set down is not standing on a pad, and letting it
	// count would move the mark to whichever pad came back first.
	TGuardValue<bool> SettingDown(bSettingRunnerDown, true);

	Runner->SetActorLocation(Target, /*bSweep=*/false, nullptr, ETeleportType::TeleportPhysics);

	// Set down, not held down. Nothing here disables input, ignores move input, changes
	// the movement mode or touches the top speed -- the runner can walk off the pad the
	// very next frame.
	if (ACharacter* const AsCharacter = Cast<ACharacter>(Runner))
	{
		if (UCharacterMovementComponent* const Movement = AsCharacter->GetCharacterMovement())
		{
			Movement->StopMovementImmediately();
		}
	}
}
