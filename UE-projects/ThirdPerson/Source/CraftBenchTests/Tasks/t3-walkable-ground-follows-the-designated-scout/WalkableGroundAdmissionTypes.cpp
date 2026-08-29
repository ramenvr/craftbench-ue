// Copyright CraftBench. All Rights Reserved.

#include "WalkableGroundAdmissionTypes.h"

#include "AI/Navigation/NavAgentSelector.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "NavigationInvokerComponent.h"
#include "UObject/ConstructorHelpers.h"

AWalkableGroundAdmissionRecastNavMesh::AWalkableGroundAdmissionRecastNavMesh(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	RuntimeGeneration = ERuntimeGenerationType::Dynamic;
	bForceRebuildOnLoad = true;
}

void AWalkableGroundAdmissionRecastNavMesh::PostInitProperties()
{
	Super::PostInitProperties();
	// RuntimeGeneration is a config property. Pin it after config has been
	// applied so the verifier-owned admission class cannot inherit the stock
	// project's Static value after its native constructor ran.
	RuntimeGeneration = ERuntimeGenerationType::Dynamic;
	bForceRebuildOnLoad = true;
}

UWalkableGroundAdmissionNavigationSystem::
	UWalkableGroundAdmissionNavigationSystem(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	bGenerateNavigationOnlyAroundNavigationInvokers = true;
	ActiveTilesUpdateInterval = 0.10f;
	InvokersMaximumDistanceFromSeed = -1.0;
	bAutoCreateNavigationData = true;
	bInitialBuildingLocked = false;

	if (SupportedAgents.IsEmpty())
	{
		SupportedAgents.Add(FNavDataConfig());
	}
	SupportedAgentsMask.Empty();
	for (int32 AgentIndex = 0; AgentIndex < SupportedAgents.Num(); ++AgentIndex)
	{
		SupportedAgents[AgentIndex].SetNavDataClass(
			AWalkableGroundAdmissionRecastNavMesh::StaticClass());
		SupportedAgentsMask.Set(AgentIndex);
	}
	SupportedAgentsMask.MarkInitialized();
	DefaultAgentName = SupportedAgents[0].Name;
}

void UWalkableGroundAdmissionNavigationSystem::PostInitProperties()
{
	Super::PostInitProperties();
	// This is also a config property on UNavigationSystemV1. The admission
	// subclass owns the mechanism-positive control and must remain invoker-only
	// after the base class loads project defaults.
	bGenerateNavigationOnlyAroundNavigationInvokers = true;
	ActiveTilesUpdateInterval = 0.10f;
	InvokersMaximumDistanceFromSeed = -1.0;
}

void UWalkableGroundAdmissionNavigationSystem::InitializeForWorld(
	UWorld& World, FNavigationSystemRunMode Mode)
{
	// UNavigationSystemV1::InitializeForWorld propagates this value to every
	// nav datum via RestrictBuildingToActiveTiles, so pin it before Super.
	bGenerateNavigationOnlyAroundNavigationInvokers = true;
	Super::InitializeForWorld(World, Mode);
	bGenerateNavigationOnlyAroundNavigationInvokers = true;
}

AWalkableGroundAdmissionScout::AWalkableGroundAdmissionScout(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Tags.AddUnique(TEXT("WalkableGroundAdmissionScout"));
	NavigationInvoker = CreateDefaultSubobject<UNavigationInvokerComponent>(
		TEXT("NavigationInvoker"));
	NavigationInvoker->SetGenerationRadii(1600.0f, 2200.0f);

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MannyMesh(
		TEXT("/Game/Characters/Mannequins/Meshes/"
			"SKM_Manny_Simple.SKM_Manny_Simple"));
	static ConstructorHelpers::FClassFinder<UAnimInstance> MannyAnim(
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
	if (MannyMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMeshAsset(MannyMesh.Object);
		GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -90.0));
		GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	}
	if (MannyAnim.Succeeded())
	{
		GetMesh()->SetAnimInstanceClass(MannyAnim.Class);
	}
}
