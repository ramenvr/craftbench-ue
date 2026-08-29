// Copyright CraftBench. All Rights Reserved.
//
// Supplied record types for task
// t2-each-catalog-reader-reports-only-its-own-records. Instances of these
// types are verifier-owned catalog content. The requested behavior belongs in
// CatalogReaderActor.{h,cpp}; these declarations only give the catalog two
// distinct metadata classes to query.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "CatalogRecordTypes.generated.h"

class ACatalogReaderActor;

/**
 * Protected publication seam for the catalog-reader task.
 *
 * The candidate may announce that its public result is ready, but it cannot
 * supply the payload or timestamp: verifier listeners snapshot the source
 * actor and the bridge supplies the engine frame.  This keeps user-facing log
 * text entirely outside the grading trust boundary.
 */
DECLARE_MULTICAST_DELEGATE_TwoParams(
	FOnCatalogReaderPublished,
	ACatalogReaderActor*,
	uint64);

class CRAFTBENCHTEMPLATE_API FCatalogReaderReportBridge
{
public:
	static FDelegateHandle AddListener(
		const FOnCatalogReaderPublished::FDelegate& Listener);
	static void RemoveListener(FDelegateHandle Handle);
	static void Publish(ACatalogReaderActor* Reader);

private:
	static FOnCatalogReaderPublished Published;
};

UCLASS(BlueprintType)
class CRAFTBENCHTEMPLATE_API UCatalogAlphaRecord : public UDataAsset
{
	GENERATED_BODY()
};

UCLASS(BlueprintType)
class CRAFTBENCHTEMPLATE_API UCatalogBetaRecord : public UDataAsset
{
	GENERATED_BODY()
};
