// Copyright CraftBench. All Rights Reserved.
//
// The course: the ONE place that says which pad is current and where a dead
// character comes back to. Both answers are derived from CurrentPadOrder, so the
// state the course exposes and the state it acts on cannot drift apart.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpikeLaneCourse.generated.h"

class ALanePadActor;

UCLASS()
class THIRDPERSON_API ASpikeLaneCourse : public AActor
{
	GENERATED_BODY()

public:
	ASpikeLaneCourse();

	/** 1 or 2 once a pad has been walked onto; 0 means the start mark. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Course")
	int32 CurrentPadOrder = 0;

	/** A character walked onto this pad. */
	void NotifyPadEntered(ALanePadActor* Pad);

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Where a character that dies right now should reappear. */
	FVector RespawnPoint() const;
	void RefreshPadMarks();

	FVector StartMarkAt = FVector::ZeroVector;
	/** Set while a dead character is waiting to come back. */
	TWeakObjectPtr<AActor> Dying;
	double ReviveAt = -1.0;
};
