#!/usr/bin/env python3
"""Main entry point script for TeckoChecker CLI.

This script can be used to run TeckoChecker from the command line.
For production use, install the package and use the 'teckochecker' command.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the CLI
from app.cli.main import run

if __name__ == "__main__":
    run()
