// Copyright CraftBench. All Rights Reserved.

#include "PredictedDashProtectedTypes.h"

#include "Camera/CameraComponent.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Net/UnrealNetwork.h"
#include "PredictedDashMovementComponent.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

DEFINE_LOG_CATEGORY_STATIC(LogPredictedDashVerifier, Log, All);

namespace
{
	constexpr TCHAR ProtocolEnv[] = TEXT("CRAFTBENCH_DASH_PROTOCOL");
	constexpr TCHAR ScenarioEnv[] = TEXT("CRAFTBENCH_DASH_SCENARIO");
	constexpr TCHAR RunNonceEnv[] = TEXT("CRAFTBENCH_DASH_RUN_NONCE");
	constexpr TCHAR PeerEnv[] = TEXT("CRAFTBENCH_DASH_PEER");

	bool ParseVector(const FString& Text, FVector& Out)
	{
		TArray<FString> Parts;
		Text.ParseIntoArray(Parts, TEXT(","), true);
		return Parts.Num() == 3
			&& LexTryParseString(Out.X, *Parts[0])
			&& LexTryParseString(Out.Y, *Parts[1])
			&& LexTryParseString(Out.Z, *Parts[2])
			&& !Out.ContainsNaN();
	}

	bool ParseUIntEnv(const TCHAR* Name, uint32& Out)
	{
		return LexTryParseString(
			Out, *FPlatformMisc::GetEnvironmentVariable(Name)) && Out != 0;
	}

	bool ParseIntEnv(const TCHAR* Name, int32& Out)
	{
		return LexTryParseString(
			Out, *FPlatformMisc::GetEnvironmentVariable(Name));
	}

	bool ParseFloatEnv(const TCHAR* Name, float& Out)
	{
		return LexTryParseString(
			Out, *FPlatformMisc::GetEnvironmentVariable(Name))
			&& FMath::IsFinite(Out);
	}

	FString VectorToken(const FVector& Value)
	{
		return FString::Printf(TEXT("%.3f,%.3f,%.3f"),
			Value.X, Value.Y, Value.Z);
	}
}

APredictedDashCharacter::APredictedDashCharacter(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<
		UPredictedDashMovementComponent>(ACharacter::CharacterMovementComponentName))
{
	bReplicates = true;
	bAlwaysRelevant = true;
	SetReplicateMovement(true);
	SetNetUpdateFrequency(60.0f);
	SetMinNetUpdateFrequency(30.0f);

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(GetRootComponent());
	CameraBoom->TargetArmLength = 420.0f;
	CameraBoom->bUsePawnControlRotation = true;
	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(
		CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MannyMesh(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple."
			"SKM_Manny_Simple"));
	if (MannyMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMeshAsset(MannyMesh.Object);
		GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -90.0));
		GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	}
}

void APredictedDashCharacter::GetLifetimeReplicatedProps(
	TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(APredictedDashCharacter, bProtocolSubject);
	DOREPLIFETIME(APredictedDashCharacter, DashEnergy);
	DOREPLIFETIME(APredictedDashCharacter, AccountingRevision);
	DOREPLIFETIME(APredictedDashCharacter, CooldownRevision);
	DOREPLIFETIME(APredictedDashCharacter, AcceptedDashNonce);
	DOREPLIFETIME(APredictedDashCharacter, RejectedDashNonce);
	DOREPLIFETIME(APredictedDashCharacter, ProtocolStartLocation);
	DOREPLIFETIME(APredictedDashCharacter, AcceptedServerLocation);
	DOREPLIFETIME(APredictedDashCharacter, RejectedServerLocation);
}

