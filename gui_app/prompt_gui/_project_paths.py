"""Shared project path resolution for all GUI modules."""
import os
import sys

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "..", "Virtual-Coach-main")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
