// Copyright CraftBench. All Rights Reserved.
//
// A post for task t3-the-yard-remembers-after-you-leave. Everything the post needs to
// STAND on the floor, to SHOW the number painted over it, and to be TAKEN OUT of the
// yard is supplied and working: the pillar, the painted patch of ground underneath it,
// the number above it, the patch of ground that notices somebody walking in, and the
// two calls that write what a person sees. Nothing here decides that a post has been
// taken, what that is worth, or what should be remembered about it.
//
// The yard holds several of these and they are not alike: each carries its own name and
// its own number, and the yard repaints those numbers whenever it opens. Read them off
// the post you are actually dealing with -- one number does not fit five posts, and the
// number a post carried yesterday is not the number it carries today.
//
// The patch of ground is a trigger volume with NO handler bound. It is set up the way
// every other trigger in this substrate is set up (query-only + overlap-everything +
// overlap events on), and it stays live whether the post is standing or gone -- so
// walking back over ground a post used to occupy is something a person can do, and
// something somebody has to decide what to do about.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MemoryPostActor.generated.h"

class UBoxComponent;
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
	 *  inside it. Overlap-only, overlap events ON, NOTHING BOUND TO IT, and never
	 *  switched off. */
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
	 *  where it stands, not by what order it is found in. The yard moves its posts
	 *  around whenever it opens. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	FName PostId = NAME_None;

	/** The number painted over this post RIGHT NOW: what it is worth to whoever takes
	 *  it. The yard repaints it whenever the yard opens, so it is never yours to
	 *  write, and the number it carried before is not the number it carries now. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Post")
	int32 WorthNow = 0;

	/** THE DISPLAY for the number. Writes the sign above the post and, in the same
	 *  breath, the mirror below, so what a person reads off the sign and what a tool
	 *  reads off the actor are the same number by construction.
	 *
	 *  The wording is the yard's. Only the number is anybody else's business: a sign
	 *  that says something other than
	 *      "<post>  worth <W>"
	 *  is a sign a person cannot read the same way twice. */
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
};
