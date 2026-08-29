// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "NavMesh/RecastNavMesh.h"
#include "NavigationSystem.h"
#include "Tasks/t3-walkable-ground-follows-the-designated-scout/DesignatedScoutCharacter.h"
#include "WalkableGroundAdmissionTypes.generated.h"

class UNavigationInvokerComponent;

/** Dynamic-only nav data used by the isolated admission world. */
UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API AWalkableGroundAdmissionRecastNavMesh
	: public ARecastNavMesh
{
	GENERATED_BODY()

public:
	AWalkableGroundAdmissionRecastNavMesh(
		const FObjectInitializer& ObjectInitializer);

	virtual void PostInitProperties() override;
};

/**
 * Admission-only navigation system. It pins invoker-bounded generation without
 * mutating ThirdPerson/Config or relying on an author console command.
 */
UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API UWalkableGroundAdmissionNavigationSystem
	: public UNavigationSystemV1
{
	GENERATED_BODY()

public:
	UWalkableGroundAdmissionNavigationSystem(
		const FObjectInitializer& ObjectInitializer);

	virtual void PostInitProperties() override;
	virtual void InitializeForWorld(
		UWorld& World, FNavigationSystemRunMode Mode) override;
};

/** Mechanism-positive admission subject: the verifier, not the candidate, owns it. */
UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API AWalkableGroundAdmissionScout
	: public ADesignatedScoutCharacter
{
	GENERATED_BODY()

public:
	AWalkableGroundAdmissionScout(const FObjectInitializer& ObjectInitializer);

	UNavigationInvokerComponent* GetNavigationInvoker() const
	{
		return NavigationInvoker;
	}

private:
	UPROPERTY(VisibleAnywhere, Category = "CraftBench|Admission")
	TObjectPtr<UNavigationInvokerComponent> NavigationInvoker;
};
