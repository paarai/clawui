import os
import sys

# Force tests to import THIS repo's package, not any workspace-global install.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT in sys.path:
    sys.path.remove(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

# Clean previously imported clawui modules that may come from another path.
for mod_name in list(sys.modules):
    if mod_name == "clawui" or mod_name.startswith("clawui."):
        sys.modules.pop(mod_name, None)
