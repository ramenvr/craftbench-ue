// Copyright CraftBench. All Rights Reserved.
//
// The alarm for task t1-guard-patrols-until-the-alarm-then-chases. SUPPLIED AND
// WORKING END TO END: stand on its plate and the board goes red, step off and it goes
// dark. Nothing here needs changing, and nothing here knows the guard exists.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AlarmPanelActor.generated.h"

class UBoxComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AAlarmPanelActor : public AActor
{
	GENERATED_BODY()

public:
	AAlarmPanelActor();

	/** The board a reviewer watches: dark grey at rest, red while the alarm rings. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alarm")
	UStaticMeshComponent* Board = nullptr;

	/** The plate on the floor that sets it off. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alarm")
	UStaticMeshComponent* Plate = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alarm")
	UBoxComponent* PlateVolume = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Alarm")
	UPointLightComponent* Lamp = nullptr;

	/** Whether the alarm is sounding right now. */
	UFUNCTION(BlueprintPure, Category = "Alarm")
	bool IsRinging() const { return Occupants > 0; }

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnPlateBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void OnPlateEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	void Refresh();

	/** How many pawns are standing on the plate. Counted rather than flagged, so two
	 *  figures on one plate do not clear the alarm when the first steps off. */
	int32 Occupants = 0;

	UPROPERTY()
	UMaterialInstanceDynamic* BoardMaterial = nullptr;
};
