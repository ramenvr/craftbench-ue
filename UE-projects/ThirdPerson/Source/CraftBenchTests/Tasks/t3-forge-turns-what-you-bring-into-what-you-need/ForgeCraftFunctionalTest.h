// Copyright CraftBench. All Rights Reserved.
//
// L2 for t3-forge-turns-what-you-bring-into-what-you-need.
//
// A hall with a forge in it, played as a two-step crafting chain against a carry cap.
// The fixture walks the character, and everything the walk produces is graded against
// the fixture's OWN implementation of the rule the prompt states -- never against a
// table of expected strings, so the hall can be re-staged without re-deriving an
// answer key by hand.
//
// THE GAME, in one paragraph. A sign posts how many units the character may have on
// them at once. Two plaques carve a chain: three of the base unit make one of the
// middle unit, three of the middle unit make the one thing at the top. Nine base units
// therefore have to reach the forge, and at a cap of three they cannot arrive in fewer
// than four loads -- and the three middle units the forge sets down on its own
// shelf-stones have to be walked out and carried back in before the top of the chain
// can be made at all. The cap forces the trips; the chain forces the errand.
//
// SIX THINGS ARE LOAD-BEARING HERE:
//
//  1. THE CAP IS READ FROM THE WORLD AND CHANGES. It is posted on a sign as
//     CarryCapUnits, and it is RE-POSTED to a smaller number part way through the run.
//     Everything the cap does is visible on the heaps themselves: walk up to a heap of
//     four with room for three and it keeps one, standing, with its label saying so;
//     walk up to a heap while already full and it is untouched. That per-heap residual
//     is what the cap gates read, so a cap that was cached at BeginPlay says so on the
//     floor of the hall rather than inside an inventory nobody can see.
//
//  2. A PLAQUE IS ONLY KNOWN ONCE THE CHARACTER HAS STOOD AT IT. The fixture models
//     the same known-set the prompt describes: a plaque becomes known when the
//     character comes within its own ReadReachUu, and it goes UNKNOWN again the moment
//     its carving differs from the one that was read. The tier-2 recipe is deliberately
//     left unread until the forge is already holding everything it needs, so "iterate
//     every plaque" makes the top of the chain several seconds early and fails its own
//     named gate.
//
//  3. THE HALL RE-STAGES ITSELF ONCE, with the character standing at the forge. The
//     cap drops, one pad is re-stocked with a material that was not in the hall before,
//     and the tier-1 plaque is re-carved to need that material instead. That single
//     re-stage invalidates four different things a submission might have cached -- the
//     cap, a pad's material, a parsed recipe, and a face that is only written when a
//     craft succeeds -- and it costs one short trip instead of a second full walk.
//
//  4. THE ROUTE IS DERIVED FROM THE LIVE REACHES, and PrepareTest refuses to start
//     unless every sample of every segment is either plainly at the thing it went to or
//     plainly clear of everything else. The lane that gets behind the forge to the
//     shelf-stones is SOLVED, not chosen: it has to be outside the forge's own take
//     reach (or three units would be handed over halfway down it) and clear of every
//     stone's reach (or it would pick up whatever is standing there in passing).
//
//  5. IDENTITY BY TAG, STATE BY REFLECTION. The fixture never includes a scaffold
//     header, so a submission may rename or subclass any of the four actors without
//     breaking the VERIFIER build -- which would score a harness fault as a model
//     failure.
//
//  6. THE SENTINEL. ACraftBenchFunctionalTest declares SUCCESS the moment the last
//     scheduled checkpoint is crossed, so the schedule ends far past the drive and
//     every deferred gate is evaluated AT the sentinel, never after it.
//
// WHAT IS DELIBERATELY *NOT* A PRECONDITION. A delivery whose staged shape depends on
// the submission having made something -- the errand delivery and the top-of-chain
// delivery both need the forge's own output to exist -- is checked SOFTLY and logged,
// never routed to HARNESS-PRECONDITION. The previous design of this task shipped a
// precondition of exactly that shape and it fired on the reference, turning a graded
// run into an attributed one. Shapes that depend only on the hall (the partial
// delivery, the tier-1 deliveries, the epilogue) are still hard preconditions, because
// those can only be lost by an authoring mistake.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "ForgeCraftFunctionalTest.generated.h"

class ACharacter;
class UTextRenderComponent;