bool APredictedDashCharacter::ConfigureScenario(
	const int32 InEnergy, const int32 InCost, const int32 InCooldownTicks,
	const uint32 InAcceptedNonce, const FVector& InAcceptedDirection,
	const float InAcceptedDistance, const uint32 InRejectedNonce,
	const FVector& InRejectedDirection, const float InRejectedDistance,
	const FVector& InStartLocation)
{
	if (!HasAuthority() || InEnergy <= InCost || InCost <= 0
		|| InCooldownTicks <= 0 || InAcceptedNonce == 0
		|| InRejectedNonce == 0 || InAcceptedNonce == InRejectedNonce
		|| InAcceptedDirection.GetSafeNormal2D().IsNearlyZero()
		|| InRejectedDirection.GetSafeNormal2D().IsNearlyZero()
		|| InAcceptedDistance < 100.0f || InRejectedDistance < 100.0f
		|| InStartLocation.ContainsNaN())
	{
		return false;
	}
	bProtocolSubject = true;
	DashEnergy = InEnergy;
	DashCost = InCost;
	CooldownTicks = InCooldownTicks;
	ExpectedAcceptedNonce = InAcceptedNonce;
	ExpectedRejectedNonce = InRejectedNonce;
	ExpectedAcceptedDirection = InAcceptedDirection.GetSafeNormal2D();
	ExpectedRejectedDirection = InRejectedDirection.GetSafeNormal2D();
	ExpectedAcceptedDistance = InAcceptedDistance;
	ExpectedRejectedDistance = InRejectedDistance;
	ProtocolStartLocation = InStartLocation;
	AcceptedServerLocation = FVector::ZeroVector;
	RejectedServerLocation = FVector::ZeroVector;
	AcceptedDashNonce = 0;
	RejectedDashNonce = 0;
	AccountingRevision = 0;
	CooldownRevision = 0;
	ProcessedNonces.Reset();
	SetActorLocation(InStartLocation, false, nullptr,
		ETeleportType::TeleportPhysics);
	ForceNetUpdate();
	return true;
}

bool APredictedDashCharacter::AuthorizeAndCommitDash(
	const FVector& Direction, const float Distance, const uint32 RequestNonce)
{
	if (!HasAuthority() || !bProtocolSubject || RequestNonce == 0
		|| ProcessedNonces.Contains(RequestNonce))
	{
		return false;
	}
	ProcessedNonces.Add(RequestNonce);
	const FVector UnitDirection = Direction.GetSafeNormal2D();
	const bool bAcceptedShape = RequestNonce == ExpectedAcceptedNonce
		&& UnitDirection.Equals(ExpectedAcceptedDirection, 0.002f)
		&& FMath::IsNearlyEqual(Distance, ExpectedAcceptedDistance, 0.2f);
	const bool bRejectedShape = RequestNonce == ExpectedRejectedNonce
		&& UnitDirection.Equals(ExpectedRejectedDirection, 0.002f)
		&& FMath::IsNearlyEqual(Distance, ExpectedRejectedDistance, 0.2f);
	if (bAcceptedShape && DashEnergy >= DashCost)
	{
		DashEnergy -= DashCost;
		++AccountingRevision;
		CooldownRevision += CooldownTicks;
		AcceptedDashNonce = static_cast<int32>(RequestNonce);
		ForceNetUpdate();
		return true;
	}
	RejectedDashNonce = static_cast<int32>(RequestNonce);
	RejectedServerLocation = GetActorLocation();
	if (!bRejectedShape)
	{
		UE_LOG(LogPredictedDashVerifier, Warning, TEXT(
			"DASH-NETWORK-POLICY-MISMATCH nonce=%u direction=%s distance=%.3f"),
			RequestNonce, *VectorToken(UnitDirection), Distance);
	}
	ForceNetUpdate();
	return false;
}

void APredictedDashCharacter::RecordAcceptedResolutionLocation()
{
	if (HasAuthority() && AcceptedDashNonce != 0)
	{
		AcceptedServerLocation = GetActorLocation();
		ForceNetUpdate();
	}
}

