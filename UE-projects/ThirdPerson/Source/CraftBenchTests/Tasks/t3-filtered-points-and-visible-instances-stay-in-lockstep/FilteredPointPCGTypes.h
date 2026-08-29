// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PCGSettings.h"
#include "FilteredPointPCGTypes.generated.h"

class UBoxComponent;
class UPCGComponent;
class UPCGGraphInterface;
class UStaticMesh;

/** One protected point fact. Candidate content never owns this oracle data. */
USTRUCT()
struct FFilteredPointFact
{
	GENERATED_BODY()

	UPROPERTY()
	int32 StableId = INDEX_NONE;

	UPROPERTY()
	float Density = 0.0f;

	UPROPERTY()
	bool bExcluded = false;

	UPROPERTY()
	FTransform Transform = FTransform::Identity;
};
/**
 * Verifier-owned graph execution host. It supplies the policy-dependent point
 * facts, actor bounds, mesh, seed, and live graph parameter without exposing a
 * candidate-authored mirror or construction-script substitute.
 */
UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API AFilteredPointPCGHost : public AActor
{
	GENERATED_BODY()

public:
	AFilteredPointPCGHost(const FObjectInitializer& ObjectInitializer);

	void ApplyPolicy(bool bUsePolicyB);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|FilteredPoints")
	void SetGraphAsset(UPCGGraphInterface* InGraph);

	UFUNCTION(BlueprintPure, Category = "CraftBench|FilteredPoints")
	UPCGComponent* GetPCGComponent() const { return PCGComponent; }

	const TArray<FFilteredPointFact>& GetPointFacts() const { return PointFacts; }
	float GetMinDensity() const { return MinDensity; }
	uint32 GetPolicySeed() const { return PolicySeed; }
	const FBox& GetProtectedFilterBounds() const { return ProtectedFilterBounds; }
	UStaticMesh* GetSpawnMesh() const { return SpawnMesh; }

private:
	UPROPERTY(VisibleAnywhere, Category = "CraftBench|FilteredPoints")
	TObjectPtr<UBoxComponent> GenerationBounds;

	UPROPERTY(VisibleAnywhere, Category = "CraftBench|FilteredPoints")
	TObjectPtr<class UStaticMeshComponent> SourceMarker;

	UPROPERTY(VisibleAnywhere, Category = "CraftBench|FilteredPoints")
	TObjectPtr<UPCGComponent> PCGComponent;

	UPROPERTY()
	TObjectPtr<UStaticMesh> SpawnMesh;

	UPROPERTY()
	TArray<FFilteredPointFact> PointFacts;

	FBox ProtectedFilterBounds = FBox(EForceInit::ForceInit);
	float MinDensity = 0.55f;
	uint32 PolicySeed = 173u;
};

/** Protected source node used by both the empty and solved graph assets. */
UCLASS(BlueprintType)
class CRAFTBENCHTESTS_API UFilteredPointSourceSettings : public UPCGSettings
{
	GENERATED_BODY()

protected:
	virtual TArray<FPCGPinProperties> InputPinProperties() const override;
	virtual TArray<FPCGPinProperties> OutputPinProperties() const override;
	virtual FPCGElementPtr CreateElement() const override;

#if WITH_EDITOR
	virtual FName GetDefaultNodeName() const override
	{
		return TEXT("CraftBenchFilteredPointSource");
	}
	virtual FText GetDefaultNodeTitle() const override
	{
		return FText::FromString(TEXT("Protected Filtered Point Source"));
	}
	virtual EPCGSettingsType GetType() const override
	{
		return EPCGSettingsType::InputOutput;
	}
#endif
};
