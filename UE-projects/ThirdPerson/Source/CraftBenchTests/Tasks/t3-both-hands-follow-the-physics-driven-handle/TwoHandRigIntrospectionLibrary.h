// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - read-only L2I and cold-readback surface.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "TwoHandRigIntrospectionLibrary.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UTwoHandRigIntrospectionLibrary
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Never compiles, repairs, or saves either asset. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|TwoHandPhysics")
	static FString InspectAssets(
		const UObject* ControlRigBlueprintObject,
		const UObject* AnimBlueprintObject,
		bool bExpectComplete,
		bool bAdmission);
};
