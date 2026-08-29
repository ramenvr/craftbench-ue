// Copyright CraftBench. All Rights Reserved.

#include "OldDoorYardFunctionalTest.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---------------------------------------------------------------- DISCLOSED
	// Every one of these is stated verbatim in the prompt. None is a private
	// threshold, and no gate compares against anything that is not on this list or
	// read live off the yard.
	constexpr double kOpenDeg       = 80.0;    // "at least 80 degrees from the pose it starts play in"
	constexpr double kShutDeg       = 10.0;    // "back within 10 degrees of that pose"
	constexpr double kBandS         = 1.20;    // "within 1.20 s"
	constexpr double kMaxDegPerSec  = 720.0;   // "never faster than 720 degrees per second"
	constexpr double kMaxCmPerSec   = 3000.0;  // "or 3000 cm per second"

	// ------------------------------------------------- UNDISCLOSED, AND WIDENINGS
	// Fixture clocking and staging tolerances. Every one of them either WIDENS the
	// disclosed contract (so a correct answer has more room, never less) or describes
	// the drive rather than the answer.
	//
	// The band grace is the one that has to be argued: the supplied travel clears
	// 80 deg in 0.444 s at 180 deg/s against a 1.20 s deadline, a 2.7x margin, so
	// this 0.2 s is not what keeps a correct answer alive - it is there so a single
	// frame of tick ordering between the fixture's model and the submission's can
	// never be the difference. At 20 FPS one frame is 0.05 s.
	constexpr double kBandGraceS    = 0.20;
	// Nothing is judged inside 1.5x the band after the FIXTURE'S OWN MODEL last
	// changed anywhere in the yard. Wired into Suppressed(); it is a yard-wide
	// cushion on top of the per-barrier and per-lamp clocks, never a substitute for
	// them, and it only ever makes a correct answer safer.
	constexpr double kSettleS       = 1.80;
	// Nor inside this window either side of a fixture-owned re-cut.
	constexpr double kRecutBlindS   = 1.50;
	// Long enough that at least 1.7 s of every dwell survives the settle suppression.
	constexpr double kDwellS        = 3.50;
	// How long the character has to have been standing squarely on a gate pad before
	// TheRunnerIsNotACrate judges anything. It MUST exceed kBandS + kBandGraceS or
	// the gate is unfair by construction: a correct answer is allowed the whole
	// disclosed 1.20 s to decide and its panel still has to travel afterwards. It is
	// belt-and-braces even so, because the gate itself now goes through BandVerdict,
	// which measures from the barrier's OWN last model change rather than from the
	// character's arrival.
	constexpr double kRunnerArmS    = 2.00;

	// The drive.
	constexpr double kWaypointUu    = 60.0;    // transit arrival
	constexpr double kPadArriveUu   = 30.0;    // arrival when the target IS a pad centre
	constexpr double kTaperUu       = 220.0;   // input tapers inside this of the last waypoint
	constexpr double kTaperFloor    = 0.16;    // and never below this, so it always arrives
	constexpr double kStopEpsUu     = 15.0;    // a crate has reached its stop
	constexpr double kPushStandUu   = 260.0;   // where the character waits before a shove
	constexpr double kPushAimUu     = 300.0;   // how far past the crate it walks while shoving
	constexpr double kLaneClearUu   = 380.0;   // every lane clears every rail by this

	// Staging tolerances.
	constexpr double kPinPosUu      = 2.0;     // a staged position may drift this far
	constexpr double kPinPct        = 0.001;   // a staged float may drift this fraction
	constexpr double kParkNearUu    = 10.0;    // a parking stop lands this close to a pad centre
	constexpr double kDeepFactor    = 5.0;     // and that is this many times inside the radius
	constexpr double kOpposedDot    = -0.8;    // the two contested rails approach from opposite sides
	constexpr double kTwinKeepUu    = 2000.0;  // the drive never comes this close to the twin
	constexpr double kBandMarginX   = 2.0;     // the staged travel must clear the band this many times over

	// The checkpoint schedule. Every 8 s is calibration; the last entry is a SENTINEL
	// far past anything the drive should need, because ACraftBenchFunctionalTest::Tick
	// ends the test the moment the last scheduled checkpoint is sampled -- so an entry
	// beyond the drive is the only thing that stops the run declaring success before
	// the last phase.
	//
	// 900 s IS DELIBERATELY GENEROUS AND IS NOT A MODEL. The first cut of this fixture
	// carried 420 s against a hand-modelled ~215 s drive; the model was low by roughly
	// a factor of two once the step table was counted properly (27 walking steps, 27
	// dwells of 3.5 s, 16 shoves of RailLen/ShoveSpeed and ~69,000 uu of routed
	// walking), which would have graded a CORRECT reference as a staging Error. The
	// sentinel is world time, not wall time: at a fixed timestep the engine runs
	// frames as fast as it can, and a run that finishes normally never reaches it, so
	// raising it costs nothing on a passing leg. It stays where it is until the
	// orchestrator reads the measured completion time out of the
	// "[t3-olddooryard] run complete at t=" line and re-tightens it to ~1.5x that.
	constexpr double kCalibEveryS   = 8.0;
	constexpr int32  kCalibCount    = 110;
	constexpr double kSentinelS     = 900.0;

	// Which gate owns the judged frames of a step. At most ONE of the arch gate's own
	// panel gates (Runner..Open) is ever armed, so a named FAIL is never a race
	// between two of them. TheOldDoorStillOpensInsideItsBand and
	// TheSecondGateAnswersToItsOwnPair are not in this list because their subjects are
	// DIFFERENT barriers: each judges its own on every judged frame and neither can
	// ever contend with these, which all judge the arch gate.
	enum EArmed : int32
	{
		ARM_NONE = 0,
		ARM_SHUT,        // TheGateStaysShutUntilBothItsCratesAreHome
		ARM_OPEN,        // TheGateOpensWhenBothItsCratesAreHome
		ARM_LEAVE,       // TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack
		ARM_CUTNOW,      // TheGateAnswersToWhatItIsCutForRightNow
		ARM_RUNNER       // TheRunnerIsNotACrate
	};
}

AOldDoorYardFunctionalTest::AOldDoorYardFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Reading the yard. Everything is read BY PROPERTY NAME off a live actor, so a
// submission that subclasses or renames still answers, and the fixture never links
// against a single line of the agent's code.
// ---------------------------------------------------------------------------

double AOldDoorYardFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (A != nullptr)
	{
		if (const FFloatProperty* const P =
				FindFProperty<FFloatProperty>(A->GetClass(), Name))
		{
			bOk = true;
			return static_cast<double>(P->GetPropertyValue_InContainer(A));
		}
		if (const FDoubleProperty* const D =
				FindFProperty<FDoubleProperty>(A->GetClass(), Name))
		{
			bOk = true;
			return D->GetPropertyValue_InContainer(A);
		}
	}
	bOk = false;
	return 0.0;
}

int32 AOldDoorYardFunctionalTest::ReadInt(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (A != nullptr)
	{
		if (const FIntProperty* const P =
				FindFProperty<FIntProperty>(A->GetClass(), Name))
		{
			bOk = true;
			return P->GetPropertyValue_InContainer(A);
		}
	}
	bOk = false;
	return 0;
}

FName AOldDoorYardFunctionalTest::ReadName(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (A != nullptr)
	{
		if (const FNameProperty* const P =
				FindFProperty<FNameProperty>(A->GetClass(), Name))
		{
			bOk = true;
			return P->GetPropertyValue_InContainer(A);
		}
	}
	bOk = false;
	return NAME_None;
}

AActor* AOldDoorYardFunctionalTest::ReadActor(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (A != nullptr)
	{
		if (const FObjectProperty* const P =
				FindFProperty<FObjectProperty>(A->GetClass(), Name))
		{
			bOk = true;
			return Cast<AActor>(P->GetObjectPropertyValue_InContainer(A));
		}
	}
	bOk = false;
	return nullptr;
}

bool AOldDoorYardFunctionalTest::WriteName(AActor* A, const TCHAR* Name,
	FName Value) const
{
	if (A != nullptr)
	{
		if (const FNameProperty* const P =
				FindFProperty<FNameProperty>(A->GetClass(), Name))
		{
			P->SetPropertyValue_InContainer(A, Value);
			return true;
		}
	}
	return false;
}

bool AOldDoorYardFunctionalTest::ResolveTagged(const TCHAR* Tag, int32 Expected,
	TArray<AActor*>& Out)
{
	Out.Reset();
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(Tag), Out);
	// Deterministic order, so a re-run reads the same yard in the same sequence.
	Out.Sort([](const AActor& A, const AActor& B) { return A.GetName() < B.GetName(); });
	if (Out.Num() != Expected)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected %d actor(s) tagged %s in the yard, "
				 "found %d"), Expected, Tag, Out.Num()));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::ResolveOne(const TCHAR* Tag,
	TWeakObjectPtr<AActor>& Out)
{
	TArray<AActor*> Found;
	if (!ResolveTagged(Tag, 1, Found))
	{
		return false;
	}
	Out = Found[0];
	return true;
}

USceneComponent* AOldDoorYardFunctionalTest::ResolvePanel(AActor* Door) const
{
	if (Door == nullptr)
	{
		return nullptr;
	}
	TArray<UStaticMeshComponent*> Meshes;
	Door->GetComponents<UStaticMeshComponent>(Meshes);
	if (Meshes.Num() == 0)
	{
		return nullptr;
	}
	// 1. The declared thing. 2. Else the largest by local bounds volume, ties by
	//    name ascending, so the answer never depends on enumeration order.
	for (UStaticMeshComponent* const M : Meshes)
	{
		if (M != nullptr && M->GetName() == TEXT("Panel"))
		{
			return M;
		}
	}
	Meshes.Sort([](const UStaticMeshComponent& A, const UStaticMeshComponent& B)
	{
		const FVector EA = A.Bounds.BoxExtent;
		const FVector EB = B.Bounds.BoxExtent;
		const double VA = EA.X * EA.Y * EA.Z;
		const double VB = EB.X * EB.Y * EB.Z;
		if (!FMath::IsNearlyEqual(VA, VB, 1.0))
		{
			return VA > VB;
		}
		return A.GetName() < B.GetName();
	});
	return Meshes[0];
}

UPointLightComponent* AOldDoorYardFunctionalTest::ResolveLight(AActor* Lamp) const
{
	if (Lamp == nullptr)
	{
		return nullptr;
	}
	TArray<UPointLightComponent*> Lights;
	Lamp->GetComponents<UPointLightComponent>(Lights);
	Lights.Sort([](const UPointLightComponent& A, const UPointLightComponent& B)
	{
		return A.GetName() < B.GetName();
	});
	return Lights.Num() > 0 ? Lights[0] : nullptr;
}

