// Copyright CraftBench. All Rights Reserved.
//
// L2 for t2-collect-then-exit.
//
// Derives ACraftBenchFunctionalTest, NOT the pawn base: the hero comes from the
// map's PlayerStart and game mode and is resolved by POSSESSION, and the control is
// a placed relic rather than a second pawn, so no fixture-local pawn spawner is
// needed and neither base class is touched.
//
// The count is a SET of distinct relic pointers, never an index high-water mark, so
// whatever order GetAllActorsWithTag happens to return cannot change a verdict.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "CollectThenExitFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class ACollectThenExitFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACollectThenExitFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** One walk leg: its waypoints are visited in order, then the leg goes idle. */
	struct FLeg
	{
		TArray<FVector> Waypoints;
		int32 Next = 0;
		bool bActive = false;
	};

	bool ResolveByTag(const TCHAR* Tag, int32 Expected, TArray<AActor*>& Out);
	AActor* NearestRelic(const TArray<AActor*>& Relics, const FVector2D& At) const;

	/** Readouts, all read by COMPONENT NAME so a subclassed actor still answers. */
	class UTextRenderComponent* FindText(AActor* OnActor, const TCHAR* Name) const;
	FString ReadTallyRaw() const;
	/** Parsed n from "n/3"; -1 when the face does not parse, incl. shipped blank. */
	int32 ReadTally() const;
	FString ReadStatus() const;
	double LampBrightness() const;

	bool VisiblyPresent(AActor* Relic) const;
	bool HeroInExit(double Margin) const;

	void ReleaseLeg(int32 Index);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Exit;
	TWeakObjectPtr<AActor> Board;
	/** The three the route visits, and the one it never does. */
	TArray<TWeakObjectPtr<AActor>> Required;
	TWeakObjectPtr<AActor> Spare;
	FVector SpareStart = FVector::ZeroVector;

	/** Fixture-owned truth: which required relics the hero has reached. */
	TSet<TWeakObjectPtr<AActor>> Contacted;

	TArray<FLeg> Legs;
	int32 ActiveLeg = -1;

	/** Continuous-guard latches. */
	bool bLampWasLit = false;
	bool bEverEscaped = false;
	bool bHeroEnteredExit = false;
};
