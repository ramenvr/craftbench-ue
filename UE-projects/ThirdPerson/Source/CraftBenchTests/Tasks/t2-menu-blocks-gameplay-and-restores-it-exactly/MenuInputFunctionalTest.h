// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "InputActionValue.h"
#include "Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/MenuInputRuntime.h"
#include "MenuInputFunctionalTest.generated.h"

class AMenuInputHost;
class AMenuInputPolicy;
class APlayerController;
class UCommonUIActionRouterBase;
class UEnhancedInputComponent;
class UEnhancedInputLocalPlayerSubsystem;
class UGameViewportClient;
class UInputAction;
class UInputMappingContext;

/** Verifier-owned correct control used only by the admission fixture. */
UCLASS()
class CRAFTBENCHTESTS_API UMenuInputAdmissionScreen : public UInputBlockingMenuBase
{
	GENERATED_BODY()

public:
	virtual TOptional<FUIInputConfig> GetDesiredInputConfig() const override;

protected:
	virtual void NativeOnActivated() override;
	virtual void NativeOnDeactivated() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> AppliedContext;
};

/** Shared deterministic two-leg driver; subclasses select final versus admission screen. */
UCLASS(Abstract)
class CRAFTBENCHTESTS_API AMenuInputFunctionalTestBase : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AMenuInputFunctionalTestBase(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual TSubclassOf<UInputBlockingMenuBase> ResolveMenuClass() const PURE_VIRTUAL(
		AMenuInputFunctionalTestBase::ResolveMenuClass, return nullptr;);
	virtual const TCHAR* SuccessLabel() const PURE_VIRTUAL(
		AMenuInputFunctionalTestBase::SuccessLabel, return TEXT("unknown"););

private:
	bool RequireHarness(bool bCondition, const FString& Detail);
	bool FailGate(const TCHAR* Gate, const FString& Detail);
	bool RequireGate(bool bCondition, const TCHAR* Gate, const FString& Detail);
	bool LoadProtectedSupport();
	bool ResolveWorldSupport();
	bool StageLeg(int32 LegIndex);
	bool RequireContext(const UInputMappingContext* Context, int32 ExpectedPriority,
		bool bExpectedPresent, const TCHAR* Gate, const TCHAR* Label);
	bool RequirePriorState(int32 LegIndex, bool bMenuExpected, const TCHAR* Stage);
	bool RequireActiveMenu(UInputBlockingMenuBase* Expected, int32 LegIndex, const TCHAR* Stage);
	bool InjectKey(const FKey& Key, EInputEvent Event, float Amount);
	void HandleGameplayAction(const FInputActionValue& Value);
	void HandleUnrelatedAction(const FInputActionValue& Value);

	TWeakObjectPtr<APlayerController> Controller;
	TWeakObjectPtr<AMenuInputHost> Host;
	TWeakObjectPtr<AMenuInputPolicy> Policy;
	TWeakObjectPtr<UCommonUIActionRouterBase> ActionRouter;
	TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> InputSubsystem;
	TWeakObjectPtr<UGameViewportClient> ViewportClient;
	TWeakObjectPtr<UInputBlockingMenuBase> FirstMenu;
	TWeakObjectPtr<UInputBlockingMenuBase> SecondMenu;

	UPROPERTY(Transient)
	TObjectPtr<UEnhancedInputComponent> PawnInputComponent;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> GameplayAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MenuAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> UnrelatedAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> StockMovementContext;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UInputMappingContext>> GameplayContexts;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UInputMappingContext>> MenuContexts;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UInputMappingContext>> UnrelatedContexts;

	int32 StockMovementPriority = 0;
	int32 GameplayActionCount = 0;
	int32 UnrelatedActionCount = 0;
};

/** Final graded fixture using the exact editable Widget Blueprint. */
UCLASS()
class CRAFTBENCHTESTS_API AMenuInputFunctionalTest : public AMenuInputFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual TSubclassOf<UInputBlockingMenuBase> ResolveMenuClass() const override;
	virtual const TCHAR* SuccessLabel() const override { return TEXT("final"); }
};

/** Admission-only fixture proving the CommonUI/Enhanced Input substrate. */
UCLASS()
class CRAFTBENCHTESTS_API AMenuInputAdmissionFunctionalTest : public AMenuInputFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual TSubclassOf<UInputBlockingMenuBase> ResolveMenuClass() const override;
	virtual const TCHAR* SuccessLabel() const override { return TEXT("admission"); }
};
