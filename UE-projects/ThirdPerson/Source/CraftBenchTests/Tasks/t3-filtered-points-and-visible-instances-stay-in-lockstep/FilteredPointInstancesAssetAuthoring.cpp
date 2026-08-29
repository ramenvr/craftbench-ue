// Copyright CraftBench. All Rights Reserved.

#include "FilteredPointInstancesAssetAuthoring.h"

#include "Elements/PCGAttributeFilter.h"
#include "Elements/PCGCullPointsOutsideActorBounds.h"
#include "Elements/PCGDensityFilter.h"
#include "Elements/PCGStaticMeshSpawner.h"
#include "Elements/PCGUserParameterGet.h"
#include "EngineUtils.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "FilteredPointInstancesFunctionalTest.h"
#include "FilteredPointPCGTypes.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "MeshSelectors/PCGMeshSelectorByAttribute.h"
#include "PCGComponent.h"
#include "PCGEdge.h"
#include "PCGGraph.h"
#include "PCGNode.h"
#include "PCGPin.h"
#include "StructUtils/PropertyBag.h"

namespace FilteredPointAuthoring
{
	const FName MinDensityParameter(TEXT("MinDensity"));
	const FName ExcludedAttribute(TEXT("Excluded"));
	const FName MeshAttribute(TEXT("Mesh"));

	FString Fail(const TCHAR* Gate, const FString& Detail)
	{
		const FString Result = FString::Printf(TEXT("FAIL %s %s"), Gate, *Detail);
		UE_LOG(LogTemp, Error, TEXT("FILTERED-POINT-AUTHORING %s"), *Result);
		return Result;
	}

	bool HasEdge(const UPCGNode* From, FName FromLabel,
		const UPCGNode* To, FName ToLabel)
	{
		const UPCGPin* Pin = From ? From->GetOutputPin(FromLabel) : nullptr;
		if (Pin == nullptr)
		{
			return false;
		}
		return Pin->Edges.ContainsByPredicate(
			[From, To, FromLabel, ToLabel](const UPCGEdge* Edge)
			{
				return Edge != nullptr && Edge->InputPin != nullptr
					&& Edge->OutputPin != nullptr
					&& Edge->InputPin->Node == From
					&& Edge->OutputPin->Node == To
					&& Edge->InputPin->Properties.Label == FromLabel
					&& Edge->OutputPin->Properties.Label == ToLabel;
			});
	}

	template <typename T>
	T* ExactSettings(const UPCGGraph* Graph, UPCGNode*& OutNode, int32& OutCount)
	{
		T* Result = nullptr;
		OutNode = nullptr;
		OutCount = 0;
		if (Graph == nullptr)
		{
			return nullptr;
		}
		for (UPCGNode* Node : Graph->GetNodes())
		{
			if (T* Settings = Node ? Cast<T>(Node->GetSettings()) : nullptr)
			{
				++OutCount;
				Result = Settings;
				OutNode = Node;
			}
		}
		return Result;
	}

	bool EnsureParameter(UPCGGraph* Graph)
	{
		const FInstancedPropertyBag* Parameters = Graph->GetUserParametersStruct();
		if (Parameters->FindPropertyDescByName(MinDensityParameter) == nullptr)
		{
			TArray<FPropertyBagPropertyDesc> Descriptions;
			Descriptions.Emplace(MinDensityParameter,
				EPropertyBagPropertyType::Float);
			if (Graph->AddUserParameters(Descriptions)
				!= EPropertyBagAlterationResult::Success)
			{
				return false;
			}
		}
		return Graph->GetUserParametersStruct()->GetNumPropertiesInBag() == 1
			&& Graph->GetMutableUserParametersStruct_Unsafe()->SetValueFloat(
				MinDensityParameter, 0.55f) == EPropertyBagResult::Success;
	}

