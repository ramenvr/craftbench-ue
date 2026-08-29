// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-screen-tint.
//
// The effect is graded against the character's MEASURED ground speed -- distance
// actually covered per frame -- as a fraction of the top speed IT CURRENTLY HAS. The
// fixture CHANGES that top speed between the two legs, which is the whole
// anti-hard-coding design: a submission that divides by a constant tracks perfectly
// on the first leg and is wrong by the ratio on the second.
//
// When the second leg does fail, the fixture works out what the effect WOULD have
// read under the first leg's top speed, and says so if that matches -- so the
// commonest wrong answer is diagnosed rather than merely failed.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "ScreenTintFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AScreenTintFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AScreenTintFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool ResolveStaging();

	float ReadFloat(const AActor* A, const TCHAR* Name, float Fallback) const;
	float ReadVignette() const;
	float ReadFringe() const;
	/** What the effect should read, given a fraction of top speed. */
	float Expected(double Fraction) const;
	/** Walks the character: still, half pace, flat out, still -- twice. */
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Tint;

	float RestVignette = 0.0f;
	float FullVignette = 0.9f;
	float SuppliedFringe = 0.6f;

	/** The top speed the character had when the run started, and the one it has now.
	 *  They differ from the second leg onward. */
	double FirstLegTopSpeed = 0.0;
	double TopSpeedNow = 0.0;
	int32 Leg = 0;

	FVector LastHeroAt = FVector::ZeroVector;
	/** Ground speed, smoothed: one hitching frame must not decide a verdict. */
	double SmoothedSpeed = 0.0;
	/** How long the smoothed fraction has held still, so the effect is never judged
	 *  during an acceleration ramp. */
	double StableSince = 0.0;
	/** The fraction the current stable window OPENED at. Compared against that,
	 *  not against the previous frame: under smooth acceleration the frame-to-
	 *  frame change is a thousandth, so a per-frame test calls the whole ramp
	 *  stable and judges an effect that is legitimately still easing. */
	double FractionAtWindowStart = 0.0;
	/** Whether each leg ever ran flat out with the effect at full. */
	bool bLegSawFull[2] = {false, false};
	bool bLegSawStill[2] = {false, false};
};
