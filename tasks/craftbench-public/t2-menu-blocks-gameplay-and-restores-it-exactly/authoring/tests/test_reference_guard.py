"""Offline positive/negative contract tests for the baseline graph guard."""
from dataclasses import dataclass
from pathlib import Path
import unittest


SOURCE = (
    Path(__file__).resolve().parents[5] / "UE-projects" / "ThirdPerson" /
    "Source" / "CraftBenchTests" / "Tasks" /
    "t2-menu-blocks-gameplay-and-restores-it-exactly" /
    "MenuInputAssetAuthoring.cpp")
EXPECTED = frozenset(("PreConstruct", "Construct", "Tick"))


@dataclass(frozen=True)
class Node:
    kind: str
    name: str = ""
    linked: bool = False
    override: bool = True
    custom: bool = False
    internal: bool = False
    disabled: bool = True
    user_enabled: bool = False


def accepts(nodes):
    observed = set()
    for node in nodes:
        if node.linked:
            return False
        if node.kind == "event":
            if (node.name not in EXPECTED or node.name in observed or
                    not node.override or node.custom or node.internal or
                    not node.disabled or node.user_enabled):
                return False
            observed.add(node.name)
        elif node.kind == "k2":
            return False
    return observed == EXPECTED


class ReferenceGuardTests(unittest.TestCase):
    def test_exact_factory_default_events_pass(self):
        self.assertTrue(accepts([
            Node("event", "PreConstruct"),
            Node("event", "Construct"),
            Node("event", "Tick"),
        ]))

    def test_connected_or_behavior_nodes_fail(self):
        defaults = [
            Node("event", "PreConstruct"),
            Node("event", "Construct"),
            Node("event", "Tick"),
        ]
        self.assertFalse(accepts(defaults + [Node("k2", "CallFunction")]))
        self.assertFalse(accepts([
            Node("event", "PreConstruct", linked=True), *defaults[1:]]))

    def test_wrong_duplicate_or_user_changed_event_fails(self):
        self.assertFalse(accepts([
            Node("event", "PreConstruct"), Node("event", "Construct"),
            Node("event", "Construct")]))
        self.assertFalse(accepts([
            Node("event", "PreConstruct"), Node("event", "Construct"),
            Node("event", "CustomEvent")]))
        self.assertFalse(accepts([
            Node("event", "PreConstruct"), Node("event", "Construct"),
            Node("event", "Tick", user_enabled=True)]))

    def test_cpp_guard_contains_all_load_bearing_checks(self):
        source = SOURCE.read_text(encoding="utf-8")
        for token in (
                "ValidateEmptyBaselineEvent", 'TEXT("PreConstruct")',
                'TEXT("Construct")', 'TEXT("Tick")', "bOverrideFunction",
                "CustomFunctionName.IsNone()", "bInternalEvent",
                "GetDesiredEnabledState() != ENodeEnabledState::Disabled",
                "HasUserSetTheEnabledState()", "!NodePin->LinkedTo.IsEmpty()",
                "Node->IsA<UK2Node>()",
                "ObservedBaselineEvents.Num() == ExpectedBaselineEvents.Num()",
                "ObservedBaselineEvents.Contains(ExpectedEvent)"):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