	UPCGNode* AddParameterGetter(UPCGGraph* Graph)
	{
		const FPropertyBagPropertyDesc* Description =
			Graph->GetUserParametersStruct()->FindPropertyDescByName(
				MinDensityParameter);
		if (Description == nullptr)
		{
			return nullptr;
		}
		UPCGUserParameterGetSettings* Settings = nullptr;
		UPCGNode* Node = Graph->AddNodeOfType<UPCGUserParameterGetSettings>(
			Settings);
		if (Node != nullptr && Settings != nullptr)
		{
			Settings->PropertyName = MinDensityParameter;
			Settings->PropertyGuid = Description->ID;
			Node->UpdateAfterSettingsChangeDuringCreation();
		}
		return Node;
	}

	bool AddEdge(UPCGGraph* Graph, UPCGNode* From, FName FromPin,
		UPCGNode* To, FName ToPin)
	{
		if (Graph == nullptr || From == nullptr || To == nullptr)
		{
			return false;
		}
		// AddLabeledEdge returns whether a single-connection destination pin had
		// to discard another edge, not whether this edge was created.
		Graph->AddLabeledEdge(From, FromPin, To, ToPin);
		return HasEdge(From, FromPin, To, ToPin);
	}

	FString CompileGraph(UPCGGraph* Graph)
	{
		Graph->SetupEditorData();
		const bool bRecompiled = Graph->Recompile();
		const bool bPrimed = Graph->PrimeGraphCompilationCache();
		Graph->MarkPackageDirty();
		return bRecompiled && bPrimed ? FString() :
			Fail(TEXT("GRAPH_COMPILE"), FString::Printf(
				TEXT("recompiled=%d primed=%d"), bRecompiled ? 1 : 0,
				bPrimed ? 1 : 0));
	}
}