FString AOldDoorYardFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	// ADVISORY, and reported as a HARNESS-PRECONDITION rather than a FAIL: a level
	// nobody can drive by hand is the LEVEL's fault, never the submission's, and it
	// grades byte-identically while being uncontrollable. Read by PROPERTY NAME so a
	// renamed or subclassed pawn still answers.
	TArray<FString> Problems;

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
				TEXT("the pawn (%s) has nothing bound to %s"),
				*Hero->GetClass()->GetName(), *FString::Join(Unbound, TEXT(", "))));
		}
	}

	const AGameModeBase* const GameMode =
		World != nullptr ? World->GetAuthGameMode() : nullptr;
	const UClass* const PCClass =
		GameMode != nullptr ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the "
						  "player lands on a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts = FindFProperty<FArrayProperty>(
				 PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
		FScriptArrayHelper Helper(
			Contexts, Contexts->ContainerPtrToValuePtr<void>(
						  PCClass->GetDefaultObject()));
		int32 Applied = 0;
		for (int32 Index = 0; Element != nullptr && Index < Helper.Num(); ++Index)
		{
			if (Element->GetObjectPropertyValue(Helper.GetElementPtr(Index)) != nullptr)
			{
				++Applied;
			}
		}
		if (Applied == 0)
		{
			Problems.Add(FString::Printf(
				TEXT("%s applies no input mapping context"), *PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s carries no DefaultMappingContexts"), *PCClass->GetName()));
	}

	return FString::Join(Problems, TEXT("; "));
}

// ---------------------------------------------------------------------------
// Resolving the yard. Identity is by TAG, never by class: the agent may subclass or
// rename anything it likes.
// ---------------------------------------------------------------------------

bool AOldDoorYardFunctionalTest::ResolveYard()
{
	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no world"));
		return false;
	}

	TArray<AActor*> Found;
	if (!ResolveTagged(TEXT("YardBarrier"), 4, Found)) { return false; }

	// THE SURFACE SWAP, and it has to happen HERE -- before the per-role tag
	// lookups below, which would otherwise resolve the placed C++ instances and
	// grade the wrong surface. All four barriers are instances of the ONE supplied
	// class the agent extends, so all four are replaced or none is: a mixed yard
	// would grade C++ for the old door and Blueprint for the new gate, which is a
	// verdict about neither. Nothing happens on the C++ lane, where no Blueprint
	// under /Game/Tasks derives from the placed class.
	SwapAllForGradedBlueprint(Found);
	// Self-check rather than trusting the swap: re-resolve by the shared tag and
	// require the same four. A swap that half-completed (one instance refused to
	// spawn) shows up here as a count mismatch and a HARNESS-PRECONDITION, not as
	// a graded failure of the submission.
	if (!ResolveTagged(TEXT("YardBarrier"), 4, Found)) { return false; }

	if (!ResolveTagged(TEXT("YardPad"), 6, Found)) { return false; }
	if (!ResolveTagged(TEXT("YardCrate"), 3, Found)) { return false; }
	if (!ResolveTagged(TEXT("GateLamp"), 4, Found)) { return false; }

	struct FRole { const TCHAR* Tag; const TCHAR* Label; };

	// -------------------------------------------------------------- barriers
	const FRole BarrierRoles[4] = {
		{ TEXT("OldDoor"),   TEXT("the old door") },
		{ TEXT("QuietDoor"), TEXT("the door nobody goes near") },
		{ TEXT("ArchGate"),  TEXT("the arch gate") },
		{ TEXT("SideGate"),  TEXT("the second gate") },
	};
	for (int32 i = 0; i < 4; ++i)
	{
		TWeakObjectPtr<AActor> A;
		if (!ResolveOne(BarrierRoles[i].Tag, A)) { return false; }
		FBarrier B;
		B.Actor = A;
		B.Label = BarrierRoles[i].Label;
		B.Panel = ResolvePanel(A.Get());
		if (!B.Panel.IsValid())
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s carries no panel component to watch"),
				BarrierRoles[i].Label));
			return false;
		}
		// SHUT IS STRUCTURAL. The hinge is squared at BeginPlay and the panel carries
		// no relative rotation of its own, so the pose the panel holds at play-start
		// is exactly the barrier ACTOR's own yaw: a level-staged constant that
		// TheYardIsNotYoursToRewire pins for the whole run. Sampling the panel here
		// instead would let a submission that swings a panel open in its first frames
		// have its own wrong pose recorded as the pose it is graded against.
		B.StagedLoc = A->GetActorLocation();
		B.StagedYaw = A->GetActorRotation().Yaw;
		B.ShutYaw = B.StagedYaw;
		bool bOk1 = false, bOk2 = false;
		B.StagedOpenAngleDeg = ReadFloat(A.Get(), TEXT("OpenAngleDeg"), bOk1);
		B.StagedTravelRate = ReadFloat(A.Get(), TEXT("TravelRateDegPerSec"), bOk2);
		if (!bOk1 || !bOk2)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose OpenAngleDeg and "
					 "TravelRateDegPerSec readably"), BarrierRoles[i].Label));
			return false;
		}
		Barriers.Add(B);
	}
	IdxOldDoor = 0;
	IdxTwinDoor = 1;
	IdxGate = 2;
	IdxSideGate = 3;

	// ------------------------------------------------------------------ pads
	const FRole PadRoles[6] = {
		{ TEXT("OldPad"),      TEXT("the old door's pad") },
		{ TEXT("QuietPad"),    TEXT("the quiet door's pad") },
		{ TEXT("GateNearPad"), TEXT("the arch gate's near pad") },
		{ TEXT("GateFarPad"),  TEXT("the arch gate's far pad") },
		{ TEXT("SideNearPad"), TEXT("the second gate's near pad") },
		{ TEXT("SideFarPad"),  TEXT("the second gate's far pad") },
	};
	for (int32 i = 0; i < 6; ++i)
	{
		TWeakObjectPtr<AActor> A;
		if (!ResolveOne(PadRoles[i].Tag, A)) { return false; }
		FPad P;
		P.Actor = A;
		P.Label = PadRoles[i].Label;
		P.Centre = A->GetActorLocation();
		bool bR = false, bB = false, bAns = false;
		P.Radius = ReadFloat(A.Get(), TEXT("ContactRadiusUu"), bR);
		P.Band = ReadFloat(A.Get(), TEXT("GroundedBandUu"), bB);
		P.Answers = ReadActor(A.Get(), TEXT("AnsweredBarrier"), bAns);
		if (!bR || !bB || !bAns || P.Radius <= 1.0 || P.Band <= 1.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose a readable "
					 "ContactRadiusUu, GroundedBandUu and AnsweredBarrier"),
				PadRoles[i].Label));
			return false;
		}
		P.StagedCentre = P.Centre;
		P.StagedRadius = P.Radius;
		P.StagedBand = P.Band;
		P.StagedAnswers = P.Answers;
		Pads.Add(P);
	}
	IdxOldPad = 0;
	IdxTwinPad = 1;
	IdxNearPad = 2;
	IdxFarPad = 3;
	IdxSideNearPad = 4;
	IdxSideFarPad = 5;

	// THE TWO GATES SHARE THE FLOOR. Each gate's pads are painted over the other's,
	// so both see exactly the same crates at exactly the same moments and the only
	// thing that can make them disagree is what each one is cut for. If the two
	// patches drifted apart the whole disagreement would be a geometry accident.
	{
		const int32 TwinA[2] = { IdxNearPad, IdxFarPad };
		const int32 TwinB[2] = { IdxSideNearPad, IdxSideFarPad };
		for (int32 t = 0; t < 2; ++t)
		{
			const FPad& PA = Pads[TwinA[t]];
			const FPad& PB = Pads[TwinB[t]];
			const double Off = FVector::Dist2D(PA.Centre, PB.Centre);
			if (Off > kPinPosUu
				|| !FMath::IsNearlyEqual(PA.Radius, PB.Radius, 0.01)
				|| !FMath::IsNearlyEqual(PA.Band, PB.Band, 0.01))
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: %s and %s are meant to be painted on "
						 "one patch of floor and they stand %.1f uu apart, or do not "
						 "match on reach and band"),
					*PA.Label, *PB.Label, Off));
				return false;
			}
		}
	}

	// ---------------------------------------------------------------- crates
	const FRole CrateRoles[3] = {
		{ TEXT("NearRailCrate"),    TEXT("the near-rail crate") },
		{ TEXT("FarRailEastCrate"), TEXT("the east far-rail crate") },
		{ TEXT("FarRailWestCrate"), TEXT("the west far-rail crate") },
	};
	for (int32 i = 0; i < 3; ++i)
	{
		TWeakObjectPtr<AActor> A;
		if (!ResolveOne(CrateRoles[i].Tag, A)) { return false; }
		FCrate C;
		C.Actor = A;
		C.Label = CrateRoles[i].Label;
		bool bN = false, bL = false, bS = false;
		C.CrateName = ReadName(A.Get(), TEXT("CrateName"), bN);
		C.RailLen = ReadFloat(A.Get(), TEXT("RailLengthUu"), bL);
		C.ShoveSpeed = ReadFloat(A.Get(), TEXT("ShoveSpeedUu"), bS);
		if (!bN || !bL || !bS || C.CrateName.IsNone() || C.RailLen <= 100.0
			|| C.ShoveSpeed <= 10.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose a readable CrateName, "
					 "RailLengthUu and ShoveSpeedUu"), CrateRoles[i].Label));
			return false;
		}
		// THE RAIL IS RE-DERIVED HERE, exactly as the crate's own BeginPlay derives
		// it (this pose, this forward line), never read back through the crate's
		// accessors, which live in the agent's writable module.
		C.Anchor = A->GetActorLocation();
		C.Axis = A->GetActorForwardVector().GetSafeNormal2D();
		if (C.Axis.IsNearlyZero())
		{
			C.Axis = FVector::ForwardVector;
		}
		C.Side = FVector::CrossProduct(FVector::UpVector, C.Axis).GetSafeNormal2D();
		C.StagedName = C.CrateName;
		C.StagedRailLen = C.RailLen;
		C.StagedShoveSpeed = C.ShoveSpeed;
		Crates.Add(C);
	}
	IdxCrateNear = 0;
	IdxCrateFarEast = 1;
	IdxCrateFarWest = 2;

	for (int32 i = 0; i < 3; ++i)
	{
		for (int32 j = i + 1; j < 3; ++j)
		{
			if (Crates[i].CrateName == Crates[j].CrateName)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: two crates both carry the name %s, so "
						 "no gate could ever tell them apart"),
					*Crates[i].CrateName.ToString()));
				return false;
			}
		}
	}

	// ----------------------------------------------------------------- lamps
	TArray<AActor*> LampActors;
	if (!ResolveTagged(TEXT("GateLamp"), 4, LampActors)) { return false; }
	for (AActor* const A : LampActors)
	{
		FLamp L;
		L.Actor = A;
		L.Light = ResolveLight(A);
		bool bS = false, bB = false;
		L.Slot = ReadInt(A, TEXT("NameSlot"), bS);
		L.Barrier = ReadActor(A, TEXT("LampBarrier"), bB);
		if (!L.Light.IsValid() || !bS || !bB)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a lamp carries no light component, or "
					 "does not expose NameSlot and LampBarrier readably"));
			return false;
		}
		// A LAMP STANDS FOR A SLOT ON ITS OWN GATE. Which gate is resolved once, here,
		// and pinned for the run: the two gates' slot-0 lamps mean different names at
		// the same instant, so a lamp read as "slot 0 in the yard" is meaningless.
		for (int32 b = 0; b < Barriers.Num(); ++b)
		{
			if (Barriers[b].Actor.Get() == L.Barrier.Get())
			{
				L.GateIndex = b;
				break;
			}
		}
		if (L.GateIndex != IdxGate && L.GateIndex != IdxSideGate)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a lamp is bolted to something that is not "
					 "one of the two gates"));
			return false;
		}
		L.Label = FString::Printf(TEXT("%s lamp %d"),
			*Barriers[L.GateIndex].Label, L.Slot);
		L.StagedSlot = L.Slot;
		L.StagedBarrier = L.Barrier;
		Lamps.Add(L);
	}
	Lamps.Sort([](const FLamp& A, const FLamp& B)
	{
		return A.GateIndex != B.GateIndex ? A.GateIndex < B.GateIndex
										  : A.Slot < B.Slot;
	});
	{
		// EXACTLY ONE SLOT-0 AND ONE SLOT-1 PER GATE. Anything else and the lamp
		// channel would be scoring a yard that cannot report what it is asked to.
		int32 Seen[2][2] = { { 0, 0 }, { 0, 0 } };
		for (const FLamp& L : Lamps)
		{
			if (L.Slot != 0 && L.Slot != 1)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: a lamp stands for slot %d, and a gate "
						 "is cut for exactly two names"), L.Slot));
				return false;
			}
			++Seen[L.GateIndex == IdxGate ? 0 : 1][L.Slot];
		}
		if (Lamps.Num() != 4 || Seen[0][0] != 1 || Seen[0][1] != 1
			|| Seen[1][0] != 1 || Seen[1][1] != 1)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: each of the two gates must carry exactly "
					 "one lamp for slot 0 and one for slot 1"));
			return false;
		}
	}

	// ------------------------------------------------------- the wiring itself
	if (Pads[IdxOldPad].Answers.Get() != Barriers[IdxOldDoor].Actor.Get()
		|| Pads[IdxTwinPad].Answers.Get() != Barriers[IdxTwinDoor].Actor.Get()
		|| Pads[IdxNearPad].Answers.Get() != Barriers[IdxGate].Actor.Get()
		|| Pads[IdxFarPad].Answers.Get() != Barriers[IdxGate].Actor.Get()
		|| Pads[IdxSideNearPad].Answers.Get() != Barriers[IdxSideGate].Actor.Get()
		|| Pads[IdxSideFarPad].Answers.Get() != Barriers[IdxSideGate].Actor.Get())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the six pads do not answer for the four "
				 "barriers the way the yard is laid out"));
		return false;
	}

	// BOTH DOORS MUST SHIP CUT FOR NOTHING. A barrier that is cut for a pair is what
	// takes the new branch; if the level shipped a door already carrying names, the
	// preservation gate would be measuring the wrong thing from frame one.
	const int32 DoorIdxs[2] = { IdxOldDoor, IdxTwinDoor };
	for (int32 d = 0; d < 2; ++d)
	{
		const int32 DoorIdx = DoorIdxs[d];
		bool bD1 = false, bD2 = false;
		const FName F = ReadName(Barriers[DoorIdx].Actor.Get(),
			TEXT("CutForFirstName"), bD1);
		const FName S2 = ReadName(Barriers[DoorIdx].Actor.Get(),
			TEXT("CutForSecondName"), bD2);
		if (!bD1 || !bD2 || !F.IsNone() || !S2.IsNone())
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s ships cut for (%s, %s) and both doors "
					 "must be cut for nothing"), *Barriers[DoorIdx].Label,
				*F.ToString(), *S2.ToString()));
			return false;
		}
	}

	// The twin has to be a MATCHED instance or it is not a control.
	if (!FMath::IsNearlyEqual(Barriers[IdxOldDoor].StagedOpenAngleDeg,
			Barriers[IdxTwinDoor].StagedOpenAngleDeg, 0.01)
		|| !FMath::IsNearlyEqual(Barriers[IdxOldDoor].StagedTravelRate,
			Barriers[IdxTwinDoor].StagedTravelRate, 0.01)
		|| !FMath::IsNearlyEqual(Pads[IdxOldPad].Radius, Pads[IdxTwinPad].Radius, 0.01)
		|| !FMath::IsNearlyEqual(Pads[IdxOldPad].Band, Pads[IdxTwinPad].Band, 0.01))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the twin door and its pad are not matched to "
				 "the old door and its pad on every staged number"));
		return false;
	}

	// Every barrier's travel must clear the disclosed band with real margin, or the
	// band would be a race against the supplied animation rather than a contract on
	// the submission's own decision latency.
	for (const FBarrier& B : Barriers)
	{
		if (B.StagedOpenAngleDeg < kOpenDeg + 5.0
			|| B.StagedTravelRate * (kBandS / kBandMarginX) < kOpenDeg)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s opens to %.0f deg at %.0f deg per "
					 "second, which cannot clear %.0f deg inside the %.2f s band with "
					 "%.0fx margin"), *B.Label, B.StagedOpenAngleDeg, B.StagedTravelRate,
				kOpenDeg, kBandS, kBandMarginX));
			return false;
		}
	}

	// ---------------------------------------------------- crates against pads
	struct FParking { int32 Crate; int32 Pad; };
	const FParking Parkings[6] = {
		{ IdxCrateNear, IdxNearPad },
		{ IdxCrateFarEast, IdxFarPad },
		{ IdxCrateFarWest, IdxFarPad },
		{ IdxCrateNear, IdxSideNearPad },
		{ IdxCrateFarEast, IdxSideFarPad },
		{ IdxCrateFarWest, IdxSideFarPad },
	};
	for (const FParking& Park : Parkings)
	{
		const FCrate& C = Crates[Park.Crate];
		const FPad& P = Pads[Park.Pad];
		const FVector Home = C.Anchor + C.Axis * C.RailLen;
		const double HomeOff = FVector::Dist2D(Home, P.Centre);
		const double AwayOff = FVector::Dist2D(C.Anchor, P.Centre);
		if (HomeOff > kParkNearUu || HomeOff * kDeepFactor > P.Radius)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s parks %.0f uu from %s, which is not "
					 "deep inside that pad's %.0f uu radius"),
				*C.Label, HomeOff, *P.Label, P.Radius));
			return false;
		}
		if (AwayOff < P.Radius * kDeepFactor)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s rests only %.0f uu from %s at its other "
					 "stop, which is not far outside that pad's %.0f uu radius"),
				*C.Label, AwayOff, *P.Label, P.Radius));
			return false;
		}
	}

	// THE TWO CONTESTED RAILS MUST OPPOSE. Parking one crate on the far pad has to
	// physically exclude the other, or the identity axis of the task is something no
	// human could play.
	const double Dot = FVector::DotProduct(
		Crates[IdxCrateFarEast].Axis, Crates[IdxCrateFarWest].Axis);
	if (Dot > kOpposedDot)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the two rails feeding the contested pad have "
				 "an axis dot product of %.2f, so they do not approach it from "
				 "opposite sides and both crates could be home at once"), Dot));
		return false;
	}

	// ------------------------------------------------------------- the pawn
	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the yard has no possessed player character"));
		return false;
	}
	const USkeletalMeshComponent* const Mesh = Hero->GetMesh();
	if (Mesh == nullptr || Mesh->GetSkeletalMeshAsset() == nullptr
		|| !Mesh->IsVisible() || Mesh->GetComponentScale().IsNearlyZero())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the player character has no visible mesh, so "
				 "a human watching the replay would see nothing"));
		return false;
	}
	// THE LEVEL MUST BE PLAYABLE BY HAND. A map that grades byte-identically while
	// being uncontrollable is the LEVEL's fault, never the submission's, so this is
	// attributed and not scored.
	const FString Broken = DescribeBrokenPlayerInput(World);
	if (!Broken.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: this level cannot be driven by hand: %s"),
			*Broken));
		return false;
	}
	WalkZ = Hero->GetActorLocation().Z;
	if (const UCharacterMovementComponent* const Move = Hero->GetCharacterMovement())
	{
		HeroSpeed = FMath::Max(static_cast<double>(Move->GetMaxSpeed()), 100.0);
	}
	return true;
}

