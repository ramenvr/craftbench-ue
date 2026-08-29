// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT (agents). Maintainer-authored L3 fixture.
//
// ARenderProbeFunctionalTest — the L3 render-context capture probe. Runs in a real
// PIE world with REAL RHI, lets the scene render for a few PIE frames (the engine
// ticks every frame — no manual tick), then captures the PIE game viewport via
// stock-UE FScreenshotRequest (NOT Aura — anti-circularity). This is the path that
// gives a screenshot with actual RENDERED CONTENT, which a one-shot editor-Python
// capture cannot (no frame advances). The screenshot is advisory evidence for the
// R2 visual track; the structural assertion ("screenshot written") is the
// deterministic gate. See docs/pie-verification-playbook.md (the PIE fixture-pattern recipes).
#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "RenderProbeFunctionalTest.generated.h"

UCLASS()
class ARenderProbeFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	FString ScreenshotPath() const;
};
