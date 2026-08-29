// Discrimination variant "wrong-category-log": anti-gaming note #2 (wrong log
// category). The literal is emitted once, in BeginPlay, at Display verbosity --
// but on a self-defined custom category instead of LogTemp, "hiding" the
// substring from any grep that ignores the category. Expected verdict: FAIL at
// the emission-count gate (the fixture's listener filters on InCategory ==
// LogTemp, so this emission is never counted and the checkpoint observes 0).

#include "SanityActor.h"

DEFINE_LOG_CATEGORY_STATIC(LogSanityCustom, Display, All);

ASanityActor::ASanityActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("SanityRoot"));
}

void ASanityActor::BeginPlay()
{
	Super::BeginPlay();
	UE_LOG(LogSanityCustom, Display, TEXT("CRAFTBENCH_SANITY_OK"));
}
