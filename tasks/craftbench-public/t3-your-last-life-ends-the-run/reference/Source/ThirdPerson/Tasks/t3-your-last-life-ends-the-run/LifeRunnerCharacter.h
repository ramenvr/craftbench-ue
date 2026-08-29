// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t3-your-last-life-ends-the-run.
//
// A runner owns its whole run and nothing else's: its own marker, its own tally of
// deaths, its own terminal answer, its own lamp row and its own word. Three of these
// stand in the level and none of them can reach another.
//
// Two things are deliberately NOT stored:
//   * remaining lives -- it is derived, every frame, as (the number currently painted
//     on this runner's own marker) minus (the deaths this runner has suffered),
//     floored at zero. The paint moves while the run is going, so anything latched at
//     the start would be wrong from the first re-paint.
//   * anything about the other runners.
// What IS latched is the terminal answer, and the lamp count at the moment it was
// reached -- because once a run is over it never changes again, whatever the board
// says afterwards.
//
// THE TWO TRIGGERS HAVE DIFFERENT SHAPES, and that is the whole trap. The crumbling
// ground is an EDGE: it costs a life on the step that carries a runner onto it and
// nothing afterwards. The finish is a CONDITION: standing on it with at least what it
// asks for wins, and both halves of that question move under the runner's feet with
// nothing to announce them -- the marker re-paints and so does the disc. So the finish
// is asked EVERY FRAME, not on an overlap event. An answer that models the finish the
// same way it models the ground never wins a run whose numbers moved while it stood
// still.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "LifeRunnerCharacter.generated.h"

class ALifeMarkerActor;
class AFinishDiscActor;
class UMaterialInterface;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ALifeRunnerCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ALifeRunnerCharacter();

	/** How many lamps the row holds. A runner is never shown more than this many. */
	static constexpr int32 LampCount = 6;

	/** The six bulbs of the row, in order from one end to the other. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runner")
	TArray<UStaticMeshComponent*> LampBulbs;

	/** The glow behind each bulb. Burning while that lamp is lit, out otherwise. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runner")
	TArray<UPointLightComponent*> LampGlows;

	/** The word that floats beside the lamp row. Starts on a placeholder. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runner")
	UTextRenderComponent* WordText = nullptr;

	/**
	 *  THE LAMP SWITCH. Lights the first Count lamps of the row, counting from one
	 *  end, and puts the rest out -- the glow and the bulb's look change together, so
	 *  what a person sees and what the row says can never disagree. Values outside
	 *  0..LampCount are pulled back into range.
	 */
	UFUNCTION(BlueprintCallable, Category = "Runner")
	void SetLitCount(int32 Count);

	/** How many lamps of this runner's row are actually burning right now. */
	UFUNCTION(BlueprintPure, Category = "Runner")
	int32 GetLitCount() const;

	/** THE WORD SWITCH. Writes the word that floats beside this runner's lamps. */
	UFUNCTION(BlueprintCallable, Category = "Runner")
	void SetStateWord(const FString& Word);

	/** The word this runner is showing right now. */
	UFUNCTION(BlueprintPure, Category = "Runner")
	FString GetStateWord() const;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** A run is going, or it is over one of the two ways. Never both, never back. */
	enum class ERunState : uint8
	{
		Running,
		Won,
		Lost
	};

	/** The live derivation: what this runner's own marker says now, minus the deaths
	 *  it has suffered, never below zero. */
	int32 RemainingLives() const;

	bool IsOnCrumblingGround() const;
	/** The finish disc this runner is standing on right now, or nullptr. */
	const AFinishDiscActor* FinishUnderfoot() const;

	void ClaimedByTheGround();
	void ReachedTheFinish();

	/** Puts the lamps and the word where this runner's state says they belong. */
	void ShowState();

	/** The marker this runner was standing on when the run opened. */
	TWeakObjectPtr<ALifeMarkerActor> OwnMarker;

	ERunState State = ERunState::Running;

	/** How many times the crumbling ground has claimed THIS runner. */
	int32 Deaths = 0;

	/** The lamp count frozen at the moment this runner's run ended. */
	int32 FrozenLitCount = 0;

	/** Entry into the crumbling ground is an edge, so the last frame is remembered. */
	bool bWasOnCrumblingGround = false;

	bool bReturnPending = false;
	double ReturnAtSeconds = -1.0;

	/** The two looks a bulb takes. Swapped whole rather than driven by a material
	 *  parameter: not every prototype material here carries a colour parameter, and a
	 *  set that silently does nothing would leave the row invisible while looking like
	 *  it had worked. */
	UPROPERTY()
	UMaterialInterface* BulbLitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* BulbDarkLook = nullptr;
};
