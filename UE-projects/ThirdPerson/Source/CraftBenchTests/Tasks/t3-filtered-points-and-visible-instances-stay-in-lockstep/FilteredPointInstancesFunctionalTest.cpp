// Copyright CraftBench. All Rights Reserved.

#include "FilteredPointInstancesFunctionalTest.h"

#include "Algo/AllOf.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Data/PCGBasePointData.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "FilteredPointPCGTypes.h"
#include "Metadata/PCGMetadata.h"
#include "Metadata/PCGMetadataAttributeTpl.h"
#include "PCGComponent.h"
#include "PCGData.h"
#include "PCGGraph.h"
#include "PCGManagedResource.h"
#include "StructUtils/PropertyBag.h"

namespace FilteredPointFixture
{
	const FName HostTag(TEXT("FilteredPointPCGHost"));
	const FName StableIdAttribute(TEXT("StableId"));
	const FName MinDensityParameter(TEXT("MinDensity"));
	constexpr double PositionTolerance = 0.75;
	constexpr double RotationTolerance = 0.25;
	constexpr double ScaleTolerance = 0.01;

	bool TransformFinite(const FTransform& Transform)
	{
		const FVector Location = Transform.GetLocation();
		const FVector Scale = Transform.GetScale3D();
		return !Transform.ContainsNaN()
			&& FMath::IsFinite(Location.X) && FMath::IsFinite(Location.Y)
			&& FMath::IsFinite(Location.Z) && FMath::IsFinite(Scale.X)
			&& FMath::IsFinite(Scale.Y) && FMath::IsFinite(Scale.Z)
			&& Transform.GetRotation().IsNormalized();
	}

	bool TransformNear(const FTransform& A, const FTransform& B)
	{
		return FVector::Dist(A.GetLocation(), B.GetLocation())
				<= PositionTolerance
			&& FMath::RadiansToDegrees(A.GetRotation().AngularDistance(
				B.GetRotation())) <= RotationTolerance
			&& FVector::Dist(A.GetScale3D(), B.GetScale3D()) <= ScaleTolerance;
	}

	int32 CountNear(const TArray<FTransform>& Values, const FTransform& Target)
	{
		int32 Count = 0;
		for (const FTransform& Value : Values)
		{
			Count += TransformNear(Value, Target) ? 1 : 0;
		}
		return Count;
	}
}

AFilteredPointInstancesFunctionalTestBase::
	AFilteredPointInstancesFunctionalTestBase(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.AddUnique(TEXT("FilteredPointInstancesFixture"));
}

bool AFilteredPointInstancesFunctionalTestBase::ResolveHarness()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FailHarness(TEXT("missing PIE world"));
		return false;
	}

	TArray<AFilteredPointPCGHost*> Hosts;
	for (TActorIterator<AFilteredPointPCGHost> It(World); It; ++It)
	{
		if (It->ActorHasTag(FilteredPointFixture::HostTag))
		{
			Hosts.Add(*It);
		}
	}
	if (Hosts.Num() != 1)
	{
		FailHarness(FString::Printf(
			TEXT("expected exact one protected PCG host; actual=%d"), Hosts.Num()));
		return false;
	}
	Host = Hosts[0];
	PCGComponent = Hosts[0]->GetPCGComponent();
	if (!PCGComponent.IsValid() || PCGComponent->GetGraph() == nullptr
		|| PCGComponent->GetGraphInstance() == nullptr
		|| Hosts[0]->GetSpawnMesh() == nullptr)
	{
		FailHarness(TEXT("host PCG component/graph/mesh is incomplete"));
		return false;
	}
	if (PCGComponent->GenerationTrigger
		!= EPCGComponentGenerationTrigger::GenerateOnDemand)
	{
		FailHarness(TEXT("PCG component is not ordinary on-demand generation"));
		return false;
	}
	return true;
}

void AFilteredPointInstancesFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	if (!ResolveHarness())
	{
		return;
	}

	UPCGComponent* Component = PCGComponent.Get();
	AFilteredPointPCGHost* CurrentHost = Host.Get();
	Component->CleanupLocalImmediate(true, true);
	CurrentHost->ApplyPolicy(UsesPolicyB());
	ProtectedBounds = CurrentHost->GetProtectedFilterBounds();
	if (!ProtectedBounds.IsValid || CurrentHost->GetPointFacts().Num() < 6)
	{
		FailHarness(TEXT("protected policy failed to publish bounds/point facts"));
		return;
	}

	FInstancedPropertyBag* Parameters = Component->GetGraphInstance()
		->GetMutableUserParametersStruct_Unsafe();
	if (Parameters == nullptr
		|| Parameters->SetValueFloat(FilteredPointFixture::MinDensityParameter,
			CurrentHost->GetMinDensity()) != EPropertyBagResult::Success)
	{
		FailHarness(TEXT("live MinDensity graph override unavailable"));
		return;
	}
	const auto Readback = Parameters->GetValueFloat(
		FilteredPointFixture::MinDensityParameter);
	if (!Readback.IsValid()
		|| !FMath::IsNearlyEqual(Readback.GetValue(),
			CurrentHost->GetMinDensity(), KINDA_SMALL_NUMBER))
	{
		FailHarness(TEXT("live MinDensity graph override did not read back"));
		return;
	}

	GenerationIssuedAt = GetWorld()->GetTimeSeconds();
	GenerationTask = Component->GenerateLocalGetTaskId(true);
	if (GenerationTask == InvalidPCGTaskId)
	{
		FailHarness(TEXT("ordinary GenerateLocalGetTaskId returned invalid task"));
		return;
	}
	// CraftBench checkpoints are absolute PIE world times. Both fixtures run in
	// the same PIE world, so each schedule must be anchored to its own epoch.
	SetCheckpointSchedule({GenerationIssuedAt + 0.25,
		GenerationIssuedAt + 5.0});
}

void AFilteredPointInstancesFunctionalTestBase::Tick(float DeltaSeconds)
{
	if (IsRunning() && PCGComponent.IsValid())
	{
		if (PCGComponent->IsGenerating())
		{
			bObservedGenerating = true;
		}
		else if (!bObservedCompletion && PCGComponent->bGenerated)
		{
			bObservedCompletion = true;
			GenerationCompletedAt = GetWorld()->GetTimeSeconds();
			UE_LOG(LogTemp, Display, TEXT(
				"FILTERED-POINT-PCG-COMPLETED policy=%s task=%llu issued=%.3f "
				"completed=%.3f observed_generating=%d"),
				UsesPolicyB() ? TEXT("B") : TEXT("A"),
				static_cast<uint64>(GenerationTask), GenerationIssuedAt,
				GenerationCompletedAt, bObservedGenerating ? 1 : 0);
		}
	}
	Super::Tick(DeltaSeconds);
}

void AFilteredPointInstancesFunctionalTestBase::PassGate(
	const TCHAR* GateName, const FString& Detail)
{
	++PassedGateCount;
	UE_LOG(LogTemp, Display, TEXT("GATE[%s]=PASS %s"), GateName, *Detail);
}

void AFilteredPointInstancesFunctionalTestBase::FailGate(
	const TCHAR* GateName, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]=FAIL %s"), GateName, *Detail));
}

void AFilteredPointInstancesFunctionalTestBase::FailHarness(
	const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Error,
		TEXT("HARNESS-PRECONDITION: ") + Detail);
}

