"""Author only the disposable admission map for the catalog-reader task."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from author_map_common import TASK_ID, author_map


author_map(
    f"/Game/__CraftBenchAdmission/{TASK_ID}/L_CatalogReadersAdmission",
    "CatalogReadersAdmissionFunctionalTest",
)
