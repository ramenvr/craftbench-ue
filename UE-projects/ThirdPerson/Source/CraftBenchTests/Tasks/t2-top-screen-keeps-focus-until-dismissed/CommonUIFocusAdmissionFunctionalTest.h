// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// Token-free admission probe for the headless activation-stack and user-focus
// primitives required by t2-top-screen-keeps-focus-until-dismissed.

#pragma once

#include "CoreMinimal.h"
#include "CommonActivatableWidget.h"
#include "CraftBenchFunctionalTest.h"
#include "CommonUIFocusAdmissionFunctionalTest.generated.h"

class APlayerController;
class UButton;
class UCommonActivatableWidgetStack;

UCLASS()
class CRAFTBENCHTESTS_API UCommonUIFocusProbeScreen : public UCommonActivatableWidget
{
	GENERATED_BODY()

public:
	void SetPreferredAlternate(bool bInPreferredAlternate) { bPreferredAlternate = bInPreferredAlternate; }
	UButton* GetPrimaryButton() const { return PrimaryButton; }
	UButton* GetAlternateButton() const { return AlternateButton; }

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual UWidget* NativeGetDesiredFocusTarget() const override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UButton> PrimaryButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> AlternateButton;

	bool bPreferredAlternate = false;
};

UCLASS()
class CRAFTBENCHTESTS_API UCommonUIFocusProbeRoot : public UCommonActivatableWidget
{
	GENERATED_BODY()

public:
	UCommonActivatableWidgetStack* GetStack() const { return Stack; }

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidgetStack> Stack;
};

UCLASS()
class CRAFTBENCHTESTS_API ACommonUIFocusAdmissionFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACommonUIFocusAdmissionFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool Require(bool bCondition, const FString& FailureDetail);
	bool RequireFocus(UButton* Expected, UButton* Unexpected, const TCHAR* Stage);

	TWeakObjectPtr<APlayerController> Controller;
	TWeakObjectPtr<UCommonUIFocusProbeScreen> Sentinel;
	TWeakObjectPtr<UCommonUIFocusProbeRoot> Root;
	TWeakObjectPtr<UCommonUIFocusProbeScreen> Home;
	TWeakObjectPtr<UCommonUIFocusProbeScreen> Detail;
	TWeakObjectPtr<UButton> HomePrimary;
	TWeakObjectPtr<UButton> DetailPrimary;
	TWeakObjectPtr<UButton> DetailAlternate;
};
