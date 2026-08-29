// Copyright CraftBench. All Rights Reserved.

#include "FilteredPointPCGTypes.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Data/PCGPointArrayData.h"
#include "Metadata/PCGMetadata.h"
#include "Metadata/PCGMetadataAttributeTpl.h"
#include "PCGComponent.h"
#include "PCGContext.h"
#include "PCGData.h"
#include "PCGElement.h"
#include "PCGGraph.h"
#include "UObject/ConstructorHelpers.h"

namespace FilteredPointPCG
{
	const FName StableIdAttribute(TEXT("StableId"));
	const FName ExcludedAttribute(TEXT("Excluded"));
	const FName MeshAttribute(TEXT("Mesh"));

	void AddFact(TArray<FFilteredPointFact>& Facts, const FTransform& HostTransform,
		int32 StableId, float Density, bool bExcluded,
		const FVector& LocalLocation, float YawDegrees, float UniformScale)
	{
		FFilteredPointFact& Fact = Facts.Emplace_GetRef();
		Fact.StableId = StableId;
		Fact.Density = Density;
		Fact.bExcluded = bExcluded;
		Fact.Transform = FTransform(
			HostTransform.TransformRotation(
				FRotator(0.0f, YawDegrees, 0.0f).Quaternion()),
			HostTransform.TransformPosition(LocalLocation),
			FVector(UniformScale));
	}
}

AFilteredPointPCGHost::AFilteredPointPCGHost(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(TEXT("FilteredPointPCGHost"));

	GenerationBounds = CreateDefaultSubobject<UBoxComponent>(
		TEXT("ProtectedGenerationBounds"));
	SetRootComponent(GenerationBounds);
	GenerationBounds->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GenerationBounds->SetHiddenInGame(true);
	GenerationBounds->SetBoxExtent(FVector(900.0, 650.0, 240.0));

	SourceMarker = CreateDefaultSubobject<UStaticMeshComponent>(
		TEXT("ProtectedSourceMarker"));
	SourceMarker->SetupAttachment(GenerationBounds);
	SourceMarker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SourceMarker->SetRelativeScale3D(FVector(0.65, 0.65, 1.8));

	PCGComponent = CreateDefaultSubobject<UPCGComponent>(TEXT("ProtectedPCG"));
	PCGComponent->GenerationTrigger = EPCGComponentGenerationTrigger::GenerateOnDemand;
	PCGComponent->bActivated = true;
	PCGComponent->Seed = 173;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		SpawnMesh = CubeMesh.Object;
		SourceMarker->SetStaticMesh(CubeMesh.Object);
	}
}

void AFilteredPointPCGHost::SetGraphAsset(UPCGGraphInterface* InGraph)
{
	if (PCGComponent != nullptr)
	{
		PCGComponent->SetGraphLocal(InGraph);
	}
}

void AFilteredPointPCGHost::ApplyPolicy(bool bUsePolicyB)
{
	using namespace FilteredPointPCG;
	PointFacts.Reset();

	if (bUsePolicyB)
	{
		SetActorLocationAndRotation(
			FVector(1850.0, 700.0, 120.0), FRotator(0.0, 27.0, 0.0),
			false, nullptr, ETeleportType::TeleportPhysics);
		GenerationBounds->SetBoxExtent(FVector(760.0, 520.0, 230.0));
		MinDensity = 0.72f;
		PolicySeed = 947u;
		const FTransform HostTransform = GetActorTransform();
		AddFact(PointFacts, HostTransform, 701, 0.95f, false,
			FVector(-350.0, -150.0, 70.0), 5.0f, 0.48f);
		AddFact(PointFacts, HostTransform, 809, 0.72f, false,
			FVector(0.0, 0.0, 70.0), 25.0f, 0.58f);
		AddFact(PointFacts, HostTransform, 1223, 0.78f, false,
			FVector(410.0, 160.0, 70.0), 55.0f, 0.52f);
		AddFact(PointFacts, HostTransform, 1319, 0.91f, false,
			FVector(-500.0, 260.0, 70.0), 80.0f, 0.44f);
		AddFact(PointFacts, HostTransform, 907, 0.90f, true,
			FVector(500.0, -200.0, 70.0), 105.0f, 0.50f);
		AddFact(PointFacts, HostTransform, 1009, 0.70f, false,
			FVector(-180.0, 350.0, 70.0), 135.0f, 0.56f);
		AddFact(PointFacts, HostTransform, 1117, 0.88f, false,
			FVector(1250.0, 0.0, 70.0), 165.0f, 0.46f);
	}
	else
	{
		SetActorLocationAndRotation(
			FVector(-1450.0, -550.0, 120.0), FRotator::ZeroRotator,
			false, nullptr, ETeleportType::TeleportPhysics);
		GenerationBounds->SetBoxExtent(FVector(900.0, 650.0, 240.0));
		MinDensity = 0.55f;
		PolicySeed = 173u;
		const FTransform HostTransform = GetActorTransform();
		AddFact(PointFacts, HostTransform, 101, 0.90f, false,
			FVector(-450.0, -200.0, 70.0), 0.0f, 0.50f);
		AddFact(PointFacts, HostTransform, 205, 0.55f, false,
			FVector(0.0, 0.0, 70.0), 20.0f, 0.60f);
		AddFact(PointFacts, HostTransform, 613, 0.76f, false,
			FVector(350.0, 220.0, 70.0), 45.0f, 0.54f);
		AddFact(PointFacts, HostTransform, 307, 0.88f, true,
			FVector(500.0, -250.0, 70.0), 75.0f, 0.48f);
		AddFact(PointFacts, HostTransform, 411, 0.54f, false,
			FVector(-250.0, 350.0, 70.0), 110.0f, 0.57f);
		AddFact(PointFacts, HostTransform, 509, 0.85f, false,
			FVector(1300.0, 0.0, 70.0), 150.0f, 0.45f);
	}

	GenerationBounds->UpdateBounds();
	ProtectedFilterBounds = GenerationBounds->Bounds.GetBox();
	PCGComponent->Seed = static_cast<int32>(PolicySeed);
}

