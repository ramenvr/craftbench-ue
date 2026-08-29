// Copyright CraftBench. All Rights Reserved.
//
// ACatalogReaderActor - pre-existing actor for task t2-each-catalog-reader-reports-only-its-own-records.
// The constructor stamps
// the common CatalogReader identity tag and exposes world-authored query facts
// plus observable report fields. No catalog query or report behavior is
// supplied. Agents may subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UObject/TopLevelAssetPath.h"
#include "CatalogReaderActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ACatalogReaderActor : public AActor
{
	GENERATED_BODY()

public:
	ACatalogReaderActor();

	/** Stable world identity used in this reader's exact report line. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Catalog")
	FName ReaderId = NAME_None;

	/** Exact metadata class configured for this placed reader. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Catalog")
	FTopLevelAssetPath ConfiguredAssetClass;

	/** Root package path configured for this placed reader. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Catalog")
	FName ConfiguredPackagePath = NAME_None;

	/** Exact metadata-only result count exposed after the report. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Catalog")
	int32 ReportedCount = INDEX_NONE;

	/** Exact sorted package identities exposed after the report. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Catalog")
	TArray<FName> ReportedPackageNames;

};
