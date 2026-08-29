// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#include "CatalogReaderAuthoringLibrary.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "Tasks/t2-each-catalog-reader-reports-only-its-own-records/CatalogRecordTypes.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	static const TCHAR* CatalogRoot =
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog");

	enum class ECatalogRecordKind : uint8
	{
		Alpha,
		Beta
	};

	struct FCatalogAssetSpec
	{
		const TCHAR* PackageName;
		ECatalogRecordKind Kind;
	};

	static const FCatalogAssetSpec CatalogSpecs[] =
	{
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Cedar"), ECatalogRecordKind::Alpha },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Lapis"), ECatalogRecordKind::Alpha },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Quartz"), ECatalogRecordKind::Alpha },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Beta_WrongType"), ECatalogRecordKind::Beta },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Beta_Amber"), ECatalogRecordKind::Beta },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Beta_Violet"), ECatalogRecordKind::Beta },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Alpha_WrongType"), ECatalogRecordKind::Alpha },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/Outside/DA_Alpha_Outside"), ECatalogRecordKind::Alpha },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/Outside/DA_Beta_Outside"), ECatalogRecordKind::Beta },
	};

	UClass* ClassForKind(const ECatalogRecordKind Kind)
	{
		return Kind == ECatalogRecordKind::Alpha
			? UCatalogAlphaRecord::StaticClass()
			: UCatalogBetaRecord::StaticClass();
	}

	FString AssetNameForPackage(const FString& PackageName)
	{
		return FPackageName::GetShortName(PackageName);
	}

	bool IsCatalogPackageResident(const FString& PackageName)
	{
		return FindPackage(nullptr, *PackageName) != nullptr;
	}

	FString JoinNames(TArray<FString> Names)
	{
		Names.Sort();
		return FString::Join(Names, TEXT("|"));
	}
}

FString UCatalogReaderAuthoringLibrary::CreateProtectedCatalog()
{
	for (const FCatalogAssetSpec& Spec : CatalogSpecs)
	{
		if (FPackageName::DoesPackageExist(FString(Spec.PackageName)))
		{
			return FString::Printf(
				TEXT("ERROR refusing to overwrite existing protected package %s"),
				Spec.PackageName);
		}
	}

	TArray<FString> Created;
	for (const FCatalogAssetSpec& Spec : CatalogSpecs)
	{
		const FString PackageName(Spec.PackageName);
		const FString AssetName = AssetNameForPackage(PackageName);
		UPackage* Package = CreatePackage(*PackageName);
		if (Package == nullptr)
		{
			return FString::Printf(TEXT("ERROR CreatePackage failed for %s"), *PackageName);
		}

		UObject* Asset = NewObject<UObject>(
			Package,
			ClassForKind(Spec.Kind),
			FName(*AssetName),
			RF_Public | RF_Standalone | RF_Transactional);
		if (Asset == nullptr)
		{
			return FString::Printf(TEXT("ERROR NewObject failed for %s"), *PackageName);
		}

		FAssetRegistryModule::AssetCreated(Asset);
		Package->MarkPackageDirty();

		const FString Filename = FPackageName::LongPackageNameToFilename(
			PackageName,
			FPackageName::GetAssetPackageExtension());
		IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true);

		FSavePackageArgs SaveArgs;
		SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
		SaveArgs.SaveFlags = SAVE_NoError;
		if (!UPackage::SavePackage(Package, Asset, *Filename, SaveArgs))
		{
			return FString::Printf(TEXT("ERROR SavePackage failed for %s"), *PackageName);
		}
		Created.Add(PackageName);
	}

	const int32 CreatedCount = Created.Num();
	return FString::Printf(
		TEXT("OK CATALOG-AUTHOR SAVED count=%d packages=%s"),
		CreatedCount,
		*JoinNames(MoveTemp(Created)));
}

FString UCatalogReaderAuthoringLibrary::InspectProtectedCatalog()
{
	IAssetRegistry& Registry =
		FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	Registry.ScanPathsSynchronous({ FString(CatalogRoot) }, true, false);

	FARFilter Filter;
	Filter.PackagePaths.Add(FName(CatalogRoot));
	Filter.bRecursivePaths = true;
	Filter.bIncludeOnlyOnDiskAssets = true;

	TArray<FAssetData> Found;
	if (!Registry.GetAssets(Filter, Found))
	{
		return TEXT("ERROR AssetRegistry GetAssets returned false");
	}

	TMap<FName, FTopLevelAssetPath> Expected;
	for (const FCatalogAssetSpec& Spec : CatalogSpecs)
	{
		Expected.Add(FName(Spec.PackageName), ClassForKind(Spec.Kind)->GetClassPathName());
	}
	if (Found.Num() != Expected.Num())
	{
		return FString::Printf(
			TEXT("ERROR catalog cardinality expected=%d found=%d"),
			Expected.Num(),
			Found.Num());
	}

	TArray<FString> Observed;
	for (const FAssetData& Data : Found)
	{
		const FTopLevelAssetPath* ExpectedClass = Expected.Find(Data.PackageName);
		if (ExpectedClass == nullptr)
		{
			return FString::Printf(
				TEXT("ERROR unexpected catalog package %s"),
				*Data.PackageName.ToString());
		}
		if (Data.AssetClassPath != *ExpectedClass)
		{
			return FString::Printf(
				TEXT("ERROR class mismatch package=%s expected=%s found=%s"),
				*Data.PackageName.ToString(),
				*ExpectedClass->ToString(),
				*Data.AssetClassPath.ToString());
		}
		if (Data.IsRedirector())
		{
			return FString::Printf(
				TEXT("ERROR redirector is not a catalog record %s"),
				*Data.PackageName.ToString());
		}
		if (IsCatalogPackageResident(Data.PackageName.ToString()))
		{
			return FString::Printf(
				TEXT("ERROR protected package is resident during cold readback %s"),
				*Data.PackageName.ToString());
		}
		Observed.Add(FString::Printf(
			TEXT("%s:%s"),
			*Data.PackageName.ToString(),
			*Data.AssetClassPath.ToString()));
	}

	const int32 ObservedCount = Observed.Num();
	return FString::Printf(
		TEXT("OK CATALOG-READBACK count=%d unloaded=%d facts=%s"),
		ObservedCount,
		ObservedCount,
		*JoinNames(MoveTemp(Observed)));
}
