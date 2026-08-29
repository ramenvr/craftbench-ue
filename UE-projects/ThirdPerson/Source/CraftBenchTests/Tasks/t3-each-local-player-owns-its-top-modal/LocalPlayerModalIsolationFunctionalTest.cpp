// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-each-local-player-owns-its-top-modal/LocalPlayerModalIsolationFunctionalTest.h"

namespace
{
	const TCHAR* RootClassPath =
		TEXT("/Game/Tasks/t3-each-local-player-owns-its-top-modal/WBP_LocalPlayerModalRoot.WBP_LocalPlayerModalRoot_C");
	const TCHAR* ScreenClassPath =
		TEXT("/Game/Tasks/t3-each-local-player-owns-its-top-modal/WBP_LocalPlayerModalScreen.WBP_LocalPlayerModalScreen_C");
}

TSubclassOf<ULocalPlayerModalRootBase>
ALocalPlayerModalIsolationFunctionalTest::GetRootWidgetClass() const
{
	return LoadClass<ULocalPlayerModalRootBase>(nullptr, RootClassPath);
}

TSubclassOf<ULocalPlayerModalScreenBase>
ALocalPlayerModalIsolationFunctionalTest::GetScreenWidgetClass() const
{
	return LoadClass<ULocalPlayerModalScreenBase>(nullptr, ScreenClassPath);
}

FString ALocalPlayerModalIsolationFunctionalTest::GetSuccessMarker() const
{
	return TEXT("LOCAL-PLAYER-MODAL-PRODUCTION-PASS");
}
