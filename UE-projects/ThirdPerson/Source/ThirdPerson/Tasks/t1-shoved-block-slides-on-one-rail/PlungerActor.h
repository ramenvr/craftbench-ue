// Copyright CraftBench. All Rights Reserved.
//
// The plunger post. Walk into it and it shoves both blocks at the same instant
// with the same push; step out and it re-arms. Already built -- it needs no
// changes for this level to work.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PlungerActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API APlungerActor : public AActor
{
	GENERATED_BODY()

public:
	APlungerActor();

	/** The post you can see and walk into. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plunger")
	UStaticMeshComponent* Post = nullptr;

	/** Query-only box that notices the character. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plunger")
	UBoxComponent* Trigger = nullptr;

	/** How many shoves have been delivered so far. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plunger")
	int32 ShoveCount = 0;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION()
	void OnTriggerBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	UFUNCTION()
	void OnTriggerEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	/** Delivers one identical push to every block in the level. */
	void ShoveBlocks();

	/** The rail bearing, read off the placed rail marker at BeginPlay. */
	FVector RailForward = FVector::ForwardVector;
	FVector RailRight = FVector::RightVector;

	/** False while the character is still standing in the trigger. */
	bool bArmed = true;

	/** Seconds of push left to deliver, and the push being delivered. */
	double PushRemaining = 0.0;
	FVector PushForce = FVector::ZeroVector;
	FVector PushOffset = FVector::ZeroVector;
};
