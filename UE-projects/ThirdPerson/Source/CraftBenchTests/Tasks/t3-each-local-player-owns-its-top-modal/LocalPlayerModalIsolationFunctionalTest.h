// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalIsolationAdmissionFunctionalTest.h"
#include "LocalPlayerModalIsolationFunctionalTest.generated.h"

/** Production fixture. The editable Widget Blueprints supply every lifecycle graph. */
UCLASS()
class CRAFTBENCHTESTS_API ALocalPlayerModalIsolationFunctionalTest
	: public ALocalPlayerModalIsolationAdmissionFunctionalTest
{
	GENERATED_BODY()

protected:
	virtual TSubclassOf<ULocalPlayerModalRootBase> GetRootWidgetClass() const override;
	virtual TSubclassOf<ULocalPlayerModalScreenBase> GetScreenWidgetClass() const override;
	virtual FString GetSuccessMarker() const override;
};
