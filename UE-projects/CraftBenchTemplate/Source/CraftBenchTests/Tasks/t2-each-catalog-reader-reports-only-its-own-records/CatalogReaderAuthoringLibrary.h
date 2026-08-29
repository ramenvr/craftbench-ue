// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// Authoring-only helpers for the protected catalog. Both functions return a
// line beginning with OK or ERROR so task-local Python can fail closed without
// loading any protected record during independent cold readback.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CatalogReaderAuthoringLibrary.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UCatalogReaderAuthoringLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Creates every protected catalog asset, but only if all outputs are absent. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString CreateProtectedCatalog();

	/** Metadata-only exact class/path/cardinality/residency readback. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectProtectedCatalog();
};
