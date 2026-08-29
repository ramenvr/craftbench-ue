#pragma once

// The fixture must live in the runtime module because the admission harness
// launches the packaged Game target as a dedicated server and three clients.
// Keep this verifier-side discovery header as the single bridge to that
// runtime declaration; there is no duplicate fixture implementation here.
#include "Tasks/t3-every-player-sees-the-same-door-state/ReplicatedDoorTypes.h"
