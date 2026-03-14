import os
import sys

# Add gui-automation package root to path for tests
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GUI_AUTOMATION_ROOT = os.path.join(REPO_ROOT, "skills", "gui-automation")

if GUI_AUTOMATION_ROOT not in sys.path:
    sys.path.insert(0, GUI_AUTOMATION_ROOT)
