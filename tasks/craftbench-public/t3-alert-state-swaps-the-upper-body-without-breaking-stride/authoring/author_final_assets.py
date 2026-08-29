"""Author the retained incomplete Alert Stride baseline asset set once."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from author_assets_common import author

author("final")
