// Copyright CraftBench. All Rights Reserved.
//
// ACraftBenchBareCharacter — the STAGE-1 base pawn (2026-08-05 health-first
// redefinition, gp-poison-dot-stack-cpp / gp-poison-dot-stack-bp): identical GAS
// plumbing to ACraftBenchCharacter (pawn-owned ASC, InitAbilityActorInfo,
// GrantedAbilities auto-grant, "CraftBenchPawn" tag) EXCEPT the pre-built
// attribute set — the "AttributeSet" default subobject is suppressed, so this
// pawn owns an ability system and NO health resource. Stage 1 of a health-first
// task is the agent BUILDING that resource on a subclass of this class:
//   - C++: construct a UCraftBenchAttributeSet default subobject on the
//     subclass (the pawn-owned ASC auto-registers owner-outer'd attribute sets
//     during InitializeComponent) and initialize Health. NOTE: the subobject
//     name "AttributeSet" stays suppressed for the whole construction of this
//     lineage, so use a DIFFERENT subobject name (e.g. "HealthAttributes").
//   - Blueprint: register the provided attribute set through an editor-visible
//     route on the inherited ASC and initialize Health (the task spec states
//     the observable contract; the route is the agent's choice).
// UCraftBenchAttributeSet remains the exported contract class the fixtures
// read (UCraftBenchAttributeSet::GetHealthAttribute()).
//
// ABSTRACT on purpose, and load-bearing twice:
//   1. ResolveAgentPawnClass skips CLASS_Abstract candidates, so this committed
//      class can never itself win L2 pawn resolution — it is a base to derive
//      from, not a pawn to grade, and every other task's resolution order is
//      untouched by committing it.
//   2. The -bp introspect scripts' "no native subclass of the scaffold" decoy
//      sweep exempts exactly this committed abstract base by /Script/ path (an
//      abstract native cannot be the resolved decoy — see the
//      resolved_pawn_is_blueprint check).
//
// The generic ACraftBenchCharacter keeps its pre-built set (gp-glide-stamina-cpp's
// fixture + committed references depend on it); a health-first submission that
// derives from IT instead of THIS class inherits a pre-built health system and
// fails the stage-1 derivation gate by name.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchBareCharacter.generated.h"

UCLASS(Abstract)
class CRAFTBENCHTEMPLATE_API ACraftBenchBareCharacter : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	ACraftBenchBareCharacter(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
};
