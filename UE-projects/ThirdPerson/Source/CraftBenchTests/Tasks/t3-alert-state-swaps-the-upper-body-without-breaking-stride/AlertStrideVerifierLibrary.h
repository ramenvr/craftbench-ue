// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY structural readback.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AlertStrideVerifierLibrary.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UAlertStrideVerifierLibrary
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Alert Stride")
	static FString InspectAssetSet(
		const FString& RootPackage, const FString& InterfacePackage,
		bool bExpectComplete);
};
