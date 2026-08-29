// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "UObject/SoftObjectPath.h"
#include "EpochAssetWorldSubsystem.generated.h"

class AEpochAssetDisplay;
struct FStreamableHandle;

/** Editable world-scoped async request surface supplied to the task agent. */
UCLASS()
class THIRDPERSON_API UEpochAssetWorldSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Epoch")
	void BeginEpochRequest(const FSoftObjectPath& RecordPath,
		AEpochAssetDisplay* Destination, bool bStartStalled);

	UFUNCTION(BlueprintPure, Category = "CraftBench|Epoch")
	bool HasActiveEpochRequest() const;

private:
	void RetireActiveRequest();

	uint64 ActiveEpoch = 0;
	TWeakObjectPtr<UWorld> BoundWorld;
	TWeakObjectPtr<AEpochAssetDisplay> BoundDestination;
	TSharedPtr<FStreamableHandle> ActiveHandle;
};
