// Copyright CraftBench. All Rights Reserved.
// Verifier discovery bridge; runtime implementations live in protected ThirdPerson.

#pragma once

#include "Tasks/t3-dash-responds-now-and-converges-later/PredictedDashProtectedTypes.h"

class APredictedDashNetworkFunctionalTestA;
class APredictedDashNetworkFunctionalTestB;

static_assert(TIsDerivedFrom<APredictedDashNetworkFunctionalTestA,
	AFunctionalTest>::IsDerived, "fixture A must remain a FunctionalTest");
static_assert(TIsDerivedFrom<APredictedDashNetworkFunctionalTestB,
	AFunctionalTest>::IsDerived, "fixture B must remain a FunctionalTest");
