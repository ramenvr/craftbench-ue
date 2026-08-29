// Copyright CraftBench. All Rights Reserved.

#include "GuardSightFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr double kSettleS = 0.5;      // "within 0.5 seconds of any change"

	// UNDISCLOSED: fixture geometry and clocking.
	constexpr double kWaypointReachedCm = 90.0;
	// Modest on purpose: enough that a coordinate key is stale, small enough that the
	// staged wall still blocks the guard it was placed for -- which PrepareTest
	// asserts rather than assumes.
	constexpr double kJitterCm = 70.0;
	constexpr double kJitterDeg = 8.0;
	/** Aim at the character's chest, not its feet: a floor trace grazes the ground. */
	constexpr double kChestUu = 40.0;
	// Long enough that the half-second settle window is comfortably inside each
	// stop, so every position on the route is actually judged.
	constexpr double kDwellS = 2.5;
	/** How far the crate is nudged before play, along the looking guard's facing. */
	constexpr double kCrateShiftCm = -120.0;
}

AGuardSightFunctionalTest::AGuardSightFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

FVector AGuardSightFunctionalTest::EyeOf(AActor* Guard) const
{
	if (Guard == nullptr)
	{
		return FVector::ZeroVector;
	}
	// The guard's SUPPLIED eye point, by component name -- the same origin the task
	// tells the agent to look from.
	TArray<UStaticMeshComponent*> Meshes;
	Guard->GetComponents<UStaticMeshComponent>(Meshes);
	for (UStaticMeshComponent* M : Meshes)
	{
		if (M != nullptr && M->GetName() == TEXT("Eye"))
		{
			return M->GetComponentLocation();
		}
	}
	return Guard->GetActorLocation();
}

float AGuardSightFunctionalTest::RangeOf(AActor* Guard) const
{
	if (const FFloatProperty* P = Guard
			? FindFProperty<FFloatProperty>(Guard->GetClass(), TEXT("SightRangeUu"))
			: nullptr)
	{
		return P->GetPropertyValue_InContainer(Guard);
	}
	return 0.0f;
}

float AGuardSightFunctionalTest::HalfAngleOf(AActor* Guard) const
{
	if (const FFloatProperty* P = Guard
			? FindFProperty<FFloatProperty>(Guard->GetClass(), TEXT("SightHalfAngleDeg"))
			: nullptr)
	{
		return P->GetPropertyValue_InContainer(Guard);
	}
	return 0.0f;
}

bool AGuardSightFunctionalTest::ReadSpotted(AActor* Guard) const
{
	// THE LAMP, not a flag. The level asks a guard to "light its lamp red", and that
	// is what a reviewer sees; a bool saying so is not the thing. Reading the lamp
	// also means any legitimate route to lighting it grades the same.
	//
	// (The scaffold's own bSpotted is a plain member, not a UPROPERTY, so reflection
	// cannot see it at all -- a fixture written against it would have read false
	// forever and failed every correct answer. Found before the first run,
	// 2026-08-18.)
	if (Guard == nullptr)
	{
		return false;
	}
	TArray<UPointLightComponent*> Lamps;
	Guard->GetComponents<UPointLightComponent>(Lamps);
	for (UPointLightComponent* L : Lamps)
	{
		if (L == nullptr || L->GetName() != TEXT("AlertLamp"))
		{
			continue;
		}
		// Hidden and zero-intensity both read as dark: they look identical.
		if (!L->IsVisible() || L->bHiddenInGame)
		{
			return false;
		}
		return L->Intensity > 0.0f;
	}
	return false;
}

bool AGuardSightFunctionalTest::ComputeShouldSee(AActor* Guard) const
{
	UWorld* const World = GetWorld();
	if (Guard == nullptr || !Hero.IsValid() || World == nullptr)
	{
		return false;
	}
	const FVector Eye = EyeOf(Guard);
	const FVector Target = Hero->GetActorLocation() + FVector(0.0, 0.0, kChestUu);
	const FVector ToTarget = Target - Eye;

	// 1. Range, measured from the guard's own position.
	if (ToTarget.Size() > RangeOf(Guard))
	{
		return false;
	}
	// 2. Cone, measured from the direction it faces.
	const FVector Facing = Guard->GetActorForwardVector().GetSafeNormal();
	const double AngleDeg = FMath::RadiansToDegrees(FMath::Acos(
		FMath::Clamp(FVector::DotProduct(Facing, ToTarget.GetSafeNormal()), -1.0, 1.0)));
	if (AngleDeg > HalfAngleOf(Guard))
	{
		return false;
	}
	// 3. Nothing solid in between. The guard itself is ignored -- the eye sits in
	// front of its body, but a jittered facing can still clip it -- and so is the
	// character, which is the thing being looked at.
	FCollisionQueryParams Params(SCENE_QUERY_STAT(GuardSight), true);
	Params.AddIgnoredActor(Guard);
	Params.AddIgnoredActor(Hero.Get());
	FHitResult Hit;
	const bool bBlocked = World->LineTraceSingleByChannel(
		Hit, Eye, Target, ECC_Visibility, Params);
	return !bBlocked;
}

