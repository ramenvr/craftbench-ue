# Reference solution — t0-sanity-bp-log-on-beginplay

The PASS oracle is the Blueprint at `Content/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer.uasset`
(committed binary alongside this note). It is an Actor Blueprint whose EventGraph
wires **Event BeginPlay → Print String("CRAFTBENCH_BP_OK")** (Print to Screen +
Print to Log both at defaults).

## Provenance / validation (2026-07-09, UE 5.8, Windows)

Authored live via the Aura MCP editor tools (`create_assets` → `bp_agent` wired
BeginPlay→PrintString → compiled clean) and **validated in PIE**: spawned into a
level, ran PIE, and the editor log recorded exactly one

```
LogBlueprintUserMessages: [BP_Announcer_C_0] CRAFTBENCH_BP_OK
```

This confirms the L2 fixture's assumptions: Print String routes to
`LogBlueprintUserMessages`, and the token fires exactly once on BeginPlay.

Note: the Aura-driven editor writes to a copy-on-write sandbox
(`Intermediate/Sandboxes/AuraSandbox/Sandbox/Game/...`), not the real `Content/`,
so the base substrate stays clean. The binary here was harvested from that sandbox.

## To re-author reproducibly

Create an Actor Blueprint at `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`, add
`Event BeginPlay → Print String` with In String = `CRAFTBENCH_BP_OK`, compile +
save. ~5 min, 1 `.uasset`, zero C++. Do not place it in a level — the L2 fixture
loads it by path (`/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer.BP_Announcer_C`) and spawns it.
