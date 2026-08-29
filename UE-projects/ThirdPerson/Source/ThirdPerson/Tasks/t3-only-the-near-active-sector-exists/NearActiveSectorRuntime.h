// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NearActiveSectorRuntime.generated.h"

class UDataLayerAsset;
class UDataLayerManager;
class UStaticMeshComponent;
class UWorldPartitionStreamingSourceComponent;

/** Verifier-owned request facts consumed by the editable controller. */
UCLASS(BlueprintType)
class THIRDPERSON_API ANearActiveSectorRequest : public AActor
{
	GENERATED_BODY()

public:
	ANearActiveSectorRequest();

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	TObjectPtr<AActor> StreamingSourceActor;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	TObjectPtr<UDataLayerAsset> SelectedLayer;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	TArray<TObjectPtr<UDataLayerAsset>> CandidateLayers;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	FVector SelectedDestination = FVector::ZeroVector;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	FName RequestToken;
};

/** Exact placed source provider. Candidate code may move it but must not replace it. */
UCLASS()
class THIRDPERSON_API ANearActiveSectorStreamingSource : public AActor
{
	GENERATED_BODY()

public:
	ANearActiveSectorStreamingSource();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Near Active Sector")
	TObjectPtr<UWorldPartitionStreamingSourceComponent> StreamingSource;
};

/** Spatial marker stored in one protected runtime Data Layer/cell. */
UCLASS()
class THIRDPERSON_API ANearActiveSectorMarker : public AActor
{
	GENERATED_BODY()

public:
	ANearActiveSectorMarker();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Near Active Sector")
	TObjectPtr<UStaticMeshComponent> VisibleMarker;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	FName SectorId;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Near Active Sector")
	FName MarkerId;

	/** Verifier-observed engine lifecycle facts; not candidate telemetry. */
	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly,
		Category = "Near Active Sector")
	int32 BeginPlayEpoch = 0;

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly,
		Category = "Near Active Sector")
	int32 EndPlayEpoch = 0;
};

/**
 * The sole editable Blueprint surface. Its native default intentionally does
 * nothing; all World Partition/Data Layer behavior must be authored in the
 * submitted Blueprint event graph.
 */
UCLASS(Abstract, Blueprintable)
class THIRDPERSON_API ANearActiveSectorControllerBase : public AActor
{
	GENERATED_BODY()

public:
	ANearActiveSectorControllerBase();

	/** Narrow Blueprint access to this world's real Data Layer manager. */
	UFUNCTION(BlueprintPure, Category = "Near Active Sector")
	UDataLayerManager* GetSectorDataLayerManager() const;

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Near Active Sector")
	void ApplySectorRequest(ANearActiveSectorRequest* Request);
	virtual void ApplySectorRequest_Implementation(ANearActiveSectorRequest* Request);
};
