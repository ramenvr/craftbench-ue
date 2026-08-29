// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/DistrictStreamingFunctionalTest.h"

#include "Engine/Level.h"
#include "Engine/LevelStreaming.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Engine/World.h"
#include "EngineUtils.h"

ADistrictStreamingFunctionalTestBase::ADistrictStreamingFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

void ADistrictStreamingAdmissionLoader::LoadRequestedDistrict_Implementation(
	ADistrictStreamRequest* Request)
{
	if (Request == nullptr || Request->RequestedDistrict.IsNull())
	{
		return;
	}
	bool bStarted = false;
	ActiveStreamingLevel = ULevelStreamingDynamic::LoadLevelInstanceBySoftObjectPtr(
		this, Request->RequestedDistrict, FTransform::Identity, bStarted);
	if (!bStarted)
	{
		ActiveStreamingLevel = nullptr;
	}
}

void ADistrictStreamingAdmissionLoader::UnloadRequestedDistrict_Implementation()
{
	if (ActiveStreamingLevel != nullptr)
	{
		ActiveStreamingLevel->SetShouldBeVisible(false);
		ActiveStreamingLevel->SetShouldBeLoaded(false);
		ActiveStreamingLevel = nullptr;
	}
}

bool ADistrictStreamingFunctionalTestBase::FailGate(
	const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("%s: %s"), Gate, *Detail));
	return false;
}

bool ADistrictStreamingFunctionalTestBase::RequireHarness(
	const bool bCondition, const FString& Detail)
{
	if (!bCondition)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Detail));
	}
	return bCondition;
}

TArray<ULevelStreaming*> ADistrictStreamingFunctionalTestBase::FindStreamsFor(
	const TSoftObjectPtr<UWorld>& WorldAsset, const bool bLoadedOnly) const
{
	TArray<ULevelStreaming*> Matches;
	const UWorld* World = GetWorld();
	const FName ExpectedPackage(*WorldAsset.ToSoftObjectPath().GetLongPackageName());
	if (World == nullptr || ExpectedPackage.IsNone())
	{
		return Matches;
	}
	for (ULevelStreaming* Stream : World->GetStreamingLevels())
	{
		if (Stream != nullptr
			&& (Stream->PackageNameToLoad == ExpectedPackage
				|| Stream->GetWorldAssetPackageFName() == ExpectedPackage)
			&& (!bLoadedOnly || (Stream->IsLevelLoaded() && Stream->IsLevelVisible())))
		{
			Matches.Add(Stream);
		}
	}
	return Matches;
}

TArray<ADistrictSectionMarker*> ADistrictStreamingFunctionalTestBase::FindMarkers(
	const FName DistrictId) const
{
	TArray<ADistrictSectionMarker*> Matches;
	for (TActorIterator<ADistrictSectionMarker> It(GetWorld()); It; ++It)
	{
		if (It->DistrictId == DistrictId)
		{
			Matches.Add(*It);
		}
	}
	return Matches;
}

bool ADistrictStreamingFunctionalTestBase::ResolveStaging()
{
	UWorld* World = GetWorld();
	TArray<ADistrictStreamLoaderBase*> Loaders;
	TArray<ADistrictStreamRequest*> Requests;
	int32 RequestActors = 0;
	for (TActorIterator<ADistrictStreamLoaderBase> It(World); It; ++It)
	{
		const bool bAdmissionClass = It->IsA<ADistrictStreamingAdmissionLoader>();
		if (bAdmissionClass == UsesAdmissionLoader())
		{
			Loaders.Add(*It);
		}
	}
	for (TActorIterator<ADistrictStreamRequest> It(World); It; ++It)
	{
		++RequestActors;
		if (It->RequestedDistrictId == ExpectedRequestedDistrictId())
		{
			Requests.Add(*It);
		}
	}
	if (!RequireHarness(Loaders.Num() == 1 && Requests.Num() == 1
		&& RequestActors == 2,
		FString::Printf(TEXT("expected loader/request/matrix=1/1/2 got=%d/%d/%d"),
			Loaders.Num(), Requests.Num(), RequestActors)))
	{
		return false;
	}
	Loader = Loaders[0];
	Request = Requests[0];
	return RequireHarness(!Request->RequestedDistrict.IsNull()
		&& !Request->UnrelatedControlDistrict.IsNull()
		&& Request->RequestedDistrictId != Request->ControlDistrictId,
		TEXT("request requires two distinct soft worlds and district identities"));
}

