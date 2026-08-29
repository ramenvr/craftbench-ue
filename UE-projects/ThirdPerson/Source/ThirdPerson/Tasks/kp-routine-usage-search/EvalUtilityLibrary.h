// Utility routines for task kp-routine-usage-search.
//
// Small project-wide helper library: a stable integer checksum, a display
// label formatter, and a score clamp. Each routine is pure computation with
// no side effects.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EvalUtilityLibrary.generated.h"

UCLASS()
class THIRDPERSON_API UEvalUtilityLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	// Returns a stable checksum of the given value; equal inputs always
	// produce equal outputs.
	UFUNCTION(BlueprintCallable, Category = "Utility")
	static int32 ComputeChecksum(int32 Value);

	// Returns the given label wrapped for display, e.g. "Ready" -> "[Ready]".
	UFUNCTION(BlueprintCallable, Category = "Utility")
	static FString FormatLabel(const FString& Label);

	// Returns the given score clamped to the range [0, 100].
	UFUNCTION(BlueprintCallable, Category = "Utility")
	static float ClampScore(float Score);
};
