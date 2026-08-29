// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.

#include "StealthYardFunctionalTest.h"

#include "CollisionQueryParams.h"
#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/EngineTypes.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/Class.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED in the prompt --------------------------------------------
	constexpr double kSettleS = 0.25;              // "a quarter of a second"

	// ---- UNDISCLOSED fixture clocking, staging and tolerances ---------------
	// Every one of these is a WIDENING of the disclosed contract, never a narrowing.
	constexpr double kSuppressAfterS = kSettleS * 1.6;   // 0.40 s
	constexpr double kDeadlineS = 0.4;             // 1.6x the disclosed quarter second
	constexpr double kMarginAngleDeg = 3.0;
	constexpr double kMarginReachFrac = 0.06;
	constexpr double kMarginEdgeUu = 40.0;         // a footprint edge this near the line
	constexpr double kPaceTolFrac = 0.01;          // 1% on a pace the yard dictates
	constexpr double kWatcherOnRoundUu = 60.0;
	constexpr double kPropMovedUu = 2.0;
	constexpr double kWaypointUu = 90.0;
	constexpr double kLampLitFloor = 0.5;

	// ---- the staging contract's own floors -----------------------------------
	constexpr double kMinCrossWindowS = 1.0;       // assertable time inside a crossing
	constexpr double kMinTurnClearanceS = 2.0;     // and to the nearest turn, both ends
	constexpr double kMinShadowWindowS = 3.0;      // visible time at the shadow spot
	constexpr double kMinTruckCoverS = 1.5;        // the truck lying across the line
	constexpr double kRouteFromRoundUu = 400.0;    // no route point nearer a round
	constexpr double kRouteFromSolidUu = 250.0;    // nor any solid thing
	constexpr double kOtherWatcherMargin = 1.25;   // "nobody unplanned is looking"

	// ---- the watch change ----------------------------------------------------
	constexpr float kRestageReachMul = 1.2f;
	constexpr float kRestageAngleMul = 0.6f;
	constexpr float kRestagePaceMul = 1.25f;
	constexpr double kRestageQuietS = 2.0;         // gates off either side of it

	// ---- the schedule --------------------------------------------------------
	// The drive is four rounds and eighteen phases and models roughly 350-450 s of
	// world time -- a range rather than a number, because three of its holds wait on
	// the YARD (a full lap of the covering watcher, the truck coming into step with a
	// cone) and the yard's own periods decide how long that takes. The graded
	// checkpoints cover 544 s of that; the SENTINEL sits past the end of the longest
	// drive this staging can produce, because ACraftBenchFunctionalTest::Tick ends the
	// test the moment the LAST scheduled checkpoint is sampled, and the fixture wants
	// to finish itself when its last phase completes instead. A phase that stalls is
	// caught by its own derived deadline long before this, so the sentinel costs
	// nothing unless something is already wrong.
	constexpr double kCheckpointEveryS = 8.0;
	constexpr int32 kGradedCheckpoints = 68;       // 8 s .. 544 s
	constexpr double kSentinelAtS = 640.0;

	// ---- the shadow entry ----------------------------------------------------
	constexpr double kRipeStepS = 0.10;            // forward-simulation step
	constexpr double kRipeClearSearchS = 14.0;     // how far ahead to look for the clear
	// The governor's own margin on a transit, kept SEPARATE from the shadow entry's
	// arrival uncertainty even though both are "the walk takes a little longer than
	// distance over speed". They pull opposite ways: a bigger number here makes the
	// governor more cautious (it must prove safety over a longer stretch), while a
	// bigger one there makes the shadow entry LESS likely to find a window. Coupling
	// them would mean tuning one and silently retuning the other.
	constexpr double kWalkHorizonSlackS = 0.75;
	// ACCELERATION SLOP ON A TRANSIT, and it is a UNCERTAINTY, not a delay: the runner
	// arrives somewhere between the ideal transit time and the ideal plus this, so the
	// covered stretch has to span the whole of that range and not merely its late end.
	// The character reaches its walk speed in about a quarter of a second, so 0.30 is
	// generous; every tenth of a second here is a tenth taken off the truck cover the
	// staging has to find, and the staging has only 2.3 s of it.
	constexpr double kRipeArriveSlackS = 0.30;

	// ---- the model's three readings -----------------------------------------
	constexpr int32 kRunning = 0;
	constexpr int32 kAway = 1;
	constexpr int32 kCaught = 2;

	const TCHAR* ReadingName(int32 R)
	{
		return (R == kCaught) ? TEXT("caught") : (R == kAway ? TEXT("away")
			: (R == kRunning ? TEXT("running") : TEXT("no single light")));
	}

	/** Flat distance from a point to a segment, all in XY. */
	double Dist2DToSegment(const FVector2D& P, const FVector2D& A, const FVector2D& B)
	{
		const FVector2D D = B - A;
		const double Denom = FVector2D::DotProduct(D, D);
		double T = 0.0;
		if (Denom > KINDA_SMALL_NUMBER)
		{
			T = FMath::Clamp(FVector2D::DotProduct(P - A, D) / Denom, 0.0, 1.0);
		}
		return FVector2D::Distance(P, A + D * T);
	}

	/** Flat distance from a point to an axis-aligned rectangle (0 when inside). */
	double Dist2DToRect(const FVector2D& P, const FVector2D& C, const FVector2D& H)
	{
		const double DX = FMath::Max(0.0, FMath::Abs(P.X - C.X) - H.X);
		const double DY = FMath::Max(0.0, FMath::Abs(P.Y - C.Y) - H.Y);
		return FMath::Sqrt(DX * DX + DY * DY);
	}
}

AStealthYardFunctionalTest::AStealthYardFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Reflection. Every number the yard is graded against is read BY NAME, never through
// a cast: the fixture never needs the agent's class layout, and the same helpers write
// the four numbers the sergeant re-sets at the watch change.
//
// This buys avoiding a cast and NOTHING MORE. The watchers, posts, mast, plate, gate,
// truck and blockers are placed instances in a committed .umap under a deny-listed
// path, so the agent can neither rename these classes nor subclass them usefully.
// ---------------------------------------------------------------------------

float AStealthYardFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0.0f;
}

int32 AStealthYardFunctionalTest::ReadInt(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0;
}

FName AStealthYardFunctionalTest::ReadName(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return NAME_None;
}

FVector AStealthYardFunctionalTest::ReadVector(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	const FStructProperty* const P = A
		? FindFProperty<FStructProperty>(A->GetClass(), Name) : nullptr;
	if (P != nullptr && P->Struct == TBaseStructure<FVector>::Get())
	{
		bOk = true;
		return *P->ContainerPtrToValuePtr<FVector>(A);
	}
	bOk = false;
	return FVector::ZeroVector;
}

bool AStealthYardFunctionalTest::WriteFloat(AActor* A, const TCHAR* Name,
	float Value) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AStealthYardFunctionalTest::WriteName(AActor* A, const TCHAR* Name,
	FName Value) const
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool AStealthYardFunctionalTest::CallBoolFunc(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	bOk = false;
	if (A == nullptr)
	{
		return false;
	}
	UFunction* const Func = A->FindFunction(FName(Name));
	if (Func == nullptr || Func->ParmsSize <= 0)
	{
		return false;
	}
	FProperty* const Ret = Func->GetReturnProperty();
	FBoolProperty* const RetBool = CastField<FBoolProperty>(Ret);
	if (RetBool == nullptr)
	{
		return false;
	}
	TArray<uint8> Parms;
	Parms.SetNumZeroed(int32(Func->ParmsSize));
	const_cast<AActor*>(A)->ProcessEvent(Func, Parms.GetData());
	bOk = true;
	return RetBool->GetPropertyValue_InContainer(Parms.GetData());
}

FVector AStealthYardFunctionalTest::CallVectorFunc(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	bOk = false;
	if (A == nullptr)
	{
		return FVector::ZeroVector;
	}
	UFunction* const Func = A->FindFunction(FName(Name));
	if (Func == nullptr || Func->ParmsSize <= 0)
	{
		return FVector::ZeroVector;
	}
	FStructProperty* const Ret = CastField<FStructProperty>(Func->GetReturnProperty());
	if (Ret == nullptr || Ret->Struct != TBaseStructure<FVector>::Get())
	{
		return FVector::ZeroVector;
	}
	TArray<uint8> Parms;
	Parms.SetNumZeroed(int32(Func->ParmsSize));
	const_cast<AActor*>(A)->ProcessEvent(Func, Parms.GetData());
	FVector Out = FVector::ZeroVector;
	Ret->CopySingleValue(&Out, Ret->ContainerPtrToValuePtr<void>(Parms.GetData()));
	bOk = true;
	return Out;
}

double AStealthYardFunctionalTest::LightIntensity(const AActor* A,
	const TCHAR* ComponentName) const
{
	if (A == nullptr)
	{
		return -1.0;
	}
	TArray<UPointLightComponent*> Lights;
	const_cast<AActor*>(A)->GetComponents<UPointLightComponent>(Lights);
	for (const UPointLightComponent* L : Lights)
	{
		if (L == nullptr || L->GetName() != FString(ComponentName))
		{
			continue;
		}
		// Hidden and zero-intensity both read as dark: they look identical.
		if (!L->IsVisible() || L->bHiddenInGame)
		{
			return 0.0;
		}
		return double(L->Intensity);
	}
	return -1.0;
}

double AStealthYardFunctionalTest::AnyLightIntensity(const AActor* A) const
{
	if (A == nullptr)
	{
		return -1.0;
	}
	TArray<UPointLightComponent*> Lights;
	const_cast<AActor*>(A)->GetComponents<UPointLightComponent>(Lights);
	for (const UPointLightComponent* L : Lights)
	{
		if (L == nullptr)
		{
			continue;
		}
		if (!L->IsVisible() || L->bHiddenInGame)
		{
			return 0.0;
		}
		return double(L->Intensity);
	}
	return -1.0;
}

// ---------------------------------------------------------------------------
// The oracle: the same rule the yard is asked to implement, run against the same live
// transforms and the same live numbers.
// ---------------------------------------------------------------------------

void AStealthYardFunctionalTest::RebuildFootprints()
{
	Footprints.Reset();
	TruckFootprintIndex = INDEX_NONE;
	for (int32 i = 0; i < Blockers.Num(); ++i)
	{
		const AActor* const B = Blockers[i].Get();
		if (B == nullptr)
		{
			continue;
		}
		bool bOk = false;
		const FVector Half = ReadVector(B, TEXT("BlockHalfExtentUu"), bOk);
		const FVector At = B->GetActorLocation();
		FFootprint F;
		F.Centre = FVector2D(At.X, At.Y);
		F.Half = FVector2D(FMath::Max(1.0, Half.X), FMath::Max(1.0, Half.Y));
		F.Label = FString::Printf(TEXT("block %d"), i + 1);
		Footprints.Add(F);
	}
	if (const AActor* const T = Truck.Get())
	{
		const FVector At = T->GetActorLocation();
		FFootprint F;
		F.Centre = FVector2D(At.X, At.Y);
		F.Half = FVector2D(FMath::Max(1.0, TruckHalf.X), FMath::Max(1.0, TruckHalf.Y));
		F.Label = TEXT("the truck");
		TruckFootprintIndex = Footprints.Num();
		Footprints.Add(F);
	}
}

bool AStealthYardFunctionalTest::SegmentHitsRect(const FVector2D& P, const FVector2D& Q,
	const FVector2D& C, const FVector2D& H)
{
	double Lo = 0.0;
	double Hi = 1.0;
	const FVector2D D = Q - P;
	const double Origin[2] = { P.X, P.Y };
	const double Delta[2] = { D.X, D.Y };
	const double Centre[2] = { C.X, C.Y };
	const double Halfs[2] = { H.X, H.Y };
	for (int32 Axis = 0; Axis < 2; ++Axis)
	{
		if (FMath::Abs(Delta[Axis]) < 1.0e-9)
		{
			if (Origin[Axis] < Centre[Axis] - Halfs[Axis]
				|| Origin[Axis] > Centre[Axis] + Halfs[Axis])
			{
				return false;
			}
			continue;
		}
		double T1 = (Centre[Axis] - Halfs[Axis] - Origin[Axis]) / Delta[Axis];
		double T2 = (Centre[Axis] + Halfs[Axis] - Origin[Axis]) / Delta[Axis];
		if (T1 > T2)
		{
			Swap(T1, T2);
		}
		Lo = FMath::Max(Lo, T1);
		Hi = FMath::Min(Hi, T2);
		if (Lo > Hi)
		{
			return false;
		}
	}
	return true;
}

double AStealthYardFunctionalTest::FootprintEdgeMargin(const FVector2D& P,
	const FVector2D& Q) const
{
	// How near the flat line comes to CHANGING its answer about a footprint: the
	// distance from the nearest corner of every rectangle to the line, or from the
	// line's own endpoints to the rectangle. Cheap, conservative, and only ever used
	// to decline to judge a frame.
	double Best = 1.0e30;
	for (const FFootprint& F : Footprints)
	{
		const FVector2D Corners[4] = {
			FVector2D(F.Centre.X - F.Half.X, F.Centre.Y - F.Half.Y),
			FVector2D(F.Centre.X + F.Half.X, F.Centre.Y - F.Half.Y),
			FVector2D(F.Centre.X + F.Half.X, F.Centre.Y + F.Half.Y),
			FVector2D(F.Centre.X - F.Half.X, F.Centre.Y + F.Half.Y) };
		for (const FVector2D& Corner : Corners)
		{
			Best = FMath::Min(Best, Dist2DToSegment(Corner, P, Q));
		}
	}
	return Best;
}

bool AStealthYardFunctionalTest::ModelCanSeeFrom(const FWatcher& W, const FVector& Eye,
	const FVector& Facing, const FVector& Point, bool bIncludeTruck) const
{
	// FLAT: the yard is level and the prompt says height plays no part.
	const FVector2D E(Eye.X, Eye.Y);
	const FVector2D P(Point.X, Point.Y);
	const FVector2D To = P - E;
	const double Distance = To.Size();
	// INCLUSIVE at the edge, exactly as the prompt states.
	if (Distance > double(W.Reach))
	{
		return false;
	}
	if (Distance > KINDA_SMALL_NUMBER)
	{
		const FVector2D Fwd = FVector2D(Facing.X, Facing.Y).GetSafeNormal();
		const double Cos = FVector2D::DotProduct(Fwd, To / Distance);
		const double AngleDeg = FMath::RadiansToDegrees(
			FMath::Acos(FMath::Clamp(Cos, -1.0, 1.0)));
		if (AngleDeg > double(W.HalfAngleDeg))
		{
			return false;
		}
	}
	for (int32 i = 0; i < Footprints.Num(); ++i)
	{
		if (!bIncludeTruck && i == TruckFootprintIndex)
		{
			continue;
		}
		if (SegmentHitsRect(E, P, Footprints[i].Centre, Footprints[i].Half))
		{
			return false;
		}
	}
	return true;
}

bool AStealthYardFunctionalTest::TruckOnLineAt(const FVector& Eye,
	const FVector& Point, const FVector2D& TruckCentre) const
{
	return SegmentHitsRect(FVector2D(Eye.X, Eye.Y), FVector2D(Point.X, Point.Y),
		TruckCentre, FVector2D(FMath::Max(1.0, TruckHalf.X),
							   FMath::Max(1.0, TruckHalf.Y)));
}

bool AStealthYardFunctionalTest::ModelCanSeeWithTruckAt(const FWatcher& W,
	const FVector& Eye, const FVector& Facing, const FVector& Point,
	const FVector2D& TruckCentre) const
{
	// The static half first: reach, view width and the crates and the wall where they
	// stand (they never move, so "where they stand" is the same question at any time).
	if (!ModelCanSeeFrom(W, Eye, Facing, Point, /*bIncludeTruck=*/false))
	{
		return false;
	}
	return !TruckOnLineAt(Eye, Point, TruckCentre);
}

bool AStealthYardFunctionalTest::ModelCanSee(const FWatcher& W, const FVector& Point,
	bool bIncludeTruck, double& OutDistance, double& OutAngleDeg) const
{
	OutDistance = 0.0;
	OutAngleDeg = 180.0;
	const AActor* const A = W.Actor.Get();
	if (A == nullptr)
	{
		return false;
	}
	const FVector Eye = A->GetActorLocation();
	const FVector2D To(Point.X - Eye.X, Point.Y - Eye.Y);
	OutDistance = To.Size();
	if (OutDistance > KINDA_SMALL_NUMBER)
	{
		const FVector Fwd = A->GetActorForwardVector();
		const FVector2D Facing = FVector2D(Fwd.X, Fwd.Y).GetSafeNormal();
		OutAngleDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
			FVector2D::DotProduct(Facing, To / OutDistance), -1.0, 1.0)));
	}
	else
	{
		OutAngleDeg = 0.0;
	}
	return ModelCanSeeFrom(W, Eye, A->GetActorForwardVector(), Point, bIncludeTruck);
}

