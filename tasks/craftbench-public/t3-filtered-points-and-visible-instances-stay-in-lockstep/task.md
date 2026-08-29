---
id: t3-filtered-points-and-visible-instances-stay-in-lockstep
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: World & Streaming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_FilteredPointInstances :: AFilteredPointInstancesFunctionalTestA", "L_FilteredPointInstances :: AFilteredPointInstancesFunctionalTestB"]
introspect: [t3_filtered_points_visible_instances.py]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-filtered-points-and-visible-instances-stay-in-lockstep/PCG_FilteredPointInstances.uasset]
---

# t3-filtered-points-and-visible-instances-stay-in-lockstep

> **AUTHORED / PRODUCTION REFERENCE PASS.** Pinned UE 5.8 evidence proves
> deterministic scheduled PCG generation, Graph Output capture, managed-instance
> enumeration, an independently cold-read production map and graph, exact
> L1/L2/L2I reference success, and named baseline rejection without manual world
> or graph ticking.

Keep filtered points and visible instances in lockstep

## Primary concept

- `pcg-graph-runtime-generation` - PCG Graph runtime generation

### Composed concepts

- `pcg-point-metadata-filtering` - point metadata and density filtering
- `pcg-managed-static-mesh-output` - PCG-managed ISM/HISM output
- `ps-components` - actor-owned components and world-varying instance parameters

### Production-pattern justification

Procedural placement commonly separates selection from representation: graph
logic chooses a stable set of points, then a managed spawner materializes those
points. Correctness depends on the two products remaining identical as graph
parameters, seed, bounds, and metadata change. Checking only output points or
only visible instances would accept a broken production pipeline.

### Concept-interaction notes

The protected map supplies stable point IDs, transforms, density, an `Excluded`
flag, a bounded generation volume, a mesh, component seed, and a live
`MinDensity` override. The verifier changes all load-bearing values between two
fixtures. It reads the completed engine graph output and PCG-managed
ISM/HISM resources independently, then joins them by stable ID and transform.

## Prompt given to the agent

> Complete the supplied PCG Graph. Keep exactly the supplied input points that
> are inside the supplied volume, are not exclusion-marked, and have density at
> least the component's live `MinDensity` parameter. Publish every retained
> point through Graph Output and spawn one supplied mesh instance at the same
> transform for every published point.
>
> The level changes component seed, threshold, volume bounds, point IDs,
> densities, exclusion flags, and transforms. Read the supplied data and graph
> parameter rather than using literal IDs, counts, positions, or a fixed seed.
> Do not place instances manually, keep hidden rejected instances, publish a
> different branch than the spawner consumes, or replace PCG output with a
> Blueprint construction script.
>
> Edit only
> `Content/Tasks/t3-filtered-points-and-visible-instances-stay-in-lockstep/PCG_FilteredPointInstances`.
> Do not edit the level, source-point assets, PCG components, volume, mesh,
> project configuration, native source, tests, or verifier assets.

## Workspace state pre-task

- The planned editable deliverable is exactly one compiled `UPCGGraph` asset:
  `Content/Tasks/t3-filtered-points-and-visible-instances-stay-in-lockstep/PCG_FilteredPointInstances.uasset`.
- The planned protected map is
  `Content/Maps/t3-filtered-points-and-visible-instances-stay-in-lockstep/L_FilteredPointInstances.umap`.
- The map will own the exact PCG components, point providers, generation volume,
  mesh, fixture, and policy data. Those packages are not editable deliverables.
- The baseline graph will have valid input and output surfaces but no reachable
  filtering or spawning implementation. The world will remain loadable and the
  fixture will be able to establish its own input oracle.

## Verifier specification

This is the intended production contract, not an admission result.

L1 builds `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64
Development`, loads the exact graph, and requires a current PCG graph asset plus
an exact one-file task inventory.

L2 runs exactly two fixture subclasses in fresh fixed-60-Hz NullRHI PIE worlds.
Each fixture captures one world-time epoch and triggers ordinary scheduled PCG
generation exactly once after installing its protected source data and graph
overrides. It never manually ticks the world, PCG subsystem, component, graph,
managed resources, or render components.

Before grading, the fixture requires the PCG plugin, exact component and graph
identity, a completed generation task, one protected input point set, one live
`MinDensity` override, exact volume bounds, and independently readable graph
output plus managed instance resources. Failure is `HARNESS-PRECONDITION`, not a
candidate verdict.

For every input point, the fixture computes the protected oracle from bounds,
`Excluded`, density, and the live threshold. It then records stable ID, density,
flag, input transform, output membership, output transform, spawned membership,
spawned transform, managed-resource identity, and duplicate counts. Fixture B
changes seed, threshold, bounds, eligible set, and transforms while preserving
the same mechanism.

Fixed L2 denominator: exactly six named gates.

1. `BelowThresholdPointsRejected`
2. `ExclusionMarkedPointsRejected`
3. `AllEligiblePointsRetained`
4. `EligiblePointsNotDuplicated`
5. `SpawnCountMatchesFilteredOutput`
6. `SpawnTransformsMatchFilteredPoints`

L2I has a fixed denominator of exactly three checks.

1. `UsesMetadataDrivenDualFilter` - the reachable graph reads the live threshold
   and exclusion metadata on the candidate path; literal point IDs or a fixed
   count cannot decide membership.
2. `PublishesAndSpawnsTheSameFilteredBranch` - one reachable filtered point
   branch feeds both Graph Output and the exact static-mesh spawner, with no
   second unfiltered or independently transformed branch.
3. `SubmissionHasNoInstanceSubstitute` - the accepted-files manifest and Asset
   Registry inventory contain only the exact graph; no map, actor Blueprint,
   construction script, mesh, point data, config, or extra asset is submitted.

Pass requires L1, L2 6/6, and L2I 3/3. Admission-only setup gates never increase
the production denominator.

## Reference solution metadata

- Planned native LOC: 0.
- Planned assets edited: exactly 1 PCG Graph.
- Expected graph size: approximately 18-32 nodes, including parameter access,
  bounds/metadata filtering, Graph Output, and one static-mesh spawning branch.
- Senior developer estimate: 10-16 hours after the engine admission seam is
  proven, including two-policy runtime verification.

## Anti-gaming notes

1. Fixed instances fail changed IDs, transforms, threshold, bounds, and seed.
2. Density-only filtering retains exclusion-marked controls.
3. Exclusion-only filtering retains below-threshold controls.
4. Hiding rejected instances fails managed-resource and instance cardinality.
5. Publishing filtered points while spawning an unfiltered branch fails the
   exact stable-ID/transform join.
6. Duplicated eligible points fail per-ID and per-transform multiplicity.
7. Construction-script or manually placed meshes fail the exact task inventory,
   graph reachability, and PCG-managed-resource identity.
8. Candidate-authored telemetry is never used as the oracle.

## Hidden invariants

- Fixture policies vary threshold, seed, volume, eligible cardinality, IDs,
  density margins, exclusion placement, and transforms.
- Every policy includes an inside/below-threshold point, an inside/excluded
  point, an outside/otherwise-eligible point, and multiple eligible controls.
- At least one density lies just above and one just below the live threshold;
  equality is an eligible boundary case.
- Stable IDs are non-contiguous and unrelated to point order or transform.
- Output and instances are joined with a fixture-owned tolerance after proving
  every transform finite; counts alone never pass.
- Generation completion comes from the engine task/component state after world
  time advances. Sleeps and manual tick pumps are outside grading.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
