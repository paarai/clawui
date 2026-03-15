"""Allow running ClawUI as `python -m clawui`."""
import sys
from .cli import main

sys.exit(main())
