// Copyright CraftBench. All Rights Reserved.

#include "CatalogRecordTypes.h"

#include "CoreGlobals.h"

FOnCatalogReaderPublished FCatalogReaderReportBridge::Published;

FDelegateHandle FCatalogReaderReportBridge::AddListener(
	const FOnCatalogReaderPublished::FDelegate& Listener)
{
	return Published.Add(Listener);
}

void FCatalogReaderReportBridge::RemoveListener(const FDelegateHandle Handle)
{
	Published.Remove(Handle);
}

void FCatalogReaderReportBridge::Publish(ACatalogReaderActor* Reader)
{
	Published.Broadcast(Reader, GFrameCounter);
}
