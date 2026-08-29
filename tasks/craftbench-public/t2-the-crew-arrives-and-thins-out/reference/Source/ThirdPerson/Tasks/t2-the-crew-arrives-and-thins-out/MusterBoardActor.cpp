// Copyright CraftBench. All Rights Reserved.

#include "MusterBoardActor.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "CrewBerthActor.h"
#include "CrewHandActor.h"
#include "CrewPlateActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kLampLitIntensity = 7000.0f;
	constexpr float kLampSpacingUu = 500.0f;
	const FLinearColor kLampColour(0.35f, 1.0f, 0.55f);

	/** A floor under the arrival clock so a nonsense gap cannot spin the fill loop. */
	constexpr double kSmallestUsefulGapSeconds = 0.01;
}

AMusterBoardActor::AMusterBoardActor()
{
	// Every frame: a plate can be stepped on at any moment, hands turn up on the
	// board's own clock, and the deck is allowed half a second to catch up.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	// A bare scene root at unit scale; the face is scaled, the root never is, so no
	// child's offset or size is multiplied behind your back.
	USceneComponent* const Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	// A 40 x 3000 x 500 cm board standing on its edge. Local +X is the side the deck
	// is on: the lamps and the chalk are on that side.
	Face = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Face"));
	Face->SetupAttachment(Pivot);
	Face->SetRelativeLocation(FVector(0.0f, 0.0f, 250.0f));
	Face->SetRelativeScale3D(FVector(0.4f, 30.0f, 5.0f));
	if (CubeMesh.Succeeded())
	{
		Face->SetStaticMesh(CubeMesh.Object);
	}
	Face->SetCollisionProfileName(TEXT("NoCollision"));
	Face->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BoardLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (BoardLook.Succeeded())
	{
		Face->SetMaterial(0, BoardLook.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Dark.Succeeded())
	{
		DarkLook = Dark.Object;
	}

	LampBulbs.Reserve(NumLamps);
	LampGlows.Reserve(NumLamps);
	for (int32 Index = 0; Index < NumLamps; ++Index)
	{
		const float AlongFace =
			(static_cast<float>(Index) - 0.5f * (NumLamps - 1)) * kLampSpacingUu;

		UStaticMeshComponent* const Bulb = CreateDefaultSubobject<UStaticMeshComponent>(
			*FString::Printf(TEXT("LampBulb%d"), Index));
		Bulb->SetupAttachment(Pivot);
		Bulb->SetRelativeLocation(FVector(60.0f, AlongFace, 330.0f));
		Bulb->SetRelativeScale3D(FVector(0.9f, 0.9f, 0.9f));
		if (SphereMesh.Succeeded())
		{
			Bulb->SetStaticMesh(SphereMesh.Object);
		}
		if (DarkLook != nullptr)
		{
			Bulb->SetMaterial(0, DarkLook);
		}
		Bulb->SetCollisionProfileName(TEXT("NoCollision"));
		Bulb->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		LampBulbs.Add(Bulb);

		UPointLightComponent* const Glow = CreateDefaultSubobject<UPointLightComponent>(
			*FString::Printf(TEXT("LampGlow%d"), Index));
		Glow->SetupAttachment(Pivot);
		Glow->SetRelativeLocation(FVector(140.0f, AlongFace, 330.0f));
		Glow->SetLightColor(kLampColour);
		Glow->SetIntensity(0.0f);
		Glow->SetAttenuationRadius(900.0f);
		Glow->SetMobility(EComponentMobility::Movable);
		LampGlows.Add(Glow);
	}

	Chalk = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Chalk"));
	Chalk->SetupAttachment(Pivot);
	Chalk->SetRelativeLocation(FVector(60.0f, 0.0f, 230.0f));
	Chalk->SetHorizontalAlignment(EHTA_Center);
	Chalk->SetWorldSize(46.0f);
	Chalk->SetTextRenderColor(FColor(240, 240, 220));

	Tags.Add(FName(TEXT("MusterBoard")));
}

void AMusterBoardActor::BeginPlay()
{
	Super::BeginPlay();

	// Every lamp dark and every spot empty from the first frame.
	for (int32 Spot = 1; Spot <= GetLampCount(); ++Spot)
	{
		SetLampLit(Spot, false);
	}
	RefreshChalkText();

	UWorld* const W = GetWorld();
	if (W == nullptr)
	{
		return;
	}

	// Resolve MY OWN furniture once, by the board name each piece carries. The deck
	// is fixed, so which pieces are mine never changes -- only the NUMBERS on them
	// do, and those are re-read every time they are used.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(W, FName(TEXT("CrewBerth")), Found);
	for (AActor* A : Found)
	{
		ACrewBerthActor* const Berth = Cast<ACrewBerthActor>(A);
		if (Berth != nullptr && Berth->BoardTag == BoardTag)
		{
			MyBerths.Add(Berth);
		}
	}

	// Lowest-numbered first. Everything downstream -- who stands where, and therefore
	// which arrival place lands on which spot -- depends on this order, so it is done
	// once, explicitly, rather than trusted to the order the level happens to return.
	for (int32 i = 1; i < MyBerths.Num(); ++i)
	{
		ACrewBerthActor* const Key = MyBerths[i];
		int32 j = i - 1;
		while (j >= 0 && MyBerths[j]->SpotNumber > Key->SpotNumber)
		{
			MyBerths[j + 1] = MyBerths[j];
			--j;
		}
		MyBerths[j + 1] = Key;
	}

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(W, FName(TEXT("CrewPlate")), Found);
	for (AActor* A : Found)
	{
		ACrewPlateActor* const Plate = Cast<ACrewPlateActor>(A);
		if (Plate == nullptr || Plate->BoardTag != BoardTag)
		{
			continue;
		}
		if (Plate->bIsCallPlate)
		{
			CallPlate = Plate;
		}
		else
		{
			StandDownPlate = Plate;
		}
	}

	// Whoever is already standing on a plate when the night starts is not a fresh
	// step onto it.
	bCallPlatePressed = (CallPlate != nullptr) && CallPlate->IsSomebodyStandingHere();
	bStandDownPlatePressed =
		(StandDownPlate != nullptr) && StandDownPlate->IsSomebodyStandingHere();
}

void AMusterBoardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* const W = GetWorld();
	if (W == nullptr)
	{
		return;
	}
	const double Now = W->GetTimeSeconds();

	PruneDeparted();

	// --- The plates, on the STEP, not on the standing. Stepping on and off again
	// --- while a call is still running must not start a second one.
	const bool bOnCall = (CallPlate != nullptr) && CallPlate->IsSomebodyStandingHere();
	const bool bOnStandDown =
		(StandDownPlate != nullptr) && StandDownPlate->IsSomebodyStandingHere();

	if (bOnCall && !bCallPlatePressed && !bCallRunning)
	{
		BeginCall(Now);
	}
	if (bOnStandDown && !bStandDownPlatePressed)
	{
		StandWatchDown();
	}
	bCallPlatePressed = bOnCall;
	bStandDownPlatePressed = bOnStandDown;

	// --- The fill, on the board's own clock. The gap is read LIVE each time the next
	// --- arrival is booked, because the chalk can change under us.
	while (bCallRunning && Now >= NextArrivalTime)
	{
		if (!BringOneAboard())
		{
			bCallRunning = false;
			break;
		}
		++ArrivalsThisCall;
		NextArrivalTime += FMath::Max(kSmallestUsefulGapSeconds,
			static_cast<double>(SecondsBetweenArrivals));
		if (ArrivalsThisCall >= CallSize)
		{
			bCallRunning = false;
		}
	}

	// --- The lamps: lit exactly while their own spot has somebody on it.
	RefreshLamps();

	// Presentation only.
	RefreshChalkText();
}