bool ADistrictStreamingFunctionalTestBase::RemoveExistingVerifierStreams()
{
	const FName RequestedPackage(
		*Request->RequestedDistrict.ToSoftObjectPath().GetLongPackageName());
	const FName ControlPackage(
		*Request->UnrelatedControlDistrict.ToSoftObjectPath().GetLongPackageName());
	int32 RemovedStreams = 0;
	for (ULevelStreaming* Stream : GetWorld()->GetStreamingLevels())
	{
		if (Stream != nullptr
			&& (Stream->PackageNameToLoad == RequestedPackage
				|| Stream->PackageNameToLoad == ControlPackage))
		{
			++RemovedStreams;
			Stream->SetShouldBeVisible(false);
			Stream->SetShouldBeLoaded(false);
			Stream->SetIsRequestingUnloadAndRemoval(true);
		}
	}
	GetWorld()->FlushLevelStreaming(EFlushLevelStreamingType::Full);
	const int32 RemainingStreams =
		FindStreamsFor(Request->RequestedDistrict, true).Num()
		+ FindStreamsFor(Request->UnrelatedControlDistrict, true).Num();
	const int32 RemainingMarkers =
		FindMarkers(Request->RequestedDistrictId).Num()
		+ FindMarkers(Request->ControlDistrictId).Num();
	UE_LOG(LogTemp, Display,
		TEXT("DISTRICT-STREAMING-HARNESS-RESET removed=%d remaining_streams=%d remaining_markers=%d"),
		RemovedStreams, RemainingStreams, RemainingMarkers);
	return RequireHarness(RemainingStreams == 0 && RemainingMarkers == 0,
		FString::Printf(TEXT("verifier stream reset incomplete streams=%d markers=%d"),
			RemainingStreams, RemainingMarkers));
}

void ADistrictStreamingFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	// Functional tests in one map share one PIE world. Remove only dynamic
	// streams created by the preceding verifier fixture before establishing the
	// next fixture's control. The submission is never called in this setup step.
	if (!RemoveExistingVerifierStreams())
	{
		return;
	}
	bool bControlStarted = false;
	ControlStream = ULevelStreamingDynamic::LoadLevelInstanceBySoftObjectPtr(
		this, Request->UnrelatedControlDistrict, FTransform::Identity,
		bControlStarted);
	if (!RequireHarness(bControlStarted && ControlStream.IsValid(),
		TEXT("verifier control district failed to start streaming")))
	{
		return;
	}
	ControlStream->bShouldBlockOnLoad = true;
	GetWorld()->FlushLevelStreaming(EFlushLevelStreamingType::Full);
	const TArray<ULevelStreaming*> ControlStreams = FindStreamsFor(
		Request->UnrelatedControlDistrict, true);
	const TArray<ADistrictSectionMarker*> ControlMarkers = FindMarkers(
		Request->ControlDistrictId);
	if (!RequireHarness(ControlStreams.Num() == 1
		&& ControlStreams[0] == ControlStream.Get()
		&& ControlMarkers.Num() == 1
		&& ControlMarkers[0]->GetLevel() == ControlStream->GetLoadedLevel(),
		FString::Printf(
			TEXT("verifier control did not block-load streams=%d markers=%d same=%d owned=%d"),
			ControlStreams.Num(), ControlMarkers.Num(),
			ControlStreams.Num() == 1 && ControlStreams[0] == ControlStream.Get() ? 1 : 0,
			ControlMarkers.Num() == 1 && ControlMarkers[0]->GetLevel()
				== ControlStream->GetLoadedLevel() ? 1 : 0)))
	{
		return;
	}
	const double Epoch = GetWorld()->GetTimeSeconds();
	UE_LOG(LogTemp, Display,
		TEXT("DISTRICT-STREAMING-WORLD-CLOCK epoch=%.3f offsets=1.00,1.20,2.20,2.40,3.40,3.60,4.60"),
		Epoch);
	SetCheckpointSchedule({Epoch + 1.00, Epoch + 1.20, Epoch + 2.20,
		Epoch + 2.40, Epoch + 3.40, Epoch + 3.60, Epoch + 4.60});
}

bool ADistrictStreamingFunctionalTestBase::RequireControlUnchanged(
	const TCHAR* Stage)
{
	const TArray<ULevelStreaming*> Streams = FindStreamsFor(
		Request->UnrelatedControlDistrict, true);
	const TArray<ADistrictSectionMarker*> Markers = FindMarkers(
		Request->ControlDistrictId);
	if (Streams.Num() != 1 || Streams[0] != ControlStream.Get()
		|| Markers.Num() != 1
		|| Markers[0]->GetLevel() != ControlStream->GetLoadedLevel())
	{
		return FailGate(TEXT("UnrelatedSectionsUnchanged"), FString::Printf(
			TEXT("stage=%s streams=%d markers=%d same_stream=%d owned=%d"),
			Stage, Streams.Num(), Markers.Num(),
			Streams.Num() == 1 && Streams[0] == ControlStream.Get() ? 1 : 0,
			Markers.Num() == 1 && Markers[0]->GetLevel()
				== ControlStream->GetLoadedLevel() ? 1 : 0));
	}
	if (ControlMarkerUniqueId == INDEX_NONE)
	{
		ControlMarker = Markers[0];
		ControlMarkerUniqueId = Markers[0]->GetUniqueID();
	}
	else if (Markers[0] != ControlMarker.Get()
		|| Markers[0]->GetUniqueID() != ControlMarkerUniqueId)
	{
		return FailGate(TEXT("UnrelatedSectionsUnchanged"), FString::Printf(
			TEXT("stage=%s control actor identity changed"), Stage));
	}
	return true;
}

