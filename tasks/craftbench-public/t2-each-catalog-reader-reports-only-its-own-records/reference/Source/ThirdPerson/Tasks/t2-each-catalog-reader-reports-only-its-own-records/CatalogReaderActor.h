// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-each-catalog-reader-reports-only-its-own-records.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UObject/TopLevelAssetPath.h"
#include "CatalogReaderActor.generated.h"

UCLASS()
class THIRDPERSON_API ACatalogReaderActor : public AActor
{
	GENERATED_BODY()

public:
	ACatalogReaderActor();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Catalog")
	FName ReaderId = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Catalog")
	FTopLevelAssetPath ConfiguredAssetClass;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Catalog")
	FName ConfiguredPackagePath = NAME_None;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Catalog")
	int32 ReportedCount = INDEX_NONE;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Catalog")
	TArray<FName> ReportedPackageNames;

protected:
	virtual void BeginPlay() override;
};
