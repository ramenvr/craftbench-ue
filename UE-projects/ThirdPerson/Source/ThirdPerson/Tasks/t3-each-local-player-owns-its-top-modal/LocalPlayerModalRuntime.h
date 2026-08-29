// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "CommonActivatableWidget.h"
#include "Input/CommonUIInputTypes.h"
#include "LocalPlayerModalRuntime.generated.h"

class UButton;
class UCommonActivatableWidgetStack;
class UEnhancedInputLocalPlayerSubsystem;
class UInputAction;
class UInputMappingContext;

/**
 * Neutral root surface for the editable WBP. The native default deliberately
 * exposes no stack; the candidate graph must return its authored player-owned
 * stack through ResolvePlayerModalStack.
 */
UCLASS(Abstract, Blueprintable)
class THIRDPERSON_API ULocalPlayerModalRootBase : public UCommonActivatableWidget
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintNativeEvent, BlueprintPure, Category = "CraftBench|Local Player Modal")
	UCommonActivatableWidgetStack* ResolvePlayerModalStack() const;
	virtual UCommonActivatableWidgetStack* ResolvePlayerModalStack_Implementation() const;

	virtual TOptional<FUIInputConfig> GetDesiredInputConfig() const override;
};

/**
 * Neutral modal surface. Each callable performs one engine operation; none is
 * invoked automatically on activation/deactivation/dismiss. The editable WBP
 * must author the lifecycle and owning-player graph.
 */
UCLASS(Abstract, Blueprintable)
class THIRDPERSON_API ULocalPlayerModalScreenBase : public UCommonActivatableWidget
{
	GENERATED_BODY()

public:
	ULocalPlayerModalScreenBase(const FObjectInitializer& ObjectInitializer);

	void ConfigurePolicy(UInputAction* InAction, UInputMappingContext* InContext,
		int32 InPriority, int32 InOwnerIndex, int32 InModalOrdinal,
		bool bInModal, bool bInPreferAlternate);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Local Player Modal")
	void ApplyConfiguredMapping();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Local Player Modal")
	void RemoveConfiguredMapping();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Local Player Modal")
	void RegisterConfiguredDismiss();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Local Player Modal")
	void CloseOnlyThisModal();

	UFUNCTION(BlueprintPure, Category = "CraftBench|Local Player Modal")
	UButton* ResolveConfiguredFocusTarget() const;

	UFUNCTION(BlueprintPure, Category = "CraftBench|Local Player Modal")
	FUIInputConfig ResolveConfiguredInputConfig() const;

	UFUNCTION(BlueprintNativeEvent, Category = "CraftBench|Local Player Modal")
	void OnConfiguredDismiss();
	virtual void OnConfiguredDismiss_Implementation();

	UInputMappingContext* GetConfiguredContext() const { return ConfiguredContext; }
	int32 GetConfiguredPriority() const { return ConfiguredPriority; }
	int32 GetOwnerIndex() const { return OwnerIndex; }
	int32 GetModalOrdinal() const { return ModalOrdinal; }
	int32 GetObservedActionCount() const { return ObservedActionCount; }
	bool IsConfiguredModal() const { return bConfiguredModal; }
	bool IsMappingApplied() const { return bMappingApplied; }

protected:
	virtual void NativeDestruct() override;

private:
	UEnhancedInputLocalPlayerSubsystem* ResolveInputSubsystem() const;
	void HandleConfiguredDismiss();

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> ConfiguredAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> ConfiguredContext;

	FUIActionBindingHandle ActionBinding;
	int32 ConfiguredPriority = 0;
	int32 OwnerIndex = INDEX_NONE;
	int32 ModalOrdinal = INDEX_NONE;
	int32 ObservedActionCount = 0;
	bool bConfiguredModal = false;
	bool bPreferAlternate = false;
	bool bMappingApplied = false;
};
