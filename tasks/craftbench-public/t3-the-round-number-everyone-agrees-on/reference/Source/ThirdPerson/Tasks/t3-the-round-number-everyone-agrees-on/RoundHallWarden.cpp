// Copyright CraftBench. All Rights Reserved.

#include "RoundHallWarden.h"

#include "RoundHallProps.h"

#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

namespace
{
	const FName kHallSignTag(TEXT("HallSign"));
	const FName kEntranceStoneTag(TEXT("EntranceStone"));
	const FName kStepMarkTag(TEXT("StepMark"));
	const FName kHoistPlateTag(TEXT("HoistPlate"));
	const FName kSinkholeTag(TEXT("Sinkhole"));

	/** A fresh body is put in with its middle this far above the mark, so the capsule
	 *  starts clear of the floor and settles onto it instead of into it. */
	constexpr float kStandingLiftUu = 100.0f;

	template <typename T>
	T* FirstWithTag(UWorld* World, const FName& Tag)
	{
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsWithTag(World, Tag, Found);
		for (AActor* A : Found)
		{
			if (T* const Typed = Cast<T>(A))
			{
				return Typed;
			}
		}
		return nullptr;
	}
}

void URoundHallWarden::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	UWorld* const World = &InWorld;

	Stone = FirstWithTag<AEntranceStoneActor>(World, kEntranceStoneTag);
	Mark = FirstWithTag<AStepMarkActor>(World, kStepMarkTag);

	// THE NUMBER THE HALL STARTS ON is read off the stone, at play, once. It is not the
	// number written in the level and it is not the same number every visit.
	if (Stone != nullptr)
	{
		RoundNumber = Stone->GetStartNumber();
	}

	if (Mark != nullptr)
	{
		Mark->OnSteppedOn.AddDynamic(this, &URoundHallWarden::HandleSteppedOn);
	}

	// Every hoist in the hall, so a second one would work too.
	TArray<AActor*> Hoists;
	UGameplayStatics::GetAllActorsWithTag(World, kHoistPlateTag, Hoists);
	for (AActor* A : Hoists)
	{
		if (AHoistPlateActor* const H = Cast<AHoistPlateActor>(A))
		{
			H->OnSignRaised.AddDynamic(this, &URoundHallWarden::HandleSignRaised);
		}
	}

	TArray<AActor*> Holes;
	UGameplayStatics::GetAllActorsWithTag(World, kSinkholeTag, Holes);
	for (AActor* A : Holes)
	{
		if (ASinkholeActor* const S = Cast<ASinkholeActor>(A))
		{
			S->OnRunnerLost.AddDynamic(this, &URoundHallWarden::HandleRunnerLost);
		}
	}

	// From the first frame the hall is on a number, and every one of its signs says so.
	TellEverySignInTheHall();

	// The runner the hall opens with is starting their walk now, on the number the hall
	// starts on.
	WriteTheDoorplate();

	// Said again on the very next tick, and only for this reason: a sign blanks its own
	// face when it starts, so if any sign in the hall were to start AFTER this runs it
	// would wipe what it was just told and the hall would open blank. Repeating once,
	// a frame later, makes the opening state independent of the order things start in.
	// It costs one frame against the half second a sign is allowed, and it is the only
	// ordering assumption in the whole file, so it is worth not making.
	World->GetTimerManager().SetTimerForNextTick(
		this, &URoundHallWarden::TellEverySignInTheHall);
	// Same reason, same one frame: the stone blanks its own doorplate when it starts.
	// Actor start-up runs inside the rules object's own start, which is ahead of this,
	// so this is belt and braces rather than a fix -- but it is one line and it removes
	// the last ordering assumption in the file.
	World->GetTimerManager().SetTimerForNextTick(
		this, &URoundHallWarden::WriteTheDoorplate);
}

void URoundHallWarden::HandleSteppedOn(AActor* /*Walker*/)
{
	// THE STEP IS READ NOW, off the mark, not remembered from the start of the visit.
	// The mark's step changes part way through and every later advance is bigger.
	if (Mark == nullptr)
	{
		return;
	}
	RoundNumber += Mark->GetStepWritten();
	TellEverySignInTheHall();
}

void URoundHallWarden::HandleSignRaised(AHallSignActor* RaisedSign)
{
	if (RaisedSign == nullptr || !RaisedSign->BelongsToTheHall())
	{
		return;
	}
	// It comes up on the number the hall is on right now. From here it keeps up with
	// every later change because TellEverySignInTheHall finds it like any other.
	RaisedSign->Print(RoundNumber);
}

void URoundHallWarden::HandleRunnerLost()
{
	// The number is NOT touched here. That is the whole point of it living on the hall:
	// losing a body cannot cost the hall its round, and every sign goes on showing what
	// it was already showing. The DOORPLATE is a different matter -- it is about who is
	// walking, not about what the hall is on -- and PutANewRunnerIn writes it at the
	// moment a fresh runner actually starts.
	PutANewRunnerIn();

	// Belt and braces: if the body that fell has not finished coming off the controller
	// this frame, try again on the next one. PutANewRunnerIn does nothing when there is
	// already a runner, so calling it twice can never make two.
	if (UWorld* const World = GetWorld())
	{
		World->GetTimerManager().SetTimerForNextTick(
			this, &URoundHallWarden::PutANewRunnerIn);
	}
}

void URoundHallWarden::PutANewRunnerIn()
{
	UWorld* const World = GetWorld();
	if (World == nullptr || Stone == nullptr)
	{
		return;
	}

	APlayerController* const PC = UGameplayStatics::GetPlayerController(World, 0);
	AGameModeBase* const Rules = World->GetAuthGameMode();
	if (PC == nullptr || Rules == nullptr)
	{
		return;
	}

	// Already somebody in the hall: leave them alone. This is what keeps there being
	// exactly one runner alive however many times this is called.
	if (PC->GetPawn() != nullptr)
	{
		return;
	}

	const FTransform Where(
		Stone->GetActorRotation(),
		Stone->GetMarkCentre() + FVector(0.0f, 0.0f, kStandingLiftUu),
		FVector::OneVector);

	// The KIND of runner comes from the hall's own rules, which is the same kind the
	// visit began with -- nothing here names a body class, so a hall that runs some
	// other kind of runner gets that kind back.
	Rules->RestartPlayerAtTransform(PC, Where);

	// A fresh runner is starting their walk, and the round they are starting on is
	// whatever the hall is on right now -- which, because the number belongs to the
	// hall and not to the body that fell, is exactly what it was before the fall. This
	// one line is the whole crossing point: it is a fact about the NUMBER, written at a
	// moment decided by the BODY. Unconditional after the restart on purpose: the early
	// return above already means this is only reached when nobody was in the hall, and
	// re-writing the same number costs nothing.
	WriteTheDoorplate();
}

void URoundHallWarden::TellEverySignInTheHall()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	TArray<AActor*> Signs;
	UGameplayStatics::GetAllActorsWithTag(World, kHallSignTag, Signs);
	for (AActor* A : Signs)
	{
		AHallSignActor* const S = Cast<AHallSignActor>(A);
		if (S == nullptr)
		{
			continue;
		}
		// The relic is not one of the hall's, so it is never written to. It goes on
		// showing the number painted on it because nothing here ever touches it.
		if (!S->BelongsToTheHall())
		{
			continue;
		}
		S->Print(RoundNumber);
	}
}

void URoundHallWarden::WriteTheDoorplate()
{
	if (Stone != nullptr)
	{
		Stone->PrintOnTheDoorplate(RoundNumber);
	}
}