void AStealthYardFunctionalTest::VisibleSet(const FVector& Point,
	TArray<int32>& Out) const
{
	Out.Reset();
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		double D = 0.0;
		double Ang = 0.0;
		if (ModelCanSee(Watchers[i], Point, /*bIncludeTruck=*/true, D, Ang))
		{
			Out.Add(i);
		}
	}
}

FString AStealthYardFunctionalTest::DescribeSet(const TArray<int32>& Set) const
{
	if (Set.Num() == 0)
	{
		return FString(TEXT("{}"));
	}
	FString S(TEXT("{"));
	for (int32 k = 0; k < Set.Num(); ++k)
	{
		S += FString::Printf(TEXT("%s%s"), k ? TEXT(", ") : TEXT(""),
			*Watchers[Set[k]].Label);
	}
	return S + TEXT("}");
}

FString AStealthYardFunctionalTest::DescribeLitLamps() const
{
	FString S(TEXT("{"));
	bool bAny = false;
	for (const FWatcher& W : Watchers)
	{
		if (AnyLightIntensity(W.Actor.Get()) > kLampLitFloor)
		{
			S += FString::Printf(TEXT("%s%s"), bAny ? TEXT(", ") : TEXT(""), *W.Label);
			bAny = true;
		}
	}
	return S + TEXT("}");
}

bool AStealthYardFunctionalTest::AnyVerdictMarginal(const FVector& Point) const
{
	for (const FWatcher& W : Watchers)
	{
		double D = 0.0;
		double Ang = 0.0;
		ModelCanSee(W, Point, true, D, Ang);
		if (W.Reach <= 0.0f)
		{
			continue;
		}
		// BOTH halves, never either: a watcher whose facing sweeps past its own view
		// width while the runner is four times its reach away is not marginal about
		// anything.
		const bool bNearAngle = FMath::Abs(Ang - double(W.HalfAngleDeg)) <= kMarginAngleDeg
			&& D <= double(W.Reach) * (1.0 + kMarginReachFrac);
		const bool bNearReach = FMath::Abs(D - double(W.Reach))
				<= double(W.Reach) * kMarginReachFrac
			&& Ang <= double(W.HalfAngleDeg) + kMarginAngleDeg;
		if (bNearAngle || bNearReach)
		{
			return true;
		}
		// And an occluder edge close enough to the line that a frame of the truck's
		// motion could flip the answer.
		if (D <= double(W.Reach) * (1.0 + kMarginReachFrac)
			&& Ang <= double(W.HalfAngleDeg) + kMarginAngleDeg)
		{
			const AActor* const A = W.Actor.Get();
			if (A != nullptr)
			{
				const FVector Eye = A->GetActorLocation();
				if (FootprintEdgeMargin(FVector2D(Eye.X, Eye.Y),
						FVector2D(Point.X, Point.Y)) <= kMarginEdgeUu)
				{
					return true;
				}
			}
		}
	}
	return false;
}

// ---------------------------------------------------------------------------
// Simulating the yard forward. This is what makes the drive safe: the fixture never
// starts a walk it cannot prove nobody will be looking at WHILE IT IS BEING WALKED.
// The horizon is always the transit, never a fixed stretch of seconds: half the places
// this drive stands are places a cone will sweep, which is what they are for.
// ---------------------------------------------------------------------------

void AStealthYardFunctionalTest::PredictWatcher(const FWatcher& W, double AheadS,
	FVector& OutAt, FVector& OutFacing) const
{
	const AActor* const A = W.Actor.Get();
	OutAt = A ? A->GetActorLocation() : FVector::ZeroVector;
	OutFacing = A ? A->GetActorForwardVector() : FVector::ForwardVector;
	const FVector2D P0(W.RoundA.X, W.RoundA.Y);
	const FVector2D P1(W.RoundB.X, W.RoundB.Y);
	const FVector2D Along = P1 - P0;
	const double Length = Along.Size();
	if (Length <= KINDA_SMALL_NUMBER || A == nullptr)
	{
		return;
	}
	const FVector2D Unit = Along / Length;
	const FVector2D Here(OutAt.X, OutAt.Y);
	double S = FVector2D::DotProduct(Here - P0, Unit);
	// Which way it is walking: its own facing, projected onto its own round.
	double Dir = FVector2D::DotProduct(FVector2D(OutFacing.X, OutFacing.Y), Unit) >= 0.0
		? 1.0 : -1.0;
	double Remaining = FMath::Max(0.0, double(W.BasePace)) * AheadS;
	// A triangle wave: it turns at each post and keeps walking in the same frame.
	while (Remaining > 0.0)
	{
		const double ToEnd = (Dir > 0.0) ? (Length - S) : S;
		if (Remaining <= ToEnd)
		{
			S += Dir * Remaining;
			Remaining = 0.0;
		}
		else
		{
			Remaining -= FMath::Max(ToEnd, 0.0);
			S = (Dir > 0.0) ? Length : 0.0;
			Dir = -Dir;
		}
	}
	const FVector2D At = P0 + Unit * FMath::Clamp(S, 0.0, Length);
	OutAt = FVector(At.X, At.Y, OutAt.Z);
	OutFacing = FVector(Unit.X * Dir, Unit.Y * Dir, 0.0);
}

FVector2D AStealthYardFunctionalTest::PredictTruck(double AheadS) const
{
	const AActor* const T = Truck.Get();
	if (T == nullptr)
	{
		return FVector2D(TruckHome.X, TruckHome.Y);
	}
	const FVector At = T->GetActorLocation();
	if (!bRailEndsKnown || TruckSpeed <= 1.0f)
	{
		return FVector2D(At.X, At.Y);
	}
	const FVector2D A(RailEndA.X, RailEndA.Y);
	const FVector2D B(RailEndB.X, RailEndB.Y);
	const FVector2D Along = B - A;
	const double Length = Along.Size();
	if (Length <= KINDA_SMALL_NUMBER)
	{
		return FVector2D(At.X, At.Y);
	}
	const FVector2D Unit = Along / Length;
	double Distance = FMath::Clamp(
		FVector2D::DotProduct(FVector2D(At.X, At.Y) - A, Unit), 0.0, Length);
	double Direction = (TruckHeading >= 0.0) ? 1.0 : -1.0;
	// The same triangle wave the truck itself walks: run to the end, turn, keep going
	// in the same step.
	double Remaining = FMath::Max(0.0, double(TruckSpeed)) * FMath::Max(AheadS, 0.0);
	while (Remaining > 0.0)
	{
		const double ToEnd = (Direction > 0.0) ? (Length - Distance) : Distance;
		if (Remaining <= ToEnd)
		{
			Distance += Direction * Remaining;
			Remaining = 0.0;
		}
		else
		{
			Remaining -= FMath::Max(ToEnd, 0.0);
			Distance = (Direction > 0.0) ? Length : 0.0;
			Direction = -Direction;
		}
	}
	const FVector2D Out = A + Unit * FMath::Clamp(Distance, 0.0, Length);
	return Out;
}

double AStealthYardFunctionalTest::EarliestSightingOnPath(const TArray<FVector>& Path,
	double HorizonS) const
{
	if (!Hero.IsValid())
	{
		return 0.0;
	}
	const double Step = 0.2;
	const double Speed = FMath::Max(MeasuredHeroSpeed, 100.0);
	const FVector Start = Hero->GetActorLocation();
	for (double T = 0.0; T <= HorizonS; T += Step)
	{
		// Where the runner would be at T, walking the ladder at its measured pace.
		double Travel = Speed * T;
		FVector At = Start;
		for (const FVector& Next : Path)
		{
			const double Leg = FVector::Dist2D(At, Next);
			if (Travel <= Leg || Leg <= KINDA_SMALL_NUMBER)
			{
				const FVector Dir = (Next - At).GetSafeNormal2D();
				At = At + Dir * Travel;
				Travel = 0.0;
				break;
			}
			Travel -= Leg;
			At = Next;
		}
		At.Z = WalkZ;
		for (const FWatcher& W : Watchers)
		{
			FVector Eye;
			FVector Facing;
			PredictWatcher(W, T, Eye, Facing);
			// The TRUCK IS LEFT OUT: a moving occluder can only ever help, so a
			// prediction that ignores it is the safe direction.
			if (ModelCanSeeFrom(W, Eye, Facing, At, /*bIncludeTruck=*/false))
			{
				return T;
			}
		}
	}
	return HorizonS;
}

double AStealthYardFunctionalTest::EarliestSightingStanding(double HorizonS) const
{
	TArray<FVector> Nowhere;
	if (Hero.IsValid())
	{
		Nowhere.Add(Hero->GetActorLocation());
	}
	return EarliestSightingOnPath(Nowhere, HorizonS);
}

// ---------------------------------------------------------------------------
// Resolution and staging.
// ---------------------------------------------------------------------------

int32 AStealthYardFunctionalTest::WatcherOnRound(FName Tag) const
{
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		if (Watchers[i].RoundTag == Tag)
		{
			return i;
		}
	}
	return INDEX_NONE;
}

bool AStealthYardFunctionalTest::ResolveRounds()
{
	UWorld* const World = GetWorld();
	Rounds.Reset();
	TSet<FName> RoundTags;
	for (const FWatcher& W : Watchers)
	{
		RoundTags.Add(W.RoundTag);
	}
	// Every round the yard marks, not merely the ones somebody is walking today: the
	// sergeant moves a watcher onto a round nobody is on yet.
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		for (const FName& Tag : It->Tags)
		{
			if (Tag.ToString().StartsWith(TEXT("Round")))
			{
				RoundTags.Add(Tag);
			}
		}
	}
	for (const FName& Tag : RoundTags)
	{
		if (Tag.IsNone())
		{
			continue;
		}
		TArray<AActor*> Posts;
		UGameplayStatics::GetAllActorsWithTag(World, Tag, Posts);
		if (Posts.Num() != 2)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the round '%s' is marked by %d post(s), "
					 "expected exactly two"), *Tag.ToString(), Posts.Num()));
			return false;
		}
		FRound R;
		R.Tag = Tag;
		FVector P0 = Posts[0]->GetActorLocation();
		FVector P1 = Posts[1]->GetActorLocation();
		// ORDER BY GEOMETRY, never by name: which post the engine happens to name
		// first is not something a level author can see, and the whole drive is solved
		// in terms of "the -X end".
		if (P1.X < P0.X)
		{
			Swap(P0, P1);
		}
		R.A = P0;
		R.B = P1;
		Rounds.Add(R);
	}
	if (Rounds.Num() != 3)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard marks %d round(s), expected three"),
			Rounds.Num()));
		return false;
	}
	Rounds.Sort([](const FRound& L, const FRound& R) { return L.A.Y < R.A.Y; });
	return true;
}

void AStealthYardFunctionalTest::ReReadNumbers()
{
	// EVERY NUMBER, EVERY FRAME. Four of them change part way through the night, and a
	// fixture that cached them would be grading the first watch's yard.
	for (FWatcher& W : Watchers)
	{
		AActor* const A = W.Actor.Get();
		bool bOk = false;
		W.Reach = ReadFloat(A, TEXT("SightReachUu"), bOk);
		W.HalfAngleDeg = ReadFloat(A, TEXT("SightHalfAngleDeg"), bOk);
		W.BasePace = ReadFloat(A, TEXT("BasePaceUuPerSec"), bOk);
		W.Pace = ReadFloat(A, TEXT("PaceUuPerSec"), bOk);
		W.RoundTag = ReadName(A, TEXT("RoundTag"), bOk);
		for (const FRound& R : Rounds)
		{
			if (R.Tag == W.StagedRoundTag)
			{
				W.RoundA = R.A;
				W.RoundB = R.B;
			}
		}
	}
	bool bOk = false;
	if (const AActor* const P = Plate.Get())
	{
		PlateIndex = ReadInt(P, TEXT("RoundIndex"), bOk);
	}
	if (const AActor* const T = Truck.Get())
	{
		TruckHalf = ReadVector(T, TEXT("TruckHalfExtentUu"), bOk);
		TruckRailHalf = ReadVector(T, TEXT("RailHalfSpanUu"), bOk);
		TruckSpeed = ReadFloat(T, TEXT("RailSpeedUuPerSec"), bOk);
	}
}

bool AStealthYardFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;

	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("StealthWatcher")), Found);
	if (Found.Num() != 3)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - expected "
				 "three watchers tagged StealthWatcher, found %d"), Found.Num()));
		return false;
	}
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	int32 Index = 0;
	for (AActor* A : Found)
	{
		FWatcher W;
		W.Actor = A;
		W.Label = FString::Printf(TEXT("watcher %d"), ++Index);
		bool bOk = false;
		W.RoundTag = ReadName(A, TEXT("RoundTag"), bOk);
		if (!bOk)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose RoundTag readably"),
				*W.Label));
			return false;
		}
		W.StagedRoundTag = W.RoundTag;
		Watchers.Add(W);
	}

	auto One = [&](const TCHAR* Tag, TWeakObjectPtr<AActor>& Out) -> bool
	{
		Found.Reset();
		UGameplayStatics::GetAllActorsWithTag(World, FName(Tag), Found);
		if (Found.Num() != 1)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the yard is not staged as authored - "
					 "expected one actor tagged %s, found %d"), Tag, Found.Num()));
			return false;
		}
		Out = Found[0];
		return true;
	};
	if (!One(TEXT("StealthMast"), Mast) || !One(TEXT("StealthStartPlate"), Plate)
		|| !One(TEXT("StealthGate"), Gate) || !One(TEXT("StealthTruck"), Truck))
	{
		return false;
	}

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("StealthBlocker")), Found);
	if (Found.Num() < 2)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the yard has %d solid block(s) tagged "
				 "StealthBlocker; it needs at least a wall and one crate"), Found.Num()));
		return false;
	}
	Found.Sort([](const AActor& L, const AActor& R) { return L.GetName() < R.GetName(); });
	for (AActor* A : Found)
	{
		bool bOk = false;
		const FVector Half = ReadVector(A, TEXT("BlockHalfExtentUu"), bOk);
		if (!bOk)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a solid block does not expose "
					 "BlockHalfExtentUu readably, so the fixture cannot tell what is "
					 "in the way"));
			return false;
		}
		Blockers.Add(A);
		StagedBlockerAt.Add(A->GetActorLocation());
		StagedBlockerHalf.Add(Half);
	}

	// The three mast lights, read from the LIGHTS themselves.
	for (const TCHAR* Name : { TEXT("RunningLight"), TEXT("AwayLight"),
							   TEXT("CaughtLight") })
	{
		if (LightIntensity(Mast.Get(), Name) < 0.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the mast carries no light named %s, so "
					 "the fixture cannot read the board"), Name));
			return false;
		}
	}
	for (const FWatcher& W : Watchers)
	{
		if (AnyLightIntensity(W.Actor.Get()) < 0.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s carries no head lamp, so the fixture "
					 "cannot tell what it is showing"), *W.Label));
			return false;
		}
	}

	if (!ResolveRounds())
	{
		return false;
	}

	StagedMastAt = Mast->GetActorLocation();
	StagedPlateAt = Plate->GetActorLocation();
	StagedGateAt = Gate->GetActorLocation();
	// WHERE THE TRUCK IS NOW, not where it was placed: the truck's own middle-of-rail
	// is private, and PrepareTest runs a fraction of a second after BeginPlay, so this
	// is the placed point plus however far it has already driven. That matters in two
	// places and neither is a verdict: the rail check below carries 150 uu of slack for
	// it, and the shadow solver's cover ESTIMATE may be a little off -- the cover the
	// gate actually grades is measured live, frame by frame, and the run-level check
	// reports the measured number if no window ever came out.
	TruckHome = Truck->GetActorLocation();
	// ... and then, properly: the rail's own two ends, read off the truck by name. The
	// middle of the rail is the midpoint of those, not wherever the truck happened to
	// have driven to by the time PrepareTest ran.
	{
		bool bA = false;
		bool bB = false;
		const FVector EndA = CallVectorFunc(Truck.Get(), TEXT("GetRailEndA"), bA);
		const FVector EndB = CallVectorFunc(Truck.Get(), TEXT("GetRailEndB"), bB);
		if (bA && bB && !EndA.Equals(EndB, 1.0))
		{
			RailEndA = EndA;
			RailEndB = EndB;
			bRailEndsKnown = true;
			TruckHome = (EndA + EndB) * 0.5;
		}
		else
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the truck does not report the two ends of "
					 "its own rail readably, so the fixture cannot tell where it will "
					 "be in two seconds -- and the one window this task is built "
					 "around is staged by predicting exactly that"));
			return false;
		}
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no visibly represented player character in "
				 "the yard"));
		return false;
	}
	WalkZ = Hero->GetActorLocation().Z;
	if (const UCharacterMovementComponent* const Move = Hero->GetCharacterMovement())
	{
		// MEASURED, not assumed: every phase deadline is derived from this.
		MeasuredHeroSpeed = FMath::Max(double(Move->GetMaxSpeed()), 100.0);
	}
	LaneY = StagedPlateAt.Y;

	ReReadNumbers();
	StageWatch(0);
	return true;
}

