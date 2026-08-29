// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - maintainer authoring/readback helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "TwoHandRigAssetAuthoring.generated.h"

class ATwoHandPhysicsHandle;
class ATwoHandRigCharacter;
class UAnimBlueprint;

UCLASS()
class CRAFTBENCHTESTS_API UTwoHandRigAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|TwoHandPhysics")
	static FString BuildControlRig(UObject* ControlRigBlueprintObject, bool bComplete);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|TwoHandPhysics")
	static FString BuildAnimGraph(
		UAnimBlueprint* AnimBlueprint,
		UObject* ControlRigBlueprintObject,
		bool bComplete);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|TwoHandPhysics")
	static FString ConfigureScenario(
		ATwoHandPhysicsHandle* Handle,
		ATwoHandRigCharacter* Subject,
		UAnimBlueprint* AnimBlueprint);

	/** Read-only authored-map contract. Does not run either fixture. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|TwoHandPhysics")
	static FString InspectAuthoredWorld(UObject* WorldContextObject, bool bAdmission);
};
