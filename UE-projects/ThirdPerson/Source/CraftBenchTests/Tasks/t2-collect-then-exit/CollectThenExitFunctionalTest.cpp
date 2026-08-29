// Copyright CraftBench. All Rights Reserved.

#include "CollectThenExitFunctionalTest.h"

#include "Components/BoxComponent.h"
#include "Components/LightComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	// DISCLOSED in the prompt.
	constexpr int32 kRequired = 3;
	constexpr double kLitIntensity = 5000.0;   // "at least 5000 bright"
	constexpr double kSpareMoveCm = 25.0;      // "within 25 cm of where it was placed"

	// UNDISCLOSED: fixture geometry and clocking, never thresholds on the answer.
	//
	// The contact margin is ONE-SIDED BY CONSTRUCTION. The engine's begin-overlap
	// edge fires at centre-to-centre 120 + 34 = 154 cm (the 120 cm RelicVolume plus
	// ACharacter's default 34 cm capsule). At 300 the fixture registers a contact
	// several frames EARLIER than the engine can, so the submission's tally can
	// never read higher than the fixture's count and G3 cannot false-FAIL correct
	// work; the same reasoning applies to the lamp at the third relic. The fixture
	// may count early, never late, and the submission is never asked to match the
	// fixture's instant.
	constexpr double kFixtureContactCm = 300.0;
	constexpr double kFixtureExitMarginCm = 150.0;
	constexpr double kWaypointReachedCm = 90.0;

	// Arena bounds = the floor extent expanded 300 cm every way. A relic outside
	// this has visibly left the arena; the slack means a relic authored near an edge
	// can never read GONE by settling or float epsilon.
	const FBox kArenaBounds(FVector(-300.0, -1500.0, -300.0),
							FVector(2700.0, 1500.0, 600.0));

	// Authored placement, the map contract. Used only to name which relic is which
	// for the ROUTE; the COUNT is a set and never depends on ordering.
	const FVector2D kRelicA(900.0, -500.0);
	const FVector2D kRelicB(1500.0, 500.0);
	const FVector2D kRelicC(1900.0, -500.0);
	const FVector2D kSpareAt(1900.0, -1000.0);
	const FVector2D kExitAt(2100.0, 0.0);

	FString Squeeze(const FString& In)
	{
		FString Out;
		for (const TCHAR C : In)
		{
			if (!FChar::IsWhitespace(C))
			{
				Out.AppendChar(C);
			}
		}
		return Out;
	}
}

ACollectThenExitFunctionalTest::ACollectThenExitFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool ACollectThenExitFunctionalTest::ResolveByTag(const TCHAR* Tag, int32 Expected,
	TArray<AActor*>& Out)
{
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(Tag), Out);
	if (Out.Num() != Expected)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected %d actor(s) tagged %s, found %d"),
			Expected, Tag, Out.Num()));
		return false;
	}
	return true;
}

AActor* ACollectThenExitFunctionalTest::NearestRelic(const TArray<AActor*>& Relics,
	const FVector2D& At) const
{
	AActor* Best = nullptr;
	double BestDist = TNumericLimits<double>::Max();
	for (AActor* R : Relics)
	{
		if (R == nullptr)
		{
			continue;
		}
		const FVector P = R->GetActorLocation();
		const double D = FVector2D::Distance(FVector2D(P.X, P.Y), At);
		if (D < BestDist)
		{
			BestDist = D;
			Best = R;
		}
	}
	return Best;
}

UTextRenderComponent* ACollectThenExitFunctionalTest::FindText(AActor* OnActor,
	const TCHAR* Name) const
{
	if (OnActor == nullptr)
	{
		return nullptr;
	}
	// By NAME, not by index: the prompt tells the agent to keep these two faces and
	// allows adding more on top, so the first text component found is not enough.
	TArray<UTextRenderComponent*> Texts;
	OnActor->GetComponents<UTextRenderComponent>(Texts);
	for (UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetName() == Name)
		{
			return T;
		}
	}
	return nullptr;
}

