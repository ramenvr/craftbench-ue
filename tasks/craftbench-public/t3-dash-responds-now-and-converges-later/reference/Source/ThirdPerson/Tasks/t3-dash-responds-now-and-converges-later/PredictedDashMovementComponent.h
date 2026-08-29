// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/CharacterMovementReplication.h"
#include "PredictedDashMovementComponent.generated.h"

class UPredictedDashMovementComponent;

struct FPredictedDashSavedMove final : public FSavedMove_Character
{
	typedef FSavedMove_Character Super;

	bool bSavedDash = false;
	FVector SavedDashDirection = FVector::ZeroVector;
	float SavedDashDistance = 0.0f;
	uint32 SavedDashNonce = 0;

	virtual void Clear() override;
	virtual uint8 GetCompressedFlags() const override;
	virtual bool CanCombineWith(
		const FSavedMovePtr& NewMove, ACharacter* InCharacter,
		float MaxDelta) const override;
	virtual void SetMoveFor(
		ACharacter* Character, float InDeltaTime, const FVector& NewAccel,
		FNetworkPredictionData_Client_Character& ClientData) override;
	virtual void PrepMoveFor(ACharacter* Character) override;
};

struct FPredictedDashNetworkMoveData final : public FCharacterNetworkMoveData
{
	typedef FCharacterNetworkMoveData Super;

	bool bDash = false;
	FVector_NetQuantizeNormal DashDirection = FVector::ZeroVector;
	float DashDistance = 0.0f;
	uint32 DashNonce = 0;

	virtual void ClientFillNetworkMoveData(
		const FSavedMove_Character& ClientMove,
		ENetworkMoveType MoveType) override;
	virtual bool Serialize(
		UCharacterMovementComponent& CharacterMovement, FArchive& Archive,
		UPackageMap* PackageMap, ENetworkMoveType MoveType) override;
};

struct FPredictedDashNetworkMoveDataContainer final
	: public FCharacterNetworkMoveDataContainer
{
	FPredictedDashNetworkMoveDataContainer();

	FPredictedDashNetworkMoveData MoveData[3];
};

class FPredictedDashClientPredictionData final
	: public FNetworkPredictionData_Client_Character
{
public:
	using Super = FNetworkPredictionData_Client_Character;

	explicit FPredictedDashClientPredictionData(
		const UCharacterMovementComponent& ClientMovement);
	virtual FSavedMovePtr AllocateNewMove() override;
};

/** CharacterMovement prediction implementation for one-shot dash requests. */
UCLASS(ClassGroup = Movement, meta = (BlueprintSpawnableComponent))
class THIRDPERSON_API UPredictedDashMovementComponent
	: public UCharacterMovementComponent
{
	GENERATED_BODY()

public:
	UPredictedDashMovementComponent();

	void RequestPredictedDash(
		const FVector& WorldDirection, float Distance, uint32 RequestNonce);
	void PrepareDashForReplay(
		const FVector& WorldDirection, float Distance, uint32 RequestNonce);

	virtual FNetworkPredictionData_Client* GetPredictionData_Client()
		const override;
	virtual void UpdateFromCompressedFlags(uint8 Flags) override;
	virtual void MoveAutonomous(
		float ClientTimeStamp, float DeltaTime, uint8 CompressedFlags,
		const FVector& NewAccel) override;
	virtual void PerformMovement(float DeltaTime) override;

	bool HasPendingDash() const { return bPendingDash; }
	const FVector& GetPendingDashDirection() const { return PendingDirection; }
	float GetPendingDashDistance() const { return PendingDistance; }
	uint32 GetPendingDashNonce() const { return PendingNonce; }

private:
	void SetPendingDash(
		const FVector& WorldDirection, float Distance, uint32 RequestNonce);
	void ClearPendingDash();

	FPredictedDashNetworkMoveDataContainer MoveDataContainer;
	bool bPendingDash = false;
	FVector PendingDirection = FVector::ZeroVector;
	float PendingDistance = 0.0f;
	uint32 PendingNonce = 0;
};
