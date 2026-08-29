// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseAssets.h"

FPrimaryAssetId UBundleLeaseRecord::GetPrimaryAssetId() const
{
	return FPrimaryAssetId(FPrimaryAssetType(TEXT("BundleLeaseRecord")), GetFName());
}