FString ACollectThenExitFunctionalTest::ReadTallyRaw() const
{
	const UTextRenderComponent* T =
		FindText(Board.Get(), TEXT("TallyText"));
	return T ? T->Text.ToString() : FString();
}

int32 ACollectThenExitFunctionalTest::ReadTally() const
{
	// Whitespace-insensitive, so 2/3, 2 / 3 and 2  /  3 all read the same. Returns
	// -1 when the face does not parse as <int>/<int> -- which is exactly what the
	// shipped-blank board reads, and -1 is never greater than the fixture's count,
	// so the blank board cannot trip the over-count guard. It fails cp0 instead, by
	// cp0's own named message.
	const FString S = Squeeze(ReadTallyRaw());
	FString Left, Right;
	if (!S.Split(TEXT("/"), &Left, &Right))
	{
		return -1;
	}
	if (Left.IsEmpty() || Right.IsEmpty() || !Left.IsNumeric() || !Right.IsNumeric())
	{
		return -1;
	}
	return FCString::Atoi(*Left);
}

FString ACollectThenExitFunctionalTest::ReadStatus() const
{
	const UTextRenderComponent* T =
		FindText(Board.Get(), TEXT("StatusText"));
	return T ? T->Text.ToString().TrimStartAndEnd().ToUpper() : FString();
}

double ACollectThenExitFunctionalTest::LampBrightness() const
{
	AActor* const E = Exit.Get();
	if (E == nullptr)
	{
		return 0.0;
	}
	TArray<ULightComponent*> Lamps;
	E->GetComponents<ULightComponent>(Lamps);
	for (ULightComponent* L : Lamps)
	{
		if (L == nullptr || L->GetName() != TEXT("ExitLamp"))
		{
			continue;
		}
		// Hidden and zero-intensity both read as DARK, because both look identical
		// to a human watching.
		if (!L->IsVisible() || L->bHiddenInGame)
		{
			return 0.0;
		}
		return static_cast<double>(L->Intensity);
	}
	return 0.0;
}

bool ACollectThenExitFunctionalTest::VisiblyPresent(AActor* Relic) const
{
	if (Relic == nullptr || !IsValid(Relic))
	{
		return false;  // destroyed
	}
	if (!kArenaBounds.IsInside(Relic->GetActorLocation()))
	{
		return false;  // removed from the arena
	}
	TArray<UPrimitiveComponent*> Prims;
	Relic->GetComponents<UPrimitiveComponent>(Prims);
	for (UPrimitiveComponent* P : Prims)
	{
		// Any visible mesh is enough: consuming a relic by hiding its mesh reads as
		// gone, exactly like destroying it.
		if (P != nullptr && P->IsVisible() && !P->bHiddenInGame
			&& P->GetClass()->GetName().Contains(TEXT("StaticMesh")))
		{
			return true;
		}
	}
	return false;
}

bool ACollectThenExitFunctionalTest::HeroInExit(double Margin) const
{
	AActor* const E = Exit.Get();
	if (E == nullptr || !Hero.IsValid())
	{
		return false;
	}
	TArray<UBoxComponent*> Boxes;
	E->GetComponents<UBoxComponent>(Boxes);
	const FVector H = Hero->GetActorLocation();
	for (UBoxComponent* B : Boxes)
	{
		if (B == nullptr || B->GetName() != TEXT("ExitVolume"))
		{
			continue;
		}
		const FVector Local = B->GetComponentTransform().InverseTransformPosition(H);
		const FVector Ext = B->GetUnscaledBoxExtent() + FVector(Margin);
		return FMath::Abs(Local.X) <= Ext.X && FMath::Abs(Local.Y) <= Ext.Y
			&& FMath::Abs(Local.Z) <= Ext.Z;
	}
	return false;
}

void ACollectThenExitFunctionalTest::ReleaseLeg(int32 Index)
{
	if (Legs.IsValidIndex(Index))
	{
		Legs[Index].Next = 0;
		Legs[Index].bActive = true;
		ActiveLeg = Index;
	}
}

