// Copyright CraftBench. All Rights Reserved.

#include "PredictedDashMovementComponent.h"

#include "GameFramework/Character.h"
#include "PredictedDashProtectedTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogPredictedDashCandidate, Log, All);

void FPredictedDashSavedMove::Clear()
{
	Super::Clear();
	bSavedDash = false;
	SavedDashDirection = FVector::ZeroVector;
	SavedDashDistance = 0.0f;
	SavedDashNonce = 0;
}

uint8 FPredictedDashSavedMove::GetCompressedFlags() const
{
	return Super::GetCompressedFlags()
		| (bSavedDash ? FLAG_Custom_0 : 0);
}

bool FPredictedDashSavedMove::CanCombineWith(
	const FSavedMovePtr& NewMove, ACharacter* InCharacter,
	const float MaxDelta) const
{
	const FPredictedDashSavedMove* Other =
		static_cast<const FPredictedDashSavedMove*>(NewMove.Get());
	if (bSavedDash || Other == nullptr || Other->bSavedDash
		|| SavedDashNonce != Other->SavedDashNonce)
	{
		return false;
	}
	return Super::CanCombineWith(NewMove, InCharacter, MaxDelta);
}

void FPredictedDashSavedMove::SetMoveFor(
	ACharacter* Character, const float InDeltaTime, const FVector& NewAccel,
	FNetworkPredictionData_Client_Character& ClientData)
{
	Super::SetMoveFor(Character, InDeltaTime, NewAccel, ClientData);
	const UPredictedDashMovementComponent* Movement = Character != nullptr
		? Cast<UPredictedDashMovementComponent>(Character->GetCharacterMovement())
		: nullptr;
	bSavedDash = Movement != nullptr && Movement->HasPendingDash();
	if (bSavedDash)
	{
		SavedDashDirection = Movement->GetPendingDashDirection();
		SavedDashDistance = Movement->GetPendingDashDistance();
		SavedDashNonce = Movement->GetPendingDashNonce();
		UE_LOG(LogPredictedDashCandidate, Display, TEXT(
			"DASH-CANDIDATE-SAVED nonce=%u distance=%.3f"),
			SavedDashNonce, SavedDashDistance);
	}
}

void FPredictedDashSavedMove::PrepMoveFor(ACharacter* Character)
{
	Super::PrepMoveFor(Character);
	if (bSavedDash && Character != nullptr)
	{
		if (UPredictedDashMovementComponent* Movement =
			Cast<UPredictedDashMovementComponent>(
				Character->GetCharacterMovement()))
		{
			Movement->PrepareDashForReplay(
				SavedDashDirection, SavedDashDistance, SavedDashNonce);
		}
	}
}

void FPredictedDashNetworkMoveData::ClientFillNetworkMoveData(
	const FSavedMove_Character& ClientMove,
	const ENetworkMoveType MoveType)
{
	Super::ClientFillNetworkMoveData(ClientMove, MoveType);
	const FPredictedDashSavedMove& DashMove =
		static_cast<const FPredictedDashSavedMove&>(ClientMove);
	bDash = DashMove.bSavedDash;
	DashDirection = DashMove.SavedDashDirection;
	DashDistance = DashMove.SavedDashDistance;
	DashNonce = DashMove.SavedDashNonce;
	if (bDash)
	{
		UE_LOG(LogPredictedDashCandidate, Display, TEXT(
			"DASH-CANDIDATE-FILL move_type=%d nonce=%u distance=%.3f"),
			static_cast<int32>(MoveType), DashNonce, DashDistance);
	}
}

bool FPredictedDashNetworkMoveData::Serialize(
	UCharacterMovementComponent& CharacterMovement, FArchive& Archive,
	UPackageMap* PackageMap, const ENetworkMoveType MoveType)
{
	bool bSuccess = Super::Serialize(
		CharacterMovement, Archive, PackageMap, MoveType);
	uint8 DashBit = bDash ? 1 : 0;
	Archive.SerializeBits(&DashBit, 1);
	bDash = DashBit != 0;
	if (bDash)
	{
		bool bDirectionSuccess = true;
		DashDirection.NetSerialize(Archive, PackageMap, bDirectionSuccess);
		uint16 QuantizedDistance = Archive.IsSaving()
			? static_cast<uint16>(FMath::Clamp(
				FMath::RoundToInt(DashDistance * 10.0f), 1, 60000))
			: 0;
		Archive << QuantizedDistance;
		if (Archive.IsLoading())
		{
			DashDistance = static_cast<float>(QuantizedDistance) / 10.0f;
		}
		Archive.SerializeIntPacked(DashNonce);
		bSuccess = bSuccess && bDirectionSuccess;
		UE_LOG(LogPredictedDashCandidate, Display, TEXT(
			"DASH-CANDIDATE-SERIALIZE archive=%s move_type=%d nonce=%u "
			"distance=%.3f success=%d"),
			Archive.IsSaving() ? TEXT("save") : TEXT("load"),
			static_cast<int32>(MoveType), DashNonce, DashDistance,
			bSuccess ? 1 : 0);
	}
	return !Archive.IsError() && bSuccess;
}

FPredictedDashNetworkMoveDataContainer::
	FPredictedDashNetworkMoveDataContainer()
{
	NewMoveData = &MoveData[0];
	PendingMoveData = &MoveData[1];
	OldMoveData = &MoveData[2];
}

FPredictedDashClientPredictionData::FPredictedDashClientPredictionData(
	const UCharacterMovementComponent& ClientMovement)
	: Super(ClientMovement)
{
}

FSavedMovePtr FPredictedDashClientPredictionData::AllocateNewMove()
{
	return MakeShared<FPredictedDashSavedMove>();
}

