"""Author only the committed two-layout final map."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from author_map_common import author


author("final")
