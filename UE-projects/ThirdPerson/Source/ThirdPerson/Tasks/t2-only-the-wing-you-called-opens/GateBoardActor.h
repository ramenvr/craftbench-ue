// Copyright CraftBench. All Rights Reserved.
//
// The board over the host gate, for task t2-only-the-wing-you-called-opens. One of
// them is already in the level and it is not yours to move.
//
// IT IS A BOARD AND A SWITCH AND NOTHING ELSE. Hand it a name and a number and it puts
// them on the board as one line of capitals -- the name, one space, the number. Hand it
// nothing and it reads NONE 0, which is what it reads from the first frame of play.
//
// NOTHING DECIDES WHAT TO PUT ON IT. Nobody notices a step, nobody works out which wing
// was called, nobody works out how many of that wing's fittings are standing in the
// host, and nobody calls Report(). That is the work.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GateBoardActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AGateBoardActor : public AActor
{
	GENERATED_BODY()

public:
	AGateBoardActor();

	/** An unscaled pivot, so the board's scale never reaches the lettering. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	TObjectPtr<USceneComponent> Pivot;

	/** The board you can see. NON-COLLIDING. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	TObjectPtr<UStaticMeshComponent> Board;

	/** The one line of lettering on it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	TObjectPtr<UTextRenderComponent> Line;

	/** THE SWITCH. Puts one line on the board: the name in capitals, a single space,
	 *  then the count. An empty name reads NONE. Negative counts read 0. */
	UFUNCTION(BlueprintCallable, Category = "Board")
	void Report(FName WingName, int32 StandingCount);

	/** Exactly what the board is showing at this instant. */
	UFUNCTION(BlueprintPure, Category = "Board")
	FString GetReportedLine() const;

protected:
	virtual void BeginPlay() override;
};
