// Copyright CraftBench. All Rights Reserved.
//
// A post for task t3-the-yard-remembers-after-you-leave. Everything the post needs to
// STAND on the floor, to SHOW the number painted over it, and to be TAKEN OUT of the
// yard is supplied and working: the pillar, the painted patch of ground underneath it,
// the number above it, the patch of ground that notices somebody walking in, and the
// two calls that write what a person sees.
//
// REFERENCE SOLUTION. Against the scaffold this file adds exactly three things: it
// listens to its own patch of ground, it latches so one arrival is one attempt, and it
// tells the keeper (which outlives it) that it exists. Every decision is the keeper's,
// and every answer the keeper gives comes off the record.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MemoryPostActor.generated.h"

class UBoxComponent;
class UPrimitiveComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AMemoryPostActor : public AActor
{
	GENERATED_BODY()

public:
	AMemoryPostActor();

	/** The pillar you can see: 60 x 60 x 240, standing on the floor. Solid while the
	 *  post is standing, and not there at all once it has been taken. MOVABLE on
	 *  purpose -- the yard takes its posts away and puts fresh ones back, and PIE
	 *  scores moving a STATIC actor as a failed test. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	UStaticMeshComponent* Pillar = nullptr;

	/** The painted patch a person sees underfoot, 260 x 260, exactly the footprint of
	 *  the ground volume below. Non-colliding: it is paint, not a step. It stays
	 *  painted after the post has gone, so an empty patch of ground is still somewhere
	 *  a person can see a post once stood. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	UStaticMeshComponent* GroundPlate = nullptr;

	/** The ground around the post: 260 x 260 in plan and 220 tall, sitting on the
	 *  floor, so a walking character's capsule (centre 96 above the floor) is well
	 *  inside it. Overlap-only, overlap events ON, and never switched off. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	UBoxComponent* Ground = nullptr;

	/** The number painted above the post. Written only by ShowWorth. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	UTextRenderComponent* WorthSign = nullptr;

	/** Which yard this post belongs to. Posts in different yards have nothing to do
	 *  with each other. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	FName YardName = NAME_None;

	/** What this post is called. A post is known by this and by nothing else -- not by
	 *  where it stands, not by what order it is found in. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	FName PostId = NAME_None;

	/** The number painted over this post RIGHT NOW: what it is worth to whoever takes
	 *  it. The yard repaints it whenever the yard opens, so it is never yours to
	 *  write. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	int32 WorthNow = 0;

	/** THE DISPLAY for the number. Writes the sign above the post and, in the same
	 *  breath, the mirror below.
	 *
	 *  The wording is the yard's -- "<post>  worth <W>". */
	UFUNCTION(BlueprintCallable, Category = "Post")
	void ShowWorth(int32 Worth);

	/** THE DISPLAY for whether the post is there. Standing means the pillar and its
	 *  number are visible and the pillar is solid; taken means all three are gone and a
	 *  person can walk straight over the patch of ground it stood on. The painted patch
	 *  and the ground volume are untouched either way. */
	UFUNCTION(BlueprintCallable, Category = "Post")
	void ShowStanding(bool bStanding);

	/** What the sign currently reads. Written ONLY by ShowWorth. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	int32 LastShownWorth = 0;

	/** Whether the post is currently shown as standing. Written ONLY by
	 *  ShowStanding. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	bool bLastShownStanding = true;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** ONE attempt per arrival. The engine's begin-overlap is already an edge; the
	 *  latch is what keeps a second capsule, a re-entry inside one frame, or a sweep
	 *  that clips a corner from counting as a second visit. */
	UFUNCTION()
	void OnGroundBegin(UPrimitiveComponent* OverlappedComponent, AActor* Other,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& Sweep);

	UFUNCTION()
	void OnGroundEnd(UPrimitiveComponent* OverlappedComponent, AActor* Other,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	/** Cleared when the runner walks off the patch, so walking back on is a fresh
	 *  arrival -- which the keeper is then free to find worth nothing. */
	bool bRunnerOnGround = false;
};