void AMusterBoardActor::BeginCall(double NowSeconds)
{
	// How many is read HERE, at the moment the plate is stepped on, and nowhere else.
	CallSize = FMath::Max(0, HandsToCall);
	ArrivalsThisCall = 0;

	// A new watch: the arrival order starts again from nobody. Whoever is already
	// aboard from an earlier watch is not part of it and can never be named by this
	// watch's slate.
	WatchArrivals.Reset();

	NextArrivalTime = NowSeconds + FMath::Max(kSmallestUsefulGapSeconds,
		static_cast<double>(SecondsBetweenArrivals));
	bCallRunning = (CallSize > 0);
}

bool AMusterBoardActor::BringOneAboard()
{
	UWorld* const W = GetWorld();
	if (W == nullptr)
	{
		return false;
	}

	ACrewBerthActor* const Berth = LowestFreeBerth();
	if (Berth == nullptr)
	{
		return false;
	}
	const int32 Code = NextUnspentCode();
	if (Code == 0)
	{
		// No number left to issue. Nobody comes aboard unbadged.
		return false;
	}

	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ACrewHandActor* const Hand = W->SpawnActor<ACrewHandActor>(
		ACrewHandActor::StaticClass(),
		Berth->GetStandLocation(),
		Berth->GetActorRotation(),
		Params);
	if (Hand == nullptr)
	{
		return false;
	}

	Hand->SetBadgeCode(Code);
	SpentCodes.Add(Code);
	Occupant.Add(Berth->SpotNumber, Hand);
	WatchArrivals.Add(Hand);
	return true;
}

