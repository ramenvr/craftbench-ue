// Copyright CraftBench. All Rights Reserved.

#include "ReplicatedDoorTypes.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/NetDriver.h"
#include "Engine/PackageMapClient.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/NetworkGuid.h"
#include "Net/UnrealNetwork.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogDoorNetworkVerifier, Log, All);

namespace
{
	constexpr TCHAR ProtocolEnv[] = TEXT("CRAFTBENCH_DOOR_PROTOCOL");
	constexpr TCHAR NonceEnv[] = TEXT("CRAFTBENCH_DOOR_NONCE");
	constexpr TCHAR PeerEnv[] = TEXT("CRAFTBENCH_DOOR_PEER");
	constexpr TCHAR FirstRequesterEnv[] = TEXT("CRAFTBENCH_DOOR_FIRST_REQUESTER");
	constexpr TCHAR SecondRequesterEnv[] = TEXT("CRAFTBENCH_DOOR_SECOND_REQUESTER");
	constexpr TCHAR ClosedTransformEnv[] = TEXT("CRAFTBENCH_DOOR_CLOSED_TRANSFORM");
	constexpr TCHAR OpenTransformEnv[] = TEXT("CRAFTBENCH_DOOR_OPEN_TRANSFORM");
	const FName DoorRevisionName(TEXT("DoorRevision"));
	const FName RequestToggleName(TEXT("RequestToggle"));

	bool NearlySameTransform(const FTransform& A, const FTransform& B)
	{
		return A.GetLocation().Equals(B.GetLocation(), 0.25)
			&& A.GetRotation().Equals(B.GetRotation(), 0.0025)
			&& A.GetScale3D().Equals(B.GetScale3D(), 0.0025);
	}

	bool FiniteTransform(const FTransform& Value)
	{
		return !Value.ContainsNaN();
	}

	bool ParseProtocolTransform(const FString& Text, FTransform& OutTransform)
	{
		TArray<FString> Parts;
		Text.ParseIntoArray(Parts, TEXT(","), true);
		if (Parts.Num() != 4)
		{
			return false;
		}
		double X = 0.0;
		double Y = 0.0;
		double Z = 0.0;
		double Yaw = 0.0;
		if (!LexTryParseString(X, *Parts[0])
			|| !LexTryParseString(Y, *Parts[1])
			|| !LexTryParseString(Z, *Parts[2])
			|| !LexTryParseString(Yaw, *Parts[3]))
		{
			return false;
		}
		OutTransform = FTransform(
			FRotator(0.0, Yaw, 0.0), FVector(X, Y, Z),
			FVector(0.35, 1.8, 2.2));
		return FiniteTransform(OutTransform);
	}
}

AReplicatedDoorStateBase::AReplicatedDoorStateBase()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = true;
	bAlwaysRelevant = true;
	bNetLoadOnClient = true;
	SetReplicateMovement(false);
	SetNetUpdateFrequency(30.0f);
	SetMinNetUpdateFrequency(10.0f);
	Tags.Add(TEXT("ReplicatedDoorState"));

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	DoorMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DoorMesh"));
	DoorMesh->SetupAttachment(SceneRoot);
	DoorMesh->SetMobility(EComponentMobility::Movable);
	DoorMesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	DoorMesh->SetStaticMesh(Cube.Object);

	ClosedRelativeTransform = FTransform(
		FRotator::ZeroRotator, FVector::ZeroVector, FVector(0.35, 1.8, 2.2));
	OpenRelativeTransform = FTransform(
		FRotator(0.0, 73.0, 0.0), FVector(18.0, 132.0, 36.0),
		FVector(0.35, 1.8, 2.2));
	DoorMesh->SetRelativeTransform(ClosedRelativeTransform);
}

void AReplicatedDoorStateBase::BeginPlay()
{
	Super::BeginPlay();
	ApplyReplicatedRevision();
}

