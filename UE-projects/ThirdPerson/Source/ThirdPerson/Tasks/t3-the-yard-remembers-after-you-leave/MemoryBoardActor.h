// Copyright CraftBench. All Rights Reserved.
//
// A counter board for task t3-the-yard-remembers-after-you-leave. Everything the board
// needs to STAND by the gate and to SHOW one number is supplied and working: the post,
// the board, and the one call that writes it. It counts nothing, it remembers nothing,
// and it has never heard of a post.
//
// Each yard has a board of its own, and a board belongs to exactly one yard.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MemoryBoardActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AMemoryBoardActor : public AActor
{
	GENERATED_BODY()

public:
	AMemoryBoardActor();

	/** The post the board is nailed to. MOVABLE for the same reason the posts and the
	 *  pads are: the yard takes the board away and puts a fresh one back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UStaticMeshComponent* Mast = nullptr;

	/** The board itself. Written only by ShowTotal. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	UTextRenderComponent* Board = nullptr;

	/** Which yard this board belongs to. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Board")
	FName YardName = NAME_None;

	/** THE DISPLAY. Writes the board and the mirror below in the same breath. The
	 *  wording is the yard's -- "<yard>  banked <N>" -- and only <N> is anybody else's
	 *  business. */
	UFUNCTION(BlueprintCallable, Category = "Board")
	void ShowTotal(int32 Total);

	/** What the board currently reads. Written ONLY by ShowTotal. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Board")
	int32 LastShownTotal = 0;

protected:
	virtual void BeginPlay() override;
};
