// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ATagGateFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns the token GLog listener, the tag-name
// host lookup, and the reflection-driven marker remove/re-add.

#include "TagGateFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/Class.h"

namespace
{
	// Constants match the task prompt exactly (tasks/cpp/t1-gameplay-tag-gate).
	static const FName HostIdentityTag(TEXT("TagGateRoot"));
	static const FName GateMarkerName(TEXT("CraftBench.TagGate.Active"));
	static const TCHAR* TickToken = TEXT("CRAFTBENCH_TAG_GATE_TICK");
	static const FName TickCategory(TEXT("LogTemp"));

	// The accessor param block declared by the scaffold: one FGameplayTag.
	struct FGateMarkerAccessorParams
	{
		FGameplayTag Tag;
	};
}

void FTagGateTickCounterDevice::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory)
{
	if (V == nullptr)
	{
		return;
	}
	if (InCategory != Category)
	{
		return;
	}
	const ELogVerbosity::Type EffectiveVerbosity = static_cast<ELogVerbosity::Type>(Verbosity & ELogVerbosity::VerbosityMask);
	if (EffectiveVerbosity > MinVerbosity)
	{
		return;
	}
	if (FCString::Strstr(V, *Substring) != nullptr)
	{
		++MatchCount;
	}
}

ATagGateFunctionalTest::ATagGateFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Install the GLog device pre-BeginPlay so an emission in the BeginPlay
	// window itself (a legal "first line") is counted.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ATagGateFunctionalTest::OnWorldActorsInitialized);
}

void ATagGateFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bDeviceInstalled || Params.World != GetWorld())
	{
		return;
	}
	InstallLogDevice();
}

void ATagGateFunctionalTest::InstallLogDevice()
{
	// Verbosity floor = Display (the prompt's stated floor), category = LogTemp.
	LogCounter = MakeUnique<FTagGateTickCounterDevice>(
		FString(TickToken), TickCategory, ELogVerbosity::Display);
	if (GLog != nullptr)
	{
		GLog->AddOutputDevice(LogCounter.Get());
		bDeviceInstalled = true;
	}
}

void ATagGateFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Ensure the listener is up even if the world-init delegate did not fire.
	if (!bDeviceInstalled)
	{
		InstallLogDevice();
	}

	// Identity by project tag, never by C++ class name — the agent may
	// legitimately subclass (or replace) the scaffold actor.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, HostIdentityTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Expected exactly one TagGateRoot-tagged actor in the level; found %d."),
				Found.Num()));
		return;
	}
	HostActor = Found[0];

	// Non-fatal request: an unregistered marker is a named FAIL, not a crash.
	// The scaffold module registers it natively; only a submission that deleted
	// that definition (or renamed the tag) lands here.
	GateTag = FGameplayTag::RequestGameplayTag(GateMarkerName, /*ErrorIfNotFound=*/false);
	if (!GateTag.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The state marker CraftBench.TagGate.Active is not registered with the tag system; the actor module's native marker definition is missing."));
		return;
	}

	// Validate both accessor seams up front so a missing/reshaped accessor is
	// a prepare-time named FAIL rather than a mid-run surprise.
	UFunction* Unused = nullptr;
	if (!ResolveAccessor(Found[0], TEXT("AddGateTag"), Unused))
	{
		return;
	}
	if (!ResolveAccessor(Found[0], TEXT("RemoveGateTag"), Unused))
	{
		return;
	}

	// Mid-interval sample times against the 0.5 s period: 1.8 sits between the
	// 1.5 and 2.0 emissions, 3.6 between 3.5 and 4.0, 5.4 between 5.2 and 5.5
	// for every legal phase — no checkpoint races a scheduled emission.
	SetCheckpointSchedule({ 1.8, 3.6, 5.4 });
}

bool ATagGateFunctionalTest::ResolveAccessor(AActor* Host, const TCHAR* FunctionName, UFunction*& OutFunction)
{
	OutFunction = nullptr;
	// No null-host FinishTest branch here on purpose (review catch 2026-08-11):
	// both call sites resolve Host through PrepareTest's Num()==1 gate and the
	// per-checkpoint null-check before invoking — a fail literal that
	// can never fire is exactly what a MATRIX re-anchor pass would hunt for.
	check(Host != nullptr);
	UFunction* Fn = Host->FindFunction(FName(FunctionName));
	if (Fn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("The host actor is missing the required accessor function '%s'."),
				FunctionName));
		return false;
	}
	if (Fn->NumParms != 1 || Fn->ParmsSize != sizeof(FGameplayTag))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Accessor function '%s' has an unexpected parameter layout; expected a single state-marker parameter."),
				FunctionName));
		return false;
	}
	OutFunction = Fn;
	return true;
}

bool ATagGateFunctionalTest::InvokeMarkerAccessor(AActor* Host, const TCHAR* FunctionName)
{
	UFunction* Fn = nullptr;
	if (!ResolveAccessor(Host, FunctionName, Fn))
	{
		return false;  // ResolveAccessor already FinishTest'd with a named message.
	}
	FGateMarkerAccessorParams Params;
	Params.Tag = GateTag;
	Host->ProcessEvent(Fn, &Params);
	return true;
}

void ATagGateFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double /*TimeSeconds*/)
{
	const int32 Count = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;
	AActor* Host = HostActor.Get();
	if (Host == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The TagGateRoot host actor is no longer present at a checkpoint."));
		return;
	}

	switch (CheckpointIndex)
	{
	case 0:
	{
		// Marker present since gameplay start: 0.5 s period over 1.8 s = 3
		// emissions (first at 0.5 s), or 4 with a legal immediate first line.
		if (Count < 3 || Count > 4)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=1.8s expected 3-4 CRAFTBENCH_TAG_GATE_TICK emissions while the marker is present; observed %d."),
					Count));
			return;
		}
		if (!InvokeMarkerAccessor(Host, TEXT("RemoveGateTag")))
		{
			return;
		}
		StopBaseline = LogCounter.IsValid() ? LogCounter->GetMatchCount() : Count;
		break;
	}
	case 1:
	{
		const int32 NewSinceStop = Count - StopBaseline;
		if (NewSinceStop != 0)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=3.6s expected no further emissions after the marker was removed at t=1.8s; observed %d new."),
					NewSinceStop));
			return;
		}
		if (!InvokeMarkerAccessor(Host, TEXT("AddGateTag")))
		{
			return;
		}
		ResumeBaseline = LogCounter.IsValid() ? LogCounter->GetMatchCount() : Count;
		break;
	}
	case 2:
	{
		const int32 NewSinceResume = Count - ResumeBaseline;
		if (NewSinceResume < 2 || NewSinceResume > 4)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=5.4s expected the emissions to resume after the marker was re-added at t=3.6s (2-4 new); observed %d new."),
					NewSinceResume));
			return;
		}
		FinishTest(
			EFunctionalTestResult::Succeeded,
			TEXT("t1-gameplay-tag-gate: gated emission verified across remove and re-add."));
		break;
	}
	default:
		break;
	}
}

void ATagGateFunctionalTest::RemoveLogDevice()
{
	if (LogCounter.IsValid())
	{
		if (GLog != nullptr)
		{
			GLog->RemoveOutputDevice(LogCounter.Get());
		}
		LogCounter.Reset();
	}
	bDeviceInstalled = false;
}

void ATagGateFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	RemoveLogDevice();
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