void AReplicatedDoorStateBase::GetLifetimeReplicatedProps(
	TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AReplicatedDoorStateBase, ClosedRelativeTransform);
	DOREPLIFETIME(AReplicatedDoorStateBase, OpenRelativeTransform);
}

int32 AReplicatedDoorStateBase::GetDoorRevision() const
{
	const FIntProperty* Property = FindFProperty<FIntProperty>(
		GetClass(), DoorRevisionName);
	return Property != nullptr
		? Property->GetPropertyValue_InContainer(this)
		: INDEX_NONE;
}

void AReplicatedDoorStateBase::ApplyReplicatedRevision()
{
	if (DoorMesh == nullptr)
	{
		return;
	}
	const int32 Revision = GetDoorRevision();
	if (Revision >= 0)
	{
		DoorMesh->SetRelativeTransform(
			(Revision & 1) != 0 ? OpenRelativeTransform : ClosedRelativeTransform);
	}
}

bool AReplicatedDoorStateBase::InvokeRequestToggle()
{
	UFunction* Function = FindFunction(RequestToggleName);
	if (Function == nullptr || Function->ParmsSize != 0)
	{
		return false;
	}
	ProcessEvent(Function, nullptr);
	return true;
}

bool AReplicatedDoorStateBase::ConfigureProtocolTransforms(
	const FTransform& InClosed, const FTransform& InOpen)
{
	if (!HasAuthority() || !FiniteTransform(InClosed)
		|| !FiniteTransform(InOpen) || NearlySameTransform(InClosed, InOpen))
	{
		return false;
	}
	ClosedRelativeTransform = InClosed;
	OpenRelativeTransform = InOpen;
	ApplyReplicatedRevision();
	ForceNetUpdate();
	return true;
}

void AReplicatedDoorStateBase::OnRep_ProtocolTransforms()
{
	ApplyReplicatedRevision();
}

bool AReplicatedDoorStateBase::IsAtClosedTransform() const
{
	return DoorMesh != nullptr
		&& NearlySameTransform(DoorMesh->GetRelativeTransform(), ClosedRelativeTransform);
}

bool AReplicatedDoorStateBase::IsAtOpenTransform() const
{
	return DoorMesh != nullptr
		&& NearlySameTransform(DoorMesh->GetRelativeTransform(), OpenRelativeTransform);
}

bool AReplicatedDoorStateBase::HasFiniteDoorTransform() const
{
	return DoorMesh != nullptr
		&& FiniteTransform(DoorMesh->GetRelativeTransform())
		&& FiniteTransform(ClosedRelativeTransform)
		&& FiniteTransform(OpenRelativeTransform);
}

AReplicatedDoorNetworkFunctionalTest::AReplicatedDoorNetworkFunctionalTest()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(TEXT("ReplicatedDoorNetworkFunctionalTest"));
	TimeLimit = 40.0f;
}

bool AReplicatedDoorNetworkFunctionalTest::ProtocolEnabled() const
{
	return FPlatformMisc::GetEnvironmentVariable(ProtocolEnv) == TEXT("1");
}