void AStealthYardFunctionalTest::StageWatch(int32 WatchIndex)
{
	Watch = WatchIndex;
	if (WatchIndex == 1)
	{
		// THE SERGEANT CHANGES THE WATCH -- while the yard is stood down, so no swap
		// can jolt an outcome, and with every gate suppressed either side of it.
		const int32 OnLane = WatcherOnRound(LaneRoundTag);
		const int32 OnFar = WatcherOnRound(FarRoundTag);
		if (OnLane != INDEX_NONE && OnFar != INDEX_NONE)
		{
			AActor* const A = Watchers[OnLane].Actor.Get();
			AActor* const B = Watchers[OnFar].Actor.Get();
			// They trade rounds, and three numbers move with them. Nothing announces
			// any of it.
			WriteName(A, TEXT("RoundTag"), FarRoundTag);
			WriteName(B, TEXT("RoundTag"), LaneRoundTag);
			WriteFloat(A, TEXT("SightHalfAngleDeg"),
				Watchers[OnLane].HalfAngleDeg * kRestageAngleMul);
			WriteFloat(A, TEXT("BasePaceUuPerSec"),
				Watchers[OnLane].BasePace * kRestagePaceMul);
			WriteFloat(B, TEXT("SightReachUu"), Watchers[OnFar].Reach * kRestageReachMul);
			// And each is set down on the round it now walks, so nobody is asked to
			// cross the yard to get there.
			for (const FRound& R : Rounds)
			{
				if (R.Tag == FarRoundTag && A != nullptr)
				{
					A->SetActorLocation(FVector(R.A.X, R.A.Y,
						A->GetActorLocation().Z), false);
				}
				if (R.Tag == LaneRoundTag && B != nullptr)
				{
					B->SetActorLocation(FVector(R.A.X, R.A.Y,
						B->GetActorLocation().Z), false);
				}
			}
		}
	}
	ReReadNumbers();
	for (FWatcher& W : Watchers)
	{
		W.StagedReach = W.Reach;
		W.StagedHalfAngleDeg = W.HalfAngleDeg;
		W.StagedBasePace = W.BasePace;
		W.StagedRoundTag = W.RoundTag;
		for (const FRound& R : Rounds)
		{
			if (R.Tag == W.RoundTag)
			{
				W.RoundA = R.A;
				W.RoundB = R.B;
			}
		}
	}
	RebuildFootprints();
	SolveSafeLaneBands();
}

// ---------------------------------------------------------------------------
// The staging contract. Every one of these is a HARNESS-PRECONDITION and never a
// graded FAIL, because each one, if broken, would make a CORRECT submission fail.
// ---------------------------------------------------------------------------

bool AStealthYardFunctionalTest::ValidateHeightsCannotMatter()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return false;
	}
	// 5 cm is the one that matters: it is what makes the prompt's promise true for a
	// submission that reads "the line between those two spots on the floor" literally.
	// The one height the promise does not cover is EXACTLY floor level, which is
	// coplanar with the floor plane and numerically ambiguous in any engine; the yard
	// keeps nothing else solid down there so that is the only residual case.
	const double Heights[4] = { 5.0, 20.0, 90.0, 170.0 };
	FCollisionQueryParams Params(FName(TEXT("StealthYardHeightProbe")), false);
	Params.AddIgnoredActor(Hero.Get());
	for (const FWatcher& W : Watchers)
	{
		Params.AddIgnoredActor(W.Actor.Get());
	}
	// The floor's own height, read off a thing the yard placed ON it rather than
	// derived from the character's capsule -- a capsule half-height is a template
	// detail and would silently move every probe if it ever changed.
	const double FloorZ = StagedPlateAt.Z;
	for (const FWatcher& W : Watchers)
	{
		const AActor* const A = W.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		for (int32 PhaseIdx = 0; PhaseIdx < 9; ++PhaseIdx)
		{
			const double T = double(PhaseIdx) / 8.0;
			const FVector Eye = FMath::Lerp(W.RoundA, W.RoundB, T);
			for (int32 k = 0; k < 12; ++k)
			{
				const double S = double(k) / 11.0;
				const FVector Target = FMath::Lerp(StagedPlateAt, StagedGateAt, S);
				bool bFirst = false;
				for (int32 h = 0; h < 4; ++h)
				{
					const FVector From(Eye.X, Eye.Y, FloorZ + Heights[h]);
					const FVector To(Target.X, Target.Y, FloorZ + Heights[h]);
					const bool bBlocked = World->LineTraceTestByChannel(
						From, To, ECC_Visibility, Params);
					if (h == 0)
					{
						bFirst = bBlocked;
					}
					else if (bBlocked != bFirst)
					{
						FinishTest(EFunctionalTestResult::Error, FString::Printf(
							TEXT("HARNESS-PRECONDITION: height changes the answer. "
								 "The line from (%.0f,%.0f) to (%.0f,%.0f) is %s at "
								 "%.0f cm and %s at %.0f cm, so a correct submission "
								 "could be split from the fixture's model by nothing "
								 "but the height it takes the line at"),
							Eye.X, Eye.Y, Target.X, Target.Y,
							bFirst ? TEXT("blocked") : TEXT("clear"), Heights[0],
							bBlocked ? TEXT("blocked") : TEXT("clear"), Heights[h]));
						return false;
					}
				}
			}
		}
	}
	return true;
}

bool AStealthYardFunctionalTest::ValidateNothingElseIsSolid()
{
	UWorld* const World = GetWorld();
	TSet<const AActor*> Allowed;
	for (const FWatcher& W : Watchers)
	{
		Allowed.Add(W.Actor.Get());
	}
	for (const TWeakObjectPtr<AActor>& B : Blockers)
	{
		Allowed.Add(B.Get());
	}
	Allowed.Add(Truck.Get());
	Allowed.Add(Hero.Get());
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* const A = *It;
		if (Allowed.Contains(A))
		{
			continue;
		}
		TArray<UPrimitiveComponent*> Prims;
		A->GetComponents<UPrimitiveComponent>(Prims);
		for (const UPrimitiveComponent* C : Prims)
		{
			if (C == nullptr)
			{
				continue;
			}
			if (C->GetCollisionResponseToChannel(ECC_Visibility) != ECR_Block)
			{
				continue;
			}
			if (C->GetCollisionEnabled() == ECollisionEnabled::NoCollision
				|| C->GetCollisionEnabled() == ECollisionEnabled::PhysicsOnly)
			{
				continue;
			}
			// The floor is allowed to be solid; it is under everything and never
			// between two places on it.
			const FBoxSphereBounds Bounds = C->Bounds;
			if (Bounds.BoxExtent.Z <= 60.0 && Bounds.BoxExtent.X > 2000.0)
			{
				continue;
			}
			// And so is anything too small to be an occluder. A PlayerStart ships a
			// 40 cm capsule on the engine's Pawn profile, which blocks Visibility and
			// is nobody's cover; failing a level over it would be a fixture defect
			// rather than a staging one.
			if (Bounds.BoxExtent.X < 60.0 || Bounds.BoxExtent.Y < 60.0
				|| A->GetClass()->GetName().Contains(TEXT("PlayerStart")))
			{
				continue;
			}
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s (%s) still stops a line, and the yard "
					 "promises that only the crates, the wall and the truck do. A prop "
					 "that quietly blocks a sightline makes a submission that asks "
					 "'is anything in the way?' disagree with a model that never sees "
					 "it"), *A->GetName(), *C->GetName()));
			return false;
		}
	}
	return true;
}

FString AStealthYardFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	TArray<FString> Problems;
	// Half one: the pawn's own input actions, read BY PROPERTY NAME so a renamed or
	// subclassed pawn still answers.
	if (Hero.IsValid())
	{
		TArray<FString> Unbound;
		for (const TCHAR* Name : { TEXT("MoveAction"), TEXT("LookAction"),
								   TEXT("MouseLookAction"), TEXT("JumpAction") })
		{
			const FObjectProperty* const Prop =
				FindFProperty<FObjectProperty>(Hero->GetClass(), Name);
			if (Prop == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(Hero.Get()) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Problems.Add(FString::Printf(
				TEXT("the character (%s) has nothing bound to %s"),
				*Hero->GetClass()->GetName(), *FString::Join(Unbound, TEXT(", "))));
		}
	}
	// Half two: a mapping context has to be applied, or no key reaches any of them.
	const AGameModeBase* const GameMode =
		(World != nullptr) ? World->GetAuthGameMode() : nullptr;
	const UClass* const PCClass =
		(GameMode != nullptr) ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the player "
						  "gets a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts =
				 FindFProperty<FArrayProperty>(PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
		FScriptArrayHelper Helper(Contexts,
			Contexts->ContainerPtrToValuePtr<void>(PCClass->GetDefaultObject()));
		int32 Applied = 0;
		for (int32 i = 0; Element != nullptr && i < Helper.Num(); ++i)
		{
			if (Element->GetObjectPropertyValue(Helper.GetElementPtr(i)) != nullptr)
			{
				++Applied;
			}
		}
		if (Applied == 0)
		{
			Problems.Add(FString::Printf(TEXT("%s applies no input mapping context"),
				*PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s exposes no DefaultMappingContexts, so this check cannot tell "
				 "whether a key reaches the character"), *PCClass->GetName()));
	}
	return FString::Join(Problems, TEXT("; "));
}

bool AStealthYardFunctionalTest::ValidateStagingContract()
{
	// (8) THE PLATE IS NOT STOOD ON AT SPAWN, or round 1 begins before the fixture has
	//     taken its baseline.
	if (PlateIndex != 0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the plate already reads %d at the start, so a "
				 "round began before the fixture took its baseline; PlayerStart is "
				 "supposed to be BESIDE the plate, never on it"), PlateIndex));
		return false;
	}

	// The three rounds, sorted south to north: the lane round, the far round and the
	// walled one. Derived from the geometry, never written down.
	LaneRoundTag = Rounds[0].Tag;
	FarRoundTag = Rounds[1].Tag;
	WalledRoundTag = Rounds[2].Tag;
	SentryIndex = WatcherOnRound(WalledRoundTag);
	if (SentryIndex == INDEX_NONE || WatcherOnRound(LaneRoundTag) == INDEX_NONE
		|| WatcherOnRound(FarRoundTag) == INDEX_NONE)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the three watchers do not walk three different "
				 "rounds, so there is no watch to change"));
		return false;
	}

	for (const FWatcher& W : Watchers)
	{
		if (W.Reach <= 100.0f || W.HalfAngleDeg <= 1.0f || W.HalfAngleDeg >= 89.0f
			|| W.BasePace <= 10.0f)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s's own numbers are unusable (reach %.0f, "
					 "view width %.1f deg, base pace %.0f)"),
				*W.Label, W.Reach, W.HalfAngleDeg, W.BasePace));
			return false;
		}
	}

	// (3) THE WALLED SENTRY IS THE WIDEST-EYED THING IN THE YARD, at EVERY staging --
	//     after the watch change's multipliers, not before, or the control's own claim
	//     could be falsified by the re-stage.
	const FWatcher& S = Watchers[SentryIndex];
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		if (i == SentryIndex)
		{
			continue;
		}
		const double MostReach = double(Watchers[i].Reach) * kRestageReachMul;
		const double MostAngle = double(Watchers[i].HalfAngleDeg);
		if (double(S.Reach) < MostReach * kOtherWatcherMargin
			|| double(S.HalfAngleDeg) <= MostAngle)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the walled sentry (%s: reach %.0f, view "
					 "width %.1f deg) does not dominate %s (at most reach %.0f, view "
					 "width %.1f after the watch change); the in-scene control only "
					 "measures something if a range-only or occlusion-blind sight test "
					 "lights it"),
				*S.Label, S.Reach, S.HalfAngleDeg, *Watchers[i].Label,
				MostReach, MostAngle));
			return false;
		}
	}

	// ... and its round has to be BEHIND the wall from every point of the route, or it
	// is not a control at all. Checked as the model sees it: over every phase of its
	// own round, facing either way, against a dozen points of the lane.
	int32 CouldSeeWithoutWall = 0;
	for (int32 PhaseIdx = 0; PhaseIdx <= 16; ++PhaseIdx)
	{
		const FVector Eye = FMath::Lerp(S.RoundA, S.RoundB, double(PhaseIdx) / 16.0);
		for (int32 k = 0; k <= 24; ++k)
		{
			FVector Target = FMath::Lerp(StagedPlateAt, StagedGateAt, double(k) / 24.0);
			Target.Z = WalkZ;
			for (int32 Side = 0; Side < 2; ++Side)
			{
				const FVector Facing(Side ? 1.0 : -1.0, 0.0, 0.0);
				if (ModelCanSeeFrom(S, Eye, Facing, Target, true))
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walled sentry can see the "
							 "route at (%.0f,%.0f) from (%.0f,%.0f); it is the "
							 "in-scene negative control and its lamp is required dark "
							 "at every checkpoint, so a yard where it CAN see somebody "
							 "would fail a correct submission"),
						Target.X, Target.Y, Eye.X, Eye.Y));
					return false;
				}
				// And it has to be the WALL doing it, not the reach: a control that is
				// merely out of range is passed by a range-only sight test, which is
				// one of the two wrong answers it exists to catch.
				const FVector2D E(Eye.X, Eye.Y);
				const FVector2D T(Target.X, Target.Y);
				const double D = FVector2D::Distance(E, T);
				const FVector2D Fwd(Facing.X, Facing.Y);
				const double Ang = (D > KINDA_SMALL_NUMBER)
					? FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
						FVector2D::DotProduct(Fwd, (T - E) / D), -1.0, 1.0)))
					: 0.0;
				if (D <= double(S.Reach) && Ang <= double(S.HalfAngleDeg))
				{
					++CouldSeeWithoutWall;
				}
			}
		}
	}
	if (CouldSeeWithoutWall < 40)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the walled sentry would hold the route in only "
				 "%d of the sampled (phase, place) pairs even with nothing in the way, "
				 "so a range-only or occlusion-blind sight test would barely light it "
				 "and the in-scene control measures almost nothing"), CouldSeeWithoutWall));
		return false;
	}

	// (9) THE START LINE AND THE GATE ARE OUT OF EVERY LIVE CONE, at every phase and
	//     BOTH stagings. Not decoration: a watcher that can see the start line ends
	//     every round on the frame it begins -- which would make the crossing gate
	//     unreachable while looking exactly like a submission that latches too eagerly
	//     -- and one that can see the gate makes both away endings impossible.
	const FVector Ends[2] = { StagedPlateAt, StagedGateAt };
	const TCHAR* EndNames[2] = { TEXT("the start plate"), TEXT("the gate") };
	for (int32 e = 0; e < 2; ++e)
	{
		FVector P(Ends[e].X, Ends[e].Y, WalkZ);
		for (int32 i = 0; i < Watchers.Num(); ++i)
		{
			// Both stagings: this watcher's own reach, and the largest it will ever
			// have after the watch change.
			const double Widest = double(Watchers[i].Reach) * kRestageReachMul;
			double Nearest = 1.0e30;
			for (int32 r = 0; r < Rounds.Num(); ++r)
			{
				Nearest = FMath::Min(Nearest, Dist2DToSegment(FVector2D(P.X, P.Y),
					FVector2D(Rounds[r].A.X, Rounds[r].A.Y),
					FVector2D(Rounds[r].B.X, Rounds[r].B.Y)));
			}
			if (i == SentryIndex)
			{
				continue;   // the wall answers for the sentry, checked above
			}
			if (Nearest < Widest * kOtherWatcherMargin)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: %s is %.0f uu from the nearest round "
						 "against a reach of up to %.0f (%.2fx, and %.2fx is the "
						 "floor). A watcher that can see the start line ends every "
						 "round on the frame it begins; one that can see the gate "
						 "makes both away endings impossible"),
					EndNames[e], Nearest, Widest, Nearest / FMath::Max(Widest, 1.0),
					kOtherWatcherMargin));
				return false;
			}
		}
	}
	return true;
}

// ---------------------------------------------------------------------------
// The geometry. Every place the drive stands is SOLVED from the live level and the
// watchers' own numbers, never written down, so a re-authored yard moves the drive
// with it and no stop can drift onto a boundary where a correct answer could round the
// wrong way.
// ---------------------------------------------------------------------------

