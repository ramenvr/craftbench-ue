// Copyright CraftBench. All Rights Reserved.
//
// The board over the host gate, for task t2-only-the-wing-you-called-opens.
//
// REFERENCE SOLUTION. The supplied board is a sign and a switch with nothing behind it;
// everything below Report() is the answer. The board is the host for the work because
// the building is fixed -- every mark, post, fitting and this board are placed in a
// level that is not writable -- so a brand new class would never be instantiated.
//
// Three things are read from the world at the moment they are needed and never cached,
// and NONE of the three is knowable from the source alone:
//   * which wing a mark is calling  -- the marks are re-lettered while play is running;
//   * which part of the level a wing's fittings are kept in -- read off that wing's
//     own post, matched by name. The place's name is nothing like the wing's, so it
//     cannot be built out of the wing's name;
//   * how many of the called wing's fittings are actually standing -- COUNTED, not
//     assumed. The wings are different sizes and a wing arrives over several frames, so
//     a constant is wrong and so is the count taken at the instant of the step. That is
//     why the board keeps itself honest every frame instead of writing itself once.
//
// And one thing is deliberately NOT done: when a new wing is called, only the wing that
// was called BEFORE it is taken down. Never every section the building knows about --
// the hall was never called and must never be disturbed.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GateBoardActor.generated.h"

class USceneComponent;
class UPrimitiveComponent;
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
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Somebody has walked onto a call mark. */
	UFUNCTION()
	void OnSomebodyStepped(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	/** Bring the named wing into the host and take the previously called one out. */
	void CallWing(FName WingName);

	/** Which part of the level the named wing's fittings are kept in, read off that
	 *  wing's own post. NAME_None if no post carries that name. */
	FName SectionForWing(FName WingName) const;

	/** Bring a part of the level into the running world, or take it back out. */
	void ShowSection(FName SectionId, bool bStanding);

	/** How many of the named wing's fittings are standing in the host right now. */
	int32 CountStandingFittings(FName WingName) const;

	/** The wing called most recently, and the part of the level it came from. Empty
	 *  until somebody has stepped on a mark. */
	UPROPERTY()
	FName OpenWing;

	UPROPERTY()
	FName OpenSection;

	/** What the board is already saying, so it is only rewritten when it changes. */
	UPROPERTY()
	FName ShownWing;

	UPROPERTY()
	int32 ShownCount = -1;
};
