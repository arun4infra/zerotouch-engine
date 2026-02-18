#!/usr/bin/env python3
"""ZTP CLI entry point for development"""
import sys
from pathlib import Path

# Add libs and cli to path
libs_path = Path(__file__).parent / "libs"
cli_path = Path(__file__).parent / "libs" / "cli"
sys.path.insert(0, str(libs_path))
sys.path.insert(0, str(cli_path))

from ztp_cli.core_commands import app

if __name__ == "__main__":
    app()
