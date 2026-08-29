// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "GuardVisibleAimVerifierLibrary.generated.h"

class UAnimBlueprint;

UCLASS()
class CRAFTBENCHTESTS_API UGuardVisibleAimVerifierLibrary
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Guard Aim")
	static FString InspectAnimBlueprint(
		const UAnimBlueprint* AnimBlueprint, bool bExpectAimOverlay);
};