void AFilteredPointInstancesFunctionalTestBase::EvaluateCandidate(
	double TimeSeconds)
{
	using namespace FilteredPointFixture;
	AFilteredPointPCGHost* CurrentHost = Host.Get();
	UPCGComponent* Component = PCGComponent.Get();
	if (CurrentHost == nullptr || Component == nullptr)
	{
		FailHarness(TEXT("host/component identity did not survive generation"));
		return;
	}
	if (Component->IsGenerating() || !bObservedCompletion || !Component->bGenerated)
	{
		FailHarness(FString::Printf(TEXT(
			"scheduled PCG generation incomplete t=%.2f generating=%d generated=%d "
			"observed_completion=%d"), TimeSeconds,
			Component->IsGenerating() ? 1 : 0, Component->bGenerated ? 1 : 0,
			bObservedCompletion ? 1 : 0));
		return;
	}

	TMap<int32, TArray<FTransform>> OutputById;
	TArray<FTransform> OutputTransforms;
	int32 PointDataCount = 0;
	bool bMetadataReadable = true;
	for (const FPCGTaggedData& Tagged :
		Component->GetGeneratedGraphOutput().TaggedData)
	{
		const UPCGBasePointData* PointData = Cast<UPCGBasePointData>(Tagged.Data);
		if (PointData == nullptr)
		{
			continue;
		}
		++PointDataCount;
		const UPCGMetadata* Metadata = PointData->ConstMetadata();
		const FPCGMetadataAttribute<int32>* StableIds = Metadata
			? Metadata->GetConstTypedAttribute<int32>(FPCGAttributeIdentifier(
				StableIdAttribute, PCGMetadataDomainID::Elements)) : nullptr;
		if (StableIds == nullptr)
		{
			bMetadataReadable = false;
			continue;
		}
		const auto Entries = PointData->GetConstMetadataEntryValueRange();
		const auto Transforms = PointData->GetConstTransformValueRange();
		if (Entries.Num() != PointData->GetNumPoints()
			|| Transforms.Num() != PointData->GetNumPoints())
		{
			bMetadataReadable = false;
			continue;
		}
		for (int32 Index = 0; Index < PointData->GetNumPoints(); ++Index)
		{
			const int32 StableId = StableIds->GetValueFromItemKey(Entries[Index]);
			OutputById.FindOrAdd(StableId).Add(Transforms[Index]);
			OutputTransforms.Add(Transforms[Index]);
		}
	}

	TArray<FTransform> InstanceTransforms;
	int32 ManagedISMResources = 0;
	int32 WrongManagedResources = 0;
	Component->ForEachManagedResource(
		[&](UPCGManagedResource* Resource)
		{
			UPCGManagedISMComponent* ManagedISM =
				Cast<UPCGManagedISMComponent>(Resource);
			if (ManagedISM == nullptr)
			{
				++WrongManagedResources;
				return;
			}
			UInstancedStaticMeshComponent* ISM = ManagedISM->GetComponent();
			if (ISM == nullptr || ISM->GetOwner() != CurrentHost
				|| ISM->GetStaticMesh() != CurrentHost->GetSpawnMesh()
				|| !ISM->IsRegistered() || !ISM->IsVisible())
			{
				++WrongManagedResources;
				return;
			}
			++ManagedISMResources;
			for (int32 Index = 0; Index < ISM->GetInstanceCount(); ++Index)
			{
				FTransform Transform;
				if (!ISM->GetInstanceTransform(Index, Transform, true))
				{
					++WrongManagedResources;
					continue;
				}
				InstanceTransforms.Add(Transform);
			}
		});

	TSet<int32> EligibleIds;
	TSet<int32> LowIds;
	TSet<int32> ExcludedIds;
	TSet<int32> OutsideIds;
	TMap<int32, FTransform> OracleTransforms;
	for (const FFilteredPointFact& Fact : CurrentHost->GetPointFacts())
	{
		const bool bInside = ProtectedBounds.IsInsideOrOn(
			Fact.Transform.GetLocation());
		if (!bInside)
		{
			OutsideIds.Add(Fact.StableId);
		}
		else if (Fact.bExcluded)
		{
			ExcludedIds.Add(Fact.StableId);
		}
		else if (Fact.Density + KINDA_SMALL_NUMBER < CurrentHost->GetMinDensity())
		{
			LowIds.Add(Fact.StableId);
		}
		else
		{
			EligibleIds.Add(Fact.StableId);
			OracleTransforms.Add(Fact.StableId, Fact.Transform);
		}
	}

	auto AnyOutput = [&OutputById](const TSet<int32>& Ids)
	{
		for (int32 Id : Ids)
		{
			const TArray<FTransform>* Values = OutputById.Find(Id);
			if (Values != nullptr && !Values->IsEmpty())
			{
				return true;
			}
		}
		return false;
	};
	auto AnyInstance = [&CurrentHost, &InstanceTransforms](const TSet<int32>& Ids)
	{
		return CurrentHost->GetPointFacts().ContainsByPredicate(
			[&Ids, &InstanceTransforms](const FFilteredPointFact& Fact)
			{
				return Ids.Contains(Fact.StableId)
					&& CountNear(InstanceTransforms, Fact.Transform) > 0;
			});
	};

	if (AnyOutput(LowIds) || AnyInstance(LowIds)
		|| AnyOutput(OutsideIds) || AnyInstance(OutsideIds))
	{
		FailGate(TEXT("BelowThresholdPointsRejected"), FString::Printf(TEXT(
			"low_or_outside_leaked low=%d outside=%d output=%d instances=%d"),
			LowIds.Num(), OutsideIds.Num(), OutputTransforms.Num(),
			InstanceTransforms.Num()));
		return;
	}
	PassGate(TEXT("BelowThresholdPointsRejected"), FString::Printf(TEXT(
		"low=%d outside=%d output_leaks=0 instance_leaks=0"),
		LowIds.Num(), OutsideIds.Num()));

	if (AnyOutput(ExcludedIds) || AnyInstance(ExcludedIds))
	{
		FailGate(TEXT("ExclusionMarkedPointsRejected"), FString::Printf(
			TEXT("excluded_leaked=%d"), ExcludedIds.Num()));
		return;
	}
	PassGate(TEXT("ExclusionMarkedPointsRejected"), FString::Printf(
		TEXT("excluded=%d output_leaks=0 instance_leaks=0"),
		ExcludedIds.Num()));

	bool bAllEligible = bMetadataReadable && PointDataCount == 1;
	for (int32 Id : EligibleIds)
	{
		const TArray<FTransform>* Values = OutputById.Find(Id);
		const FTransform* Oracle = OracleTransforms.Find(Id);
		bAllEligible &= Values != nullptr && Values->Num() >= 1
			&& Oracle != nullptr && Values->ContainsByPredicate(
				[Oracle](const FTransform& Value)
				{
					return TransformNear(Value, *Oracle);
				});
	}
	if (!bAllEligible)
	{
		FailGate(TEXT("AllEligiblePointsRetained"), FString::Printf(TEXT(
			"metadata=%d point_data=%d eligible=%d output_ids=%d"),
			bMetadataReadable ? 1 : 0, PointDataCount, EligibleIds.Num(),
			OutputById.Num()));
		return;
	}
	PassGate(TEXT("AllEligiblePointsRetained"), FString::Printf(TEXT(
		"eligible=%d output_ids=%d point_data=1"), EligibleIds.Num(),
		OutputById.Num()));

	bool bUnique = OutputById.Num() == EligibleIds.Num();
	for (int32 Id : EligibleIds)
	{
		const TArray<FTransform>* Values = OutputById.Find(Id);
		bUnique &= Values != nullptr && Values->Num() == 1;
	}
	if (!bUnique || OutputTransforms.Num() != EligibleIds.Num())
	{
		FailGate(TEXT("EligiblePointsNotDuplicated"), FString::Printf(TEXT(
			"eligible=%d output=%d output_ids=%d"), EligibleIds.Num(),
			OutputTransforms.Num(), OutputById.Num()));
		return;
	}
	PassGate(TEXT("EligiblePointsNotDuplicated"), FString::Printf(TEXT(
		"eligible=%d output=%d unique_ids=%d"), EligibleIds.Num(),
		OutputTransforms.Num(), OutputById.Num()));

	if (WrongManagedResources != 0 || ManagedISMResources != 1
		|| InstanceTransforms.Num() != OutputTransforms.Num())
	{
		FailGate(TEXT("SpawnCountMatchesFilteredOutput"), FString::Printf(TEXT(
			"managed_ism=%d wrong_resources=%d output=%d instances=%d"),
			ManagedISMResources, WrongManagedResources, OutputTransforms.Num(),
			InstanceTransforms.Num()));
		return;
	}
	PassGate(TEXT("SpawnCountMatchesFilteredOutput"), FString::Printf(TEXT(
		"managed_ism=1 output=%d instances=%d"), OutputTransforms.Num(),
		InstanceTransforms.Num()));

	bool bTransformsExact = Algo::AllOf(OutputTransforms, TransformFinite)
		&& Algo::AllOf(InstanceTransforms, TransformFinite);
	TArray<bool> UsedInstances;
	UsedInstances.Init(false, InstanceTransforms.Num());
	for (const FTransform& OutputTransform : OutputTransforms)
	{
		int32 Match = INDEX_NONE;
		for (int32 Index = 0; Index < InstanceTransforms.Num(); ++Index)
		{
			if (!UsedInstances[Index]
				&& TransformNear(OutputTransform, InstanceTransforms[Index]))
			{
				Match = Index;
				break;
			}
		}
		if (Match == INDEX_NONE)
		{
			bTransformsExact = false;
			break;
		}
		UsedInstances[Match] = true;
	}
	if (!bTransformsExact || UsedInstances.Contains(false))
	{
		FailGate(TEXT("SpawnTransformsMatchFilteredPoints"), FString::Printf(TEXT(
			"finite_join=0 output=%d instances=%d"), OutputTransforms.Num(),
			InstanceTransforms.Num()));
		return;
	}
	PassGate(TEXT("SpawnTransformsMatchFilteredPoints"), FString::Printf(TEXT(
		"finite_join=1 tolerance_cm=%.2f output=%d instances=%d"),
		PositionTolerance, OutputTransforms.Num(), InstanceTransforms.Num()));

	if (PassedGateCount != 6)
	{
		FailHarness(FString::Printf(TEXT("gate denominator drift actual=%d"),
			PassedGateCount));
		return;
	}
	UE_LOG(LogTemp, Display, TEXT(
		"FILTERED-POINT-PCG-TELEMETRY policy=%s threshold=%.3f seed=%u "
		"facts=%d eligible=%d low=%d excluded=%d outside=%d output=%d "
		"instances=%d point_data=%d managed_ism=%d generation_seconds=%.3f"),
		UsesPolicyB() ? TEXT("B") : TEXT("A"), CurrentHost->GetMinDensity(),
		CurrentHost->GetPolicySeed(), CurrentHost->GetPointFacts().Num(),
		EligibleIds.Num(), LowIds.Num(), ExcludedIds.Num(), OutsideIds.Num(),
		OutputTransforms.Num(), InstanceTransforms.Num(), PointDataCount,
		ManagedISMResources, GenerationCompletedAt - GenerationIssuedAt);
	FinishTest(EFunctionalTestResult::Succeeded,
		FString::Printf(TEXT(
			"FILTERED-POINT-PCG-SUCCEEDED policy=%s gates=6/6 output=%d "
			"instances=%d"), UsesPolicyB() ? TEXT("B") : TEXT("A"),
			OutputTransforms.Num(), InstanceTransforms.Num()));
}

void AFilteredPointInstancesFunctionalTestBase::OnCheckpoint(
	int32 CheckpointIndex, double TimeSeconds)
{
	if (CheckpointIndex == 0)
	{
		UE_LOG(LogTemp, Display, TEXT(
			"FILTERED-POINT-PCG-CHECKPOINT policy=%s index=0 t=%.2f task=%llu "
			"generating=%d generated=%d"),
			UsesPolicyB() ? TEXT("B") : TEXT("A"), TimeSeconds,
			static_cast<uint64>(GenerationTask),
			PCGComponent.IsValid() && PCGComponent->IsGenerating() ? 1 : 0,
			PCGComponent.IsValid() && PCGComponent->bGenerated ? 1 : 0);
		return;
	}
	if (CheckpointIndex == 1)
	{
		EvaluateCandidate(TimeSeconds);
		return;
	}
	FailHarness(FString::Printf(TEXT("unexpected checkpoint=%d"),
		CheckpointIndex));
}
