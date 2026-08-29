// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
//
// PIE-native implementation. The engine owns BeginPlay and every world tick;
// this fixture never calls World->Tick, Actor->Tick, or DispatchBeginPlay.

#include "CatalogReadersFunctionalTest.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "CoreGlobals.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/ScopeLock.h"
#include "Modules/ModuleManager.h"
#include "Tasks/t2-each-catalog-reader-reports-only-its-own-records/CatalogReaderActor.h"
#include "Tasks/t2-each-catalog-reader-reports-only-its-own-records/CatalogRecordTypes.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	static const FName ReaderATag(TEXT("CatalogReader.A"));
	static const FName ReaderBTag(TEXT("CatalogReader.B"));
	static const FName ReaderAId(TEXT("NorthArchive"));
	static const FName ReaderBId(TEXT("SouthArchive"));
	static const FName ShelfAPath(
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA"));
	static const FName ShelfBPath(
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB"));
	static const TCHAR* CatalogRoot =
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog");
	static const TCHAR* ExpectedAlphaPackages[] =
	{
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Cedar"),
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Lapis"),
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Quartz"),
	};

	static const TCHAR* ExpectedBetaPackages[] =
	{
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Beta_Amber"),
		TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Beta_Violet"),
	};

	struct FPinnedCatalogAsset
	{
		const TCHAR* PackageName;
		bool bAlpha;
	};

	static const FPinnedCatalogAsset PinnedCatalog[] =
	{
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Cedar"), true },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Lapis"), true },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Alpha_Quartz"), true },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfA/DA_Beta_WrongType"), false },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Beta_Amber"), false },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Beta_Violet"), false },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/ShelfB/DA_Alpha_WrongType"), true },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/Outside/DA_Alpha_Outside"), true },
		{ TEXT("/Game/Maps/t2-each-catalog-reader-reports-only-its-own-records/Catalog/Outside/DA_Beta_Outside"), false },
	};

	TArray<FName> MakeNames(const TCHAR* const* Values, const int32 Count)
	{
		TArray<FName> Result;
		Result.Reserve(Count);
		for (int32 Index = 0; Index < Count; ++Index)
		{
			Result.Add(FName(Values[Index]));
		}
		Result.Sort([](const FName& Left, const FName& Right)
		{
			return Left.LexicalLess(Right);
		});
		return Result;
	}
}

ACatalogReadersFunctionalTest::ACatalogReadersFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this,
		&ACatalogReadersFunctionalTest::OnWorldActorsInitialized);
	AssetLoadedHandle = FCoreUObjectDelegates::OnAssetLoaded.AddUObject(
		this,
		&ACatalogReadersFunctionalTest::OnProtectedAssetLoaded);
	ReportPublishedHandle = FCatalogReaderReportBridge::AddListener(
		FOnCatalogReaderPublished::FDelegate::CreateUObject(
			this,
			&ACatalogReadersFunctionalTest::OnReaderPublished));
	bBridgeInstalled = ReportPublishedHandle.IsValid();
}

void ACatalogReadersFunctionalTest::OnWorldActorsInitialized(
	const FActorsInitializedParams& Params)
{
	if (bWorldPrepared || Params.World != GetWorld())
	{
		return;
	}
	bWorldPrepared = true;
	WorldInitFrame = GFrameCounter;

	AllCatalogPackages.Reset();
	for (const FPinnedCatalogAsset& Pin : PinnedCatalog)
	{
		AllCatalogPackages.Add(FName(Pin.PackageName));
	}

	Readers.Reset();
	FReaderExpectation& ReaderA = Readers.AddDefaulted_GetRef();
	ReaderA.ActorTag = ReaderATag;
	ReaderA.ReaderId = ReaderAId;
	ReaderA.ClassPath = UCatalogAlphaRecord::StaticClass()->GetClassPathName();
	ReaderA.PackagePath = ShelfAPath;
	ReaderA.ExpectedPackages = MakeNames(
		ExpectedAlphaPackages,
		UE_ARRAY_COUNT(ExpectedAlphaPackages));

	FReaderExpectation& ReaderB = Readers.AddDefaulted_GetRef();
	ReaderB.ActorTag = ReaderBTag;
	ReaderB.ReaderId = ReaderBId;
	ReaderB.ClassPath = UCatalogBetaRecord::StaticClass()->GetClassPathName();
	ReaderB.PackagePath = ShelfBPath;
	ReaderB.ExpectedPackages = MakeNames(
		ExpectedBetaPackages,
		UE_ARRAY_COUNT(ExpectedBetaPackages));

	if (!BuildProtectedCatalogOracle())
	{
		return;
	}

	for (FReaderExpectation& Reader : Readers)
	{
		if (!ConfigureReader(Reader))
		{
			return;
		}
	}

}