void AStealthYardFunctionalTest::SolveSafeLaneBands()
{
	SafeBands.Reset();
	const double X0 = FMath::Min(StagedPlateAt.X, StagedGateAt.X);
	const double X1 = FMath::Max(StagedPlateAt.X, StagedGateAt.X);
	bool bOpen = false;
	double Start = X0;
	for (double X = X0; X <= X1 + 1.0; X += 100.0)
	{
		const FVector P(X, LaneY, WalkZ);
		bool bEverSeen = false;
		for (const FWatcher& W : Watchers)
		{
			for (int32 PhaseIdx = 0; PhaseIdx <= 24 && !bEverSeen; ++PhaseIdx)
			{
				const FVector Eye = FMath::Lerp(W.RoundA, W.RoundB, double(PhaseIdx) / 24.0);
				for (int32 Side = 0; Side < 2; ++Side)
				{
					const FVector2D Along =
						FVector2D(W.RoundB.X - W.RoundA.X, W.RoundB.Y - W.RoundA.Y)
							.GetSafeNormal();
					const FVector Facing(Along.X * (Side ? 1.0 : -1.0),
										 Along.Y * (Side ? 1.0 : -1.0), 0.0);
					// The truck is left out: it moves, so it cannot make a place SAFE.
					if (ModelCanSeeFrom(W, Eye, Facing, P, /*bIncludeTruck=*/false))
					{
						bEverSeen = true;
						break;
					}
				}
			}
			if (bEverSeen)
			{
				break;
			}
		}
		if (!bEverSeen && !bOpen)
		{
			bOpen = true;
			Start = X;
		}
		else if (bEverSeen && bOpen)
		{
			bOpen = false;
			if (X - 100.0 - Start > 400.0)
			{
				SafeBands.Add(FVector2D(Start, X - 100.0));
			}
		}
	}
	if (bOpen && X1 - Start > 400.0)
	{
		SafeBands.Add(FVector2D(Start, X1));
	}
}

double AStealthYardFunctionalTest::NearestSafeLaneX(double X) const
{
	double Best = X;
	double BestD = 1.0e30;
	for (const FVector2D& Band : SafeBands)
	{
		const double Clamped = FMath::Clamp(X, Band.X, Band.Y);
		const double D = FMath::Abs(Clamped - X);
		if (D < BestD)
		{
			BestD = D;
			Best = Clamped;
		}
	}
	return Best;
}

bool AStealthYardFunctionalTest::SolveSpots()
{
	const int32 LaneWatcher = WatcherOnRound(LaneRoundTag);
	if (LaneWatcher == INDEX_NONE)
	{
		return false;
	}
	const FWatcher& L = Watchers[LaneWatcher];
	const double RoundY = L.RoundA.Y;
	const double A = L.RoundA.X;
	const double B = L.RoundB.X;

	// --- the SHADOW spot ---------------------------------------------------
	// Solved from the closed form the whole layout follows from: a watcher walking a
	// straight round, facing along it, holds a stationary target at perpendicular
	// offset p and along-track lead b inside its cone while b >= p/tan(theta), and
	// inside its reach while b <= sqrt(R*R - p*p). Both ends are MID-LEG exactly when
	// both bounds lie strictly inside the round -- which is what keeps a waypoint
	// poller from ever sampling inside the window.
	double BestScore = -1.0;
	for (double P = 300.0; P <= 1600.0; P += 25.0)
	{
		const double Theta = FMath::DegreesToRadians(
			FMath::Clamp(double(L.HalfAngleDeg), 1.0, 89.0));
		const double Cone = P / FMath::Tan(Theta);
		const double ReachBound = FMath::Sqrt(FMath::Max(
			double(L.Reach) * double(L.Reach) - P * P, 0.0));
		if (ReachBound <= Cone)
		{
			continue;   // no window at this offset, whatever the along-track position
		}
		const double Width = ReachBound - Cone;
		const double Duration = Width / FMath::Max(double(L.BasePace), 1.0);
		if (Duration < kMinShadowWindowS)
		{
			continue;
		}
		const double Slack = (B - A) - Width;
		if (Slack <= 0.0)
		{
			continue;
		}
		const double Clear = (Slack * 0.5) / FMath::Max(double(L.BasePace), 1.0);
		if (Clear < kMinTurnClearanceS)
		{
			continue;
		}
		// Centred: the target sits west of the round, seen on the westward pass.
		const double Xs = B - Slack * 0.5 - ReachBound;
		const FVector Candidate(Xs, RoundY - P, WalkZ);
		// The east pass must give NOTHING, or the window is two windows a lap and the
		// grazing shape this yard exists to avoid comes back.
		if (Xs - A >= Cone)
		{
			continue;
		}
		// Clear of every round, every solid thing and the truck's whole swept rail.
		bool bClear = true;
		for (const FRound& R : Rounds)
		{
			if (Dist2DToSegment(FVector2D(Xs, RoundY - P),
					FVector2D(R.A.X, R.A.Y), FVector2D(R.B.X, R.B.Y))
				< kRouteFromRoundUu)
			{
				bClear = false;
			}
		}
		for (int32 i = 0; i < Blockers.Num(); ++i)
		{
			if (Dist2DToRect(FVector2D(Xs, RoundY - P),
					FVector2D(StagedBlockerAt[i].X, StagedBlockerAt[i].Y),
					FVector2D(StagedBlockerHalf[i].X, StagedBlockerHalf[i].Y))
				< kRouteFromSolidUu)
			{
				bClear = false;
			}
		}
		if (Dist2DToRect(FVector2D(Xs, RoundY - P),
				FVector2D(TruckHome.X, TruckHome.Y),
				FVector2D(FMath::Abs(TruckHalf.X) + FMath::Abs(TruckRailHalf.X),
						  FMath::Abs(TruckHalf.Y) + FMath::Abs(TruckRailHalf.Y)))
			< kRouteFromSolidUu)
		{
			bClear = false;
		}
		if (!bClear)
		{
			continue;
		}
		// (7) NOBODY UNPLANNED IS LOOKING: no watcher other than the one this window
		//     names may hold the spot from ANY phase of its own round.
		bool bOthersBlind = true;
		for (int32 i = 0; i < Watchers.Num() && bOthersBlind; ++i)
		{
			if (i == LaneWatcher)
			{
				continue;
			}
			for (int32 PhaseIdx = 0; PhaseIdx <= 24 && bOthersBlind; ++PhaseIdx)
			{
				const FVector Eye =
					FMath::Lerp(Watchers[i].RoundA, Watchers[i].RoundB, double(PhaseIdx) / 24.0);
				for (int32 Side = 0; Side < 2; ++Side)
				{
					const FVector Facing(Side ? 1.0 : -1.0, 0.0, 0.0);
					if (ModelCanSeeFrom(Watchers[i], Eye, Facing, Candidate, false))
					{
						bOthersBlind = false;
						break;
					}
				}
			}
		}
		if (!bOthersBlind)
		{
			continue;
		}
		// (6) THE SHADOW WINDOW IS REAL, and it is MEASURED rather than assumed. The
		//     truck's rail has to lie across the line from the covering watcher to
		//     this spot for a real stretch AND then let go of it: a rail that never
		//     covers gives nothing to grade, and a rail that covers the line from END
		//     TO END never clears, so the board's half of the gate could never fire.
		//     Measured at three phases of the window and taken at its WORST.
		const double RailLength = 2.0 * TruckRailHalf.Size();
		const double RailSeconds = RailLength / FMath::Max(double(TruckSpeed), 1.0);
		double WorstCoverS = 1.0e30;
		bool bAlwaysCovered = false;
		for (int32 k = 0; k <= 2; ++k)
		{
			const double Xw = FMath::Lerp(Xs + Cone, Xs + ReachBound, double(k) / 2.0);
			int32 Run = 0;
			int32 Longest = 0;
			int32 Blocked = 0;
			const int32 Samples = 60;
			for (int32 j = 0; j <= Samples; ++j)
			{
				const double F = double(j) / double(Samples) * 2.0 - 1.0;
				const FVector2D TruckAt(TruckHome.X + TruckRailHalf.X * F,
										TruckHome.Y + TruckRailHalf.Y * F);
				if (SegmentHitsRect(FVector2D(Xw, RoundY), FVector2D(Xs, RoundY - P),
						TruckAt, FVector2D(TruckHalf.X, TruckHalf.Y)))
				{
					++Run;
					++Blocked;
					Longest = FMath::Max(Longest, Run);
				}
				else
				{
					Run = 0;
				}
			}
			if (Blocked > Samples - 2)
			{
				bAlwaysCovered = true;   // it never lets go: nothing to clear
			}
			WorstCoverS = FMath::Min(WorstCoverS,
				double(Longest) / double(Samples) * RailSeconds);
		}
		// 1.5x THE COVER FLOOR, not 1.2x. The gate wants kMinTruckCoverS of cover;
		// the DRIVE wants a little more than that, because the shadow entry only
		// commits the runner when it can prove the truck will still be across the line
		// half a second after the cover floor is reached AND will then let go while
		// the cone still holds. A window sized exactly to the gate's floor is a window
		// the entry can never call ripe, and a drive that never commits reports a
		// staging fault instead of a grade.
		if (bAlwaysCovered || WorstCoverS < kMinTruckCoverS * 1.5)
		{
			continue;
		}
		const double Score = FMath::Min(Duration, 12.0) + FMath::Min(Clear, 8.0)
			+ FMath::Min(WorstCoverS, 4.0);
		if (Score > BestScore)
		{
			BestScore = Score;
			SpotShadow = Candidate;
			MeasuredShadowWindowS = Duration;
		}
	}
	if (BestScore < 0.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: no place in this yard gives the watcher on the "
				 "lane round (%s: reach %.0f, view width %.1f deg, base pace %.0f) a "
				 "continuous %.1f s of sight with %.1f s of clearance to both of its "
				 "turns AND the truck's rail across the line; the shadow gate has "
				 "nothing to measure"),
			*L.Label, L.Reach, L.HalfAngleDeg, L.BasePace, kMinShadowWindowS,
			kMinTurnClearanceS));
		return false;
	}

	// --- the SPLIT spot ----------------------------------------------------
	// The identical standing place walked in BOTH stagings with a DIFFERENT watcher
	// covering the round: out of reach for the one that has it now, and inside a real
	// mid-leg window for the one that takes it at the watch change. Solved against the
	// numbers the sergeant WILL set, which the fixture knows because it sets them.
	const int32 FarWatcher = WatcherOnRound(FarRoundTag);
	if (FarWatcher == INDEX_NONE)
	{
		return false;
	}
	const double FutureReach = double(Watchers[FarWatcher].Reach) * kRestageReachMul;
	const double FutureTheta = FMath::DegreesToRadians(FMath::Clamp(
		double(Watchers[FarWatcher].HalfAngleDeg), 1.0, 89.0));
	const double FuturePace = FMath::Max(double(Watchers[FarWatcher].BasePace), 1.0);
	const double PLane = FMath::Abs(RoundY - LaneY);
	const double ConeB = PLane / FMath::Tan(FutureTheta);
	const double ReachB = FMath::Sqrt(FMath::Max(FutureReach * FutureReach
		- PLane * PLane, 0.0));
	if (ReachB <= ConeB)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: after the watch change the lane round's "
				 "watcher reaches %.0f uu through %.1f deg, so at the lane's %.0f uu "
				 "offset its view width lets go (%.0f uu) further out than its reach "
				 "does (%.0f uu) and there is NO crossing window at all -- the gate "
				 "this task is built around would be unreachable"),
			FutureReach, FMath::RadiansToDegrees(FutureTheta), PLane, ConeB, ReachB));
		return false;
	}
	const double CrossWidth = ReachB - ConeB;
	MeasuredCrossWindowS = CrossWidth / FuturePace;
	const double CrossSlack = (B - A) - CrossWidth;
	MeasuredCrossClearanceS = (CrossSlack * 0.5) / FuturePace;
	if (MeasuredCrossWindowS < kMinCrossWindowS
		|| MeasuredCrossClearanceS < kMinTurnClearanceS)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the staged crossing gives %.2f s of continuous "
				 "sight with %.2f s of clearance to the nearest turn, against floors "
				 "of %.1f s and %.1f s. A window this tight can be straddled by a "
				 "correct submission, which is a manufactured failure, not a "
				 "measurement"),
			MeasuredCrossWindowS, MeasuredCrossClearanceS, kMinCrossWindowS,
			kMinTurnClearanceS));
		return false;
	}
	// East of the round, seen on the eastward pass, both ends strictly mid-leg.
	const double SplitX = A + CrossSlack * 0.5 + ReachB;
	SpotSplit = FVector(SplitX, LaneY, WalkZ);
	// ... and NOBODY may hold it under the staging in force, or the two holds cannot
	// give opposite answers and the gate measures nothing.
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		for (int32 PhaseIdx = 0; PhaseIdx <= 24; ++PhaseIdx)
		{
			const FVector Eye =
				FMath::Lerp(Watchers[i].RoundA, Watchers[i].RoundB, double(PhaseIdx) / 24.0);
			for (int32 Side = 0; Side < 2; ++Side)
			{
				const FVector Facing(Side ? 1.0 : -1.0, 0.0, 0.0);
				if (ModelCanSeeFrom(Watchers[i], Eye, Facing, SpotSplit, false))
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: %s can already hold the split spot "
							 "(%.0f,%.0f) on the FIRST watch, from (%.0f,%.0f). The "
							 "whole point of that place is that it means opposite "
							 "things on the two watches"),
						*Watchers[i].Label, SpotSplit.X, SpotSplit.Y, Eye.X, Eye.Y));
					return false;
				}
			}
		}
	}

	// ... and the truck must be clear of that line ANYWHERE INSIDE THE WINDOW, or the
	// two gates that own the split spot would be measuring the truck instead of the
	// two watchers' eyes. Checked over the window widened by 300 uu of watcher travel
	// at each end, because the window's own ends are where a frame of difference lands.
	{
		const double WinLo = A + CrossSlack * 0.5 - 300.0;
		const double WinHi = B - CrossSlack * 0.5 + 300.0;
		const FVector2D SweptC(TruckHome.X, TruckHome.Y);
		const FVector2D SweptH(FMath::Abs(TruckHalf.X) + FMath::Abs(TruckRailHalf.X),
							   FMath::Abs(TruckHalf.Y) + FMath::Abs(TruckRailHalf.Y));
		for (int32 k = 0; k <= 40; ++k)
		{
			const double Xw = FMath::Lerp(WinLo, WinHi, double(k) / 40.0);
			if (SegmentHitsRect(FVector2D(Xw, RoundY),
					FVector2D(SpotSplit.X, SpotSplit.Y), SweptC, SweptH))
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: the truck's swept rail lies across the "
						 "line from (%.0f,%.0f) to the split spot (%.0f,%.0f), inside "
						 "the crossing window; SeenTheMomentTheyCross and "
						 "EachWatcherSeesWithItsOwnEyes would be measuring the truck "
						 "instead of the two watchers' eyes"),
					Xw, RoundY, SpotSplit.X, SpotSplit.Y));
				return false;
			}
		}
	}

	// --- the OPEN spot: a lane place nobody can ever see, for the final gates ----
	SpotOpen = FVector(NearestSafeLaneX(0.5 * (A + B)), LaneY, WalkZ);

	// --- the WAIT point for the shadow entry -------------------------------
	// The lane rest point nearest the shadow spot that no watcher can ever see. The
	// runner stands here, in the open and safe, until the covering watcher's cone and
	// the truck's rail come into step -- see ShadowEntryRipe. Without a wait point the
	// drive would have to walk straight in and hope, and arriving while the cone holds
	// the spot with the truck elsewhere ends round 1 on the spot: a staging coin toss,
	// not a measurement.
	SpotShadowWait = FVector(NearestSafeLaneX(SpotShadow.X), LaneY, WalkZ);
	UE_LOG(LogTemp, Display,
		TEXT("[t3-stealth] lane round '%s' x[%.0f..%.0f] y%.0f; shadow (%.0f,%.0f) "
			 "window %.2fs; split (%.0f,%.0f) crossing %.2fs clearance %.2fs; open "
			 "(%.0f,%.0f); hero pace %.0f; %d safe lane band(s)"),
		*LaneRoundTag.ToString(), A, B, RoundY, SpotShadow.X, SpotShadow.Y,
		MeasuredShadowWindowS, SpotSplit.X, SpotSplit.Y, MeasuredCrossWindowS,
		MeasuredCrossClearanceS, SpotOpen.X, SpotOpen.Y, MeasuredHeroSpeed,
		SafeBands.Num());
	return true;
}