// ---------------------------------------------------------------------------
// The routed ring, and the drive built on it.
//
// EVERY TRANSIT IS ROUTED, never a straight line. Measured on this yard: the straight
// line from the old door's pad to the near crate's shove station passes 24 uu from
// that crate and shoves it before the drive ever means to. So the drive travels a
// rectangle that sits OUTSIDE both rail groups, hops perpendicular onto a station, and
// hops back off. Every clearance below is measured off the placed actors.
// ---------------------------------------------------------------------------

double AOldDoorYardFunctionalTest::LaneX(int32 Lane) const
{
	return Lane == 1 ? LaneFarX : LaneNearX;
}

int32 AOldDoorYardFunctionalTest::LaneOf(const FVector& P) const
{
	return FMath::Abs(P.X - LaneNearX) <= FMath::Abs(P.X - LaneFarX) ? 0 : 1;
}

double AOldDoorYardFunctionalTest::RailParam(const FCrate& C) const
{
	if (!C.Actor.IsValid())
	{
		return 0.0;
	}
	return FVector::DotProduct(C.Actor->GetActorLocation() - C.Anchor, C.Axis);
}

FVector AOldDoorYardFunctionalTest::PushStation(int32 CrateIndex, double Dir) const
{
	const FCrate& C = Crates[CrateIndex];
	const FVector At = Dir > 0.0
		? C.Anchor - C.Axis * kPushStandUu
		: C.Anchor + C.Axis * (C.RailLen + kPushStandUu);
	return FVector(At.X, At.Y, WalkZ);
}

TArray<FVector> AOldDoorYardFunctionalTest::RouteTo(const FVector& Target,
	int32 Lane) const
{
	TArray<FVector> Out;
	if (!Hero.IsValid() || Lane == INDEX_NONE)
	{
		return Out;
	}
	const FVector Here = Hero->GetActorLocation();
	const double FromX = LaneX(LaneOf(Here));
	const double ToX = LaneX(Lane);

	// 1. Hop perpendicular onto whichever lane this end of the walk hangs off. The
	//    hop is across open floor by construction: the lanes sit outside both rail
	//    groups and every station sits on a rail.
	Out.Add(FVector(FromX, Here.Y, WalkZ));

	// 2. If the two ends hang off different lanes, cross at whichever end of the
	//    ring is the shorter way round.
	if (!FMath::IsNearlyEqual(FromX, ToX, 1.0))
	{
		const double CostNorth =
			FMath::Abs(Here.Y - CrossNorthY) + FMath::Abs(CrossNorthY - Target.Y);
		const double CostSouth =
			FMath::Abs(Here.Y - CrossSouthY) + FMath::Abs(CrossSouthY - Target.Y);
		const double CrossY = CostNorth <= CostSouth ? CrossNorthY : CrossSouthY;
		Out.Add(FVector(FromX, CrossY, WalkZ));
		Out.Add(FVector(ToX, CrossY, WalkZ));
	}

	// 3. Travel the target's lane, then hop off it onto the target.
	Out.Add(FVector(ToX, Target.Y, WalkZ));
	Out.Add(FVector(Target.X, Target.Y, WalkZ));
	return Out;
}

bool AOldDoorYardFunctionalTest::PairIsOpenable(FName First, FName Second) const
{
	if (First.IsNone() || Second.IsNone() || First == Second)
	{
		return false;
	}
	bool bFirstIsACrate = false;
	bool bSecondIsACrate = false;
	for (const FCrate& C : Crates)
	{
		bFirstIsACrate = bFirstIsACrate || C.CrateName == First;
		bSecondIsACrate = bSecondIsACrate || C.CrateName == Second;
	}
	// THE UNWINNABILITY TRAP. The two far-rail crates contest a single pad and can
	// never be home at the same time, so a pair naming both of them is unopenable by
	// LAYOUT rather than by anything a submission did. Any pair the drive later
	// requires the gate to OPEN under must therefore name the near-pad crate.
	const FName Near = Crates[IdxCrateNear].CrateName;
	return bFirstIsACrate && bSecondIsACrate && (First == Near || Second == Near);
}

void AOldDoorYardFunctionalTest::ApplyRecut(int32 Which, double Now)
{
	// BOTH GATES ARE RE-CUT TOGETHER, TO DIFFERENT PAIRS, AND NOTHING ANNOUNCES IT.
	// The sequences are chosen so the two gates disagree at almost every judged
	// dwell -- and so that at re-cut #2, with no actor in the yard moving, the arch
	// gate's new pair cannot be satisfied by this layout and it must come DOWN while
	// the second gate's new pair is already standing on the pads and it must come UP.
	const int32 W = FMath::Clamp(Which, 0, 2);
	const int32 ArchPairs[3][2] = {
		{ IdxCrateNear,    IdxCrateFarEast },  // #0, written before the first judged frame
		{ IdxCrateFarWest, IdxCrateNear    },  // #1, with both pads empty
		{ IdxCrateFarWest, IdxCrateFarEast },  // #2, unopenable BY LAYOUT, on purpose
	};
	const int32 SidePairs[3][2] = {
		{ IdxCrateFarWest, IdxCrateNear    },  // #0
		{ IdxCrateNear,    IdxCrateFarEast },  // #1
		{ IdxCrateFarWest, IdxCrateNear    },  // #2, satisfied the instant it is written
	};
	const int32 GateIdx[2] = { IdxGate, IdxSideGate };
	for (int32 g = 0; g < 2; ++g)
	{
		const int32* const Pair = (g == 0) ? ArchPairs[W] : SidePairs[W];
		FBarrier& B = Barriers[GateIdx[g]];
		B.ExpectFirst = Crates[Pair[0]].CrateName;
		B.ExpectSecond = Crates[Pair[1]].CrateName;
		WriteName(B.Actor.Get(), TEXT("CutForFirstName"), B.ExpectFirst);
		WriteName(B.Actor.Get(), TEXT("CutForSecondName"), B.ExpectSecond);
	}
	StagingUntil = Now + kRecutBlindS;
	++RecutsApplied;
	UE_LOG(LogTemp, Display,
		TEXT("[t3-olddooryard] re-cut #%d at t=%.2f: the arch gate is now cut for "
			 "(%s, %s) and the second gate for (%s, %s)"), Which, Now,
		*Barriers[IdxGate].ExpectFirst.ToString(),
		*Barriers[IdxGate].ExpectSecond.ToString(),
		*Barriers[IdxSideGate].ExpectFirst.ToString(),
		*Barriers[IdxSideGate].ExpectSecond.ToString());
}

