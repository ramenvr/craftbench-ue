// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DistrictStreamingRuntime.generated.h"

class ULevelStreamingDynamic;
class UStaticMeshComponent;
class UWorld;

/** Verifier-owned world request; the editable loader reads, but never mutates, it. */
UCLASS(BlueprintType)
class THIRDPERSON_API ADistrictStreamRequest : public AActor
{
	GENERATED_BODY()

public:
	ADistrictStreamRequest();

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "District Streaming")
	TSoftObjectPtr<UWorld> RequestedDistrict;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "District Streaming")
	TSoftObjectPtr<UWorld> UnrelatedControlDistrict;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "District Streaming")
	FName RequestedDistrictId;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "District Streaming")
	FName ControlDistrictId;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "District Streaming")
	FName InstanceName;
};

/**
 * Editable Blueprint surface. The baseline implementations intentionally do
 * nothing; a correct graph owns the real ULevelStreamingDynamic lifecycle.
 */
UCLASS(Abstract, Blueprintable)
class THIRDPERSON_API ADistrictStreamLoaderBase : public AActor
{
	GENERATED_BODY()

public:
	ADistrictStreamLoaderBase();

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "District Streaming")
	void LoadRequestedDistrict(ADistrictStreamRequest* Request);
	virtual void LoadRequestedDistrict_Implementation(ADistrictStreamRequest* Request);

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "District Streaming")
	void UnloadRequestedDistrict();
	virtual void UnloadRequestedDistrict_Implementation();

	UFUNCTION(BlueprintPure, Category = "District Streaming")
	ULevelStreamingDynamic* GetActiveStreamingLevel() const { return ActiveStreamingLevel; }

protected:
	UPROPERTY(BlueprintReadWrite, Transient, Category = "District Streaming")
	TObjectPtr<ULevelStreamingDynamic> ActiveStreamingLevel;
};

/** Exact marker authored into each verifier-owned streamed section. */
UCLASS()
class THIRDPERSON_API ADistrictSectionMarker : public AActor
{
	GENERATED_BODY()

public:
	ADistrictSectionMarker();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "District Streaming")
	TObjectPtr<UStaticMeshComponent> VisibleMarker;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "District Streaming")
	FName DistrictId;
};
