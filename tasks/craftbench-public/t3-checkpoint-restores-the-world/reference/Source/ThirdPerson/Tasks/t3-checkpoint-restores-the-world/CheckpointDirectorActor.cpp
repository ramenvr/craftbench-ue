// Copyright CraftBench. All Rights Reserved.

#include "CheckpointDirectorActor.h"

#include "CheckpointYardProps.h"

#include "Components/SceneComponent.h"

#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"

ACheckpointDirectorActor::ACheckpointDirectorActor()
{
	// The yard announces a stand, a bank and a death. What it does NOT announce is a
	// coin being picked up, so the coins are read each frame from the coins themselves.
	PrimaryActorTick.bCanEverTick = true;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	Tags.Add(FName(TEXT("CheckpointDirector")));
}

void ACheckpointDirectorActor::FindTheYard()
{
	TArray<AActor*> Found;

	UGameplayStatics::GetAllActorsOfClass(this, ACheckpointStandActor::StaticClass(), Found);
	for (AActor* A : Found)
	{
		if (ACheckpointStandActor* const S = Cast<ACheckpointStandActor>(A))
		{
			Stands.Add(S);
			S->OnStoodOn.AddDynamic(this, &ACheckpointDirectorActor::OnPadStoodOn);
		}
	}

	UGameplayStatics::GetAllActorsOfClass(this, ALatchDoorActor::StaticClass(), Found);
	for (AActor* A : Found)
	{
		if (ALatchDoorActor* const D = Cast<ALatchDoorActor>(A))
		{
			Doors.Add(D);
		}
	}

	UGameplayStatics::GetAllActorsOfClass(this, ACoinPickupActor::StaticClass(), Found);
	for (AActor* A : Found)
	{
		if (ACoinPickupActor* const C = Cast<ACoinPickupActor>(A))
		{
			Coins.Add(C);
		}
	}

	UGameplayStatics::GetAllActorsOfClass(this, AHazardStripActor::StaticClass(), Found);
	for (AActor* A : Found)
	{
		if (AHazardStripActor* const H = Cast<AHazardStripActor>(A))
		{
			Hazards.Add(H);
			H->OnLethalTouch.AddDynamic(this, &ACheckpointDirectorActor::OnLifeEnded);
		}
	}

	UGameplayStatics::GetAllActorsOfClass(this, ABankCounterActor::StaticClass(), Found);
	if (Found.Num() > 0)
	{
		Counter = Cast<ABankCounterActor>(Found[0]);
		if (Counter != nullptr)
		{
			Counter->OnBanked.AddDynamic(this, &ACheckpointDirectorActor::OnCoinsBanked);
		}
	}

	Places.Init(EPlace::OnStand, Coins.Num());
	MarkPlaces = Places;
	MarkDoorOpen.Init(false, Doors.Num());
}

void ACheckpointDirectorActor::BeginPlay()
{
	Super::BeginPlay();
	FindTheYard();
}

void ACheckpointDirectorActor::ReadTheCoins()
{
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (Coins[i] == nullptr || Places[i] == EPlace::OverTheLine)
		{
			// Over the line is a one-way door. A banked coin is hidden exactly like a
			// carried one, so re-reading it from the coin would quietly turn progress
			// back into something somebody is holding.
			continue;
		}
		Places[i] = Coins[i]->IsCollected() ? EPlace::InHand : EPlace::OnStand;
	}
}

void ACheckpointDirectorActor::RememberThisMoment()
{
	ReadTheCoins();
	MarkPlaces = Places;
	MarkDoorOpen.SetNum(Doors.Num());
	for (int32 i = 0; i < Doors.Num(); ++i)
	{
		MarkDoorOpen[i] = (Doors[i] != nullptr) && Doors[i]->IsOpen();
	}
	bRemembered = true;
}

int32 ACheckpointDirectorActor::CountInHand() const
{
	int32 N = 0;
	for (const EPlace P : Places)
	{
		if (P == EPlace::InHand)
		{
			++N;
		}
	}
	return N;
}

void ACheckpointDirectorActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!bHaveEntrance)
	{
		if (const ACharacter* const Hero = UGameplayStatics::GetPlayerCharacter(this, 0))
		{
			Entrance = Hero->GetActorTransform();
			bHaveEntrance = true;
		}
	}

	ReadTheCoins();

	if (!bRemembered)
	{
		// Before anybody has stood on a pad the mark is the way in, and the moment that
		// mark was set is the moment the yard opened. Taken on the first tick rather
		// than in BeginPlay because nothing guarantees this actor begins play after the
		// counter has put its own opening number on the board.
		RememberThisMoment();
	}
}

void ACheckpointDirectorActor::OnPadStoodOn(ACheckpointStandActor* Stand)
{
	if (Stand == nullptr || bPuttingBack)
	{
		// Coming back lands on the mark pad, which announces the stand again. Ignoring
		// it here and moving the character last are two independent reasons the same
		// answer comes out either way.
		return;
	}
	if (Mark != nullptr && Mark != Stand)
	{
		Mark->SetArmed(false);
	}
	Mark = Stand;
	Mark->SetArmed(true);

	// Standing on a pad does nothing else. No door moves, no coin is touched, and
	// nothing is banked.
	RememberThisMoment();
}

void ACheckpointDirectorActor::OnCoinsBanked(int32 Amount, int32 NewBanked)
{
	ReadTheCoins();
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (Places[i] == EPlace::InHand)
		{
			Places[i] = EPlace::OverTheLine;
		}
	}
}

void ACheckpointDirectorActor::OnLifeEnded(AActor* Victim)
{
	const ACharacter* const Hero = UGameplayStatics::GetPlayerCharacter(this, 0);
	if (Hero == nullptr || Victim != Hero)
	{
		return;
	}
	PutTheYardBack();
}

void ACheckpointDirectorActor::PutTheYardBack()
{
	bPuttingBack = true;
	ReadTheCoins();

	// 1. THE DOORS, through the door's own operation. Putting the leaf back by hand
	//    would look right and leave the latch set, and the plate would never open that
	//    door again.
	for (int32 i = 0; i < Doors.Num(); ++i)
	{
		if (Doors[i] != nullptr && MarkDoorOpen.IsValidIndex(i)
			&& Doors[i]->IsOpen() != MarkDoorOpen[i])
		{
			Doors[i]->SetOpen(MarkDoorOpen[i]);
		}
	}

	// 2. THE COINS: what the mark remembered, minus anything that has crossed the line
	//    since. A coin that was sitting on its stand when the mark was set and has been
	//    banked in the meantime does NOT come back.
	for (int32 i = 0; i < Coins.Num(); ++i)
	{
		if (Coins[i] == nullptr || Places[i] == EPlace::OverTheLine)
		{
			continue;
		}
		const EPlace Want = MarkPlaces.IsValidIndex(i) ? MarkPlaces[i] : EPlace::OnStand;
		if (Want == EPlace::OverTheLine)
		{
			continue;
		}
		if (Want == EPlace::OnStand && Coins[i]->IsCollected())
		{
			Coins[i]->Restore();
		}
		else if (Want == EPlace::InHand && !Coins[i]->IsCollected())
		{
			Coins[i]->Collect();
		}
		Places[i] = Want;
	}

	// 3. CARRIED IS DERIVED, NOT RESTORED. The snapshot's number is the wrong one: some
	//    of what was in hand when the mark was set has been banked since, and handing
	//    it back would let the same coins be banked twice. BANKED itself is not written
	//    here or anywhere else in this file.
	if (Counter != nullptr)
	{
		Counter->SetCarried(CountInHand());
	}

	// 4. THE CHARACTER, LAST, so that if the pad announces the stand again the yard it
	//    would be remembering is already the right one.
	if (ACharacter* const Hero = UGameplayStatics::GetPlayerCharacter(this, 0))
	{
		const FTransform Back = (Mark != nullptr) ? Mark->GetRespawnTransform() : Entrance;
		if (UCharacterMovementComponent* const Move = Hero->GetCharacterMovement())
		{
			// A teleport does not clear velocity -- the movement component only marks
			// the move and re-finds the floor -- so without this they arrive sliding.
			Move->StopMovementImmediately();
		}
		Hero->TeleportTo(Back.GetLocation(), Back.Rotator());
	}

	bPuttingBack = false;
}