FString UFilteredPointInstancesAssetAuthoring::ConfigureGraph(
	UPCGGraph* Graph, bool bSolved)
{
	using namespace FilteredPointAuthoring;
	if (Graph == nullptr)
	{
		return Fail(TEXT("GRAPH_NULL"), TEXT("graph=null"));
	}
	TArray<UPCGNode*> Existing;
	Existing.Reserve(Graph->GetNodes().Num());
	for (UPCGNode* Node : Graph->GetNodes())
	{
		Existing.Add(Node);
	}
	Graph->RemoveNodes(Existing);
	if (!EnsureParameter(Graph))
	{
		return Fail(TEXT("GRAPH_PARAMETER"), TEXT("MinDensity exact-one failed"));
	}

	UPCGNode* OutputNode = Graph->GetOutputNode();
	UFilteredPointSourceSettings* SourceSettings = nullptr;
	UPCGNode* SourceNode =
		Graph->AddNodeOfType<UFilteredPointSourceSettings>(SourceSettings);
	if (OutputNode == nullptr || SourceNode == nullptr || SourceSettings == nullptr)
	{
		return Fail(TEXT("GRAPH_SOURCE"), TEXT("source/output creation failed"));
	}
	SourceNode->SetNodePosition(-800, 0);

	if (!bSolved)
	{
		if (!AddEdge(Graph, SourceNode, PCGPinConstants::DefaultOutputLabel,
			OutputNode, PCGPinConstants::DefaultOutputLabel))
		{
			return Fail(TEXT("GRAPH_BASELINE_EDGE"), TEXT("source->output failed"));
		}
		if (const FString CompileFailure = CompileGraph(Graph);
			!CompileFailure.IsEmpty())
		{
			return CompileFailure;
		}
		return InspectBaselineGraph(Graph);
	}

	UPCGCullPointsOutsideActorBoundsSettings* BoundsSettings = nullptr;
	UPCGDensityFilterSettings* DensitySettings = nullptr;
	UPCGAttributeFilteringSettings* ExclusionSettings = nullptr;
	UPCGStaticMeshSpawnerSettings* SpawnerSettings = nullptr;
	UPCGNode* BoundsNode = Graph->AddNodeOfType<
		UPCGCullPointsOutsideActorBoundsSettings>(BoundsSettings);
	UPCGNode* DensityNode = Graph->AddNodeOfType<UPCGDensityFilterSettings>(
		DensitySettings);
	UPCGNode* ExclusionNode = Graph->AddNodeOfType<
		UPCGAttributeFilteringSettings>(ExclusionSettings);
	UPCGNode* SpawnerNode = Graph->AddNodeOfType<
		UPCGStaticMeshSpawnerSettings>(SpawnerSettings);
	UPCGNode* ParameterNode = AddParameterGetter(Graph);
	if (BoundsNode == nullptr || DensityNode == nullptr
		|| ExclusionNode == nullptr || SpawnerNode == nullptr
		|| ParameterNode == nullptr || BoundsSettings == nullptr
		|| DensitySettings == nullptr || ExclusionSettings == nullptr
		|| SpawnerSettings == nullptr)
	{
		return Fail(TEXT("GRAPH_NODES"), TEXT("solved node creation failed"));
	}

	BoundsSettings->BoundsExpansion = 0.0f;
	BoundsSettings->Mode = EPCGCullPointsMode::Ordered;
	DensitySettings->LowerBound = 0.55f;
	DensitySettings->UpperBound = 1.0f;
	DensitySettings->bInvertFilter = false;
	DensitySettings->bNormalizeOutputDensity = false;
	ExclusionSettings->TargetAttribute.SetAttributeName(ExcludedAttribute);
	ExclusionSettings->Operator = EPCGAttributeFilterOperator::Equal;
	ExclusionSettings->bUseConstantThreshold = true;
	ExclusionSettings->AttributeTypes.Type = EPCGMetadataTypes::Boolean;
	ExclusionSettings->AttributeTypes.BoolValue = false;
	ExclusionSettings->bGenerateOutputDataEvenIfEmpty = true;
	SpawnerSettings->SetMeshSelectorType(
		UPCGMeshSelectorByAttribute::StaticClass());
	UPCGMeshSelectorByAttribute* Selector = Cast<UPCGMeshSelectorByAttribute>(
		SpawnerSettings->MeshSelectorParameters);
	if (Selector == nullptr)
	{
		return Fail(TEXT("GRAPH_MESH_SELECTOR"),
			TEXT("by-attribute selector unavailable"));
	}
	Selector->AttributeName = MeshAttribute;
	SpawnerSettings->bSynchronousLoad = true;
	SpawnerSettings->bApplyMeshBoundsToPoints = false;

	BoundsNode->SetNodePosition(-560, 0);
	DensityNode->SetNodePosition(-320, 0);
	ExclusionNode->SetNodePosition(-80, 0);
	ParameterNode->SetNodePosition(-560, -260);
	SpawnerNode->SetNodePosition(180, 180);
	OutputNode->SetNodePosition(440, -80);
	for (UPCGNode* Node : {BoundsNode, DensityNode, ExclusionNode,
		ParameterNode, SpawnerNode})
	{
		Node->UpdateAfterSettingsChangeDuringCreation();
	}

	const bool bEdges =
		AddEdge(Graph, SourceNode, PCGPinConstants::DefaultOutputLabel,
			BoundsNode, PCGPinConstants::DefaultInputLabel)
		&& AddEdge(Graph, BoundsNode, PCGPinConstants::DefaultOutputLabel,
			DensityNode, PCGPinConstants::DefaultInputLabel)
		&& AddEdge(Graph, ParameterNode, MinDensityParameter,
			DensityNode, TEXT("LowerBound"))
		&& AddEdge(Graph, DensityNode, PCGPinConstants::DefaultOutputLabel,
			ExclusionNode, PCGPinConstants::DefaultInputLabel)
		&& AddEdge(Graph, ExclusionNode, PCGPinConstants::DefaultInFilterLabel,
			OutputNode, PCGPinConstants::DefaultOutputLabel)
		&& AddEdge(Graph, ExclusionNode, PCGPinConstants::DefaultInFilterLabel,
			SpawnerNode, PCGPinConstants::DefaultInputLabel);
	if (!bEdges)
	{
		return Fail(TEXT("GRAPH_EDGES"), TEXT("solved edge creation failed"));
	}
	if (const FString CompileFailure = CompileGraph(Graph);
		!CompileFailure.IsEmpty())
	{
		return CompileFailure;
	}
	return InspectSolvedGraph(Graph);
}