void APredictedDashCharacter::ClientIssueDash_Implementation(
	const FVector_NetQuantizeNormal Direction, const float Distance,
	const int32 RequestNonce)
{
	ClientRequestNonce = static_cast<uint32>(FMath::Max(RequestNonce, 0));
	ClientRequestDistance = Distance;
	ClientRequestBaseline = GetActorLocation();
	++ClientRequestSerial;
	bClientPredictionLogged = false;
	const FString Peer = FPlatformMisc::GetEnvironmentVariable(PeerEnv).ToUpper();
	UE_LOG(LogPredictedDashVerifier, Display, TEXT(
		"DASH-NETWORK-REQUEST nonce=%s peer=%s request=%d baseline=%s "
		"direction=%s distance=%.3f accepted_ack=%d rejected_ack=%d"),
		*FPlatformMisc::GetEnvironmentVariable(RunNonceEnv), *Peer,
		RequestNonce, *VectorToken(ClientRequestBaseline),
		*VectorToken(Direction), Distance, AcceptedDashNonce, RejectedDashNonce);
	if (UPredictedDashMovementComponent* Movement =
		Cast<UPredictedDashMovementComponent>(GetCharacterMovement()))
	{
		Movement->RequestPredictedDash(
			Direction, Distance, static_cast<uint32>(RequestNonce));
	}
}

APredictedDashGameMode::APredictedDashGameMode()
{
	DefaultPawnClass = APredictedDashCharacter::StaticClass();
	PlayerControllerClass = APlayerController::StaticClass();
	bStartPlayersAsSpectators = false;
}

APredictedDashNetworkFunctionalTestBase::
	APredictedDashNetworkFunctionalTestBase()
{
	PrimaryActorTick.bCanEverTick = false;
	TimeLimit = 55.0f;
}

APredictedDashNetworkFunctionalTestA::
	APredictedDashNetworkFunctionalTestA()
{
	ScenarioId = TEXT("A");
	Tags.Add(TEXT("PredictedDashFixtureA"));
}

APredictedDashNetworkFunctionalTestB::
	APredictedDashNetworkFunctionalTestB()
{
	ScenarioId = TEXT("B");
	Tags.Add(TEXT("PredictedDashFixtureB"));
}

void APredictedDashNetworkFunctionalTestBase::BeginPlay()
{
	Super::BeginPlay();
	if (FPlatformMisc::GetEnvironmentVariable(ProtocolEnv) != TEXT("1")
		|| !FPlatformMisc::GetEnvironmentVariable(ScenarioEnv).Equals(
			ScenarioId, ESearchCase::IgnoreCase))
	{
		return;
	}
	RunNonce = FPlatformMisc::GetEnvironmentVariable(RunNonceEnv);
	PeerId = GetNetMode() == NM_DedicatedServer ? TEXT("SERVER")
		: FPlatformMisc::GetEnvironmentVariable(PeerEnv).ToUpper();
	FString Reason;
	if (!ValidateCommonHarness(Reason)
		|| (GetNetMode() == NM_DedicatedServer && !ReadServerPolicy(Reason)))
	{
		EmitHarnessError(Reason);
		return;
	}
	StartSeconds = FPlatformTime::Seconds();
	PhaseSeconds = StartSeconds;
	UE_LOG(LogPredictedDashVerifier, Display, TEXT(
		"DASH-NETWORK-BOOT nonce=%s scenario=%s peer=%s net_mode=%s"),
		*RunNonce, *ScenarioId, *PeerId, *ToString(GetNetMode()));
	bBootLogged = true;
	GetWorldTimerManager().SetTimer(PollTimer, this,
		&APredictedDashNetworkFunctionalTestBase::PollProtocol,
		0.025f, true);
}

void APredictedDashNetworkFunctionalTestBase::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	GetWorldTimerManager().ClearTimer(PollTimer);
	Super::EndPlay(EndPlayReason);
}

bool APredictedDashNetworkFunctionalTestBase::ValidateCommonHarness(
	FString& OutReason) const
{
	if (RunNonce.Len() != 32)
	{
		OutReason = TEXT("RUN_NONCE_INVALID");
		return false;
	}
	if (ScenarioId != TEXT("A") && ScenarioId != TEXT("B"))
	{
		OutReason = TEXT("SCENARIO_INVALID");
		return false;
	}
	if (GetWorld() == nullptr || GetWorld()->GetNetDriver() == nullptr)
	{
		OutReason = TEXT("NET_DRIVER_INVALID");
		return false;
	}
	if (GetNetMode() != NM_DedicatedServer
		&& (GetNetMode() != NM_Client
			|| (PeerId != TEXT("OWNER") && PeerId != TEXT("OBSERVER"))))
	{
		OutReason = TEXT("ROLE_INVALID");
		return false;
	}
	return true;
}

