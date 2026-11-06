"""
main.py

Root entry point for cernodata. Delegates execution to src.main.
"""

from __future__ import annotations

import sys
from src.main import main

if __name__ == "__main__":
    main(sys.argv[1:])