FString UFilteredPointInstancesAssetAuthoring::InspectBaselineGraph(
	UPCGGraph* Graph)
{
	using namespace FilteredPointAuthoring;
	if (Graph == nullptr || Graph->GetUserParametersStruct() == nullptr
		|| Graph->GetUserParametersStruct()->GetNumPropertiesInBag() != 1
		|| Graph->GetUserParametersStruct()->FindPropertyDescByName(
			MinDensityParameter) == nullptr)
	{
		return Fail(TEXT("BASELINE_PARAMETER"),
			TEXT("MinDensity parameter is not exact-one"));
	}
	UPCGNode* SourceNode = nullptr;
	int32 SourceCount = 0;
	ExactSettings<UFilteredPointSourceSettings>(Graph, SourceNode, SourceCount);
	UPCGNode* OutputNode = Graph->GetOutputNode();
	if (Graph->GetNodes().Num() != 1 || SourceCount != 1
		|| !HasEdge(SourceNode, PCGPinConstants::DefaultOutputLabel,
			OutputNode, PCGPinConstants::DefaultOutputLabel))
	{
		return Fail(TEXT("BASELINE_SHAPE"), FString::Printf(
			TEXT("nodes=%d source=%d direct_output=%d"), Graph->GetNodes().Num(),
			SourceCount, HasEdge(SourceNode,
				PCGPinConstants::DefaultOutputLabel, OutputNode,
				PCGPinConstants::DefaultOutputLabel) ? 1 : 0));
	}
	return TEXT("PASS baseline_empty=1 graph_exact=1 nodes=1 source=1 "
		"parameter=MinDensity direct_output=1 filters=0 spawner=0");
}