void AReplicatedDoorNetworkFunctionalTest::BeginPlay()
{
	Super::BeginPlay();
	if (!ProtocolEnabled())
	{
		return;
	}

	RunNonce = FPlatformMisc::GetEnvironmentVariable(NonceEnv);
	PeerId = FPlatformMisc::GetEnvironmentVariable(PeerEnv).ToUpper();
	FirstRequester = FPlatformMisc::GetEnvironmentVariable(
		FirstRequesterEnv).ToUpper();
	SecondRequester = FPlatformMisc::GetEnvironmentVariable(
		SecondRequesterEnv).ToUpper();
	if (GetNetMode() == NM_DedicatedServer)
	{
		PeerId = TEXT("SERVER");
	}
	FString Reason;
	if (!ValidateCommonHarness(Reason))
	{
		EmitHarnessError(Reason);
		return;
	}
	if (GetNetMode() == NM_DedicatedServer)
	{
		FTransform Closed;
		FTransform Open;
		if (!ParseProtocolTransform(
			FPlatformMisc::GetEnvironmentVariable(ClosedTransformEnv), Closed)
			|| !ParseProtocolTransform(
				FPlatformMisc::GetEnvironmentVariable(OpenTransformEnv), Open)
			|| !Door->ConfigureProtocolTransforms(Closed, Open))
		{
			EmitHarnessError(TEXT("PROTOCOL_TRANSFORMS_INVALID"));
			return;
		}
	}
	StartProtocolSeconds = FPlatformTime::Seconds();
	PhaseStartProtocolSeconds = StartProtocolSeconds;
	UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
		"DOOR-NETWORK-BOOT nonce=%s peer=%s net_mode=%s map=%s"),
		*RunNonce, *PeerId, *ToString(GetNetMode()),
		*GetWorld()->GetPackage()->GetName());
	bBootLogged = true;
	GetWorldTimerManager().SetTimer(PollTimer, this,
		&AReplicatedDoorNetworkFunctionalTest::PollProtocol, 0.05f, true);
}

void AReplicatedDoorNetworkFunctionalTest::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	GetWorldTimerManager().ClearTimer(PollTimer);
	Super::EndPlay(EndPlayReason);
}

bool AReplicatedDoorNetworkFunctionalTest::ValidateCommonHarness(
	FString& OutReason) const
{
	if (RunNonce.Len() != 32)
	{
		OutReason = TEXT("NONCE_INVALID");
		return false;
	}
	if ((FirstRequester != TEXT("A") && FirstRequester != TEXT("B"))
		|| (SecondRequester != TEXT("A") && SecondRequester != TEXT("B"))
		|| FirstRequester == SecondRequester)
	{
		OutReason = TEXT("REQUESTER_POLICY_INVALID");
		return false;
	}
	if (Door == nullptr || Door->GetClass() == AReplicatedDoorStateBase::StaticClass()
		|| Door->GetDoorRevision() == INDEX_NONE || Door->DoorMesh == nullptr)
	{
		OutReason = TEXT("DOOR_BINDING_INVALID");
		return false;
	}
	if (!Door->GetIsReplicated() || !Door->bAlwaysRelevant
		|| Door->IsReplicatingMovement() || !Door->HasFiniteDoorTransform()
		|| NearlySameTransform(Door->ClosedRelativeTransform,
			Door->OpenRelativeTransform))
	{
		OutReason = TEXT("DOOR_REPLICATION_OR_TRANSFORM_INVALID");
		return false;
	}
	if (GetWorld() == nullptr || GetWorld()->GetNetDriver() == nullptr
		|| !GetWorld()->GetNetDriver()->GetNetGuidCache().IsValid())
	{
		OutReason = TEXT("NET_DRIVER_INVALID");
		return false;
	}
	if (GetNetMode() != NM_DedicatedServer
		&& (GetNetMode() != NM_Client
			|| (PeerId != TEXT("A") && PeerId != TEXT("B")
				&& PeerId != TEXT("C"))))
	{
		OutReason = TEXT("PEER_ROLE_INVALID");
		return false;
	}
	return true;
}

FString AReplicatedDoorNetworkFunctionalTest::DoorNetGuid() const
{
	const UNetDriver* Driver = GetWorld() != nullptr
		? GetWorld()->GetNetDriver() : nullptr;
	const TSharedPtr<FNetGUIDCache> Cache = Driver != nullptr
		? Driver->GetNetGuidCache() : nullptr;
	if (!Cache.IsValid() || Door == nullptr)
	{
		return FString();
	}
	const FNetworkGUID Guid = Cache->GetNetGUID(Door);
	return Guid.IsValid() ? Guid.ToString() : FString();
}

