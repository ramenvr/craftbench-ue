// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "WalkableGroundAdmissionAuthoring.generated.h"

class UBlueprint;

/** Read/write admission-map setup plus read-only exact asset/map inspection. */
UCLASS()
class CRAFTBENCHTESTS_API UWalkableGroundAdmissionAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Pins the editor world's persistent navigation config to the admission-only
	 * nav system and strips authored nav-data actors. Returns one PASS/FAIL
	 * string so Unreal Python has no bool + FString& return-shape ambiguity.
	 */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|WalkableGround")
	static FString ConfigureAdmissionWorld(UObject* WorldContextObject);

	/** Cold/read-only identity check for the admission world. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|WalkableGround")
	static FString InspectAdmissionWorld(UObject* WorldContextObject);

	/** Cold/read-only identity check for the protected production world. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|WalkableGround")
	static FString InspectProductionWorld(UObject* WorldContextObject);

	/** Configure and save the supplied Blueprint as empty or correct. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|WalkableGround")
	static FString ConfigureDesignatedScoutBlueprint(
		UBlueprint* Blueprint, bool bWithInvoker,
		float GenerationRadius = 1600.0f,
		float RemovalRadius = 2200.0f);

	/** Fixed structural evidence for the future exact task Blueprint. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|WalkableGround")
	static FString InspectDesignatedScoutBlueprint(UBlueprint* Blueprint);

	/** Exact answer-free baseline shell inspection. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|WalkableGround")
	static FString InspectDesignatedScoutBlueprintShell(UBlueprint* Blueprint);
};
