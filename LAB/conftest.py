"""Keep standalone LAB imports compatible with package imports."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
