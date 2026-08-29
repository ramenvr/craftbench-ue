// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY, AUTHORING-ONLY. No runtime fixture calls this helper.
// It creates the deterministic editable Widget Blueprint scaffold and the
// task-local reference graphs without exposing editor-only types to the game
// module or requiring an interactive editor/Aura session.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FocusStackAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UFocusStackAssetAuthoring : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Creates and saves the three untouched, submission-shaped baseline assets. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool CreateBaselineAssets();

	/** Converts the saved baseline assets into the deterministic reference solution. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool BuildReferenceAssets();

	/** Independent readback used by the thin Python authoring driver. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool ValidateBaselineAssets();

	/** Independent readback used before reference harvest. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool ValidateReferenceAssets();
};
