"""Author the isolated one-fixture Alert Stride admission map once."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from author_map_common import author

author("admission")
