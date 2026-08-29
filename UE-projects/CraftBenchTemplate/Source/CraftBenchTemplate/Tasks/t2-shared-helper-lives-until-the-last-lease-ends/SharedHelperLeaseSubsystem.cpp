// Copyright CraftBench. All Rights Reserved.
//
// Empty behavior scaffold for task
// t2-shared-helper-lives-until-the-last-lease-ends. The agent supplies the
// cache/lease lifetime behavior; the verifier supplies all live inputs.

#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.h"

USharedHelperLease* USharedHelperLeaseSubsystem::AcquireLease(
	UObject* Owner,
	FName Key,
	int32 Version,
	const FString& Payload)
{
	return nullptr;
}

bool USharedHelperLeaseSubsystem::ReleaseLease(USharedHelperLease* Lease)
{
	return false;
}
