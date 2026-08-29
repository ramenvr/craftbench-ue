// Utility routines for task kp-routine-usage-search.
#include "EvalUtilityLibrary.h"

int32 UEvalUtilityLibrary::ComputeChecksum(int32 Value)
{
	// Deterministic mix; no state, no randomness.
	int32 Mixed = Value * 31 + 7;
	Mixed ^= (Mixed << 13);
	Mixed ^= (Mixed >> 5);
	return Mixed;
}

FString UEvalUtilityLibrary::FormatLabel(const FString& Label)
{
	return FString::Printf(TEXT("[%s]"), *Label);
}

float UEvalUtilityLibrary::ClampScore(float Score)
{
	return FMath::Clamp(Score, 0.0f, 100.0f);
}