bool AStealthYardFunctionalTest::ShadowEntryRipe(double& OutArriveS,
	double& OutCoverS, double& OutClearS) const
{
	OutArriveS = OutCoverS = OutClearS = 0.0;
	const int32 Cover = WatcherOnRound(LaneRoundTag);
	if (Cover == INDEX_NONE || !Hero.IsValid() || !bRailEndsKnown)
	{
		return false;
	}
	const FWatcher& W = Watchers[Cover];
	const FVector Here = Hero->GetActorLocation();
	const FVector Target(SpotShadow.X, SpotShadow.Y, WalkZ);
	const double Distance = FVector::Dist2D(Here, Target);
	const double Speed = FMath::Max(MeasuredHeroSpeed, 100.0);
	const double Arrive = Distance / Speed + kRipeArriveSlackS;
	const FVector Direction = (Target - Here).GetSafeNormal2D();

	// (a) NOBODY SEES THE RUNNER ON THE WAY IN. With the truck predicted where it will
	//     actually be, because on this one leg the truck is what the runner is walking
	//     into the shadow of.
	for (double T = 0.0; T <= Arrive; T += kRipeStepS)
	{
		const double Travel = FMath::Min(Speed * T, Distance);
		FVector At = Here + Direction * Travel;
		At.Z = WalkZ;
		const FVector2D TruckAt = PredictTruck(T);
		for (const FWatcher& Any : Watchers)
		{
			FVector Eye;
			FVector Facing;
			PredictWatcher(Any, T, Eye, Facing);
			if (ModelCanSeeWithTruckAt(Any, Eye, Facing, At, TruckAt))
			{
				return false;
			}
		}
	}

	// WHERE THE RUNNER ACTUALLY STOPS, not where it was aimed. DriveHero stops issuing
	// input once the runner is inside kWaypointUu of the waypoint and the character
	// then coasts, so the standing place is a short SEGMENT, not a point. Every check
	// below is made at BOTH ends of it: a window that holds only at the exact spot is a
	// window the drive cannot be relied on to land inside, and landing outside it is
	// how round 1 ends on arrival with nothing measured.
	const FVector Stop = Target - Direction * kWaypointUu;

	// (b) ON ARRIVAL the covering watcher's cone already holds the spot AND the truck
	//     already lies across the line -- continuously, for longer than the cover floor
	//     plus the moment phase 2 needs to notice it, so the phase completes BEFORE the
	//     clearing rather than racing it. Nobody else may hold the spot at all.
	// FROM THE EARLIEST POSSIBLE ARRIVAL, not the latest. `Arrive` is the ideal transit
	// plus the acceleration slop, so the runner may be standing on the spot up to that
	// slop EARLIER than `Arrive` -- and those are frames on which the cone could hold it
	// with the truck elsewhere, which ends the round before the window opens. Checking
	// from `Arrive` alone left them unexamined.
	const double EarliestArrive = Distance / Speed;
	const double CoverUntil = Arrive + kMinTruckCoverS + 0.2;
	for (double T = EarliestArrive; T <= CoverUntil; T += kRipeStepS)
	{
		const FVector2D TruckAt = PredictTruck(T);
		FVector Eye;
		FVector Facing;
		PredictWatcher(W, T, Eye, Facing);
		for (int32 End = 0; End < 2; ++End)
		{
			const FVector& Where = End ? Stop : Target;
			if (!ModelCanSeeFrom(W, Eye, Facing, Where, /*bIncludeTruck=*/false))
			{
				return false;   // the cone is not there yet, or has let go already
			}
			if (!TruckOnLineAt(Eye, Where, TruckAt))
			{
				return false;   // the truck is not covering: the runner is caught
			}
		}
		for (int32 i = 0; i < Watchers.Num(); ++i)
		{
			if (i == Cover)
			{
				continue;
			}
			FVector OtherEye;
			FVector OtherFacing;
			PredictWatcher(Watchers[i], T, OtherEye, OtherFacing);
			if (ModelCanSeeWithTruckAt(Watchers[i], OtherEye, OtherFacing, Target,
					TruckAt)
				|| ModelCanSeeWithTruckAt(Watchers[i], OtherEye, OtherFacing, Stop,
					TruckAt))
			{
				return false;
			}
		}
	}

	// (c) AND THEN THE TRUCK LETS GO while the cone still holds the spot. That single
	//     instant is what phase 3 grades, so a window whose cone lets go first is no
	//     window at all -- it would end the round with nothing measured.
	double ClearAt = -1.0;
	for (double T = CoverUntil; T <= Arrive + kRipeClearSearchS; T += kRipeStepS)
	{
		FVector Eye;
		FVector Facing;
		PredictWatcher(W, T, Eye, Facing);
		const bool bCone = ModelCanSeeFrom(W, Eye, Facing, Target, false)
			&& ModelCanSeeFrom(W, Eye, Facing, Stop, false);
		const bool bTruck = TruckOnLineAt(Eye, Target, PredictTruck(T))
			|| TruckOnLineAt(Eye, Stop, PredictTruck(T));
		if (!bCone)
		{
			break;             // the cone let go before the truck did
		}
		if (!bTruck)
		{
			ClearAt = T;       // this is the frame the round is meant to end on
			break;
		}
	}
	if (ClearAt < 0.0)
	{
		return false;
	}
	OutArriveS = Arrive;
	OutCoverS = ClearAt - Arrive;
	OutClearS = ClearAt;
	return true;
}

bool AStealthYardFunctionalTest::SolveSeenSpot(int32 WatcherIndex, FVector& Out) const
{
	if (!Watchers.IsValidIndex(WatcherIndex))
	{
		return false;
	}
	const FWatcher& W = Watchers[WatcherIndex];
	const AActor* const A = W.Actor.Get();
	if (A == nullptr)
	{
		return false;
	}
	const FVector Eye = A->GetActorLocation();
	const FVector Fwd = A->GetActorForwardVector().GetSafeNormal2D();
	// Squarely inside its live reach and view width, straight ahead of it, far enough
	// out that the runner never walks into the watcher itself -- and reachable by a
	// corridor that clears everything solid.
	for (double S = 0.75; S >= 0.30; S -= 0.05)
	{
		const FVector Candidate(Eye.X + Fwd.X * double(W.Reach) * S,
								Eye.Y + Fwd.Y * double(W.Reach) * S, WalkZ);
		if (ModelCanSeeFrom(W, Eye, Fwd, Candidate, true) == false)
		{
			continue;
		}
		bool bReachable = true;
		for (int32 i = 0; i < Blockers.Num(); ++i)
		{
			const FVector2D C(StagedBlockerAt[i].X, StagedBlockerAt[i].Y);
			const FVector2D H(StagedBlockerHalf[i].X + kRouteFromSolidUu,
							  StagedBlockerHalf[i].Y + kRouteFromSolidUu);
			if (SegmentHitsRect(FVector2D(Candidate.X, LaneY),
					FVector2D(Candidate.X, Candidate.Y), C, H))
			{
				bReachable = false;
			}
		}
		const FVector2D SweptC(TruckHome.X, TruckHome.Y);
		const FVector2D SweptH(
			FMath::Abs(TruckHalf.X) + FMath::Abs(TruckRailHalf.X) + kRouteFromSolidUu,
			FMath::Abs(TruckHalf.Y) + FMath::Abs(TruckRailHalf.Y) + kRouteFromSolidUu);
		if (SegmentHitsRect(FVector2D(Candidate.X, LaneY),
				FVector2D(Candidate.X, Candidate.Y), SweptC, SweptH))
		{
			bReachable = false;
		}
		for (const FWatcher& Other : Watchers)
		{
			const AActor* const OA = Other.Actor.Get();
			if (OA != nullptr && FVector::Dist2D(OA->GetActorLocation(), Candidate)
					< kRouteFromSolidUu)
			{
				bReachable = false;
			}
		}
		if (bReachable)
		{
			Out = Candidate;
			return true;
		}
	}
	return false;
}

// ---------------------------------------------------------------------------
// The drive. Every standing phase is "stay here until MY model says X", never "stay
// here for T seconds", except where a fixed dwell is the thing being asserted.
//
// EVERY WALK IS GOVERNED. A transit is released only once the model has simulated all
// three watchers forward and proved that no point of the intended leg can be seen for
// long enough to finish it with margin. Without that, a transit ends a round by
// accident and the gate that was about to be measured never arms.
// ---------------------------------------------------------------------------

double AStealthYardFunctionalTest::PathLength(const FVector& From,
	const TArray<FVector>& Path) const
{
	double Length = 0.0;
	FVector At = From;
	for (const FVector& P : Path)
	{
		Length += FVector::Dist2D(At, P);
		At = P;
	}
	return Length;
}

void AStealthYardFunctionalTest::PlanWalkTo(const FVector& Target, bool bViaLane)
{
	Waypoints.Reset();
	WaypointIndex = 0;
	bWalkReleased = false;
	NextSafetyCheckAt = -1.0;
	if (!Hero.IsValid())
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	if (bViaLane)
	{
		if (FMath::Abs(Here.Y - LaneY) > 150.0)
		{
			Waypoints.Add(FVector(Here.X, LaneY, WalkZ));
		}
		// Hop between the lane's permanently-safe bands, so no single leg is longer
		// than the model can prove safe.
		const double FromX = Here.X;
		const double ToX = Target.X;
		TArray<double> Rests;
		for (const FVector2D& Band : SafeBands)
		{
			const double Mid = 0.5 * (Band.X + Band.Y);
			if ((Mid - FromX) * (ToX - FromX) > 0.0
				&& FMath::Abs(Mid - FromX) < FMath::Abs(ToX - FromX))
			{
				Rests.Add(Mid);
			}
		}
		Rests.Sort([FromX](const double L, const double R)
		{
			return FMath::Abs(L - FromX) < FMath::Abs(R - FromX);
		});
		for (const double X : Rests)
		{
			Waypoints.Add(FVector(X, LaneY, WalkZ));
		}
		if (FMath::Abs(Target.Y - LaneY) > 150.0)
		{
			Waypoints.Add(FVector(Target.X, LaneY, WalkZ));
		}
	}
	Waypoints.Add(FVector(Target.X, Target.Y, WalkZ));
}

void AStealthYardFunctionalTest::DriveHero(double Now)
{
	if (!Hero.IsValid() || !Waypoints.IsValidIndex(WaypointIndex))
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Waypoints[WaypointIndex];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointUu)
	{
		++WaypointIndex;
		bWalkReleased = false;
		NextSafetyCheckAt = -1.0;
		return;
	}
	// THE GOVERNOR. Released once per leg, then the leg is walked without further
	// question -- re-deciding every frame would let a walk stall half way across a
	// danger band, which is worse than not starting it.
	if (!bWalkReleased)
	{
		// ONCE A ROUND IS OVER THERE IS NOTHING LEFT TO PROTECT. Being seen changes
		// nothing about a round that has already ended, and three of the drive's most
		// important walks -- out of the place the runner was caught standing in, into
		// the gateway twice, and squarely into a frozen watcher's cone -- START or END
		// somewhere a watcher can plainly see. A governor that applied here would
		// refuse every one of them and the drive would stall on the very frame it was
		// supposed to begin proving that the first ending wins for ever.
		if (RoundIsOver())
		{
			bWalkReleased = true;
		}
		else
		{
			if (Now < NextSafetyCheckAt)
			{
				return;
			}
			NextSafetyCheckAt = Now + 0.25;
			TArray<FVector> Leg;
			Leg.Add(Target);
			// THE HORIZON IS THE TRANSIT, and nothing beyond it. What this rule has to
			// prove is "nobody sees the runner BEFORE it gets there"; what it must not
			// demand is "nobody sees the runner for seconds after it arrives", because
			// two of the places this drive stands are places a cone is MEANT to sweep
			// -- the shadow spot and the split spot on the second watch. Demanding
			// safety past arrival makes those two walks unreleasable and the drive
			// never finishes a single phase.
			const double Need = FVector::Dist2D(Here, Target)
				/ FMath::Max(MeasuredHeroSpeed, 100.0);
			const double Horizon = Need * 1.35 + kWalkHorizonSlackS;
			if (EarliestSightingOnPath(Leg, Horizon) >= Horizon - 0.01)
			{
				bWalkReleased = true;
			}
			else
			{
				return;
			}
		}
	}
	Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
}

void AStealthYardFunctionalTest::BeginPhase(int32 NewPhase, double Now)
{
	Phase = NewPhase;
	PhaseStartedAt = Now;
	HoldSince = -1.0;
	Waypoints.Reset();
	WaypointIndex = 0;
	bWalkReleased = false;
	NextSafetyCheckAt = -1.0;
	CrossFirstVisibleAt = -1.0;
	GateEntries = 0;
	bInGateVolume = false;

	// THE TRUCK WINDOW SPANS TWO PHASES and its bookkeeping must NOT be cleared between
	// them. Phase 2 completes the moment the cover reaches its floor; phase 3 waits for
	// the same cover to be let go of. Zeroing the cover at the phase boundary would
	// force phase 3 to wait for a SECOND cover window that the staging never promised,
	// and the clearing -- the sharpest thing this fixture measures -- would never latch.
	if (Phase == 2)
	{
		TruckCoverSince = -1.0;
		TruckCoverBest = 0.0;
		TruckClearedAt = -1.0;
		bShadowEntryCommitted = false;
		ShadowWaitSince = Now;
		LastRipeReportAt = -1.0;
	}

	const FVector PlateAt(StagedPlateAt.X, StagedPlateAt.Y, WalkZ);
	const FVector GateAt(StagedGateAt.X, StagedGateAt.Y, WalkZ);

	switch (Phase)
	{
	case 1:  case 6:  case 11: case 15: PlanWalkTo(PlateAt, true); break;
	// Phase 2 walks to the WAIT point, not to the shadow spot. The last few hundred
	// centimetres are committed later, when the yard's own two clocks line up -- see
	// ShadowEntryRipe and the commit block in Tick.
	case 2:  PlanWalkTo(SpotShadowWait, true); break;
	case 4:  case 13: PlanWalkTo(SpotOpen, true); break;
	case 5:  case 14:
	{
		// IN, OUT, AND IN AGAIN. Two separate arrivals in the gateway after the round
		// has already been lost: one entry proves nothing, because a submission that
		// only ever overwrites the outcome on the FIRST touch would pass it. The walk
		// back out is a real leg, far enough that no capsule of any plausible size is
		// still overlapping the volume when the runner stops -- the runner coasts a
		// little past every waypoint, so "just outside" is not outside.
		const double Back = (StagedGateAt.X >= StagedPlateAt.X) ? -900.0 : 900.0;
		const FVector OutAgain(GateAt.X + Back, LaneY, WalkZ);
		PlanWalkTo(GateAt, true);
		Waypoints.Add(OutAgain);
		Waypoints.Add(GateAt);
		break;
	}
	case 7:  case 12: PlanWalkTo(SpotSplit, true); break;
	case 8:  case 16: PlanWalkTo(GateAt, true); break;
	// 9 and 17 are deliberately NOT planned here. The round has only just been won, so
	// the watchers have not finished standing down yet; a place solved from a watcher
	// still walking is not the place it stops at. The plan is laid a moment later, in
	// Tick, off the watcher's settled pose.
	default: break;
	}

	// A deadline derived from the MEASURED walk and the MEASURED hero pace, never from
	// a written number of seconds -- plus the waiting the governor may have to do,
	// which is bounded by a whole lap of the slowest watcher.
	double SlowestLap = 20.0;
	for (const FWatcher& W : Watchers)
	{
		SlowestLap = FMath::Max(SlowestLap,
			2.0 * FVector::Dist2D(W.RoundA, W.RoundB)
				/ FMath::Max(double(W.BasePace), 1.0));
	}
	if (Waypoints.Num() > 0 && Hero.IsValid())
	{
		const double Ideal = PathLength(Hero->GetActorLocation(), Waypoints)
			/ FMath::Max(MeasuredHeroSpeed, 100.0);
		PhaseDeadline = Now + Ideal * 2.5 + SlowestLap * double(Waypoints.Num()) + 20.0;
	}
	else
	{
		PhaseDeadline = Now + 30.0;
	}
	switch (Phase)
	{
	// The holds that wait on the yard rather than on a walk get a whole handful of
	// laps: the truck and the watcher have to come into step, and how long that takes
	// is the yard's business, not the submission's. Bounded, because an unbounded wait
	// on a yard that can never come into step would burn the whole sentinel and report
	// nothing.
	case 2:  PhaseDeadline += FMath::Min(SlowestLap * 8.0, 180.0) + 30.0; break;
	case 3:  PhaseDeadline = Now + FMath::Min(SlowestLap * 4.0, 90.0) + 20.0; break;
	case 7:  PhaseDeadline = Now + SlowestLap * 3.0 + 40.0; break;
	case 12: PhaseDeadline += SlowestLap * 4.0; break;
	case 8: case 16: PhaseDeadline += SlowestLap * 2.0; break;
	// Planned late (see above), so the deadline covers the longest walk this yard can
	// ask for plus the six-second hold, derived from the floor and the measured pace.
	case 9: case 17: PhaseDeadline = Now + 20000.0
		/ FMath::Max(MeasuredHeroSpeed, 100.0) + 40.0; break;
	case 10:         PhaseDeadline = Now + 30.0; break;
	default: break;
	}
}

