# Authoring notes

Status: **AUTHORED; REFERENCE PASS / EMPTY FAIL DISCRIMINATION PROVEN.**
Editor and Game builds are green. Admission passed three consecutive exact-one
rounds after the verifier stopped using generator-active tile counts for loaded
static nav data and the verifier-owned marker supplied an exact navigable goal
location. The empty final assets, retained final map, and exact two-package
reference were authored and independently cold-read. Production reference
passed L1/L2/L2I; the byte-identical empty baseline passed L1 and failed at the
intended decision-topology gates.

## Contract frozen for the first build

- Submission surface: exact `BB_GuardPatrolChase` and `BT_GuardPatrolChase` packages only.
- Verifier-owned world: character, AI controller, alert source, moving target, two marker actors, navigation, fixture, and map.
- Supplied Blackboard keys: `AlertActive` Boolean, `LiveTarget` Actor object, and `PatrolPoint` Actor object. UE 5.8's engine-owned persistent `SelfActor` Actor key is also serialized and is not part of the writable task surface.
- Decision topology: root selector; first chase sequence decorated on `AlertActive == true` with observer abort `Both`; second infinite-loop patrol sequence; chase uses Move To `LiveTarget`; patrol selects then Move To `PatrolPoint`.
- No actor Tick owns decisions. The controller reacts to the alert delegate and the engine Behavior Tree owns branch selection.

## UE 5.8 API audit

- `UBehaviorTreeComponent::GetActiveNode()` is public in `BehaviorTreeComponent.h` and exposes the engine-owned executing node.
- `UBTTask_BlackboardBase::GetSelectedBlackboardKey()` is public and identifies whether the active Move To uses `LiveTarget` or `PatrolPoint`.
- `UBTCompositeNode::Children`, `FBTCompositeChild::Decorators`, `UBehaviorTree::RootNode`, and `UBehaviorTree::BlackboardAsset` are public reflected runtime structures suitable for independent inspection.
- Editable graphs use `UBehaviorTreeGraph`, `UBehaviorTreeGraphNode_*`, `UEdGraphSchema_BehaviorTree`, and `UAIGraphNode::AddSubNode` from UE 5.8 `BehaviorTreeEditor` and `AIGraph` editor modules.
- `UBehaviorTreeGraph::UpdateAsset()` rebuilds the runtime tree from the editable graph. The helper must not fabricate a runtime-only `RootNode` beside an empty editor graph.
- `FBlueprintEditorUtils::CreateNewGraph` plus `CreateDefaultNodesForGraph` matches `FBehaviorTreeEditor::RestoreBehaviorTree` for initial graph creation.

## Fairness and anti-opt-out

- Admission assets live under `/Game/__CraftBenchAdmission/...`; final task assets live under `/Game/Tasks/...`; the two namespaces are never overwritten in one process.
- Authoring scripts refuse existing exact outputs. A rerun requires an explicit owner-reviewed quarantine, not recursive deletion.
- Cold readback runs in a fresh process and locks package hashes before/after.
- Map and fixture scripts reject final/reference paths during admission.
- The final runner requires exact test enumeration count one and a JSON-authoritative result.

## Evidence ledger

- Static/API audit: complete.
- Lightweight Python AST/contract tests: PASS (`GUARD-STATIC-CONTRACTS-PASS python=17 gates=5 l2i=4`).
- Editor and Game builds: PASS.
- Admission assets: PASS, SHA-256 `E93348DF3AE71B4B494C1DEA096B15471872702163747A48B8BF4072D0C0F138`
  and `BB5E72A875A4BF5409CB59AE3F606A0A6BFC3E56C27555CE2F1BD9F647170216`.
- Admission map/readback: PASS, SHA-256
  `6E874A10C73DBC8BF5D752CEE77B2DE9177AF24544DCB92902F69E04A87197B1`;
  author marker recorded `active_tiles=20`.
- Admission round 1/2 were harness investigations. Rounds 8, 9, and 10 are
  consecutive exact-one Success legs with all five named gates and unchanged
  protected hashes (`<run-out>{8,9}` and
  `...round-10`).
- Empty final baseline hashes: Blackboard
  `C614A865F577E0DFDE2187EF133A0340EF9996260787BEAFDEE39BDD1EE3D774`;
  Behavior Tree
  `2732258C0A74DE60B47184EF217281B24D9BAE82378E813BE1807258A7DC12E6`.
- Retained final map: 65,161 bytes, SHA-256
  `BF2FD8D3D6EAA8A6CE8492F7ABDFE380EA234B8C0636CB3AEE3FDD7CB11171E2`;
  fresh cold readback PASS at
  `<run-out>/readback.log`.
- Reference closure: PASS at
  `<run-out>/closure.json`; reference
  Blackboard SHA `215B3CFCDB3114208E437A9A3BC1A482336AF5E88A83F3D04E9A60861B3E6EBE`
  and Behavior Tree SHA
  `9308B3F4D823F4E1863A4C1A9243F3AF9D380BF02FD8E089042D0A5E6667FCE1`;
  live empty hashes restored exactly.
- Production reference: unified PASS, L1 zero warnings, L2 1/1, L2I 4/4;
  `<run-out>/report.json`.
- Production empty baseline: L1 PASS, L2 exact failure
  `GATE[PrioritySelectorAndDecoratorsAuthored]`, L2I 0/4 with Blackboard
  contract retained and authored topology absent;
  `<run-out>/report.json`.
- Official refgate: pending.

## First shared dependency boundary

No shared file was changed by this task owner. Root single-point merged and
diff-checked the direct private CraftBenchTests dependencies `AIGraph` and
`BehaviorTreeEditor`, because the task-local authoring helper instantiates
exported editor graph types. Both Editor and Game builds are now verified green.