bool AOldDoorYardFunctionalTest::StageDrive()
{
	// ------------------------------------------------------------- the lanes
	// The whole ring assumes the three rails run along one bearing and that the near
	// rail and the two contested rails are separated across it. Both are MEASURED.
	for (const FCrate& C : Crates)
	{
		if (FMath::Abs(C.Axis.X) > 0.05)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s runs on a rail this drive cannot route "
					 "around (its bearing is %.2f, %.2f)"),
				*C.Label, C.Axis.X, C.Axis.Y));
			return false;
		}
	}
	const double NearRailX = Crates[IdxCrateNear].Anchor.X;
	const double FarRailX = Crates[IdxCrateFarEast].Anchor.X;
	if (FMath::Abs(Crates[IdxCrateFarWest].Anchor.X - FarRailX) > 5.0
		|| FMath::Abs(NearRailX - FarRailX) < 2.0 * kLaneClearUu)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the near rail sits at %.0f and the two "
				 "contested rails at %.0f and %.0f, which this drive cannot walk "
				 "between"), NearRailX, FarRailX, Crates[IdxCrateFarWest].Anchor.X));
		return false;
	}
	const double Sign = NearRailX > FarRailX ? 1.0 : -1.0;
	LaneNearX = NearRailX + Sign * kLaneClearUu;
	LaneFarX = FarRailX - Sign * kLaneClearUu;

	// The ring's two ends: clear of every rail extent and every shove station.
	double YMax = -TNumericLimits<double>::Max();
	double YMin = TNumericLimits<double>::Max();
	for (int32 i = 0; i < Crates.Num(); ++i)
	{
		const FCrate& C = Crates[i];
		const double Ys[4] = {
			C.Anchor.Y, (C.Anchor + C.Axis * C.RailLen).Y,
			PushStation(i, 1.0).Y, PushStation(i, -1.0).Y };
		for (const double Y : Ys)
		{
			YMax = FMath::Max(YMax, Y);
			YMin = FMath::Min(YMin, Y);
		}
	}
	CrossNorthY = Pads[IdxOldPad].Centre.Y;
	CrossSouthY = YMin - kLaneClearUu;
	if (CrossNorthY < YMax + kLaneClearUu)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the crossing at the old door's end of the "
				 "yard sits at %.0f, only %.0f uu clear of the nearest rail work"),
			CrossNorthY, CrossNorthY - YMax));
		return false;
	}
	// The far crossing has to clear BOTH gates' own swing, not just their frames.
	const int32 SwingIdxs[2] = { IdxGate, IdxSideGate };
	for (int32 g = 0; g < 2; ++g)
	{
		const int32 GIdx = SwingIdxs[g];
		if (CrossSouthY > Barriers[GIdx].StagedLoc.Y - 600.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the far crossing at %.0f does not clear "
					 "%s at %.0f by enough for its panel to swing"),
				CrossSouthY, *Barriers[GIdx].Label, Barriers[GIdx].StagedLoc.Y));
			return false;
		}
	}
	// Neither lane may run through a barrier's frame.
	for (const FBarrier& B : Barriers)
	{
		if (FMath::Abs(LaneNearX - B.StagedLoc.X) < 340.0
			|| FMath::Abs(LaneFarX - B.StagedLoc.X) < 340.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a walking lane passes through the frame "
					 "of %s"), *B.Label));
			return false;
		}
	}
	// AND THE DRIVE NEVER GOES NEAR THE CONTROL. The twin door and its pad are the
	// in-scene negative control; a route that brushed them would make the control
	// prove nothing.
	{
		TArray<FVector> Extremes;
		Extremes.Add(FVector(LaneNearX, CrossNorthY, WalkZ));
		Extremes.Add(FVector(LaneNearX, CrossSouthY, WalkZ));
		Extremes.Add(FVector(LaneFarX, CrossNorthY, WalkZ));
		Extremes.Add(FVector(LaneFarX, CrossSouthY, WalkZ));
		Extremes.Add(Pads[IdxOldPad].Centre);
		Extremes.Add(Pads[IdxNearPad].Centre);
		for (int32 i = 0; i < Crates.Num(); ++i)
		{
			Extremes.Add(PushStation(i, 1.0));
			Extremes.Add(PushStation(i, -1.0));
			Extremes.Add(Crates[i].Anchor);
			Extremes.Add(Crates[i].Anchor + Crates[i].Axis * Crates[i].RailLen);
		}
		for (const FVector& P : Extremes)
		{
			const double D = FMath::Min(
				FVector::Dist2D(P, Pads[IdxTwinPad].Centre),
				FVector::Dist2D(P, Barriers[IdxTwinDoor].StagedLoc));
			if (D < kTwinKeepUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: the drive passes within %.0f uu of the "
						 "untouched twin pair, which must stay at least %.0f uu away"),
					D, kTwinKeepUu));
				return false;
			}
		}
	}

	// ------------------------------------------------------------- the steps
	const int32 A = IdxCrateNear;      // parks on the near pad
	const int32 B = IdxCrateFarEast;   // contests the far pad from one side
	const int32 C = IdxCrateFarWest;   // and from the other
	const int32 LaneA = 0;
	const int32 LaneF = 1;

	auto Go = [this](int32 Phase, int32 Armed, const FVector& Target, int32 Lane,
		double Arrive, double Hold, bool bStay, const TCHAR* What)
	{
		FStep S;
		S.Kind = EStep::Go;
		S.Phase = Phase;
		S.ArmedGate = Armed;
		S.Target = Target;
		S.Lane = Lane;
		S.ArriveUu = Arrive;
		S.Hold = Hold;
		S.bStayOnTarget = bStay;
		S.What = What;
		Steps.Add(S);
	};
	auto Push = [this](int32 Phase, int32 Armed, int32 Crate, double Dir,
		const TCHAR* What)
	{
		FStep S;
		S.Kind = EStep::Push;
		S.Phase = Phase;
		S.ArmedGate = Armed;
		S.Crate = Crate;
		S.Dir = Dir;
		S.What = What;
		Steps.Add(S);
	};
	auto Retreat = [this](int32 Phase, int32 Armed, int32 Crate, double Hold,
		const TCHAR* What)
	{
		FStep S;
		S.Kind = EStep::Retreat;
		S.Phase = Phase;
		S.ArmedGate = Armed;
		S.Crate = Crate;
		S.Hold = Hold;
		S.What = What;
		Steps.Add(S);
	};
	auto Stand = [this](int32 Phase, int32 Armed, double Hold, const TCHAR* What)
	{
		FStep S;
		S.Kind = EStep::Stand;
		S.Phase = Phase;
		S.ArmedGate = Armed;
		S.Hold = Hold;
		S.What = What;
		Steps.Add(S);
	};
	auto Recut = [this](int32 Phase, int32 Which, const TCHAR* What)
	{
		FStep S;
		S.Kind = EStep::Recut;
		S.Phase = Phase;
		S.ArmedGate = ARM_NONE;
		S.Recut = Which;
		S.What = What;
		Steps.Add(S);
	};

	const FVector OldPadAt = Pads[IdxOldPad].Centre;
	const FVector NearPadAt = Pads[IdxNearPad].Centre;
	const FVector OldPadOff = FVector(LaneNearX, OldPadAt.Y, WalkZ);

	// One whole shove, start to finish: walk to the station, shove until the crate is
	// at its stop, then RETREAT to the lane before anything is judged. The retreat is
	// not tidiness: while shoving, the character presses up against the crate and its
	// own body centre sits about 102 uu from a pad centre whose radius is 100, and no
	// dwell may ever be judged from there.
	auto Shove = [&](int32 Phase, int32 Armed, int32 Crate, double Dir, double Hold,
		const TCHAR* WhatWalk, const TCHAR* WhatPush, const TCHAR* WhatDwell)
	{
		Go(Phase, Armed, PushStation(Crate, Dir), Crate == A ? LaneA : LaneF,
			kWaypointUu, 0.0, false, WhatWalk);
		Push(Phase, Armed, Crate, Dir, WhatPush);
		Retreat(Phase, Armed, Crate, Hold, WhatDwell);
	};

	// -- phase 0: arrival. No gate is armed: the character may spawn anywhere.
	Go(0, ARM_NONE, OldPadOff, LaneA, kWaypointUu, 0.0, false,
		TEXT("walk to the old door's end of the yard"));

	// -- phases 1 and 2: the two BASELINE old-door cycles, before the character has
	//    touched a crate. Everything the preservation gate later reports is reported
	//    against these two, measured in the same run.
	for (int32 Cycle = 1; Cycle <= 2; ++Cycle)
	{
		Go(Cycle, ARM_NONE, OldPadAt, LaneA, kPadArriveUu, kDwellS, true,
			TEXT("stand on the old door's pad"));
		Go(Cycle, ARM_NONE, OldPadOff, LaneA, kWaypointUu, kDwellS, false,
			TEXT("step off the old door's pad"));
	}

	// -- phase 3: the near crate home. Gate SHUT, lamp 0 lit, lamp 1 dark.
	//    THE EMPTY SUBMISSION DIES HERE, on a wrong-OPEN.
	Shove(3, ARM_SHUT, A, 1.0, kDwellS,
		TEXT("walk to the near crate"),
		TEXT("shove the near crate home"),
		TEXT("one crate home and the gate must stay shut"));

	// -- phase 4: both home. Gate OPEN, both lamps lit.
	Shove(4, ARM_OPEN, B, 1.0, kDwellS,
		TEXT("walk round to the east far rail"),
		TEXT("shove the east far crate home"),
		TEXT("both crates home and the gate must be open"));

	// -- phase 5: the far crate leaves (the gate must shut), then the crate the gate
	//    is NOT cut for takes the contested pad (it must stay shut).
	Shove(5, ARM_LEAVE, B, -1.0, kDwellS,
		TEXT("walk round behind the east far crate"),
		TEXT("shove the east far crate off"),
		TEXT("the far crate has left and the gate must shut"));
	Shove(5, ARM_SHUT, C, 1.0, kDwellS,
		TEXT("walk round to the west far rail"),
		TEXT("shove the west far crate home"),
		TEXT("a crate the gate is not cut for holds the contested pad"));

	// -- phase 6: the far crate comes back.
	Shove(6, ARM_SHUT, C, -1.0, kDwellS,
		TEXT("walk round behind the west far crate"),
		TEXT("shove the west far crate off"),
		TEXT("the contested pad is empty again"));
	Shove(6, ARM_LEAVE, B, 1.0, kDwellS,
		TEXT("walk back round to the east far rail"),
		TEXT("shove the east far crate home again"),
		TEXT("the far crate is back and the gate must open again"));

	// -- phase 7: the near crate leaves, then a PERSON stands squarely on the pad it
	//    left. A person is not a crate and never counts toward anything.
	Shove(7, ARM_LEAVE, A, -1.0, kDwellS,
		TEXT("walk round behind the near crate"),
		TEXT("shove the near crate off"),
		TEXT("the near crate has left and the gate must shut again"));
	Go(7, ARM_RUNNER, NearPadAt, LaneA, kPadArriveUu, kDwellS, true,
		TEXT("stand squarely on the empty near pad"));

	// -- phase 8: the near crate comes back.
	Shove(8, ARM_LEAVE, A, 1.0, kDwellS,
		TEXT("step off and walk to the near crate"),
		TEXT("shove the near crate home again"),
		TEXT("the near crate is back and the gate must open again"));

	// -- phase 9: old-door cycle 3, AFTER the gate has been opened, re-shut and
	//    re-opened. The narrowing-the-shared-question answer dies here.
	Go(9, ARM_NONE, OldPadAt, LaneA, kPadArriveUu, kDwellS, true,
		TEXT("walk back east and stand on the old door's pad"));
	Go(9, ARM_NONE, OldPadOff, LaneA, kWaypointUu, kDwellS, false,
		TEXT("step off the old door's pad again"));

	// -- phase 10: clear both gate pads.
	Shove(10, ARM_SHUT, B, -1.0, kDwellS,
		TEXT("walk back west behind the east far crate"),
		TEXT("shove the east far crate off"),
		TEXT("the contested pad is clear"));
	Shove(10, ARM_SHUT, A, -1.0, kDwellS,
		TEXT("walk round behind the near crate"),
		TEXT("shove the near crate off"),
		TEXT("both gate pads are empty and the gate must be shut"));

	// -- phase 11: RE-CUT #1, with both pads empty.
	Recut(11, 1, TEXT("the gate is re-cut with nothing on either pad"));
	Stand(11, ARM_SHUT, kDwellS, TEXT("the yard settles after the re-cut"));

	// -- phase 12: the east far crate is now cut for NOTHING. Both lamps dark.
	Shove(12, ARM_CUTNOW, B, 1.0, kDwellS,
		TEXT("walk to the east far rail"),
		TEXT("shove the east far crate home"),
		TEXT("a crate that is no longer named holds the contested pad"));

	// -- phase 13: the near crate is now the SECOND name. Lamp 1 lit, lamp 0 dark.
	Shove(13, ARM_CUTNOW, B, -1.0, kDwellS,
		TEXT("walk behind the east far crate"),
		TEXT("shove the east far crate off"),
		TEXT("the contested pad is empty before the swap"));
	Shove(13, ARM_CUTNOW, A, 1.0, kDwellS,
		TEXT("walk round to the near rail"),
		TEXT("shove the near crate home"),
		TEXT("the near crate now answers to the second name"));

	// -- phase 14: the west far crate is now the FIRST name. Gate open, both lit.
	Shove(14, ARM_CUTNOW, C, 1.0, kDwellS,
		TEXT("walk round to the west far rail"),
		TEXT("shove the west far crate home"),
		TEXT("the pair the gate is cut for is home the other way round"));

	// -- phase 15: the runner on the pad again, with the other crate home.
	Shove(15, ARM_LEAVE, A, -1.0, kDwellS,
		TEXT("walk behind the near crate"),
		TEXT("shove the near crate off"),
		TEXT("the gate shuts when the second name leaves"));
	Go(15, ARM_RUNNER, NearPadAt, LaneA, kPadArriveUu, kDwellS, true,
		TEXT("stand squarely on the empty near pad a second time"));

	// -- phase 16: and back.
	Shove(16, ARM_LEAVE, A, 1.0, kDwellS,
		TEXT("step off and walk to the near crate"),
		TEXT("shove the near crate home"),
		TEXT("the gate opens again when the second name comes back"));

	// -- phase 17: RE-CUT #2, WITH NOTHING MOVING. No actor changes position, no
	//    overlap begins or ends: only the writing on the gate. The gate must come
	//    down and one lamp must go dark.
	Recut(17, 2, TEXT("the gate is re-cut with nothing in the yard moving"));
	Stand(17, ARM_CUTNOW, kDwellS,
		TEXT("the gate must come down with nothing having moved"));

	// -- phase 18: old-door cycle 4, after every re-cut.
	Go(18, ARM_NONE, OldPadAt, LaneA, kPadArriveUu, kDwellS, true,
		TEXT("walk east one last time and stand on the old door's pad"));
	Go(18, ARM_NONE, OldPadOff, LaneA, kWaypointUu, kDwellS, false,
		TEXT("step off the old door's pad one last time"));

	// -- phase 19: the run-level gate.
	{
		FStep S;
		S.Kind = EStep::Finish;
		S.Phase = 19;
		S.ArmedGate = ARM_NONE;
		S.What = TEXT("the run-level gate");
		Steps.Add(S);
	}
	return true;
}

