// Copyright CraftBench. All Rights Reserved.
// PROTECTED TASK SUPPORT - NOT PART OF THE EDITABLE SUBMISSION.

#pragma once

#include "CoreMinimal.h"
#include "Engine/NetSerialization.h"
#include "FunctionalTest.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "PredictedDashProtectedTypes.generated.h"

class UCameraComponent;
class USpringArmComponent;

UCLASS()
class THIRDPERSON_API APredictedDashCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	explicit APredictedDashCharacter(
		const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
	virtual void GetLifetimeReplicatedProps(
		TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	bool ConfigureScenario(
		int32 InEnergy, int32 InCost, int32 InCooldownTicks,
		uint32 InAcceptedNonce, const FVector& InAcceptedDirection,
		float InAcceptedDistance, uint32 InRejectedNonce,
		const FVector& InRejectedDirection, float InRejectedDistance,
		const FVector& InStartLocation);
	bool AuthorizeAndCommitDash(
		const FVector& Direction, float Distance, uint32 RequestNonce);
	void RecordAcceptedResolutionLocation();

	UFUNCTION(Client, Reliable)
	void ClientIssueDash(
		FVector_NetQuantizeNormal Direction, float Distance,
		int32 RequestNonce);

	bool IsProtocolSubject() const { return bProtocolSubject; }
	int32 GetDashEnergy() const { return DashEnergy; }
	int32 GetAccountingRevision() const { return AccountingRevision; }
	int32 GetCooldownRevision() const { return CooldownRevision; }
	int32 GetAcceptedDashNonce() const { return AcceptedDashNonce; }
	int32 GetRejectedDashNonce() const { return RejectedDashNonce; }
	const FVector& GetProtocolStartLocation() const
		{ return ProtocolStartLocation; }
	const FVector& GetAcceptedServerLocation() const
		{ return AcceptedServerLocation; }
	const FVector& GetRejectedServerLocation() const
		{ return RejectedServerLocation; }

	int32 GetClientRequestSerial() const { return ClientRequestSerial; }
	uint32 GetClientRequestNonce() const { return ClientRequestNonce; }
	float GetClientRequestDistance() const { return ClientRequestDistance; }
	const FVector& GetClientRequestBaseline() const
		{ return ClientRequestBaseline; }
	bool IsClientPredictionLogged() const { return bClientPredictionLogged; }
	void MarkClientPredictionLogged() { bClientPredictionLogged = true; }

	UPROPERTY(VisibleAnywhere, Category = "CraftBench|Dash")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, Category = "CraftBench|Dash")
	TObjectPtr<UCameraComponent> FollowCamera;

private:
	UPROPERTY(Replicated)
	bool bProtocolSubject = false;

	UPROPERTY(Replicated)
	int32 DashEnergy = 0;

	UPROPERTY(Replicated)
	int32 AccountingRevision = 0;

	UPROPERTY(Replicated)
	int32 CooldownRevision = 0;

	UPROPERTY(Replicated)
	int32 AcceptedDashNonce = 0;

	UPROPERTY(Replicated)
	int32 RejectedDashNonce = 0;

	UPROPERTY(Replicated)
	FVector ProtocolStartLocation = FVector::ZeroVector;

	UPROPERTY(Replicated)
	FVector AcceptedServerLocation = FVector::ZeroVector;

	UPROPERTY(Replicated)
	FVector RejectedServerLocation = FVector::ZeroVector;

	int32 DashCost = 0;
	int32 CooldownTicks = 0;
	uint32 ExpectedAcceptedNonce = 0;
	uint32 ExpectedRejectedNonce = 0;
	FVector ExpectedAcceptedDirection = FVector::ZeroVector;
	FVector ExpectedRejectedDirection = FVector::ZeroVector;
	float ExpectedAcceptedDistance = 0.0f;
	float ExpectedRejectedDistance = 0.0f;
	TSet<uint32> ProcessedNonces;

	int32 ClientRequestSerial = 0;
	uint32 ClientRequestNonce = 0;
	float ClientRequestDistance = 0.0f;
	FVector ClientRequestBaseline = FVector::ZeroVector;
	bool bClientPredictionLogged = false;
};

UCLASS()
class THIRDPERSON_API APredictedDashGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	APredictedDashGameMode();
};

UCLASS(Abstract)
class THIRDPERSON_API APredictedDashNetworkFunctionalTestBase
	: public AFunctionalTest
{
	GENERATED_BODY()

public:
	APredictedDashNetworkFunctionalTestBase();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	FString ScenarioId;

private:
	enum class EServerPhase : uint8
	{
		WaitingPlayers,
		Stabilizing,
		WaitingFirst,
		SettlingFirst,
		WaitingSecond,
		SettlingFinal,
		Terminal,
	};

	void PollProtocol();
	void PollServer(double Now);
	void PollClient(double Now);
	bool ReadServerPolicy(FString& OutReason);
	bool ValidateCommonHarness(FString& OutReason) const;
	APredictedDashCharacter* FindProtocolSubject() const;
	TArray<APlayerController*> ServerPlayersByJoinOrder() const;
	void IssueRequest(bool bAcceptedRequest);
	bool RequestResolved(bool bAcceptedRequest) const;
	void EmitHarnessError(const FString& Reason);
	void EmitBehaviorFailure(const FString& Reason);
	void RequestProcessExit();

	FTimerHandle PollTimer;
	FString RunNonce;
	FString PeerId;
	double StartSeconds = 0.0;
	double PhaseSeconds = 0.0;
	double StableSeconds = -1.0;
	EServerPhase ServerPhase = EServerPhase::WaitingPlayers;
	TWeakObjectPtr<APredictedDashCharacter> Subject;
	bool bFirstAccepted = true;
	bool bBootLogged = false;
	bool bClientReadyLogged = false;
	bool bSimulatedObserved = false;
	bool bAcceptedConverged = false;
	bool bRejectedRolledBack = false;
	bool bTerminal = false;
	int32 LastClientRequestSerial = 0;
	int32 InitialEnergy = 0;
	int32 Cost = 0;
	int32 CooldownTicks = 0;
	uint32 AcceptedNonce = 0;
	uint32 RejectedNonce = 0;
	FVector AcceptedDirection = FVector::ZeroVector;
	FVector RejectedDirection = FVector::ZeroVector;
	float AcceptedDistance = 0.0f;
	float RejectedDistance = 0.0f;
	FVector StartLocation = FVector::ZeroVector;
};

UCLASS()
class THIRDPERSON_API APredictedDashNetworkFunctionalTestA final
	: public APredictedDashNetworkFunctionalTestBase
{
	GENERATED_BODY()

public:
	APredictedDashNetworkFunctionalTestA();
};

UCLASS()
class THIRDPERSON_API APredictedDashNetworkFunctionalTestB final
	: public APredictedDashNetworkFunctionalTestBase
{
	GENERATED_BODY()

public:
	APredictedDashNetworkFunctionalTestB();
};
