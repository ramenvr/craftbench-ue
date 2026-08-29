// Copyright CraftBench. All Rights Reserved.

#include "RenderProbeFunctionalTest.h"

#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

FString ARenderProbeFunctionalTest::ScreenshotPath() const
{
	return FPaths::ConvertRelativePathToFull(
		FPaths::ProjectSavedDir() / TEXT("CraftBench/l3_renderprobe.png"));
}

void ARenderProbeFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	// Capture after the scene has rendered a few PIE frames, then assert after the
	// async screenshot has flushed (PIE keeps ticking between checkpoints).
	SetCheckpointSchedule({0.25, 0.6});
}

void ARenderProbeFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (CheckpointIndex == 0)
	{
		// Stock-UE PIE viewport screenshot (NOT Aura). Async — it fulfils on a
		// later rendered frame; we assert at the next checkpoint once it has flushed.
		const FString Path = ScreenshotPath();
		IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), /*Tree=*/true);
		IFileManager::Get().Delete(*Path, /*RequireExists=*/false);
		FScreenshotRequest::RequestScreenshot(Path, /*bShowUI=*/false, /*bAddFilenameSuffix=*/false);
		UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH-L3 requested screenshot: %s"), *Path);
	}
	else
	{
		const bool bWritten = IFileManager::Get().FileExists(*ScreenshotPath());
		AssertTrue(bWritten, FString::Printf(TEXT("screenshot_written: %s"), *ScreenshotPath()));
		UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH-L3 screenshot written=%d at %s"),
			bWritten ? 1 : 0, *ScreenshotPath());
	}
}
