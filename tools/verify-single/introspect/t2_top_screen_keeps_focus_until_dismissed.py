"""Read-only L2I grader for t2-top-screen-keeps-focus-until-dismissed.

The fixed denominator is three named checks. Runtime navigation and focus are
graded by AFocusStackFunctionalTest; this script proves only saved Widget
Blueprint parentage, the real activation stack/root-content declaration, and
the exact focusable buttons. Identity is by pre-declared asset path and widget
name, never by generated-class discovery.
"""
import json

try:
    import unreal
except ImportError:  # offline syntax checks
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"

ROOT = "/Game/Tasks/t2-top-screen-keeps-focus-until-dismissed/WBP_MenuRoot"
HOME = "/Game/Tasks/t2-top-screen-keeps-focus-until-dismissed/WBP_HomeScreen"
DETAIL = "/Game/Tasks/t2-top-screen-keeps-focus-until-dismissed/WBP_DetailScreen"

STACK_NAME = "ScreenStack"
HOME_BUTTON = "Button_HomePrimary"
DETAIL_PRIMARY = "Button_DetailPrimary"
DETAIL_ALTERNATE = "Button_DetailAlternate"

CHECK_IDS = (
    "root_and_screens_are_activatable",
    "real_stack_declares_home_start",
    "declared_focus_buttons_are_focusable",
)


def _defang(value, limit=320):
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = text.replace(START, "<START>").replace(END, "<END>")
    return text[:limit]


def check(cid, passed, detail):
    return {"id": cid, "passed": bool(passed), "detail": _defang(detail)}


def emit(results):
    ordered = [results.get(cid, check(cid, False, "grader did not set result"))
               for cid in CHECK_IDS]
    payload = json.dumps({"checks": ordered}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


def _read_prop(obj, *names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError("property unavailable: %s (%r)" % (names[0], last))


def _load_blueprint(path):
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        return None
    return unreal.load_asset(path)


def _compile_clean(bp):
    if bp is None:
        return False, "missing"
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    compile_fn = getattr(lib, "compile_blueprint", None) if lib is not None else None
    if compile_fn is None:
        raise RuntimeError("BlueprintEditorLibrary.compile_blueprint unavailable")
    compile_fn(bp)
    status = str(_read_prop(bp, "status", "Status"))
    return "UP_TO_DATE" in status.upper(), status


def _generated_class(path):
    try:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(path)
        if cls is not None:
            return cls
    except Exception:  # noqa: BLE001
        pass
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1] + "_C")


def _derives(cls, base_cls):
    if cls is None or base_cls is None:
        return False
    try:
        return bool(unreal.MathLibrary.class_is_child_of(cls, base_cls))
    except Exception:  # noqa: BLE001
        return False


def _tree(bp):
    if bp is None:
        return None
    try:
        return unreal.find_object(bp, "WidgetTree")
    except Exception:  # noqa: BLE001
        return None


def _widget(bp, name):
    tree = _tree(bp)
    if tree is None:
        return None
    try:
        return unreal.find_object(tree, name)
    except Exception:  # noqa: BLE001
        return None


def _path(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_path_name())
    except Exception:  # noqa: BLE001
        return str(obj)


def main():
    results = {}
    if unreal is None:
        for cid in CHECK_IDS:
            results[cid] = check(cid, False, "unreal module unavailable")
        emit(results)
        return

    assets = {path: _load_blueprint(path) for path in (ROOT, HOME, DETAIL)}

    try:
        base = unreal.load_class(None, "/Script/CommonUI.CommonActivatableWidget")
        clean = []
        statuses = []
        derived = []
        for path in (ROOT, HOME, DETAIL):
            ok, status = _compile_clean(assets[path])
            clean.append(ok)
            statuses.append(status)
            derived.append(_derives(_generated_class(path), base))
        passed = all(clean) and all(derived)
        results[CHECK_IDS[0]] = check(
            CHECK_IDS[0], passed,
            "asset_count=%d derived=%s statuses=%s" % (
                sum(assets[p] is not None for p in assets), derived, statuses))
    except Exception as exc:  # agent asset shape/API errors are graded false
        results[CHECK_IDS[0]] = check(CHECK_IDS[0], False, "parent/compile read failed: %r" % exc)

    try:
        root_bp = assets[ROOT]
        stack_type = getattr(unreal, "CommonActivatableWidgetStack", None)
        if root_bp is None or stack_type is None:
            raise RuntimeError("root asset or stack reflection is unavailable")
        named = _widget(root_bp, STACK_NAME)
        # UObject names are unique within the saved WidgetTree outer. Resolving
        # the exact required name and checking its reflected class is therefore
        # the stable UE 5.8 equivalent of counting that declared stack; the
        # protected WidgetTree RootWidget/AllWidgets properties are not exposed
        # to Python in this engine build.
        stacks = [named] if named is not None and isinstance(named, stack_type) else []
        home_cls = _generated_class(HOME)
        declared = _read_prop(named, "root_content_widget_class", "RootContentWidgetClass") \
            if named is not None else None
        named_match = (named is not None and len(stacks) == 1 and
                       _path(named) == _path(stacks[0]))
        declared_home = (declared is not None and home_cls is not None and
                         _path(declared) == _path(home_cls))
        passed = len(stacks) == 1 and named_match and declared_home
        results[CHECK_IDS[1]] = check(
            CHECK_IDS[1], passed,
            "stack_count=%d named_match=%s declared_home=%s" % (
                len(stacks), named_match, declared_home))
    except Exception as exc:
        results[CHECK_IDS[1]] = check(CHECK_IDS[1], False, "stack declaration read failed: %r" % exc)

    try:
        requested = (
            (assets[HOME], HOME_BUTTON),
            (assets[DETAIL], DETAIL_PRIMARY),
            (assets[DETAIL], DETAIL_ALTERNATE),
        )
        observed = []
        for bp, name in requested:
            widget = _widget(bp, name)
            is_button = widget is not None and isinstance(widget, unreal.Button)
            focusable = bool(_read_prop(widget, "is_focusable", "IsFocusable")) if is_button else False
            observed.append((name, is_button, focusable))
        passed = all(is_button and focusable for _, is_button, focusable in observed)
        results[CHECK_IDS[2]] = check(CHECK_IDS[2], passed, "buttons=%s" % (observed,))
    except Exception as exc:
        results[CHECK_IDS[2]] = check(CHECK_IDS[2], False, "button reflection failed: %r" % exc)

    emit(results)


if __name__ == "__main__":
    main()
