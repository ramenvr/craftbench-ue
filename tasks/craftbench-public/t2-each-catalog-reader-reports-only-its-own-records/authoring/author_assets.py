"""Create only the protected catalog records for the catalog-reader task.

The C++ helper refuses to overwrite any output. Run this in its own fresh
UnrealEditor-Cmd process, then run introspect_catalog.py in a second process.
"""

import unreal


PREFIX = "CATALOG-ASSETS-AUTHOR"


def fail(message):
    unreal.log_error(f"{PREFIX} ERROR {message}")
    raise RuntimeError(message)


def main():
    helper = getattr(unreal, "CatalogReaderAuthoringLibrary", None)
    if helper is None:
        fail("CatalogReaderAuthoringLibrary is unavailable; build the editor target")
    result = str(helper.create_protected_catalog())
    unreal.log(f"{PREFIX} {result}")
    if not result.startswith("OK CATALOG-AUTHOR SAVED "):
        fail("protected catalog creation failed: " + result)
    unreal.log(f"{PREFIX} COMPLETE")


main()
