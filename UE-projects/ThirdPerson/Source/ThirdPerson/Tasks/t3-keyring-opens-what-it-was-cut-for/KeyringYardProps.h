// Copyright CraftBench. All Rights Reserved.
//
// The three props the yard is built out of, for task t3-keyring-opens-what-it-was-cut-for.
// Everything they need to SHOW what has happened is supplied and working: a stand can
// hand its key over, a bay's panel can slide aside, and the board can be told what to
// show. Nothing in here decides WHEN any of that should happen.
//
// Read off the props, never guessed:
//   AKeyStandActor::KeyCategory        what that one key is cut for. The yard re-cuts
//                                      its six keys before you arrive and the six names
//                                      are not the same twice.
//   ADoorBayActor::WantsCategory       what that bay is painted with.
//   ADoorBayActor::AlsoWantsCategory   the second category, on the ONE bay that has one;
//                                      NAME_None on the other six.
//   *::MatRadiusUu                     how far that prop's own painted mat reaches from
//                                      the middle, measured ON THE GROUND. Stand mats and
//                                      bay mats are not the same size.
//
// THESE NAMES AND THE THREE COMPONENT TAGS ("Key", "Panel", "Sign") ARE THE CONTRACT THE
// YARD READS THE PROPS THROUGH. Add whatever you like on top of them; renaming, retyping
// or un-tagging one is a failed shift, not a free pass.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "KeyringYardProps.generated.h"

class UMaterialInterface;
class USceneComponent;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

/**
 * A post with one key floating above it and a lamp that is lit while the key is still
 * there. Six of these stand in the yard, all the same class, each cut for its own
 * category.
 */
UCLASS()
class THIRDPERSON_API AKeyStandActor : public AActor
{
	GENERATED_BODY()

public:
	AKeyStandActor();

	/** Root, at floor level in the middle of this stand's mat. Everything else hangs
	 *  off it unscaled, so every relative number below is in world units. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Key Stand")
	USceneComponent* Mount = nullptr;

	/** The post. Solid: it is a prop and it blocks. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Key Stand")
	UStaticMeshComponent* Post = nullptr;

	/** The key itself, floating above the post. ComponentTag "Key". */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Key Stand")
	UStaticMeshComponent* Key = nullptr;

	/** Lit while the stand still holds its key, dark once it does not. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Key Stand")
	UPointLightComponent* Lamp = nullptr;

	/** What THIS key is cut for. Read it off the stand -- the yard re-cuts all six
	 *  before the shift starts and no two stands carry the same one. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Key Stand")
	FName KeyCategory = NAME_None;

	/** How far THIS stand's mat reaches from the middle, on the ground. Bay mats are
	 *  a different size; read each one off the thing it belongs to. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Key Stand")
	float MatRadiusUu = 400.0f;

	/** THE HANDOVER. Takes the key off the stand (or puts it back): hides the key mesh
	 *  and puts the lamp out. Idempotent -- calling it with the same value twice
	 *  changes nothing, so a per-frame caller cannot walk the state anywhere. */
	UFUNCTION(BlueprintCallable, Category = "Key Stand")
	void SetKeyTaken(bool bNewKeyTaken);

	UFUNCTION(BlueprintPure, Category = "Key Stand")
	bool IsKeyTaken() const { return bKeyTaken; }

protected:
	virtual void BeginPlay() override;

private:
	bool bKeyTaken = false;
};

/**
 * A frame with a solid panel across it. Seven of these; six stand in a row down the
 * middle of the yard and one stands inside the walled corner behind the last of them.
 * Each is painted with the category (or, on exactly one of them, the two categories) it
 * will open for.
 */
UCLASS()
class THIRDPERSON_API ADoorBayActor : public AActor
{
	GENERATED_BODY()

public:
	ADoorBayActor();

	/** Root. Carries the two frame posts, the panel and the lamp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door Bay")
	USceneComponent* Frame = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door Bay")
	UStaticMeshComponent* PostA = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door Bay")
	UStaticMeshComponent* PostB = nullptr;

	/** The panel across the frame. ComponentTag "Panel". BlockAll while shut. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door Bay")
	UStaticMeshComponent* Panel = nullptr;

	/** Red while shut, green once open. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door Bay")
	UPointLightComponent* Lamp = nullptr;

	/** The category this bay is painted with. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door Bay")
	FName WantsCategory = NAME_None;

	/** The SECOND category, on the one bay that is painted with two. NAME_None on the
	 *  other six -- a bay with no second category asks for nothing extra. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door Bay")
	FName AlsoWantsCategory = NAME_None;

	/** How far THIS bay's mat reaches from the middle, on the ground. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door Bay")
	float MatRadiusUu = 760.0f;

	/** How far the panel travels when the bay opens. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door Bay")
	float SlideUu = 800.0f;

	/** THE OPENING. Slides the panel aside, drops its collision so a body can walk
	 *  through the frame, and turns the lamp from red to green (or puts all three back).
	 *  The panel is SET to its open pose, never nudged, so calling this every frame
	 *  leaves it exactly where one slide puts it. */
	UFUNCTION(BlueprintCallable, Category = "Door Bay")
	void SetOpen(bool bNewOpen);

	UFUNCTION(BlueprintPure, Category = "Door Bay")
	bool IsOpen() const { return bOpen; }

	/** Where the panel sits in the frame's own space while the bay is shut. The open
	 *  pose is this plus SlideUu along the frame's local X. */
	UFUNCTION(BlueprintPure, Category = "Door Bay")
	FVector PanelShutRelative() const;

protected:
	virtual void BeginPlay() override;

private:
	bool bOpen = false;
};

/**
 * The board by the gate. It shows whatever it is handed and nothing else: it does not
 * sort, it does not throw duplicates away, and it does not know that keys or bays exist.
 */
UCLASS()
class THIRDPERSON_API ARingBoardActor : public AActor
{
	GENERATED_BODY()

public:
	ARingBoardActor();

	/** Root, at floor level. The slab and the face hang off it as siblings so the face
	 *  does not inherit the slab's non-uniform scale. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ring Board")
	USceneComponent* Mount = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ring Board")
	UStaticMeshComponent* Board = nullptr;

	/** The face. ComponentTag "Sign". Ships reading "--". */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ring Board")
	UTextRenderComponent* Sign = nullptr;

	/** THE READOUT. Writes the categories onto the face, joined with ", ", in exactly
	 *  the order they are handed over. An empty array renders "--". It does NOT sort and
	 *  it does NOT de-duplicate: hand it the same category three times and the board
	 *  says so. */
	UFUNCTION(BlueprintCallable, Category = "Ring Board")
	void ShowRing(const TArray<FName>& CategoriesInOrder);

	/** Whatever the face reads right now. */
	UFUNCTION(BlueprintPure, Category = "Ring Board")
	FString CurrentReadout() const;

protected:
	virtual void BeginPlay() override;
};
