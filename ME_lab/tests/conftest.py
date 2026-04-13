"""Add the app root and shared-core root to sys.path for test imports."""

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
SHARED_ROOT = APP_ROOT.parent / "shared_core"

sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(SHARED_ROOT))
