// Copyright CraftBench. All Rights Reserved.
// PROTECTED TASK SUPPORT - NOT PART OF THE EDITABLE SUBMISSION.

#pragma once

#include "CoreMinimal.h"
#include "FunctionalTest.h"
#include "GameFramework/Actor.h"
#include "ReplicatedDoorTypes.generated.h"

class APlayerController;
class UStaticMeshComponent;
class USceneComponent;

/** Native, verifier-owned surface for the one editable Door Blueprint. */
UCLASS(Blueprintable)
class THIRDPERSON_API AReplicatedDoorStateBase : public AActor
{
	GENERATED_BODY()

public:
	AReplicatedDoorStateBase();
	virtual void BeginPlay() override;
	virtual void GetLifetimeReplicatedProps(
		TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Door")
	void ApplyReplicatedRevision();

	UFUNCTION(BlueprintPure, Category = "CraftBench|Door")
	int32 GetDoorRevision() const;

	/** Protected fixture hook. It calls the candidate-authored RequestToggle event. */
	bool InvokeRequestToggle();
	bool ConfigureProtocolTransforms(
		const FTransform& InClosed, const FTransform& InOpen);

	bool IsAtClosedTransform() const;
	bool IsAtOpenTransform() const;
	bool HasFiniteDoorTransform() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench|Door")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench|Door")
	TObjectPtr<UStaticMeshComponent> DoorMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, ReplicatedUsing = OnRep_ProtocolTransforms,
		Category = "CraftBench|Door")
	FTransform ClosedRelativeTransform = FTransform::Identity;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, ReplicatedUsing = OnRep_ProtocolTransforms,
		Category = "CraftBench|Door")
	FTransform OpenRelativeTransform = FTransform::Identity;

private:
	UFUNCTION()
	void OnRep_ProtocolTransforms();
};

/**
 * Protected ordinary-process protocol actor. The custom L2 runner launches one
 * dedicated server, two initial clients, and one late client; this class emits
 * only verifier-owned facts from each real network world.
 */
UCLASS()
class THIRDPERSON_API AReplicatedDoorNetworkFunctionalTest
	: public AFunctionalTest
{
	GENERATED_BODY()

public:
	AReplicatedDoorNetworkFunctionalTest();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Door")
	TObjectPtr<AReplicatedDoorStateBase> Door;

private:
	enum class EServerPhase : uint8
	{
		WaitingInitialPeers,
		WaitingRevisionOne,
		WaitingLatePeer,
		WaitingRevisionTwo,
		Settling,
		Terminal,
	};

	void PollProtocol();
	void PollServer(double Elapsed);
	void PollClient(double Elapsed);
	void LogObservationIfChanged();
	void EmitHarnessError(const FString& Reason);
	void EmitBehaviorFailure(const FString& Reason);
	void EmitTerminalSuccess();
	void RequestProcessExit();
	FString DoorNetGuid() const;
	TArray<APlayerController*> ServerPlayersByJoinOrder() const;
	APlayerController* LocalPlayerController() const;
	bool ProtocolEnabled() const;
	bool ValidateCommonHarness(FString& OutReason) const;

	FTimerHandle PollTimer;
	FString RunNonce;
	FString PeerId;
	FString FirstRequester;
	FString SecondRequester;
	double StartProtocolSeconds = 0.0;
	double PhaseStartProtocolSeconds = 0.0;
	double LatePeerConnectedSeconds = -1.0;
	double RevisionTwoObservedSeconds = -1.0;
	int32 LastObservedRevision = INDEX_NONE;
	bool bBootLogged = false;
	bool bReadyLogged = false;
	bool bRequestAttempted = false;
	bool bTerminal = false;
	EServerPhase ServerPhase = EServerPhase::WaitingInitialPeers;
};
