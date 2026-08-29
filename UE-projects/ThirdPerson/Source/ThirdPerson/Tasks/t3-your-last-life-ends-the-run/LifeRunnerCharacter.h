// Copyright CraftBench. All Rights Reserved.
//
// A runner for task t3-your-last-life-ends-the-run. Three of them stand at the near
// end of the floor, one on each painted marker disc. Each arrives visible, animated,
// drivable, with a row of six lamps floating over its head and a word floating beside
// them -- and with nothing at all that decides what either of those should say.
//
// Supplied and working:
//   * the lamp row  -- SetLitCount() / GetLitCount()
//   * the floating word -- SetStateWord() / GetStateWord()
// The lamps start dark and the word starts reading a placeholder. NOTHING CALLS
// EITHER OF THEM.
//
// There is deliberately no "lives remaining" number on this class. The lamp row is
// the only place a runner's remaining lives is ever shown, so making the row right is
// the same job as working the number out.
//
// This class is placed (or spawned) three times over. Keep the marking its
// constructor puts on it: the level tells one thing from another by those markings.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "LifeRunnerCharacter.generated.h"

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

private:
	/** The two looks a bulb takes. Swapped whole rather than driven by a material
	 *  parameter: not every prototype material here carries a colour parameter, and a
	 *  set that silently does nothing would leave the row invisible while looking like
	 *  it had worked. */
	UPROPERTY()
	UMaterialInterface* BulbLitLook = nullptr;

	UPROPERTY()
	UMaterialInterface* BulbDarkLook = nullptr;
};