bool APredictedDashNetworkFunctionalTestBase::ReadServerPolicy(
	FString& OutReason)
{
	int32 FirstAccepted = 0;
	if (!ParseIntEnv(TEXT("CRAFTBENCH_DASH_FIRST_ACCEPTED"), FirstAccepted)
		|| (FirstAccepted != 0 && FirstAccepted != 1)
		|| !ParseIntEnv(TEXT("CRAFTBENCH_DASH_INITIAL_ENERGY"), InitialEnergy)
		|| !ParseIntEnv(TEXT("CRAFTBENCH_DASH_COST"), Cost)
		|| !ParseIntEnv(TEXT("CRAFTBENCH_DASH_COOLDOWN_TICKS"), CooldownTicks)
		|| !ParseUIntEnv(TEXT("CRAFTBENCH_DASH_ACCEPT_NONCE"), AcceptedNonce)
		|| !ParseUIntEnv(TEXT("CRAFTBENCH_DASH_REJECT_NONCE"), RejectedNonce)
		|| !ParseVector(FPlatformMisc::GetEnvironmentVariable(
			TEXT("CRAFTBENCH_DASH_ACCEPT_DIRECTION")), AcceptedDirection)
		|| !ParseVector(FPlatformMisc::GetEnvironmentVariable(
			TEXT("CRAFTBENCH_DASH_REJECT_DIRECTION")), RejectedDirection)
		|| !ParseFloatEnv(TEXT("CRAFTBENCH_DASH_ACCEPT_DISTANCE"),
			AcceptedDistance)
		|| !ParseFloatEnv(TEXT("CRAFTBENCH_DASH_REJECT_DISTANCE"),
			RejectedDistance)
		|| !ParseVector(FPlatformMisc::GetEnvironmentVariable(
			TEXT("CRAFTBENCH_DASH_START")), StartLocation)
		|| InitialEnergy <= Cost || Cost <= 0 || CooldownTicks <= 0
		|| AcceptedNonce == RejectedNonce || AcceptedDistance < 100.0f
		|| RejectedDistance < 100.0f)
	{
		OutReason = TEXT("SERVER_POLICY_INVALID");
		return false;
	}
	bFirstAccepted = FirstAccepted != 0;
	return true;
}

