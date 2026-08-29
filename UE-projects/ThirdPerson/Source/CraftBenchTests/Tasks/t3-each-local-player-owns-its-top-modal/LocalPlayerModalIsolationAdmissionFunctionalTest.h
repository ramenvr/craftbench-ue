// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// Admission-only proof for task t3-each-local-player-owns-its-top-modal.
// This class is deliberately not the production fixture named by task.md.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalRuntime.h"
#include "LocalPlayerModalIsolationAdmissionFunctionalTest.generated.h"

class APlayerController;
class UButton;
class UCommonActivatableWidgetStack;
class UCommonUIActionRouterBase;
class UEnhancedInputLocalPlayerSubsystem;
class UGameInstance;
class UGameViewportClient;
class UInputAction;
class UInputMappingContext;
class ULocalPlayer;

/** Verifier-owned screen used to prove real per-player CommonUI routing. */
UCLASS()
class CRAFTBENCHTESTS_API ULocalPlayerModalAdmissionScreen : public ULocalPlayerModalScreenBase
{
	GENERATED_BODY()

public:
	ULocalPlayerModalAdmissionScreen(const FObjectInitializer& ObjectInitializer);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual UWidget* NativeGetDesiredFocusTarget() const override;
	virtual void NativeOnActivated() override;
	virtual void NativeOnDeactivated() override;
	virtual void OnConfiguredDismiss_Implementation() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UButton> PrimaryButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> AlternateButton;

};

/** One activatable stack root, owned by exactly one local player. */
UCLASS()
class CRAFTBENCHTESTS_API ULocalPlayerModalAdmissionRoot : public ULocalPlayerModalRootBase
{
	GENERATED_BODY()

public:
	virtual UCommonActivatableWidgetStack* ResolvePlayerModalStack_Implementation() const override;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidgetStack> Stack;
};

/**
 * Admission-only real-RHI probe. It creates a second local player, two real
 * action routers, two independent stacks and two Slate users in one PIE world.
 */
UCLASS()
class CRAFTBENCHTESTS_API ALocalPlayerModalIsolationAdmissionFunctionalTest
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ALocalPlayerModalIsolationAdmissionFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual TSubclassOf<ULocalPlayerModalRootBase> GetRootWidgetClass() const;
	virtual TSubclassOf<ULocalPlayerModalScreenBase> GetScreenWidgetClass() const;
	virtual FString GetSuccessMarker() const;

private:
	bool RequireHarness(bool bCondition, const FString& Detail);
	bool FailGate(const TCHAR* Gate, const FString& Detail);
	bool RequireGate(bool bCondition, const TCHAR* Gate, const FString& Detail);
	bool ResolveTwoLocalPlayers();
	bool BuildHomeStacks(int32 Epoch);
	bool BeginEpoch(int32 Epoch);
	bool VerifyPlayerState(int32 PlayerIndex,
		ULocalPlayerModalScreenBase* ExpectedTop,
		int32 ExpectedStackCount, const TCHAR* Stage);
	bool VerifyFocus(int32 PlayerIndex, UButton* Expected, const TCHAR* Gate,
		const TCHAR* Stage);
	bool VerifyContextMatrix(int32 PlayerIndex,
		ULocalPlayerModalScreenBase* ExpectedTop, const TCHAR* Stage);
	bool InjectSharedKey(int32 PlayerIndex, EInputEvent Event);
	bool VerifyAfterOwnedAction(int32 OwnerIndex, int32 OtherIndex,
		bool bOtherAlreadyPopped, const TCHAR* Stage);
	void RemoveAdmissionUI();

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> SharedAction;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UInputMappingContext>> EpochContexts;

	TWeakObjectPtr<UGameInstance> GameInstance;
	TWeakObjectPtr<UGameViewportClient> ViewportClient;
	TArray<TWeakObjectPtr<ULocalPlayer>> LocalPlayers;
	TArray<TWeakObjectPtr<APlayerController>> Controllers;
	TArray<TWeakObjectPtr<UCommonUIActionRouterBase>> ActionRouters;
	TArray<TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem>> InputSubsystems;
	TArray<TWeakObjectPtr<ULocalPlayerModalRootBase>> Roots;
	TArray<TWeakObjectPtr<ULocalPlayerModalScreenBase>> Homes;
	TArray<TWeakObjectPtr<ULocalPlayerModalScreenBase>> ActionTargets;
	TArray<TWeakObjectPtr<ULocalPlayerModalScreenBase>> TopsAfterPop;
	TArray<int32> InitialStackCounts;
	TArray<int32> ContextOwners;
	TArray<int32> ContextPriorities;
	TArray<TWeakObjectPtr<ULocalPlayerModalScreenBase>> ContextScreens;

	bool bCreatedSecondLocalPlayer = false;
	bool bReassignedSecondInputDevice = false;
	FInputDeviceId ReassignedSecondInputDevice = INPUTDEVICEID_NONE;
	FPlatformUserId PreviousSecondInputDeviceOwner = PLATFORMUSERID_NONE;
	int32 CurrentEpoch = INDEX_NONE;
	int32 FirstOwner = INDEX_NONE;
	int32 SecondOwner = INDEX_NONE;
	FKey CurrentSharedKey;
};
