// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Tasks/t3-only-the-near-active-sector-exists/NearActiveSectorRuntime.h"
#include "NearActiveSectorFunctionalTest.generated.h"

class UDataLayerAsset;
class UWorldPartitionStreamingSourceComponent;

/** Verifier-owned correct control used only in admission worlds. */
UCLASS()
class CRAFTBENCHTESTS_API ANearActiveSectorAdmissionController
	: public ANearActiveSectorControllerBase
{
	GENERATED_BODY()

public:
	virtual void ApplySectorRequest_Implementation(
		ANearActiveSectorRequest* Request) override;
};

UCLASS(Abstract)
class CRAFTBENCHTESTS_API ANearActiveSectorFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ANearActiveSectorFunctionalTestBase(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;
	virtual void StartTest() override;

	UPROPERTY(EditInstanceOnly, Category = "Near Active Sector")
	TObjectPtr<UDataLayerAsset> LayerA;

	UPROPERTY(EditInstanceOnly, Category = "Near Active Sector")
	TObjectPtr<UDataLayerAsset> LayerB;

	UPROPERTY(EditInstanceOnly, Category = "Near Active Sector")
	FVector SectorALocation = FVector::ZeroVector;

	UPROPERTY(EditInstanceOnly, Category = "Near Active Sector")
	FVector SectorBLocation = FVector::ZeroVector;

	UPROPERTY(EditInstanceOnly, Category = "Near Active Sector")
	float ExpectedSourceRadius = 3200.0f;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual bool ReverseOrder() const PURE_VIRTUAL(
		ANearActiveSectorFunctionalTestBase::ReverseOrder, return false;);
	virtual bool UsesAdmissionController() const PURE_VIRTUAL(
		ANearActiveSectorFunctionalTestBase::UsesAdmissionController, return false;);

private:
	bool ResolveStaging();
	bool RequireHarness(bool bCondition, const FString& Detail);
	void FailGate(const TCHAR* Gate, const FString& Detail);
	void Issue(UDataLayerAsset* SelectedLayer, const FVector& Destination,
		const FName Token);
	bool RequireSettled(const TCHAR* Stage) const;
	bool RequireInitialReset() const;
	bool RequireLayerStates(UDataLayerAsset* ActiveLayer,
		UDataLayerAsset* InactiveLayer, const TCHAR* Stage) const;
	TArray<ANearActiveSectorMarker*> LiveMarkers() const;
	bool RequireExactMarkers(FName SectorId, const TCHAR* Stage,
		TArray<TWeakObjectPtr<ANearActiveSectorMarker>>* Capture = nullptr) const;
	bool RequireNoMarkers(const TCHAR* Gate, const TCHAR* Stage) const;

	TWeakObjectPtr<ANearActiveSectorControllerBase> Controller;
	TWeakObjectPtr<ANearActiveSectorRequest> Request;
	TWeakObjectPtr<ANearActiveSectorStreamingSource> Source;
	TWeakObjectPtr<UWorldPartitionStreamingSourceComponent> SourceComponent;
	TArray<TWeakObjectPtr<ANearActiveSectorMarker>> RetiredFirstMarkers;
	TMap<FName, TWeakObjectPtr<ANearActiveSectorMarker>> RetiredFirstById;
	TMap<FName, int32> RetiredFirstBeginEpochs;
	UDataLayerAsset* FirstLayer = nullptr;
	UDataLayerAsset* SecondLayer = nullptr;
	FVector FirstLocation = FVector::ZeroVector;
	FVector SecondLocation = FVector::ZeroVector;
	FName FirstSector;
	FName SecondSector;
};

UCLASS()
class CRAFTBENCHTESTS_API ANearActiveSectorFunctionalTestA
	: public ANearActiveSectorFunctionalTestBase
{
	GENERATED_BODY()
protected:
	virtual bool ReverseOrder() const override { return false; }
	virtual bool UsesAdmissionController() const override { return false; }
};

UCLASS()
class CRAFTBENCHTESTS_API ANearActiveSectorFunctionalTestB
	: public ANearActiveSectorFunctionalTestBase
{
	GENERATED_BODY()
protected:
	virtual bool ReverseOrder() const override { return true; }
	virtual bool UsesAdmissionController() const override { return false; }
};

UCLASS()
class CRAFTBENCHTESTS_API ANearActiveSectorAdmissionFunctionalTestA
	: public ANearActiveSectorFunctionalTestBase
{
	GENERATED_BODY()
protected:
	virtual bool ReverseOrder() const override { return false; }
	virtual bool UsesAdmissionController() const override { return true; }
};

UCLASS()
class CRAFTBENCHTESTS_API ANearActiveSectorAdmissionFunctionalTestB
	: public ANearActiveSectorFunctionalTestBase
{
	GENERATED_BODY()
protected:
	virtual bool ReverseOrder() const override { return true; }
	virtual bool UsesAdmissionController() const override { return true; }
};