TArray<APlayerController*>
APredictedDashNetworkFunctionalTestBase::ServerPlayersByJoinOrder() const
{
	TArray<APlayerController*> Players;
	for (FConstPlayerControllerIterator It =
		GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		APlayerController* Controller = It->Get();
		if (Controller != nullptr && Controller->PlayerState != nullptr
			&& Controller->GetPawn() != nullptr)
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

APredictedDashCharacter*
APredictedDashNetworkFunctionalTestBase::FindProtocolSubject() const
{
	for (TActorIterator<APredictedDashCharacter> It(GetWorld()); It; ++It)
	{
		if (It->IsProtocolSubject())
		{
			return *It;
		}
	}
	return nullptr;
}

void APredictedDashNetworkFunctionalTestBase::PollProtocol()
{
	if (bTerminal || GetWorld() == nullptr)
	{
		return;
	}
	const double Now = FPlatformTime::Seconds();
	if (GetNetMode() == NM_DedicatedServer)
	{
		PollServer(Now);
	}
	else
	{
		PollClient(Now);
	}
}

void APredictedDashNetworkFunctionalTestBase::IssueRequest(
	const bool bAcceptedRequest)
{
	APredictedDashCharacter* DashSubject = Subject.Get();
	if (DashSubject == nullptr)
	{
		EmitHarnessError(TEXT("SUBJECT_LOST_BEFORE_REQUEST"));
		return;
	}
	DashSubject->ClientIssueDash(
		bAcceptedRequest ? AcceptedDirection : RejectedDirection,
		bAcceptedRequest ? AcceptedDistance : RejectedDistance,
		static_cast<int32>(bAcceptedRequest ? AcceptedNonce : RejectedNonce));
	UE_LOG(LogPredictedDashVerifier, Display, TEXT(
		"DASH-NETWORK-SERVER-ISSUE nonce=%s scenario=%s request=%u "
		"expected=%s direction=%s distance=%.3f baseline=%s"),
		*RunNonce, *ScenarioId,
		bAcceptedRequest ? AcceptedNonce : RejectedNonce,
		bAcceptedRequest ? TEXT("accept") : TEXT("reject"),
		*VectorToken(bAcceptedRequest ? AcceptedDirection : RejectedDirection),
		bAcceptedRequest ? AcceptedDistance : RejectedDistance,
		*VectorToken(DashSubject->GetActorLocation()));
}

bool APredictedDashNetworkFunctionalTestBase::RequestResolved(
	const bool bAcceptedRequest) const
{
	const APredictedDashCharacter* DashSubject = Subject.Get();
	return DashSubject != nullptr && (bAcceptedRequest
		? DashSubject->GetAcceptedDashNonce() == static_cast<int32>(AcceptedNonce)
		: DashSubject->GetRejectedDashNonce() == static_cast<int32>(RejectedNonce));
}

void APredictedDashNetworkFunctionalTestBase::PollServer(const double Now)
{
	const double Elapsed = Now - StartSeconds;
	const double PhaseElapsed = Now - PhaseSeconds;
	APredictedDashCharacter* DashSubject = Subject.Get();
	switch (ServerPhase)
	{
	case EServerPhase::WaitingPlayers:
	{
		const TArray<APlayerController*> Players = ServerPlayersByJoinOrder();
		if (Players.Num() == 2)
		{
			DashSubject = Cast<APredictedDashCharacter>(Players[0]->GetPawn());
			if (DashSubject == nullptr || !DashSubject->ConfigureScenario(
				InitialEnergy, Cost, CooldownTicks, AcceptedNonce,
				AcceptedDirection, AcceptedDistance, RejectedNonce,
				RejectedDirection, RejectedDistance, StartLocation))
			{
				EmitHarnessError(TEXT("SUBJECT_CONFIGURATION_FAILED"));
				return;
			}
			Subject = DashSubject;
			ServerPhase = EServerPhase::Stabilizing;
			PhaseSeconds = Now;
			UE_LOG(LogPredictedDashVerifier, Display, TEXT(
				"DASH-NETWORK-SERVER-READY nonce=%s scenario=%s players=2 "
				"first=%s energy=%d cost=%d cooldown=%d start=%s"),
				*RunNonce, *ScenarioId,
				bFirstAccepted ? TEXT("accept") : TEXT("reject"),
				InitialEnergy, Cost, CooldownTicks,
				*VectorToken(StartLocation));
		}
		else if (Elapsed > 35.0)
		{
			EmitHarnessError(TEXT("TWO_PLAYERS_TIMEOUT"));
		}
		break;
	}
	case EServerPhase::Stabilizing:
		if (PhaseElapsed >= 2.0)
		{
			IssueRequest(bFirstAccepted);
			ServerPhase = EServerPhase::WaitingFirst;
			PhaseSeconds = Now;
		}
		break;
	case EServerPhase::WaitingFirst:
		if (RequestResolved(bFirstAccepted))
		{
			if (bFirstAccepted)
			{
				DashSubject->RecordAcceptedResolutionLocation();
			}
			UE_LOG(LogPredictedDashVerifier, Display, TEXT(
				"DASH-NETWORK-SERVER-RESOLVE nonce=%s scenario=%s request=%u "
				"result=%s location=%s energy=%d accounting=%d cooldown=%d"),
				*RunNonce, *ScenarioId,
				bFirstAccepted ? AcceptedNonce : RejectedNonce,
				bFirstAccepted ? TEXT("accepted") : TEXT("rejected"),
				*VectorToken(DashSubject->GetActorLocation()),
				DashSubject->GetDashEnergy(),
				DashSubject->GetAccountingRevision(),
				DashSubject->GetCooldownRevision());
			ServerPhase = EServerPhase::SettlingFirst;
			PhaseSeconds = Now;
		}
		else if (PhaseElapsed > 15.0)
		{
			EmitBehaviorFailure(TEXT("FIRST_REQUEST_TIMEOUT"));
		}
		break;
	case EServerPhase::SettlingFirst:
		if (PhaseElapsed >= 3.0)
		{
			IssueRequest(!bFirstAccepted);
			ServerPhase = EServerPhase::WaitingSecond;
			PhaseSeconds = Now;
		}
		break;
	case EServerPhase::WaitingSecond:
		if (RequestResolved(!bFirstAccepted))
		{
			if (!bFirstAccepted)
			{
				DashSubject->RecordAcceptedResolutionLocation();
			}
			UE_LOG(LogPredictedDashVerifier, Display, TEXT(
				"DASH-NETWORK-SERVER-RESOLVE nonce=%s scenario=%s request=%u "
				"result=%s location=%s energy=%d accounting=%d cooldown=%d"),
				*RunNonce, *ScenarioId,
				bFirstAccepted ? RejectedNonce : AcceptedNonce,
				bFirstAccepted ? TEXT("rejected") : TEXT("accepted"),
				*VectorToken(DashSubject->GetActorLocation()),
				DashSubject->GetDashEnergy(),
				DashSubject->GetAccountingRevision(),
				DashSubject->GetCooldownRevision());
			const bool bExact = DashSubject->GetDashEnergy()
				== InitialEnergy - Cost
				&& DashSubject->GetAccountingRevision() == 1
				&& DashSubject->GetCooldownRevision() == CooldownTicks
				&& DashSubject->GetAcceptedDashNonce()
					== static_cast<int32>(AcceptedNonce)
				&& DashSubject->GetRejectedDashNonce()
					== static_cast<int32>(RejectedNonce);
			if (!bExact)
			{
				EmitBehaviorFailure(TEXT("AUTHORITY_ACCOUNTING_INVALID"));
				return;
			}
			UE_LOG(LogPredictedDashVerifier, Display, TEXT(
				"DASH-NETWORK-SERVER-COMPLETE nonce=%s scenario=%s "
				"energy=%d accounting=1 cooldown=%d accepted=%u rejected=%u "
				"start=%s accepted_location=%s rejected_location=%s final=%s"),
				*RunNonce, *ScenarioId, DashSubject->GetDashEnergy(),
				CooldownTicks, AcceptedNonce, RejectedNonce,
				*VectorToken(DashSubject->GetProtocolStartLocation()),
				*VectorToken(DashSubject->GetAcceptedServerLocation()),
				*VectorToken(DashSubject->GetRejectedServerLocation()),
				*VectorToken(DashSubject->GetActorLocation()));
			ServerPhase = EServerPhase::SettlingFinal;
			PhaseSeconds = Now;
		}
		else if (PhaseElapsed > 15.0)
		{
			EmitBehaviorFailure(TEXT("SECOND_REQUEST_TIMEOUT"));
		}
		break;
	case EServerPhase::SettlingFinal:
		// The clients need one stable replicated second to emit their terminal
		// observations.  They may disconnect immediately afterward, so all
		// authority facts were validated and logged while the subject was live.
		if (PhaseElapsed >= 2.0)
		{
			bTerminal = true;
			ServerPhase = EServerPhase::Terminal;
			RequestProcessExit();
		}
		break;
	case EServerPhase::Terminal:
		break;
	}
}

void APredictedDashNetworkFunctionalTestBase::PollClient(const double Now)
{
	APredictedDashCharacter* DashSubject = FindProtocolSubject();
	if (DashSubject == nullptr)
	{
		if (Now - StartSeconds > 35.0)
		{
			EmitHarnessError(TEXT("CLIENT_SUBJECT_TIMEOUT"));
		}
		return;
	}
	Subject = DashSubject;
	const bool bOwner = DashSubject->IsLocallyControlled()
		&& DashSubject->GetLocalRole() == ROLE_AutonomousProxy;
	const bool bSimulated = DashSubject->GetLocalRole() == ROLE_SimulatedProxy;
	if (!bClientReadyLogged)
	{
		if ((PeerId == TEXT("OWNER")) != bOwner
			|| (PeerId == TEXT("OBSERVER")) != bSimulated)
		{
			EmitHarnessError(TEXT("SUBJECT_ROLE_ASSIGNMENT_INVALID"));
			return;
		}
		bClientReadyLogged = true;
		InitialEnergy = DashSubject->GetDashEnergy();
		UE_LOG(LogPredictedDashVerifier, Display, TEXT(
			"DASH-NETWORK-CLIENT-READY nonce=%s scenario=%s peer=%s role=%s "
			"start=%s energy=%d"),
			*RunNonce, *ScenarioId, *PeerId,
			bOwner ? TEXT("autonomous") : TEXT("simulated"),
			*VectorToken(DashSubject->GetProtocolStartLocation()),
			DashSubject->GetDashEnergy());
	}

	if (bOwner && DashSubject->GetClientRequestSerial()
		!= LastClientRequestSerial)
	{
		LastClientRequestSerial = DashSubject->GetClientRequestSerial();
	}
	if (bOwner && LastClientRequestSerial > 0
		&& !DashSubject->IsClientPredictionLogged())
	{
		const float Delta = FVector::Dist2D(
			DashSubject->GetActorLocation(),
			DashSubject->GetClientRequestBaseline());
		const uint32 Request = DashSubject->GetClientRequestNonce();
		const bool bAcknowledged = DashSubject->GetAcceptedDashNonce()
			== static_cast<int32>(Request)
			|| DashSubject->GetRejectedDashNonce()
				== static_cast<int32>(Request);
		if (Delta >= FMath::Max(30.0f,
			DashSubject->GetClientRequestDistance() * 0.20f)
			&& !bAcknowledged)
		{
			DashSubject->MarkClientPredictionLogged();
			UE_LOG(LogPredictedDashVerifier, Display, TEXT(
				"DASH-NETWORK-PREDICT nonce=%s scenario=%s peer=OWNER "
				"request=%u displacement=%.3f before_ack=1 location=%s"),
				*RunNonce, *ScenarioId, Request, Delta,
				*VectorToken(DashSubject->GetActorLocation()));
		}
	}

	if (bSimulated && !bSimulatedObserved
		&& DashSubject->GetAcceptedDashNonce() != 0
		&& !DashSubject->GetAcceptedServerLocation().IsNearlyZero()
		&& FVector::Dist2D(DashSubject->GetActorLocation(),
			DashSubject->GetProtocolStartLocation()) >= 50.0f)
	{
		bSimulatedObserved = true;
		UE_LOG(LogPredictedDashVerifier, Display, TEXT(
			"DASH-NETWORK-SIMULATED nonce=%s scenario=%s peer=OBSERVER "
			"accepted=%d displacement=%.3f count=1 location=%s"),
			*RunNonce, *ScenarioId, DashSubject->GetAcceptedDashNonce(),
			FVector::Dist2D(DashSubject->GetActorLocation(),
				DashSubject->GetProtocolStartLocation()),
			*VectorToken(DashSubject->GetActorLocation()));
	}

	if (!bAcceptedConverged && DashSubject->GetAcceptedDashNonce() != 0
		&& !DashSubject->GetAcceptedServerLocation().IsNearlyZero()
		&& FVector::Dist2D(DashSubject->GetActorLocation(),
			DashSubject->GetAcceptedServerLocation()) <= 18.0f)
	{
		bAcceptedConverged = true;
		UE_LOG(LogPredictedDashVerifier, Display, TEXT(
			"DASH-NETWORK-CONVERGED nonce=%s scenario=%s peer=%s "
			"accepted=%d error=%.3f"),
			*RunNonce, *ScenarioId, *PeerId,
			DashSubject->GetAcceptedDashNonce(),
			FVector::Dist2D(DashSubject->GetActorLocation(),
				DashSubject->GetAcceptedServerLocation()));
	}

	if (bOwner && !bRejectedRolledBack
		&& DashSubject->GetRejectedDashNonce() != 0
		&& !DashSubject->GetRejectedServerLocation().IsNearlyZero()
		&& FVector::Dist2D(DashSubject->GetActorLocation(),
			DashSubject->GetRejectedServerLocation()) <= 18.0f)
	{
		bRejectedRolledBack = true;
		UE_LOG(LogPredictedDashVerifier, Display, TEXT(
			"DASH-NETWORK-ROLLBACK nonce=%s scenario=%s peer=OWNER "
			"rejected=%d error=%.3f energy=%d accounting=%d cooldown=%d"),
			*RunNonce, *ScenarioId, DashSubject->GetRejectedDashNonce(),
			FVector::Dist2D(DashSubject->GetActorLocation(),
				DashSubject->GetRejectedServerLocation()),
			DashSubject->GetDashEnergy(),
			DashSubject->GetAccountingRevision(),
			DashSubject->GetCooldownRevision());
	}

	const bool bResultsComplete = DashSubject->GetAcceptedDashNonce() != 0
		&& DashSubject->GetRejectedDashNonce() != 0
		&& DashSubject->GetAccountingRevision() == 1
		&& DashSubject->GetCooldownRevision() > 0
		&& DashSubject->GetDashEnergy() < InitialEnergy;
	const bool bPeerComplete = bOwner
		? bAcceptedConverged && bRejectedRolledBack
		: bAcceptedConverged && bSimulatedObserved;
	if (bResultsComplete && bPeerComplete)
	{
		if (StableSeconds < 0.0)
		{
			StableSeconds = Now;
		}
		else if (Now - StableSeconds >= 1.0)
		{
			UE_LOG(LogPredictedDashVerifier, Display, TEXT(
				"DASH-NETWORK-CLIENT-COMPLETE nonce=%s scenario=%s peer=%s "
				"role=%s predicted=%d simulated_count=%d converged=1 rollback=%d "
				"energy=%d accounting=%d cooldown=%d final=%s"),
				*RunNonce, *ScenarioId, *PeerId,
				bOwner ? TEXT("autonomous") : TEXT("simulated"),
				bOwner ? 1 : 0, bSimulatedObserved ? 1 : 0,
				bRejectedRolledBack ? 1 : 0,
				DashSubject->GetDashEnergy(),
				DashSubject->GetAccountingRevision(),
				DashSubject->GetCooldownRevision(),
				*VectorToken(DashSubject->GetActorLocation()));
			bTerminal = true;
			RequestProcessExit();
		}
	}
	else
	{
		StableSeconds = -1.0;
	}
	if (Now - StartSeconds > 50.0)
	{
		EmitBehaviorFailure(TEXT("CLIENT_PROTOCOL_TIMEOUT"));
	}
}

void APredictedDashNetworkFunctionalTestBase::EmitHarnessError(
	const FString& Reason)
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	UE_LOG(LogPredictedDashVerifier, Error, TEXT(
		"DASH-NETWORK-HARNESS-ERROR nonce=%s scenario=%s peer=%s reason=%s"),
		*RunNonce, *ScenarioId, *PeerId, *Reason);
	RequestProcessExit();
}

void APredictedDashNetworkFunctionalTestBase::EmitBehaviorFailure(
	const FString& Reason)
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	UE_LOG(LogPredictedDashVerifier, Error, TEXT(
		"DASH-NETWORK-BEHAVIOR-FAIL nonce=%s scenario=%s peer=%s reason=%s"),
		*RunNonce, *ScenarioId, *PeerId, *Reason);
	RequestProcessExit();
}

void APredictedDashNetworkFunctionalTestBase::RequestProcessExit()
{
	GetWorldTimerManager().ClearTimer(PollTimer);
	FPlatformMisc::RequestExit(false);
}