UPredictedDashMovementComponent::UPredictedDashMovementComponent()
{
	SetNetworkMoveDataContainer(MoveDataContainer);
}

void UPredictedDashMovementComponent::SetPendingDash(
	const FVector& WorldDirection, const float Distance,
	const uint32 RequestNonce)
{
	const FVector Direction = WorldDirection.GetSafeNormal2D();
	if (Direction.IsNearlyZero() || !FMath::IsFinite(Distance)
		|| Distance < 25.0f || Distance > 3000.0f || RequestNonce == 0)
	{
		return;
	}
	bPendingDash = true;
	PendingDirection = Direction;
	PendingDistance = Distance;
	PendingNonce = RequestNonce;
}

void UPredictedDashMovementComponent::RequestPredictedDash(
	const FVector& WorldDirection, const float Distance,
	const uint32 RequestNonce)
{
	if (CharacterOwner != nullptr && CharacterOwner->IsLocallyControlled()
		&& CharacterOwner->GetLocalRole() == ROLE_AutonomousProxy)
	{
		SetPendingDash(WorldDirection, Distance, RequestNonce);
	}
}

void UPredictedDashMovementComponent::PrepareDashForReplay(
	const FVector& WorldDirection, const float Distance,
	const uint32 RequestNonce)
{
	SetPendingDash(WorldDirection, Distance, RequestNonce);
}

FNetworkPredictionData_Client*
UPredictedDashMovementComponent::GetPredictionData_Client() const
{
	if (ClientPredictionData == nullptr)
	{
		UPredictedDashMovementComponent* MutableThis =
			const_cast<UPredictedDashMovementComponent*>(this);
		MutableThis->ClientPredictionData =
			new FPredictedDashClientPredictionData(*this);
	}
	return ClientPredictionData;
}

void UPredictedDashMovementComponent::UpdateFromCompressedFlags(
	const uint8 Flags)
{
	Super::UpdateFromCompressedFlags(Flags);
	if ((Flags & FSavedMove_Character::FLAG_Custom_0) == 0)
	{
		ClearPendingDash();
	}
	else
	{
		bPendingDash = true;
	}
}

void UPredictedDashMovementComponent::MoveAutonomous(
	const float ClientTimeStamp, const float DeltaTime,
	const uint8 CompressedFlags, const FVector& NewAccel)
{
	bool bCurrentDataDash = false;
	uint32 CurrentDataNonce = 0;
	if (const FCharacterNetworkMoveData* CurrentData =
		GetCurrentNetworkMoveData())
	{
		const FPredictedDashNetworkMoveData* DashData =
			static_cast<const FPredictedDashNetworkMoveData*>(CurrentData);
		bCurrentDataDash = DashData->bDash;
		CurrentDataNonce = DashData->DashNonce;
		if (DashData->bDash)
		{
			SetPendingDash(DashData->DashDirection,
				DashData->DashDistance, DashData->DashNonce);
		}
	}
	if ((CompressedFlags & FSavedMove_Character::FLAG_Custom_0) != 0
		|| bCurrentDataDash)
	{
		UE_LOG(LogPredictedDashCandidate, Display, TEXT(
			"DASH-CANDIDATE-AUTONOMOUS role=%d flag=%d data=%d nonce=%u"),
			CharacterOwner != nullptr
				? static_cast<int32>(CharacterOwner->GetLocalRole()) : -1,
			(CompressedFlags & FSavedMove_Character::FLAG_Custom_0) != 0 ? 1 : 0,
			bCurrentDataDash ? 1 : 0, CurrentDataNonce);
	}
	Super::MoveAutonomous(
		ClientTimeStamp, DeltaTime, CompressedFlags, NewAccel);
}

void UPredictedDashMovementComponent::PerformMovement(const float DeltaTime)
{
	Super::PerformMovement(DeltaTime);
	if (!bPendingDash || CharacterOwner == nullptr || UpdatedComponent == nullptr)
	{
		return;
	}

	bool bExecute = true;
	if (CharacterOwner->HasAuthority())
	{
		APredictedDashCharacter* DashCharacter =
			Cast<APredictedDashCharacter>(CharacterOwner);
		bExecute = DashCharacter != nullptr
			&& DashCharacter->AuthorizeAndCommitDash(
				PendingDirection, PendingDistance, PendingNonce);
	}
	else if (const APredictedDashCharacter* DashCharacter =
		Cast<APredictedDashCharacter>(CharacterOwner))
	{
		bExecute = DashCharacter->GetRejectedDashNonce()
			!= static_cast<int32>(PendingNonce);
	}
	UE_LOG(LogPredictedDashCandidate, Display, TEXT(
		"DASH-CANDIDATE-PERFORM role=%d authority=%d nonce=%u execute=%d"),
		static_cast<int32>(CharacterOwner->GetLocalRole()),
		CharacterOwner->HasAuthority() ? 1 : 0, PendingNonce,
		bExecute ? 1 : 0);

	if (bExecute)
	{
		FHitResult Hit;
		SafeMoveUpdatedComponent(
			PendingDirection * PendingDistance,
			UpdatedComponent->GetComponentQuat(), true, Hit);
		if (Hit.IsValidBlockingHit())
		{
			SlideAlongSurface(PendingDirection * PendingDistance,
				1.0f - Hit.Time, Hit.Normal, Hit, true);
		}
	}
	ClearPendingDash();
}

void UPredictedDashMovementComponent::ClearPendingDash()
{
	bPendingDash = false;
	PendingDirection = FVector::ZeroVector;
	PendingDistance = 0.0f;
	PendingNonce = 0;
}
