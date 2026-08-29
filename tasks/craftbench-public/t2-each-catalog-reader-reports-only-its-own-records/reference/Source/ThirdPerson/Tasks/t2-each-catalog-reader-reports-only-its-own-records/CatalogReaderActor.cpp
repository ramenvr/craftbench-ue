// Copyright CraftBench. All Rights Reserved.
//
// Reference solution: one actor-scoped metadata query and one exact report at
// BeginPlay. FAssetData package identities are used without resolving assets.

#include "CatalogReaderActor.h"
#include "CatalogRecordTypes.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/SceneComponent.h"
#include "Modules/ModuleManager.h"

ACatalogReaderActor::ACatalogReaderActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName(TEXT("CatalogReader")));

	USceneComponent* SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
}

void ACatalogReaderActor::BeginPlay()
{
	Super::BeginPlay();

	ReportedPackageNames.Reset();

	FARFilter Filter;
	Filter.PackagePaths.Add(ConfiguredPackagePath);
	Filter.ClassPaths.Add(ConfiguredAssetClass);
	Filter.bRecursivePaths = true;
	Filter.bRecursiveClasses = false;
	Filter.bIncludeOnlyOnDiskAssets = true;

	TArray<FAssetData> Assets;
	IAssetRegistry& Registry =
		FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	Registry.GetAssets(Filter, Assets);

	for (const FAssetData& Asset : Assets)
	{
		ReportedPackageNames.Add(Asset.PackageName);
	}
	ReportedPackageNames.Sort([](const FName& Left, const FName& Right)
	{
		return Left.LexicalLess(Right);
	});
	ReportedCount = ReportedPackageNames.Num();
	FCatalogReaderReportBridge::Publish(this);
}
