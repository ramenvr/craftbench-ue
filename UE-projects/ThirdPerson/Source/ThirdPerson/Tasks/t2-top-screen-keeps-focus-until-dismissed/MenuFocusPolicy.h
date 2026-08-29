// Copyright CraftBench. All Rights Reserved.
//
// AMenuFocusPolicy - supplied world policy for task t2-top-screen-keeps-focus-until-dismissed.
// The editable menu screens read the current choice whenever details opens.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MenuFocusPolicy.generated.h"

UENUM(BlueprintType)
enum class EMenuFocusChoice : uint8
{
	Primary,
	Alternate
};

UCLASS()
class THIRDPERSON_API AMenuFocusPolicy : public AActor
{
	GENERATED_BODY()

public:
	AMenuFocusPolicy();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Menu Policy")
	EMenuFocusChoice PreferredDetailAction = EMenuFocusChoice::Alternate;
};
