// Copyright CraftBench. All Rights Reserved.

#include "CraftBenchBareCharacter.h"

ACraftBenchBareCharacter::ACraftBenchBareCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.DoNotCreateDefaultSubobject(TEXT("AttributeSet")))
{
	// The suppression above is the ENTIRE difference from ACraftBenchCharacter:
	// the base ctor's CreateOptionalDefaultSubobject<UCraftBenchAttributeSet>
	// returns null (Optional is load-bearing — UE IGNORES the suppression for a
	// required subobject), so this pawn's ASC carries no attribute set until a
	// subclass builds one (stage 1 of a health-first task). The name
	// "AttributeSet" stays suppressed for the whole construction, so a stage-1
	// subclass must create its set under a DIFFERENT subobject name (e.g.
	// "HealthAttributes").
}
