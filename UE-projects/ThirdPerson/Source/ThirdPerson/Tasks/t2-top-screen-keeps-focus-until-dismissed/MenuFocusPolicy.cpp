// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-top-screen-keeps-focus-until-dismissed/MenuFocusPolicy.h"

AMenuFocusPolicy::AMenuFocusPolicy()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName(TEXT("MenuFocusPolicy")));
}