void AStealthYardFunctionalTest::AdvancePhases(double Now)
{
	const bool bAtEndOfWalk = Waypoints.Num() > 0 && WaypointIndex >= Waypoints.Num();
	const double Elapsed = Now - PhaseStartedAt;
	const int32 Slot = RoundSlot();
	bool bDone = false;

	auto Held = [this, Now](bool bCondition, double Seconds) -> bool
	{
		if (!bCondition) { HoldSince = -1.0; return false; }
		if (HoldSince < 0.0) { HoldSince = Now; }
		return (Now - HoldSince) >= Seconds;
	};

	switch (Phase)
	{
	case 0:  bDone = Elapsed >= 3.0; break;
	case 1:  case 6: case 11: case 15: bDone = (PlateIndex == (Phase == 1 ? 1
				: (Phase == 6 ? 2 : (Phase == 11 ? 3 : 4)))); break;
	case 2:
		// The truck has to have lain across the covering watcher's line for a real
		// stretch WHILE the runner was inside that watcher's live reach and view
		// width. Measured, never assumed -- and only once the runner has actually
		// stepped in, which is its own decision (ShadowEntryRipe) and not this walk's.
		bDone = bShadowEntryCommitted && bAtEndOfWalk
			&& TruckCoverBest >= kMinTruckCoverS;
		break;
	case 3:
		// ... and then it clears, and the board owes the yard a caught reading within
		// the quarter second the prompt promises.
		bDone = (TruckClearedAt > 0.0) && (Now - TruckClearedAt) >= kDeadlineS + 0.6;
		break;
	case 4:  case 13: bDone = Held(bAtEndOfWalk, 6.0); break;
	case 5:  case 14: bDone = bAtEndOfWalk && GateEntries >= 2; break;
	case 7:
	{
		// One complete lap of the covering watcher with nobody seeing anything: the
		// half of EachWatcherSeesWithItsOwnEyes that the FIRST watch owns.
		const int32 Cover = WatcherOnRound(LaneRoundTag);
		const double Lap = (Cover != INDEX_NONE)
			? 2.0 * FVector::Dist2D(Watchers[Cover].RoundA, Watchers[Cover].RoundB)
				/ FMath::Max(double(Watchers[Cover].BasePace), 1.0)
			: 20.0;
		bDone = bAtEndOfWalk && Held(true, Lap + 1.0);
		break;
	}
	case 8:  case 16: bDone = (Slot >= 0 && RoundEnding[Slot] == kAway); break;
	case 9:  case 17: bDone = Held(bAtEndOfWalk, 6.0); break;
	case 10: bDone = Elapsed >= 4.0; break;
	case 12: bDone = (Slot >= 0 && RoundEnding[Slot] == kCaught)
				&& (Now - RoundEndedAt[Slot]) >= kDeadlineS + 0.6; break;
	default: bDone = true; break;
	}

	if (!bDone)
	{
		if (Now > PhaseDeadline)
		{
			// A PHASE THAT OVERRAN. Before this is written off as a staging fault, the
			// gates a submission could STALL the drive with are re-checked
			// UNCONDITIONALLY: a yard whose watchers were never stood down is not
			// where the fixture left it, and a harness exit must never launder a FAIL.
			if (!GateNotRewired(Now) || !GateStandDown(Now))
			{
				return;
			}
			// ... including the RUNNING half, which is not otherwise armed during the
			// three windowed phases. A submission that simply never writes a pace
			// leaves every watcher standing still through a running round; the drive's
			// forward simulation then predicts cones that never sweep, no window ever
			// ripens, and the phase overruns -- which would hand a do-nothing delivery
			// a harness exit instead of the FAIL it earned. Judged only outside the
			// settle window, because the yard is allowed its quarter second even here.
			if (!RoundIsOver() && Now - LastModelChangeAt >= kSuppressAfterS
				&& !GateRoundStartsClean(Now))
			{
				return;
			}
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: phase %d of the drive ran past its derived "
					 "deadline (%.0fs) with the plate at %d, the model reading %s, the "
					 "best truck cover %.2fs against a %.1fs floor, the shadow entry "
					 "%s, and every watcher's numbers and pace exactly as the yard "
					 "staged them; the yard cannot finish the drive, which is ours and "
					 "not the submission's"),
				Phase, PhaseDeadline - PhaseStartedAt, PlateIndex,
				ReadingName(ModelOutcome), TruckCoverBest, kMinTruckCoverS,
				bShadowEntryCommitted ? TEXT("committed") : TEXT("never ripe")));
		}
		return;
	}

	// Two things happen between phases rather than inside one.
	if (Phase == 7)
	{
		bSplitHoldDone[0] = true;
		SplitCoveringWatcher[0] = WatcherOnRound(LaneRoundTag);
	}
	if (Phase == 12)
	{
		bSplitHoldDone[1] = true;
		SplitCoveringWatcher[1] = WatcherOnRound(LaneRoundTag);
	}
	if (Phase == 9)
	{
		// THE SERGEANT CHANGES THE WATCH -- and the yard is stood down when he does,
		// so no swap can jolt an outcome. Every gate is off for two seconds either
		// side of it.
		StagingUntil = Now + kRestageQuietS;
		BeginPhase(10, Now);
		StageWatch(1);
		if (!IsRunning())
		{
			return;
		}
		StagingUntil = FMath::Max(StagingUntil, Now + kRestageQuietS);
		return;
	}
	if (Phase >= 17)
	{
		bDriveComplete = true;
		return;
	}
	BeginPhase(Phase + 1, Now);
}

// ---------------------------------------------------------------------------
// The model.
// ---------------------------------------------------------------------------

int32 AStealthYardFunctionalTest::RoundSlot() const
{
	return FMath::Clamp(PlateIndex - 1, -1, 3);
}

void AStealthYardFunctionalTest::StepModel(double Now)
{
	// 1. HAS A FRESH ROUND BEGUN? A changed plate number -- nothing else -- re-arms
	//    the yard.
	if (PlateIndex != SeenRoundIndex)
	{
		SeenRoundIndex = PlateIndex;
		ModelOutcome = kRunning;
		LastModelChangeAt = Now;
		// The fresh round owns no ending yet, so it owns no burning lamp either.
		const int32 Fresh = RoundSlot();
		if (Fresh >= 0)
		{
			RoundCaughtBy[Fresh].Reset();
		}
	}
	if (!Hero.IsValid())
	{
		return;
	}
	const FVector Runner = Hero->GetActorLocation();
	VisibleSet(Runner, ModelVisible);

	// 2. IS THE RUNNER STANDING IN THE GATEWAY? Asked EVERY frame, whatever the round
	//    is doing. The drive walks into the gateway twice after a round has already
	//    been lost -- that walk is the whole of "caught is final even at the gate" --
	//    so this bookkeeping cannot sit behind the round-is-over early return.
	//
	// "REACHED THE GATE" IS ASKED OF THE GATE. The prompt discloses exactly one reader
	// -- the gate knows when somebody is standing in it -- so the model calls THAT, by
	// name, and never re-derives standing-in-it from the volume's extents. A
	// re-derivation is a second definition of the same words, and this one was
	// STRICTER than the disclosed reader (a point test on the runner's origin against
	// a half-extent the gate's own overlap answers to a capsule radius earlier), which
	// latched the model's away ending some five frames after a correct submission's
	// and failed the reference by name. Two definitions of one disclosed fact is the
	// undisclosed-gate defect, not a tolerance question.
	bool bAtGate = false;
	{
		bool bAsked = false;
		bAtGate = CallBoolFunc(Gate.Get(), TEXT("IsSomebodyStandingInIt"), bAsked);
		if (!bAsked)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the gate does not answer "
					 "IsSomebodyStandingInIt, which is the only reader of 'the runner "
					 "reached the gate' the prompt discloses; the fixture will not "
					 "grade against a second definition of its own"));
			return;
		}
	}
	if (bInGateVolume != bAtGate)
	{
		bInGateVolume = bAtGate;
		if (bAtGate)
		{
			++GateEntries;
		}
	}

	// 3. HOW THE ROUND ENDS. A round that is over stays over.
	if (ModelOutcome != kRunning)
	{
		return;
	}
	const int32 Slot = RoundSlot();
	if (ModelVisible.Num() > 0)
	{
		ModelOutcome = kCaught;
		LastModelChangeAt = Now;
		// WHO WAS LOOKING. Latched here and never re-derived: from this instant the
		// watchers freeze and the runner walks away, so "who can see the runner" and
		// "who saw the runner when the round ended" stop being the same question
		// within a second or two. That divergence is the lamp channel's whole lit
		// half -- see the note at the top of the header.
		if (Slot >= 0)
		{
			if (RoundEnding[Slot] >= 0) { ++RoundEndingChanges[Slot]; }
			RoundEnding[Slot] = kCaught;
			RoundEndedAt[Slot] = Now;
			RoundCaughtBy[Slot] = ModelVisible;
		}
	}
	else if (bAtGate)
	{
		ModelOutcome = kAway;
		LastModelChangeAt = Now;
		// Nobody caught anybody, so no lamp stays on.
		if (Slot >= 0)
		{
			if (RoundEnding[Slot] >= 0) { ++RoundEndingChanges[Slot]; }
			RoundEnding[Slot] = kAway;
			RoundEndedAt[Slot] = Now;
			RoundCaughtBy[Slot].Reset();
		}
	}
}

int32 AStealthYardFunctionalTest::BoardReading() const
{
	const AActor* const M = Mast.Get();
	const bool bRun = LightIntensity(M, TEXT("RunningLight")) > kLampLitFloor;
	const bool bAway = LightIntensity(M, TEXT("AwayLight")) > kLampLitFloor;
	const bool bCaught = LightIntensity(M, TEXT("CaughtLight")) > kLampLitFloor;
	const int32 Count = (bRun ? 1 : 0) + (bAway ? 1 : 0) + (bCaught ? 1 : 0);
	if (Count != 1)
	{
		return -1;
	}
	return bRun ? kRunning : (bAway ? kAway : kCaught);
}

FString AStealthYardFunctionalTest::BoardDescription() const
{
	const AActor* const M = Mast.Get();
	return FString::Printf(TEXT("running=%s away=%s caught=%s"),
		LightIntensity(M, TEXT("RunningLight")) > kLampLitFloor ? TEXT("BURNS") : TEXT("dark"),
		LightIntensity(M, TEXT("AwayLight")) > kLampLitFloor ? TEXT("BURNS") : TEXT("dark"),
		LightIntensity(M, TEXT("CaughtLight")) > kLampLitFloor ? TEXT("BURNS") : TEXT("dark"));
}

// ---------------------------------------------------------------------------
// The gates.
// ---------------------------------------------------------------------------

bool AStealthYardFunctionalTest::Suppressed(double Now) const
{
	if (Now < StagingUntil)
	{
		return true;   // the fixture itself moved something
	}
	if (Now - LastModelChangeAt < kSuppressAfterS)
	{
		return true;   // 1.6x the quarter second the prompt promises
	}
	return Hero.IsValid() && AnyVerdictMarginal(Hero->GetActorLocation());
}

bool AStealthYardFunctionalTest::GateNotRewired(double Now)
{
	(void)Now;
	auto SameF = [](double A, double B)
	{
		return FMath::Abs(A - B) <= FMath::Abs(B) * 0.001 + 0.001;
	};
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		const FWatcher& W = Watchers[i];
		AActor* const A = W.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a watcher stopped existing mid-run"));
			return false;
		}
		if (!SameF(W.Reach, W.StagedReach) || !SameF(W.HalfAngleDeg, W.StagedHalfAngleDeg)
			|| !SameF(W.BasePace, W.StagedBasePace) || W.RoundTag != W.StagedRoundTag)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: a watcher's own numbers were changed. "
					 "The yard set %s to reach %.0f uu, %.1f deg of view, a base pace "
					 "of %.0f uu/s on round '%s'; it now reads %.0f / %.1f / %.0f / "
					 "'%s'. The pace that is yours to write is PaceUuPerSec"),
				*W.Label, W.StagedReach, W.StagedHalfAngleDeg, W.StagedBasePace,
				*W.StagedRoundTag.ToString(), W.Reach, W.HalfAngleDeg, W.BasePace,
				*W.RoundTag.ToString()));
			return false;
		}
		// ON ITS OWN ROUND. This is load-bearing rather than ceremonial: the model
		// reads the watchers' LIVE transforms, so without it a submission that parks a
		// watcher on the runner makes the model AGREE the round should be caught, and
		// every other window becomes unreachable -- a do-nothing pass.
		const FVector At = A->GetActorLocation();
		const double Off = Dist2DToSegment(FVector2D(At.X, At.Y),
			FVector2D(W.RoundA.X, W.RoundA.Y), FVector2D(W.RoundB.X, W.RoundB.Y));
		if (Off > kWatcherOnRoundUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: %s was moved off its own round. It is "
					 "%.0f uu from the line between the two posts carrying its own "
					 "RoundTag '%s' ((%.0f,%.0f) to (%.0f,%.0f)); %.0f uu is as far as "
					 "the yard allows"),
				*W.Label, Off, *W.RoundTag.ToString(), W.RoundA.X, W.RoundA.Y,
				W.RoundB.X, W.RoundB.Y, kWatcherOnRoundUu));
			return false;
		}
	}
	for (int32 i = 0; i < Blockers.Num(); ++i)
	{
		const AActor* const B = Blockers[i].Get();
		bool bOk = false;
		const FVector Half = ReadVector(B, TEXT("BlockHalfExtentUu"), bOk);
		if (B == nullptr || FVector::Dist(B->GetActorLocation(), StagedBlockerAt[i])
				> kPropMovedUu
			|| !Half.Equals(StagedBlockerHalf[i], 0.1))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: solid block %d was moved or resized. "
					 "The yard put it at (%.0f,%.0f) with a half-extent of "
					 "(%.0f,%.0f,%.0f)"), i + 1, StagedBlockerAt[i].X,
				StagedBlockerAt[i].Y, StagedBlockerHalf[i].X, StagedBlockerHalf[i].Y,
				StagedBlockerHalf[i].Z));
			return false;
		}
	}
	auto Unmoved = [this](const AActor* A, const FVector& Where, const TCHAR* What) -> bool
	{
		if (A != nullptr && FVector::Dist(A->GetActorLocation(), Where) <= kPropMovedUu)
		{
			return true;
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardIsNotYoursToRewire: %s was moved. The yard put it at "
				 "(%.0f,%.0f,%.0f)"), What, Where.X, Where.Y, Where.Z));
		return false;
	};
	if (!Unmoved(Mast.Get(), StagedMastAt, TEXT("the mast"))
		|| !Unmoved(Plate.Get(), StagedPlateAt, TEXT("the start plate"))
		|| !Unmoved(Gate.Get(), StagedGateAt, TEXT("the gate")))
	{
		return false;
	}
	if (const AActor* const T = Truck.Get())
	{
		const FVector At = T->GetActorLocation();
		const FVector Rail = TruckRailHalf.GetSafeNormal();
		const FVector Delta = At - TruckHome;
		const double Along = FVector::DotProduct(Delta, Rail);
		const double Sideways = (Delta - Rail * Along).Size2D();
		if (Sideways > 8.0 || FMath::Abs(Along) > TruckRailHalf.Size() + 150.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: the truck is off its own rail. It is "
					 "at (%.0f,%.0f), %.0f uu to one side of the line the yard laid "
					 "for it"), At.X, At.Y, Sideways));
			return false;
		}
	}
	return true;
}

bool AStealthYardFunctionalTest::GateExactlyOneLamp(double Now)
{
	(void)Now;
	const AActor* const M = Mast.Get();
	const bool bRun = LightIntensity(M, TEXT("RunningLight")) > kLampLitFloor;
	const bool bAway = LightIntensity(M, TEXT("AwayLight")) > kLampLitFloor;
	const bool bCaught = LightIntensity(M, TEXT("CaughtLight")) > kLampLitFloor;
	const int32 Count = (bRun ? 1 : 0) + (bAway ? 1 : 0) + (bCaught ? 1 : 0);
	if (Count == 1)
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ExactlyOneLampBurnsOnTheBoard: %d of 3 board lights burning (%s); "
			 "exactly one must burn. Nothing has to have happened yet -- before "
			 "anybody has stepped on the plate the yard is waiting, and waiting reads "
			 "running"), Count, *BoardDescription()));
	return false;
}