TArray<APlayerController*>
AReplicatedDoorNetworkFunctionalTest::ServerPlayersByJoinOrder() const
{
	TArray<APlayerController*> Players;
	if (GetWorld() == nullptr)
	{
		return Players;
	}
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator();
		It; ++It)
	{
		APlayerController* Controller = It->Get();
		if (Controller != nullptr && Controller->PlayerState != nullptr)
		{
			Players.Add(Controller);
		}
	}
	Players.Sort([](const APlayerController& Left,
		const APlayerController& Right)
	{
		return Left.PlayerState->GetPlayerId()
			< Right.PlayerState->GetPlayerId();
	});
	return Players;
}

APlayerController* AReplicatedDoorNetworkFunctionalTest::LocalPlayerController() const
{
	return GetWorld() != nullptr ? GetWorld()->GetFirstPlayerController() : nullptr;
}

void AReplicatedDoorNetworkFunctionalTest::LogObservationIfChanged()
{
	if (Door == nullptr)
	{
		return;
	}
	const int32 Revision = Door->GetDoorRevision();
	const FString Guid = DoorNetGuid();
	if (Revision == LastObservedRevision || Revision < 0 || Guid.IsEmpty())
	{
		return;
	}
	LastObservedRevision = Revision;
	UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
		"DOOR-NETWORK-OBS nonce=%s peer=%s guid=%s revision=%d "
		"closed=%d open=%d finite=%d authority=%d local_owner=%d"),
		*RunNonce, *PeerId, *Guid, Revision,
		Door->IsAtClosedTransform() ? 1 : 0,
		Door->IsAtOpenTransform() ? 1 : 0,
		Door->HasFiniteDoorTransform() ? 1 : 0,
		Door->HasAuthority() ? 1 : 0,
		Door->HasLocalNetOwner() ? 1 : 0);
}

void AReplicatedDoorNetworkFunctionalTest::PollProtocol()
{
	if (bTerminal || GetWorld() == nullptr || Door == nullptr)
	{
		return;
	}
	const double Elapsed = FPlatformTime::Seconds() - StartProtocolSeconds;
	LogObservationIfChanged();
	if (GetNetMode() == NM_DedicatedServer)
	{
		PollServer(Elapsed);
	}
	else
	{
		PollClient(Elapsed);
	}
}