bool ADistrictStreamingFunctionalTestBase::RequireRequestedLoaded(
	const TCHAR* Stage, const bool bCaptureFirstIdentity)
{
	const TArray<ULevelStreaming*> Streams = FindStreamsFor(
		Request->RequestedDistrict, true);
	const TArray<ADistrictSectionMarker*> Markers = FindMarkers(
		Request->RequestedDistrictId);
	if (Streams.Num() != 1 || Markers.Num() != 1
		|| Streams[0]->GetLoadedLevel() == nullptr
		|| Markers[0]->GetLevel() != Streams[0]->GetLoadedLevel()
		|| Markers[0]->GetLevel() == GetWorld()->PersistentLevel)
	{
		return FailGate(TEXT("ExactActorsEnterViaNamedSection"), FString::Printf(
			TEXT("stage=%s streams=%d markers=%d owned=%d persistent=%d"),
			Stage, Streams.Num(), Markers.Num(),
			Streams.Num() == 1 && Markers.Num() == 1
				&& Markers[0]->GetLevel() == Streams[0]->GetLoadedLevel() ? 1 : 0,
			Markers.Num() == 1 && Markers[0]->GetLevel()
				== GetWorld()->PersistentLevel ? 1 : 0));
	}
	if (bCaptureFirstIdentity)
	{
		FirstRequestedMarker = Markers[0];
		FirstRequestedMarkerUniqueId = Markers[0]->GetUniqueID();
	}
	else if (FirstRequestedMarker.IsValid()
		|| Markers[0] == FirstRequestedMarker.Get())
	{
		return FailGate(TEXT("ReloadCreatesFreshSectionActors"), FString::Printf(
			TEXT("stage=%s prior marker still resolves old_id=%d new_id=%d"),
			Stage, FirstRequestedMarkerUniqueId, Markers[0]->GetUniqueID()));
	}
	return true;
}

bool ADistrictStreamingFunctionalTestBase::RequireRequestedAbsent(
	const TCHAR* Stage)
{
	const TArray<ULevelStreaming*> LoadedStreams = FindStreamsFor(
		Request->RequestedDistrict, true);
	const TArray<ADistrictSectionMarker*> Markers = FindMarkers(
		Request->RequestedDistrictId);
	if (LoadedStreams.Num() != 0 || Markers.Num() != 0)
	{
		return FailGate(TEXT("ExactActorsLeaveAfterUnload"), FString::Printf(
			TEXT("stage=%s loaded_streams=%d markers=%d"), Stage,
			LoadedStreams.Num(), Markers.Num()));
	}
	return true;
}

void ADistrictStreamingFunctionalTestBase::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (!Loader.IsValid() || !Request.IsValid() || !ControlStream.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: staged request, loader, or control identity changed"));
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("DISTRICT-STREAMING-TELEMETRY cp=%d t=%.3f request=%s control=%s requested_loaded=%d control_loaded=%d"),
		CheckpointIndex, TimeSeconds, *Request->RequestedDistrictId.ToString(),
		*Request->ControlDistrictId.ToString(),
		FindStreamsFor(Request->RequestedDistrict, true).Num(),
		FindStreamsFor(Request->UnrelatedControlDistrict, true).Num());

	switch (CheckpointIndex)
	{
	case 0:
		if (!RequireControlUnchanged(TEXT("initial")))
		{
			return;
		}
		if (!FindStreamsFor(Request->RequestedDistrict, true).IsEmpty()
			|| !FindMarkers(Request->RequestedDistrictId).IsEmpty())
		{
			FailGate(TEXT("NamedSectionInactiveAtStart"),
				TEXT("requested section was active before the loader request"));
			return;
		}
		Loader->LoadRequestedDistrict(Request.Get());
		break;
	case 1:
		RequireControlUnchanged(TEXT("load-requested"));
		break;
	case 2:
		if (!RequireRequestedLoaded(TEXT("first-load"), true)
			|| !RequireControlUnchanged(TEXT("first-load")))
		{
			return;
		}
		Loader->UnloadRequestedDistrict();
		break;
	case 3:
		RequireControlUnchanged(TEXT("unload-requested"));
		break;
	case 4:
		if (!RequireRequestedAbsent(TEXT("unloaded"))
			|| !RequireControlUnchanged(TEXT("unloaded")))
		{
			return;
		}
		Loader->LoadRequestedDistrict(Request.Get());
		break;
	case 5:
		RequireControlUnchanged(TEXT("reload-requested"));
		break;
	case 6:
		if (!RequireRequestedLoaded(TEXT("reloaded"), false)
			|| !RequireControlUnchanged(TEXT("reloaded")))
		{
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("DISTRICT-STREAMING-SUCCEEDED request=%s gates=5 runtime_observed=1"),
			*Request->RequestedDistrictId.ToString());
		break;
	default:
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: unexpected checkpoint index"));
		break;
	}
}
