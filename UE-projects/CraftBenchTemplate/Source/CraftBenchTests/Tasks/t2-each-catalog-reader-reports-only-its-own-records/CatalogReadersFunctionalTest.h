// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ACatalogReadersFunctionalTest - L2 verifier for task
// t2-each-catalog-reader-reports-only-its-own-records. Before placed actors
// receive BeginPlay, this fixture installs two distinct world query configs,
// snapshots the protected catalog through Asset Registry metadata, installs a
// protected report-publication listener, and arms an asset-load listener. Normal PIE ticks then
// carry the test through three world-clock checkpoints.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "HAL/CriticalSection.h"
#include "UObject/TopLevelAssetPath.h"
#include "CatalogReadersFunctionalTest.generated.h"

class ACatalogReaderActor;
struct FActorsInitializedParams;

struct FCatalogObservedPublication
{
	TWeakObjectPtr<ACatalogReaderActor> Reader;
	FName ReaderId;
	int32 Count = INDEX_NONE;
	TArray<FName> PackageNames;
	uint64 Frame = 0;
};

UCLASS()
class CRAFTBENCHTESTS_API ACatalogReadersFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACatalogReadersFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FReaderExpectation
	{
		FName ActorTag;
		FName ReaderId;
		FTopLevelAssetPath ClassPath;
		FName PackagePath;
		TArray<FName> ExpectedPackages;
		TWeakObjectPtr<ACatalogReaderActor> Actor;
	};

	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void OnProtectedAssetLoaded(UObject* LoadedAsset);
	void OnReaderPublished(ACatalogReaderActor* Reader, uint64 Frame);
	void RemoveDelegates();

	bool BuildProtectedCatalogOracle();
	bool ConfigureReader(FReaderExpectation& Expectation);
	bool CheckExactReaderState(FString& OutDetail) const;
	bool CheckCatalogStayedUnloaded(FString& OutDetail) const;
	bool CheckOneBeginPlayReportPerReader(FString& OutDetail) const;
	TArray<FCatalogObservedPublication> SnapshotPublications() const;

	TArray<FReaderExpectation> Readers;
	TArray<FName> AllCatalogPackages;
	TSet<FName> PackagesObservedLoading;
	mutable FCriticalSection LoadEventMutex;

	TArray<FCatalogObservedPublication> Publications;
	mutable FCriticalSection PublicationMutex;
	FDelegateHandle WorldInitHandle;
	FDelegateHandle AssetLoadedHandle;
	FDelegateHandle ReportPublishedHandle;
	bool bBridgeInstalled = false;
	bool bWorldPrepared = false;
	uint64 WorldInitFrame = 0;

	FString HarnessError;
	FString GradedSetupFailure;
};
