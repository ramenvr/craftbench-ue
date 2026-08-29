"""Author the isolated complete admission AnimBlueprint once."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from author_assets_common import author

author("admission")