void AReplicatedDoorNetworkFunctionalTest::PollServer(const double Elapsed)
{
	if (!Door->HasAuthority())
	{
		EmitHarnessError(TEXT("SERVER_WITHOUT_AUTHORITY"));
		return;
	}
	const FString Guid = DoorNetGuid();
	if (Guid.IsEmpty())
	{
		if (Elapsed > 30.0)
		{
			EmitHarnessError(TEXT("SERVER_NETGUID_TIMEOUT"));
		}
		return;
	}
	const TArray<APlayerController*> Players = ServerPlayersByJoinOrder();
	APlayerController* FirstController = Players.IsValidIndex(0)
		? Players[0] : nullptr;
	APlayerController* SecondController = Players.IsValidIndex(1)
		? Players[1] : nullptr;
	APlayerController* LateController = Players.IsValidIndex(2)
		? Players[2] : nullptr;
	const double PhaseElapsed = FPlatformTime::Seconds()
		- PhaseStartProtocolSeconds;

	switch (ServerPhase)
	{
	case EServerPhase::WaitingInitialPeers:
		if (Players.Num() == 2)
		{
			Door->SetOwner(FirstController);
			Door->ForceNetUpdate();
			bReadyLogged = true;
			ServerPhase = EServerPhase::WaitingRevisionOne;
			PhaseStartProtocolSeconds = FPlatformTime::Seconds();
			UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
				"DOOR-NETWORK-READY nonce=%s peer=SERVER guid=%s "
				"initial_clients=2 owner=Door%s revision=%d"),
				*RunNonce, *Guid, *FirstRequester, Door->GetDoorRevision());
		}
		else if (Elapsed > 35.0)
		{
			EmitHarnessError(TEXT("INITIAL_CLIENTS_TIMEOUT"));
		}
		break;

	case EServerPhase::WaitingRevisionOne:
		if (Door->GetDoorRevision() == 1)
		{
			UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
				"DOOR-NETWORK-SERVER-REVISION nonce=%s guid=%s revision=1 open=%d"),
				*RunNonce, *Guid, Door->IsAtOpenTransform() ? 1 : 0);
			ServerPhase = EServerPhase::WaitingLatePeer;
			PhaseStartProtocolSeconds = FPlatformTime::Seconds();
		}
		else if (Door->GetDoorRevision() != 0)
		{
			EmitBehaviorFailure(TEXT("UNEXPECTED_FIRST_REVISION"));
		}
		else if (PhaseElapsed > 20.0)
		{
			EmitBehaviorFailure(TEXT("REVISION_ONE_TIMEOUT"));
		}
		break;

	case EServerPhase::WaitingLatePeer:
		if (Players.Num() == 3 && LateController != nullptr
			&& LatePeerConnectedSeconds < 0.0)
		{
			LatePeerConnectedSeconds = FPlatformTime::Seconds();
			UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
				"DOOR-NETWORK-LATE-CONNECTED nonce=%s guid=%s revision=%d"),
				*RunNonce, *Guid, Door->GetDoorRevision());
		}
		if (LatePeerConnectedSeconds >= 0.0
			&& FPlatformTime::Seconds() - LatePeerConnectedSeconds >= 2.0)
		{
			if (Door->GetDoorRevision() != 1 || SecondController == nullptr)
			{
				EmitBehaviorFailure(TEXT("LATE_JOIN_STATE_DID_NOT_HOLD"));
				break;
			}
			Door->SetOwner(SecondController);
			Door->ForceNetUpdate();
			UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
				"DOOR-NETWORK-OWNER nonce=%s guid=%s owner=Door%s revision=1"),
				*RunNonce, *Guid, *SecondRequester);
			ServerPhase = EServerPhase::WaitingRevisionTwo;
			PhaseStartProtocolSeconds = FPlatformTime::Seconds();
		}
		else if (PhaseElapsed > 30.0)
		{
			EmitHarnessError(TEXT("LATE_CLIENT_TIMEOUT"));
		}
		break;

	case EServerPhase::WaitingRevisionTwo:
		if (Door->GetDoorRevision() == 2)
		{
			UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
				"DOOR-NETWORK-SERVER-REVISION nonce=%s guid=%s revision=2 closed=%d"),
				*RunNonce, *Guid, Door->IsAtClosedTransform() ? 1 : 0);
			RevisionTwoObservedSeconds = FPlatformTime::Seconds();
			ServerPhase = EServerPhase::Settling;
		}
		else if (Door->GetDoorRevision() != 1)
		{
			EmitBehaviorFailure(TEXT("UNEXPECTED_SECOND_REVISION"));
		}
		else if (PhaseElapsed > 20.0)
		{
			EmitBehaviorFailure(TEXT("REVISION_TWO_TIMEOUT"));
		}
		break;

	case EServerPhase::Settling:
		if (FPlatformTime::Seconds() - RevisionTwoObservedSeconds >= 3.0)
		{
			EmitTerminalSuccess();
		}
		break;

	case EServerPhase::Terminal:
		break;
	}
}