// ---------------------------------------------------------------------------
// PrepareTest. RE-CUT #0 happens here, and it is the whole reason a hard-coded or
// BeginPlay-cached answer is wrong from the FIRST judged frame: PIE fires BeginPlay on
// every placed actor BEFORE this runs, so the pair a submission could read ahead of
// time (in the editor, in the level, or in its own BeginPlay) is not the pair the run
// grades.
// ---------------------------------------------------------------------------

void AOldDoorYardFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (!ResolveYard())
	{
		return;
	}

	FName LevelPair[2][2];
	const int32 GateIdx[2] = { IdxGate, IdxSideGate };
	for (int32 g = 0; g < 2; ++g)
	{
		AActor* const G = Barriers[GateIdx[g]].Actor.Get();
		bool bF = false, bS = false;
		LevelPair[g][0] = ReadName(G, TEXT("CutForFirstName"), bF);
		LevelPair[g][1] = ReadName(G, TEXT("CutForSecondName"), bS);
		if (!bF || !bS)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: %s does not expose CutForFirstName and "
					 "CutForSecondName readably, so nothing can re-cut it"),
				*Barriers[GateIdx[g]].Label));
			return;
		}
		// A LEVEL PAIR MUST ITSELF BE PLAYABLE BY HAND. The owner plays the reference
		// before this ships, and a gate nobody can open is not a yard.
		if (!PairIsOpenable(LevelPair[g][0], LevelPair[g][1]))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the level was saved with %s cut for "
					 "(%s, %s), which nobody could open by hand"),
				*Barriers[GateIdx[g]].Label, *LevelPair[g][0].ToString(),
				*LevelPair[g][1].ToString()));
			return;
		}
	}
	// The two gates must not ship cut for the SAME pair either, or the level would
	// show a submission a yard in which one answer happens to serve both.
	if (LevelPair[0][0] == LevelPair[1][0] && LevelPair[0][1] == LevelPair[1][1])
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: both gates are saved cut for the same pair"));
		return;
	}

	const double Now = GetWorld() != nullptr
		? static_cast<double>(GetWorld()->GetTimeSeconds()) : 0.0;
	ApplyRecut(0, Now);

	// NEITHER LEVEL PAIR MAY BE THE PAIR ITS OWN GATE IS GRADED AGAINST. If one were,
	// an answer that read that pair once and cached it would survive most of the run
	// and nothing would fail to say so: the task would quietly get easier, with a
	// green reference and no signal at all.
	for (int32 g = 0; g < 2; ++g)
	{
		const FBarrier& B = Barriers[GateIdx[g]];
		if (LevelPair[g][0] == B.ExpectFirst && LevelPair[g][1] == B.ExpectSecond)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the level saves %s holding the same pair "
					 "(%s, %s) that this test writes before the first judged frame, "
					 "so a hard-coded answer would not be wrong from the start"),
				*B.Label, *LevelPair[g][0].ToString(), *LevelPair[g][1].ToString()));
			return;
		}
	}
	// AND THE TWO GATES MUST BE CUT FOR DIFFERENT PAIRS from the first judged frame
	// on, or the second gate proves nothing.
	if (Barriers[IdxGate].ExpectFirst == Barriers[IdxSideGate].ExpectFirst
		&& Barriers[IdxGate].ExpectSecond == Barriers[IdxSideGate].ExpectSecond)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: re-cut #0 leaves both gates cut for the same "
				 "pair, so nothing in the run could tell one from the other"));
		return;
	}
	// EVERY PAIR THE DRIVE LATER REQUIRES A GATE TO OPEN UNDER HAS TO BE OPENABLE.
	// The arch gate's re-cut #2 is the deliberate exception and is checked nowhere:
	// it names the two contested crates on purpose, which is exactly why it must come
	// down with nothing in the yard moving while the second gate goes up.
	if (!PairIsOpenable(Crates[IdxCrateNear].CrateName,
			Crates[IdxCrateFarEast].CrateName)
		|| !PairIsOpenable(Crates[IdxCrateFarWest].CrateName,
			Crates[IdxCrateNear].CrateName))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: a pair the drive requires a gate to open "
				 "under does not name the near-pad crate, which makes it unopenable "
				 "by layout and the task unwinnable"));
		return;
	}

	if (!StageDrive())
	{
		return;
	}

	// The graded instants are every frame; the schedule is calibration plus a
	// SENTINEL far past the ~215 s the drive models. ACraftBenchFunctionalTest::Tick
	// ends the test the moment the LAST scheduled checkpoint is sampled, so without
	// an entry beyond the drive the run would declare success before the last phase.
	TArray<double> Schedule;
	for (int32 i = 1; i <= kCalibCount; ++i)
	{
		Schedule.Add(kCalibEveryS * i);
	}
	Schedule.Add(kSentinelS);
	TimeLimitMargin = 20.0f;
	SetCheckpointSchedule(Schedule);

	StepIndex = 0;
	RouteIndex = 0;
	bPrepared = true;
	BeginStep(Now);

	UE_LOG(LogTemp, Display,
		TEXT("[t3-olddooryard] staged: crates %s (near) %s (far east) %s (far west); "
			 "arch level pair (%s, %s) -> graded (%s, %s); second-gate level pair "
			 "(%s, %s) -> graded (%s, %s); lanes x=%.0f and x=%.0f; crossings y=%.0f "
			 "and y=%.0f; %d steps; hero speed %.0f"),
		*Crates[IdxCrateNear].CrateName.ToString(),
		*Crates[IdxCrateFarEast].CrateName.ToString(),
		*Crates[IdxCrateFarWest].CrateName.ToString(),
		*LevelPair[0][0].ToString(), *LevelPair[0][1].ToString(),
		*Barriers[IdxGate].ExpectFirst.ToString(),
		*Barriers[IdxGate].ExpectSecond.ToString(),
		*LevelPair[1][0].ToString(), *LevelPair[1][1].ToString(),
		*Barriers[IdxSideGate].ExpectFirst.ToString(),
		*Barriers[IdxSideGate].ExpectSecond.ToString(),
		LaneNearX, LaneFarX, CrossNorthY, CrossSouthY, Steps.Num(), HeroSpeed);
}

// ---------------------------------------------------------------------------
// The oracle. The fixture's own copy of the whole rule, from LIVE readings.
// ---------------------------------------------------------------------------

FName AOldDoorYardFunctionalTest::LiveCut(const FBarrier& B, int32 Slot) const
{
	// LIVE, off THAT barrier. The two gates carry different pairs at the same
	// instant, so there is no such thing as "the name in slot 0" for the yard.
	bool bOk = false;
	return ReadName(B.Actor.Get(),
		Slot == 0 ? TEXT("CutForFirstName") : TEXT("CutForSecondName"), bOk);
}

bool AOldDoorYardFunctionalTest::IsResting(const FPad& Pad, const AActor* Body) const
{
	if (Body == nullptr)
	{
		return false;
	}
	// Measured off the body's OWN SOLID SHAPE, so a name floating over a crate or a
	// number floating over a head plays no part. This is the predicate the prompt
	// discloses in full, re-implemented rather than called: AYardPadActor's copy of
	// it lives in the agent's writable module, and a submission that widened it would
	// otherwise move this model along with it.
	FVector Origin = FVector::ZeroVector;
	FVector Extent = FVector::ZeroVector;
	Body->GetActorBounds(/*bOnlyCollidingComponents=*/true, Origin, Extent);
	if (Extent.IsNearlyZero())
	{
		return false;
	}
	if (FVector::Dist2D(Origin, Pad.Centre) > Pad.Radius)
	{
		return false;
	}
	return FMath::Abs((Origin.Z - Extent.Z) - Pad.Centre.Z) <= Pad.Band;
}

bool AOldDoorYardFunctionalTest::AnyResting(const FPad& Pad) const
{
	// A person or a crate. The yard has never cared which, and that is the only
	// reason the old door works.
	if (Hero.IsValid() && IsResting(Pad, Hero.Get()))
	{
		return true;
	}
	for (const FCrate& C : Crates)
	{
		if (IsResting(Pad, C.Actor.Get()))
		{
			return true;
		}
	}
	return false;
}

bool AOldDoorYardFunctionalTest::NamedCrateHome(const FBarrier& B, FName Wanted) const
{
	if (Wanted.IsNone())
	{
		return false;
	}
	for (const FPad& P : Pads)
	{
		if (P.Answers.Get() != B.Actor.Get())
		{
			continue;
		}
		for (const FCrate& C : Crates)
		{
			if (C.CrateName == Wanted && IsResting(P, C.Actor.Get()))
			{
				return true;
			}
		}
	}
	return false;
}

bool AOldDoorYardFunctionalTest::ModelWants(const FBarrier& B) const
{
	bool bOk = false;
	const FName First = ReadName(B.Actor.Get(), TEXT("CutForFirstName"), bOk);
	const FName Second = ReadName(B.Actor.Get(), TEXT("CutForSecondName"), bOk);
	if (First.IsNone() && Second.IsNone())
	{
		// The rule that already runs, untouched: any single body on any pad that
		// answers for this barrier.
		for (const FPad& P : Pads)
		{
			if (P.Answers.Get() == B.Actor.Get() && AnyResting(P))
			{
				return true;
			}
		}
		return false;
	}
	// A barrier cut for a pair asks the same pads a different question.
	return NamedCrateHome(B, First) && NamedCrateHome(B, Second);
}

double AOldDoorYardFunctionalTest::PanelAngle(const FBarrier& B) const
{
	if (!B.Panel.IsValid())
	{
		return 0.0;
	}
	return FMath::Abs(FMath::FindDeltaAngleDegrees(
		B.ShutYaw, static_cast<double>(B.Panel->GetComponentRotation().Yaw)));
}

bool AOldDoorYardFunctionalTest::LampIsLit(const FLamp& L) const
{
	// Read off the lamp's OWN LIGHT, never off a flag: visible, and burning.
	const UPointLightComponent* const Light = L.Light.Get();
	return Light != nullptr && Light->IsVisible() && Light->Intensity > 0.0f;
}

FString AOldDoorYardFunctionalTest::HomeCrateList(const FBarrier& B) const
{
	TArray<FString> Parts;
	for (const FPad& P : Pads)
	{
		if (P.Answers.Get() != B.Actor.Get())
		{
			continue;
		}
		for (const FCrate& C : Crates)
		{
			if (IsResting(P, C.Actor.Get()))
			{
				Parts.Add(FString::Printf(TEXT("%s on %s"),
					*C.CrateName.ToString(), *P.Label));
			}
		}
	}
	if (Hero.IsValid())
	{
		for (const FPad& P : Pads)
		{
			if (P.Answers.Get() == B.Actor.Get() && IsResting(P, Hero.Get()))
			{
				Parts.Add(FString::Printf(TEXT("the runner on %s"), *P.Label));
			}
		}
	}
	return Parts.Num() > 0 ? FString::Join(Parts, TEXT(", ")) : FString(TEXT("nothing"));
}

FString AOldDoorYardFunctionalTest::LampStateList() const
{
	TArray<FString> Parts;
	for (const FLamp& L : Lamps)
	{
		const FBarrier& G = Barriers[L.GateIndex];
		Parts.Add(FString::Printf(TEXT("%s slot %d (%s) is %s"), *G.Label, L.Slot,
			*LiveCut(G, L.Slot).ToString(),
			LampIsLit(L) ? TEXT("lit") : TEXT("dark")));
	}
	return FString::Join(Parts, TEXT(", "));
}

// ---------------------------------------------------------------------------
// Stepping the model. Every subject carries its OWN clock, so the disclosed 1.20 s
// band is enforced per barrier and per lamp rather than being swallowed by one
// yard-wide settle window.
// ---------------------------------------------------------------------------