bool ACatalogReadersFunctionalTest::BuildProtectedCatalogOracle()
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
		HarnessError = TEXT("protected Asset Registry query returned false");
		return false;
	}
	if (Found.Num() != UE_ARRAY_COUNT(PinnedCatalog))
	{
		HarnessError = FString::Printf(
			TEXT("protected catalog expected %d records; found %d"),
			UE_ARRAY_COUNT(PinnedCatalog),
			Found.Num());
		return false;
	}

	TMap<FName, FTopLevelAssetPath> Expected;
	for (const FPinnedCatalogAsset& Pin : PinnedCatalog)
	{
		Expected.Add(
			FName(Pin.PackageName),
			(Pin.bAlpha ? UCatalogAlphaRecord::StaticClass() : UCatalogBetaRecord::StaticClass())
				->GetClassPathName());
	}

	for (const FAssetData& Data : Found)
	{
		const FTopLevelAssetPath* ExpectedClass = Expected.Find(Data.PackageName);
		if (ExpectedClass == nullptr || Data.AssetClassPath != *ExpectedClass || Data.IsRedirector())
		{
			HarnessError = FString::Printf(
				TEXT("protected catalog identity/class mismatch for %s"),
				*Data.PackageName.ToString());
			return false;
		}
	}

	for (const FName PackageName : AllCatalogPackages)
	{
		if (FindPackage(nullptr, *PackageName.ToString()) != nullptr)
		{
			HarnessError = FString::Printf(
				TEXT("protected package was resident before reader BeginPlay: %s"),
				*PackageName.ToString());
			return false;
		}
	}
	return true;
}

bool ACatalogReadersFunctionalTest::ConfigureReader(FReaderExpectation& Expectation)
{
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), Expectation.ActorTag, Found);
	if (Found.Num() != 1)
	{
		GradedSetupFailure = FString::Printf(
			TEXT("tag %s expected one placed reader; found %d"),
			*Expectation.ActorTag.ToString(),
			Found.Num());
		return false;
	}

	ACatalogReaderActor* Reader = Cast<ACatalogReaderActor>(Found[0]);
	if (Reader == nullptr)
	{
		GradedSetupFailure = FString::Printf(
			TEXT("tag %s did not resolve to the supplied reader contract"),
			*Expectation.ActorTag.ToString());
		return false;
	}

	Expectation.Actor = Reader;
	Reader->ReaderId = Expectation.ReaderId;
	Reader->ConfiguredAssetClass = Expectation.ClassPath;
	Reader->ConfiguredPackagePath = Expectation.PackagePath;
	Reader->ReportedCount = INDEX_NONE;
	Reader->ReportedPackageNames.Reset();
	return true;
}

void ACatalogReadersFunctionalTest::OnProtectedAssetLoaded(UObject* LoadedAsset)
{
	if (LoadedAsset == nullptr)
	{
		return;
	}
	UPackage* Package = LoadedAsset->GetOutermost();
	if (Package == nullptr)
	{
		return;
	}
	const FName PackageName = Package->GetFName();
	if (!AllCatalogPackages.Contains(PackageName))
	{
		return;
	}
	FScopeLock Lock(&LoadEventMutex);
	PackagesObservedLoading.Add(PackageName);
}

void ACatalogReadersFunctionalTest::OnReaderPublished(
	ACatalogReaderActor* Reader,
	const uint64 Frame)
{
	if (Reader == nullptr || Reader->GetWorld() != GetWorld())
	{
		return;
	}

	FCatalogObservedPublication Observed;
	Observed.Reader = Reader;
	Observed.ReaderId = Reader->ReaderId;
	Observed.Count = Reader->ReportedCount;
	Observed.PackageNames = Reader->ReportedPackageNames;
	Observed.Frame = Frame;

	FScopeLock Lock(&PublicationMutex);
	Publications.Add(MoveTemp(Observed));
}

TArray<FCatalogObservedPublication>
ACatalogReadersFunctionalTest::SnapshotPublications() const
{
	FScopeLock Lock(&PublicationMutex);
	return Publications;
}

void ACatalogReadersFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (!bWorldPrepared)
	{
		FinishTest(
			EFunctionalTestResult::Error,
			TEXT("HARNESS: pre-BeginPlay world callback did not run"));
		return;
	}
	if (!HarnessError.IsEmpty())
	{
		FinishTest(
			EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS: %s"), *HarnessError));
		return;
	}
	if (!GradedSetupFailure.IsEmpty())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("CR-0 reader_world_configuration: %s"),
				*GradedSetupFailure));
		return;
	}
	if (!bBridgeInstalled)
	{
		FinishTest(
			EFunctionalTestResult::Error,
			TEXT("HARNESS: protected report bridge was not installed before BeginPlay"));
		return;
	}

	SetCheckpointSchedule({ 0.20, 0.80, 1.20 });
}