void AReplicatedDoorNetworkFunctionalTest::PollClient(const double Elapsed)
{
	APlayerController* Controller = LocalPlayerController();
	const FString Guid = DoorNetGuid();
	if (Controller == nullptr || Guid.IsEmpty())
	{
		if (Elapsed > 35.0)
		{
			EmitHarnessError(TEXT("CLIENT_WORLD_OR_NETGUID_TIMEOUT"));
		}
		return;
	}
	if (!bReadyLogged)
	{
		bReadyLogged = true;
		UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
			"DOOR-NETWORK-READY nonce=%s peer=%s guid=%s revision=%d"),
			*RunNonce, *PeerId, *Guid, Door->GetDoorRevision());
	}

	const bool bShouldRequest =
		(PeerId == FirstRequester && Door->GetDoorRevision() == 0)
		|| (PeerId == SecondRequester && Door->GetDoorRevision() == 1);
	if (!bRequestAttempted && bShouldRequest && Door->HasLocalNetOwner())
	{
		bRequestAttempted = true;
		const int32 BeforeRevision = Door->GetDoorRevision();
		const FTransform BeforeTransform = Door->DoorMesh->GetRelativeTransform();
		const bool bInvoked = Door->InvokeRequestToggle();
		const int32 AfterRevision = Door->GetDoorRevision();
		const FTransform AfterTransform = Door->DoorMesh->GetRelativeTransform();
		const bool bUnchanged = BeforeRevision == AfterRevision
			&& NearlySameTransform(BeforeTransform, AfterTransform);
		UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
			"DOOR-NETWORK-REQUEST nonce=%s peer=%s guid=%s invoked=%d "
			"before_revision=%d after_revision=%d unchanged=%d"),
			*RunNonce, *PeerId, *Guid, bInvoked ? 1 : 0,
			BeforeRevision, AfterRevision, bUnchanged ? 1 : 0);
		if (!bInvoked || !bUnchanged)
		{
			EmitBehaviorFailure(!bInvoked
				? TEXT("REQUEST_EVENT_MISSING") : TEXT("REQUEST_CHANGED_LOCALLY"));
			return;
		}
	}

	if (Door->GetDoorRevision() == 2 && Door->IsAtClosedTransform())
	{
		if (RevisionTwoObservedSeconds < 0.0)
		{
			RevisionTwoObservedSeconds = FPlatformTime::Seconds();
		}
		else if (FPlatformTime::Seconds() - RevisionTwoObservedSeconds >= 1.0)
		{
			UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
				"DOOR-NETWORK-CLIENT-COMPLETE nonce=%s peer=%s guid=%s revision=2"),
				*RunNonce, *PeerId, *Guid);
			RequestProcessExit();
		}
	}
	else if (Elapsed > 60.0)
	{
		EmitBehaviorFailure(TEXT("CLIENT_CONVERGENCE_TIMEOUT"));
	}
}

void AReplicatedDoorNetworkFunctionalTest::EmitHarnessError(
	const FString& Reason)
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	ServerPhase = EServerPhase::Terminal;
	UE_LOG(LogDoorNetworkVerifier, Error, TEXT(
		"DOOR-NETWORK-HARNESS-ERROR nonce=%s peer=%s reason=%s"),
		*RunNonce, *PeerId, *Reason);
	RequestProcessExit();
}

void AReplicatedDoorNetworkFunctionalTest::EmitBehaviorFailure(
	const FString& Reason)
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	ServerPhase = EServerPhase::Terminal;
	UE_LOG(LogDoorNetworkVerifier, Error, TEXT(
		"DOOR-NETWORK-BEHAVIOR-FAIL nonce=%s peer=%s reason=%s revision=%d guid=%s"),
		*RunNonce, *PeerId, *Reason,
		Door != nullptr ? Door->GetDoorRevision() : INDEX_NONE,
		*DoorNetGuid());
	RequestProcessExit();
}

void AReplicatedDoorNetworkFunctionalTest::EmitTerminalSuccess()
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	ServerPhase = EServerPhase::Terminal;
	UE_LOG(LogDoorNetworkVerifier, Display, TEXT(
		"DOOR-NETWORK-SERVER-COMPLETE nonce=%s guid=%s revision=2 clients=3"),
		*RunNonce, *DoorNetGuid());
	RequestProcessExit();
}

void AReplicatedDoorNetworkFunctionalTest::RequestProcessExit()
{
	GetWorldTimerManager().ClearTimer(PollTimer);
	FPlatformMisc::RequestExit(false);
}