void AOldDoorYardFunctionalTest::StepModel(double Now)
{
	// Re-read every staged number LIVE, so a re-staged yard moves the model with it
	// and TheYardIsNotYoursToRewire has something to compare against.
	for (FPad& P : Pads)
	{
		bool bOk = false;
		P.Centre = P.Actor.IsValid() ? P.Actor->GetActorLocation() : P.StagedCentre;
		P.Radius = ReadFloat(P.Actor.Get(), TEXT("ContactRadiusUu"), bOk);
		P.Band = ReadFloat(P.Actor.Get(), TEXT("GroundedBandUu"), bOk);
		P.Answers = ReadActor(P.Actor.Get(), TEXT("AnsweredBarrier"), bOk);
	}
	for (FCrate& C : Crates)
	{
		bool bOk = false;
		C.CrateName = ReadName(C.Actor.Get(), TEXT("CrateName"), bOk);
		C.RailLen = ReadFloat(C.Actor.Get(), TEXT("RailLengthUu"), bOk);
		C.ShoveSpeed = ReadFloat(C.Actor.Get(), TEXT("ShoveSpeedUu"), bOk);
	}
	for (FLamp& L : Lamps)
	{
		bool bOk = false;
		L.Slot = ReadInt(L.Actor.Get(), TEXT("NameSlot"), bOk);
		L.Barrier = ReadActor(L.Actor.Get(), TEXT("LampBarrier"), bOk);
	}

	for (int32 i = 0; i < Barriers.Num(); ++i)
	{
		FBarrier& B = Barriers[i];
		const bool bWant = ModelWants(B);
		const double Ang = PanelAngle(B);
		if (bWant != B.bModelOpen)
		{
			B.bModelOpen = bWant;
			B.ModelChangedAt = Now;
			B.ReachedAt = -1.0;
			if (i == IdxOldDoor && CycleCursor < 4)
			{
				if (bWant)
				{
					Cycles[CycleCursor].OpenLatency = -1.0;
					Cycles[CycleCursor].AngleReached = 0.0;
				}
				else
				{
					Cycles[CycleCursor].ShutLatency = -1.0;
				}
			}
		}
		else if (B.ReachedAt < 0.0
			&& (bWant ? (Ang >= kOpenDeg) : (Ang <= kShutDeg)))
		{
			B.ReachedAt = Now;
		}

		if (i == IdxOldDoor && CycleCursor < 4)
		{
			FCycle& Cyc = Cycles[CycleCursor];
			if (bWant)
			{
				Cyc.AngleReached = FMath::Max(Cyc.AngleReached, Ang);
				if (Cyc.OpenLatency < 0.0 && Ang >= kOpenDeg)
				{
					Cyc.OpenLatency = Now - B.ModelChangedAt;
				}
			}
			else if (Cyc.OpenLatency > -0.5 || Cyc.AngleReached > 0.0)
			{
				if (Cyc.ShutLatency < 0.0 && Ang <= kShutDeg)
				{
					Cyc.ShutLatency = Now - B.ModelChangedAt;
					Cyc.bGraded = true;
					++CycleCursor;
				}
			}
		}

		if (i == IdxGate)
		{
			// Run-level bookkeeping: a gate that latches open can only rise once, and
			// a gate driven purely off overlap edges never comes back down at the
			// re-cut where nothing moves.
			if (Ang >= kOpenDeg)
			{
				if (RecutsApplied <= 1) { bGateRoseBeforeRecut1 = true; }
				else if (RecutsApplied == 2) { bGateRoseBetweenRecuts = true; }
			}
			if (Ang <= kShutDeg)
			{
				if (RecutsApplied <= 1 && bGateRoseBeforeRecut1)
				{
					bGateCameHomeBeforeRecut1 = true;
				}
				if (RecutsApplied >= 3) { bGateCameHomeAfterRecut2 = true; }
			}
		}
		else if (i == IdxSideGate)
		{
			// THE SECOND GATE MOVES THE OTHER WAY at the two moments that matter: it
			// comes up before the first re-cut while the arch gate is shut, comes
			// home again, and comes up a second time at the last re-cut -- the one
			// where nothing in the yard moves and the arch gate is coming DOWN.
			if (Ang >= kOpenDeg)
			{
				if (RecutsApplied <= 1) { bSideRoseBeforeRecut1 = true; }
				else if (RecutsApplied >= 3) { bSideRoseAfterRecut2 = true; }
			}
			if (Ang <= kShutDeg && RecutsApplied <= 1 && bSideRoseBeforeRecut1)
			{
				bSideCameHomeBeforeRecut1 = true;
			}
		}
	}

	// Each lamp's own clock, against ITS OWN GATE's pair. The same crate lights
	// slot 0 on one gate and slot 1 on the other at the same instant.
	for (FLamp& L : Lamps)
	{
		const FBarrier& G = Barriers[L.GateIndex];
		const bool bWant = NamedCrateHome(G, LiveCut(G, L.Slot));
		if (!L.bExpectSeeded)
		{
			L.bExpectSeeded = true;
			L.bExpect = bWant;
			L.ExpectChangedAt = Now;
		}
		else if (bWant != L.bExpect)
		{
			L.bExpect = bWant;
			L.ExpectChangedAt = Now;
		}
	}

	// The yard-wide settle clock. It carries the three panels' wants, the two lamps'
	// wants and WHICH CRATES are resting on the gate's pads -- crates only, never the
	// character, whose body centre passes within a few uu of a pad's own radius while
	// it is leaning on a crate and would otherwise re-arm the clock for ever.
	FString Digest;
	for (const FBarrier& B : Barriers)
	{
		Digest += B.bModelOpen ? TEXT("O") : TEXT("s");
	}
	for (const FLamp& L : Lamps)
	{
		const FBarrier& G = Barriers[L.GateIndex];
		Digest += NamedCrateHome(G, LiveCut(G, L.Slot)) ? TEXT("L") : TEXT("d");
	}
	for (const FPad& P : Pads)
	{
		for (const FCrate& C : Crates)
		{
			Digest += IsResting(P, C.Actor.Get()) ? TEXT("1") : TEXT("0");
		}
	}
	if (Digest != LastModelDigest)
	{
		LastModelDigest = Digest;
		LastModelChangeAt = Now;
	}
}

// ---------------------------------------------------------------------------
// The gates, in the order they are evaluated. At most ONE of the gate-panel gates
// (Runner / CutRightNow / LeavesAndComesBack / StaysShut / OpensWhenBothHome) is armed
// on any frame, so a named FAIL is never a race between two of them.
// TheOldDoorStillOpensInsideItsBand judges a DIFFERENT barrier and can never contend
// with any of them; the lamp gate is an independent channel and always runs LAST, only
// once whichever panel gate was armed has already agreed.
// ---------------------------------------------------------------------------

int32 AOldDoorYardFunctionalTest::ArmedNow() const
{
	return Steps.IsValidIndex(StepIndex) ? Steps[StepIndex].ArmedGate : ARM_NONE;
}

bool AOldDoorYardFunctionalTest::Suppressed(double Now) const
{
	if (!bPrepared || bDriveComplete || !Steps.IsValidIndex(StepIndex))
	{
		return true;
	}
	// AND inside the yard-wide settle window: 1.5x the disclosed band since the
	// fixture's own model last changed ANYWHERE in the yard. This is on top of the
	// per-barrier and per-lamp clocks, never a substitute for them, and it is a
	// widening: every dwell is 3.5 s, so at least 1.7 s of each still gets judged.
	if (Now - LastModelChangeAt < kSettleS)
	{
		return true;
	}
	// Inside the window around a fixture-owned re-cut, and before the drive has
	// arrived at all: the character may spawn anywhere.
	return Now <= StagingUntil || Steps[StepIndex].Phase == 0;
}

bool AOldDoorYardFunctionalTest::BandVerdict(const FBarrier& B, double Now,
	FString& OutWhy) const
{
	const double Elapsed = Now - B.ModelChangedAt;
	if (Elapsed < kBandS + kBandGraceS)
	{
		// Still inside the time the yard promises it, plus one frame's worth of
		// grace either way. A widening, never a narrowing.
		return true;
	}
	const double Ang = PanelAngle(B);
	if (B.bModelOpen ? (Ang >= kOpenDeg) : (Ang <= kShutDeg))
	{
		return true;
	}
	OutWhy = FString::Printf(
		TEXT("%s should have been %s since t=%.2f (%.2f s ago, against the %.2f s the "
			 "yard promises) and its panel reads %.1f deg from the pose it started "
			 "play in; IT is cut for (%s, %s) right now, what is resting on ITS OWN "
			 "pads is %s, and the lamps read %s"),
		*B.Label, B.bModelOpen ? TEXT("open") : TEXT("shut"), B.ModelChangedAt,
		Elapsed, kBandS, Ang, *LiveCut(B, 0).ToString(), *LiveCut(B, 1).ToString(),
		*HomeCrateList(B), *LampStateList());
	return false;
}

FString AOldDoorYardFunctionalTest::BaselineText() const
{
	TArray<FString> Parts;
	for (int32 i = 0; i < 2; ++i)
	{
		Parts.Add(FString::Printf(
			TEXT("cycle %d reached %.1f deg, opening in %.2f s and coming home in "
				 "%.2f s"), i, Cycles[i].AngleReached,
			Cycles[i].OpenLatency, Cycles[i].ShutLatency));
	}
	return FString::Join(Parts, TEXT("; "));
}

bool AOldDoorYardFunctionalTest::CheckTravelCaps(FBarrier& B, double Budget,
	const TCHAR*)
{
	if (!B.Panel.IsValid())
	{
		return true;
	}
	const double NowAngle = PanelAngle(B);
	const FVector NowLoc = B.Panel->GetComponentLocation();
	if (!B.bSeeded)
	{
		// SEEDED from this sample. A default-constructed baseline reads hundreds of
		// cm of travel on frame one and fails everything, the reference included.
		B.LastAngle = NowAngle;
		B.LastPanelLoc = NowLoc;
		B.bSeeded = true;
		return true;
	}
	const double DegStep = FMath::Abs(NowAngle - B.LastAngle);
	const double CmStep = FVector::Dist(NowLoc, B.LastPanelLoc);
	B.LastAngle = NowAngle;
	B.LastPanelLoc = NowLoc;
	return DegStep <= kMaxDegPerSec * Budget && CmStep <= kMaxCmPerSec * Budget;
}