bool ACatalogReadersFunctionalTest::CheckExactReaderState(FString& OutDetail) const
{
	for (const FReaderExpectation& Expected : Readers)
	{
		const ACatalogReaderActor* Reader = Expected.Actor.Get();
		if (Reader == nullptr)
		{
			OutDetail = FString::Printf(
				TEXT("reader %s no longer exists"),
				*Expected.ReaderId.ToString());
			return false;
		}
		if (Reader->ReportedCount != Expected.ExpectedPackages.Num())
		{
			OutDetail = FString::Printf(
				TEXT("reader %s count expected=%d found=%d"),
				*Expected.ReaderId.ToString(),
				Expected.ExpectedPackages.Num(),
				Reader->ReportedCount);
			return false;
		}
		if (Reader->ReportedPackageNames != Expected.ExpectedPackages)
		{
			TArray<FString> Found;
			for (const FName PackageName : Reader->ReportedPackageNames)
			{
				Found.Add(PackageName.ToString());
			}
			OutDetail = FString::Printf(
				TEXT("reader %s package identities/order mismatch found=%s"),
				*Expected.ReaderId.ToString(),
				*FString::Join(Found, TEXT("|")));
			return false;
		}
	}
	return true;
}

bool ACatalogReadersFunctionalTest::CheckCatalogStayedUnloaded(FString& OutDetail) const
{
	{
		FScopeLock Lock(&LoadEventMutex);
		if (PackagesObservedLoading.Num() > 0)
		{
			TArray<FString> Loaded;
			for (const FName PackageName : PackagesObservedLoading)
			{
				Loaded.Add(PackageName.ToString());
			}
			Loaded.Sort();
			OutDetail = FString::Printf(
				TEXT("asset-load callback observed %s"),
				*FString::Join(Loaded, TEXT("|")));
			return false;
		}
	}

	for (const FName PackageName : AllCatalogPackages)
	{
		if (FindPackage(nullptr, *PackageName.ToString()) != nullptr)
		{
			OutDetail = FString::Printf(
				TEXT("package is resident at checkpoint %s"),
				*PackageName.ToString());
			return false;
		}
	}
	return true;
}

bool ACatalogReadersFunctionalTest::CheckOneBeginPlayReportPerReader(
	FString& OutDetail) const
{
	const TArray<FCatalogObservedPublication> Reports = SnapshotPublications();
	if (Reports.Num() != Readers.Num())
	{
		OutDetail = FString::Printf(
			TEXT("expected=%d observed=%d"),
			Readers.Num(),
			Reports.Num());
		return false;
	}

	for (const FReaderExpectation& Expected : Readers)
	{
		int32 ExactMatches = 0;
		uint64 MatchFrame = 0;
		for (const FCatalogObservedPublication& Report : Reports)
		{
			if (Report.Reader == Expected.Actor
				&& Report.ReaderId == Expected.ReaderId
				&& Report.Count == Expected.ExpectedPackages.Num()
				&& Report.PackageNames == Expected.ExpectedPackages)
			{
				++ExactMatches;
				MatchFrame = Report.Frame;
			}
		}
		if (ExactMatches != 1)
		{
			OutDetail = FString::Printf(
				TEXT("reader %s exact protected publications expected=1 found=%d"),
				*Expected.ReaderId.ToString(),
				ExactMatches);
			return false;
		}
		const int64 FrameDelta =
			static_cast<int64>(MatchFrame) - static_cast<int64>(WorldInitFrame);
		if (FrameDelta < 0 || FrameDelta > 1)
		{
			OutDetail = FString::Printf(
				TEXT("reader %s report frame delta expected=0..1 found=%lld"),
				*Expected.ReaderId.ToString(),
				FrameDelta);
			return false;
		}
	}
	return true;
}

void ACatalogReadersFunctionalTest::OnCheckpoint(
	const int32 CheckpointIndex,
	const double TimeSeconds)
{
	FString Detail;
	if (!CheckExactReaderState(Detail))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs (checkpoint %d): CR-1 exact_actor_scoped_metadata_reports: %s"),
				TimeSeconds,
				CheckpointIndex,
				*Detail));
		return;
	}
	if (!CheckCatalogStayedUnloaded(Detail))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs (checkpoint %d): CR-2 all_examined_packages_remain_unloaded: %s"),
				TimeSeconds,
				CheckpointIndex,
				*Detail));
		return;
	}

	if (CheckpointIndex == 2)
	{
		if (!CheckOneBeginPlayReportPerReader(Detail))
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs (checkpoint %d): CR-3 one_beginplay_report_per_instance: %s"),
					TimeSeconds,
					CheckpointIndex,
					*Detail));
			return;
		}

		UE_LOG(
			LogTemp,
			Display,
			TEXT("[CB-CATALOG] checkpoint=2 readers=%d catalog=%d reports=%d unloaded=1"),
			Readers.Num(),
			AllCatalogPackages.Num(),
			SnapshotPublications().Num());
	}
}

void ACatalogReadersFunctionalTest::RemoveDelegates()
{
	if (ReportPublishedHandle.IsValid())
	{
		FCatalogReaderReportBridge::RemoveListener(ReportPublishedHandle);
		ReportPublishedHandle.Reset();
	}
	bBridgeInstalled = false;

	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	if (AssetLoadedHandle.IsValid())
	{
		FCoreUObjectDelegates::OnAssetLoaded.Remove(AssetLoadedHandle);
		AssetLoadedHandle.Reset();
	}
}

void ACatalogReadersFunctionalTest::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	RemoveDelegates();
	Super::EndPlay(EndPlayReason);
}
