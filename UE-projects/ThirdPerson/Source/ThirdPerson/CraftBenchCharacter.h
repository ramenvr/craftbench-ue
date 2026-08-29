// Copyright CraftBench. All Rights Reserved.
//
// ACraftBenchCharacter — the generalizable substrate pawn for CraftBench motion
// and GAS tasks. Ported verbatim from the CraftBenchTemplate substrate
// 2026-08-05 (owner decision: gameplay tasks run on the ThirdPerson substrate,
// which ships Manny/Quinn natively — no asset drops). Same class name on
// purpose: fixtures and the L2I graders resolve the scaffold by NAME +
// derivation, so the port keeps every consumer's diff minimal.
//
// Owns the un-conceptual GAS plumbing the agent shouldn't have to re-derive
// headless:
//   - a pawn-owned UAbilitySystemComponent (avatar = owner = this pawn; NOT a
//     PlayerState-owned ASC — minimal model, right for atomic single-player PIE);
//   - InitAbilityActorInfo in both BeginPlay and PossessedBy (idempotent);
//   - a minimal UCraftBenchAttributeSet;
//   - an EditAnywhere GrantedAbilities array auto-granted on the authority — the
//     agent fills it (C++ subclass ctor OR Blueprint defaults) and that is the
//     ONLY GAS wiring the agent must do besides authoring the ability;
//   - the "CraftBenchPawn" identity tag.
//
// Deliberately an ACharacter subclass (not AThirdPersonCharacter): the GAS
// fixtures spawn + possess it themselves in headless PIE, so the stock
// template's Enhanced Input / camera rig would be dead weight there. The
// substrate's native mannequin content under /Game/Characters/ is what a
// Blueprint subclass assigns for visual representation.
//
// The base ships GrantedAbilities EMPTY — an unmodified pawn grants nothing, so a
// tag-trigger finds no ability and the GAS task fails (anti-gaming).
//
// 2026-08-05 health-first redefinition (gp-poison-dot-stack-cpp / -bp): THIS class
// deliberately KEEPS pre-constructing the attribute set — ripping it out would
// break every task whose fixture presets/reads attributes on a generic-scaffold
// pawn (gp-glide-stamina-cpp's fixture writes+reads Power on this very set, and its
// committed references subclass this class). The stage-1 ("the agent BUILDS the
// health system") seam is the ABSTRACT sibling ACraftBenchBareCharacter
// (CraftBenchBareCharacter.h), which suppresses the subobject; health-first
// tasks derive from it. UCraftBenchAttributeSet remains the exported contract
// class either way.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AbilitySystemInterface.h"
#include "CraftBenchCharacter.generated.h"

class UAbilitySystemComponent;
class UCraftBenchAttributeSet;
class UGameplayAbility;
class UInputAction;
struct FInputActionValue;

UCLASS()
class THIRDPERSON_API ACraftBenchCharacter : public ACharacter, public IAbilitySystemInterface
{
	GENERATED_BODY()

public:
	/** FObjectInitializer pass-through so a subclass can suppress the pre-built
	 *  attribute set via DoNotCreateDefaultSubobject (the stage-1 seam — see
	 *  ACraftBenchBareCharacter). */
	ACraftBenchCharacter(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());

	//~ IAbilitySystemInterface.
	virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;

	/** Abilities auto-granted on the authority at BeginPlay/PossessedBy. The agent
	 *  populates this (C++ ctor or BP class defaults) with the ability they author. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|GAS")
	TArray<TSubclassOf<UGameplayAbility>> GrantedAbilities;

	// --- Human-drivable input (Option C, owner-authorised 2026-08-18) -----------
	//
	// Before this, the class derived from bare ACharacter with NO input wiring at
	// all, so nobody could drive a task pawn even after possessing it. The
	// deliverable of every task in this family is a gameplay ability, and it was
	// observable only by reading a verdict.
	//
	// The mapping context is deliberately NOT applied here: it comes from the
	// player controller (BP_ThirdPersonPlayerController's DefaultMappingContexts),
	// exactly as Epic's own AThirdPersonCharacter relies on. Adding it in both
	// places would double-register the context.
	//
	// Defaults are resolved in the constructor from the stock /Game/Input assets, so
	// a task pawn is drivable out of the box; an agent may still override them per
	// task in the ctor or in Blueprint class defaults.

	/** Move (2D axis). */
	UPROPERTY(EditAnywhere, Category = "CraftBench|Input")
	UInputAction* MoveAction;

	/** Look (2D axis, gamepad). */
	UPROPERTY(EditAnywhere, Category = "CraftBench|Input")
	UInputAction* LookAction;

	/** Look (2D axis, mouse). */
	UPROPERTY(EditAnywhere, Category = "CraftBench|Input")
	UInputAction* MouseLookAction;

	/** Jump (boolean). */
	UPROPERTY(EditAnywhere, Category = "CraftBench|Input")
	UInputAction* JumpAction;

	/** Bind the actions above. Runs via PawnClientRestart, which only fires for a
	 *  LOCAL controller — which is why the fixture must possess the PIE player
	 *  controller rather than spawning an AI one. */
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

protected:
	virtual void PossessedBy(AController* NewController) override;
	virtual void BeginPlay() override;

	/** Move/look handlers, mirroring Epic's AThirdPersonCharacter so a reviewer's
	 *  muscle memory transfers between a task map and the template. */
	void Move(const struct FInputActionValue& Value);
	void Look(const struct FInputActionValue& Value);

	void InitAbilityActorInfo();
	void GrantDefaultAbilities();

	UPROPERTY(VisibleAnywhere, Category = "CraftBench|GAS")
	TObjectPtr<UAbilitySystemComponent> AbilitySystemComponent;

	/** Pre-built minimal attribute set. NULL on the ACraftBenchBareCharacter
	 *  lineage (subobject suppressed — the stage-1 seam), so null-check it. */
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> AttributeSet;

private:
	bool bAbilitiesGranted = false;
};