void ACollectThenExitFunctionalTest::LogCalib(int32 Index, double Now) const
{
	int32 Present = 0;
	for (const TWeakObjectPtr<AActor>& R : Required)
	{
		if (VisiblyPresent(R.Get()))
		{
			++Present;
		}
	}
	if (VisiblyPresent(Spare.Get()))
	{
		++Present;
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-collect calib] cp%d t=%.2f taken=%d tally='%s' status='%s' "
			 "lamp=%.0f relics=%d inExit=%d"),
		Index, Now, Contacted.Num(), *ReadTallyRaw(), *ReadStatus(),
		LampBrightness(), Present, HeroInExit(kFixtureExitMarginCm) ? 1 : 0);
}

void ACollectThenExitFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}

	// Identity by POSSESSION for the hero, by TAG for everything placed.
	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no possessed player character in the arena"));
		return;
	}
	TArray<AActor*> Relics, Exits, Boards;
	if (!ResolveByTag(TEXT("ArenaRelic"), 4, Relics)) { return; }
	if (!ResolveByTag(TEXT("ArenaExit"), 1, Exits)) { return; }
	if (!ResolveByTag(TEXT("ArenaBoard"), 1, Boards)) { return; }
	Exit = Exits[0];
	Board = Boards[0];

	if (FindText(Board.Get(), TEXT("TallyText")) == nullptr
		|| FindText(Board.Get(), TEXT("StatusText")) == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the signboard is missing TallyText or "
				 "StatusText, so the run has no readouts to judge"));
		return;
	}
	{
		TArray<ULightComponent*> Lamps;
		bool bFound = false;
		Exit->GetComponents<ULightComponent>(Lamps);
		for (ULightComponent* L : Lamps)
		{
			bFound |= (L != nullptr && L->GetName() == TEXT("ExitLamp"));
		}
		if (!bFound)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the exit has no ExitLamp component, so "
					 "there is no lamp readout to judge"));
			return;
		}
	}

	// Which relic is which, for the ROUTE only, by authored position.
	AActor* const A = NearestRelic(Relics, kRelicA);
	AActor* const B = NearestRelic(Relics, kRelicB);
	AActor* const C = NearestRelic(Relics, kRelicC);
	AActor* const S = NearestRelic(Relics, kSpareAt);
	if (A == nullptr || B == nullptr || C == nullptr || S == nullptr
		|| A == B || A == C || A == S || B == C || B == S || C == S)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the four relics are not at the four authored "
				 "spots, so the walk route cannot be built"));
		return;
	}
	Required = {A, B, C};
	Spare = S;
	SpareStart = S->GetActorLocation();

	const FVector ExitAt(kExitAt.X, kExitAt.Y, 0.0);
	const FVector PA = A->GetActorLocation();
	const FVector PB = B->GetActorLocation();
	const FVector PC = C->GetActorLocation();
	// Eight legs, each released by the checkpoint that graded the previous one, so
	// the next observable is never reached before the current one has been judged.
	Legs.Empty();
	Legs.Add({{ExitAt}});                                          // 1 sealed exit
	Legs.Add({{PA}});                                              // 2 relic A
	Legs.Add({{PA + FVector(0.0, 300.0, 0.0), PA}});                // 3 off and back
	Legs.Add({{PB}});                                              // 4 relic B
	Legs.Add({{ExitAt}});                                          // 5 sealed again
	Legs.Add({{PC}});                                              // 6 relic C
	Legs.Add({{ExitAt}});                                          // 7 open exit
	Legs.Add({{ExitAt - FVector(500.0, 0.0, 0.0), ExitAt}});        // 8 out and back

	SetCheckpointSchedule({0.7, 5.0, 8.4, 10.6, 13.8, 16.4, 18.5, 20.6, 23.8});
}

void ACollectThenExitFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base first: checkpoint clock + timeout machinery

	if (!IsRunning() || !Hero.IsValid() || !Exit.IsValid() || !Board.IsValid())
	{
		return;
	}

	// DRIVE. One leg at a time, re-applied every frame because input is consumed
	// per frame -- the same path a human's WASD drives.
	if (Legs.IsValidIndex(ActiveLeg) && Legs[ActiveLeg].bActive)
	{
		FLeg& Leg = Legs[ActiveLeg];
		if (Leg.Waypoints.IsValidIndex(Leg.Next))
		{
			const FVector Here = Hero->GetActorLocation();
			const FVector Target = Leg.Waypoints[Leg.Next];
			const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
			if (Flat.Size2D() <= kWaypointReachedCm)
			{
				++Leg.Next;
			}
			else
			{
				Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
			}
		}
		else
		{
			Leg.bActive = false;
		}
	}

	// COUNT -- a SET of distinct relics, so array order cannot change a verdict.
	for (const TWeakObjectPtr<AActor>& R : Required)
	{
		AActor* const Relic = R.Get();
		if (Relic == nullptr)
		{
			continue;
		}
		if (FVector::Dist2D(Hero->GetActorLocation(), Relic->GetActorLocation())
			<= kFixtureContactCm)
		{
			Contacted.Add(R);
		}
	}
	const int32 Taken = Contacted.Num();

	const double Lamp = LampBrightness();
	const FString Status = ReadStatus();
	if (Lamp > 0.0) { bLampWasLit = true; }
	if (Status == TEXT("ESCAPED")) { bEverEscaped = true; }
	if (HeroInExit(kFixtureExitMarginCm)) { bHeroEnteredExit = true; }

	// CONTINUOUS GUARDS, every frame, all on FIXTURE-owned truth.
	if (Taken < kRequired && Lamp > 0.0)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ExitStaysSealedUntilThird: the exit lit up before the third relic "
				 "was gathered (lamp %.0f with %d relic(s) walked into)"),
			Lamp, Taken));
		return;
	}
	if (Status == TEXT("ESCAPED") && !bHeroEnteredExit)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("WinNeedsAnEntry: the run was won without walking into an open exit"));
		return;
	}
	if (ReadTally() > Taken)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TallyNeverOverCounts: the tally counted more relics than were "
				 "walked into (face reads %d, %d walked into)"),
			ReadTally(), Taken));
		return;
	}
	if (bLampWasLit && Lamp <= 0.0)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("ExitNeverReseals: the exit re-sealed after opening"));
		return;
	}
	if (bEverEscaped && Status != TEXT("ESCAPED"))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("WinPersists: the win did not persist (status reads '%s' after "
				 "reading ESCAPED)"), *Status));
		return;
	}
	{
		AActor* const S = Spare.Get();
		const bool bMoved = (S != nullptr)
			&& FVector::Dist(S->GetActorLocation(), SpareStart) > kSpareMoveCm;
		if (!VisiblyPresent(S) || bMoved)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("SpareRelicSurvives: the relic nobody walked into did not "
					 "survive the run"));
			return;
		}
	}
}