bool AGuardSightFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found, Crates;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("SightGuard")), Found);
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("SightCrate")), Crates);
	if (Found.Num() != 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - expected "
				 "two guards, found %d"), Found.Num()));
		return false;
	}
	if (Crates.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - expected "
				 "one crate, found %d"), Crates.Num()));
		return false;
	}
	Crate = Crates[0];
	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in "
				 "the yard"));
		return false;
	}
	for (AActor* A : Found)
	{
		if (RangeOf(A) <= 0.0f || HalfAngleOf(A) <= 0.0f)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a readable guard surface is missing - "
					 "SightRangeUu or SightHalfAngleDeg could not be read"));
			return false;
		}
		FGuard G;
		G.Actor = A;
		Guards.Add(G);
	}

	// JITTER. The prompt withholds the guards' coordinates; this makes even a leaked
	// coordinate stale, so a submission keyed on position rather than on what a guard
	// can see fails the every-frame comparison. Deterministic, not random: a fixed
	// offset per guard keeps the run reproducible.
	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		AActor* const A = Guards[i].Actor.Get();
		const double Sign = (i == 0) ? 1.0 : -1.0;
		A->SetActorLocation(A->GetActorLocation()
			+ FVector(Sign * kJitterCm * 0.5, Sign * kJitterCm, 0.0));
		A->SetActorRotation(A->GetActorRotation()
			+ FRotator(0.0, Sign * kJitterDeg, 0.0));
		Guards[i].Staged = A->GetActorTransform();
	}
	return true;
}

void AGuardSightFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}

	// The route: stand where BOTH guards would see the character if nothing were in
	// the way, then behind the crate, then behind the guards, then far away, then back
	// to the first spot. Waypoints are derived from the guards' JITTERED positions, so
	// the drive and the truth agree about where things are.
	const FVector A = Guards[0].Actor->GetActorLocation();
	const FVector B = Guards[1].Actor->GetActorLocation();
	const FVector Mid = (A + B) * 0.5;
	const FVector Facing = Guards[0].Actor->GetActorForwardVector().GetSafeNormal2D();
	const FVector Right = FVector::CrossProduct(FVector::UpVector, Facing);
	const FVector Hero0 = Hero->GetActorLocation();

	// MOVE THE CRATE, along the line the guard behind it looks down. Its placed
	// coordinates are as leakable as the guards', and the route's behind-the-crate
	// waypoint is derived from wherever it ends up -- so the occlusion still happens,
	// but a submission that hard-codes where the crate stands is reading a stale
	// number. Deterministic, like the guard jitter.
	if (Crate.IsValid())
	{
		Crate->SetActorLocation(Crate->GetActorLocation() + Facing * kCrateShiftCm);
	}

	const FVector InFront = Mid + Facing * 600.0 + FVector(0.0, 0.0, Hero0.Z - Mid.Z);
	const FVector BehindCrate = Crate.IsValid()
		? Crate->GetActorLocation() + Facing * 120.0 + FVector(0.0, 0.0, Hero0.Z - Mid.Z)
		: InFront;
	// Offset to the CLEAR guard's side, not straight back. A straight line from the
	// in-front stop to a point directly behind the guards runs through the wall the
	// walled guard hides behind -- and that wall has to be wide enough to cover a
	// jittered guard's sightlines, so it reaches across the direct path.
	const FVector BehindGuards = Mid - Facing * 500.0 - Right * 600.0
		+ FVector(0.0, 0.0, Hero0.Z - Mid.Z);
	const FVector FarAway = Mid + Facing * 1700.0 + FVector(0.0, 0.0, Hero0.Z - Mid.Z);

	Route = {InFront, BehindCrate, InFront, BehindGuards, InFront, FarAway, InFront};

	// Which guard the staged wall blocks is decided GEOMETRICALLY, after the jitter,
	// by tracing from each eye to the spot the character will stand on. Deciding it by
	// tag, name or index would be exactly the shortcut the task forbids the agent.
	{
		UWorld* const World = GetWorld();
		for (int32 i = 0; i < Guards.Num(); ++i)
		{
			FCollisionQueryParams Params(SCENE_QUERY_STAT(GuardStaging), true);
			Params.AddIgnoredActor(Guards[i].Actor.Get());
			FHitResult Hit;
			if (World->LineTraceSingleByChannel(Hit, EyeOf(Guards[i].Actor.Get()),
					InFront + FVector(0.0, 0.0, kChestUu), ECC_Visibility, Params))
			{
				BlockedIndex = i;
			}
		}
		if (BlockedIndex == INDEX_NONE)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - "
					 "neither guard is blocked by the wall, so there is no control"));
			return;
		}
	}

	TArray<double> Schedule;
	for (int32 i = 0; i < 18; ++i)
	{
		Schedule.Add(1.0 + 2.0 * i);
	}
	// The SENTINEL: the base declares success the moment the last scheduled checkpoint
	// is crossed, and this fixture grades off measured sight windows.
	Schedule.Add(90.0);
	TimeLimitMargin = 6.0f;
	SetCheckpointSchedule(Schedule);
}