FString UFilteredPointInstancesAssetAuthoring::InspectSolvedGraph(
	UPCGGraph* Graph)
{
	using namespace FilteredPointAuthoring;
	if (Graph == nullptr || Graph->GetUserParametersStruct() == nullptr
		|| Graph->GetUserParametersStruct()->GetNumPropertiesInBag() != 1
		|| Graph->GetUserParametersStruct()->FindPropertyDescByName(
			MinDensityParameter) == nullptr)
	{
		return Fail(TEXT("SOLVED_PARAMETER"),
			TEXT("MinDensity parameter is not exact-one"));
	}
	UPCGNode* SourceNode = nullptr;
	UPCGNode* BoundsNode = nullptr;
	UPCGNode* DensityNode = nullptr;
	UPCGNode* ExclusionNode = nullptr;
	UPCGNode* ParameterNode = nullptr;
	UPCGNode* SpawnerNode = nullptr;
	int32 SourceCount = 0;
	int32 BoundsCount = 0;
	int32 DensityCount = 0;
	int32 ExclusionCount = 0;
	int32 ParameterCount = 0;
	int32 SpawnerCount = 0;
	ExactSettings<UFilteredPointSourceSettings>(Graph, SourceNode, SourceCount);
	UPCGCullPointsOutsideActorBoundsSettings* Bounds =
		ExactSettings<UPCGCullPointsOutsideActorBoundsSettings>(
			Graph, BoundsNode, BoundsCount);
	UPCGDensityFilterSettings* Density =
		ExactSettings<UPCGDensityFilterSettings>(
			Graph, DensityNode, DensityCount);
	UPCGAttributeFilteringSettings* Exclusion =
		ExactSettings<UPCGAttributeFilteringSettings>(
			Graph, ExclusionNode, ExclusionCount);
	UPCGUserParameterGetSettings* Parameter =
		ExactSettings<UPCGUserParameterGetSettings>(
			Graph, ParameterNode, ParameterCount);
	UPCGStaticMeshSpawnerSettings* Spawner =
		ExactSettings<UPCGStaticMeshSpawnerSettings>(
			Graph, SpawnerNode, SpawnerCount);
	UPCGNode* OutputNode = Graph->GetOutputNode();
	if (Graph->GetNodes().Num() != 6 || SourceCount != 1 || BoundsCount != 1
		|| DensityCount != 1 || ExclusionCount != 1 || ParameterCount != 1
		|| SpawnerCount != 1 || Bounds == nullptr || Density == nullptr
		|| Exclusion == nullptr || Parameter == nullptr || Spawner == nullptr)
	{
		return Fail(TEXT("SOLVED_CARDINALITY"), FString::Printf(TEXT(
			"nodes=%d source=%d bounds=%d density=%d exclusion=%d parameter=%d "
			"spawner=%d"), Graph->GetNodes().Num(), SourceCount, BoundsCount,
			DensityCount, ExclusionCount, ParameterCount, SpawnerCount));
	}
	const UPCGMeshSelectorByAttribute* Selector =
		Cast<UPCGMeshSelectorByAttribute>(Spawner->MeshSelectorParameters);
	const bool bSettingsExact = Bounds->BoundsExpansion == 0.0f
		&& !Density->bInvertFilter && !Density->bNormalizeOutputDensity
		&& FMath::IsNearlyEqual(Density->UpperBound, 1.0f)
		&& Exclusion->TargetAttribute.GetName() == ExcludedAttribute
		&& Exclusion->Operator == EPCGAttributeFilterOperator::Equal
		&& Exclusion->bUseConstantThreshold
		&& Exclusion->AttributeTypes.Type == EPCGMetadataTypes::Boolean
		&& !Exclusion->AttributeTypes.BoolValue
		&& Parameter->PropertyName == MinDensityParameter
		&& Selector != nullptr && Selector->AttributeName == MeshAttribute
		&& Spawner->bSynchronousLoad;
	const bool bEdges =
		HasEdge(SourceNode, PCGPinConstants::DefaultOutputLabel,
			BoundsNode, PCGPinConstants::DefaultInputLabel)
		&& HasEdge(BoundsNode, PCGPinConstants::DefaultOutputLabel,
			DensityNode, PCGPinConstants::DefaultInputLabel)
		&& HasEdge(ParameterNode, MinDensityParameter,
			DensityNode, TEXT("LowerBound"))
		&& HasEdge(DensityNode, PCGPinConstants::DefaultOutputLabel,
			ExclusionNode, PCGPinConstants::DefaultInputLabel)
		&& HasEdge(ExclusionNode, PCGPinConstants::DefaultInFilterLabel,
			OutputNode, PCGPinConstants::DefaultOutputLabel)
		&& HasEdge(ExclusionNode, PCGPinConstants::DefaultInFilterLabel,
			SpawnerNode, PCGPinConstants::DefaultInputLabel);
	if (!bSettingsExact || !bEdges)
	{
		return Fail(TEXT("SOLVED_CONTRACT"), FString::Printf(
			TEXT("settings=%d edges=%d selector=%s"), bSettingsExact ? 1 : 0,
			bEdges ? 1 : 0, *GetPathNameSafe(Selector)));
	}
	return TEXT("PASS graph_exact=1 solved=1 nodes=6 source=1 bounds=1 "
		"density=1 exclusion=1 parameter=MinDensity spawner=1 "
		"metadata=Excluded mesh_attribute=Mesh output_branch=1 shared_branch=1");
}

