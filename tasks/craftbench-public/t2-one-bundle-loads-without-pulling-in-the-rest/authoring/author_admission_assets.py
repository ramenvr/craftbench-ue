"""Create the exact 15 protected bundle-lease assets once, fail closed."""

import unreal


TASK = "t2-one-bundle-loads-without-pulling-in-the-rest"
ROOT = f"/Game/Maps/{TASK}/Records"
RECORDS = (
    ("Quartz", "DA_BundleRecord_Quartz", (
        ("Quartz", "Quartz.Q", 137.125),
        ("Violet", "Quartz.V", -42.375))),
    ("Violet", "DA_BundleRecord_Violet", (
        ("Quartz", "Violet.Q", 803.625),
        ("Violet", "Violet.V", 19.875))),
    ("Amber", "DA_BundleRecord_Amber", (
        ("Quartz", "Amber.Q", -611.25),
        ("Violet", "Amber.V", 271.75))),
)


def fail(message):
    unreal.log_error("BUNDLE-LEASE-ASSET-AUTHOR-ERROR " + message)
    raise RuntimeError(message)


def exact_names():
    names = []
    for stem, record, bundles in RECORDS:
        names.append(record)
        for bundle, _identity, _marker in bundles:
            names.extend((f"DA_{stem}_{bundle}_Payload",
                          f"DA_{stem}_{bundle}_Hidden"))
    return names


def create_data_asset(name, cls):
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", cls)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, ROOT, cls, factory)
    if asset is None or not isinstance(asset, cls):
        fail(f"create_asset failed or wrong class: {ROOT}/{name}")
    return asset


def save_exact(name, asset):
    path = f"{ROOT}/{name}"
    if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
        fail("save failed: " + path)
    reloaded = unreal.EditorAssetLibrary.load_asset(path)
    if reloaded is None or reloaded.get_path_name() != f"{path}.{name}":
        fail("exact readback failed: " + path)
    return reloaded


def main():
    record_cls = getattr(unreal, "BundleLeaseRecord", None)
    payload_cls = getattr(unreal, "BundleLeasePayload", None)
    hidden_cls = getattr(unreal, "BundleLeaseHiddenDependency", None)
    if not record_cls or not payload_cls or not hidden_cls:
        fail("task classes unavailable; build ThirdPersonEditor first")
    existing = [name for name in exact_names()
                if unreal.EditorAssetLibrary.does_asset_exist(f"{ROOT}/{name}")]
    if existing:
        fail("exact output exists; quarantine explicitly before retry: " +
             ",".join(existing))

    authored = {}
    for stem, _record_name, bundles in RECORDS:
        for bundle, identity, marker in bundles:
            hidden_name = f"DA_{stem}_{bundle}_Hidden"
            hidden = create_data_asset(hidden_name, hidden_cls)
            hidden.set_editor_property("authored_marker", marker)
            authored[hidden_name] = save_exact(hidden_name, hidden)

            payload_name = f"DA_{stem}_{bundle}_Payload"
            payload = create_data_asset(payload_name, payload_cls)
            payload.set_editor_property("payload_identity", identity)
            payload.set_editor_property("hidden_dependency", authored[hidden_name])
            authored[payload_name] = save_exact(payload_name, payload)

    for stem, record_name, bundles in RECORDS:
        record = create_data_asset(record_name, record_cls)
        for bundle, _identity, _marker in bundles:
            record.set_editor_property(
                f"{bundle.lower()}_payload",
                authored[f"DA_{stem}_{bundle}_Payload"])
        authored[record_name] = save_exact(record_name, record)

    inventory = [name for name in exact_names()
                 if unreal.EditorAssetLibrary.does_asset_exist(f"{ROOT}/{name}")]
    if inventory != exact_names():
        fail("post-save exact inventory mismatch")
    unreal.log("BUNDLE-LEASE-ASSET-AUTHOR-SAVED "
               "assets=15 primary=3 payload=6 hidden=6 bundles=6")


main()