bool AStealthYardFunctionalTest::GateSeenTheMomentTheyCross(double Now)
{
	const int32 Cover = WatcherOnRound(LaneRoundTag);
	if (ModelVisible.Num() > 0)
	{
		if (CrossFirstVisibleAt < 0.0)
		{
			CrossFirstVisibleAt = Now;
		}
		// The SECOND half of the two-watch comparison lives here rather than in a
		// second gate on the same frames: the identical standing place that nobody
		// could hold on watch 1 is held on watch 2 by a DIFFERENT watcher. The
		// run-level check refuses to report a pass unless the two holds disagreed.
		bSplitHoldSeen[1] = true;
		SplitCoveringWatcher[1] = Cover;
	}
	if (CrossFirstVisibleAt < 0.0)
	{
		// Before the cone reaches the runner the board owes the yard a running
		// reading, and nothing else.
		if (BoardReading() != kRunning)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SeenTheMomentTheyCross: the board reads '%s' at the split spot "
					 "(%.0f,%.0f) while no watcher can see the runner at all. The "
					 "round is still running until somebody's own reach AND own view "
					 "width hold the runner with nothing solid between (%s)"),
				ReadingName(BoardReading()), SpotSplit.X, SpotSplit.Y,
				*BoardDescription()));
			return false;
		}
		return true;
	}
	if (Now - CrossFirstVisibleAt <= kDeadlineS)
	{
		return true;   // inside the quarter second the prompt allows, plus its margin
	}
	if (BoardReading() == kCaught)
	{
		return true;
	}
	const double Since = (Cover != INDEX_NONE && Watchers.IsValidIndex(Cover))
		? double(Watchers[Cover].BasePace) : 0.0;
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("SeenTheMomentTheyCross: %.2f s after the covering watcher's own reach "
			 "and view width first held the runner at the split spot (%.0f,%.0f), the "
			 "board still reads '%s' (%s). That crossing opens and closes entirely "
			 "between two of the watcher's turns -- %.2f s of continuous sight with "
			 "%.2f s of clearance to the nearest turn at both ends, at a pace of %.0f "
			 "uu/s -- so nothing that only re-asks the question when a watcher reaches "
			 "a post, or on a one-to-two-second re-scan, ever samples inside it"),
		Now - CrossFirstVisibleAt, SpotSplit.X, SpotSplit.Y,
		ReadingName(BoardReading()), *BoardDescription(), MeasuredCrossWindowS,
		MeasuredCrossClearanceS, Since));
	return false;
}

bool AStealthYardFunctionalTest::GateTruckShadow(double Now)
{
	const int32 Cover = WatcherOnRound(LaneRoundTag);
	if (Cover == INDEX_NONE || !Hero.IsValid())
	{
		return true;
	}
	const FWatcher& W = Watchers[Cover];
	const AActor* const A = W.Actor.Get();
	if (A == nullptr)
	{
		return true;
	}
	const FVector Eye = A->GetActorLocation();
	const FVector Runner = Hero->GetActorLocation();
	// Would this watcher hold the runner if the truck were not there?
	const bool bWouldSee = ModelCanSeeFrom(W, Eye, A->GetActorForwardVector(),
		Runner, /*bIncludeTruck=*/false);
	const bool bTruckOnLine = TruckFootprintIndex != INDEX_NONE
		&& SegmentHitsRect(FVector2D(Eye.X, Eye.Y), FVector2D(Runner.X, Runner.Y),
			Footprints[TruckFootprintIndex].Centre,
			Footprints[TruckFootprintIndex].Half);

	// The covered half only means anything WHILE THE ROUND IS STILL RUNNING. Once the
	// truck has let go and the round has ended caught, the board reads caught for ever
	// -- so if the truck happened to swing back across the line during the second phase
	// 3 waits out, the test below would demand a running board from a yard that is
	// correctly showing caught. That is a false FAIL, and it is one the reference finds
	// first.
	const bool bStillRunning = !RoundIsOver();
	if (bWouldSee && bTruckOnLine && bStillRunning)
	{
		if (TruckCoverSince < 0.0)
		{
			TruckCoverSince = Now;
		}
		TruckCoverBest = FMath::Max(TruckCoverBest, Now - TruckCoverSince);
		// WHILE THE TRUCK LIES ACROSS THE LINE the watcher's lamp is dark and the
		// board still reads running -- even though the runner is squarely inside that
		// watcher's live reach and view width. This is where a correct submission and
		// an occlusion-blind one disagree, and where a blocker set cached at BeginPlay
		// or a baked visibility map dies: the geometry is only right if the line test
		// is re-run against live transforms.
		const double Lamp = AnyLightIntensity(A);
		const int32 Board = BoardReading();
		if (Lamp > kLampLitFloor || Board != kRunning)
		{
			const FVector TruckAt = Truck.IsValid()
				? Truck->GetActorLocation() : FVector::ZeroVector;
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheTruckMakesAShadowWhileItPasses: the truck is at (%.0f,%.0f) "
					 "with its %.0fx%.0f footprint lying across the flat line from %s "
					 "at (%.0f,%.0f) to the runner at (%.0f,%.0f), and has been for "
					 "%.2f s -- yet that watcher's lamp %s and the board reads '%s' "
					 "(%s). The crates, the wall and the truck are solid and block a "
					 "watcher's view, and where the truck is at this instant is what "
					 "settles it"),
				TruckAt.X, TruckAt.Y, TruckHalf.X * 2.0, TruckHalf.Y * 2.0, *W.Label,
				Eye.X, Eye.Y, Runner.X, Runner.Y, Now - TruckCoverSince,
				Lamp > kLampLitFloor ? TEXT("BURNS") : TEXT("is dark"),
				ReadingName(Board), *BoardDescription()));
			return false;
		}
		return true;
	}

	// THE CLEARING. The lamp is deliberately NOT asserted lit here, and this is the one
	// place the two halves of the prompt meet: the instant the watcher can see the
	// runner the round has ENDED, and from that moment the stand-down rule requires
	// every lamp dark. A gate asking for a burning lamp and a caught board on the same
	// frame is unsatisfiable, and unsatisfiable for the REFERENCE first. So the lamp
	// carries the covered half and the BOARD carries the cleared half.
	if (TruckCoverSince >= 0.0)
	{
		if (TruckCoverBest >= kMinTruckCoverS && bWouldSee && !bTruckOnLine
			&& TruckClearedAt < 0.0)
		{
			TruckClearedAt = Now;
			++TruckWindowsProved;
		}
		TruckCoverSince = -1.0;
	}
	if (!bStillRunning && TruckClearedAt < 0.0)
	{
		// The round ended without the truck ever having let go of the line -- which
		// means it ended for some OTHER reason, and the window this gate exists to
		// measure never happened. Say nothing here; the run-level check reports the
		// best cover measured, and the phase deadline attributes it to the yard.
		return true;
	}
	if (TruckClearedAt > 0.0 && Now - TruckClearedAt > kDeadlineS
		&& BoardReading() != kCaught && Phase == 3)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheTruckMakesAShadowWhileItPasses: %.2f s after the truck's footprint "
				 "cleared the line from %s to the runner -- leaving the runner inside "
				 "that watcher's own reach and own view width with nothing solid "
				 "between them -- the board still reads '%s' (%s). The truck had lain "
				 "across that line for %.2f s, and the whole stretch of sight it sits "
				 "inside runs %.2f s and opens and closes between two of that "
				 "watcher's turns, so nothing that re-asks the question only at a "
				 "patrol post -- or on a one-to-two-second re-scan -- ever samples the "
				 "moment it clears"),
			Now - TruckClearedAt, *W.Label, ReadingName(BoardReading()),
			*BoardDescription(), TruckCoverBest, MeasuredShadowWindowS));
		return false;
	}
	return true;
}

bool AStealthYardFunctionalTest::GateOwnEyes(double Now)
{
	(void)Now;
	const int32 Half = (Watch == 0) ? 0 : 1;
	if (ModelVisible.Num() > 0)
	{
		bSplitHoldSeen[Half] = true;
		// From the model's first visible frame the crossing gate owns this window and
		// the round has ended, so the lamps are the stand-down gate's business.
		return true;
	}
	// Up to that frame the board and every lamp must match the model.
	const int32 Board = BoardReading();
	const int32 Slot = RoundSlot();
	const int32 Want = (Slot >= 0 && RoundEnding[Slot] >= 0)
		? RoundEnding[Slot] : ModelOutcome;
	if (Board == Want && DescribeLitLamps() == FString(TEXT("{}")))
	{
		return true;
	}
	const int32 Cover = WatcherOnRound(LaneRoundTag);
	const FString Who = Watchers.IsValidIndex(Cover)
		? Watchers[Cover].Label : FString(TEXT("nobody"));
	const double R = Watchers.IsValidIndex(Cover) ? double(Watchers[Cover].Reach) : 0.0;
	const double Th = Watchers.IsValidIndex(Cover)
		? double(Watchers[Cover].HalfAngleDeg) : 0.0;
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("EachWatcherSeesWithItsOwnEyes: standing at the split spot (%.0f,%.0f) on "
			 "watch %d, the round covering that ground is walked by %s, whose OWN "
			 "reach is %.0f uu and whose OWN view width is %.1f deg. Nobody can hold "
			 "the runner there right now, so the board owes the yard '%s' with every "
			 "head lamp dark; it reads '%s' with lamps %s. The same standing place is "
			 "walked on BOTH watches with a different watcher covering it, and one "
			 "shared sight radius cannot report both answers"),
		SpotSplit.X, SpotSplit.Y, Watch + 1, *Who, R, Th, ReadingName(Want),
		ReadingName(Board), *DescribeLitLamps()));
	return false;
}

bool AStealthYardFunctionalTest::GateCaughtIsFinal(double Now)
{
	(void)Now;
	const int32 Slot = RoundSlot();
	if (Slot < 0 || RoundEnding[Slot] != kCaught)
	{
		return true;
	}
	if (BoardReading() == kCaught)
	{
		return true;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("CaughtIsFinalEvenAtTheGate: round %d was lost at t=%.1f s and the board "
			 "now reads '%s' (%s) with the plate still at %d. The first ending wins "
			 "for ever: reaching the gate after being caught still reads caught, and "
			 "%d walk(s) into the gateway have happened since"),
		Slot + 1, RoundEndedAt[Slot], ReadingName(BoardReading()), *BoardDescription(),
		PlateIndex, GateEntries));
	return false;
}

bool AStealthYardFunctionalTest::GateAwayIsFinal(double Now)
{
	(void)Now;
	const int32 Slot = RoundSlot();
	if (Slot < 0 || RoundEnding[Slot] != kAway)
	{
		return true;
	}
	if (BoardReading() == kAway)
	{
		return true;
	}
	const int32 Cover = WatcherOnRound(LaneRoundTag);
	const FString Who = Watchers.IsValidIndex(Cover)
		? Watchers[Cover].Label : FString(TEXT("a watcher"));
	const double R = Watchers.IsValidIndex(Cover) ? double(Watchers[Cover].Reach) : 0.0;
	const double Th = Watchers.IsValidIndex(Cover)
		? double(Watchers[Cover].HalfAngleDeg) : 0.0;
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("AwayIsFinalEvenInPlainSight: round %d was won at t=%.1f s, and the "
			 "runner is now standing squarely inside %s's live reach (%.0f uu) and "
			 "view width (%.1f deg) -- yet the board reads '%s' (%s). Being seen after "
			 "getting away still reads away; a round ends once and only once"),
		Slot + 1, RoundEndedAt[Slot], *Who, R, Th, ReadingName(BoardReading()),
		*BoardDescription()));
	return false;
}

bool AStealthYardFunctionalTest::GateRoundStartsClean(double Now)
{
	(void)Now;
	const int32 Slot = RoundSlot();
	if (Slot < 0)
	{
		// Before the first click the yard is waiting, and waiting reads running.
		if (BoardReading() == kRunning)
		{
			return true;
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("EveryRoundStartsCleanWhenThePlateClicks: nobody has stepped on the "
				 "plate yet (it reads %d) and the board already shows '%s' (%s). "
				 "Before anybody has begun a round the yard is simply waiting, and "
				 "waiting reads running"), PlateIndex, ReadingName(BoardReading()),
			*BoardDescription()));
		return false;
	}
	if (RoundEnding[Slot] >= 0)
	{
		return true;   // this round has already ended; another gate owns it
	}
	if (BoardReading() != kRunning)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("EveryRoundStartsCleanWhenThePlateClicks: the plate clicked from %d "
				 "to %d and nothing has ended round %d yet, but the board reads '%s' "
				 "(%s). A fresh plate number re-arms everything -- a latch armed once "
				 "for the session never re-arms, so the next round opens still showing "
				 "the one before"),
			PlateIndex - 1, PlateIndex, Slot + 1, ReadingName(BoardReading()),
			*BoardDescription()));
		return false;
	}
	// ... and every watcher is walking its round again at ITS OWN base pace.
	for (const FWatcher& W : Watchers)
	{
		const double Want = double(W.BasePace);
		if (FMath::Abs(double(W.Pace) - Want) > FMath::Max(Want * kPaceTolFrac, 0.5))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("EveryRoundStartsCleanWhenThePlateClicks: round %d is running "
					 "(the plate reads %d) and %s is pacing at %.1f uu/s while ITS OWN "
					 "base pace reads %.1f. There is no 'the' pace here -- each watcher "
					 "carries its own, and the sergeant may have re-set it since the "
					 "last round"),
				Slot + 1, PlateIndex, *W.Label, W.Pace, Want));
			return false;
		}
	}
	return true;
}

bool AStealthYardFunctionalTest::GateLampsShowWhatIsSeen(double Now)
{
	(void)Now;
	TArray<int32> Lit;
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		if (AnyLightIntensity(Watchers[i].Actor.Get()) > kLampLitFloor)
		{
			Lit.Add(i);
		}
	}
	if (Lit == ModelVisible)
	{
		return true;
	}
	FString Numbers;
	for (const FWatcher& W : Watchers)
	{
		Numbers += FString::Printf(TEXT("%s[reach %.0f, view %.1f deg] "),
			*W.Label, W.Reach, W.HalfAngleDeg);
	}
	const FString Control = (SentryIndex != INDEX_NONE
		&& Lit.Contains(SentryIndex))
		? FString::Printf(TEXT(" The walled sentry (%s) is among them: it has the "
			"largest reach and the widest view width in the yard and a solid wall "
			"across every line from its round to every place the runner can stand, so "
			"a range-only sight test lights it and a cone test that never asks what is "
			"in the way lights it too."), *Watchers[SentryIndex].Label)
		: FString();
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("EachWatcherShowsWhatItCanSeeRightNow: the round is still running and the "
			 "burning head lamps should be exactly %s, but they are %s. %s A watcher's "
			 "lamp burns exactly while THAT watcher can see the runner -- its own "
			 "reach, its own view width, from where it is standing and facing at this "
			 "instant, with nothing solid on the flat line, and the truck is solid "
			 "wherever it happens to be.%s"),
		*DescribeSet(ModelVisible), *DescribeSet(Lit), *Numbers, *Control));
	return false;
}

bool AStealthYardFunctionalTest::GateStandDown(double Now)
{
	(void)Now;
	const int32 Slot = RoundSlot();
	if (Slot < 0 || RoundEnding[Slot] < 0)
	{
		return true;   // the round is still running; another channel owns it
	}

	// HALF ONE: every watcher stands still. No exceptions, no matter who caught whom.
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		const FWatcher& W = Watchers[i];
		if (FMath::Abs(double(W.Pace)) > 0.5)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardStandsDownWhenTheRoundIsOver: round %d ended %s at "
					 "t=%.1f s and the plate still reads %d, but %s is pacing at %.1f "
					 "uu/s. From the moment a round has ended until a fresh one begins "
					 "every watcher stands still"),
				Slot + 1, ReadingName(RoundEnding[Slot]), RoundEndedAt[Slot],
				PlateIndex, *W.Label, W.Pace));
			return false;
		}
	}

	// HALF TWO -- THE LIT HALF OF THE LAMP CHANNEL, and the only place in the run where
	// a burning head lamp is REQUIRED. The lamps that stay on are the ones that could
	// see the runner AT THE INSTANT THE ROUND ENDED, and nothing else; a round that
	// ended at the gate leaves every lamp dark. That set was latched when the round
	// ended and is never re-derived, which is exactly the difference this gate
	// measures: within a second or two of a catch the watchers are frozen and the
	// runner has walked away, so a submission that recomputes "who can see the runner"
	// during the stand-down reports {} and a submission that darkens everything
	// reports {} too. Both are named here, and the in-scene control is gauged in the
	// same breath, because the sentry is never in the latched set either.
	const TArray<int32>& Want = RoundCaughtBy[Slot];
	TArray<int32> Lit;
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		if (AnyLightIntensity(Watchers[i].Actor.Get()) > kLampLitFloor)
		{
			Lit.Add(i);
		}
	}
	if (Lit == Want)
	{
		return true;
	}
	FString Live;
	for (int32 i = 0; i < Watchers.Num(); ++i)
	{
		if (ModelVisible.Contains(i))
		{
			Live += FString::Printf(TEXT("%s "), *Watchers[i].Label);
		}
	}
	if (Live.IsEmpty())
	{
		Live = TEXT("nobody");
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheYardStandsDownWhenTheRoundIsOver: round %d ended %s at t=%.1f s and "
			 "the plate still reads %d, so the burning head lamps should be exactly %s "
			 "-- the watchers that could see the runner AT THAT INSTANT -- and they are "
			 "%s. Every other lamp is dark, and a round that ended at the gate leaves "
			 "them all dark. For contrast, the model says %s could see the runner RIGHT "
			 "NOW, from where the watchers are frozen and where the runner has since "
			 "walked to; that is a different question and it is not the one the yard is "
			 "showing"),
		Slot + 1, ReadingName(RoundEnding[Slot]), RoundEndedAt[Slot], PlateIndex,
		*DescribeSet(Want), *DescribeSet(Lit), *Live));
	return false;
}