TArray<FPCGPinProperties> UFilteredPointSourceSettings::InputPinProperties() const
{
	return {};
}

TArray<FPCGPinProperties> UFilteredPointSourceSettings::OutputPinProperties() const
{
	return {FPCGPinProperties(PCGPinConstants::DefaultOutputLabel,
		FPCGDataTypeIdentifier{EPCGDataType::Point})};
}

namespace
{
	class FFilteredPointSourceElement final : public IPCGElement
	{
	public:
		virtual bool CanExecuteOnlyOnMainThread(FPCGContext* Context) const override
		{
			return true;
		}

		virtual bool IsCacheable(const UPCGSettings* InSettings) const override
		{
			return false;
		}

	protected:
		virtual bool ExecuteInternal(FPCGContext* Context) const override
		{
			using namespace FilteredPointPCG;
			UPCGComponent* SourceComponent = Context != nullptr
				? Cast<UPCGComponent>(Context->ExecutionSource.Get()) : nullptr;
			AFilteredPointPCGHost* Host = SourceComponent != nullptr
				? Cast<AFilteredPointPCGHost>(SourceComponent->GetOwner()) : nullptr;
			if (Host == nullptr || Host->GetSpawnMesh() == nullptr)
			{
				return true;
			}

			UPCGPointArrayData* PointData =
				FPCGContext::NewObject_AnyThread<UPCGPointArrayData>(Context);
			const TArray<FFilteredPointFact>& Facts = Host->GetPointFacts();
			PointData->SetNumPoints(Facts.Num());
			PointData->AllocateProperties(
				EPCGPointNativeProperties::Transform
				| EPCGPointNativeProperties::Density
				| EPCGPointNativeProperties::Seed
				| EPCGPointNativeProperties::MetadataEntry);

			auto Transforms = PointData->GetTransformValueRange();
			auto Densities = PointData->GetDensityValueRange();
			auto Seeds = PointData->GetSeedValueRange();
			auto Entries = PointData->GetMetadataEntryValueRange();
			FPCGMetadataDomain* Domain = PointData->MutableMetadata()
				->GetMetadataDomain(PCGMetadataDomainID::Elements);
			FPCGMetadataAttribute<int32>* StableIds =
				Domain->CreateAttribute<int32>(StableIdAttribute, INDEX_NONE,
					false, false);
			FPCGMetadataAttribute<bool>* Excluded =
				Domain->CreateAttribute<bool>(ExcludedAttribute, false,
					false, false);
			FPCGMetadataAttribute<FSoftObjectPath>* Meshes =
				Domain->CreateAttribute<FSoftObjectPath>(MeshAttribute,
					FSoftObjectPath(), false, false);
			if (StableIds == nullptr || Excluded == nullptr || Meshes == nullptr)
			{
				return true;
			}

			const FSoftObjectPath MeshPath(Host->GetSpawnMesh());
			for (int32 Index = 0; Index < Facts.Num(); ++Index)
			{
				const FFilteredPointFact& Fact = Facts[Index];
				Transforms[Index] = Fact.Transform;
				Densities[Index] = Fact.Density;
				Seeds[Index] = HashCombineFast(
					Host->GetPolicySeed(), GetTypeHash(Fact.StableId));
				Entries[Index] = Domain->AddEntry();
				StableIds->SetValue(Entries[Index], Fact.StableId);
				Excluded->SetValue(Entries[Index], Fact.bExcluded);
				Meshes->SetValue(Entries[Index], MeshPath);
			}

			FPCGTaggedData& Tagged = Context->OutputData.TaggedData.Emplace_GetRef();
			Tagged.Data = PointData;
			Tagged.Pin = PCGPinConstants::DefaultOutputLabel;
			return true;
		}
	};
}

FPCGElementPtr UFilteredPointSourceSettings::CreateElement() const
{
	return MakeShared<FFilteredPointSourceElement>();
}