void AMusterBoardActor::StandWatchDown()
{
	// RESOLVE EVERY PLACE TO A BODY FIRST, then send them ashore. Destroying as the
	// slate is walked would shift the remaining places under the loop, which sends
	// the wrong hands ashore while sending the right NUMBER of them.
	TArray<ACrewHandActor*> Going;
	for (const int32 Place : SlatePositions)
	{
		// "The second to turn up this watch" is the second entry of the arrival
		// order -- not standing spot number 2, and not a count.
		const int32 Index = Place - 1;
		if (!WatchArrivals.IsValidIndex(Index))
		{
			continue;
		}
		ACrewHandActor* const Hand = WatchArrivals[Index].Get();
		if (IsValid(Hand))
		{
			Going.AddUnique(Hand);
		}
	}

	for (ACrewHandActor* const Hand : Going)
	{
		SendAshore(Hand);
	}
}

void AMusterBoardActor::SendAshore(ACrewHandActor* Hand)
{
	if (!IsValid(Hand))
	{
		return;
	}

	for (auto It = Occupant.CreateIterator(); It; ++It)
	{
		if (It.Value().Get() == Hand)
		{
			It.RemoveCurrent();
		}
	}
	// Emptied, never removed: the arrival PLACES of everybody else must not shift.
	for (TWeakObjectPtr<ACrewHandActor>& Slot : WatchArrivals)
	{
		if (Slot.Get() == Hand)
		{
			Slot.Reset();
		}
	}

	Hand->Destroy();
}

ACrewBerthActor* AMusterBoardActor::LowestFreeBerth() const
{
	for (ACrewBerthActor* const Berth : MyBerths)
	{
		if (Berth == nullptr)
		{
			continue;
		}
		const TWeakObjectPtr<ACrewHandActor>* const Found =
			Occupant.Find(Berth->SpotNumber);
		if (Found == nullptr || !Found->IsValid())
		{
			return Berth;
		}
	}
	return nullptr;
}

int32 AMusterBoardActor::NextUnspentCode() const
{
	// The roster is read LIVE and IN WRITTEN ORDER, and a number spent earlier
	// tonight is skipped -- including the numbers of hands that have already gone
	// ashore. The re-chalked roster keeps the old numbers and adds new ones, so
	// starting at the top would re-issue a badge somebody is still wearing.
	for (const int32 Code : RosterCodes)
	{
		if (Code != 0 && !SpentCodes.Contains(Code))
		{
			return Code;
		}
	}
	return 0;
}

void AMusterBoardActor::PruneDeparted()
{
	for (auto It = Occupant.CreateIterator(); It; ++It)
	{
		if (!It.Value().IsValid())
		{
			It.RemoveCurrent();
		}
	}
}

void AMusterBoardActor::RefreshLamps()
{
	for (const ACrewBerthActor* const Berth : MyBerths)
	{
		if (Berth == nullptr)
		{
			continue;
		}
		const TWeakObjectPtr<ACrewHandActor>* const Found =
			Occupant.Find(Berth->SpotNumber);
		SetLampLit(Berth->SpotNumber, Found != nullptr && Found->IsValid());
	}
}

void AMusterBoardActor::RefreshChalkText()
{
	if (Chalk == nullptr)
	{
		return;
	}

	FString Roster;
	for (int32 Index = 0; Index < RosterCodes.Num(); ++Index)
	{
		Roster += (Index == 0 ? TEXT("") : TEXT(" "));
		Roster += FString::FromInt(RosterCodes[Index]);
	}
	FString Slate;
	for (int32 Index = 0; Index < SlatePositions.Num(); ++Index)
	{
		Slate += (Index == 0 ? TEXT("") : TEXT(" "));
		Slate += FString::FromInt(SlatePositions[Index]);
	}

	Chalk->SetText(FText::FromString(FString::Printf(
		TEXT("CALL %d   EVERY %.1fs<br>ROSTER %s<br>ASHORE %s"),
		HandsToCall, SecondsBetweenArrivals, *Roster, *Slate)));
}

void AMusterBoardActor::SetLampLit(int32 SpotNumber, bool bNewLit)
{
	// The lamp row is numbered the way the standing spots are: the first lamp belongs
	// to spot number 1.
	const int32 Index = SpotNumber - 1;
	if (LampGlows.IsValidIndex(Index) && LampGlows[Index] != nullptr)
	{
		LampGlows[Index]->SetIntensity(bNewLit ? kLampLitIntensity : 0.0f);
	}
	if (LampBulbs.IsValidIndex(Index) && LampBulbs[Index] != nullptr)
	{
		UMaterialInterface* const Look = bNewLit ? LitLook : DarkLook;
		if (Look != nullptr)
		{
			LampBulbs[Index]->SetMaterial(0, Look);
		}
	}
}

bool AMusterBoardActor::IsLampLit(int32 SpotNumber) const
{
	const int32 Index = SpotNumber - 1;
	return LampGlows.IsValidIndex(Index)
		&& LampGlows[Index] != nullptr
		&& LampGlows[Index]->Intensity > 0.0f;
}

int32 AMusterBoardActor::GetLampCount() const
{
	return LampGlows.Num();
}
