// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/DistrictStreamingRuntime.h"
#include "DistrictStreamingFunctionalTest.generated.h"

class ULevel;
class ULevelStreaming;
class ULevelStreamingDynamic;

/** Verifier-owned correct control used only by admission fixtures. */
UCLASS()
class CRAFTBENCHTESTS_API ADistrictStreamingAdmissionLoader
	: public ADistrictStreamLoaderBase
{
	GENERATED_BODY()

public:
	virtual void LoadRequestedDistrict_Implementation(
		ADistrictStreamRequest* Request) override;
	virtual void UnloadRequestedDistrict_Implementation() override;
};

/** Shared two-world, load/unload/reload driver. */
UCLASS(Abstract)
class CRAFTBENCHTESTS_API ADistrictStreamingFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ADistrictStreamingFunctionalTestBase(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual FName ExpectedRequestedDistrictId() const PURE_VIRTUAL(
		ADistrictStreamingFunctionalTestBase::ExpectedRequestedDistrictId,
		return NAME_None;);
	virtual bool UsesAdmissionLoader() const PURE_VIRTUAL(
		ADistrictStreamingFunctionalTestBase::UsesAdmissionLoader,
		return false;);

private:
	bool ResolveStaging();
	bool RemoveExistingVerifierStreams();
	bool FailGate(const TCHAR* Gate, const FString& Detail);
	bool RequireHarness(bool bCondition, const FString& Detail);
	TArray<ULevelStreaming*> FindStreamsFor(const TSoftObjectPtr<UWorld>& WorldAsset,
		bool bLoadedOnly) const;
	TArray<ADistrictSectionMarker*> FindMarkers(FName DistrictId) const;
	bool RequireControlUnchanged(const TCHAR* Stage);
	bool RequireRequestedLoaded(const TCHAR* Stage, bool bCaptureFirstIdentity);
	bool RequireRequestedAbsent(const TCHAR* Stage);

	TWeakObjectPtr<ADistrictStreamLoaderBase> Loader;
	TWeakObjectPtr<ADistrictStreamRequest> Request;
	TWeakObjectPtr<ULevelStreamingDynamic> ControlStream;
	TWeakObjectPtr<ADistrictSectionMarker> ControlMarker;
	TWeakObjectPtr<ADistrictSectionMarker> FirstRequestedMarker;
	int32 ControlMarkerUniqueId = INDEX_NONE;
	int32 FirstRequestedMarkerUniqueId = INDEX_NONE;
};

UCLASS()
class CRAFTBENCHTESTS_API ADistrictStreamingFunctionalTestAlpha
	: public ADistrictStreamingFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual FName ExpectedRequestedDistrictId() const override
	{
		return TEXT("Alpha");
	}
	virtual bool UsesAdmissionLoader() const override { return false; }
};

UCLASS()
class CRAFTBENCHTESTS_API ADistrictStreamingFunctionalTestBeta
	: public ADistrictStreamingFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual FName ExpectedRequestedDistrictId() const override
	{
		return TEXT("Beta");
	}
	virtual bool UsesAdmissionLoader() const override { return false; }
};

UCLASS()
class CRAFTBENCHTESTS_API ADistrictStreamingAdmissionFunctionalTestAlpha
	: public ADistrictStreamingFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual FName ExpectedRequestedDistrictId() const override
	{
		return TEXT("Alpha");
	}
	virtual bool UsesAdmissionLoader() const override { return true; }
};
UCLASS()
class CRAFTBENCHTESTS_API ADistrictStreamingAdmissionFunctionalTestBeta
	: public ADistrictStreamingFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual FName ExpectedRequestedDistrictId() const override
	{
		return TEXT("Beta");
	}
	virtual bool UsesAdmissionLoader() const override { return true; }
};