void ACollectThenExitFunctionalTest::OnCheckpoint(int32 Index, double TimeSeconds)
{
	if (!Hero.IsValid() || !Exit.IsValid() || !Board.IsValid())
	{
		return;
	}
	LogCalib(Index, TimeSeconds);

	const int32 Taken = Contacted.Num();
	const int32 Tally = ReadTally();
	const FString Status = ReadStatus();
	const double Lamp = LampBrightness();

	// Every checkpoint gauges the control and the tally against fixture truth.
	if (Tally != Taken)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TallyMatchesWalkIns: the tally face read '%s' with %d relic(s) "
				 "walked into (a blank face reads as nothing at all)"),
			*ReadTallyRaw(), Taken));
		return;
	}

	switch (Index)
	{
	case 0:
		if (Status != TEXT("SEALED") || Lamp > 0.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ArenaStartsSealed: the arena did not start sealed and dark "
					 "(status '%s', lamp %.0f)"), *Status, Lamp));
			return;
		}
		for (const TWeakObjectPtr<AActor>& R : Required)
		{
			if (!VisiblyPresent(R.Get()))
			{
				FinishTest(EFunctionalTestResult::Failed,
					TEXT("AllRelicsStandAtStart: a relic was already missing when "
						 "play began"));
				return;
			}
		}
		ReleaseLeg(0);
		break;

	case 1:
		if (Lamp > 0.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("FirstSealedContactStaysDark: the exit was already lit on the "
					 "first sealed contact (lamp %.0f)"), Lamp));
			return;
		}
		if (Status == TEXT("ESCAPED"))
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("FirstSealedContactDoesNotWin: the first sealed contact won "
					 "the run"));
			return;
		}
		ReleaseLeg(1);
		break;

	case 2:
		if (VisiblyPresent(Required[0].Get()) || Taken != 1 || Status != TEXT("SEALED")
			|| Lamp > 0.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("FirstRelicConsumedAndCounted: the first relic was not consumed "
					 "and counted (still present %d, taken %d, status '%s', lamp "
					 "%.0f)"),
				VisiblyPresent(Required[0].Get()) ? 1 : 0, Taken, *Status, Lamp));
			return;
		}
		ReleaseLeg(2);
		break;

	case 3:
		if (Tally != 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ReTouchCountsNothing: walking back over a gathered relic "
					 "counted it again (face reads '%s')"), *ReadTallyRaw()));
			return;
		}
		ReleaseLeg(3);
		break;

	case 4:
		if (VisiblyPresent(Required[1].Get()) || Taken != 2 || Status != TEXT("SEALED")
			|| Lamp > 0.0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SecondRelicConsumedAndCounted: the second relic was not "
					 "consumed and counted (still present %d, taken %d, status '%s', "
					 "lamp %.0f)"),
				VisiblyPresent(Required[1].Get()) ? 1 : 0, Taken, *Status, Lamp));
			return;
		}
		ReleaseLeg(4);
		break;

	case 5:
		if (Lamp > 0.0 || Status != TEXT("SEALED"))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SecondSealedContactStaysSealed: the exit opened on the second "
					 "sealed contact, two relics in (status '%s', lamp %.0f)"),
				*Status, Lamp));
			return;
		}
		if (Status == TEXT("ESCAPED"))
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("SecondSealedContactDoesNotWin: the second sealed contact won "
					 "the run"));
			return;
		}
		ReleaseLeg(5);
		break;

	case 6:
		if (VisiblyPresent(Required[2].Get()) || Taken != kRequired
			|| Status != TEXT("OPEN") || Lamp < kLitIntensity)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ThirdRelicOpensExit: the exit did not open when the third "
					 "relic was gathered (still present %d, taken %d, status '%s', "
					 "lamp %.0f, the level asks for %.0f)"),
				VisiblyPresent(Required[2].Get()) ? 1 : 0, Taken, *Status, Lamp,
				kLitIntensity));
			return;
		}
		if (Status == TEXT("ESCAPED"))
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("OpeningAloneDoesNotWin: opening the exit won the run without "
					 "an entry"));
			return;
		}
		ReleaseLeg(6);
		break;

	case 7:
		if (Status != TEXT("ESCAPED") || Lamp < kLitIntensity || Tally != kRequired)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("EnteringOpenExitWins: walking into the open exit did not win "
					 "the run (status '%s', lamp %.0f, face '%s')"),
				*Status, Lamp, *ReadTallyRaw()));
			return;
		}
		ReleaseLeg(7);
		break;

	case 8:
		if (Status != TEXT("ESCAPED") || Lamp < kLitIntensity || Tally != kRequired)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("WinSurvivesLeavingAndReturning: the win did not survive "
					 "leaving the exit and re-entering it (status '%s', lamp %.0f, "
					 "face '%s')"), *Status, Lamp, *ReadTallyRaw()));
			return;
		}
		if (!VisiblyPresent(Spare.Get())
			|| FVector::Dist(Spare->GetActorLocation(), SpareStart) > kSpareMoveCm)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("SpareRelicStandsAtTheEnd: the relic nobody walked into was "
					 "gone by the end of the run"));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded,
			TEXT("three relics gathered, the exit opened and the run was won and "
				 "stayed won, with the fourth relic untouched"));
		break;

	default:
		break;
	}
}
