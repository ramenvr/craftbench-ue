// Copyright CraftBench. All Rights Reserved.
//
// Runtime support for task t2-menu-blocks-gameplay-and-restores-it-exactly.
// The editable menu owns the assigned binding only while it is active.

#pragma once

#include "CoreMinimal.h"
#include "CommonActivatableWidget.h"
#include "GameFramework/Actor.h"
#include "MenuInputRuntime.generated.h"

class APlayerController;
class UCommonActivatableWidgetStack;
class UEnhancedInputLocalPlayerSubsystem;
class UInputAction;
class UInputMappingContext;

/** World-owned assignment read by each newly activated menu instance. */
UCLASS(BlueprintType)
class THIRDPERSON_API AMenuInputPolicy : public AActor
{
	GENERATED_BODY()

public:
	AMenuInputPolicy();

	UFUNCTION(BlueprintPure, Category = "Menu Input")
	UInputMappingContext* GetCurrentMenuContext() const { return CurrentMenuContext; }

	UFUNCTION(BlueprintPure, Category = "Menu Input")
	UInputAction* GetCurrentMenuAction() const { return CurrentMenuAction; }

	UFUNCTION(BlueprintPure, Category = "Menu Input")
	int32 GetCurrentMenuPriority() const { return CurrentMenuPriority; }

	void SetCurrentAssignment(UInputMappingContext* InContext, UInputAction* InAction, int32 InPriority);

private:
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Menu Input", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UInputMappingContext> CurrentMenuContext;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Menu Input", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UInputAction> CurrentMenuAction;

	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Menu Input", meta = (AllowPrivateAccess = "true"))
	int32 CurrentMenuPriority = 0;
};

/**
 * Blueprint surface for the editable menu. The base registers the menu's real
 * UI action but intentionally does not add or remove an input context.
 */
UCLASS(Abstract, Blueprintable)
class THIRDPERSON_API UInputBlockingMenuBase : public UCommonActivatableWidget
{
	GENERATED_BODY()

public:
	void ConfigureFromPolicy(AMenuInputPolicy* InPolicy);

	UFUNCTION(BlueprintPure, Category = "Menu Input")
	AMenuInputPolicy* GetMenuInputPolicy() const { return MenuPolicy; }

	UFUNCTION(BlueprintPure, Category = "Menu Input")
	UEnhancedInputLocalPlayerSubsystem* GetMenuInputSubsystem() const;

	UFUNCTION(BlueprintPure, Category = "Menu Input")
	int32 GetObservedMenuActionCount() const { return ObservedMenuActionCount; }

protected:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual void ActivateMappingContext() override;
	virtual void DeactivateMappingContext() override;

private:
	void RegisterConfiguredMenuAction();
	void HandleMenuAction();

	UPROPERTY(Transient)
	TObjectPtr<AMenuInputPolicy> MenuPolicy;

	UPROPERTY(Transient)
	int32 ObservedMenuActionCount = 0;

	FUIActionBindingHandle MenuActionBinding;
};

/** Native stack root used by the immutable lifecycle host. */
UCLASS()
class THIRDPERSON_API UMenuInputStackRoot : public UCommonActivatableWidget
{
	GENERATED_BODY()

public:
	UCommonActivatableWidgetStack* GetScreenStack() const { return ScreenStack; }

protected:
	virtual TOptional<FUIInputConfig> GetDesiredInputConfig() const override;
	virtual TSharedRef<SWidget> RebuildWidget() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UCommonActivatableWidgetStack> ScreenStack;
};

/** Placed lifecycle host; the fixture drives the same public push/pop path a game uses. */
UCLASS()
class THIRDPERSON_API AMenuInputHost : public AActor
{
	GENERATED_BODY()

public:
	AMenuInputHost();

	bool InitializeForPlayer(APlayerController* InController, FString& OutFailure);
	UInputBlockingMenuBase* PushMenu(TSubclassOf<UInputBlockingMenuBase> MenuClass,
		AMenuInputPolicy* Policy, FString& OutFailure);
	bool PopMenu(FString& OutFailure);
	void RemoveMenuTree();

	UMenuInputStackRoot* GetRoot() const { return Root; }
	UCommonActivatableWidgetStack* GetStack() const;
	UInputBlockingMenuBase* GetActiveMenu() const { return ActiveMenu; }

private:
	UPROPERTY(Transient)
	TObjectPtr<UMenuInputStackRoot> Root;

	UPROPERTY(Transient)
	TObjectPtr<UInputBlockingMenuBase> ActiveMenu;
};
