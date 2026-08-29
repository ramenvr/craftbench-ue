# UE 5.8 API audit

The APIs below were statically audited and subsequently compiled, linked, and
exercised by admission/final authoring, cold readback, and functional tests.

Runtime route:

- `UStateTreeComponent` is the engine-owned execution component. The fixture's
  wrapper reads `GetActiveStateNames()` only in `WITH_GAMEPLAY_DEBUGGER`, the
  same configuration used by the Editor functional-test target.
- `USkeletalMeshComponent::LinkAnimClassLayers`,
  `UnlinkAnimClassLayers`, and `GetLinkedAnimLayerInstanceByClass` are public
  Engine APIs in `Components/SkeletalMeshComponent.h`.
- `FStateTreeConditionCommonBase` and `FStateTreeTaskCommonBase` keep signal
  selection and layer lifetime inside StateTree execution rather than in the
  character Tick.

Editor authoring route:

- `UAnimLayerInterfaceFactory` creates the animation-layer interface asset.
  The retained copy lives in the denied map namespace, outside the four-file
  submission overlay; the admission copy lives in its verifier-only namespace.
- `FBlueprintEditorUtils::ImplementNewInterface` creates the declared layer
  implementations on calm and alert Animation Blueprints.
- `UAnimGraphNode_LinkedAnimLayer` supplies the host layer route;
  `UAnimGraphNode_LayeredBoneBlend` preserves the speed-driven locomotion base
  below `spine_01`; the alert implementation uses one additive
  `UAnimGraphNode_ModifyBone` on `hand_r`. Its 18 cm component-space offset is
  evaluated inside the declared upper-body layer; it does not move the Actor,
  replace the main AnimInstance, or touch the locomotion base.
- `UStateTreeFactory`, `UStateTreeComponentSchema`, typed
  `AddConditionWithOuter<T>`/`AddTask<T>`, and
  `UStateTreeEditingSubsystem::CompileStateTree` create and compile the exact
  Calm/Alert asset.

Structural readback traverses only nodes reachable from each AnimGraph output,
checks the compiled linked-node property, exact interface/class references,
StateTree node structs and instance data, and absence of Slot nodes.

Direct dependency audit:

- Runtime: `Engine`, `StateTreeModule`, `GameplayStateTreeModule` already exist
  in `ThirdPerson.Build.cs`.
- Verifier/editor: `StateTreeDeveloper`, `StateTreeEditorModule`, `AnimGraph`,
  `AnimGraphRuntime`, `BlueprintGraph`, `KismetCompiler`, and `UnrealEd` already
  exist in `CraftBenchTests.Build.cs`.
- No shared dependency or plugin edit is requested.

The original spine-roll authoring compiled and linked, but admission round 01
measured only 0.038 cm of live hand displacement. The replacement 18 cm hand
offset then exposed an authoring bug: the shown-by-default Translation pin
overrode the direct node member. The helper now writes the exposed pin default;
five fresh admission legs observed 17.999 cm live displacement and stable lower-
body continuity without threshold changes.