bool AOldDoorYardFunctionalTest::GateNotRewired(double Now)
{
	auto Near = [](double A, double Bv)
	{
		return FMath::Abs(A - Bv) <= FMath::Max(FMath::Abs(Bv) * kPinPct, 0.01);
	};

	for (const FBarrier& B : Barriers)
	{
		if (!B.Actor.IsValid())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: %s is gone from the yard"), *B.Label));
			return false;
		}
		bool bOk = false;
		const double Open = ReadFloat(B.Actor.Get(), TEXT("OpenAngleDeg"), bOk);
		const double Rate = ReadFloat(B.Actor.Get(), TEXT("TravelRateDegPerSec"), bOk);
		if (FVector::Dist(B.Actor->GetActorLocation(), B.StagedLoc) > kPinPosUu
			|| FMath::Abs(FMath::FindDeltaAngleDegrees(
				B.StagedYaw, B.Actor->GetActorRotation().Yaw)) > 0.5
			|| !Near(Open, B.StagedOpenAngleDeg) || !Near(Rate, B.StagedTravelRate))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: %s has been moved or its own numbers "
					 "rewritten (it stands %.1f uu off where the yard put it, opening "
					 "to %.1f deg at %.1f deg per second against a staged %.1f and "
					 "%.1f)"), *B.Label,
				FVector::Dist(B.Actor->GetActorLocation(), B.StagedLoc), Open, Rate,
				B.StagedOpenAngleDeg, B.StagedTravelRate));
			return false;
		}
	}

	for (const FPad& P : Pads)
	{
		if (!P.Actor.IsValid()
			|| FVector::Dist(P.Centre, P.StagedCentre) > kPinPosUu
			|| !Near(P.Radius, P.StagedRadius) || !Near(P.Band, P.StagedBand)
			|| P.Answers.Get() != P.StagedAnswers.Get())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: %s has been moved, re-sized, or "
					 "pointed at a different door (it reads a %.1f uu reach and a "
					 "%.1f uu band against a staged %.1f and %.1f)"), *P.Label,
				P.Radius, P.Band, P.StagedRadius, P.StagedBand));
			return false;
		}
	}

	for (const FCrate& C : Crates)
	{
		if (!C.Actor.IsValid())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: %s has left the yard altogether"),
				*C.Label));
			return false;
		}
		// EVERY CRATE IS STILL ON ITS OWN RAIL, every frame. Load-bearing rather than
		// ceremonial: the model reads LIVE transforms, so without this a submission
		// that teleported a crate onto a pad would make the model agree with itself.
		const FVector Here = C.Actor->GetActorLocation();
		const double Along = FMath::Clamp(
			FVector::DotProduct(Here - C.Anchor, C.Axis), 0.0, C.RailLen);
		const double OffRail = FVector::Dist(Here, C.Anchor + C.Axis * Along);
		if (C.CrateName != C.StagedName || !Near(C.RailLen, C.StagedRailLen)
			|| !Near(C.ShoveSpeed, C.StagedShoveSpeed) || OffRail > 3.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: %s is no longer the crate the yard "
					 "staged (it answers to %s against a staged %s, and it stands "
					 "%.1f uu off the line between its own two stops)"), *C.Label,
				*C.CrateName.ToString(), *C.StagedName.ToString(), OffRail));
			return false;
		}
	}

	for (const FLamp& L : Lamps)
	{
		if (!L.Actor.IsValid() || L.Slot != L.StagedSlot
			|| L.Barrier.Get() != L.StagedBarrier.Get())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardIsNotYoursToRewire: a lamp has been re-slotted or bolted "
					 "to a different barrier (it now says slot %d against a staged "
					 "%d)"), L.Slot, L.StagedSlot));
			return false;
		}
	}

	// EVERY BARRIER'S PAIR IS COMPARED AGAINST WHAT THIS TEST ITSELF LAST WROTE,
	// never against what the level holds -- the level is deliberately saved holding
	// different pairs. The two DOORS are pinned by the same clause at empty, which
	// catches a submission that writes names onto a door to push it down whichever
	// branch it built. Suspended only inside the fixture's own re-cut windows,
	// because the fixture is the one writing there.
	if (Now > StagingUntil)
	{
		for (const FBarrier& B : Barriers)
		{
			const FName First = LiveCut(B, 0);
			const FName Second = LiveCut(B, 1);
			if (First != B.ExpectFirst || Second != B.ExpectSecond)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheYardIsNotYoursToRewire: the writing on %s is not the "
						 "foreman's any more (it reads (%s, %s) where the yard last "
						 "cut it for (%s, %s)); the re-cut is his to make, not the "
						 "submission's"), *B.Label, *First.ToString(),
					*Second.ToString(), *B.ExpectFirst.ToString(),
					*B.ExpectSecond.ToString()));
				return false;
			}
		}
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateTwinNeverMoves(double Now)
{
	FBarrier& T = Barriers[IdxTwinDoor];
	const double Ang = PanelAngle(T);
	if (Ang > kShutDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheDoorNobodyTouchesNeverMoves: at t=%.2f the door 3000 cm east that "
				 "nothing in this run ever approaches has swung %.1f deg from the "
				 "pose it started play in, and the yard allows %.0f; whatever moved "
				 "it was aimed at every barrier in the level rather than at the one "
				 "that is cut for names"), Now, Ang, kShutDeg));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateOldDoorBand(double Now)
{
	FBarrier& Old = Barriers[IdxOldDoor];
	FString Why;
	if (!BandVerdict(Old, Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheOldDoorStillOpensInsideItsBand: the door that worked before any "
				 "of this no longer does. %s. Measured earlier in THIS run, before "
				 "the character had touched a crate: %s"),
			*Why, *BaselineText()));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateRunnerIsNotACrate(double Now)
{
	// A GATE THAT CANNOT FAIL IS NOT A GATE. This one's whole premise is that a PERSON
	// is squarely on one of the gate's own pads; if the drive did not actually get the
	// character there, the gate is vacuous and a submission would be credited with
	// passing something that was never asked. That is the level's fault, not the
	// submission's, so it is attributed rather than scored.
	const FPad& Near = Pads[IdxNearPad];
	if (!Hero.IsValid() || !IsResting(Near, Hero.Get()))
	{
		FailStaging(FString::Printf(
			TEXT("the drive meant to stand a person squarely on the gate's near pad "
				 "and the character is %.0f uu from its centre against a %.0f uu "
				 "reach"),
			Hero.IsValid()
				? FVector::Dist2D(Hero->GetActorLocation(), Near.Centre) : -1.0,
			Near.Radius), Now);
		return false;
	}

	// ROUTED THROUGH THE SAME BAND ARITHMETIC AS EVERY OTHER PANEL GATE. Judging
	// this one on a bare angle made it the only gate with no decision latency at all:
	// a correct answer is allowed the whole disclosed 1.20 s to decide and its panel
	// still has to travel afterwards, which is more time than the arm window alone
	// gives it. BandVerdict measures from the barrier's OWN last model change, so the
	// gate now says exactly what the prompt promises and nothing tighter.
	const FBarrier& Gate = Barriers[IdxGate];
	FString Why;
	if (!BandVerdict(Gate, Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRunnerIsNotACrate: a person has been standing squarely on one of "
				 "the gate's own pads for %.2f s and the gate has not stayed shut; a "
				 "person is not a crate and never counts toward anything. %s"),
			Now - HoldSince, *Why));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateCutRightNow(double Now)
{
	FString Why;
	if (!BandVerdict(Barriers[IdxGate], Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheGateAnswersToWhatItIsCutForRightNow: whatever is written on the "
				 "gate at the moment you need to know is the answer, and it has been "
				 "re-cut %d times in this run without anything announcing it. %s"),
			RecutsApplied - 1, *Why));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateLeavesAndComesBack(double Now)
{
	FString Why;
	if (!BandVerdict(Barriers[IdxGate], Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack: a crate has "
				 "just been shoved off one of the gate's pads or back onto it, and "
				 "the gate did not follow. %s"), *Why));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateStaysShut(double Now)
{
	FString Why;
	if (!BandVerdict(Barriers[IdxGate], Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheGateStaysShutUntilBothItsCratesAreHome: the gate is open with "
				 "less than both of the names it is cut for resting on its pads. %s"),
			*Why));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateOpensWhenBothHome(double Now)
{
	FString Why;
	if (!BandVerdict(Barriers[IdxGate], Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheGateOpensWhenBothItsCratesAreHome: a crate carrying each of the "
				 "two names the gate is cut for is resting on one of its pads and the "
				 "gate has not come up. %s"), *Why));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateSecondGateAnswers(double Now)
{
	// THE IN-SCENE CONTROL ON THE SIDE THE SUBMISSION ACTUALLY BUILDS. The twin door
	// proves nothing about the new behaviour -- it is cut for nothing and takes the
	// branch that already shipped. This one is a matched instance of the same class,
	// cut for its OWN pair, standing over the SAME two patches of floor and watching
	// the SAME three crates, so nothing about the layout can tell the two gates
	// apart: only what is written on each of them can. It is armed on every judged
	// frame, and through most of the run its answer is the opposite of the arch
	// gate's.
	FString Why;
	if (!BandVerdict(Barriers[IdxSideGate], Now, Why))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheSecondGateAnswersToItsOwnPair: this yard has two gates, they are "
				 "cut for different pairs of names, and they stand over the same two "
				 "patches of floor -- so what one of them is doing says nothing at "
				 "all about what the other one should be doing. %s. The arch gate is "
				 "cut for (%s, %s) at the same instant"), *Why,
			*LiveCut(Barriers[IdxGate], 0).ToString(),
			*LiveCut(Barriers[IdxGate], 1).ToString()));
		return false;
	}
	return true;
}

bool AOldDoorYardFunctionalTest::GateLamps(double Now)
{
	for (const FLamp& L : Lamps)
	{
		if (Now - L.ExpectChangedAt < kBandS + kBandGraceS)
		{
			continue;
		}
		if (LampIsLit(L) != L.bExpect)
		{
			const FBarrier& G = Barriers[L.GateIndex];
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheGateLampsNameTheCratesItHolds: %s should be %s because %s is "
					 "cut for (%s, %s) right now and what is resting on ITS OWN pads "
					 "is %s, but the lamps read %s (they have had %.2f s, and the "
					 "yard promises %.2f). A lamp stands for a slot ON ITS OWN GATE: "
					 "the two gates carry different pairs at the same instant"),
				*L.Label, L.bExpect ? TEXT("burning") : TEXT("out"), *G.Label,
				*LiveCut(G, 0).ToString(), *LiveCut(G, 1).ToString(),
				*HomeCrateList(G), *LampStateList(),
				Now - L.ExpectChangedAt, kBandS));
			return false;
		}
	}
	return true;
}

bool AOldDoorYardFunctionalTest::PreservationStillHolds(double Now)
{
	// A HARNESS EXIT CAN NEVER LAUNDER A FAIL. A submission that jams the gate's
	// panel across the walking lane, or that moves a crate, can stop a phase from
	// completing -- so before any overrun is written off as a staging fault, the
	// three gates that do not depend on the drive having got anywhere are re-checked
	// UNCONDITIONALLY.
	if (!GateNotRewired(Now)) { return false; }
	if (!GateTwinNeverMoves(Now)) { return false; }
	if (!GateOldDoorBand(Now)) { return false; }
	return true;
}

void AOldDoorYardFunctionalTest::FailStaging(const FString& Why, double Now)
{
	if (!PreservationStillHolds(Now))
	{
		return;  // already reported as a graded FAIL, which it is
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the drive could not complete, and the yard is "
			 "otherwise intact: %s"), *Why));
}

void AOldDoorYardFunctionalTest::GradeRunLevel(double Now)
{
	if (!bGateRoseBeforeRecut1 || !bGateCameHomeBeforeRecut1
		|| !bGateRoseBetweenRecuts || !bGateCameHomeAfterRecut2
		|| !bSideRoseBeforeRecut1 || !bSideCameHomeBeforeRecut1
		|| !bSideRoseAfterRecut2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheGateRoseAgainAfterEveryRecut: over the whole run the arch gate "
				 "had to come up before the first re-cut (it %s), come home again (it "
				 "%s), come up once more between the two re-cuts (it %s) and come "
				 "home after the second (it %s); and the second gate had to come up "
				 "before the first re-cut, while the arch gate was shut (it %s), come "
				 "home again (it %s), and come up at the LAST re-cut, with nothing in "
				 "the yard moving and the arch gate coming down (it %s). A gate that "
				 "latches open can only rise once; a gate that only recomputes on an "
				 "overlap edge never moves at all when nothing has moved; and one "
				 "answer written for THE gate can never do both of these at once"),
			bGateRoseBeforeRecut1 ? TEXT("did") : TEXT("did not"),
			bGateCameHomeBeforeRecut1 ? TEXT("did") : TEXT("did not"),
			bGateRoseBetweenRecuts ? TEXT("did") : TEXT("did not"),
			bGateCameHomeAfterRecut2 ? TEXT("did") : TEXT("did not"),
			bSideRoseBeforeRecut1 ? TEXT("did") : TEXT("did not"),
			bSideCameHomeBeforeRecut1 ? TEXT("did") : TEXT("did not"),
			bSideRoseAfterRecut2 ? TEXT("did") : TEXT("did not")));
		return;
	}
	int32 Graded = 0;
	for (const FCycle& C : Cycles)
	{
		Graded += C.bGraded ? 1 : 0;
	}
	if (Graded < 4)
	{
		FailStaging(FString::Printf(
			TEXT("only %d of the old door's four cycles were measured end to end"),
			Graded), Now);
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-olddooryard] run complete at t=%.2f. Old-door cycles, all four: "
			 "0 %.1f deg %.2f s open %.2f s home | 1 %.1f %.2f %.2f | 2 %.1f %.2f "
			 "%.2f | 3 %.1f %.2f %.2f"), Now,
		Cycles[0].AngleReached, Cycles[0].OpenLatency, Cycles[0].ShutLatency,
		Cycles[1].AngleReached, Cycles[1].OpenLatency, Cycles[1].ShutLatency,
		Cycles[2].AngleReached, Cycles[2].OpenLatency, Cycles[2].ShutLatency,
		Cycles[3].AngleReached, Cycles[3].OpenLatency, Cycles[3].ShutLatency);
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("The old door still opens inside its band, the twin never moved, and both "
			 "gates answered to what each of them was cut for through every re-cut."));
}

// ---------------------------------------------------------------------------
// The drive. Movement input is consumed per frame, so it is re-applied every tick
// through AddMovementInput -- the same path AThirdPersonCharacter::DoMove drives with
// WASD. The world is NEVER ticked here.
// ---------------------------------------------------------------------------

