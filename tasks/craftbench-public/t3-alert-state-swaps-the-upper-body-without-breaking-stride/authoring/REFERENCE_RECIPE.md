# Disposable reference harvest recipe

Do not author a reference over the live retained baseline.

1. Create and cold-read the retained incomplete four-asset baseline under
   `/Game/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride`.
   Record all four SHA-256 values plus the read-only interface hash under the
   map namespace.
2. Copy the substrate to a fresh short-path disposable workspace using the
   governed substrate-copy seam.
3. In the disposable workspace only, remove the copied four baseline packages
   through the approved recoverable workflow and invoke
   `author_reference.py`, which calls
   `UAlertStrideAssetAuthoring::AuthorAssetSet` with the same final editable
   root, reuses the copied read-only interface package without saving it, and
   passes `bComplete=true`.
4. Run `readback_assets.py --mode reference` in a second fresh editor process and
   the fixed L2I candidate. Require 4/4.
5. Harvest exactly the four editable `.uasset` files into
   `reference/Content/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/`.
   Reject extra files, redirectors, links, or side packages.
6. Prove every reference hash differs where the completed graph/tree changed.
   Recheck that the live retained four baseline hashes and read-only interface
   hash never changed.
7. Production `run_task.py` overlays the harvested reference only into its
   disposable scratch project. It must never copy reference bytes into live
   content.

The reference is asset-only: no native source belongs in the reference overlay.
