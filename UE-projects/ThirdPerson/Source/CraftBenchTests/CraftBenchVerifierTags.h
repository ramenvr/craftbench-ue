// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
// Changes here require maintainer review (.github/CODEOWNERS).
//
// FCraftBenchVerifierTags — the gameplay tags the VERIFIER owns.
//
// V1.1 (the g2 verifier-extensions spec §5). These tags are stamped as
// ASSET TAGS onto the runtime-built UGameplayEffects the fixture applies TO the
// agent's pawn (CraftBenchTestEffects.h). They exist so a fixture can tell its
// OWN effects apart from each other and from anything the submission applied —
// by tag query, and independently of the Spec.Def pointer identity that
// ACraftBenchPawnFunctionalTest::PawnEffectCount() uses.
//
// WHY THEY LIVE HERE AND NOT IN Source/ThirdPerson/CraftBenchGameplayTags.h:
// that file is in the AGENT-WRITABLE runtime module. Only a tag the AGENT must
// carry (e.g. "Ability.Poison", which the submitted ability is required to
// have) may live there. A tag the verifier stamps on its own effects must sit
// in the deny-write module, or a submission could redefine, shadow or read it.
//
// STYLE: static accessor methods, not raw FNativeGameplayTag globals — the same
// reason the runtime module's FCraftBenchGameplayTags gives (a method exports
// cleanly across modules; UE_DECLARE_GAMEPLAY_TAG_EXTERN emits a bare `extern
// FNativeGameplayTag` with no API macro, so a cross-module consumer would fail
// to link).
//
// The "CraftBench.Verifier.*" namespace is deliberate: a fixture can match the
// whole family with an FGameplayTagQuery on Root() (e.g. to assert a submission
// granted itself immunity to every verifier-applied effect, or to assert it did
// NOT), and no agent-authored tag can collide inside it without the collision
// being visible in the submission.

#pragma once

#include "CoreMinimal.h"
#include "GameplayTagContainer.h"

struct CRAFTBENCHTESTS_API FCraftBenchVerifierTags
{
	/** "CraftBench.Verifier" — the parent of every tag below. Resolved from a
	 *  child's direct parent rather than registered separately, so there is
	 *  exactly one registration site per tag name. Use it to build a family
	 *  query (FGameplayEffectQuery::EffectTagQuery) over all verifier effects. */
	static FGameplayTag Root();

	/** "CraftBench.Verifier.Drain" — a PERIODIC effect the world applies to the
	 *  pawn that reduces an attribute over time (the externally-applied DoT the
	 *  agent's feature is supposed to notice, resist, clamp or cleanse). */
	static FGameplayTag Drain();

	/** "CraftBench.Verifier.Heal" — a PERIODIC effect the world applies that
	 *  increases an attribute over time (the HoT half; the clamp gate's driver). */
	static FGameplayTag Heal();

	/** "CraftBench.Verifier.Delta" — a one-shot INSTANT change to an attribute
	 *  (the "the world hits you once" shape). Instant effects execute and are
	 *  never added to the active container, so PawnEffectCount() is always 0 for
	 *  one of these; gate on the VALUE. */
	static FGameplayTag Delta();

	/** "CraftBench.Verifier.Modifier" — an INFINITE, non-periodic modifier the
	 *  world imposes (a competing buff/debuff on a current value). Moves the
	 *  post-aggregator read only; the base value is untouched. That asymmetry is
	 *  exactly what PawnAttribute() vs PawnAttributeBase() exists to expose. */
	static FGameplayTag Modifier();

	/** "CraftBench.Verifier.Control" — the CONTROL leg. A second, deliberately
	 *  inert or externally-calibrated effect applied alongside the real one so a
	 *  fixture can measure expected magnitude from outside the submission
	 *  instead of hard-coding it. Never the subject of a gate on its own. */
	static FGameplayTag Control();
};