FString UFilteredPointInstancesAssetAuthoring::InspectMap(
	UObject* WorldContextObject, bool bAdmission)
{
	using namespace FilteredPointAuthoring;
	UWorld* World = WorldContextObject
		? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return Fail(TEXT("MAP_WORLD"), TEXT("world=null"));
	}
	const FString ExpectedPackage = bAdmission
		? TEXT("/Game/Maps/t3-filtered-points-and-visible-instances-stay-in-lockstep/"
			"L_FilteredPointInstancesAdmission")
		: TEXT("/Game/Maps/t3-filtered-points-and-visible-instances-stay-in-lockstep/"
			"L_FilteredPointInstances");
	if (World->GetPackage()->GetName() != ExpectedPackage)
	{
		return Fail(TEXT("MAP_PACKAGE"), FString::Printf(
			TEXT("expected=%s actual=%s"), *ExpectedPackage,
			*World->GetPackage()->GetName()));
	}

	int32 HostCount = 0;
	int32 FixtureACount = 0;
	int32 FixtureBCount = 0;
	int32 PlayerStartCount = 0;
	int32 FloorCount = 0;
	AFilteredPointPCGHost* Host = nullptr;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor->GetClass() == AFilteredPointPCGHost::StaticClass())
		{
			++HostCount;
			Host = CastChecked<AFilteredPointPCGHost>(Actor);
		}
		else if (Actor->GetClass()
			== AFilteredPointInstancesFunctionalTestA::StaticClass())
		{
			++FixtureACount;
		}
		else if (Actor->GetClass()
			== AFilteredPointInstancesFunctionalTestB::StaticClass())
		{
			++FixtureBCount;
		}
		else if (Actor->GetClass() == APlayerStart::StaticClass())
		{
			++PlayerStartCount;
		}
		if (Actor->ActorHasTag(TEXT("FilteredPointInstancesFloor")))
		{
			++FloorCount;
		}
	}
	if (HostCount != 1 || FixtureACount != 1 || FixtureBCount != 1
		|| PlayerStartCount != 1 || FloorCount != 1 || Host == nullptr)
	{
		return Fail(TEXT("MAP_CARDINALITY"), FString::Printf(TEXT(
			"host=%d fixture_a=%d fixture_b=%d player_start=%d floor=%d"),
			HostCount, FixtureACount, FixtureBCount, PlayerStartCount, FloorCount));
	}
	UPCGComponent* Component = Host->GetPCGComponent();
	UPCGGraph* Graph = Component ? Component->GetGraph() : nullptr;
	const FString ExpectedGraph = bAdmission
		? TEXT("/Game/__CraftBenchAdmission/"
			"t3-filtered-points-and-visible-instances-stay-in-lockstep/"
			"PCG_FilteredPointInstances_Admission.PCG_FilteredPointInstances_Admission")
		: TEXT("/Game/Tasks/"
			"t3-filtered-points-and-visible-instances-stay-in-lockstep/"
			"PCG_FilteredPointInstances.PCG_FilteredPointInstances");
	UClass* GameMode = World->GetWorldSettings()
		? World->GetWorldSettings()->DefaultGameMode : nullptr;
	const bool bHostExact = Component != nullptr && Graph != nullptr
		&& GetPathNameSafe(Graph) == ExpectedGraph
		&& Component->GenerationTrigger
			== EPCGComponentGenerationTrigger::GenerateOnDemand
		&& Host->GetSpawnMesh() != nullptr;
	const bool bGameModeExact = GameMode != nullptr
		&& GetPathNameSafe(GameMode)
			== TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
				"BP_ThirdPersonGameMode_C");
	if (!bHostExact || !bGameModeExact)
	{
		return Fail(TEXT("MAP_IDENTITY"), FString::Printf(TEXT(
			"host_exact=%d graph=%s game_mode_exact=%d game_mode=%s"),
			bHostExact ? 1 : 0, *GetPathNameSafe(Graph),
			bGameModeExact ? 1 : 0, *GetPathNameSafe(GameMode)));
	}
	return FString::Printf(TEXT(
		"PASS map_exact=1 mode=%s host=1 fixture_a=1 fixture_b=1 "
		"player_start=1 floor=1 graph_exact=1 pcg_on_demand=1 mesh=1 "
		"game_mode_exact=1 runtime_observed=0"),
		bAdmission ? TEXT("admission") : TEXT("final"));
}