bool AStealthYardFunctionalTest::RoundIsOver() const
{
	const int32 Slot = RoundSlot();
	return Slot >= 0 && RoundEnding[Slot] >= 0;
}

bool AStealthYardFunctionalTest::GateControlAtCheckpoint(double Now)
{
	// THE IN-SCENE NEGATIVE CONTROL, gauged at EVERY checkpoint whatever the
	// suppression: the walled sentry can never be marginal about anything, because a
	// solid wall stands across every line from its round to every place the runner can
	// be, and PrepareTest refused to start unless that was true.
	if (SentryIndex == INDEX_NONE || !Watchers.IsValidIndex(SentryIndex))
	{
		return true;
	}
	const FWatcher& S = Watchers[SentryIndex];
	if (AnyLightIntensity(S.Actor.Get()) <= kLampLitFloor)
	{
		return true;
	}
	const int32 Slot = RoundSlot();
	const bool bOver = (Slot >= 0 && RoundEnding[Slot] >= 0);
	const AActor* const A = S.Actor.Get();
	const FVector At = A ? A->GetActorLocation() : FVector::ZeroVector;
	const FVector Runner = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	const double Flat = FVector::Dist2D(At, Runner);
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("%s: the walled sentry (%s) has its lamp BURNING at t=%.1f s. It is at "
			 "(%.0f,%.0f), %.0f uu flat from the runner at (%.0f,%.0f), with the "
			 "largest reach (%.0f uu) and the widest view width (%.1f deg) in the "
			 "yard -- and a solid wall across every line from its round to every place "
			 "the runner can stand. It can never see anybody. A range-only sight test "
			 "lights it, and so does a cone test that never asks what is in the way"),
		bOver ? TEXT("TheYardStandsDownWhenTheRoundIsOver")
			  : TEXT("EachWatcherShowsWhatItCanSeeRightNow"),
		*S.Label, Now, At.X, At.Y, Flat, Runner.X, Runner.Y, S.Reach, S.HalfAngleDeg));
	return false;
}

// ---------------------------------------------------------------------------
// PrepareTest
// ---------------------------------------------------------------------------

void AStealthYardFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr || !ResolveStaging())
	{
		return;
	}
	if (const FString Unwired = DescribeBrokenPlayerInput(World); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. The "
				 "graded drive would still pass, so fix the substrate, not the task."),
			*Unwired));
		return;
	}
	RebuildFootprints();
	if (!ValidateNothingElseIsSolid() || !ValidateHeightsCannotMatter())
	{
		return;
	}
	if (!ValidateStagingContract())
	{
		return;
	}
	SolveSafeLaneBands();
	if (!SolveSpots())
	{
		return;
	}

	ModelOutcome = kRunning;
	SeenRoundIndex = PlateIndex;
	// THE SETTLE WINDOW STARTS AT THE START. Every gate that runs inside the window
	// gets the same quarter second of grace on the first frame of the run that it gets
	// after every later change -- otherwise a submission that paints the board from its
	// own Tick rather than from BeginPlay is judged on a frame whose outcome is decided
	// by actor tick order, which is neither something it controls nor something it can
	// observe. Nothing is lost: an empty delivery still dies on the first judged frame.
	LastModelChangeAt = GetWorld() ? double(GetWorld()->GetTimeSeconds()) : 0.0;
	Phase = 0;
	PhaseStartedAt = 0.0;
	PhaseDeadline = 30.0;
	Waypoints.Reset();
	WaypointIndex = 0;

	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	// The last entry is a SENTINEL, far past the drive, because the base class ends the
	// test the moment the last scheduled checkpoint is sampled. The drive models
	// roughly 350-450 s of world time -- a range, because three of its holds wait on
	// the yard's own periods -- and the fixture finishes itself as soon as its last
	// phase completes, so the sentinel costs nothing unless something is already wrong.
	Schedule.Add(kSentinelAtS);
	SetCheckpointSchedule(Schedule);
	bPrepared = true;
}

// ---------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------

void AStealthYardFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !bPrepared || !Hero.IsValid() || Watchers.Num() != 3)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	// EVERY NUMBER, EVERY FRAME. Four of them change part way through the night.
	ReReadNumbers();
	RebuildFootprints();

	// WHICH WAY THE TRUCK IS RUNNING, measured from two consecutive frames rather than
	// assumed: which end it set off toward is private to the truck, and the shadow
	// entry has to predict its position seconds ahead.
	if (const AActor* const T = Truck.Get())
	{
		const FVector At = T->GetActorLocation();
		if (bTruckPrevKnown && bRailEndsKnown)
		{
			const FVector2D Along(RailEndB.X - RailEndA.X, RailEndB.Y - RailEndA.Y);
			const FVector2D Step(At.X - TruckPrevAt.X, At.Y - TruckPrevAt.Y);
			if (Step.SizeSquared() > 0.01)
			{
				TruckHeading =
					(FVector2D::DotProduct(Along.GetSafeNormal(), Step) >= 0.0)
						? 1.0 : -1.0;
			}
		}
		TruckPrevAt = At;
		bTruckPrevKnown = true;
	}

	StepModel(Now);

	if (!GateNotRewired(Now))
	{
		return;
	}

	if (!Suppressed(Now))
	{
		// THE BOARD'S SHAPE, inside the same settle window as everything else. This was
		// once judged outside the window, which quietly narrowed the contract the
		// prompt discloses: a submission that paints the board in its own Tick reads
		// zero of three on the first frame whenever actor tick order puts this fixture
		// ahead of the mast, and a board transition split across two frames reads zero
		// or two for one frame. The prompt gives the yard a quarter of a second to
		// catch up after anything changes and makes no exception for this, so neither
		// does the fixture. An empty delivery still dies here, on the first judged
		// frame of the run, because nothing ever settles it.
		if (!GateExactlyOneLamp(Now))
		{
			return;
		}
		bool bOk = true;
		// EXACTLY ONE BOARD GATE, narrowest window first. The three windowed gates take
		// precedence; outside them the round's own state decides, so a round that has
		// ended is always owned by the gate whose name describes that ending and never
		// by the re-arm gate.
		const int32 Slot = RoundSlot();
		const int32 Ended = (Slot >= 0) ? RoundEnding[Slot] : -1;
		if (Phase == 12)
		{
			bOk = GateSeenTheMomentTheyCross(Now);
		}
		else if (Phase == 2 || Phase == 3)
		{
			bOk = GateTruckShadow(Now);
		}
		else if (Phase == 7)
		{
			bOk = GateOwnEyes(Now);
		}
		else if (Ended == kCaught)
		{
			bOk = GateCaughtIsFinal(Now);
		}
		else if (Ended == kAway)
		{
			bOk = GateAwayIsFinal(Now);
		}
		else
		{
			bOk = GateRoundStartsClean(Now);
		}
		// THEN EXACTLY ONE INDEPENDENT CHANNEL GATE, always LAST, and only once the
		// board has already been agreed. They are NOT suppressed inside a board gate's
		// window: suppressing them would leave the head lamps and the paces ungraded
		// on exactly the frames that matter most.
		if (bOk)
		{
			bOk = (Ended >= 0) ? GateStandDown(Now) : GateLampsShowWhatIsSeen(Now);
		}
		if (!bOk)
		{
			return;
		}
	}

	// THE SHADOW ENTRY. The runner stands on the lane rest point, in the open and safe,
	// until the covering watcher's cone and the truck's rail come into step -- and then
	// walks the last leg in one committed go. Both halves matter: waiting is what makes
	// the window a measurement instead of a coin toss, and committing without
	// re-governing is what stops the walk stalling half way in, where the truck's
	// shadow is the only thing between the runner and the end of the round.
	if (Phase == 2 && !bShadowEntryCommitted
		&& Waypoints.Num() > 0 && WaypointIndex >= Waypoints.Num())
	{
		double ArriveS = 0.0;
		double CoverS = 0.0;
		double ClearS = 0.0;
		if (ShadowEntryRipe(ArriveS, CoverS, ClearS))
		{
			PlanWalkTo(SpotShadow, /*bViaLane=*/false);
			bWalkReleased = true;   // the ripeness test IS this leg's governor
			bShadowEntryCommitted = true;
			UE_LOG(LogTemp, Display,
				TEXT("[t3-stealth] shadow entry committed at t=%.2f after waiting "
					 "%.1fs: arrive in %.2fs, truck across the line for %.2fs, then it "
					 "lets go at +%.2fs"),
				Now, Now - ShadowWaitSince, ArriveS, CoverS, ClearS);
		}
		else if (Now - LastRipeReportAt > 10.0)
		{
			LastRipeReportAt = Now;
			UE_LOG(LogTemp, Display,
				TEXT("[t3-stealth] waiting on the lane at (%.0f,%.0f) for the truck and "
					 "the cone to come into step (%.1fs so far)"),
				SpotShadowWait.X, SpotShadowWait.Y, Now - ShadowWaitSince);
		}
	}

	// The two stand-down holds are planned a moment after their phase opens, off the
	// pose the covering watcher SETTLED at rather than the one it was walking through.
	if ((Phase == 9 || Phase == 17) && Waypoints.Num() == 0
		&& Now - PhaseStartedAt >= 0.6)
	{
		const int32 Cover = WatcherOnRound(LaneRoundTag);
		FVector Seen;
		if (Cover != INDEX_NONE && SolveSeenSpot(Cover, Seen))
		{
			SpotSeen = Seen;
			PlanWalkTo(SpotSeen, true);
		}
		else
		{
			// Nowhere in front of it is both visible and reachable. That is the yard's
			// fault, so the hold falls back to standing where the runner is; the
			// stand-down gate still grades every pace and every lamp, it simply grades
			// them without the runner planted in a frozen cone.
			PlanWalkTo(Hero->GetActorLocation(), false);
			UE_LOG(LogTemp, Warning,
				TEXT("[t3-stealth] phase %d: no reachable place inside the frozen "
					 "covering watcher's reach and view width; holding where the "
					 "runner stands instead"), Phase);
		}
	}

	DriveHero(Now);
	AdvancePhases(Now);

	if (bDriveComplete && IsRunning())
	{
		int32 Caught = 0;
		int32 Away = 0;
		int32 Changed = 0;
		for (int32 i = 0; i < 4; ++i)
		{
			Caught += (RoundEnding[i] == kCaught) ? 1 : 0;
			Away += (RoundEnding[i] == kAway) ? 1 : 0;
			Changed += RoundEndingChanges[i];
		}
		if (Caught < 2 || Away < 2 || Changed > 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("BothEndingsHappenedTwice: across the four rounds the yard ended "
					 "caught %d time(s) and away %d time(s), and %d round(s) showed a "
					 "second ending after the first. The night is long: the yard has to "
					 "be able to run round after round, ending some one way and some "
					 "the other, and a round ends once and only once"),
				Caught, Away, Changed));
			return;
		}
		// AND THE DISCRIMINATING SITUATION HAS TO HAVE HAPPENED. This is about the RUN,
		// not the submission: the same standing place had to be held on both watches
		// and give OPPOSITE answers, or a shared sight radius would have graded exactly
		// like three watchers with three sets of numbers.
		if (!bSplitHoldDone[0] || !bSplitHoldDone[1]
			|| bSplitHoldSeen[0] || !bSplitHoldSeen[1])
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the split spot (%.0f,%.0f) did not mean "
					 "opposite things on the two watches -- watch 1 %s the runner and "
					 "watch 2 %s (holds completed: %d / %d). Without that, one shared "
					 "sight radius would grade exactly like three watchers with three "
					 "sets of numbers, and EachWatcherSeesWithItsOwnEyes proved "
					 "nothing"),
				SpotSplit.X, SpotSplit.Y,
				bSplitHoldSeen[0] ? TEXT("held") : TEXT("never held"),
				bSplitHoldSeen[1] ? TEXT("held it") : TEXT("never did"),
				bSplitHoldDone[0] ? 1 : 0, bSplitHoldDone[1] ? 1 : 0));
			return;
		}
		if (TruckWindowsProved < 1)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the truck never lay across the covering "
					 "watcher's line for %.1f s and then cleared it while the runner "
					 "was still inside that watcher's reach and view width (best cover "
					 "measured %.2f s). The moving-occluder gate had nothing to "
					 "measure, which is the yard's fault and not the submission's"),
				kMinTruckCoverS, TruckCoverBest));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
			TEXT("Four rounds ran: %d caught, %d away, no round ever showed two "
				 "endings. The split spot was held on both watches and meant opposite "
				 "things; the truck proved %d shadow window(s); the walled sentry's "
				 "lamp stayed dark at every checkpoint."),
			Caught, Away, TruckWindowsProved));
	}
}

void AStealthYardFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	FString Bits;
	for (const FWatcher& W : Watchers)
	{
		double D = 0.0;
		double Ang = 0.0;
		const bool bSees = ModelCanSee(W, H, true, D, Ang);
		Bits += FString::Printf(TEXT("%s['%s' d%.0f/%.0f a%.1f/%.1f see%d pace%.0f "
			"lamp%d] "), *W.Label, *W.RoundTag.ToString(), D, W.Reach, Ang,
			W.HalfAngleDeg, bSees ? 1 : 0, W.Pace,
			AnyLightIntensity(W.Actor.Get()) > kLampLitFloor ? 1 : 0);
	}
	const FVector T = Truck.IsValid() ? Truck->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-stealth calib] cp%d t=%.2f watch=%d phase=%d at=(%.0f,%.0f) "
			 "plate=%d model=%s board=[%s] truck=(%.0f,%.0f) cover=%.2f %s"),
		Index, Now, Watch + 1, Phase, H.X, H.Y, PlateIndex, ReadingName(ModelOutcome),
		*BoardDescription(), T.X, T.Y, TruckCoverBest, *Bits);
}

void AStealthYardFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	// The in-scene control is gauged at EVERY checkpoint, suppression or none.
	if (bPrepared && !GateControlAtCheckpoint(TimeSeconds))
	{
		return;
	}
	if (CheckpointIndex < kGradedCheckpoints)
	{
		return;
	}
	// THE SENTINEL. The base class ends the test the moment the last scheduled
	// checkpoint is sampled, so the run-level gate is evaluated here as well as when
	// the drive completes -- whichever comes first.
	if (bDriveComplete)
	{
		return;
	}
	// The drive did not finish. Before that is written off as a staging fault, the
	// gates a submission could stall the drive with are re-checked unconditionally: a
	// yard whose watchers were never stood down is not where the fixture left it, and a
	// yard whose watchers never started walking is not either.
	if (!GateNotRewired(TimeSeconds) || !GateStandDown(TimeSeconds))
	{
		return;
	}
	if (!RoundIsOver() && TimeSeconds - LastModelChangeAt >= kSuppressAfterS
		&& !GateRoundStartsClean(TimeSeconds))
	{
		return;
	}
	int32 Caught = 0;
	int32 Away = 0;
	for (int32 i = 0; i < 4; ++i)
	{
		Caught += (RoundEnding[i] == kCaught) ? 1 : 0;
		Away += (RoundEnding[i] == kAway) ? 1 : 0;
	}
	if (Caught < 2 || Away < 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("BothEndingsHappenedTwice: the yard ended caught %d time(s) and away "
				 "%d time(s) and the drive was still at phase %d when the run ran out "
				 "of time. A yard that can only ever end one way, or only once per "
				 "session, never reaches this"), Caught, Away, Phase));
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the drive was still at phase %d at the sentinel "
			 "with every continuous gate green, every watcher's numbers exactly as "
			 "staged and the yard properly stood down; the yard is staged so the drive "
			 "cannot finish, which is ours and not the submission's"), Phase));
}
