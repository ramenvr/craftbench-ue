// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADefaultCubeMeshFunctionalTest implementation. PIE-native: no manual ticking,
// no manual DispatchBeginPlay. The pre-BeginPlay probe runs in
// OnWorldInitializedActors (the same window the t0 log listener uses); the
// runtime and class-default probes run at checkpoint 0. All failure messages
// are ASCII-only and stable — the discrimination matrix keys on them.

#include "DefaultCubeMeshFunctionalTest.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName CubeMeshDisplayTag(TEXT("CubeMeshDisplay"));
	static const TCHAR* EngineCubeObjectPath = TEXT("/Engine/BasicShapes/Cube.Cube");

	enum class ECubeProbe : uint8
	{
		Cube,          // a qualifying component displays the engine cube
		CubeHidden,    // the cube is assigned but only on an unregistered/invisible component
		WrongMesh,     // a component has a mesh, but not the engine cube
		NoMesh,        // component(s) exist, none has any mesh assigned
		NoComponent,   // the actor has no static-mesh component at all
	};

	/**
	 * Classifies how (or whether) an actor displays the engine cube.
	 * bRequireRegisteredVisible additionally demands the component be
	 * registered, visible and not hidden in game (used for the placed instance
	 * at checkpoint time; the pre-BeginPlay and class-default probes check mesh
	 * identity only). OutDetail is a stable ASCII fragment naming what was
	 * found instead — the discrimination matrix keys on these fragments.
	 */
	ECubeProbe ProbeActorForEngineCube(const AActor* Actor, const bool bRequireRegisteredVisible, FString& OutDetail)
	{
		if (Actor == nullptr)
		{
			// Defensive only — every call site null-checks with its own,
			// site-specific message before probing. Deliberately NOT the
			// empty-leg wording: a null actor is not a missing component.
			OutDetail = TEXT("the probed actor is null.");
			return ECubeProbe::NoComponent;
		}

		TInlineComponentArray<UStaticMeshComponent*> MeshComponents;
		Actor->GetComponents(MeshComponents);

		if (MeshComponents.Num() == 0)
		{
			OutDetail = TEXT("found no static-mesh component on the actor.");
			return ECubeProbe::NoComponent;
		}

		bool bSawCubeAnywhere = false;
		const UStaticMesh* FirstOtherMesh = nullptr;

		for (const UStaticMeshComponent* MeshComponent : MeshComponents)
		{
			if (MeshComponent == nullptr)
			{
				continue;
			}
			const UStaticMesh* Mesh = MeshComponent->GetStaticMesh();
			if (Mesh == nullptr)
			{
				continue;
			}
			if (Mesh->GetPathName() == EngineCubeObjectPath)
			{
				bSawCubeAnywhere = true;
				const bool bQualifies = !bRequireRegisteredVisible
					|| (MeshComponent->IsRegistered() && MeshComponent->IsVisible() && !MeshComponent->bHiddenInGame);
				if (bQualifies)
				{
					OutDetail = TEXT("the engine cube is assigned and displayed.");
					return ECubeProbe::Cube;
				}
			}
			else if (FirstOtherMesh == nullptr)
			{
				FirstOtherMesh = Mesh;
			}
		}

		if (bSawCubeAnywhere)
		{
			OutDetail = TEXT("found the engine cube only on a component that is not registered and visible.");
			return ECubeProbe::CubeHidden;
		}
		if (FirstOtherMesh != nullptr)
		{
			OutDetail = FString::Printf(
				TEXT("found a static-mesh component showing '%s' instead of the engine cube."),
				*FirstOtherMesh->GetPathName());
			return ECubeProbe::WrongMesh;
		}
		OutDetail = TEXT("found a static-mesh component with no mesh assigned.");
		return ECubeProbe::NoMesh;
	}
}

ADefaultCubeMeshFunctionalTest::ADefaultCubeMeshFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Register the callback early; the probe runs inside it, after
	// PostInitializeComponents and before placed-actor BeginPlay — so a
	// runtime-assigned (BeginPlay-time) mesh is observed against the correct
	// window. The Params.World filter makes the CDO's registration inert.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ADefaultCubeMeshFunctionalTest::OnWorldActorsInitialized);
}

void ADefaultCubeMeshFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bPreBeginPlayProbed || Params.World != GetWorld())
	{
		return;
	}
	bPreBeginPlayProbed = true;

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(Params.World, CubeMeshDisplayTag, Found);
	if (Found.Num() != 1)
	{
		bPreBeginPlayCube = false;
		PreBeginPlayDetail = FString::Printf(
			TEXT("pre-BeginPlay tag resolution found %d 'CubeMeshDisplay' actor(s)."), Found.Num());
		return;
	}

	FString Detail;
	// Mesh identity only at this window — registration/visibility is asserted
	// on the live instance at checkpoint time.
	const ECubeProbe Pre = ProbeActorForEngineCube(Found[0], /*bRequireRegisteredVisible=*/false, Detail);
	bPreBeginPlayCube = (Pre == ECubeProbe::Cube);
	// Window-specific wording, deliberately DISJOINT from the checkpoint-time
	// probe details: the discrimination matrix keys on the checkpoint
	// fragments, and this fragment is embedded inside the runtime-assignment
	// failure message — reusing a checkpoint fragment here would nest one
	// leg's MATRIX substring inside another leg's failure output.
	switch (Pre)
	{
		case ECubeProbe::Cube:
			PreBeginPlayDetail = TEXT("the engine cube was already assigned at the pre-BeginPlay window.");
			break;
		case ECubeProbe::NoComponent:
			PreBeginPlayDetail = TEXT("no static-mesh component existed yet at the pre-BeginPlay window.");
			break;
		case ECubeProbe::NoMesh:
			PreBeginPlayDetail = TEXT("no mesh was yet assigned at the pre-BeginPlay window.");
			break;
		case ECubeProbe::WrongMesh:
			PreBeginPlayDetail = TEXT("a different mesh was assigned at the pre-BeginPlay window.");
			break;
		default:
			// CubeHidden is unreachable with bRequireRegisteredVisible=false.
			PreBeginPlayDetail = TEXT("the pre-BeginPlay observation was inconclusive.");
			break;
	}
}

void ADefaultCubeMeshFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, not by class — the agent may subclass the host actor.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, CubeMeshDisplayTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'CubeMeshDisplay' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];

	// One checkpoint, well past BeginPlay: any runtime assignment has happened
	// by then, so the contrast with the pre-BeginPlay probe is decisive.
	SetCheckpointSchedule({ 0.5 });
}

void ADefaultCubeMeshFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (CheckpointIndex != 0)
	{
		return;
	}

	// (1) The placed instance displays the engine cube right now, on a
	// registered + visible component. An agent-destroyed/invalidated host is
	// agent-caused, so it grades as a plain FAIL with its own message (not the
	// empty-leg wording — a vanished actor is not a missing component).
	if (Host == nullptr || !IsValid(Host))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At t=%.2fs: the tagged actor is no longer valid at checkpoint time."), TimeSeconds));
		return;
	}
	FString NowDetail;
	const ECubeProbe Now = ProbeActorForEngineCube(Host, /*bRequireRegisteredVisible=*/true, NowDetail);
	if (Now != ECubeProbe::Cube)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs: expected a registered, visible static-mesh component on the 'CubeMeshDisplay' actor displaying the engine cube ('/Engine/BasicShapes/Cube.Cube'); %s"),
				TimeSeconds, *NowDetail));
		return;
	}

	// (2) The cube was already present BEFORE BeginPlay — the default state of
	// the placed instance, not a runtime acquisition.
	if (!bPreBeginPlayCube)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs: the actor displays the engine cube at checkpoint time, but the cube was assigned at runtime rather than carried as a class default (pre-BeginPlay observation: %s)"),
				TimeSeconds, *PreBeginPlayDetail));
		return;
	}

	// (3) The TYPE carries the cube: the class default object has a
	// static-mesh component with the cube assigned (per-instance map edits or
	// per-run state cannot produce this). A CDO that cannot be RESOLVED is a
	// verifier-side precondition failure, not an agent behavior — flag it as
	// such. (Today EFunctionalTestResult::Error still grades as a FAIL; the
	// prefix + Error express the intended semantics for a future routing rule.)
	const AActor* ClassDefault = (Host->GetClass() != nullptr)
		? Host->GetClass()->GetDefaultObject<AActor>()
		: nullptr;
	if (ClassDefault == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: at t=%.2fs the class default object could not be resolved."), TimeSeconds));
		return;
	}
	FString CdoDetail;
	if (ProbeActorForEngineCube(ClassDefault, /*bRequireRegisteredVisible=*/false, CdoDetail) != ECubeProbe::Cube)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs: the class default object does not carry the engine cube on a static-mesh component; %s"),
				TimeSeconds, *CdoDetail));
		return;
	}

	// All three probes green — the base finishes the test as success after the
	// last checkpoint.
}

void ADefaultCubeMeshFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