void AOldDoorYardFunctionalTest::BeginStep(double Now)
{
	if (!Steps.IsValidIndex(StepIndex) || !Hero.IsValid())
	{
		return;
	}
	FStep& S = Steps[StepIndex];
	S.Route.Reset();
	if (S.Kind == EStep::Go)
	{
		S.Route = RouteTo(S.Target, S.Lane);
	}
	else if (S.Kind == EStep::Retreat && Crates.IsValidIndex(S.Crate))
	{
		// Straight off the rail onto this crate's own lane. Perpendicular, so it can
		// never read as a shove: the crate only moves for somebody walking ALONG its
		// rail, and this walk is across it.
		const int32 Lane = S.Crate == IdxCrateNear ? 0 : 1;
		S.Route.Add(FVector(LaneX(Lane), Hero->GetActorLocation().Y, WalkZ));
	}

	RouteIndex = 0;
	bArrived = S.Route.Num() == 0;
	HoldSince = bArrived ? Now : -1.0;
	bPushDone = false;
	StepStartedAt = Now;

	double RouteLen = 0.0;
	FVector From = Hero->GetActorLocation();
	for (const FVector& P : S.Route)
	{
		RouteLen += FVector::Dist2D(From, P);
		From = P;
	}
	// DERIVED, and generously. The pace assumed here is well under half the
	// character's measured top speed, because a deadline that a correct answer can
	// miss is a manufactured failure and this repo has four of those on record.
	switch (S.Kind)
	{
	case EStep::Push:
		StepDeadline = Now + (Crates.IsValidIndex(S.Crate)
			? Crates[S.Crate].RailLen / FMath::Max(Crates[S.Crate].ShoveSpeed * 0.5, 1.0)
			: 10.0) + 30.0;
		break;
	case EStep::Stand:
		StepDeadline = Now + S.Hold + 10.0;
		break;
	case EStep::Recut:
		StepDeadline = Now + 5.0;
		break;
	default:
		StepDeadline = Now + RouteLen / FMath::Max(HeroSpeed * 0.4, 1.0) + S.Hold + 20.0;
		break;
	}

	if (S.Kind == EStep::Recut)
	{
		ApplyRecut(S.Recut, Now);
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t3-olddooryard] step %d (phase %d) t=%.2f: %s"),
		StepIndex, S.Phase, Now, *S.What);
}

void AOldDoorYardFunctionalTest::DriveCharacter(double Now, float)
{
	if (!Hero.IsValid() || !Steps.IsValidIndex(StepIndex))
	{
		return;
	}
	FStep& S = Steps[StepIndex];
	const FVector Here = Hero->GetActorLocation();

	if (S.Kind == EStep::Push && Crates.IsValidIndex(S.Crate)
		&& Crates[S.Crate].Actor.IsValid())
	{
		// Walk INTO the crate, aiming past it along its own rail. The crate reads
		// what a body is asking to do, not how fast it is managing to move, so
		// leaning on it is exactly right.
		const FCrate& C = Crates[S.Crate];
		const FVector Aim = C.Actor->GetActorLocation() + C.Axis * S.Dir * kPushAimUu;
		const FVector Flat(Aim.X - Here.X, Aim.Y - Here.Y, 0.0);
		if (!Flat.IsNearlyZero())
		{
			Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		}
		return;
	}

	if (!bArrived)
	{
		while (RouteIndex < S.Route.Num())
		{
			const FVector Target = S.Route[RouteIndex];
			const bool bLast = RouteIndex == S.Route.Num() - 1;
			const double Arrive = bLast && S.ArriveUu > 0.0 ? S.ArriveUu : kWaypointUu;
			const double D = FVector::Dist2D(Here, Target);
			if (D <= Arrive)
			{
				++RouteIndex;
				continue;
			}
			// The input TAPERS on the last leg only. Without it the character brakes
			// from full pace and can coast past a 100 uu pad radius it was asked to
			// stand in the middle of; with it the approach is a person slowing down.
			double Scale = 1.0;
			if (bLast && D < kTaperUu)
			{
				Scale = FMath::Clamp(D / kTaperUu, kTaperFloor, 1.0);
			}
			const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
			if (!Flat.IsNearlyZero())
			{
				Hero->AddMovementInput(Flat.GetSafeNormal(), static_cast<float>(Scale));
			}
			break;
		}
		if (RouteIndex >= S.Route.Num())
		{
			bArrived = true;
			HoldSince = Now;
		}
		return;
	}

	if (S.bStayOnTarget)
	{
		// A person standing on a pad keeps standing on it. A light corrective input
		// holds the character at the centre instead of letting braking drift it out
		// toward the pad's own edge.
		const double D = FVector::Dist2D(Here, S.Target);
		if (D > 8.0)
		{
			const FVector Flat(S.Target.X - Here.X, S.Target.Y - Here.Y, 0.0);
			if (!Flat.IsNearlyZero())
			{
				Hero->AddMovementInput(Flat.GetSafeNormal(),
					static_cast<float>(FMath::Clamp(D / 120.0, 0.10, 0.50)));
			}
		}
	}
}

void AOldDoorYardFunctionalTest::AdvanceSteps(double Now)
{
	if (bDriveComplete || !Steps.IsValidIndex(StepIndex))
	{
		return;
	}
	FStep& S = Steps[StepIndex];

	if (S.Kind == EStep::Finish)
	{
		bDriveComplete = true;
		GradeRunLevel(Now);
		return;
	}

	bool bDone = false;
	switch (S.Kind)
	{
	case EStep::Push:
	{
		if (Crates.IsValidIndex(S.Crate))
		{
			const FCrate& C = Crates[S.Crate];
			const double Want = S.Dir > 0.0 ? C.RailLen : 0.0;
			bPushDone = FMath::Abs(RailParam(C) - Want) <= kStopEpsUu;
		}
		bDone = bPushDone;
		break;
	}
	case EStep::Stand:
		bDone = Now - StepStartedAt >= S.Hold;
		break;
	case EStep::Recut:
		bDone = true;
		break;
	default:
		bDone = bArrived && HoldSince >= 0.0 && Now - HoldSince >= S.Hold;
		break;
	}

	if (bDone)
	{
		++StepIndex;
		BeginStep(Now);
		return;
	}

	if (Now > StepDeadline)
	{
		FailStaging(FString::Printf(
			TEXT("step %d of phase %d (%s) ran past its derived deadline of %.1f s"),
			StepIndex, S.Phase, *S.What, StepDeadline - StepStartedAt), Now);
	}
}

void AOldDoorYardFunctionalTest::LogCalib(int32 Index, double Now) const
{
	if (Barriers.Num() < 4)
	{
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-olddooryard calib] cp%d t=%.2f step=%d phase=%d old=%.1f(%d) "
			 "twin=%.1f arch=%.1f(%d) cut=(%s,%s) side=%.1f(%d) cut=(%s,%s) "
			 "home=[%s] lamps=[%s]"),
		Index, Now, StepIndex,
		Steps.IsValidIndex(StepIndex) ? Steps[StepIndex].Phase : -1,
		PanelAngle(Barriers[IdxOldDoor]), Barriers[IdxOldDoor].bModelOpen ? 1 : 0,
		PanelAngle(Barriers[IdxTwinDoor]),
		PanelAngle(Barriers[IdxGate]), Barriers[IdxGate].bModelOpen ? 1 : 0,
		*LiveCut(Barriers[IdxGate], 0).ToString(),
		*LiveCut(Barriers[IdxGate], 1).ToString(),
		PanelAngle(Barriers[IdxSideGate]), Barriers[IdxSideGate].bModelOpen ? 1 : 0,
		*LiveCut(Barriers[IdxSideGate], 0).ToString(),
		*LiveCut(Barriers[IdxSideGate], 1).ToString(),
		*HomeCrateList(Barriers[IdxGate]), *LampStateList());
}

void AOldDoorYardFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!bPrepared)
	{
		return;
	}
	LogCalib(CheckpointIndex, TimeSeconds);

	// THE IN-SCENE CONTROL IS GAUGED AT EVERY CHECKPOINT as well as on every frame.
	// It is the one gate that can never be excused by the drive not having got
	// anywhere: nothing in this run goes within 2,000 uu of it.
	if (!GateTwinNeverMoves(TimeSeconds))
	{
		return;
	}

	// The sentinel. Reaching it means the drive never finished.
	if (CheckpointIndex >= kCalibCount && !bDriveComplete)
	{
		FailStaging(FString::Printf(
			TEXT("the run reached its sentinel at %.0f s still on step %d of phase "
				 "%d"), TimeSeconds, StepIndex,
			Steps.IsValidIndex(StepIndex) ? Steps[StepIndex].Phase : -1),
			TimeSeconds);
	}
}

void AOldDoorYardFunctionalTest::Tick(float DeltaSeconds)
{
	const double Budget = FMath::Max(static_cast<double>(DeltaSeconds),
		static_cast<double>(KINDA_SMALL_NUMBER));

	// THE TRAVEL CAPS RUN BEFORE THE BASE CLOCK, so the frame that crosses the final
	// checkpoint is still covered. It travels: a panel that teleports into place has
	// not travelled, whatever pose it ends up holding.
	if (bPrepared && IsRunning() && Barriers.Num() == 4)
	{
		if (!CheckTravelCaps(Barriers[IdxOldDoor], Budget, TEXT("old")))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheOldDoorStillOpensInsideItsBand: the old door's panel jumped "
					 "rather than travelled inside one frame of %.4f s, and the yard "
					 "allows %.0f degrees and %.0f cm per second"),
				Budget, kMaxDegPerSec, kMaxCmPerSec));
			return;
		}
		if (!CheckTravelCaps(Barriers[IdxTwinDoor], Budget, TEXT("twin")))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDoorNobodyTouchesNeverMoves: the untouched twin door's panel "
					 "jumped inside one frame of %.4f s; nothing in this run goes "
					 "within 2000 uu of it"), Budget));
			return;
		}
		if (!CheckTravelCaps(Barriers[IdxGate], Budget, TEXT("gate")))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheGateOpensWhenBothItsCratesAreHome: the arch gate's panel "
					 "jumped rather than travelled inside one frame of %.4f s, and "
					 "the yard allows %.0f degrees and %.0f cm per second"),
				Budget, kMaxDegPerSec, kMaxCmPerSec));
			return;
		}
		if (!CheckTravelCaps(Barriers[IdxSideGate], Budget, TEXT("side")))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSecondGateAnswersToItsOwnPair: the second gate's panel "
					 "jumped rather than travelled inside one frame of %.4f s, and "
					 "the yard allows %.0f degrees and %.0f cm per second"),
				Budget, kMaxDegPerSec, kMaxCmPerSec));
			return;
		}
	}

	Super::Tick(DeltaSeconds);  // base first: checkpoint clock + timeout machinery

	if (!bPrepared || !IsRunning() || !Hero.IsValid() || bDriveComplete)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World != nullptr
		? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	StepModel(Now);

	// 1 and 2: integrity and the in-scene control, every frame, from the first.
	if (!GateNotRewired(Now)) { return; }
	if (!GateTwinNeverMoves(Now)) { return; }

	if (!Suppressed(Now))
	{
		// 3: the headline preservation gate. Its subject is the OLD DOOR, so it can
		//    never contend with any of the gate's own gates below.
		if (!GateOldDoorBand(Now)) { return; }

		// 4 to 8: AT MOST ONE, chosen by the step in progress. Where the step arms
		//    the default pair, the model picks which of the two names the failure --
		//    so the gate that fires is always the one that describes what went wrong.
		bool bPanelOk = true;
		switch (ArmedNow())
		{
		case ARM_RUNNER:
			if (bArrived && HoldSince >= 0.0 && Now - HoldSince >= kRunnerArmS)
			{
				bPanelOk = GateRunnerIsNotACrate(Now);
			}
			break;
		case ARM_CUTNOW:
			bPanelOk = GateCutRightNow(Now);
			break;
		case ARM_LEAVE:
			bPanelOk = GateLeavesAndComesBack(Now);
			break;
		case ARM_SHUT:
		case ARM_OPEN:
		default:
			// EVERY OTHER JUDGED FRAME. The two named gates of this pair are one
			// statement split in two, so the MODEL picks which of them names the
			// failure rather than the step table guessing in advance. The default
			// arm matters as much as the explicit ones: the four old-door cycles
			// arm no gate of their own, and without it the arch gate would go
			// unjudged straight through them.
			bPanelOk = Barriers[IdxGate].bModelOpen
				? GateOpensWhenBothHome(Now) : GateStaysShut(Now);
			break;
		}
		if (!bPanelOk) { return; }

		// 9: THE SECOND GATE, on every judged frame, from its own model. It judges a
		//    DIFFERENT barrier from any of 4-8, so it can never contend with them;
		//    it runs after them so that at the first single-crate dwell the arch
		//    gate's own gate is the one that names an over-permissive answer.
		if (!GateSecondGateAnswers(Now)) { return; }

		// 10: the lamps, an INDEPENDENT channel, always LAST and only once whichever
		//     panel gate was armed has already agreed. That gets both halves: a
		//     wrong panel is always named by a panel gate, and a right panel with
		//     wrong lamps is always named here. All FOUR lamps, each against the
		//     pair written on ITS OWN gate.
		if (!GateLamps(Now)) { return; }
	}

	AdvanceSteps(Now);
	DriveCharacter(Now, DeltaSeconds);
}