FString AGuardSightFunctionalTest::Diagnose(AActor* Guard) const
{
	UWorld* const World = GetWorld();
	if (Guard == nullptr || !Hero.IsValid() || World == nullptr)
	{
		return TEXT("unresolved");
	}
	const FVector Eye = EyeOf(Guard);
	const FVector Target = Hero->GetActorLocation() + FVector(0.0, 0.0, kChestUu);
	const FVector ToTarget = Target - Eye;
	const FVector Facing = Guard->GetActorForwardVector().GetSafeNormal();
	const double AngleDeg = FMath::RadiansToDegrees(FMath::Acos(
		FMath::Clamp(FVector::DotProduct(Facing, ToTarget.GetSafeNormal()), -1.0, 1.0)));
	FCollisionQueryParams Params(SCENE_QUERY_STAT(GuardSightDiag), true);
	Params.AddIgnoredActor(Guard);
	Params.AddIgnoredActor(Hero.Get());
	FHitResult Hit;
	const bool bHit = World->LineTraceSingleByChannel(
		Hit, Eye, Target, ECC_Visibility, Params);
	return FString::Printf(TEXT("d=%.0f a=%.0f blocker=%s"), ToTarget.Size(), AngleDeg,
		bHit ? *GetNameSafe(Hit.GetActor()) : TEXT("none"));
}

void AGuardSightFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString S;
	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		S += FString::Printf(TEXT("g%d[truth=%d lit=%d %s%s] "), i,
			Guards[i].bShouldSee ? 1 : 0,
			ReadSpotted(Guards[i].Actor.Get()) ? 1 : 0,
			*Diagnose(Guards[i].Actor.Get()),
			i == BlockedIndex ? TEXT(" WALLED") : TEXT(""));
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t1-guard calib] cp%d t=%.2f %swindows=%d wp=%d"),
		Index, Now, *S, SightWindows, Waypoint);
}

void AGuardSightFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !Hero.IsValid() || Guards.Num() != 2)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	bool bAnyTruth = false;
	for (int32 i = 0; i < Guards.Num(); ++i)
	{
		FGuard& G = Guards[i];
		AActor* const A = G.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("GuardsStayResolvable: a guard could no longer be resolved"));
			return;
		}
		const bool bTruth = ComputeShouldSee(A);
		if (bTruth != G.bShouldSee)
		{
			G.bShouldSee = bTruth;
			G.ChangedAt = Now;
		}
		if (bTruth) { G.bEverSeenTrue = true; }
		bAnyTruth = bAnyTruth || bTruth;

		const bool bLit = ReadSpotted(A);
		// Judged only once the half second the level allows has passed since the truth
		// last changed -- so a correct answer is never failed for its settle time.
		if (Now > G.ChangedAt + kSettleS)
		{
			if (bTruth && !bLit)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("LampLitWhileVisible: a guard could see the character and its "
						 "lamp was dark (%.0f uu away, %.0f deg off its facing, "
						 "nothing in between)"),
					FVector::Dist(EyeOf(A), Hero->GetActorLocation()),
					FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
						FVector::DotProduct(A->GetActorForwardVector().GetSafeNormal(),
							(Hero->GetActorLocation() - EyeOf(A)).GetSafeNormal()),
						-1.0, 1.0)))));
				return;
			}
			if (!bTruth && bLit)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("LampDarkWhenNotVisible: a guard lit its lamp while it could "
						 "not see the character (%.0f uu away, %.0f deg off its "
						 "facing)"),
					FVector::Dist(EyeOf(A), Hero->GetActorLocation()),
					FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
						FVector::DotProduct(A->GetActorForwardVector().GetSafeNormal(),
							(Hero->GetActorLocation() - EyeOf(A)).GetSafeNormal()),
						-1.0, 1.0)))));
				return;
			}
			if (bTruth && bLit) { G.bEverCorrectlyLit = true; }
		}
	}

	// THE CONTROL. The walled guard's truth must never become true. WHO that failure
	// belongs to depends on why: the prompt forbids moving the guards, so a guard that
	// has left the transform PrepareTest gave it is the submission's doing and grades
	// as a FAIL -- while a guard that never moved and can nonetheless see means the
	// YARD is mis-staged, which is ours, and must never be scored against a model.
	// (Measured 2026-08-18: a wall that cleared the placed positions stopped clearing
	// the jittered ones, and a correct reference solution FAILED this line.)
	if (Guards.IsValidIndex(BlockedIndex) && Guards[BlockedIndex].bEverSeenTrue)
	{
		const FGuard& Walled = Guards[BlockedIndex];
		AActor* const A = Walled.Actor.Get();
		const bool bMoved = A == nullptr
			|| !A->GetActorLocation().Equals(Walled.Staged.GetLocation(), 1.0)
			|| !A->GetActorRotation().Equals(Walled.Staged.Rotator(), 0.5f);
		if (bMoved)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheWalledGuardNeverSees: the guard behind the wall was moved "
					 "away from where the yard put it (now %s, staged %s) and could "
					 "then see the character; the brief forbids moving the guards"),
				*(A ? A->GetActorLocation() : FVector::ZeroVector).ToCompactString(),
				*Walled.Staged.GetLocation().ToCompactString()));
		}
		else
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the guard behind the wall never moved and "
					 "could still see the character - the wall does not cover its "
					 "sightlines across the staged jitter, so the control is not "
					 "controlling anything. This is a staging fault, not a "
					 "submission fault."));
		}
		return;
	}

	if (bAnyTruth && !bWasVisibleToAny) { ++SightWindows; }
	bWasVisibleToAny = bAnyTruth;

	if (Route.IsValidIndex(Waypoint))
	{
		const FVector Here = Hero->GetActorLocation();
		const FVector Target = Route[Waypoint];
		const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
		if (Flat.Size2D() <= kWaypointReachedCm)
		{
			// STAND here first. Advancing on arrival consumed three waypoints in the
			// first second and the character was never anywhere long enough for a
			// guard to be judged on it.
			if (DwellUntil < 0.0) { DwellUntil = Now + kDwellS; }
			else if (Now >= DwellUntil) { ++Waypoint; DwellUntil = -1.0; }
		}
		else { Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f); }
	}
}

void AGuardSightFunctionalTest::OnCheckpoint(int32 Index, double TimeSeconds)
{
	if (Guards.Num() != 2)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : TimeSeconds;
	LogCalib(Index, Now);

	if (Index < 18)
	{
		return;
	}
	// The SENTINEL, and the gates that are vacuous unless their leg happened.
	if (Waypoint < Route.Num())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRouteWasWalked: the run never finished its route (%d of %d "
				 "waypoints), so most of what this level asks was never measured"),
			Waypoint, Route.Num()));
		return;
	}
	if (SightWindows < 3)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("LampLitWhileVisible: the character only became visible %d time(s), "
				 "so lighting again on every return was never measured"),
			SightWindows));
		return;
	}
	const int32 ClearIndex = 1 - BlockedIndex;
	if (!Guards[ClearIndex].bEverCorrectlyLit)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("LampLitWhileVisible: the guard with a clear view never lit its lamp "
				 "at all"));
		return;
	}
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("the guard with a clear view lit red exactly while it could see the "
			 "character and went dark behind the crate, behind its back and out of "
			 "range, and the guard behind the wall stayed dark throughout"));
}
