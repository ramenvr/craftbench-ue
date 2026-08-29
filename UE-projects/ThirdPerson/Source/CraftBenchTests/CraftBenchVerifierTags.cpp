// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.

#include "CraftBenchVerifierTags.h"

#include "GameplayTagContainer.h"

namespace
{
	// Registered from Config/DefaultGameplayTags.ini (substrate-committed,
	// NOT config_writable in AGENT_WRITABLE.json - agents can read the five
	// generic names but never write the file). This REPLACES the previous
	// UE_DEFINE_GAMEPLAY_TAG statics: native-tag registration from a
	// Type=Editor module trips the NativeGameplayTags.cpp:41 ensure on UE 5.8
	// ("module type must be Runtime or RuntimeAndProgram") at DLL attach, and
	// the follow-on exception killed every attended editor boot (2026-08-12;
	// the -unattended verifier editors survived the handled ensure, which is
	// why refgate stayed green while the authoring lane died).
	//
	// The parent "CraftBench.Verifier" is created implicitly by the tag
	// manager from the ini leaves; Root() derives it from a leaf so the two
	// can never drift.
	FGameplayTag Leaf(const TCHAR* Name)
	{
		// ErrorIfNotFound=true: a workdir whose substrate lost the ini FAILS
		// LOUDLY here rather than handing fixtures an empty tag.
		return FGameplayTag::RequestGameplayTag(FName(Name), true);
	}
}

FGameplayTag FCraftBenchVerifierTags::Root()
{
	// GameplayTagContainer.h:147 — FGameplayTag::RequestDirectParent(). Derived
	// rather than registered so "CraftBench.Verifier" cannot drift out of sync
	// with the leaves if a leaf is ever renamed.
	return Leaf(TEXT("CraftBench.Verifier.Drain")).RequestDirectParent();
}

FGameplayTag FCraftBenchVerifierTags::Drain()
{
	return Leaf(TEXT("CraftBench.Verifier.Drain"));
}

FGameplayTag FCraftBenchVerifierTags::Heal()
{
	return Leaf(TEXT("CraftBench.Verifier.Heal"));
}

FGameplayTag FCraftBenchVerifierTags::Delta()
{
	return Leaf(TEXT("CraftBench.Verifier.Delta"));
}

FGameplayTag FCraftBenchVerifierTags::Modifier()
{
	return Leaf(TEXT("CraftBench.Verifier.Modifier"));
}

FGameplayTag FCraftBenchVerifierTags::Control()
{
	return Leaf(TEXT("CraftBench.Verifier.Control"));
}
