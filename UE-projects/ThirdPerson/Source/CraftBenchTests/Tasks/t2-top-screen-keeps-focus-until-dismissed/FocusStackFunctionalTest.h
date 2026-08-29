// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GameFramework/Actor.h"
#include "FocusStackFunctionalTest.generated.h"

class AMenuFocusPolicy;
class APlayerController;
class UButton;
class UCommonActivatableWidget;
class UCommonActivatableWidgetStack;

/**
 * Verifier-owned driver for the three public menu commands. It deliberately
 * contains no fallback navigation behavior: the submitted root must implement
 * the lifecycle behind OpenDetails, DismissTop, and CloseMenu.
 */
UCLASS()
class CRAFTBENCHTESTS_API AMenuLifecycleHost : public AActor
{
	GENERATED_BODY()

public:
	AMenuLifecycleHost();

	bool CreateRoot(APlayerController* OwningController, FString& OutFailure);
	bool ActivateRoot(FString& OutFailure);
	bool InvokeRootCommand(FName CommandName, FString& OutFailure);
	bool RefreshLivePointers(FString& OutFailure);
	bool AttemptBuriedScreenFocusForTest(FString& OutFailure);
	void RemoveRoot();

	UCommonActivatableWidget* GetRoot() const { return Root; }
	UCommonActivatableWidgetStack* GetStack() const { return Stack; }
	UCommonActivatableWidget* GetHome() const { return Home; }
	UCommonActivatableWidget* GetActiveDetail() const { return ActiveDetail; }
	UButton* GetHomePrimary() const { return HomePrimary; }
	UButton* GetDetailPrimary() const { return DetailPrimary; }
	UButton* GetDetailAlternate() const { return DetailAlternate; }

private:
	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidget> Root;

	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidgetStack> Stack;

	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidget> Home;

	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidget> ActiveDetail;

	UPROPERTY(Transient)
	TObjectPtr<UButton> HomePrimary;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DetailPrimary;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DetailAlternate;
};

/** PIE-native lifecycle and user-focus verifier. */
UCLASS()
class CRAFTBENCHTESTS_API AFocusStackFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AFocusStackFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool RequireHarness(bool bCondition, const FString& Detail);
	bool FailGate(const TCHAR* Gate, const FString& Detail);
	bool RequireGate(bool bCondition, const TCHAR* Gate, const FString& Detail);
	bool RequireExactFocus(UButton* Expected, const TArray<UButton*>& MustNotOwnFocus,
		const TCHAR* Gate, const TCHAR* Stage);
	bool ResolveProtectedActors();
	bool RefreshGeneratedState(const TCHAR* Gate, const TCHAR* Stage);
	void LogFocus(const TCHAR* Stage) const;

	TWeakObjectPtr<APlayerController> Controller;
	TWeakObjectPtr<AMenuLifecycleHost> Host;
	TWeakObjectPtr<AMenuFocusPolicy> Policy;
	TWeakObjectPtr<UCommonActivatableWidget> Sentinel;
	TWeakObjectPtr<UButton> SentinelPrimary;
	TWeakObjectPtr<UButton> SentinelAlternate;
	TWeakObjectPtr<UCommonActivatableWidget> InitialHome;
	TWeakObjectPtr<UCommonActivatableWidget> FirstDetail;
	TWeakObjectPtr<UCommonActivatableWidget> SecondDetail;
	TWeakObjectPtr<UButton> HomePrimary;
	TWeakObjectPtr<UButton> FirstDetailPrimary;
	TWeakObjectPtr<UButton> FirstDetailAlternate;
	TWeakObjectPtr<UButton> SecondDetailPrimary;
	TWeakObjectPtr<UButton> SecondDetailAlternate;
};