UCLASS()
class AForgeCraftFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AForgeCraftFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** What a stop on the walk is for. Transit stops exist only to keep every turn a
	 *  right angle on open floor; they have no dwell and are never graded. */
	enum class EStopKind : uint8 { Transit, Forge, Pad, Plaque, Product };

	/** What a delivery is staged to prove. PrepareTest cannot check these (the holdings
	 *  do not exist yet), so each is asserted AT its delivery. The three that depend
	 *  only on the hall end the run as HARNESS-PRECONDITION when their shape is lost;
	 *  the two that depend on the forge's own output being there are logged and
	 *  otherwise graded like any other delivery. */
	enum class ERole : uint8
	{
		None,
		/** Not enough of anything to make the first step: nothing is spent, nothing is
		 *  made, and what the forge is holding comes out untouched. Hall-only. */
		Partial,
		/** Three of the base unit and two to spare: exactly three go. Hall-only. */
		Tier1,
		/** Everything the top of the chain needs is in the forge and the recipe for it
		 *  has never been read. Depends on the forge's own output -- SOFT. */
		Unread,
		/** Both steps of the chain fit at once and the higher one has to win. Depends
		 *  on the forge's own output -- SOFT. */
		Top,
		/** After the re-stage: a material the hall did not have before, and the tier-1
		 *  recipe re-carved out from under anything that remembered it. Hall-only. */
		Epilogue
	};

	struct FStop
	{
		FVector At = FVector::ZeroVector;
		double Dwell = 0.0;
		EStopKind Kind = EStopKind::Transit;
		int32 Ref = INDEX_NONE;        // pad / plaque index
		ERole Role = ERole::None;      // forge stops only
		/** Errand stops are resolved when the walk reaches them: the forge's own output
		 *  is spawned mid-run, so where it stands is not knowable up front. */
		bool bDeferred = false;
	};

	/** One staged pad. The hall owns where it is and what stands on it; the submission
	 *  owns only how much of it gets taken. */
	struct FPad
	{
		FVector At = FVector::ZeroVector;
		TWeakObjectPtr<AActor> Heap;
		FName StagedId = NAME_None;
		/** What this pad held before the re-stage, kept so a submission still working
		 *  from a material the hall has replaced can be told so by name. */
		FName PreviousId = NAME_None;
		int32 StagedUnits = 0;
		/** THE FIXTURE'S OWN MODEL of what should still be standing here: the staged
		 *  count minus everything the cap allowed the character to carry off. */
		int32 Remaining = 0;
		float Reach = 220.0f;
		bool bApproached = false;
		bool bInReachNow = false;
		/** The residual is not compared while the character is anywhere near the heap,
		 *  nor for kSettleS afterwards. A submission is free to measure "close enough"
		 *  in 3D or off a bounds sphere and so fire a frame or two either side of the
		 *  fixture's own flat test; the window absorbs exactly that. */
		double CompareFrom = 0.0;
		/** The closest the character has EVER been. "You emptied a heap you never
		 *  walked up to" is judged against this and not against the in-reach flag. */
		double ClosestApproachUu = 1.0e9;
	};

	struct FPlaque
	{
		TWeakObjectPtr<AActor> Actor;
		FVector StagedAt = FVector::ZeroVector;
		FString StagedCarving;
		/** The carving as the character last read it, standing close enough. Empty
		 *  means unread. A re-carve makes it stale, and stale is unknown. */
		FString ReadCarving;
		int32 StagedTier = 0;
		double DistToForge = 0.0;
	};

	/** A heap the forge spawned: one standing on no staged pad. Carried under exactly
	 *  the same cap as anything else. */
	struct FProduct
	{
		TWeakObjectPtr<AActor> Actor;
		FName Id = NAME_None;
		/** WHERE IT STOOD and HOW FAR it could be taken from, both remembered rather
		 *  than re-read every frame. DESTROYING a heap is one of the legal ways to
		 *  empty it, and a submission that destroys it a frame before the fixture's
		 *  own flat test fires would otherwise leave the fixture with no location to
		 *  measure against -- it would never model the pickup, and would then fail
		 *  correct work for "a heap you never walked up to". */
		FVector At = FVector::ZeroVector;
		double Reach = 220.0;
		int32 Remaining = 0;
		double SeenAt = -1.0;
		bool bApproached = false;
		bool bInReachNow = false;
		double CompareFrom = 0.0;
		double ClosestApproachUu = 1.0e9;
	};

	struct FDelivery
	{
		int32 Phase = 0;
		int32 IndexInPhase = 0;
		ERole Role = ERole::None;
		double At = -1.0;
		TMap<FName, int32> ExpectedHeld;
		FName ExpectedProduct = NAME_None;
		int32 ExpectedInputs = 0;
		int32 ExpectedTier = 0;
		/** What the SAME rule would have chosen with the whole wall readable. Only ever
		 *  different from ExpectedProduct where the staging says it must be. */
		FName WholeWallProduct = NAME_None;
		bool bSettled = false;
	};

	// ---- staging -------------------------------------------------------------
	bool ResolveHall();
	bool StageHall(int32 PhaseIndex);
	void BuildRoute(int32 PhaseIndex);
	bool SweepRoute();

	// ---- reflection ----------------------------------------------------------
	static FString ReadStr(const AActor* A, const TCHAR* Prop);
	static bool WriteStr(AActor* A, const TCHAR* Prop, const FString& Value);
	static FName ReadName(const AActor* A, const TCHAR* Prop);
	static bool WriteName(AActor* A, const TCHAR* Prop, FName Value);
	static int32 ReadInt(const AActor* A, const TCHAR* Prop, int32 Fallback);
	static bool WriteInt(AActor* A, const TCHAR* Prop, int32 Value);
	static float ReadFloat(const AActor* A, const TCHAR* Prop, float Fallback);
	static UTextRenderComponent* FindText(AActor* On, const TCHAR* Name);
	static FString ReadFace(AActor* On, const TCHAR* Name);
	/** Every way a heap can legitimately be gone from the hall: destroyed, the actor
	 *  hidden, the pile hidden, or simply emptied. The prompt describes an OUTCOME and
	 *  never names a mechanism, so the gate has to accept every mechanism that produces
	 *  it. */
	static bool HeapIsGone(const AActor* Heap);
	/** How many units are standing on a heap right now, with every "gone" mechanism
	 *  reading as zero. */
	static int32 LiveUnits(const AActor* Heap);

	// ---- the world's own answer ---------------------------------------------
	/** The step, every unit the carving lists (repeats included) and the single thing
	 *  they make. Parsed by the FIXTURE from the live CarvedText -- never by calling the
	 *  submission's parser, which would grade the submission against itself. */
	static void ParseCarving(const FString& Carved, int32& OutTier,
		TArray<FName>& OutInputs, FName& OutOutput);
	static bool Contains(const TMap<FName, int32>& Have, const TArray<FName>& Need);
	static FString FormatHeld(const TMap<FName, int32>& Held);
	static bool ParseHeldFace(const FString& Face, TMap<FName, int32>& Out);
	/** The prompt's rule, once: the highest step carved among the recipes it may use
	 *  whose units the holdings cover with multiplicities. bKnownOnly=false asks the
	 *  same question of the WHOLE wall, which is what the read-set gate compares
	 *  against. Returns the chosen plaque index, or INDEX_NONE when nothing fits. */
	int32 ChooseRecipe(const TMap<FName, int32>& Held, bool bKnownOnly,
		int32& OutTier, int32& OutFittingCount) const;
	bool IsKnown(const FPlaque& P) const;
	int32 PlaqueForOutput(FName Output) const;
	int32 TierOf(FName Output) const;
	int32 CarriedTotal() const;

	// ---- per-frame -----------------------------------------------------------
	bool ObserveHeaps(double Now);
	void ObservePlaques(double Now);
	bool CheckNothingMoved(double Now);
	void MaybeDeliver(double Now);
	bool CheckDeliveryOutcome(double Now);
	bool CheckFaces(double Now);
	/** Everything the forge set down that belongs to this delivery, counted BY TIME
	 *  rather than by which delivery happened to be the latest when the actor turned
	 *  up. Tick order inside a frame is the engine's to choose: on the frame a delivery
	 *  lands, the submission's own tick may run first and spawn the product BEFORE the
	 *  fixture has recorded the delivery, and an incremental counter would then charge
	 *  it to the PREVIOUS delivery and fail correct work. */
	int32 ProductsFor(const FDelivery& D, FName& OutLast) const;
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now);
	void Precondition(const FString& Why);

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Forge;
	TWeakObjectPtr<AActor> Sign;
	UClass* HeapClass = nullptr;
	float ForgeReach = 450.0f;
	FVector ForgeAt = FVector::ZeroVector;
	TArray<FVector> Stones;
	double HeroZ = 0.0;
	/** The lane that gets behind the forge, SOLVED from the forge's own take reach and
	 *  the shelf-stones' own row offset rather than written down. */
	double LaneAbsY = 0.0;

	TArray<FPad> Pads;
	TArray<FPlaque> Plaques;
	TArray<FProduct> Products;
	/** Which plaque carves the first step of the chain and which carves the top, worked
	 *  out from the steps the hall carved rather than from an index. */
	int32 TierOnePlaque = INDEX_NONE;
	int32 TierTwoPlaque = INDEX_NONE;

	/** The cap as the hall has it posted right now, and where the hall posted it. */
	int32 CarryCap = 0;
	FVector SignAt = FVector::ZeroVector;

	TMap<FName, int32> Carried;      // the fixture's model of what the character holds
	TMap<FName, int32> Holdings;     // the fixture's model of what the forge holds
	TArray<FDelivery> Deliveries;

	/** The two faces as the fixture says they should read RIGHT NOW, and when each last
	 *  changed. Both are recomputed every frame: what the forge could make next changes
	 *  when the character walks up to a plaque and when the hall re-carves one, neither
	 *  of which is a delivery. */
	FString WantHeldLine = TEXT("EMPTY");
	FString WantCanLine = TEXT("NOTHING");
	double HeldChangedAt = 0.0;
	double CanChangedAt = 0.0;

	TArray<FStop> Route;
	int32 Waypoint = 0;
	double DwellUntil = -1.0;
	int32 Phase = 0;
	int32 PhasesRun = 1;
	bool bStaging = false;
	/** World time the hall re-staged. */
	double RestagedAt = -1.0;
};
