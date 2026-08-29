// Copyright CraftBench. All Rights Reserved.

#include "RecipePlaqueActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* const kSlabMesh = TEXT("/Engine/BasicShapes/Cube");
	const TCHAR* const kSlabLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02");
	const TCHAR* const kArrow = TEXT("->");
	const TCHAR* const kTierMark = TEXT(":");
	const TCHAR* const kTierWord = TEXT("TIER");

	/** Splits a carving into the step it is carved with, the token list left of "->",
	 *  and the single token right of it. Whitespace-insensitive and case-folded UP,
	 *  so "tier 1: ore  ore ore->INGOT" reads the same as
	 *  "TIER 1 : ORE ORE ORE -> INGOT". Returns false when there is no arrow, no left
	 *  side, or the right side is not exactly one token; the step is 0 when the
	 *  carving does not open with one, and nothing before the ":" is ever mistaken
	 *  for a unit. */
	bool SplitCarving(const FString& Carved, int32& OutTier, TArray<FString>& OutLeft,
		FString& OutRight)
	{
		OutTier = 0;
		FString Body = Carved;

		// THE STEP, if the carving opens with one. Anything else before a ":" is left
		// where it is rather than being swallowed, so an unexpected carving degrades
		// to "no step" instead of silently losing its units.
		FString Head, Tail;
		if (Body.Split(kTierMark, &Head, &Tail))
		{
			Head.ToUpperInline();
			TArray<FString> HeadTokens;
			Head.ParseIntoArrayWS(HeadTokens);
			if (HeadTokens.Num() == 2 && HeadTokens[0] == kTierWord
				&& HeadTokens[1].IsNumeric())
			{
				OutTier = FCString::Atoi(*HeadTokens[1]);
				Body = Tail;
			}
		}

		FString Left, Right;
		if (!Body.Split(kArrow, &Left, &Right))
		{
			return false;
		}
		Left.ToUpperInline();
		Right.ToUpperInline();
		Left.ParseIntoArrayWS(OutLeft);
		TArray<FString> RightTokens;
		Right.ParseIntoArrayWS(RightTokens);
		if (OutLeft.Num() == 0 || RightTokens.Num() != 1)
		{
			return false;
		}
		OutRight = RightTokens[0];
		return true;
	}
}

ARecipePlaqueActor::ARecipePlaqueActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kSlabMesh);

	Slab = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Slab"));
	SetRootComponent(Slab);
	if (CubeMesh.Succeeded())
	{
		Slab->SetStaticMesh(CubeMesh.Object);
	}
	// A 320 x 40 x 200 cm standing slab.
	Slab->SetRelativeScale3D(FVector(3.2f, 0.4f, 2.0f));
	Slab->SetMobility(EComponentMobility::Movable);
	Slab->SetCollisionProfileName(TEXT("NoCollision"));
	Slab->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kSlabLook);
	if (Look.Succeeded())
	{
		Slab->SetMaterial(0, Look.Object);
	}

	Carving = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Carving"));
	Carving->SetupAttachment(Slab);
	// Divided back out of the slab's own scale so the carving sits proud of the face
	// rather than inside it.
	// Relative offsets are multiplied by the slab's own non-uniform scale, so the
	// 30 uu of clearance is divided back out of it (0.4 in Y) to land 30 uu proud
	// of the face rather than 12 uu inside it.
	Carving->SetRelativeLocation(FVector(0.0f, -30.0f / 0.4f, 0.0f));
	Carving->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	Carving->SetRelativeScale3D(FVector(1.0f / 3.2f, 1.0f / 0.4f, 1.0f / 2.0f));
	Carving->SetHorizontalAlignment(EHTA_Center);
	Carving->SetVerticalAlignment(EVRTA_TextCenter);
	Carving->SetWorldSize(48.0f);
	Carving->SetTextRenderColor(FColor(230, 230, 255));
	Carving->SetMobility(EComponentMobility::Movable);
	Carving->SetText(FText::FromString(TEXT("--")));

	Tags.Add(FName("RecipePlaque"));
}

void ARecipePlaqueActor::BeginPlay()
{
	Super::BeginPlay();

	// Say what is carved on you from the first frame, whatever the editor left behind.
	RefreshCarving();
}

TArray<FName> ARecipePlaqueActor::GetInputs() const
{
	TArray<FName> Out;
	TArray<FString> Left;
	FString Right;
	int32 Tier = 0;
	if (!SplitCarving(CarvedText, Tier, Left, Right))
	{
		return Out;
	}
	// REPEATS ARE KEPT. "ORE ORE COAL" is three entries, and the two ORE are two
	// units, not one kind -- that difference is the whole of the counting rule.
	Out.Reserve(Left.Num());
	for (const FString& Token : Left)
	{
		Out.Add(FName(*Token));
	}
	return Out;
}

FName ARecipePlaqueActor::GetOutput() const
{
	TArray<FString> Left;
	FString Right;
	int32 Tier = 0;
	if (!SplitCarving(CarvedText, Tier, Left, Right))
	{
		return NAME_None;
	}
	return FName(*Right);
}

int32 ARecipePlaqueActor::GetTier() const
{
	TArray<FString> Left;
	FString Right;
	int32 Tier = 0;
	if (!SplitCarving(CarvedText, Tier, Left, Right))
	{
		return 0;
	}
	return Tier;
}

void ARecipePlaqueActor::RefreshCarving()
{
	if (Carving != nullptr)
	{
		Carving->SetText(FText::FromString(CarvedText));
	}
}
