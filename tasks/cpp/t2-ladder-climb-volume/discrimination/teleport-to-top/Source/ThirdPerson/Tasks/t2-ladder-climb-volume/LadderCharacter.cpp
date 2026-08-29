// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT "teleport-to-top" — see header. Volume-gated, but the climb
// is a single SetActorLocation to the ladder's top: the destination is right,
// the journey never happened.

#include "LadderCharacter.h"

ALadderCharacter::ALadderCharacter()
{
	Tags.Add(FName("ClimbHero"));
}

AActor* ALadderCharacter::FindLadder() const
{
	TArray<AActor*> Overlapping;
	GetOverlappingActors(Overlapping);
	for (AActor* Actor : Overlapping)
	{
		if (Actor != nullptr && Actor->ActorHasTag(FName(TEXT("LadderVolume"))))
		{
			return Actor;
		}
	}
	return nullptr;
}

void ALadderCharacter::DoClimbStart()
{
	if (const AActor* Ladder = FindLadder())
	{
		const FBox Bounds = Ladder->GetComponentsBoundingBox(true);
		FVector Spot = GetActorLocation();
		Spot.Z = Bounds.Max.Z + 100.0f;
		SetActorLocation(Spot, false, nullptr, ETeleportType::TeleportPhysics);
	}
}

void ALadderCharacter::DoClimbEnd()
{
}
